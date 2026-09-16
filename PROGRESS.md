# PROGRESS

| Phase | Status | Exit Gate |
|---|---|---|
| P0 Bootstrap | ✅ Done (reviewer approved, merged PR #1) | backend/frontend/tests runnable |
| P1 Data ingestion | ✅ Done (reviewer approved, PR #2); P1.1 canonical graph definition ✅ Done (reviewer approved, PR #3) | normalized data + provenance |
| P2 Circuit extraction | ✅ Done (reviewer approved, PR #4) | deterministic bounded circuit |
| P3 Simulation | ✅ Done (reviewer approved, PR #5) | tested simplified dynamics |
| P4 Escape | ✅ Done (reviewer approved, PR #6) — biological status PARTIALLY SUPPORTED | stimulus → action |
| P5 Web UI | ✅ Done (awaiting human confirmation) | interactive end-to-end demo |
| P6 Brain inspector | ⬜ Not started | inspectable provenance |
| P7 Food | ⬜ Future | second behavior |
| P8 Webcam | ⬜ Future | camera stimulus adapter |
| P9 Robot | ⬜ Future | safe physical adapter |

## Current Phase
P5 (Interactive Web Demo) complete. Stopped before P6, waiting for human confirmation.

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
- (P2) Graph representation: numpy CSR out-adjacency + CSR in-adjacency (int32 indices/weights, int64 indptr) built from the canonical parquet tables with pyarrow `index_in` + `lexsort`; ~418 MB for 25.56 M edges; no NetworkX for the full graph. A memory-mappable `.npy` cache (`data/processed/graph_cache/`, git-ignored, keyed on table size/mtime) makes reloads ~0.2 s.
- (P2) Extraction = multi-source BFS by hop level (downstream = out-edges, upstream = in-edges), `synapse_count >= min_synapses`, `max_neurons` checked *before* a hop level is added (hard abort, nothing truncated). The artifact is the induced subgraph: every canonical edge between included neurons above the threshold, stored pre→post regardless of traversal direction. Ids in configs are deduplicated and sorted, so output is independent of input order.
- (P2) Targets only report reachability (`reachable`, `minimum_path_length` = BFS hop); no path is fabricated. Optional `restrict_to_target_paths` keeps neurons with `hop_from_seed + hop_to_target <= max_hops` (off by default).
- (P2) Artifacts: `data/circuits/<id>.json` (full) + `<id>.parquet` (edges with the five provenance columns + schema metadata) sealed with a sha256 `circuit_hash`; `Circuit.load` verifies it. Large technical smoke circuits with real ids are git-ignored; the perf report and the fixture circuit are committed. New runtime dependency: `numpy`.
- (P3) COMPUTATIONAL DYNAMICS layer = `backend/app/simulation/`: simplified discrete-time LIF-like model on a P2 `Circuit`. `SimulationConfig` is frozen pydantic, labelled **COMPUTATIONAL MODEL PARAMETERS — NOT MEASURED MALECNS PARAMETERS**; every output is SIMULATED and labelled so.
- (P3) Weights: `w = transform(synapse_count) × weight_scale`, transform ∈ {log1p (default), linear, sqrt, binary}. `synapse_count` = structural observation; `w` = computational transformation, not an electrophysiological strength.
- (P3) No excitatory/inhibitory sign is derived: `sign_mode = unsigned_excitatory_only` is the only mode. Neurotransmitter *predictions* ride along as `neurotransmitter_prediction` metadata and do not influence dynamics; a signed mode would need explicit implementation, documentation and justification.
- (P3) Stimulus is generic input injection (`stimulate(neuron_ids, intensity, duration_steps)`); no sensory/behavioural naming. One-step synaptic delay; refractory neurons hold the reset potential and ignore input.
- (P3) Snapshots reference the circuit by `circuit_id` + `circuit_hash` only; biological provenance is never copied into simulation artifacts. Large snapshots are git-ignored; run reports are committed.
- (P3) Stability is a model property: on the dense 1,992-neuron technical subgraph the default parameters reverberate (period 3); `weight_scale ≈ 0.2` propagates then decays; ≤ 0.15 does not propagate. Recorded in NEUROSCIENCE.md §8; parameters must be recorded with every experiment.
- (P4) Research gate first (`docs/circuits/escape_v1.md`): sensory = LC4 + LPLC2, output = DNp01 (giant fiber), all identified by exact MaleCNS `cell_type` (GF corroborated by instance `DNp01(GF)` and hemibrainType "Giant Fiber"); all 311 LC4/LPLC2 synapse directly onto the ipsilateral GF (0 contralateral edges). Literature (Klapoetke 2017, von Reyn 2017, Ache 2019, Wu 2016, Namiki 2018, Jang 2023, Dombrovski 2023) verified via search metadata only — journal sites are blocked here. **BIOLOGICAL CIRCUIT STATUS: PARTIALLY SUPPORTED.**
- (P4) Negative results recorded, nothing substituted: LC6, LC16, LPLC1 have no usable direct edge to the GF; two-hop circuits exceed the 2,000-neuron limit; the contralateral GF pathway is unidentified.
- (P4) escape_v1 = monosynaptic LC4/LPLC2 → GF circuit extracted with P2 (max_hops 1, min_synapses 10, restrict_to_target_paths): 286 neurons / 932 edges, hash `db7c46e6…`. The config records the full sensory population (311), the stimulated subset in the circuit (284) and the 27 excluded LPLC2 with the reason.
- (P4) Stimulus schema `looming / left|center|right / intensity 0..1` is APPLICATION INPUT; mapping = `current = intensity × gain` into the ipsilateral group (left → L, right → R, center → both). Decoder exposes only `NO_ACTION` / `ESCAPE` (GF azimuth-invariant); the firing GF side is metadata. Every result carries the disclaimer "STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED. STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS."
- (P4) No parameter was tuned toward an outcome: the demo runs on P3 defaults; `simulation_config_overrides` in the config is empty and any future change must be recorded in escape_v1.md.
- (P5) The web API is a *behaviour-level* API over the P4 runner (`GET /escape/config`, `POST /escape/run`, `WS /ws/escape` in `backend/app/api/escape.py`); it contains no simulation, mapping or decoding logic. The generic SDD §7 endpoints (`/circuits`, `/simulation/*`, `/neurons/{id}`, `/ws/simulation`) are deferred to the brain inspector (P6+). The frontend keeps the `/api` prefix (Vite proxy, now also for WebSocket upgrades).
- (P5) Per-group activity (`EscapeResult.group_activity`: per-step SIMULATED spike counts per `cell_type × side` group, plus `group_edges` aggregated from the artifact) is computed once in the P4 runner from the engine's `spikes_per_step`, the circuit node metadata and the configured sides — so the API and the UI never re-derive activity or invent structure. Sides come only from the escape config; edges only from the artifact.
- (P5) The UI replays the backend result step by step (one backend step per tick, `?pace=` ms, default 140 ms): looming-disc size, node glow, active edges, timeline highlights and the final action all read the backend per-step data. No client-side timer generates activity, and the action is shown only after the last backend step has been replayed. Over WebSocket the backend streams `stimulus_started → neural_activity × steps → sensory_activation → output_activation → action_decoded → experiment_finished` (derived from the same result); REST is used only when the socket cannot be opened.
- (P5) Error contract shared by HTTP and WebSocket: `invalid_request` 422, `config_unavailable` / `circuit_unavailable` / `circuit_mismatch` 503, `simulation_error` 500, `timeout` 504. The escape service is loaded at startup (`lifespan`) and re-attempted per request after a failure; `/health` stays up when the circuit is missing. The UI shows `NO RESULT` for any failed run — ESCAPE is never displayed without a successful backend result.
- (P5) Only `NO ACTION` / `ESCAPE` are rendered (the decoder's action set); the firing giant-fiber side is displayed as metadata `GF activity: Left / Right / Both / None`. The fly's takeoff animation is direction-less and labelled as such.
- (P5) `CURRENT_PHASE` in `backend/app/__init__.py` is now updated per delivered phase (`P5`); the Playwright health smoke asserts it.
- (P5) Playwright happy paths run against the live backend; only error states intercept requests (`page.route` / `page.routeWebSocket`, installed before navigation). Smoke screenshots are written to `docs/screenshots/` by `tests/smoke-demo.spec.ts` and committed.
- (P1.1) **Source dataset ≠ canonical simulation graph** (DATA.md §8). SOURCE DATASET = MaleCNS v1.0, ≈166,700 neurons (project figure; equals the 166,700 bodies with a `superclass`; paper 166,691). CANONICAL SIMULATION GRAPH = `status == "Traced"`, 165,122 neurons, 25,563,197 connections. The canonical count is never presented as the dataset census. Both blocks are mandatory in `provenance.json` for biological data (`Provenance` validator), reported by `inspect_dataset.py`, written into the parquet schema metadata, and guarded by `tests/test_canonical_graph.py`. Traced filtering behaviour is unchanged.

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

---

## P1.1 Report (2026-09-16) — Canonical Graph Definition

Scope: make the distinction between the published SOURCE DATASET and the CANONICAL SIMULATION
GRAPH explicit everywhere. No change to the `status == "Traced"` selection, no circuit
extraction.

### Modified files
- `DATA.md` — new §8 "Source Dataset vs Canonical Simulation Graph" (definitions, counts, rules).
- `README.md` — new section "來源資料集 vs Canonical 模擬圖"; 165,122 is always labelled as the canonical subset.
- `docs/dataset_research.md` §6.2, `docs/DEVELOPMENT.md` — pointers to the distinction.
- `backend/app/connectome/adapter.py` — `DatasetInfo.source_name`, `official_neuron_count`, `official_neuron_count_source`.
- `backend/app/connectome/provenance.py` — `SourceDataset`, `CanonicalGraph` models; `Provenance.source_dataset` / `canonical_graph`, required for non-synthetic data.
- `backend/app/connectome/inspect.py` — report carries both blocks plus `canonical_graph_consistent`; markdown prints "## Source dataset" and "## Canonical simulation graph".
- `backend/app/connectome/malecns.py` — `SOURCE_NAME`, `OFFICIAL_NEURON_COUNT = 166_700` with its basis, `MaleCnsConfig.selection_rule`, `inspect()` now summarises the source (annotated bodies, status counts, bodies with superclass, raw connection rows).
- `backend/app/connectome/fixture.py` — fixture selection rule and source counts.
- `backend/app/connectome/__init__.py` — exports.
- `scripts/normalize_dataset.py` — writes `source_dataset` / `canonical_graph`, prints both, stores them in the parquet schema metadata.
- `scripts/inspect_dataset.py` — fixture path reports both blocks.
- `backend/tests/test_canonical_graph.py` (new, 13 tests), `test_provenance.py`, `test_fixture_adapter.py` (updated).
- `data/processed/provenance.json`, `inspection_report.{json,md}` — regenerated from the real v1.0 files (checksums OK, 79 s).

### Test results
- `ruff check`: all checks passed.
- `pytest`: **88 passed** (75 previous + 13 new). Guards include: default rule still `("Traced",)`; biological provenance rejected without both blocks; committed `provenance.json` holds source 166,700 / canonical 165,122 / 25,563,197 with `status == "Traced"`; committed report consistent; normalize/inspect scripts emit both blocks; parquet metadata carries the rule; DATA.md documents the distinction; every README line mentioning 165,122 says "canonical".

### Smoke results
- `make smoke`: backend `/health` PASS; data smoke (fixture + production inspect) prints both sections, `consistent with the normalized tables: True`; Playwright 4 passed.

### Final counts
| | Neurons | Connections |
|---|---:|---:|
| SOURCE DATASET — MaleCNS v1.0 | ≈166,700 official (211,577 annotated bodies; 166,700 with `superclass`; paper 166,691) | 151,856,684 raw body→body rows |
| CANONICAL SIMULATION GRAPH — `status == "Traced"` | **165,122** | **25,563,197** |

### Known limitations
- The "≈166,700" figure is the project-level description supplied at review; it matches the `superclass` count empirically but the official pages remain unreachable from this environment, so its wording is recorded as a basis string rather than a verbatim quote.
- The canonical rule is still a project decision; changing it (e.g. Traced+Assign) regenerates a different canonical graph and is recorded automatically.

---

## P2 Report (2026-09-16) — Graph & Circuit Extractor

### A. Architecture (`backend/app/circuits/`, BIOLOGICAL STRUCTURE layer)
- `graph.py` — `ConnectivityGraph`: canonical graph as CSR out/in adjacency; `from_tables()`, `load(processed_dir, use_cache)`, `resolve()` (fail-loud id mapping), `successors/predecessors/neighbors(min_synapses)`, `node_metadata()`, `fingerprint()`; `.npy` cache with validity stamp.
- `extractor.py` — `CircuitExtractor.traverse()` (bounded multi-source BFS) and `.extract(config, circuit_id)` → `Circuit`; `_induced_edges()`; stats (visited/returned/examined, timings, RSS).
- `artifact.py` — pydantic `ExtractorConfig`, `Circuit`, `CircuitNode` (`minimum_hop_from_seed`, `is_seed`, `is_target`, nullable `cell_type`/`cell_class`/`neurotransmitter`), `CircuitEdge` (pre, post, synapse_count, dataset, dataset_version), `TargetReport`, `CanonicalGraphRef`, `ExtractionStats`, `CircuitProvenance`; `save()/load()/edges_table()`, integrity hash.
- `errors.py` — `GraphBuildError`, `MissingNeuronError`, `MaxNeuronsExceededError`, `ArtifactIntegrityError`.
- Scripts: `scripts/extract_circuit.py` (CLI), `scripts/smoke_circuit.py` (fixture expectation + technical MaleCNS run + perf report). Makefile: `extract`, `smoke-circuit` (part of `smoke`). Settings: `graph_cache_dir`.

### B. Graph representation
CSR arrays: `out_indptr[N+1]`, `out_indices[E]` (int32 post index), `out_weights[E]` (int32), and the mirror `in_*` grouped by postsynaptic neuron; `neuron_ids[N]` maps index → id, a dict maps id → index. Build: pyarrow `index_in` (string ids → indices), numpy `lexsort`, `bincount`/`cumsum`. Duplicate edges, dangling endpoints, mixed datasets and non-unique ids fail loudly. Production: N = 165,122, E = 25,563,197, arrays 418.3 MB.

### C. Tests
`pytest`: **134 passed** (88 previous + 46 new in `test_circuit_graph.py` 12, `test_circuit_extractor.py` 24, `test_circuit_artifact.py` 7, `test_circuit_scripts.py` 3). Coverage of the required list: directionality (down vs up on the same seed), max_hops (0/1/2, target beyond hops), min_synapses (traversal + induced edges), upstream, downstream, determinism (seed order), missing seed, missing target, max_neurons abort (hop 0/1/2, exactly-at-limit allowed), unreachable target, provenance preservation (every edge verbatim from the fixture edge list, nothing invented), export/import round trip (JSON + Parquet + metadata), tamper detection, cache build/reuse/invalidation, CSR vs brute force and BFS vs naive reference on a seeded random graph. `ruff check`: clean. Frontend typecheck unchanged.

### D. Smoke test
- Fixture: downstream from `syn_001`, 2 hops, min 1 → exactly the expected 6 nodes / 9 edges; targets `syn_007` reachable (2), `syn_002` unreachable; JSON round trip and parquet row count verified.
- Production (**TECHNICAL EXTRACTION SMOKE TEST — NOT A BIOLOGICALLY INTERPRETED CIRCUIT**; seed = lowest-index neuron with ≥ 3 downstream partners at min_synapses 10, target = its lowest-index hop-2 successor; chosen mechanically, no biological meaning):
  - `smoke_technical_downstream_min10_hops2`: seed 10001, target 10010 → reachable, minimum_path_length 2.
  - `smoke_technical_upstream_min10_hops2`: aborted as designed (hop 2 would reach 11,741 neurons > 2,000) — demonstrates the hard limit on real data.
  - `smoke_technical_upstream_min10_hops1`: succeeded.
- `make smoke` (health, data, circuit, Playwright): passed.

### E. Performance (this container, 15 GB RAM; graph 165,122 / 25,563,197)
| Measure | Value |
|---|---|
| Graph load, cold (parquet → CSR + cache write) | 26.4 s |
| Graph load, warm (memory-mapped `.npy` cache) | 0.20–0.26 s |
| Adjacency arrays | 418.3 MB |
| Process max RSS (warm run incl. Python/pyarrow) | ≈ 576 MB |
| Downstream 2 hops, min 10: visited / returned / edges / examined / time | 1,992 / 1,992 / 36,755 / 15,060 / 0.15–0.34 s |
| Upstream 1 hop, min 10: visited / returned / edges / examined / time | 330 / 330 / 3,129 / 695 / 0.012 s |
| Upstream 2 hops, min 10 | aborted before hop 2 (11,741 > 2,000) |
Report file: `data/circuits/smoke_technical_extraction.perf.json`.

### F. Sample extracted circuit size
1,992 neurons / 36,755 directed edges (downstream, 2 hops, min_synapses 10, max_neurons 2000) — JSON 6.6 MB, Parquet 108 KB; upstream 1 hop: 330 neurons / 3,129 edges.

### Acceptance Criteria (P2)
| Criterion | Result | Evidence |
|---|---|---|
| deterministic bounded extraction works | ✅ | fixture expectation reproduced; seed-order determinism test; sorted ids/nodes/edges |
| directionality works | ✅ | downstream vs upstream tests; edges always pre→post |
| thresholds work | ✅ | min_synapses filters traversal and induced edges |
| max_neurons hard abort works | ✅ | `MaxNeuronsExceededError` tests; production upstream run aborted before hop 2 |
| missing IDs fail loudly | ✅ | `MissingNeuronError` for seeds and targets, listing the ids |
| biological edge provenance preserved | ✅ | every edge = verbatim canonical edge with dataset/version; artifact `verify()` |
| exported artifact can be loaded again | ✅ | JSON/Parquet round trip, hash verified, tamper rejected |
| synthetic tests pass | ✅ | 46 new tests |
| production smoke passes if data available | ✅ | technical extraction on MaleCNS v1.0 |
| TASKS.md: no exported edge without source provenance | ✅ | `CircuitEdge` requires the five columns; `verify()` rejects foreign dataset |

### G. Known limitations
- Induced-subgraph semantics: the artifact contains *all* canonical edges among included neurons above the threshold (including edges into earlier hops and self-loops); it does not restrict to traversal-tree edges. Documented; `restrict_to_target_paths` narrows to seed→target paths.
- `minimum_hop_from_seed` is the BFS hop count under the `min_synapses` filter; it is not weighted by synapse count.
- Node metadata in artifacts is limited to `cell_type`, `cell_class`, `neurotransmitter` (nullable, from the canonical table); regions are unavailable (P1 limitation).
- The `.npy` cache is validated by file size/mtime of the parquet tables, not by content hash; deleting `data/processed/graph_cache/` forces a rebuild.
- The technical smoke circuits use mechanically chosen real ids and carry no biological meaning; no looming/escape neuron selection has been attempted (that is P4's research gate).
- Extraction runs in-process; no API endpoint (`POST /circuits/extract`) yet (later phase).

### Next phase suggestions (P3 — do not start without confirmation)
1. `SimulationConfig` + weight normalization function from `synapse_count` (documented, config-driven).
2. Discrete-time LIF-like engine over a `Circuit` artifact (vectorized numpy over the induced edge list), deterministic seed, stimulate/step/run/reset, activity snapshots; clearly labelled modeled, not measured.
3. Tests: decay without input, firing with sufficient input, propagation across a fixture edge, deterministic reset; no inhibition unless a documented sign source exists (the canonical table has NT *predictions* only).

---

## P3 Report (2026-09-16) — Neural Simulation Engine

### A. Simulation architecture (`backend/app/simulation/`, COMPUTATIONAL DYNAMICS layer)
- `config.py` — `SimulationConfig` (frozen, `extra="forbid"`, label field pinned to "COMPUTATIONAL MODEL PARAMETERS — NOT MEASURED MALECNS PARAMETERS"): `dt`, `resting_potential`, `reset_potential`, `threshold`, `leak`, `refractory_steps`, `weight_transform`, `weight_scale`, `stimulus_gain`, `noise_std`, `max_potential`, `max_steps_per_run`, `random_seed`, `sign_mode`. Cross-field validation: `threshold > reset`, `threshold > resting`, `max_potential > threshold`, `0 ≤ leak·dt ≤ 1`, all values finite.
- `weights.py` — `normalize_weights(counts, transform, scale)`; rejects negative/non-finite counts, non-positive/non-finite scale, unknown transform, non-finite results.
- `engine.py` — `SimulationEngine(circuit, config)`: reads the circuit once (ids, edges, counts, NT metadata; edges to unknown nodes → `CircuitCompatibilityError`), builds per-neuron arrays (`threshold`, `reset_potential`, `leak` — heterogeneity hook) and mutable state (`membrane_potential`, `refractory_remaining`, `fired`). Methods `reset()`, `stimulate()`, `step()`, `run()`, `get_state()`, `get_activity()`, `snapshot()`, `from_snapshot()`; numpy-vectorised (`np.bincount` over the edge list for synaptic input).
- `state.py` — `NeuronState`, `StimulusRecord`, `SimulationState`, `StepSummary`, `RunSummary`, `SimulationSnapshot` (JSON save/load).
- `errors.py` — `CircuitCompatibilityError`, `UnknownNeuronError`, `InvalidStimulusError`, `NumericalInstabilityError`, `SimulationLimitError`, `SnapshotMismatchError`.
- Scripts `scripts/run_simulation.py`, `scripts/smoke_simulation.py`; Makefile `simulate`, `smoke-simulation` (part of `smoke`); `Settings.simulations_data_dir`; outputs in `data/simulations/` (`*.report.json` tracked, `*.snapshot.json` ignored).
- The three layers stay separate: BIOLOGICAL STRUCTURE (canonical graph, circuit artifact) → COMPUTATIONAL DYNAMICS (this engine) → APPLICATION DECODING (not implemented).

### B. Equations / model
Per step, for a non-refractory neuron *i* (model units):
`V_i ← V_rest + (V_i − V_rest)(1 − leak·dt) + Σ_j w_ji·fired_j(prev) + gain·Σ intensity + N(0, noise_std)`;
`V_i ← min(V_i, max_potential)`; NaN/Inf → `NumericalInstabilityError`;
`fired_i ← V_i ≥ threshold` ⇒ `V_i = V_reset`, `refractory_i = refractory_steps`.
Refractory neurons hold `V_reset`, ignore input, count down. Synaptic delay = one step. Defaults: dt 1.0, rest 0, reset 0, threshold 1.0, leak 0.2 (decay factor 0.8), refractory 2, noise 0, max_potential 100, max_steps_per_run 10,000, seed 0.

### C. Weight normalization
`w = transform(synapse_count) × weight_scale`, transform ∈ {`log1p` (default), `linear`, `sqrt`, `binary`}; configurable via `SimulationConfig`, tested for each transform (values, monotonicity, non-negativity, scale linearity, invalid inputs). Documented in NEUROSCIENCE.md §8 and SDD.md §6: synapse_count is the biological structural observation, the weight is a computational transformation. Signs: none invented (`unsigned_excitatory_only`).

### D. Tests
`pytest`: **205 passed** (134 previous + 71 new: config 28, weights 8, engine 27, snapshot 4, scripts 3). Coverage of the required list: reset; single neuron firing; threshold (inclusive, boundary); leak (geometric, configurable, non-zero rest, leak 0 and 1); refractory (blocks firing for N steps, holds reset, ignores input); weighted propagation (strong vs weak edge); multi-hop propagation with one-step delay (chain and fixture: hop k fires at step k+1, then activity stops and potentials return to rest); weight normalization (all transforms); explicit transform/scale changing dynamics; unsigned mode (no negative weights, NT metadata preserved but inert); determinism (with and without noise, seed sensitivity); unknown neuron; invalid stimuli (duration 0/negative/non-int, intensity negative/NaN/Inf/non-numeric, empty ids); run limits; NaN/Inf protection (state NaN, non-finite weights rejected, clamp keeps finite); incompatible circuits; state fields; activity raster; snapshot serialization + round trip; snapshot references circuit hash and carries no provenance; resume from snapshot equals uninterrupted run (RNG state restored); snapshot/circuit mismatch rejected; no biological metadata mutation (circuit unchanged and hash intact after runs); CLI scripts. `ruff check` clean; frontend typecheck unchanged. No test needs MaleCNS.

### E. Technical smoke — TECHNICAL CONNECTOME-GROUNDED SIMULATION — NOT A BIOLOGICAL ACTIVITY CLAIM
- Fixture demo (synthetic): stimulate `syn_001` (intensity 2.0, 3 steps) → seed fires at step 1, hop-1 neurons at step 2, hop-2 at step 3, then no firing for 27 steps and all potentials back at rest. PASS.
- Real P2 circuit `smoke_technical_downstream_min10_hops2` (1,992 neurons / 36,755 edges, seed 10001 chosen mechanically in P2), generic stimulus intensity 2.0 for 5 steps, 50 steps:

| Variant (`weight_scale`) | Neurons activated | Firing events | Activity stopped by step 40 | Pattern |
|---|---:|---:|---|---|
| default (1.0) | 1,992 | 31,900 | no | period-3 reverberation 1 → 27 → 1,964 |
| 0.5 | 1,992 | 31,900 | no | same period-3 pattern |
| 0.3 | 1,992 | 30,628 | no | sustained irregular (1, 2, 105, 211, 819, …) |
| 0.2 | 10 | 11 | yes (quiet after step 8) | transient propagation then decay |
| 0.15 / 0.1 / 0.05 | 1 | 2 | yes | seed only, no propagation |

Report: `data/simulations/smoke_technical_simulation.report.json`. These outcomes describe the computational model on a positive-only dense subgraph; no behaviour or biological meaning is assigned.

### F. Performance (this container)
| Measure | Value |
|---|---|
| Engine build for 1,992 neurons / 36,755 edges | ≈ 9 ms |
| Mean step time (default params, 1,000-step benchmark) | ≈ 0.19 ms/step |
| Mean step time (damped, few spikes) | ≈ 0.11 ms/step |
| 50-step run | ≈ 10 ms |
| Peak RSS of the smoke process (incl. circuit load) | ≈ 184 MB |
| Fixture (6 neurons) 30 steps | < 1 ms |

The MVP target (≈ 2,000 neurons, tens of thousands of edges, interactive runs) is met with large margin; the full 165,122-neuron graph is intentionally not simulated.

### Acceptance Criteria (P3)
| Criterion | Result |
|---|---|
| simulation runs on P2 Circuit artifact | ✅ fixture and real technical circuit |
| generic stimulus can trigger firing | ✅ |
| firing propagates through structural edges | ✅ chain, fixture (hop k → step k+1), real circuit |
| leak works | ✅ geometric decay tests |
| refractory works | ✅ |
| reset works | ✅ state equals a fresh engine |
| deterministic replay works | ✅ incl. seeded noise and snapshot resume |
| weight transformation is explicit | ✅ configurable, tested, documented |
| no E/I sign is invented | ✅ single `unsigned_excitatory_only` mode; NT metadata inert |
| numerical safeguards work | ✅ validation, clamp, NaN/Inf abort, run limits |
| snapshots serialize | ✅ JSON round trip, circuit hash reference, resume |
| tests pass | ✅ 205 |
| technical MaleCNS smoke passes | ✅ |

### G. Known limitations
- Unsigned excitatory-only dynamics: with no inhibition, dense subgraphs either reverberate or stay silent depending on `weight_scale`; the transient regime is narrow (≈ 0.2 on the technical circuit). Signed dynamics need a justified sign source first.
- Global parameters only (per-neuron arrays exist but are initialised from the global config); no synaptic delays other than one step; no conductance-based synapses; no adaptation.
- `settled_to_rest` in the report only checks potentials at the final step and can read "true" during a reset-dominated oscillation; use `activity_stopped_in_last_10_steps` for activity.
- Snapshots do not store the spike history, only the current state, stimuli and RNG state (activity logs are in the run report).
- The engine runs in-process; no API/WebSocket streaming yet (P5).
- Model units are dimensionless; nothing maps to mV or ms.

### Next phase suggestions (P4 — do not start without confirmation)
1. Research gate first: `docs/circuits/escape_v1.md` with defensible visual/looming input and descending output populations from authoritative MaleCNS annotations/literature; stop and document if the mapping cannot be verified (NEUROSCIENCE.md §5).
2. Only then: `LoomingStimulus` → generic `stimulate()` mapping, selected circuit config, `MotorDecoder` (activity → IDLE/FORWARD/LEFT/RIGHT/ESCAPE_LEFT/ESCAPE_RIGHT), action enum, end-to-end experiment runner recording dataset/version, circuit hash, config, seed, stimulus, output (NEUROSCIENCE.md §6).
3. If the biological mapping is uncertain, build the pipeline on the synthetic fixture and label it as such.

---

## P4 Report (2026-09-16) — Looming / Escape Behavior

### A. Research findings (`docs/circuits/escape_v1.md`)
- Looming-responsive visual projection types documented in the literature: LPLC2 (Klapoetke 2017), LC4 (von Reyn 2017, Ache 2019), LC6/LC16/LPLC1 (Wu 2016). All exist in MaleCNS v1.0 as `visual_projection` types: LC4 126, LPLC2 185, LC6 124, LPLC1 134, LC16 182.
- Escape descending neurons: DNp01 = giant fiber (Namiki 2018; Ache 2019), azimuth-invariant, drives takeoff (Jang 2023); DNp02/DNp04/DNp11 receive LC4 gradients and set forward/backward takeoff (Dombrovski 2023). All present as pairs in MaleCNS with sides.
- Structural verification in the canonical graph: LC4 → DNp01 6,362 synapses over all 126 LC4 (per pair min 21, median 51); LPLC2 → DNp01 4,862 over all 185 LPLC2 (median 27); every edge ipsilateral; LC4 and LPLC2 are the two largest input types of both GFs. LC4 → DNp02/DNp04/DNp11 also direct (reference only).
- Negative results: LC6 → GF none; LC16 → GF none; LPLC1 → GF 1 synapse; 2-hop expansion aborts at every threshold.
- Environment limitation: every journal site is egress-blocked; citations are metadata-verified (title, venue, year, authors, DOI/URL, indexed summary).

### B. Biological circuit status
**PARTIALLY SUPPORTED** — sensory mapping SUPPORTED, output mapping SUPPORTED, identifiers SUPPORTED, structural path SUPPORTED, citations PARTIALLY (metadata only), directional decoding UNSUPPORTED (excluded), signed dynamics UNSUPPORTED (excluded). Results are described as "an action decoded from simulated activity on a biologically grounded structural circuit"; no behaviour is claimed as reproduced.

### C. Sensory neurons
LC4 + LPLC2, 311 neurons (L 165 / R 146), grouped by `mcns_somaSide`; 284 are in the circuit and receive stimulus current (126 LC4 + 158 LPLC2); 27 LPLC2 with < 10 synapses onto a GF are excluded and listed in the config with the reason.

### D. Output neurons
DNp01 (giant fiber): `10010` (L, `DNp01(GF)_L`) and `10001` (R, `DNp01(GF)_R`).

### E. Structural paths
Monosynaptic, ipsilateral: L sensory → GF L only; R sensory → GF R only (verified with P2). Hop-1 path-restricted extraction at min_synapses 10 keeps all 311 → 284 seeds; both targets reachable with `minimum_path_length = 1`.

### F. Extracted circuit
`data/circuits/escape_v1.json` (+ `.parquet`): 286 neurons / 932 edges (LC4→DNp01 126, LPLC2→DNp01 158, LC4→LC4 204, LPLC2→LPLC2 435, LPLC2→LC4 9); hash `db7c46e6a165354d7aed499525e303131bd8d6367e492b2e4fc31117cdc2c78d`, recorded as `expected_circuit_hash` in `backend/app/behavior/configs/escape_v1.json` and verified by tests and by the runner.

### G. Simulation result (P3 defaults, unchanged; 30 steps; stimulus 5 steps)
| direction | intensity | sensory first spike | GF spikes R/L | first GF spike | action |
|---|---|---|---|---|---|
| left | 0.2 | – | 0/0 | – | NO_ACTION |
| left | 0.5 | step 3 (155) | 0/1 | 4 | ESCAPE |
| left | 1.0 | step 1 (155) | 0/2 | 2 | ESCAPE |
| center | 0.2 | – | 0/0 | – | NO_ACTION |
| center | 0.5 | step 3 (284) | 1/1 | 4 | ESCAPE |
| center | 1.0 | step 1 (284) | 2/2 | 2 | ESCAPE |
| right | 0.2 | – | 0/0 | – | NO_ACTION |
| right | 0.5 | step 3 (129) | 1/0 | 4 | ESCAPE |
| right | 1.0 | step 1 (129) | 2/0 | 2 | ESCAPE |
Activity stops when the stimulus ends (no reverberation in this circuit). Each run ≈ 1.5 ms. Timeline events t0–t4 recorded per run (t2 = "no intermediate neuron fired (monosynaptic)"). Report: `data/simulations/escape_v1_demo.report.json`.

### H. Decoded action
`ESCAPE` for intensity ≥ 0.5 in every direction, `NO_ACTION` for 0.2; the firing GF side follows the stimulated side and is reported as metadata only.

### I. Tests
`pytest`: **234 passed** (205 + 29 new: sensors 5, motor 4, escape config 5, runner 10, biological 5). Synthetic: stimulus validation, mapper, direction handling, intensity bounds, simulation integration (fixture circuit), motor threshold, NO_ACTION, determinism, event timeline, provenance references, config-mismatch rejection. Biological: every configured MaleCNS id exists (skips without data), every artifact edge from `male-cns v1.0` with ≥ 10 synapses, artifact hash = configured hash, citations present, no synthetic ids, roles match cell types, configured population = all canonical LC4/LPLC2. `ruff check` clean; frontend typecheck unchanged.

### J. Limitations
- Citations verified by metadata only; a human should spot-check the cited passages.
- Monosynaptic LC4/LPLC2 → GF only: no contralateral pathway, no inhibitory size-encoding inputs, no LC6/LC16/LPLC1 routes, no DNp02/DNp04/DNp11 forward/backward decoding (candidate `escape_v2`).
- Unsigned excitatory-only dynamics with computational defaults; intensity→latency behaviour is a model property.
- Left/right selects the ipsilateral sensory group only; no directional action is decoded.
- The stimulus is a normalized application input; no visual-scene geometry (angular size/velocity) is modelled.
- No API/UI yet (P5/P6).

### Next phase suggestions (P5 — do not start without confirmation)
1. FastAPI endpoints per SDD §7 (`/circuits`, `/simulation/*`, `/neurons/{id}`) wrapping the P2–P4 modules, with `escape_v1` as the default circuit and the disclaimer in every payload.
2. WebSocket streaming of per-step SIMULATED activity from `SimulationEngine.step()`.
3. Three-column UI (Environment / Circuit / Action): Danger button → `LoomingStimulus` → timeline → decoded action, with NEUROSCIENCE.md §3 wording.

---

## P5 Report (2026-09-16) — Interactive Web Demo

### A. UI architecture (`frontend/src`)
- **Header**: title `FlyBrain Agent`, subtitle `Connectome-grounded simulation using MaleCNS v1.0`, the three scientific labels (`Structural connectivity: biological data` / `Neural activity: simulated` / `Behavior decoding: computational interpretation`), compact backend badge (`components/BackendBadge.tsx`, `GET /health`, Re-check).
- **Three columns** (`.grid`, desktop ≥ 1280 px; 2 columns on tablet with Action spanning; 1 column on phones):
  - `environment/EnvironmentPanel.tsx` — SVG arena with the virtual fly, the looming disc (origin follows LEFT/CENTER/RIGHT, radius grows with the replayed stimulus steps and intensity, pulses while current is injected, dims when the stimulus ends), direction segmented control, intensity slider + numeric field (0–1, validated client-side), **TRIGGER LOOMING** / **RESET**. Fly takes off on ESCAPE (labelled "takeoff animation · direction not decoded"). No webcam.
  - `brain/BrainPanel.tsx` — schematic node/cluster view built from `GET /escape/config`: groups `LC4 L/R`, `LPLC2 L/R`, `DNp01 (GF) L/R` with neuron counts, edges aggregated from the circuit artifact (width ∝ synapses; within-group edges listed, not drawn), badge **SIMULATED ACTIVITY**, step indicator, glow = fraction of the group with a simulated spike at the replayed step, edges animate while their source group fires.
  - `dashboard/ActionPanel.tsx` — large **NO ACTION** / **ESCAPE** (idle `—`, `RUNNING…`, `DECODING…`, `NO RESULT` on error), metadata (GF activity Left/Right/Both/None, GF spikes, first GF / sensory step, stimulated neurons, transport + streamed events, experiment id, circuit hash, runtime), timeline t0–t4 highlighted as the replay reaches each backend step, error box with code + message.
- **How this works** (`dashboard/HowItWorks.tsx`, `<details>`): the three layers from the backend, **BIOLOGICAL CIRCUIT STATUS: PARTIALLY SUPPORTED**, dataset / circuit / hash verification, populations, mapping & decoder rules, simulation parameters (with the "NOT MEASURED" label), limitations, 7 citations, research document path.
- **Footer**: the P4 disclaimer verbatim + required wording ("Neural activity shown here is simulated", "Structural connectivity from a biological dataset").
- **State** (`demo/useEscapeDemo.ts`): reducer `idle → requesting → replaying → finished | error`; config fetched on mount; WebSocket first (`api/escapeSocket.ts`), REST fallback (`api/client.ts`) only when the socket cannot be opened; 15 s client timeout; RESET aborts in-flight runs. `?pace=<ms>` (default 140) sets the replay speed, `?transport=rest` forces REST. Dark scientific theme in `styles.css` (glow/pulse keyframes, reduced-motion fallback).

### B. API (`backend/app/api/escape.py`)
| Endpoint | Notes |
|---|---|
| `GET /escape/config` | config version, `circuit_id` / `circuit_hash` (+ `expected_circuit_hash`, `circuit_verified`), `biological_status`, dataset/version/selection rule, 286 neurons / 932 edges, sensory population 311 (L 165 / R 146) vs stimulated 284 vs excluded 27 + reason, output groups, `groups` (6) and `group_edges` (10, from the artifact), actions `["NO_ACTION","ESCAPE"]`, mapping/decoder rules, simulation parameters, `layers`, limitations, citations, disclaimer, scientific labels |
| `POST /escape/run` | body `{"stimulus":"looming","direction":"center","intensity":0.5}` (+ optional `steps`, bounded); returns `experiment_id`, `created_at`, `stimulus`, `circuit_id`, `circuit_hash`, `circuit`, `timeline` (t0–t4), `sensory_activity`, `group_activity`, `per_step_fired_counts`, `output_activity`, `gf_activity`, `action`, `decision`, `simulation_config`, `random_seed`, `runtime_seconds`, `disclaimer` |
| `WS /ws/escape` | same body (+ `pace_ms` 0–2000); events `stimulus_started`, `neural_activity` (per step: `fired_total`, `fired_by_group`, `stimulus_active`), `sensory_activation`, `output_activation`, `action_decoded`, `experiment_finished` (full result); `error` events; connection stays open for further runs |
Errors: `detail = {error, message}` with `invalid_request` 422, `config_unavailable` / `circuit_unavailable` / `circuit_mismatch` 503, `simulation_error` 500, `timeout` 504. `EscapeServiceHolder` loads config + hash-verified circuit at startup (`lifespan`), re-attempts after failure; `/health` is unaffected. New settings `FLYBRAIN_ESCAPE_CONFIG`, `FLYBRAIN_ESCAPE_MAX_STEPS` (500), `FLYBRAIN_ESCAPE_RUN_TIMEOUT_SECONDS` (10). Runner extension (P4 module): `ActivityGroup`, `GroupEdge`, `GroupActivity`, `EscapeResult.group_activity`. `CURRENT_PHASE = "P5"`.

### C. Simulation → animation mapping
| Backend fact (SIMULATED unless noted) | UI element |
|---|---|
| `stimulus_duration_steps` = 5, replayed step *s* | looming disc radius `6 + progress × (16 + 44 × intensity)` with `progress = min(s, 5) / 5`; pulses while `s ≤ 5`, dims after; origin x from direction (structure of the request, not biology) |
| `group_activity.fired_counts[group][s-1] / neuron_count` | node glow opacity & colour mix; label `fired / count`; `data-active` |
| `fired_counts[pre_group][s-1] > 0` | edge `pre → post` animates (dash flow) |
| `timeline.t1.step`, `t3.step` | timeline items highlighted once `s ≥ step`; WebSocket `sensory_activation` / `output_activation` follow the `neural_activity` of that step |
| `per_step_fired_counts[s-1]` | "N simulated spikes this step" |
| `action` (after the last step) | large NO ACTION / ESCAPE; fly takeoff on ESCAPE |
| `decision.fired_output_sides` → `gf_activity` | "GF activity: Left / Right / Both / None" (metadata) |
Observed timelines: CENTER 0.5 → sensory step 3 (284 neurons), GF step 4 (both) → ESCAPE; CENTER 0.2 → no spikes → NO_ACTION; LEFT 1.0 → sensory step 1 (155), GF L step 2 → ESCAPE, GF activity Left. Runs take ~2 ms server-side; 35 WebSocket events for a 30-step run.

### D. Tests
- Backend `pytest`: **274 passed** (234 + 40 new in `tests/test_api_escape.py`): config endpoint (fields, verified hash, groups vs configured populations, ipsilateral group edges summing to 932 edges / artifact synapses, three layers), run endpoint (CENTER 0.5 ESCAPE/Both, CENTER 0.2 NO_ACTION/None, side metadata L/R/Both, required fields, only NO_ACTION/ESCAPE, exact disclaimer, hash = config = artifact, group activity consistent with per-step counts, determinism, `steps` override), validation (10 invalid bodies → 422, non-JSON, steps above limit), error states (missing circuit 503 + `/health` up, tampered hash 503 `circuit_mismatch`, missing config 503, simulation exception 500, slow run 504), WebSocket (event order/steps/counts equal REST, NO_ACTION stream, invalid input keeps the connection, unavailable circuit error event, events derived from the result), OpenAPI. `ruff check` / `ruff format --check` clean (backend + scripts).
- Frontend `npm run typecheck` clean (strict TS). Playwright **27 passed** (`tests/smoke.spec.ts` 4, `tests/escape-demo.spec.ts` 16, `tests/smoke-demo.spec.ts` 7): page loads; backend connected + circuit loaded; change direction; change intensity (slider + field); invalid intensity blocked; trigger looming (WebSocket transport, hash, replay to 30/30); CENTER 0.2 → NO ACTION; CENTER 0.5 → ESCAPE + Both + fly jumps; LEFT 1.0 → ESCAPE + Left, no `ESCAPE_LEFT/RIGHT` anywhere; brain animation follows backend steps (sensory at step 1, GF at step 2, slow pace); reset; backend unavailable (socket closed + REST refused → error, `NO RESULT`, fly stays); error contract (`simulation_error`, `circuit_mismatch`); backend unavailable at load (banner, empty circuit, disclaimer still visible); REST fallback; disclaimer / SIMULATED ACTIVITY / PARTIALLY SUPPORTED visible; smoke scenarios + tablet 1024×768 + mid-replay captures.

### E. Smoke demo (`make smoke-web` → `scripts/smoke_web_demo.py`; `make smoke` runs everything in 33 s)
| Scenario | REST action | GF activity | sensory / GF first step | WebSocket |
|---|---|---|---|---|
| CENTER 0.2 | NO_ACTION | None | – / – | 33 events, same action |
| CENTER 0.5 | ESCAPE | Both | 3 / 4 | 35 events, same action |
| LEFT 1.0 | ESCAPE | Left | 1 / 2 | 35 events, same action |
Invalid intensity 1.5 → HTTP 422. Report: `data/simulations/web_demo_smoke.report.json`. `make smoke` = backend health, data, circuit, simulation, escape, web, Playwright — all PASS.

### F. Screenshots (`docs/screenshots/`, 1440×900 unless noted)
`p5-idle-dashboard.png`, `p5-center-0.2-no-action.png`, `p5-center-0.5-escape.png`, `p5-left-1.0-escape.png`, `p5-replay-step1-sensory.png` (sensory groups glowing at backend step 1), `p5-replay-step2-giant-fiber.png` (both GF nodes glowing at step 2), `p5-how-it-works.png` (BIOLOGICAL CIRCUIT STATUS: PARTIALLY SUPPORTED), `p5-tablet-1024x768.png`. Regenerated by `tests/smoke-demo.spec.ts` on every Playwright run.

### Acceptance Criteria (P5)
| Criterion | Status |
|---|---|
| User can trigger looming and see stimulus → neural activity → action without a terminal | ✅ TRIGGER LOOMING → arena / brain / action panels |
| Brain animation reflects backend simulation events | ✅ replay of `group_activity` per backend step; WebSocket events streamed; test "brain animation follows the backend steps" |
| Backend reuses P4 pipeline without duplicating logic | ✅ `EscapeService` calls `EscapeExperiment.run`; API only reshapes |
| Circuit hash visible/verifiable | ✅ config + run payloads + UI metadata; hash-mismatch → 503 |
| Disclaimer visible | ✅ footer (exact P4 text), config/run payloads |
| Scientific labels visible | ✅ header chips + SIMULATED ACTIVITY badge + APPLICATION INPUT / DECODING tags |
| Only NO ACTION / ESCAPE shown; GF side as metadata | ✅ |
| Error states | ✅ backend unavailable, simulation error, invalid intensity, circuit mismatch, timeout (client 15 s / server 10 s) — no ESCAPE on failure |
| Backend + Playwright tests, smoke demo | ✅ 274 / 27 / PASS |
| Documentation updated | ✅ `docs/DEVELOPMENT.md` §2, §4, §4f; README; SDD §7 note; PROGRESS |

### G. Known limitations
- The circuit is monosynaptic, so the t2 intermediate event is always "no intermediate neuron fired" and the brain view has only two rows; per-neuron inspection (positions, ids, synapse counts per edge) is P6.
- Nodes are `cell_type × side` groups, not individual neurons; the schematic layout (L/R columns, sensory above output) is a presentation choice, not anatomy.
- The looming disc's size/position and the fly's takeoff are schematic visual mappings of dimensionless backend steps (`dt = 1`), not physical geometry or kinematics.
- Replay pacing (`?pace=`, default 140 ms per step) is a presentation parameter; the backend timeline is what is replayed, but the wall-clock speed is the UI's.
- WebSocket needs a proxy that forwards upgrades (Vite dev server does; a production reverse proxy must too); otherwise the UI falls back to REST and shows `transport: rest`.
- A server-side timeout (504) does not cancel the worker thread already running (runs take ~2 ms, so this is theoretical).
- No authentication, rate limiting or multi-user isolation; one process-wide experiment object (each run builds a fresh engine, so runs are independent).
- Playwright's `routeWebSocket` must be installed before navigation; the screenshot spec rewrites `docs/screenshots/*.png` on every run (≈3 MB tracked binaries).
- UI copy is English only; `frontend` still has no lint/format toolchain (typecheck only).

### Next phase suggestions (P6 — do not start without confirmation)
1. Brain inspector: `GET /circuits/{id}`, `GET /neurons/{id}` (P2 artifact metadata, MaleCNS ids, cell types, synapse counts, provenance) and a per-neuron view of the escape circuit.
2. Activity inspector: per-neuron spike raster from `spikes_per_step` and `SimulationSnapshot` download, all labelled SIMULATED.
3. Provenance panel linking each displayed number to `provenance.json` / `docs/circuits/escape_v1.md`.
