# PROGRESS

| Phase | Status | Exit Gate |
|---|---|---|
| P0 Bootstrap | ✅ Done (awaiting human confirmation) | backend/frontend/tests runnable |
| P1 Data ingestion | ⬜ Not started | normalized data + provenance |
| P2 Circuit extraction | ⬜ Not started | deterministic bounded circuit |
| P3 Simulation | ⬜ Not started | tested simplified dynamics |
| P4 Escape | ⬜ Not started | stimulus → action |
| P5 Web UI | ⬜ Not started | interactive end-to-end demo |
| P6 Brain inspector | ⬜ Not started | inspectable provenance |
| P7 Food | ⬜ Future | second behavior |
| P8 Webcam | ⬜ Future | camera stimulus adapter |
| P9 Robot | ⬜ Future | safe physical adapter |

## Current Phase
P0 complete. Stopped, waiting for human confirmation before P1 (see START_HERE.md).

## Blockers
None recorded.

## Decision Log
- MVP is P0-P6.
- Full 166,691-neuron real-time simulation is not an MVP requirement.
- Biological structure, modeled dynamics, and application decoding must remain separate.
- (P0) Backend package layout follows SDD §2; `connectome/`, `circuits/`, `simulation/`, `sensors/`, `motor/` exist as empty, documented packages labelled with their layer (structure / dynamics / decoding) and owning phase. No logic in them yet.
- (P0) Backend routes are served at the root (`GET /health`, per SDD §7). The frontend calls `/api/*`; the Vite dev server proxies `/api/*` to the backend with the prefix stripped. For production builds `VITE_API_BASE_URL` points at the backend origin and CORS allows the frontend origin.
- (P0) All runtime parameters are in `backend/app/config/settings.py` (pydantic-settings, `FLYBRAIN_` env prefix). Route handlers receive settings through dependency injection and hold no configuration.
- (P0) `@playwright/test` is pinned to 1.56.1 to match the Chromium build available in the development environment; developers on other machines run `npx playwright install chromium`.
- (P0) Frontend uses Vite 7 / React 19 / TypeScript 5.9 (strict). No lint/format toolchain added yet to keep dependencies minimal.
- (P0) `.gitignore` excludes `data/raw/*` entirely plus binary data formats anywhere under `data/`; `.gitkeep` files and (later) `data/processed/provenance.json` remain committable.

---

## P0 Report (2026-09-16)

### Added / modified files
Project documents copied to the repository root: `README.md` (pack version + developer Quick Start section), `PRD.md`, `SDD.md`, `DATA.md`, `NEUROSCIENCE.md`, `AGENTS.md`, `TASKS.md`, `PROGRESS.md`, `START_HERE.md`.

Repository tooling
- `.gitignore` — data/raw, binary data formats, Python caches/venv, `.env*` (keeps `.env.example`), node_modules, dist, Playwright outputs.
- `Makefile` — `install`, `backend`, `frontend`, `test`, `test-backend`, `typecheck-frontend`, `lint`, `smoke`, `smoke-backend`, `smoke-frontend`, `clean`.
- `scripts/smoke_test.py` — boots uvicorn on a free port, asserts `GET /health`, stdlib only.
- `docs/DEVELOPMENT.md` — developer run instructions, configuration table, layout.
- `data/raw/.gitkeep`, `data/processed/.gitkeep`, `data/circuits/.gitkeep`.

Backend (`backend/`)
- `pyproject.toml` — package metadata, dependencies (fastapi, uvicorn, pydantic, pydantic-settings), dev extras (pytest, httpx, ruff), pytest and ruff configuration.
- `app/__init__.py` — `__version__`, `SERVICE_NAME`, `CURRENT_PHASE`.
- `app/__main__.py` — `python -m app` entry using configured host/port.
- `app/config/settings.py`, `app/config/__init__.py` — `Settings`, `get_settings()` (cached), `clear_settings_cache()`.
- `app/models/health.py` — `HealthResponse` schema.
- `app/api/health.py`, `app/api/__init__.py` — `GET /health`.
- `app/main.py` — `create_app(settings=None)` factory with CORS; module-level `app`.
- `app/connectome/`, `app/circuits/`, `app/simulation/`, `app/sensors/`, `app/motor/` — empty documented packages.
- `.env.example`.
- `tests/conftest.py`, `tests/test_health.py`, `tests/test_config.py`, `tests/test_app.py`.

