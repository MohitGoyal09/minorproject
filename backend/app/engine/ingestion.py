import os
from decimal import Decimal
from typing import Optional
import pymupdf4llm

from app.schemas.invoice import ExtractedInvoice, ExtractionConfidence
from app.engine.table_corrector import TableLayoutCorrector
from app.engine.heuristics import HeuristicExtractor
from app.engine.invariants import validate_invoice_arithmetic


class DocumentIngestionService:
    """
    End-to-End Ingestion Service combining:
    - Base Paper 2 (Yao et al.): Hybrid Markdown layout representation + Table Layout Correction.
    - Base Paper 1 (Rana et al.): Template-free Heuristic field extraction & validation.
    """

    @classmethod
    def process_pdf_invoice(cls, pdf_path: str) -> ExtractedInvoice:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Invoice document not found at: {pdf_path}")

        # 1. Convert PDF to layout-preserved Markdown (Yao et al. hybrid representation)
        raw_markdown = pymupdf4llm.to_markdown(pdf_path)

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
            subtotal=subtotal,
            total_tax=total_tax,
            total_discount=total_discount,
            grand_total=grand_total,
            line_items=line_items,
            confidence=ExtractionConfidence.HIGH
        )

        # 6. Apply Invariant Arithmetic Validation
        is_math_valid, math_warnings = validate_invoice_arithmetic(invoice)
        if not is_math_valid:
            invoice.confidence = ExtractionConfidence.LOW
            invoice.validation_flags = math_warnings

        return invoice
