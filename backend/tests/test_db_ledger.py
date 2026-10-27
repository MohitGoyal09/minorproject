from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.accounting import Tenant, Account, JournalEntry, AuditLog
from app.schemas.accounting import (
    ProposedJournalEntry,
    ProposedJournalLine,
    EntryType,
    TransactionType,
)
from app.db.seed_accounts import seed_standard_accounts
from app.engine.ledger import post_journal_entry, generate_trial_balance
from app.engine.invariants import InvariantViolation


@pytest.fixture
def db_session():
    """Provides a fresh, isolated in-memory SQLite database for each test."""
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_post_and_trial_balance_reconciliation(db_session):
    """
    End-to-End Test for the Golden Furniture Invoice:
    1. Create Tenant and seed Chart of Accounts.
    2. Post double-entry transaction:
       - Furniture A/c: Dr 50,000
       - Input CGST: Dr 4,500
       - Input SGST: Dr 4,500
       - Creditor A/c: Cr 59,000
    3. Generate Trial Balance from posted ledger.
    4. Assert Debits == Credits == 59,000.00 with exact Decimal precision.
    """
    # 1. Setup Tenant
    tenant = Tenant(name="Modern Tech Solutions Pvt Ltd", gstin="07BBBBB1111B1Z2", currency="INR")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    # 2. Seed COA
    seeded_count = seed_standard_accounts(db_session, tenant.id)
    assert seeded_count > 10

    # 3. Create Golden Proposal
    proposal = ProposedJournalEntry(
        source_document_id="doc_001",
        invoice_number="INV-2026-001",
        entry_date=date(2026, 10, 15),
        transaction_type=TransactionType.ASSET_ACQUISITION_CREDIT,
        narration="Purchase of office furniture on credit from ABC Furniture Mart",
        reasoning="Capitalized under asset policy (>10k threshold) with eligible ITC.",
        lines=[
            ProposedJournalLine(
                account_code="1050",
                account_name="Office Furniture & Fixtures",
                entry_type=EntryType.DEBIT,
                amount=Decimal("50000.00"),
            ),
            ProposedJournalLine(
                account_code="1081",
                account_name="Input CGST A/c",
                entry_type=EntryType.DEBIT,
                amount=Decimal("4500.00"),
            ),
            ProposedJournalLine(
                account_code="1082",
                account_name="Input SGST A/c",
                entry_type=EntryType.DEBIT,
                amount=Decimal("4500.00"),
            ),
            ProposedJournalLine(
                account_code="2010",
                account_name="Accounts Payable / Creditors",
                entry_type=EntryType.CREDIT,
                amount=Decimal("59000.00"),
            ),
        ],
    )

    # 4. Post Entry
    posted_entry = post_journal_entry(db_session, tenant.id, proposal, posted_by="TEST_RUNNER")
    assert posted_entry.id is not None
    assert posted_entry.status == "POSTED"

    # Verify audit log was created
    audit = db_session.query(AuditLog).filter(AuditLog.entity_id == posted_entry.id).first()
    assert audit is not None
    assert audit.action == "POST"

    # 5. Generate Trial Balance
    tb = generate_trial_balance(db_session, tenant.id, as_of_date=date(2026, 10, 31))
    
    assert tb.is_balanced is True
    assert tb.total_debit_balance == Decimal("59000.00")
    assert tb.total_credit_balance == Decimal("59000.00")
    assert len(tb.rows) == 4

    # Check individual account balances
    row_map = {r.account_code: r for r in tb.rows}
    assert row_map["1050"].closing_balance == Decimal("50000.00")
    assert row_map["1050"].balance_type == "DEBIT"
    assert row_map["1081"].closing_balance == Decimal("4500.00")
    assert row_map["1081"].balance_type == "DEBIT"
    assert row_map["1082"].closing_balance == Decimal("4500.00")
    assert row_map["1082"].balance_type == "DEBIT"
    assert row_map["2010"].closing_balance == Decimal("59000.00")
    assert row_map["2010"].balance_type == "CREDIT"


def test_post_unbalanced_entry_rejected(db_session):
    """Verify that posting an unbalanced entry raises InvariantViolation and rolls back."""
    tenant = Tenant(name="Test Co", gstin="07XXXXX9999X1Z1")
    db_session.add(tenant)
    db_session.commit()
    seed_standard_accounts(db_session, tenant.id)

    imbalanced_proposal = ProposedJournalEntry(
        source_document_id="doc_002",
        invoice_number="INV-BAD",
        entry_date=date(2026, 10, 15),
        transaction_type=TransactionType.EXPENSE_OFFICE_CREDIT,
        narration="Bad entry",
        reasoning="Test",
        lines=[
            ProposedJournalLine(
                account_code="5010",
                account_name="Office Supplies & Stationery",
                entry_type=EntryType.DEBIT,
                amount=Decimal("1000.00"),
            ),
            ProposedJournalLine(
                account_code="2010",
                account_name="Accounts Payable / Creditors",
                entry_type=EntryType.CREDIT,
                amount=Decimal("1050.00"),  # 50 difference
            ),
        ],
    )

    with pytest.raises(InvariantViolation) as exc_info:
        post_journal_entry(db_session, tenant.id, imbalanced_proposal)

    assert "Double-entry imbalance" in str(exc_info.value)
    # Ensure nothing was saved
    assert db_session.query(JournalEntry).count() == 0


def test_post_invalid_account_code_rejected(db_session):
    """Verify that posting to an account that doesn't exist in the COA is rejected."""
    tenant = Tenant(name="Test Co 2", gstin="07YYYYY8888Y1Z2")
    db_session.add(tenant)
    db_session.commit()
    seed_standard_accounts(db_session, tenant.id)

    invalid_coa_proposal = ProposedJournalEntry(
        source_document_id="doc_003",
        invoice_number="INV-UNKNOWN-ACC",
        entry_date=date(2026, 10, 15),
        transaction_type=TransactionType.EXPENSE_OFFICE_CREDIT,
        narration="Bad account code",
        reasoning="Test",
        lines=[
            ProposedJournalLine(
                account_code="8888",  # Not in COA
                account_name="Alien Expense A/c",
                entry_type=EntryType.DEBIT,
                amount=Decimal("500.00"),
            ),
            ProposedJournalLine(
                account_code="2010",
                account_name="Accounts Payable / Creditors",
                entry_type=EntryType.CREDIT,
                amount=Decimal("500.00"),
            ),
        ],
    )

    with pytest.raises(InvariantViolation) as exc_info:
        post_journal_entry(db_session, tenant.id, invalid_coa_proposal)

    assert "does not exist or is inactive" in str(exc_info.value)
    assert db_session.query(JournalEntry).count() == 0
