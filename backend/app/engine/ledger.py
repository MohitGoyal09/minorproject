import re
from decimal import Decimal
from datetime import date, datetime, timezone
from typing import List, Dict, Optional
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
    ValidationCheckStatus,
)
from app.schemas.invoice import ExtractedInvoice
from app.schemas.reports import LedgerAccountBalance, TrialBalanceReport
from app.engine.invariants import (
    validate_double_entry_invariants,
    validate_chart_of_accounts,
    validate_journal_invariants_detailed,
    InvariantViolation,
    DuplicateInvoiceViolation,
)


def normalise_invoice_number(value: str) -> str:
    """Case and whitespace are not part of an invoice number's identity."""
    return re.sub(r"\s+", "", (value or "")).upper()


def supplier_identity(invoice: ExtractedInvoice) -> str:
    """GSTIN identifies a supplier; fall back to a normalised name."""
    return (invoice.vendor_gstin or invoice.vendor_name or "").strip().upper()


def find_duplicate_entry(
    db: Session,
    tenant_id: str,
    invoice_number: str,
    invoice: Optional[ExtractedInvoice] = None,
) -> Optional[JournalEntry]:
    """A duplicate is the same supplier issuing the same invoice number again.

    Cross-vendor reuse of INV-001 is legitimate. When the supplier is unknown on
    either side, fall back to number-only matching rather than allowing a
    possible double post.
    """
    target = normalise_invoice_number(invoice_number)
    posted = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.status == EntryPostingStatus.POSTED,
        )
        .all()
    )
    for entry in posted:
        if normalise_invoice_number(entry.invoice_number) != target:
            continue
        if invoice is None or entry.document is None or entry.document.invoice is None:
            return entry
        if supplier_identity(entry.document.invoice) == supplier_identity(invoice):
            return entry
    return None


def post_journal_entry(
    db: Session,
    tenant_id: str,
    proposal: ProposedJournalEntry,
    posted_by: str = "SYSTEM_AUTOMATION",
    allow_review_override: bool = False,
    invoice: Optional[ExtractedInvoice] = None,
) -> JournalEntry:
    """
    Atomically posts a validated journal entry into the authoritative ledger.
    Enforces:
    1. Duplicate invoice posting prevention.
    2. Zero tolerance for double-entry imbalance.
    3. All referenced accounts exist and are active in the tenant's Chart of Accounts.
    4. Non-negative amounts.
    5. Human approval verification if review is required.
    """
    # 1. Duplicate Invoice Posting Prevention (supplier + normalised number)
    existing_entry = find_duplicate_entry(db, tenant_id, proposal.invoice_number, invoice)
    if existing_entry:
        raise DuplicateInvoiceViolation(
            f"Duplicate Posting Blocked: Invoice #{proposal.invoice_number} has already been posted to the ledger (Entry ID: {existing_entry.id})."
        )

    # 2. Detailed Journal Invariants & COA Checks
    tenant_accounts = db.query(Account).filter(Account.tenant_id == tenant_id, Account.is_active == True).all()
    account_code_map = {acc.code: acc for acc in tenant_accounts}
    active_codes = set(account_code_map.keys())

    checks = validate_journal_invariants_detailed(
        entry=proposal,
        active_account_codes=active_codes,
        invoice=invoice,
    )

    failures = [c.explanation for c in checks if c.status == ValidationCheckStatus.FAIL]
    if failures:
        raise InvariantViolation(f"Cannot post invalid journal entry: {'; '.join(failures)}")

    # 3. Human Approval Gate
    # If the proposal was flagged for review (e.g. ambiguous classification, warnings),
    # an automated system cannot post it without explicit human approval.
    if proposal.requires_human_review and posted_by == "SYSTEM_AUTOMATION" and not allow_review_override:
        raise InvariantViolation(
            f"Posting Gate Blocked: Entry for invoice #{proposal.invoice_number} requires human review: {'; '.join(proposal.review_reasons)}"
        )

    # 4. Atomic Database Transaction: Post Entry and Lines
    try:
        db_entry = JournalEntry(
            tenant_id=tenant_id,
            document_id=proposal.source_document_id if proposal.source_document_id and proposal.source_document_id != "doc_simulated" else None,
            invoice_number=proposal.invoice_number,
            entry_date=proposal.entry_date,
            transaction_type=proposal.transaction_type,
            narration=proposal.narration,
            status=EntryPostingStatus.POSTED,
            posted_at=datetime.now(timezone.utc)
        )
        db.add(db_entry)
        db.flush()  # Generates db_entry.id

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

        # Audit trail recording
        audit_record = AuditLog(
            tenant_id=tenant_id,
            entity_name="JournalEntry",
            entity_id=db_entry.id,
            action="POST",
            performed_by=posted_by,
            details=f"Posted entry for invoice #{proposal.invoice_number}. Total Debits/Credits: INR {proposal.total_debits}"
        )
        db.add(audit_record)

        db.commit()
        db.refresh(db_entry)
        return db_entry
    except Exception as e:
        db.rollback()
        raise e


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

    balances: Dict[str, Dict[str, Decimal]] = {
        acc_id: {"debit": Decimal("0.00"), "credit": Decimal("0.00")} for acc_id in account_map
    }

    for line in lines:
        if line.entry_type == EntryType.DEBIT:
            balances[line.account_id]["debit"] += Decimal(str(line.amount))
        else:
            balances[line.account_id]["credit"] += Decimal(str(line.amount))

    tb_rows: List[LedgerAccountBalance] = []
    for acc_id, totals in balances.items():
        acc = account_map[acc_id]
        tot_dr = totals["debit"].quantize(Decimal("0.01"))
        tot_cr = totals["credit"].quantize(Decimal("0.01"))

        if tot_dr == Decimal("0.00") and tot_cr == Decimal("0.00"):
            continue

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

    tb_rows.sort(key=lambda x: x.account_code)
    return TrialBalanceReport.from_rows(as_of_date=as_of_date, rows=tb_rows)
