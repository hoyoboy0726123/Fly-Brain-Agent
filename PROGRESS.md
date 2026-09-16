# PROGRESS

| Phase | Status | Exit Gate |
|---|---|---|
| P0 Bootstrap | ✅ Done (reviewer approved, merged PR #1) | backend/frontend/tests runnable |
| P1 Data ingestion | ✅ Done (awaiting human confirmation) | normalized data + provenance |
| P2 Circuit extraction | ⬜ Not started | deterministic bounded circuit |
| P3 Simulation | ⬜ Not started | tested simplified dynamics |
| P4 Escape | ⬜ Not started | stimulus → action |
| P5 Web UI | ⬜ Not started | interactive end-to-end demo |
| P6 Brain inspector | ⬜ Not started | inspectable provenance |
| P7 Food | ⬜ Future | second behavior |
| P8 Webcam | ⬜ Future | camera stimulus adapter |
| P9 Robot | ⬜ Future | safe physical adapter |

## Current Phase
P1 complete. Stopped before P2, waiting for human confirmation (see START_HERE.md).

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
- (P1) Dataset: the official **MaleCNS v1.0** release (Janelia FlyEM / Cambridge / MRC LMB / Google Research), neuPrint id `male-cns:v1.0`, bulk files from `gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/`, license **CC-BY 4.0** (verbatim from the official website source). No other connectome was considered. Verification record: `docs/dataset_research.md`.
- (P1) The Google Research / Janelia / neuPrint / publisher web pages are blocked by this environment's egress proxy; the official data bucket (`storage.googleapis.com`) and the official website source repository (`github.com/janelia-flyem/male-cns`) were used as authoritative sources instead. A human should spot-check `male-cns.janelia.org/download` once.
- (P1) Production inputs: `body-annotations-…feather` (neurons/annotations), `connectome-weights-…feather` (full graph), `body-neurotransmitters-…feather` (optional). `weight` → `synapse_count`, verified by Σweight = 311,833,243 = `Neuprint_Meta.totalPostCount` = `syn-partners` rows.
- (P1) Neuron set = bodies with `status == "Traced"` by default (165,122; the publishers' own rule for their `-traced-only` table, verified identical). Configurable via `--status` / `--all-statuses`; recorded in `provenance.json`. Open question for the human: align with the paper's 166,691 / neuPrint `:Neuron` set instead?
- (P1) Edges whose endpoints are not both in the neuron set are counted by category and dropped by default (`--keep-dangling` retains them). Result: 25,563,197 edges.
- (P1) `region` is null (not present in the flat annotation table; neuPrint ROI membership not ingested). `neurotransmitter` = the publishers' per-body `predicted_nt` **prediction**, labelled as such; `sex` = constant `male` (specimen). Every other annotation column is carried through verbatim as `mcns_<column>`; NT extras as `mcns_nt_<column>`.
- (P1) Raw files are hashed (sha256 + md5) and md5 is compared with the bucket listing; normalization refuses to run on a mismatch. Parquet outputs are git-ignored; `provenance.json` and `inspection_report.{json,md}` are committed.
- (P1) Tests never download: the synthetic fixture `backend/tests/fixtures/tiny_connectome.json` and synthetic Feather files with the verified MaleCNS schema (`tests/synthetic_malecns.py`) cover the fixture adapter and the production adapter offline.
- (P1) New runtime dependency: `pyarrow` only (Feather/Parquet/compute). No pandas/polars yet.

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

---

## P1 Report (2026-09-16)

### Research gate (before any adapter code)
`docs/dataset_research.md` records, with per-fact verification tags: official name, neuPrint id
`male-cns:v1.0`, release dates (v1.0 2026-06-08; v0.9 2025-10-05), access mechanisms, the
actual v1.0 file list with sizes/md5, actual column schemas (read from the Arrow footers),
neuron identifier (body ID), connectivity representation (`body_pre`,`body_post`,`weight`),
synapse representation (`syn-partners`), annotation tables, license (CC-BY 4.0, verbatim),
blocked domains, and open questions. Nothing was guessed; `-significant-only` (undocumented) is
not used.

### Added / modified files
Backend `backend/app/connectome/`
- `schema.py` — SDD §3 pyarrow schemas + fail-loud validation (`SchemaValidationError`).
- `normalize.py` — pure functions: id stringification, table builders, `classify_edges`, `filter_dangling` + `DanglingReport`, parquet I/O, sha256/md5.
- `adapter.py` — `DatasetAdapter` (inspect / validate_schema / load_neurons / load_connections), `DatasetInfo`, `RawFileRecord`, `InspectionResult`, `ConnectionsResult`.
- `malecns.py` — production `MaleCnsV1Adapter` + `MaleCnsConfig` (verified file names, bucket md5s, column lists; streaming over 2,318 record batches; NT join; status rule).
- `fixture.py` — `SyntheticFixtureAdapter` (every row flagged `synthetic = true`).
- `provenance.py` — `Provenance` / `RawFileEntry` (DATA.md §3 fields + integrity, normalization rules, counts; license required unless synthetic).
- `inspect.py` — `inspect_tables()` → `InspectionReport` (DATA.md §7) with markdown rendering.
- `__init__.py` — exports.
- `app/config/settings.py` — `malecns_raw_subdir` / `malecns_raw_dir`. `pyproject.toml` — `pyarrow`.

Scripts: `scripts/normalize_dataset.py` (raw → `neurons.parquet`, `connections.parquet`, `provenance.json`, `inspection_report.{json,md}`), `scripts/inspect_dataset.py` (report for processed data or `--fixture`).

Tests: `tests/fixtures/tiny_connectome.json` (+ README, SYNTHETIC), `tests/synthetic_malecns.py`, `test_connectome_schema.py`, `test_connectome_normalize.py`, `test_fixture_adapter.py`, `test_malecns_adapter.py`, `test_inspect_report.py`, `test_provenance.py`, `test_data_scripts.py`.

Docs / tooling: `docs/dataset_research.md`, `docs/DEVELOPMENT.md` (§4b data workflow), `README.md`, `Makefile` (`normalize`, `normalize-fixture`, `inspect`, `smoke-data`; `smoke` now includes `smoke-data`).

Data (generated, not committed unless small): `data/processed/neurons.parquet` (6.2 MB, ignored), `data/processed/connections.parquet` (87 MB, ignored), `data/processed/provenance.json`, `data/processed/inspection_report.{json,md}` (committed).

### Unit test results
- `ruff check` (backend + scripts): all checks passed.
- `pytest`: **75 passed** (18 from P0 + 57 new: schema 8, normalize 10, fixture adapter 8, MaleCNS adapter 17, inspection report 5, provenance 3, CLI scripts 6). No test downloads data.
- `npm run typecheck` (frontend): passed (unchanged in P1).
- A real defect was caught by the synthetic-schema tests before the production run: pyarrow joins reject the list-typed `somaLocation` column; the NT join now runs on a `bodyId`-only table.

### Smoke test results
- `scripts/inspect_dataset.py --fixture --keep-dangling`: 8 neurons, 13 edges, dangling pre 1 / post 1 (`syn_unknown_*` reported), synthetic = True.
- `scripts/normalize_dataset.py --adapter malecns` on the real v1.0 files: all md5 match; 165,122 neurons × 49 columns; 25,563,197 connections; 126,293,487 dangling raw edges counted and dropped; 67 s.
- `scripts/inspect_dataset.py` on `data/processed`: 0 missing IDs, 0 duplicate IDs, 0 duplicate edge pairs, synapse_count 1 / 2,591 / median 2.0, license and source recorded.
- `make smoke` (backend `/health`, data smoke, Playwright 4 tests): passed.

### Acceptance Criteria (TASKS.md P1)
| Criterion | Result | Evidence |
|---|---|---|
| normalized neurons/connections generated | ✅ | `data/processed/neurons.parquet`, `connections.parquet` (real data) + fixture run |
| dangling edges reported | ✅ | `DanglingReport` in `provenance.json` (`counts.dangling`) and `inspection_report.md`; fixture shows 2 dangling |
| provenance exists | ✅ | `data/processed/provenance.json` with license, source, download URL, raw file sha256/md5 vs bucket md5, transform script, rules, counts |
| no biological fields invented | ✅ | `region` null; NT labelled prediction; all optional columns null unless present in source; tests assert `region` is null and synthetic rows are flagged |
| tests do not require full download | ✅ | 75 tests run on fixture + synthetic-schema files only |

### Final report (as requested)
- **A. Dataset/version:** MaleCNS v1.0 (`male-cns:v1.0`), released 2026-06-08, from `gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/`.
- **B. Neurons:** 165,122 normalized (status Traced). Annotation table has 211,577 bodies; 166,700 carry a `superclass`; paper headline 166,691 (search-only).
- **C. Connections:** 25,563,197 directed neuron→neuron edges (Σ synapse_count 124,025,046) out of 151,856,684 raw body-pair rows.
- **D. Annotations:** 36 raw columns preserved (`mcns_*`): type (11,751 distinct), class (21), superclass (26 among Traced), subclass, status/statusLabel, somaSide, instance, flywireType/hemibrainType/mancType cross-references, dimorphism, fruDsx, vfbId, somaNeuromere, nerves, … plus NT predictions (8 labels).
- **E. License:** CC-BY 4.0 (official statement "The Male CNS is licensed under CC-BY.").
- **F. Provenance:** `data/processed/provenance.json` (raw sha256/md5 vs bucket md5, source page, download URL, citation links, normalization rules, counts, generator/git commit).
- **G. Tests:** 75 passed, ruff clean.
- **H. Smoke:** fixture + production inspect reports OK; `make smoke` green.
- **I. Known limitations:** see below.

### Known limitations
- Official web pages (Google Research, janelia.org, male-cns.janelia.org, neuPrint, Cell, bioRxiv, doi.org) were unreachable from this environment; facts were verified from the official bucket and the official website source repo. DOI `10.1016/j.cell.2026.08.015` is search-only.
- Neuron definition (`status == "Traced"`, 165,122) differs slightly from the paper's 166,691 and from the 166,700 bodies with a `superclass`; the neuPrint `:Neuron` criterion could not be read. Configurable, recorded in provenance, flagged for human decision.
- `region` is not ingested (needs neuPrint ROI data, 4.6 GB `Neuprint_Neurons.feather`).
- `neurotransmitter` uses the publishers' `predicted_nt` prediction; `consensus_nt` semantics live in the (blocked) paper methods. Both are kept.
- Only body-level connectivity is ingested (no synapse coordinates / ROIs per edge).
- `connections.parquet` (87 MB) is generated locally, not committed; anyone reproducing must download ≈1.1 GB.
- No API endpoints (`GET /datasets`) yet; that belongs to later phases.

### Next phase suggestions (P2 — do not start without confirmation)
1. Graph builder over `neurons.parquet` / `connections.parquet` (scipy sparse or NetworkX on the reduced graph), seed/target resolution by `neuron_id` and by `cell_type`.
2. Bounded directed traversal with `max_hops`, `min_synapses`, hard `max_neurons` abort; deterministic ordering; export circuit artifact (SDD §4) carrying `dataset`, `dataset_version`, extractor config and every edge's provenance (source ids + synapse_count).
3. Tests on the synthetic fixture (hop limit, threshold, directionality, determinism, abort, missing seed); smoke on the fixture and, when present, on the production tables.
4. Decide the neuron-set question (Traced vs paper count) before extraction results are presented as biological.
