import re
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from app.schemas.invoice import InvoiceLineItem


class TableLayoutCorrector:
    """
    Implements Table Layout Correction inspired by Yao et al. (2026).
    Handles:
    - Merged summary footer cells (e.g. 'Total Tax (GST):<br>INR 2,160.00' in one cell)
    - Fragmented column splits (e.g. '500' and '.00' split across columns)
    - Isolating HSN/SAC codes from numerical calculations
    - Reconstructing Qty, Unit Price, Discount, and Total with mathematical alignment
    """

    SUMMARY_KEYWORDS = [
        "subtotal", "sub total", "sub-total",
        "total tax", "gst", "cgst", "sgst", "igst", "vat",
        "grand total", "total amount", "net payable", "balance due",
        "total discount", "round off"
    ]

    @staticmethod
    def extract_monetary_amount(text: str) -> Optional[Decimal]:
        if not text:
            return None
        matches = re.findall(r"\b(?:\d{1,3}(?:,\d{3})*|\d+)\.\d{2}\b", text)
        if matches:
            cleaned = matches[-1].replace(",", "")
            try:
                return Decimal(cleaned).quantize(Decimal("0.01"))
            except Exception:
                pass
        
        int_matches = re.findall(r"\b\d+\b", text)
        if int_matches:
            try:
                return Decimal(int_matches[-1]).quantize(Decimal("0.01"))
            except Exception:
                pass
        return None

    @classmethod
    def is_summary_row(cls, row_cells: List[str]) -> bool:
        row_text = " ".join(row_cells).lower()
        return any(keyword in row_text for keyword in cls.SUMMARY_KEYWORDS)

    @classmethod
    def extract_summary_totals(cls, rows: List[List[str]]) -> Dict[str, Decimal]:
        totals: Dict[str, Decimal] = {}
        for row in rows:
            row_str = " ".join(row).lower()
            amt = None
            for cell in reversed(row):
                found = cls.extract_monetary_amount(cell)
                if found is not None:
                    amt = found
                    break

            if amt is not None:
                if "subtotal" in row_str or "sub total" in row_str:
                    totals["subtotal"] = amt
                elif "total tax" in row_str or "tax" in row_str or "gst" in row_str:
                    totals["total_tax"] = amt
                elif "discount" in row_str:
                    totals["total_discount"] = amt
                elif "grand total" in row_str:
                    totals["grand_total"] = amt

        return totals

    @classmethod
    def reconstruct_table(cls, markdown_table: str) -> Tuple[List[InvoiceLineItem], Dict[str, Decimal]]:
        lines = [line.strip() for line in markdown_table.strip().split("\n") if line.strip()]
        if len(lines) < 2:
            return ([], {})

        parsed_rows: List[List[str]] = []
        for line in lines:
            if not line.startswith("|") or not line.endswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if cells and all(set(c).issubset({"-", ":", " "}) for c in cells):
                continue
            parsed_rows.append(cells)

        if not parsed_rows:
            return ([], {})

        data_rows = parsed_rows[1:]
        item_rows: List[List[str]] = []
        summary_rows: List[List[str]] = []

        for row in data_rows:
            if cls.is_summary_row(row):
                summary_rows.append(row)
            else:
                first_non_empty = next((c for c in row if c), "")
                if first_non_empty and not any(kw in first_non_empty.lower() for kw in cls.SUMMARY_KEYWORDS):
                    item_rows.append(row)

        extracted_totals = cls.extract_summary_totals(summary_rows)

        line_items: List[InvoiceLineItem] = []
        for row in item_rows:
            desc = row[0].replace("**", "").replace("*", "").strip() if len(row) > 0 else "Item"
            hsn = row[1].strip() if len(row) > 1 and row[1].strip() not in ("-", "") else None
            
            # Combine remaining columns and stitch together any fragmented decimal splits (like '500' and '.00')
            remaining_text = " ".join(row[2:])
            remaining_text = re.sub(r"(\d+)\s+(\.\d{2})", r"\1\2", remaining_text)  # merge '500 .00' -> '500.00'

            # Extract numbers from remaining columns
            # Finds tokens with optional decimals
            tokens = re.findall(r"\b(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{2})?\b", remaining_text)
            nums: List[Decimal] = []
            for t in tokens:
                try:
                    nums.append(Decimal(t.replace(",", "")).quantize(Decimal("0.01")))
                except Exception:
                    pass

            qty = Decimal("1.00")
            unit_price = Decimal("0.00")
            discount = Decimal("0.00")
            total_amt = Decimal("0.00")

            if nums:
                total_amt = nums[-1]
                if len(nums) == 2:
                    # Qty, Total
                    qty = nums[0]
                    unit_price = (total_amt / qty).quantize(Decimal("0.01")) if qty > 0 else total_amt
                elif len(nums) == 3:
                    # Qty, Unit Price, Total
                    qty = nums[0]
                    unit_price = nums[1]
                elif len(nums) >= 4:
                    # Qty, Unit Price, Discount, Total
                    qty = nums[0]
                    unit_price = nums[1]
                    discount = nums[2]

            line_items.append(
                InvoiceLineItem(
                    description=desc,
                    hsn_sac=hsn,
                    quantity=qty if qty > Decimal("0.00") else Decimal("1.00"),
                    unit_price=unit_price,
                    discount_amount=discount,
                    total_amount=total_amt
                )
            )

        return (line_items, extracted_totals)
