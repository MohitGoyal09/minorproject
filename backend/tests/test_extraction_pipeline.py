import os
import json
from decimal import Decimal
import pytest

from app.engine.ingestion import DocumentIngestionService

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
INVOICES_DIR = os.path.join(DATA_DIR, "sample_invoices")
GROUND_TRUTH_DIR = os.path.join(DATA_DIR, "ground_truth")


def load_ground_truth(invoice_id: str) -> dict:
    gt_path = os.path.join(GROUND_TRUTH_DIR, f"{invoice_id}.json")
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_extract_furniture_invoice_e2e():
    """
    Tests end-to-end extraction and table correction on the Golden Furniture Invoice.
    Compares against ground-truth annotations.
    """
    pdf_path = os.path.join(INVOICES_DIR, "INV-2026-001.pdf")
    gt = load_ground_truth("INV-2026-001")

    extracted = DocumentIngestionService.process_pdf_invoice(pdf_path)

    # 1. Header Metadata Checks
    assert extracted.invoice_number == gt["invoice_number"]
    assert extracted.vendor_name == gt["vendor_name"]
    assert extracted.vendor_gstin == gt["vendor_gstin"]
    assert extracted.buyer_gstin == gt["buyer_gstin"]

    # 2. Financial Totals Checks
    assert extracted.subtotal == Decimal(str(gt["subtotal"]))
    assert extracted.total_tax == Decimal(str(gt["total_tax"]))
    assert extracted.grand_total == Decimal(str(gt["grand_total"]))

    # 3. Table Layout Correction Checks (Yao et al.)
    assert len(extracted.line_items) == 2

    # Line item 1: Executive Wooden Desk
    item1 = extracted.line_items[0]
    assert "Executive Wooden Desk" in item1.description
    assert item1.quantity == Decimal("2.00")
    assert item1.unit_price == Decimal("15000.00")
    assert item1.total_amount == Decimal("30000.00")

    # Line item 2: Ergonomic Mesh Chair
    item2 = extracted.line_items[1]
    assert "Ergonomic Mesh Chair" in item2.description
    assert item2.quantity == Decimal("4.00")
    assert item2.unit_price == Decimal("5000.00")
    assert item2.total_amount == Decimal("20000.00")

    # 4. Invariant Math Validation Checks
    assert len(extracted.validation_flags) == 0
    assert extracted.confidence.value == "HIGH"


def test_extract_cloud_invoice_e2e():
    """Tests extraction on the Cloud Server expense invoice."""
    pdf_path = os.path.join(INVOICES_DIR, "INV-2026-002.pdf")
    gt = load_ground_truth("INV-2026-002")

    extracted = DocumentIngestionService.process_pdf_invoice(pdf_path)

    assert extracted.invoice_number == gt["invoice_number"]
    assert extracted.vendor_name == gt["vendor_name"]
    assert extracted.subtotal == Decimal(str(gt["subtotal"]))
    assert extracted.total_tax == Decimal(str(gt["total_tax"]))
    assert extracted.grand_total == Decimal(str(gt["grand_total"]))

    assert len(extracted.line_items) == 1
    assert "Cloud Server" in extracted.line_items[0].description
    assert extracted.line_items[0].total_amount == Decimal("12000.00")
    assert len(extracted.validation_flags) == 0


def test_extract_stationery_invoice_e2e():
    """Tests extraction on stationery invoice with discount."""
    pdf_path = os.path.join(INVOICES_DIR, "INV-2026-003.pdf")
    gt = load_ground_truth("INV-2026-003")

    extracted = DocumentIngestionService.process_pdf_invoice(pdf_path)

    assert extracted.invoice_number == gt["invoice_number"]
    assert extracted.vendor_name == gt["vendor_name"]
    assert len(extracted.line_items) == 1
    assert "A4 Printing Paper" in extracted.line_items[0].description
    assert extracted.line_items[0].quantity == Decimal("10.00")
    assert extracted.line_items[0].discount_amount == Decimal("500.00")
    assert extracted.grand_total == Decimal(str(gt["grand_total"]))
