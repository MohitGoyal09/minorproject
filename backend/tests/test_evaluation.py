"""Tests for the ground-truth evaluation report."""

from datetime import date
from decimal import Decimal

from app.schemas.invoice import ExtractedInvoice, InvoiceLineItem
from app.eval.evaluator import evaluate_dataset, score_invoice


def build_invoice(**overrides):
    values = dict(
        invoice_number="INV-TEST-001",
        invoice_date=date(2026, 10, 15),
        due_date=date(2026, 11, 15),
        vendor_name="ABC Furniture Mart",
        vendor_gstin="07AAAAA0000A1Z5",
        buyer_name="Modern Tech Solutions Pvt Ltd",
        buyer_gstin="07BBBBB1111B1Z2",
        place_of_supply="Delhi (07)",
        subtotal=Decimal("15000.00"),
        total_tax=Decimal("2700.00"),
        total_discount=Decimal("0.00"),
        grand_total=Decimal("17700.00"),
        line_items=[
            InvoiceLineItem(
                description="Executive Wooden Desk",
                hsn_sac="9403",
                quantity=Decimal("1"),
                unit_price=Decimal("15000.00"),
                discount_amount=Decimal("0.00"),
                total_amount=Decimal("15000.00"),
            )
        ],
    )
    values.update(overrides)
    return ExtractedInvoice(**values)


def build_ground_truth():
    return {
        "invoice_number": "INV-TEST-001",
        "invoice_date": "2026-10-15",
        "due_date": "2026-11-15",
        "vendor_name": "ABC Furniture Mart",
        "vendor_gstin": "07AAAAA0000A1Z5",
        "buyer_name": "Modern Tech Solutions Pvt Ltd",
        "buyer_gstin": "07BBBBB1111B1Z2",
        "place_of_supply": "Delhi (07)",
        "subtotal": 15000.0,
        "total_tax": 2700.0,
        "total_discount": 0.0,
        "grand_total": 17700.0,
        "line_items": [
            {
                "description": "Executive Wooden Desk",
                "hsn_sac": "9403",
                "quantity": 1.0,
                "unit_price": 15000.0,
                "discount_amount": 0.0,
                "total_amount": 15000.0,
            }
        ],
        "accounting_ground_truth": {
            "journal_lines": [
                {"account_code": "1050", "entry_type": "DEBIT", "amount": 15000.0},
                {"account_code": "1081", "entry_type": "DEBIT", "amount": 1350.0},
                {"account_code": "1082", "entry_type": "DEBIT", "amount": 1350.0},
                {"account_code": "2010", "entry_type": "CREDIT", "amount": 17700.0},
            ]
        },
    }


def proposal_for(gt):
    from app.schemas.accounting import ProposedJournalEntry, ProposedJournalLine, EntryType, TransactionType

    lines = [
        ProposedJournalLine(
            account_code=line["account_code"],
            account_name=line["account_code"],
            entry_type=EntryType(line["entry_type"]),
            amount=Decimal(str(line["amount"])),
        )
        for line in gt["accounting_ground_truth"]["journal_lines"]
    ]
    return ProposedJournalEntry(
        source_document_id="doc_evaluation",
        invoice_number=gt["invoice_number"],
        entry_date=date(2026, 10, 15),
        transaction_type=TransactionType.ASSET_ACQUISITION_CREDIT,
        narration="test",
        reasoning="test",
        lines=lines,
    )


# --- scoring --------------------------------------------------------------

def test_a_correct_extraction_scores_one_hundred_percent():
    gt = build_ground_truth()

    result = score_invoice(build_invoice(), gt, proposal_for(gt))

    assert result.accuracy == 1.0
    assert result.is_exact is True
    assert result.failed_checks == []


def test_a_wrong_total_is_reported_as_a_failed_check():
    gt = build_ground_truth()

    result = score_invoice(build_invoice(grand_total=Decimal("17000.00")), gt, proposal_for(gt))

    assert result.is_exact is False
    assert result.accuracy < 1.0
    assert any("grand_total" in check for check in result.failed_checks)


def test_a_missing_line_item_lowers_line_item_recall():
    gt = build_ground_truth()

    result = score_invoice(build_invoice(line_items=[]), gt, proposal_for(gt))

    assert result.is_exact is False
    assert result.line_items_expected == 1
    assert result.line_items_extracted == 0


def test_journal_lines_are_compared_without_regard_to_order():
    gt = build_ground_truth()
    proposal = proposal_for(gt)
    proposal.lines.reverse()

    result = score_invoice(build_invoice(), gt, proposal)

    assert result.journal_matched == len(gt["accounting_ground_truth"]["journal_lines"])


def test_a_wrong_journal_account_is_detected():
    gt = build_ground_truth()
    proposal = proposal_for(gt)
    proposal.lines[0].account_code = "9999"

    result = score_invoice(build_invoice(), gt, proposal)

    assert result.journal_matched == 3
    assert result.is_exact is False


# --- full dataset ---------------------------------------------------------

def test_dataset_report_covers_every_sample_invoice():
    report = evaluate_dataset()

    assert report.invoice_count == 4
    numbers = sorted(row.invoice_number for row in report.rows)
    assert numbers == ["INV-2026-001", "INV-2026-002", "INV-2026-003", "NOS/26-27/0418"]


def test_dataset_report_reproduces_known_totals():
    report = evaluate_dataset()
    totals = {row.invoice_number: row.actual["grand_total"] for row in report.rows}

    assert totals["INV-2026-001"] == "59000.00"
    assert totals["INV-2026-002"] == "14160.00"
    assert totals["INV-2026-003"] == "3920.00"
    assert totals["NOS/26-27/0418"] == "52430.00"


def test_dataset_report_renders_markdown():
    report = evaluate_dataset()

    markdown = report.to_markdown()

    assert "| Invoice |" in markdown
    assert "Field accuracy" in markdown


def test_every_ground_truth_gstin_is_well_formed():
    """Guards the sample data: a 16-character GSTIN is unparseable by design."""
    import json
    import re

    from app.eval.evaluator import GROUND_TRUTH_DIR

    pattern = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$")
    for path in sorted(GROUND_TRUTH_DIR.glob("*.json")):
        ground_truth = json.loads(path.read_text())
        assert pattern.match(ground_truth["vendor_gstin"]), path.name


def test_cloud_subscription_is_expensed_not_capitalized():
    from app.engine.interpreter import AccountingInterpreter

    invoice = build_invoice(
        vendor_name="CloudGrid Technologies India",
        vendor_gstin="27CCCCC2222C1Z8",
        subtotal=Decimal("12000.00"),
        total_tax=Decimal("2160.00"),
        grand_total=Decimal("14160.00"),
        line_items=[
            InvoiceLineItem(
                description="Dedicated Cloud Server (Monthly)",
                hsn_sac="998315",
                quantity=Decimal("1"),
                unit_price=Decimal("12000.00"),
                total_amount=Decimal("12000.00"),
            )
        ],
    )

    proposal = AccountingInterpreter.interpret_invoice(invoice, document_id="doc_test")
    codes = {line.account_code for line in proposal.lines}

    assert "5020" in codes, codes
    assert "1060" not in codes, codes


def test_every_sample_invoice_matches_its_ground_truth_exactly():
    report = evaluate_dataset()

    assert report.exact_invoices == 4, report.to_markdown()
    assert report.overall_accuracy == 1.0
