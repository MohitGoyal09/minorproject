"""CLI: regenerate the evaluation report.

    cd backend && PYTHONPATH=. python -m app.eval.report
    cd backend && PYTHONPATH=. python -m app.eval.report --write ../docs/EVALUATION.md
"""

import argparse
from pathlib import Path

from app.eval.evaluator import REPO_ROOT, evaluate_dataset


def build_document(report) -> str:
    return f"""# Evaluation (regression fixtures)

Every number on this page is measured, not estimated. Regenerate it with:

```bash
cd backend && PYTHONPATH=. python -m app.eval.report --write ../docs/EVALUATION.md
```

## What is measured

The full pipeline runs on each invoice in `data/sample_invoices/` and is compared
against `data/ground_truth/`, using exact or two-decimal comparison:

- **Header fields** - invoice number, dates, vendor, buyer, GSTINs, place of supply.
- **Totals** - subtotal, total tax, total discount, grand total.
- **Line items** - description, HSN/SAC, quantity, unit price, discount, line total.
- **Journal entry** - every proposed debit and credit (account code, side, amount),
  compared as an order-independent multiset.

A check passes only on an exact match; there is no partial credit inside a check.
An invoice is *exact* when every check matches.

## Results

These are agreement checks against the author's own fixtures, not accuracy on
unseen documents. Every fixture PDF and its expected JSON are written from the
same hand-authored dictionary, so a pass proves the pipeline still matches the
author's intent; it does not prove extraction quality.

{report.to_markdown()}

## What this does not measure

- **Per-line tax components.** The fixtures print a combined tax total, so
  component extraction cannot be scored here.
- **Persistence and corrections.** That the stored invoice equals the POSTed one
  is covered by `tests/test_correction_export.py`, not by this report.
- **Posting and the ledger.** Covered by `tests/test_posting_boundary.py`.
- **Reports and exports.** Covered by `tests/test_correction_export.py`.
- **Unseen layouts, rotations, multi-page tables, handwriting.** Not represented
  in the fixtures at all.

## Scan path

A rasterised, text-free copy of `INV-2026-001.pdf` is read by the OCR fallback and
produces the same line items, totals and journal entry as the digital PDF, at
`MEDIUM` confidence. Covered by `tests/test_scan_ocr.py`
(`test_real_ocr_reads_a_scanned_invoice`) and by the live HTTP check.

## How to reproduce

```bash
cd backend && python -m pytest -q                      # 75 tests, includes the evaluation
cd backend && PYTHONPATH=. python -m app.eval.report    # print this table
```

## Limitations

- **Four synthetic invoices, not a public benchmark.** The set covers capital
  goods, an intra-state service, a discounted supplies invoice and a five-line
  intra-state invoice. It does not establish accuracy on unseen real-world
  layouts; that needs SROIE, CORD or DocILE and is future work.
- **Labels are not independent of the code.** They were written alongside the
  fixtures and the rule set. Treat the numbers as regression, not measurement.

- **Template-free, not model-based.** Vendor layouts are handled by heuristics and
  geometry, not a trained model. Accuracy on unseen vendors is therefore unknown.
- **Classification accuracy is partly policy.** The cloud-subscription invoice
  passes because the SAC prefix 9983 is authoritative; a differently worded line
  with no SAC code could be classified differently.
- The evaluation imports the production pipeline directly, so it measures the
  real code path rather than a test double.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ground-truth evaluation.")
    parser.add_argument(
        "--write",
        nargs="?",
        const=str(REPO_ROOT / "docs" / "EVALUATION.md"),
        help="Write the report to a file instead of printing it.",
    )
    args = parser.parse_args()

    report = evaluate_dataset()
    document = build_document(report)

    if args.write:
        destination = Path(args.write)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document)
        print(f"Wrote {destination}")
        print(f"Overall accuracy: {report.overall_accuracy:.1%} ({report.exact_invoices}/{report.invoice_count} exact)")
    else:
        print(document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
