"""Regression tests for identity extraction (F-15, F-16)."""

from datetime import date
from decimal import Decimal

from app.engine.heuristics import HeuristicExtractor
from app.engine.invariants import validate_invoice_identity
from app.schemas.invoice import ExtractedInvoice, InvoiceLineItem


def test_a_due_date_is_never_used_as_the_invoice_date():
    text = "Supplier: ABC Ltd\nDue Date: 2026-11-15\nGSTIN:07AAAAA0000A1Z5"

    invoice_date, due_date = HeuristicExtractor.extract_dates(text)

    assert invoice_date == date.today()
    assert due_date == date(2026, 11, 15)


def test_a_written_month_date_is_parsed():
    invoice_date, _ = HeuristicExtractor.extract_dates("Invoice Date: 15-Oct-2026")

    assert invoice_date == date(2026, 10, 15)


def test_a_slash_date_with_a_day_above_twelve_is_parsed():
    invoice_date, _ = HeuristicExtractor.extract_dates("Invoice Date: 10/15/2026")

    assert invoice_date == date(2026, 10, 15)


def test_invoice_number_punctuation_is_preserved():
    assert HeuristicExtractor.extract_invoice_number("Invoice No: INV.2026.001") == "INV.2026.001"


def test_invoice_number_spaces_are_preserved():
    assert HeuristicExtractor.extract_invoice_number("Invoice No: INV 2026 001") == "INV 2026 001"


def test_a_document_title_is_not_a_vendor_name():
    vendor, _ = HeuristicExtractor.extract_entity_names("# Purchase Order\nInvoice No: X-1\n")

    assert vendor == "Unknown Vendor"


def test_buyer_first_gstin_does_not_become_the_vendor():
    text = (
        "Buyer GSTIN: 07BBBBB1111B1Z2\n"
        "Supplier GSTIN: 27AAAAA0000A1Z5\n"
    )

    tags = HeuristicExtractor.extract_gstin_tags(text)

    assert tags["buyer_gstin"] == "07BBBBB1111B1Z2"
    assert tags["vendor_gstin"] == "27AAAAA0000A1Z5"


def test_a_lone_gstin_is_not_assigned_to_both_roles():
    tags = HeuristicExtractor.extract_gstin_tags("Buyer GSTIN: 07BBBBB1111B1Z2")

    assert tags["buyer_gstin"] == "07BBBBB1111B1Z2"
    assert tags["vendor_gstin"] is None


# --- identity invariants ---------------------------------------------------

def build_invoice(**overrides):
    values = dict(
        invoice_number="INV-1",
        invoice_date=date(2026, 11, 19),
        vendor_name="ABC Furniture Mart",
        vendor_gstin="07AAAAA0000A1Z5",
        buyer_gstin="07BBBBB1111B1Z2",
        subtotal=Decimal("1000"),
        total_tax=Decimal("180"),
        grand_total=Decimal("1180"),
        line_items=[InvoiceLineItem(description="Desk", quantity=Decimal("1"),
                                    unit_price=Decimal("1000"), total_amount=Decimal("1000"))],
    )
    values.update(overrides)
    return ExtractedInvoice(**values)


def test_an_unknown_invoice_number_fails_identity():
    results = validate_invoice_identity(build_invoice(invoice_number="UNKNOWN_INV"))

    assert any(r.status.value == "FAIL" for r in results)


def test_an_unknown_vendor_fails_identity():
    results = validate_invoice_identity(build_invoice(vendor_name="Unknown Vendor"))

    assert any(r.status.value == "FAIL" for r in results)


def test_the_same_gstin_on_both_sides_fails_identity():
    results = validate_invoice_identity(build_invoice(buyer_gstin="07AAAAA0000A1Z5"))

    assert any("GSTIN" in r.check_name and r.status.value == "FAIL" for r in results)


def test_a_complete_identity_passes():
    results = validate_invoice_identity(build_invoice())

    assert all(r.status.value == "PASS" for r in results)
