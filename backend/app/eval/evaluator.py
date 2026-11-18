"""Ground-truth evaluation (methodology stage 2 and 5 accuracy).

Scores the real pipeline against ``data/ground_truth/*.json``: header fields,
totals, line items, and the proposed journal entry. No model, no judgement calls
— every check is an exact or two-decimal comparison, so the numbers are
reproducible and defensible in a report.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from app.engine.ingestion import DocumentIngestionService
from app.engine.interpreter import AccountingInterpreter
from app.schemas.accounting import ProposedJournalEntry
from app.schemas.invoice import ExtractedInvoice

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = REPO_ROOT / "data" / "sample_invoices"
GROUND_TRUTH_DIR = REPO_ROOT / "data" / "ground_truth"

HEADER_FIELDS = (
    "invoice_number",
    "invoice_date",
    "due_date",
    "vendor_name",
    "vendor_gstin",
    "buyer_name",
    "buyer_gstin",
    "place_of_supply",
)
TOTAL_FIELDS = ("subtotal", "total_tax", "total_discount", "grand_total")
LINE_FIELDS = ("description", "hsn_sac", "quantity", "unit_price", "discount_amount", "total_amount")


def _text(value) -> Optional[str]:
    if value is None:
        return None
    return " ".join(str(value).split()).casefold()


def _money(value) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _journal_signature(line) -> str:
    code = line["account_code"] if isinstance(line, dict) else line.account_code
    entry_type = line["entry_type"] if isinstance(line, dict) else line.entry_type
    amount = line["amount"] if isinstance(line, dict) else line.amount
    entry_type = getattr(entry_type, "value", entry_type)
    return f"{code}:{entry_type}:{_money(amount)}"


@dataclass
class InvoiceEvaluation:
    invoice_number: str
    confidence: str
    field_checks: Dict[str, bool] = field(default_factory=dict)
    line_checks: Dict[str, bool] = field(default_factory=dict)
    journal_checks: Dict[str, bool] = field(default_factory=dict)
    expected: Dict[str, str] = field(default_factory=dict)
    actual: Dict[str, str] = field(default_factory=dict)
    line_items_expected: int = 0
    line_items_extracted: int = 0
    line_items_matched: int = 0
    journal_expected: int = 0
    journal_matched: int = 0

    @property
    def total_checks(self) -> int:
        return len(self.field_checks) + len(self.line_checks) + len(self.journal_checks)

    @property
    def passed_checks(self) -> int:
        return (
            sum(self.field_checks.values())
            + sum(self.line_checks.values())
            + sum(self.journal_checks.values())
        )

    @property
    def accuracy(self) -> float:
        return self.passed_checks / self.total_checks if self.total_checks else 0.0

    @property
    def failed_checks(self) -> List[str]:
        failed = [name for name, ok in self.field_checks.items() if not ok]
        failed += [name for name, ok in self.line_checks.items() if not ok]
        failed += [name for name, ok in self.journal_checks.items() if not ok]
        return failed

    @property
    def is_exact(self) -> bool:
        return self.total_checks > 0 and self.failed_checks == []


@dataclass
class DatasetEvaluation:
    rows: List[InvoiceEvaluation] = field(default_factory=list)

    @property
    def invoice_count(self) -> int:
        return len(self.rows)

    def _rate(self, selector) -> float:
        passed = total = 0
        for row in self.rows:
            for name, ok in selector(row).items():
                total += 1
                passed += 1 if ok else 0
        return passed / total if total else 0.0

    @property
    def field_accuracy(self) -> float:
        return self._rate(lambda row: row.field_checks)

    @property
    def line_item_accuracy(self) -> float:
        return self._rate(lambda row: row.line_checks)

    @property
    def journal_accuracy(self) -> float:
        return self._rate(lambda row: row.journal_checks)

    @property
    def overall_accuracy(self) -> float:
        return self._rate(lambda row: {**row.field_checks, **row.line_checks, **row.journal_checks})

    @property
    def exact_invoices(self) -> int:
        return sum(1 for row in self.rows if row.is_exact)

    def to_markdown(self) -> str:
        lines = [
            "| Invoice | Fields | Line items | Journal | Overall | Exact | Extraction |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in sorted(self.rows, key=lambda r: r.invoice_number):
            lines.append(
                f"| {row.invoice_number} "
                f"| {row.passed_checks}/{row.total_checks} "
                f"| {row.line_items_matched}/{row.line_items_expected} "
                f"| {row.journal_matched}/{row.journal_expected} "
                f"| {row.accuracy:.1%} "
                f"| {'yes' if row.is_exact else 'no'} "
                f"| {row.confidence} |"
            )

        lines += [
            "",
            f"- Invoices evaluated: **{self.invoice_count}**",
            f"- Field accuracy (headers and totals): **{self.field_accuracy:.1%}**",
            f"- Line-item accuracy: **{self.line_item_accuracy:.1%}**",
            f"- Journal-entry accuracy: **{self.journal_accuracy:.1%}**",
            f"- Overall check accuracy: **{self.overall_accuracy:.1%}**",
            f"- Exact invoices: **{self.exact_invoices}/{self.invoice_count}**",
        ]

        mismatches = [
            (row.invoice_number, check)
            for row in sorted(self.rows, key=lambda r: r.invoice_number)
            for check in row.failed_checks
        ]
        if mismatches:
            lines += ["", "### Mismatches", "", "| Invoice | Check | Expected | Extracted |", "|---|---|---|---|"]
            for invoice_number, check in mismatches:
                expected = next((row.expected.get(check, "") for row in self.rows if row.invoice_number == invoice_number), "")
                actual = next((row.actual.get(check, "") for row in self.rows if row.invoice_number == invoice_number), "")
                lines.append(f"| {invoice_number} | {check} | {expected} | {actual} |")
        return "\n".join(lines)


def score_invoice(
    invoice: ExtractedInvoice,
    ground_truth: dict,
    proposal: Optional[ProposedJournalEntry] = None,
) -> InvoiceEvaluation:
    result = InvoiceEvaluation(
        invoice_number=str(invoice.invoice_number),
        confidence=getattr(invoice.confidence, "value", str(invoice.confidence)),
    )

    # Header fields
    for name in HEADER_FIELDS:
        expected = ground_truth.get(name)
        if expected is None:
            continue
        actual_value = getattr(invoice, name, None)
        if name in ("invoice_date", "due_date"):
            passed = _iso(actual_value) == _iso(expected)
            expected_str, actual_str = _iso(expected), _iso(actual_value)
        elif name.endswith("gstin") or name == "invoice_number":
            passed = (str(actual_value).strip().upper() if actual_value else None) == str(expected).strip().upper()
            expected_str, actual_str = str(expected), str(actual_value)
        else:
            passed = _text(actual_value) == _text(expected)
            expected_str, actual_str = str(expected), str(actual_value)
        result.field_checks[name] = passed
        result.expected[name] = expected_str or ""
        result.actual[name] = actual_str or ""

    # Totals
    for name in TOTAL_FIELDS:
        expected = ground_truth.get(name)
        if expected is None:
            continue
        actual_value = getattr(invoice, name, None)
        result.field_checks[name] = _money(actual_value) == _money(expected)
        result.expected[name] = str(_money(expected))
        result.actual[name] = str(_money(actual_value))

    # Line items
    expected_lines: Sequence[dict] = ground_truth.get("line_items") or []
    extracted_lines = list(invoice.line_items)
    result.line_items_expected = len(expected_lines)
    result.line_items_extracted = len(extracted_lines)
    result.field_checks["line_item_count"] = len(expected_lines) == len(extracted_lines)

    for index in range(min(len(expected_lines), len(extracted_lines))):
        expected_line = expected_lines[index]
        actual_line = extracted_lines[index]
        for name in LINE_FIELDS:
            expected_value = expected_line.get(name)
            if expected_value is None and name == "hsn_sac":
                expected_value = None
            actual_value = getattr(actual_line, name, None)
            if name in ("quantity", "unit_price", "discount_amount", "total_amount"):
                passed = _money(actual_value) == _money(expected_value)
            else:
                passed = _text(actual_value) == _text(expected_value)
            result.line_checks[f"line{index + 1}.{name}"] = passed
        if all(result.line_checks.get(f"line{index + 1}.{name}", False) for name in LINE_FIELDS):
            result.line_items_matched += 1

    # Journal entry (order-independent)
    journal_ground_truth = (ground_truth.get("accounting_ground_truth") or {}).get("journal_lines") or []
    result.journal_expected = len(journal_ground_truth)
    if proposal is not None and journal_ground_truth:
        expected_counter = Counter(_journal_signature(line) for line in journal_ground_truth)
        actual_counter = Counter(_journal_signature(line) for line in proposal.lines)
        remaining = expected_counter.copy()
        for signature, count in actual_counter.items():
            usable = min(count, remaining.get(signature, 0))
            result.journal_matched += usable
            remaining[signature] -= usable
        result.journal_checks["journal_exact"] = expected_counter == actual_counter
        for signature, count in expected_counter.items():
            result.journal_checks[f"journal.{signature}"] = actual_counter.get(signature, 0) >= count
            result.expected[f"journal.{signature}"] = signature
            result.actual[f"journal.{signature}"] = signature if actual_counter.get(signature) else "missing"

    return result


def evaluate_invoice_file(pdf_path: Path, ground_truth: dict) -> InvoiceEvaluation:
    invoice = DocumentIngestionService.process_pdf_invoice(str(pdf_path))
    proposal = AccountingInterpreter.interpret_invoice(
        invoice=invoice,
        document_id=f"eval-{pdf_path.stem}",
    )
    return score_invoice(invoice, ground_truth, proposal)


def evaluate_dataset(
    sample_dir: Path = SAMPLE_DIR,
    ground_truth_dir: Path = GROUND_TRUTH_DIR,
) -> DatasetEvaluation:
    report = DatasetEvaluation()
    for truth_file in sorted(ground_truth_dir.glob("*.json")):
        pdf_path = sample_dir / f"{truth_file.stem}.pdf"
        if not pdf_path.exists():
            continue
        ground_truth = json.loads(truth_file.read_text())
        report.rows.append(evaluate_invoice_file(pdf_path, ground_truth))
    return report
