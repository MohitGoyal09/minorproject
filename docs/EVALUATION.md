# Evaluation (regression fixtures)

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

| Invoice | Fields | Line items | Journal | Overall | Exact | Extraction |
|---|---|---|---|---|---|---|
| INV-2026-001 | 31/31 | 2/2 | 5/5 | 100.0% | yes | HIGH |
| INV-2026-002 | 23/23 | 1/1 | 3/3 | 100.0% | yes | HIGH |
| INV-2026-003 | 24/24 | 1/1 | 4/4 | 100.0% | yes | HIGH |
| NOS/26-27/0418 | 51/51 | 5/5 | 6/6 | 100.0% | yes | HIGH |

- Invoices evaluated: **4**
- Field accuracy (headers and totals): **100.0%**
- Line-item accuracy: **100.0%**
- Journal-entry accuracy: **100.0%**
- Overall check accuracy: **100.0%**
- Exact invoices: **4/4**

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