Frontend (`frontend/`)
- `package.json`, `tsconfig.json`, `tsconfig.node.json`, `vite.config.ts` (dev proxy `/api` → backend), `index.html`, `.env.example`.
- `src/main.tsx`, `src/App.tsx`, `src/styles.css`, `src/vite-env.d.ts`.
- `src/api/types.ts` (typed `HealthResponse` + runtime guard), `src/api/client.ts` (`fetchHealth`), `src/api/useBackendHealth.ts` (hook).
- `src/components/HealthStatus.tsx` — health card with ok / unreachable / re-check.
- `src/environment/`, `src/brain/`, `src/dashboard/` — reserved (`.gitkeep`).
- `playwright.config.ts` — starts backend (uvicorn) and Vite, then runs `tests/smoke.spec.ts`.

### Unit test results
- `ruff check .` (backend): all checks passed.
- `pytest` (backend): **18 passed**, 0 failed (`test_app.py` 6, `test_config.py` 7, `test_health.py` 5). Two third-party deprecation warnings from starlette/anyio, none from project code.
- `npm run typecheck` (frontend, strict TS for `src/`, config and tests): passed.
- `npm run build` (frontend): production build succeeded.

### Smoke test results
- Backend: `scripts/smoke_test.py` → `PASS`. Response: `{"status":"ok","service":"flybrain-agent-backend","version":"0.0.1","environment":"development","phase":"P0"}`.
- Backend entry point: `FLYBRAIN_PORT=8011 FLYBRAIN_ENVIRONMENT=production python -m app` served `/health` with `environment: production`; CORS header returned for `http://localhost:5173`.
- Frontend: Playwright `npm run test:e2e` → **4 passed**: page loads; page displays live backend health (status `ok`, service, phase `P0`, non-empty version); unreachable state when `/api/health` is aborted; Re-check recovers to `ok` once the backend is back.
- One Playwright run failed while iterating: the recovery test originally failed only the first request, which React StrictMode's double-invoked mount effect swallowed in dev mode. The test now keeps the backend down until Re-check is pressed. A separate one-off "did not expect test.describe()" error came from running Playwright outside `frontend/` (no config found); documented in `docs/DEVELOPMENT.md`.

### Acceptance Criteria (TASKS.md P0)
| Criterion | Result | Evidence |
|---|---|---|
| backend starts | ✅ | `python -m app` / uvicorn served `GET /health` 200 |
| frontend starts | ✅ | Vite dev server served the page; Playwright observed heading + health card |
| tests run | ✅ | pytest 18 passed; typecheck passed; Playwright 4 passed |
| no raw dataset required | ✅ | no code reads `data/`; `data/raw/*` git-ignored; tests and smoke tests ran with empty `data/` |

Smoke test definitions from TASKS.md: "Backend `/health` returns success" ✅; "Frontend loads and can display backend health" ✅.

### Known limitations
- P0 only: no dataset adapter, graph, simulation, sensor, motor or WebSocket code exists. The layer packages are empty on purpose.
- The UI is a single health card; the three-column Environment / Fly Brain / Action layout is deferred to P5.
- No CI workflow yet; checks run locally via `make test` / `make smoke`.
- No frontend lint/format toolchain (ESLint/Prettier) yet; only strict `tsc`.
- `@playwright/test` is pinned to 1.56.1; other machines may need `npx playwright install chromium` once.
- Backend `python -m app` enables uvicorn auto-reload only when `FLYBRAIN_ENVIRONMENT=development`.

### Next phase suggestions (P1 — do not start without confirmation)
1. Follow DATA.md §2 first: inspect the current official MCNS dataset access page, actual file list, schema, version and license. Record findings before writing any adapter code. Stop and report if access or license is unclear.
2. Add `DatasetAdapter` interface (`inspect`, `load_neurons`, `load_connections`, `validate_schema`) in `backend/app/connectome/`, plus the synthetic `backend/tests/fixtures/tiny_connectome.*` fixture, clearly labelled synthetic.
3. Add `scripts/inspect_dataset.py` producing the DATA.md §7 report and `data/processed/provenance.json` writer.
4. Add pyarrow / pandas-or-polars dependencies only when the adapter needs them.
