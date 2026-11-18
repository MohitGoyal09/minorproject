import re
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple


class HeuristicExtractor:
    """
    Template-free heuristic field extraction inspired by Rana et al. (2025).
    Extracts invoice numbers, dates, GSTINs, vendor and buyer information
    from unconstrained text and markdown streams using robust regex patterns.
    """

    GSTIN_PATTERN = r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b"
    INVOICE_NUM_PATTERNS = [
        r"(?:invoice\s*no\.?|inv\s*#|invoice\s*number|bill\s*no\.?)[\s*:]+([A-Za-z0-9][A-Za-z0-9\-_/.]*(?:\s+[A-Za-z0-9\-_/.]{1,12}){0,3})",
        r"\b(INV[-.]\d{4}[-.]\d{3,})\b",
    ]
    DATE_PATTERNS = [
        r"(?:invoice\s*date|date|dated)[\s*:]+(\d{4}-\d{2}-\d{2})",
        r"(?:invoice\s*date|date|dated)[\s*:]+(\d{2}[/-]\d{2}[/-]\d{4})",
        r"\b(\d{4}-\d{2}-\d{2})\b",
    ]
    DUE_DATE_PATTERNS = [
        r"(?:due\s*date|payment\s*due)[\s*:]+(\d{4}-\d{2}-\d{2})",
        r"(?:due\s*date|payment\s*due)[\s*:]+(\d{2}[/-]\d{2}[/-]\d{4})",
    ]

    # Lines that are labels or document titles, never a supplier name.
    PROSE_STOPWORDS = (
        "invoice", "tax", "gstin", "gst", "date", "no.", "number", "address",
        "billed", "buyer", "ship", "place of supply", "total", "subtotal",
        "amount", "due", "original", "duplicate", "triplicate", "receipt",
        "statement", "purchase order", "terms", "bank", "account", "ifsc",
        "pan", "cin", "email", "phone", "mobile", "website", "declaration",
    )

    @classmethod
    def extract_gstin_tags(cls, text: str) -> Dict[str, Optional[str]]:
        gstins = re.findall(cls.GSTIN_PATTERN, text)
        result = {"vendor_gstin": None, "buyer_gstin": None}
        
        buyer_match = re.search(r"(?:buyer\s*gstin|customer\s*gstin)[\s*:]+(" + cls.GSTIN_PATTERN + ")", text, re.IGNORECASE)
        if buyer_match:
            result["buyer_gstin"] = buyer_match.group(1)
        
        vendor_match = re.search(r"(?:vendor\s*gstin|supplier\s*gstin|gstin)[\s*:]+(" + cls.GSTIN_PATTERN + ")", text, re.IGNORECASE)
        if vendor_match and vendor_match.group(1) != result["buyer_gstin"]:
            result["vendor_gstin"] = vendor_match.group(1)
        
        remaining = [g for g in gstins if g != result["buyer_gstin"]]
        if not result["vendor_gstin"] and remaining:
            result["vendor_gstin"] = remaining[0]
        if not result["buyer_gstin"]:
            buyer_candidates = [g for g in gstins if g != result["vendor_gstin"]]
            if buyer_candidates:
                result["buyer_gstin"] = buyer_candidates[0]

        return result

    @classmethod
    def extract_invoice_number(cls, text: str) -> str:
        for pat in cls.INVOICE_NUM_PATTERNS:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "UNKNOWN_INV"

    DATE_FORMATS = (
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
        "%d-%b-%Y", "%d %b %Y", "%m/%d/%Y",
    )

    @classmethod
    def parse_date_safe(cls, date_str: str) -> date:
        raw = " ".join((date_str or "").replace(",", " ").split())
        for fmt in cls.DATE_FORMATS:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return date.today()

    DATE_VALUE = r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2}[ -][A-Za-z]{3,9}[ -]\d{4})"

    @classmethod
    def extract_dates(cls, text: str) -> Tuple[date, Optional[date]]:
        """Read the due date and the invoice date from their own labels.

        A due date must never satisfy the invoice-date pattern, otherwise an
        invoice with only a due date is dated in the future.
        """
        due_date = None
        due_match = re.search(r"(?:due\s*date|payment\s*due)[\s*:]+" + cls.DATE_VALUE, text, re.IGNORECASE)
        if due_match:
            due_date = cls.parse_date_safe(due_match.group(1))

        inv_date = None
        invoice_match = re.search(
            r"(?:invoice\s*date|date\s*of\s*invoice|dated)[\s*:]+" + cls.DATE_VALUE,
            text, re.IGNORECASE,
        )
        if invoice_match:
            inv_date = cls.parse_date_safe(invoice_match.group(1))

        if inv_date is None:
            # An unlabelled date is accepted only when it is not the due date.
            for candidate in re.finditer(cls.DATE_VALUE, text):
                parsed = cls.parse_date_safe(candidate.group(1))
                if due_date is None or parsed != due_date:
                    inv_date = parsed
                    break

        return (inv_date or date.today(), due_date)

    @classmethod
    def extract_entity_names(cls, text: str) -> Tuple[str, Optional[str]]:
        vendor_name = "Unknown Vendor"
        buyer_name = None

        # 1. Try markdown header `# **Company Name**`
        header_match = re.search(r"#\s*\*{0,2}(.*?)\*{0,2}\s*$", text, re.MULTILINE)
        if header_match:
            candidate = header_match.group(1).strip()
            lowered = candidate.lower()
            if (
                len(candidate) > 2
                and "invoice" not in lowered
                and not any(word in lowered for word in cls.PROSE_STOPWORDS)
            ):
                vendor_name = candidate

        # 2. If vendor still unknown, check first bold block `**Company Name**` before GSTIN
        if vendor_name == "Unknown Vendor":
            bold_match = re.search(r"\*{2}([A-Za-z0-9\s&.,-]+?)\*{2}\s*(?:GSTIN|Address|\n)", text)
            if bold_match:
                candidate = bold_match.group(1).strip()
                if len(candidate) > 2 and "invoice" not in candidate.lower():
                    vendor_name = candidate

        # 3. Buyer extraction
        buyer_match = re.search(
            r"(?:billed\s*to|customer|buyer)[\s*:]+\*{0,2}([A-Za-z0-9\s.,&]+?)(?:\*{0,2}\s*(?:\n|\*\*|GSTIN|Invoice|Due))",
            text,
            re.IGNORECASE
        )
        if buyer_match:
            buyer_name = buyer_match.group(1).strip()

        # 4. Plain-text fallback (OCR output has no markdown headings or bold)
        if vendor_name == "Unknown Vendor":
            vendor_name = cls._first_prose_candidate(text)

        return (vendor_name, buyer_name)

    @classmethod
    def _first_prose_candidate(cls, text: str) -> str:
        """First plausible company line: no digits, two or more words, no label words."""
        for raw in text.splitlines()[:20]:
            line = re.sub(r"[*_#|]", " ", raw).strip(" :-\t")
            if not 3 <= len(line) <= 60:
                continue
            if re.search(r"\d", line) or len(line.split()) < 2:
                continue
            if any(word in line.lower() for word in cls.PROSE_STOPWORDS):
                continue
            return line
        return "Unknown Vendor"
