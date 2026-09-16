# Development Guide

How to run, test and smoke-test FlyBrain Agent locally. P0 (Bootstrap) needs **no dataset**.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | ^20.19 or >=22.12 | required by Vite 7 |
| npm | 10+ | ships with Node |
| make | any | optional convenience wrapper |

## 1. Install

```bash
# from the repository root
make install
```

Or step by step:

```bash
# Backend: virtualenv + editable install with dev extras
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -e "backend[dev]"

# Frontend
cd frontend && npm install
```

Playwright needs a Chromium build matching the pinned `@playwright/test` version. If one is
not already available on your machine:

```bash
cd frontend && npx playwright install chromium
```

## 2. Run

Two terminals:

```bash
make backend    # FastAPI on http://127.0.0.1:8000  (docs at /docs, health at /health)
make frontend   # Vite on   http://127.0.0.1:5173
```

Equivalent raw commands:

```bash
cd backend && .venv/bin/python -m app          # honours FLYBRAIN_* env vars, reloads in development
cd frontend && npm run dev
```

Open http://127.0.0.1:5173. The page shows the backend health card (status, service,
version, environment, phase). In development the UI calls `/api/*`, which Vite proxies to
the backend with the `/api` prefix stripped (`/api/health` -> `/health`).

## 3. Tests

```bash
make test               # backend pytest + frontend typecheck
make test-backend       # cd backend && .venv/bin/python -m pytest
make typecheck-frontend # cd frontend && npm run typecheck
make lint               # ruff check on backend
```

## 4. Smoke tests

```bash
make smoke              # both of the following
make smoke-backend      # scripts/smoke_test.py: boots uvicorn on a free port, asserts GET /health
make smoke-frontend     # cd frontend && npm run test:e2e (Playwright)
```

The Playwright run starts **both** servers itself (backend via `backend/.venv` Python, or
`FLYBRAIN_PYTHON`, else `python3`; frontend via `npm run dev`) and verifies that the page
loads and displays live backend health, plus the unreachable/recovery states.

Run Playwright from `frontend/` via `npm run test:e2e` (or `make smoke-frontend` from the
root). Invoked from another directory, `playwright test` does not find
`frontend/playwright.config.ts`, falls back to defaults, and may load the spec files with a
different Playwright copy (error: "did not expect test.describe() to be called here").

## 5. Configuration

Backend (`FLYBRAIN_` prefix, optional `backend/.env`, see `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `FLYBRAIN_ENVIRONMENT` | `development` | `development` / `test` / `production` |
| `FLYBRAIN_HOST` | `127.0.0.1` | bind address for `python -m app` |
| `FLYBRAIN_PORT` | `8000` | bind port for `python -m app` |
| `FLYBRAIN_LOG_LEVEL` | `INFO` | uvicorn log level |
| `FLYBRAIN_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | comma-separated allowed origins |
| `FLYBRAIN_DATA_DIR` | `<repo>/data` | parent of `raw/`, `processed/`, `circuits/` |

Frontend (`frontend/.env.local`, see `frontend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `/api` | backend base URL used by the UI |

Dev-server / test ports:

| Variable | Default | Purpose |
|---|---|---|
| `FLYBRAIN_BACKEND_URL` | `http://127.0.0.1:8000` | Vite proxy target |
| `FLYBRAIN_BACKEND_PORT` | `8000` | backend port started by Playwright |
| `FLYBRAIN_FRONTEND_PORT` | `5173` | Vite port (dev server and Playwright) |
| `FLYBRAIN_PYTHON` | auto | interpreter Playwright uses to start the backend |

## 6. Layout (P0)

```text
backend/app/api          HTTP routers (GET /health)
backend/app/config       Settings (pydantic-settings)
backend/app/models       API schemas
backend/app/connectome   BIOLOGICAL STRUCTURE  (P1, empty)
backend/app/circuits     BIOLOGICAL STRUCTURE  (P2, empty)
backend/app/simulation   COMPUTATIONAL DYNAMICS (P3, empty)
backend/app/sensors      APPLICATION DECODING  (P4, empty)
backend/app/motor        APPLICATION DECODING  (P4, empty)
backend/tests            pytest suite
frontend/src/api         typed API client + hooks
frontend/src/components  UI components
frontend/src/{environment,brain,dashboard}  reserved for P5/P6
frontend/tests           Playwright smoke tests
data/{raw,processed,circuits}  gitkept; raw data is never committed
scripts/smoke_test.py    backend smoke test
```

## 7. Data policy reminder

`data/raw/` is git-ignored and must stay that way (see `DATA.md`). Nothing in P0 reads,
downloads or fabricates connectome data.
