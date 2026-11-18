import os
import re
from decimal import Decimal
from typing import Tuple

import pymupdf4llm

from app.schemas.invoice import ExtractedInvoice, ExtractionConfidence
from app.engine.table_corrector import TableLayoutCorrector
from app.engine.heuristics import HeuristicExtractor
from app.engine.invariants import validate_invoice_arithmetic
from app.engine.ocr import OcrService

_AMOUNT_CELL_RE = re.compile(r"^(?:inr|rs\.?|₹)?\s*-?[\d,]", re.IGNORECASE)

OCR_FLAG = (
    "Text extracted via OCR from a scanned document. "
    "Verify the fields against the original image before posting."
)


def has_usable_table(markdown: str) -> bool:
    """True when the markdown already holds a real line-item table.

    A pipe table with at least two numeric cells proves the PDF carries a text
    layer worth reading. Prose-only output means the document is a scan.
    """
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 3 and sum(1 for cell in cells if _AMOUNT_CELL_RE.match(cell)) >= 2:
            return True
    return False


def load_invoice_markdown(pdf_path: str) -> Tuple[str, bool]:
    """Return ``(markdown, used_ocr)`` for an invoice PDF.

    Digital PDFs keep the fast PyMuPDF text layer. Scans, photos and PDFs whose
    text layer holds no table fall back to OCR.
    """
    try:
        markdown = pymupdf4llm.to_markdown(pdf_path)
    except Exception:
        # PyMuPDF's bundled OCR path can fail on image-only pages; the
        # dedicated OCR fallback below is authoritative for those files.
        markdown = ""

    if has_usable_table(markdown):
        return markdown, False

    return OcrService.pdf_to_markdown(pdf_path), True


class DocumentIngestionService:
    """
    End-to-End Ingestion Service combining:
    - Base Paper 2 (Yao et al.): Hybrid Markdown layout representation + Table Layout Correction.
    - Base Paper 1 (Rana et al.): Template-free Heuristic field extraction & validation.
    - OCR fallback for scanned or photographed invoices.
    """

    @classmethod
    def process_pdf_invoice(cls, pdf_path: str) -> ExtractedInvoice:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Invoice document not found at: {pdf_path}")

        # 1. Convert PDF to layout-preserved Markdown (text layer, else OCR)
        raw_markdown, used_ocr = load_invoice_markdown(pdf_path)

        # 2. Extract and Correct Table Layout
        # Find table section inside markdown
        table_lines = [line for line in raw_markdown.split("\n") if line.strip().startswith("|")]
        table_str = "\n".join(table_lines)

        line_items, trapped_totals = TableLayoutCorrector.reconstruct_table(table_str)

        # 3. Extract Metadata via Heuristics (Rana et al.)
        inv_no = HeuristicExtractor.extract_invoice_number(raw_markdown)
        inv_date, due_date = HeuristicExtractor.extract_dates(raw_markdown)
        gstins = HeuristicExtractor.extract_gstin_tags(raw_markdown)
        vendor, buyer = HeuristicExtractor.extract_entity_names(raw_markdown)

        # Place of supply extraction
        pos = None
        pos_code = None
        pos_match = re.search(r"Place of Supply:\*?\*?\s*([^\n\|]+)", raw_markdown, re.IGNORECASE)
        if pos_match:
            pos = pos_match.group(1).replace("*", "").strip()
            code_match = re.search(r"\((\d{2})\)|\b(\d{2})\b", pos)
            if code_match:
                pos_code = code_match.group(1) or code_match.group(2)

        # 4. Resolve Totals
        subtotal = trapped_totals.get("subtotal")
        total_tax = trapped_totals.get("total_tax", Decimal("0.00"))
        total_discount = trapped_totals.get("total_discount", Decimal("0.00"))
        grand_total = trapped_totals.get("grand_total")

        # If subtotal not directly extracted, compute sum of line items
        if not subtotal:
            subtotal = sum((item.total_amount for item in line_items), start=Decimal("0.00"))

        if not grand_total:
            grand_total = subtotal + total_tax - total_discount

        # 5. Construct Initial Normalized Model
        invoice = ExtractedInvoice(
            invoice_number=inv_no,
            invoice_date=inv_date,
            due_date=due_date,
            vendor_name=vendor,
            vendor_gstin=gstins.get("vendor_gstin"),
            buyer_name=buyer,
            buyer_gstin=gstins.get("buyer_gstin"),
            place_of_supply=pos,
            place_of_supply_state_code=pos_code,
            subtotal=subtotal,
            total_tax=total_tax,
            total_discount=total_discount,
            grand_total=grand_total,
            line_items=line_items,
            confidence=ExtractionConfidence.MEDIUM if used_ocr else ExtractionConfidence.HIGH
        )

        if used_ocr:
            invoice.validation_flags.append(OCR_FLAG)

        # 6. Apply Invariant Arithmetic Validation
        is_math_valid, math_warnings = validate_invoice_arithmetic(invoice)
        if not is_math_valid:
            invoice.confidence = ExtractionConfidence.LOW
            invoice.validation_flags.extend(math_warnings)

        return invoice
