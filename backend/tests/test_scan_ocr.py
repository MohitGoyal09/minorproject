"""Tests for the scanned-document OCR path (stage 1 + 2 of the methodology)."""

import os

import pytest

from app.engine import ingestion
from app.engine.ingestion import DocumentIngestionService, has_usable_table, load_invoice_markdown
from app.engine.ocr import Word, group_words_into_rows, rows_to_markdown
from app.schemas.invoice import ExtractionConfidence

DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_invoices")
)
DIGITAL_PDF = os.path.join(DATA_DIR, "INV-2026-001.pdf")


def word(text, x0, y0, x1=None, y1=None):
    return Word(text=text, x0=x0, y0=y0, x1=x1 if x1 is not None else x0 + 60, y1=y1 if y1 is not None else y0 + 18)


# --- row grouping ---------------------------------------------------------

def test_group_words_into_rows_splits_by_vertical_position():
    words = [
        word("Invoice", 100, 100),
        word("No:", 180, 101),
        word("INV-2026-001", 240, 100),
        word("Total", 100, 400),
        word("59,000.00", 300, 401),
    ]

    rows = group_words_into_rows(words)

    assert len(rows) == 2
    assert [w.text for w in rows[0]] == ["Invoice", "No:", "INV-2026-001"]
    assert [w.text for w in rows[1]] == ["Total", "59,000.00"]


def test_group_words_into_rows_sorts_cells_left_to_right():
    words = [word("C", 300, 100), word("A", 100, 100), word("B", 200, 100)]

    rows = group_words_into_rows(words)

    assert [w.text for w in rows[0]] == ["A", "B", "C"]


# --- markdown reconstruction ---------------------------------------------

def test_rows_to_markdown_keeps_prose_outside_the_table():
    rows = [
        [word("ABC Furniture Mart", 100, 100)],
        [word("Invoice No: INV-2026-001", 100, 150)],
        [word("Item Description", 100, 545), word("HSN/SAC", 400, 545),
         word("Qty", 600, 545), word("Unit Price", 800, 545),
         word("Discount", 1000, 545), word("Total", 1200, 545)],
        [word("Executive Wooden Desk", 100, 615), word("9403", 400, 615),
         word("15,000.00", 800, 615), word("0.00", 1000, 615),
         word("30,000.00", 1200, 615)],
    ]

    markdown = rows_to_markdown(rows)
    lines = [line for line in markdown.splitlines() if line.strip()]

    assert "ABC Furniture Mart" in lines[0]
    assert "Invoice No: INV-2026-001" in lines[1]
    table_lines = [line for line in lines if line.startswith("|")]
    assert len(table_lines) == 3  # header + separator + one data row
    assert table_lines[0].startswith("| Item Description |")
    assert set(table_lines[1].replace("|", "").replace(" ", "")) == {"-"}
    # A missing Qty cell keeps its column so downstream parsing stays aligned.
    assert [cell.strip() for cell in table_lines[2].split("|")[1:7]] == [
        "Executive Wooden Desk", "9403", "", "15,000.00", "0.00", "30,000.00",
    ]


def test_rows_to_markdown_emits_no_table_for_pure_prose():
    rows = [[word("This page contains no tabular line items at all", 100, 100)]]

    markdown = rows_to_markdown(rows)

    assert "|" not in markdown


# --- text-layer detection -------------------------------------------------

def test_has_usable_table_accepts_the_digital_sample_invoice():
    markdown = ingestion.pymupdf4llm.to_markdown(DIGITAL_PDF)

    assert has_usable_table(markdown) is True


def test_has_usable_table_rejects_prose_and_empty_text():
    assert has_usable_table("") is False
    assert has_usable_table("# Invoice\n\nNo structured rows on this page.") is False


# --- ingestion routing ----------------------------------------------------

