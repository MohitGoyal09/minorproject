# Intelligent Invoice Processing for Automated Accounting Book Generation

End-to-end invoice intelligence and verified double-entry accounting. The system
reads an invoice PDF or scan, validates every figure, proposes a balanced journal
entry, and generates the books (ledger, trial balance, P&L, balance sheet).

Two halves:

1. **Document intelligence** — text-layer extraction for digital PDFs, OCR fallback
   for scans and photos, layout-aware table reconstruction, template-free field
   heuristics.
2. **Deterministic accounting** — GST-aware interpretation, hard invariant checks,
   immutable ledger, and financial statements derived from journal lines only.

## Requirements

- Python 3.13 or newer
- Node.js 20 or newer

## Setup

```bash
# Backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt   # tests only

# Frontend
cd frontend && npm install && cd ..
```

## Run

```bash
# Terminal 1 - API on http://127.0.0.1:8000 (docs at /docs)
PYTHONPATH=backend python -m uvicorn app.main:app --port 8000 --reload

# Terminal 2 - UI on http://localhost:5173
cd frontend && npm run dev
```

Windows: `./run_system.ps1` starts both. The SQLite database is created on first
start, so no migration step is needed.

If port 8000 is already taken, start the API elsewhere and point the dev proxy at
it:

```bash
PYTHONPATH=backend python -m uvicorn app.main:app --port 8011 --reload
cd frontend && VITE_PROXY_TARGET=http://127.0.0.1:8011 npm run dev
```

## Authentication

Every business endpoint needs a bearer token; `/api/health` and
`/api/auth/login` stay public.

```bash
curl -X POST http://127.0.0.1:8011/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin123"}'
# -> {"access_token":"eyJ...","token_type":"bearer","user":{...}}

curl http://127.0.0.1:8011/api/documents -H "Authorization: Bearer eyJ..."
```

The admin is seeded on first login from `ADMIN_EMAIL` / `ADMIN_PASSWORD`
(defaults `admin@example.com` / `admin123`). Set `SECRET_KEY` and change the
password before exposing the API; see `.env.example`. The UI shows a sign-in
screen and keeps the token for 8 hours (`ACCESS_TOKEN_EXPIRE_MINUTES`).

## Deployment

Vercel hosts the React app; the FastAPI backend needs a container host because
PyMuPDF and ONNX Runtime exceed serverless limits. `render.yaml` is a ready
blueprint for the API, and `docs/DEPLOYMENT.md` has the step-by-step, including
the `VITE_API_BASE_URL` variable and the Postgres requirement (SQLite on an
ephemeral disk resets on every redeploy).

## Tests

```bash
cd backend && python -m pytest -q
```

75 tests cover extraction, table correction, OCR routing, invariants, ledger
posting, corrections, exports, and the ground-truth evaluation.

## Evaluation

```bash
cd backend && PYTHONPATH=. python -m app.eval.report           # print the table
cd backend && PYTHONPATH=. python -m app.eval.report --write ../docs/EVALUATION.md
```

The pipeline is scored against `data/ground_truth/` on header fields, totals,
line items, and every journal line. Current result: **100% check accuracy,
4/4 invoices exact**, including a scanned copy through the OCR path. The report
also states what the four synthetic samples cannot prove.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload a PDF or scanned invoice |
| `POST` | `/api/documents/{id}/process` | Extract, interpret, validate |
| `GET` | `/api/documents/{id}` | Stored invoice, proposal, validation report |
| `PUT` | `/api/documents/{id}/invoice` | Save human corrections, then re-validate |
| `POST` | `/api/journal/post` | Post a balanced entry to the ledger (immutable) |
| `GET` | `/api/reports/ledger` | Posted journal entries |
| `GET` | `/api/reports/trial-balance` | Trial balance |
| `GET` | `/api/reports/profit-and-loss` | Profit & loss |
| `GET` | `/api/reports/balance-sheet` | Balance sheet |
| `GET` | `/api/reports/audit-logs` | Audit trail |
| `GET` | `/api/reports/export/{report}` | CSV or Excel (`?format=csv|xlsx`) |
| `GET` | `/api/reports/export/tally` | Tally Prime voucher import XML |

## How a document flows

```
PDF/scan -> text layer, else OCR -> markdown table -> table correction
        -> field heuristics -> arithmetic/GST/COA invariants
        -> journal proposal -> human review or auto-post -> ledger -> statements
```

A scan is always marked `MEDIUM` confidence and needs human review. Posted
entries are immutable; the API rejects edits with `409`.

## Limits

- Extraction is regex and geometry based. It is template-free but tuned to Indian
  GST invoices; unusual layouts need the review screen.
- Classification is a documented rule set (keywords, HSN prefixes, ITC rules),
  not a trained model.
- Single seeded tenant, no authentication. Add those before exposing the API.

## Sample data

`data/sample_invoices/` holds four digital invoices; `data/ground_truth/` holds
their expected extraction and journal entries; `data/generators/` regenerates
them.
