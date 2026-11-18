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
        "total tax", "cgst", "sgst", "igst",
        "grand total", "total amount", "net payable", "balance due",
        "total discount", "round off"
    ]
    COMPRESSED_SUMMARY_KEYWORDS = [
        "subtotal", "totaltax", "grandtotal", "totalamount", "totaldiscount", "netpayable", "balancedue", "roundoff"
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
        for kw in cls.SUMMARY_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", row_text):
                return True
        # Check compressed text for multi-word summary terms split across markdown cells
        compressed = re.sub(r"[\s\*\_\-]+", "", row_text)
        return any(ckw in compressed for ckw in cls.COMPRESSED_SUMMARY_KEYWORDS)

    @classmethod
    def extract_summary_totals(cls, rows: List[List[str]]) -> Dict[str, Decimal]:
        totals: Dict[str, Decimal] = {}
        for row in rows:
            row_str = " ".join(row).lower()
            row_comp = re.sub(r"[\s\*\_\-]+", "", row_str)
            amt = None
            for cell in reversed(row):
                found = cls.extract_monetary_amount(cell)
                if found is not None:
                    amt = found
                    break

            if amt is not None:
                if "subtotal" in row_comp or "subtotal" in row_str:
                    totals["subtotal"] = amt
                elif "totaltax" in row_comp or "totaltax" in row_str or "gst" in row_comp:
                    totals["total_tax"] = amt
                elif "discount" in row_comp or "discount" in row_str:
                    totals["total_discount"] = amt
                elif "grandtotal" in row_comp or "grandtotal" in row_str:
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

        header_cells: List[str] = parsed_rows[0] if parsed_rows else []
        data_rows = parsed_rows[1:]
        item_rows: List[List[str]] = []
        summary_rows: List[List[str]] = []

        for row in data_rows:
            if cls.is_summary_row(row):
                summary_rows.append(row)
            else:
                desc = row[0].replace("**", "").replace("*", "").strip() if len(row) > 0 else ""
                if desc and len(desc) >= 2 and not cls.is_summary_row([desc]):
                    item_rows.append(row)
                else:
                    summary_rows.append(row)

        extracted_totals = cls.extract_summary_totals(summary_rows)

        line_items: List[InvoiceLineItem] = []
        for row in item_rows:
            line_items.append(cls._build_line_item(row, header_cells))

        return (line_items, extracted_totals)

    # ------------------------------------------------------------------
    # Column-aware row mapping (Table Structure Recognition)
    # ------------------------------------------------------------------

    @staticmethod
    def _amount_tokens(text: str) -> List[Decimal]:
        """Every monetary token in a cell, in reading order."""
        tokens: List[Decimal] = []
        pattern = r"(?:INR|Rs\.?|₹)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
        for raw in re.findall(pattern, text or "", re.IGNORECASE):
            try:
                tokens.append(Decimal(raw.replace(",", "")).quantize(Decimal("0.01")))
            except Exception:
                continue
        return tokens

    @classmethod
    def _header_column_map(cls, header_cells: List[str]) -> Dict[str, int]:
        """Map semantic column names to their index, using the header labels."""
        mapping: Dict[str, int] = {}
        for index, cell in enumerate(header_cells):
            label = re.sub(r"[*_`]", "", cell or "")
            label = re.sub(r"<br\s*/?>", " ", label).strip().lower()
            if not label:
                continue
            if "description" in label or "item" in label or "particular" in label:
                mapping.setdefault("description", index)
            elif "hsn" in label or "sac" in label:
                mapping.setdefault("hsn", index)
            elif "qty" in label or "quantity" in label:
                mapping.setdefault("qty", index)
            elif "price" in label or "rate" in label:
                mapping.setdefault("rate", index)
            elif "discount" in label or label.startswith("disc"):
                mapping.setdefault("discount", index)
            elif "total" in label or "amount" in label:
                mapping.setdefault("total", index)
        return mapping

    @classmethod
    def _build_line_item(cls, row: List[str], header_cells: List[str]) -> InvoiceLineItem:
        desc = row[0].replace("**", "").replace("*", "").strip() if len(row) > 0 else "Item"
        hsn = row[1].strip() if len(row) > 1 and row[1].strip() not in ("-", "") else None

        mapped = cls._map_row_to_columns(row, header_cells)
        if mapped is not None:
            return InvoiceLineItem(
                description=desc,
                hsn_sac=mapped.pop("hsn_sac", hsn),
                **mapped
            )

        # Fallback: positional number heuristic when no usable header exists.
        remaining_text = " ".join(row[2:])
        remaining_text = re.sub(r"(\d+)\s+(\.\d{2})", r"\1\2", remaining_text)  # merge '500 .00' -> '500.00'

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

        return InvoiceLineItem(
            description=desc,
            hsn_sac=hsn,
            quantity=qty if qty > Decimal("0.00") else Decimal("1.00"),
            unit_price=unit_price,
            discount_amount=discount,
            total_amount=total_amt
        )

    @classmethod
    def _map_row_to_columns(cls, row: List[str], header_cells: List[str]) -> Optional[Dict[str, Decimal]]:
        """Assign a row's cells by header label, tolerating empty (OCR-missed) cells."""
        if not header_cells or len(row) != len(header_cells):
            return None

        columns = cls._header_column_map(header_cells)
        if not {"qty", "rate", "total"} & set(columns) or "total" not in columns:
            return None

        def tokens(name: str) -> List[Decimal]:
            index = columns.get(name)
            return cls._amount_tokens(row[index]) if index is not None else []

        qty_tokens = tokens("qty")
        rate_tokens = tokens("rate")
        total_tokens = tokens("total")
        discount_tokens = tokens("discount")

        total = total_tokens[-1] if total_tokens else None
        rate = rate_tokens[0] if rate_tokens else None
        if total is None and rate is None:
            return None

        qty = qty_tokens[0] if qty_tokens else None
        # A merged "Unit Price<br>Discount" column carries both values.
        discount = (
            discount_tokens[0] if discount_tokens
            else (rate_tokens[1] if len(rate_tokens) > 1 else Decimal("0.00"))
        )

        if qty is None:
            qty = (total / rate).quantize(Decimal("0.01")) if (rate and total) else Decimal("1.00")
        if qty <= Decimal("0.00"):
            qty = Decimal("1.00")
        if total is None:
            total = (qty * rate - discount).quantize(Decimal("0.01"))
        if rate is None:
            rate = (total / qty).quantize(Decimal("0.01"))

        mapped: Dict[str, Decimal] = {
            "quantity": qty,
            "unit_price": rate,
            "discount_amount": discount,
            "total_amount": total,
        }
        if "hsn" in columns:
            mapped["hsn_sac"] = row[columns["hsn"]].strip() or None
        return mapped