def test_ingestion_uses_ocr_when_the_text_layer_has_no_table(monkeypatch):
    ocr_markdown = (
        "ABC Furniture Mart\n"
        "Invoice No: INV-2026-001\n"
        "Invoice Date: 2026-10-15\n"
        "GSTIN:07AAAAA0000A1Z5\n"
        "| Item Description | HSN/SAC | Qty | Unit Price | Discount | Total |\n"
        "|---|---|---|---|---|---|\n"
        "| Executive Wooden Desk | 9403 | 2 | 15,000.00 | 0.00 | 30,000.00 |\n"
        "| Grand Total: | | | | | 30,000.00 |\n"
    )
    monkeypatch.setattr(ingestion.pymupdf4llm, "to_markdown", lambda *a, **k: "")
    monkeypatch.setattr(
        ingestion.OcrService, "pdf_to_markdown", classmethod(lambda cls, *a, **k: ocr_markdown)
    )

    markdown, used_ocr = load_invoice_markdown(DIGITAL_PDF)

    assert used_ocr is True
    assert "Executive Wooden Desk" in markdown


def test_ingestion_keeps_text_layer_when_a_table_exists(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ingestion.OcrService,
        "pdf_to_markdown",
        classmethod(lambda cls, *a, **k: calls.append(1) or "| a | b | 1 | 2 |"),
    )

    _, used_ocr = load_invoice_markdown(DIGITAL_PDF)

    assert used_ocr is False
    assert calls == []


def test_scanned_invoice_is_flagged_for_review(monkeypatch):
    ocr_markdown = (
        "ABC Furniture Mart\n"
        "Invoice No: INV-2026-001\n"
        "Invoice Date: 2026-10-15\n"
        "GSTIN:07AAAAA0000A1Z5\n"
        "| Item Description | HSN/SAC | Qty | Unit Price | Discount | Total |\n"
        "|---|---|---|---|---|---|\n"
        "| Executive Wooden Desk | 9403 | 2 | 15,000.00 | 0.00 | 30,000.00 |\n"
        "| Subtotal: | | | | | 30,000.00 |\n"
        "| Grand Total: | | | | | 30,000.00 |\n"
    )
    monkeypatch.setattr(ingestion.pymupdf4llm, "to_markdown", lambda *a, **k: "")
    monkeypatch.setattr(
        ingestion.OcrService, "pdf_to_markdown", classmethod(lambda cls, *a, **k: ocr_markdown)
    )

    invoice = DocumentIngestionService.process_pdf_invoice(DIGITAL_PDF)

    assert invoice.confidence == ExtractionConfidence.MEDIUM
    assert any("OCR" in flag for flag in invoice.validation_flags)


def test_digital_invoice_is_not_flagged_as_ocr():
    invoice = DocumentIngestionService.process_pdf_invoice(DIGITAL_PDF)

    assert invoice.confidence == ExtractionConfidence.HIGH
    assert not any("OCR" in flag for flag in invoice.validation_flags)


def test_vendor_name_falls_back_to_first_prose_line():
    from app.engine.heuristics import HeuristicExtractor

    text = (
        "ABC Furniture Mart\n"
        "GSTIN:07AAAAA0000A1Z5\n"
        "Invoice No: INV-2026-001\n"
        "Invoice Date: 2026-10-15\n"
    )

    vendor, _ = HeuristicExtractor.extract_entity_names(text)

    assert vendor == "ABC Furniture Mart"


def test_vendor_name_skips_document_titles_when_falling_back():
    from app.engine.heuristics import HeuristicExtractor

    text = "TAX INVOICE\nORIGINAL FOR RECIPIENT\nABC Furniture Mart\nGSTIN:07AAAAA0000A1Z5\n"

    vendor, _ = HeuristicExtractor.extract_entity_names(text)

    assert vendor == "ABC Furniture Mart"


# --- real OCR engine (optional, skipped when not installed) ---------------

def test_ocr_service_reports_availability():
    from app.engine.ocr import OcrService

    assert isinstance(OcrService.is_available(), bool)


@pytest.mark.skipif(
    not os.path.exists("/tmp/scanned_INV-2026-001.pdf"),
    reason="scanned fixture is generated by scripts/verify_scan_pipeline.py",
)
def test_real_ocr_reads_a_scanned_invoice():
    from app.engine.ocr import OcrService

    markdown = OcrService.pdf_to_markdown("/tmp/scanned_INV-2026-001.pdf", dpi=200)

    assert "ABC Furniture Mart" in markdown
    assert "INV-2026-001" in markdown
    assert "|" in markdown
