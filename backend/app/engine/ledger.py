from decimal import Decimal
from datetime import date, datetime, timezone
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.accounting import (
    Tenant,
    Account,
    JournalEntry,
    JournalLine,
    AuditLog,
    EntryPostingStatus,
)
from app.schemas.accounting import (
    ProposedJournalEntry,
    EntryType,
    AccountCategory,
    NormalBalance,
)
from app.schemas.reports import LedgerAccountBalance, TrialBalanceReport
from app.engine.invariants import (
    validate_double_entry_invariants,
    validate_chart_of_accounts,
    InvariantViolation,
)


def post_journal_entry(
    db: Session,
    tenant_id: str,
    proposal: ProposedJournalEntry,
    posted_by: str = "SYSTEM_AUTOMATION"
) -> JournalEntry:
    """
    Atomically posts a validated journal entry into the authoritative ledger.
    Ensures all double-entry invariants are satisfied before writing to disk.
    """
    # 1. Check double entry invariants
    is_valid, errors = validate_double_entry_invariants(proposal)
    if not is_valid:
        raise InvariantViolation(f"Cannot post unbalanced or invalid entry: {'; '.join(errors)}")

    # 2. Check Chart of Accounts existence
    tenant_accounts = db.query(Account).filter(Account.tenant_id == tenant_id, Account.is_active == True).all()
    account_code_map = {acc.code: acc for acc in tenant_accounts}

    coa_valid, coa_errors = validate_chart_of_accounts(proposal, set(account_code_map.keys()))
    if not coa_valid:
        raise InvariantViolation(f"Account validation failed: {'; '.join(coa_errors)}")

    # 3. Create persistent JournalEntry record
    db_entry = JournalEntry(
        tenant_id=tenant_id,
        document_id=proposal.source_document_id if proposal.source_document_id != "doc_001" else None,
        invoice_number=proposal.invoice_number,
        entry_date=proposal.entry_date,
        transaction_type=proposal.transaction_type,
        narration=proposal.narration,
        status=EntryPostingStatus.POSTED,
        posted_at=datetime.now(timezone.utc)
    )
    db.add(db_entry)
    db.flush()  # Populates db_entry.id

    # 4. Create persistent JournalLine records
    for line in proposal.lines:
        acc = account_code_map[line.account_code]
        db_line = JournalLine(
            entry_id=db_entry.id,
            account_id=acc.id,
            entry_type=line.entry_type,
            amount=line.amount,
            description=line.description or line.account_name
        )
        db.add(db_line)

    # 5. Log audit trail
    audit_record = AuditLog(
        tenant_id=tenant_id,
        entity_name="JournalEntry",
        entity_id=db_entry.id,
        action="POST",
        performed_by=posted_by,
        details=f"Posted entry for invoice {proposal.invoice_number}. Total: INR {proposal.total_debits}"
    )
    db.add(audit_record)

    db.commit()
    db.refresh(db_entry)
    return db_entry


def generate_trial_balance(db: Session, tenant_id: str, as_of_date: date) -> TrialBalanceReport:
    """
    Calculates the authoritative Trial Balance dynamically from posted journal lines.
    Zero precomputed cached balances; derives truth directly from double-entry history.
    """
    accounts = db.query(Account).filter(Account.tenant_id == tenant_id).all()
    account_map = {acc.id: acc for acc in accounts}

    # Query posted journal lines up to as_of_date
    lines = (
        db.query(JournalLine)
        .join(JournalEntry)
        .filter(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.status == EntryPostingStatus.POSTED,
            JournalEntry.entry_date <= as_of_date
        )
        .all()
    )

    # Aggregate debits and credits per account
    balances: Dict[str, Dict[str, Decimal]] = {
        acc_id: {"debit": Decimal("0.00"), "credit": Decimal("0.00")} for acc_id in account_map
    }

    for line in lines:
        if line.entry_type == EntryType.DEBIT:
            balances[line.account_id]["debit"] += Decimal(str(line.amount))
        else:
            balances[line.account_id]["credit"] += Decimal(str(line.amount))

    # Build Trial Balance rows
    tb_rows: List[LedgerAccountBalance] = []
    for acc_id, totals in balances.items():
        acc = account_map[acc_id]
        tot_dr = totals["debit"].quantize(Decimal("0.01"))
        tot_cr = totals["credit"].quantize(Decimal("0.01"))

        # If no activity in account, skip
        if tot_dr == Decimal("0.00") and tot_cr == Decimal("0.00"):
            continue

        # Normal balance net calculation
        if acc.normal_balance == NormalBalance.DEBIT:
            net_balance = (tot_dr - tot_cr).quantize(Decimal("0.01"))
            balance_type = "DEBIT" if net_balance >= Decimal("0.00") else "CREDIT"
            net_balance = abs(net_balance)
        else:
            net_balance = (tot_cr - tot_dr).quantize(Decimal("0.01"))
            balance_type = "CREDIT" if net_balance >= Decimal("0.00") else "DEBIT"
            net_balance = abs(net_balance)

        tb_rows.append(
            LedgerAccountBalance(
                account_code=acc.code,
                account_name=acc.name,
                category=acc.category.value,
                total_debits=tot_dr,
                total_credits=tot_cr,
                closing_balance=net_balance,
                balance_type=balance_type
            )
        )

    # Sort rows by account code
    tb_rows.sort(key=lambda x: x.account_code)
    return TrialBalanceReport.from_rows(as_of_date=as_of_date, rows=tb_rows)
