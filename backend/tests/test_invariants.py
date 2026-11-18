from decimal import Decimal
from datetime import date
import pytest

from app.schemas.invoice import ExtractedInvoice, InvoiceLineItem, TaxBreakdown, ExtractionConfidence
from app.schemas.accounting import (
    ProposedJournalEntry,
    ProposedJournalLine,
    EntryType,
    TransactionType,
)
from app.engine.invariants import (
    validate_double_entry_invariants,
    validate_chart_of_accounts,
    validate_invoice_arithmetic,
)


def test_valid_double_entry_balanced():
    """Verify that a correctly balanced entry with exact decimals passes validation."""
    entry = ProposedJournalEntry(
        source_document_id="doc_001",
        invoice_number="INV-2026-001",
        entry_date=date(2026, 10, 15),
        transaction_type=TransactionType.ASSET_ACQUISITION_CREDIT,
        narration="Purchase of office furniture on credit from ABC Furniture Mart",
        reasoning="Capitalized under asset capitalization policy (>10k threshold) with eligible ITC.",
        lines=[
            ProposedJournalLine(
                account_code="1050",
                account_name="Office Furniture A/c",
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
                account_name="ABC Furniture Mart (Creditor)",
                entry_type=EntryType.CREDIT,
                amount=Decimal("59000.00"),
            ),
        ],
    )

    is_valid, errors = validate_double_entry_invariants(entry)
    assert is_valid is True
    assert len(errors) == 0
    assert entry.total_debits == Decimal("59000.00")
    assert entry.total_credits == Decimal("59000.00")
    assert entry.is_balanced is True


def test_unbalanced_double_entry_rejected():
    """Verify that an unbalanced entry is caught and rejected."""
    entry = ProposedJournalEntry(
        source_document_id="doc_002",
        invoice_number="INV-2026-002",
        entry_date=date(2026, 10, 15),
        transaction_type=TransactionType.EXPENSE_OFFICE_CREDIT,
        narration="Stationery purchase",
        reasoning="Office expense.",
        lines=[
            ProposedJournalLine(
                account_code="5010",
                account_name="Office Supplies Expense A/c",
                entry_type=EntryType.DEBIT,
                amount=Decimal("1000.00"),
            ),
            ProposedJournalLine(
                account_code="2010",
                account_name="Vendor Payable A/c",
                entry_type=EntryType.CREDIT,
                amount=Decimal("1200.00"),  # Imbalance of 200
            ),
        ],
    )

    is_valid, errors = validate_double_entry_invariants(entry)
    assert is_valid is False
    assert any("Double-entry imbalance" in err for err in errors)


def test_chart_of_accounts_validation():
    """Verify that proposed accounts must exist in active Chart of Accounts."""
    active_accounts = {"1050", "1081", "1082", "2010"}
    
    entry = ProposedJournalEntry(
        source_document_id="doc_003",
        invoice_number="INV-2026-003",
        entry_date=date(2026, 10, 15),
        transaction_type=TransactionType.ASSET_ACQUISITION_CREDIT,
        narration="Furniture purchase",
        reasoning="Test",
        lines=[
            ProposedJournalLine(
                account_code="9999",  # Non-existent account code
                account_name="Unknown Fictitious A/c",
                entry_type=EntryType.DEBIT,
                amount=Decimal("100.00"),
            ),
            ProposedJournalLine(
                account_code="2010",
                account_name="ABC Furniture Mart",
                entry_type=EntryType.CREDIT,
                amount=Decimal("100.00"),
            ),
        ],
    )

    is_valid, errors = validate_chart_of_accounts(entry, active_accounts)
    assert is_valid is False
    assert any("does not exist or is inactive" in err for err in errors)


def test_invoice_arithmetic_heuristics_valid():
    """Verify that consistent invoice math passes heuristic validation."""
    invoice = ExtractedInvoice(
        invoice_number="INV-2026-001",
        invoice_date=date(2026, 10, 15),
        vendor_name="ABC Furniture Mart",
        subtotal=Decimal("50000.00"),
        total_discount=Decimal("0.00"),
        total_tax=Decimal("9000.00"),
        grand_total=Decimal("59000.00"),
        line_items=[
            InvoiceLineItem(
                description="Executive Desk",
                quantity=Decimal("2.00"),
                unit_price=Decimal("15000.00"),
                total_amount=Decimal("30000.00"),
                tax_rate_percent=Decimal("18.00"),
                tax_amount=Decimal("5400.00"),
            ),
            InvoiceLineItem(
                description="Ergonomic Chairs",
                quantity=Decimal("4.00"),
                unit_price=Decimal("5000.00"),
                total_amount=Decimal("20000.00"),
                tax_rate_percent=Decimal("18.00"),
                tax_amount=Decimal("3600.00"),
            ),
        ],
        taxes=[
            TaxBreakdown(tax_type="CGST", rate_percent=Decimal("9.00"), taxable_amount=Decimal("50000.00"), tax_amount=Decimal("4500.00")),
            TaxBreakdown(tax_type="SGST", rate_percent=Decimal("9.00"), taxable_amount=Decimal("50000.00"), tax_amount=Decimal("4500.00")),
        ],
        confidence=ExtractionConfidence.HIGH,
    )

    is_valid, warnings = validate_invoice_arithmetic(invoice)
    assert is_valid is True
    assert len(warnings) == 0


def test_invoice_arithmetic_heuristics_catches_errors():
    """Verify that arithmetic inconsistencies are detected and flagged."""
    corrupted_invoice = ExtractedInvoice(
        invoice_number="INV-CORRUPT",
        invoice_date=date(2026, 10, 15),
        vendor_name="Glitch Tech",
        subtotal=Decimal("1000.00"),
        total_tax=Decimal("180.00"),
        grand_total=Decimal("1500.00"),  # 1000 + 180 should be 1180, not 1500
        line_items=[
            InvoiceLineItem(
                description="Faulty Widget",
                quantity=Decimal("2.00"),
                unit_price=Decimal("400.00"),
                total_amount=Decimal("1000.00"),  # 2 * 400 is 800, not 1000
            )
        ],
    )

    is_valid, warnings = validate_invoice_arithmetic(corrupted_invoice)
    assert is_valid is False
    assert len(warnings) >= 2
    assert any("Line item 1 ('Faulty Widget'): Math mismatch" in w for w in warnings)
    assert any("Grand total discrepancy" in w for w in warnings)


def test_separately_stated_discount_is_not_a_subtotal_discrepancy():
    """Subtotal is gross; line totals are net of discount. 4000 - 500 == 3500 is correct."""
    invoice = ExtractedInvoice(
        invoice_number="INV-DISC-001",
        invoice_date=date(2026, 10, 20),
        vendor_name="Delhi Paper & Print Hub",
        vendor_gstin="07DDDDD3333D1Z9",
        subtotal=Decimal("4000.00"),
        total_tax=Decimal("420.00"),
        total_discount=Decimal("500.00"),
        grand_total=Decimal("3920.00"),
        line_items=[
            InvoiceLineItem(
                description="A4 Printing Paper (Cartons)",
                hsn_sac="4802",
                quantity=Decimal("10"),
                unit_price=Decimal("400.00"),
                discount_amount=Decimal("500.00"),
                total_amount=Decimal("3500.00"),
            )
        ],
    )

    is_valid, warnings = validate_invoice_arithmetic(invoice)

    assert is_valid, warnings
