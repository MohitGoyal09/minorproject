# Deployment

Vercel runs static builds and serverless functions. This project cannot run its
backend there: `pymupdf`, `onnxruntime` and `rapidocr` exceed the serverless
bundle limit and cold-start badly. Split it:

| Part | Host | Why |
|---|---|---|
| React app | **Vercel** | Static Vite build |
| FastAPI | **Render / Fly / Railway** | Long-running process, large native wheels |
| Database | **Neon / Supabase Postgres** | SQLite on an ephemeral disk resets on every redeploy |

## 1. Backend on Render

`render.yaml` in the repo root is a blueprint. In Render: **New > Blueprint**,
pick this repo, apply. It sets:

- root directory `backend`
- build `pip install -r requirements.txt`
- start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- health check `/api/health`
- plan `starter` — RapidOCR plus ONNX Runtime needs more than the 512 MB free tier

Then set `DATABASE_URL` in the dashboard, for example:

```
postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
```

Add the driver to `backend/requirements.txt` when you switch:

```
psycopg2-binary==2.9.10
```

CORS is already `allow_origins=["*"]`, so the Vercel domain is accepted without
configuration.

Verify:

```bash
curl https://<your-service>.onrender.com/api/health
```

## 2. Frontend on Vercel

1. Import the repo, set **Root Directory** to `frontend`.
2. Framework preset: Vite. Build `npm run build`, output `dist`.
3. Add an environment variable for Production and Preview:

```
VITE_API_BASE_URL = https://<your-service>.onrender.com
```

`src/App.jsx` reads it once:

```js
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || '';
```

Locally the variable is unset, so requests stay relative and Vite's `/api` proxy
handles them. Redeploy after changing the variable; Vite inlines env values at
build time.

## 3. Things that behave differently in production

- **Uploads and SQLite live on the instance disk.** On Render that disk is
  replaced on every deploy. Uploaded PDFs and the database vanish. Postgres fixes
  the data; uploaded files are disposable in this design.
- **`Base.metadata.create_all()` runs at import.** The schema appears on first
  boot. There are no migrations yet, so a column change needs a fresh database or
  a manual `ALTER`.
- **OCR is memory-hungry.** First scan loads the ONNX models, roughly 400–600 MB
  resident. On a 512 MB instance the process is killed mid-request.
- **No registration flow.** One admin account is seeded from `ADMIN_EMAIL` /
  `ADMIN_PASSWORD` the first time someone logs in. Set both on the host, and set
  a real `SECRET_KEY` (rotate it to sign everyone out). Tokens live in
  `localStorage`, so an XSS bug would expose them; there is no refresh-token or
  revocation list yet.
- **Windows users:** `run_system.ps1` is local only; the container uses the
  commands above.

## Local check before deploying

```bash
cd backend && python -m pytest -q
cd frontend && npm run build
```
