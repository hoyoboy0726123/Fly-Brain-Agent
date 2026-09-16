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

One command (validates first, starts both servers, prints the URLs, Ctrl+C stops both):

```bash
make demo                        # = backend/.venv/bin/python scripts/run_demo.py
python scripts/run_demo.py       # any interpreter with the backend installed (macOS / Linux / Windows)
make demo-check                  # validation only: config, committed artifact + hash, node_modules, npm
make demo-smoke                  # start, verify /health, the Vite page and the /api proxy, stop
```

Startup validation never falls back to synthetic data: a missing or tampered `escape_v1`
artifact, a hash that differs from `expected_circuit_hash`, missing backend or frontend
dependencies each stop the launcher with a message naming the fix (`git checkout -- …`,
`make build-escape-config`, `make install-frontend`, …).

Two terminals, if you prefer:

```bash
make backend    # FastAPI on http://127.0.0.1:8000  (docs at /docs, health at /health)
make frontend   # Vite on   http://127.0.0.1:5173
```

Equivalent raw commands:

```bash
cd backend && .venv/bin/python -m app          # honours FLYBRAIN_* env vars, reloads in development
cd frontend && npm run dev
```

Open http://127.0.0.1:5173. The page is the P5 interactive demo (see §4f): header with the
backend badge, three panels (Environment / Fly Brain / Action) and the "How this works"
section. In development the UI calls `/api/*`, which Vite proxies to the backend with the
`/api` prefix stripped (`/api/health` -> `/health`); WebSocket upgrades are proxied the same
way (`/api/ws/escape` -> `/ws/escape`).

## 2b. Continuous integration

`.github/workflows/ci.yml` runs on push and pull_request:

| Job | Steps | Data |
|---|---|---|
| backend (Python 3.11, 3.12) | `pip install -e backend[dev]`, `ruff check` + `ruff format --check` (backend + scripts), `pytest`, smoke scripts (health, fixture inspection, fixture circuit / simulation, escape demo, web demo API) | synthetic fixture + committed `escape_v1` artifact |
| frontend (Node 22) | `npm ci`, `npm run typecheck`, `npm run build` | — |
| e2e | backend + frontend install, `npx playwright install --with-deps chromium`, `scripts/run_demo.py --check`, `--smoke`, `npm run test:e2e` (all specs, live backend) | committed `escape_v1` artifact |

Not covered by CI (needs the raw MaleCNS files, local only): `make normalize`, the technical
extraction / simulation smokes on the canonical graph (they print "skipped" in CI),
`make build-escape-config`. CI never downloads the dataset.

## 3. Tests

```bash
make test               # backend pytest + frontend typecheck
make test-backend       # cd backend && .venv/bin/python -m pytest
make typecheck-frontend # cd frontend && npm run typecheck
make lint               # ruff check on backend
```

## 4. Smoke tests

```bash
make smoke              # all of the following (+ data / circuit / simulation / escape smokes)
make smoke-backend      # scripts/smoke_test.py: boots uvicorn on a free port, asserts GET /health
make smoke-web          # scripts/smoke_web_demo.py: escape API over REST + WebSocket (P5)
make smoke-frontend     # cd frontend && npm run test:e2e (Playwright)
```

The Playwright run starts **both** servers itself (backend via `backend/.venv` Python, or
`FLYBRAIN_PYTHON`, else `python3`; frontend via `npm run dev`) and runs three spec files:
`tests/smoke.spec.ts` (backend health card, unreachable/recovery states),
`tests/escape-demo.spec.ts` (the P5 demo: controls, live runs, error states, disclaimer) and
`tests/smoke-demo.spec.ts` (the three documented scenarios), `tests/inspector.spec.ts` (P6 brain
inspector), `tests/landing.spec.ts` (P6.1 landing, story, presets), `tests/smoke-inspector.spec.ts`
(MVP screenshots A–E) and `tests/release-screenshots.spec.ts` (release screenshots). Screenshot
specs write to `frontend/test-results/screenshots/` (git-ignored); `make screenshots` sets
`FLYBRAIN_SCREENSHOT_DIR=../docs/screenshots` to refresh the curated set. Happy paths always hit
the live backend; only error states are mocked.

Run Playwright from `frontend/` via `npm run test:e2e` (or `make smoke-frontend` from the
root). Invoked from another directory, `playwright test` does not find
`frontend/playwright.config.ts`, falls back to defaults, and may load the spec files with a
different Playwright copy (error: "did not expect test.describe() to be called here").

## 4b. Connectome data (P1)

Nothing in the test suite needs a download. To work with the real dataset:

1. Read `docs/dataset_research.md` (what the files are, how they were verified, license CC-BY).
2. Download the MaleCNS v1.0 flat-connectome files (≈1.1 GB weights + 14 MB annotations +
   43 MB neurotransmitters) into
   `data/raw/male-cns/v1.0/connectome-data/flat-connectome/` (commands in the research doc §8).
3. `make normalize` → `data/processed/neurons.parquet`, `connections.parquet`,
   `provenance.json`, `inspection_report.{json,md}`. Raw files are never modified; their
   sha256/md5 are recorded and compared with the bucket listing (mismatch aborts).
4. `make inspect` prints the DATA.md §7 report.

Options (see `scripts/normalize_dataset.py --help`): `--status Traced Assign`,
`--all-statuses`, `--keep-dangling`, `--weights-file <name>`, `--no-neurotransmitters`,
`--no-hash`, `--out-dir`. The synthetic fixture path is `make normalize-fixture` /
`scripts/inspect_dataset.py --fixture`.

Parquet outputs are git-ignored; `provenance.json` and the inspection report are committed.

`provenance.json` and the inspection report always distinguish the **source dataset**
(MaleCNS v1.0, ≈166,700 neurons) from the **canonical simulation graph** (`status == "Traced"`,
165,122 neurons / 25,563,197 connections). See `DATA.md` §8; tests in
`backend/tests/test_canonical_graph.py` guard the distinction.

## 4c. Circuit extraction (P2)

The canonical graph (`neurons.parquet` + `connections.parquet`) is loaded into a compact
CSR adjacency (out-edges by presynaptic neuron, in-edges by postsynaptic neuron, numpy
int32) — about 400 MB for 25.5 M edges, no NetworkX. The first load builds a memory-mappable
`.npy` cache in `data/processed/graph_cache/` (git-ignored); later loads take well under a
second.

```bash
make extract ARGS="--circuit-id demo --seeds 10001 --targets 12345 --max-hops 2 \
                   --min-synapses 10 --max-neurons 2000 --direction downstream"
make smoke-circuit          # fixture extraction with a known result (+ technical MaleCNS run when data present)
scripts/extract_circuit.py --fixture --circuit-id fx --seeds syn_001 --max-hops 2 --min-synapses 1 --max-neurons 50
```

Semantics: multi-source BFS from the seeds following out-edges (`downstream`) or in-edges
(`upstream`) whose `synapse_count >= min_synapses`, at most `max_hops` levels. `max_neurons`
is a **hard limit**: the run aborts before adding a hop level that would exceed it. Missing
seed or target ids fail loudly. The artifact is the subgraph induced by the discovered
neurons (every canonical edge between them above the threshold), written to
`data/circuits/<circuit_id>.json` (full artifact) and `.parquet` (edges with the five
provenance columns). Every node carries `minimum_hop_from_seed`; every target reports
`reachable` and `minimum_path_length` (never fabricated). `--restrict-to-target-paths`
optionally keeps only neurons on a seed→target path of length ≤ max_hops.

Artifacts produced by `smoke_circuit.py` on MaleCNS are labelled
"TECHNICAL EXTRACTION SMOKE TEST — NOT A BIOLOGICALLY INTERPRETED CIRCUIT".

## 4d. Simulation (P3)

`backend/app/simulation/` runs a simplified LIF-like model on a P2 circuit artifact. All
outputs are SIMULATED; parameters are computational, not measured (see NEUROSCIENCE.md §8).

```bash
make simulate ARGS="--fixture --stimulate syn_001 --intensity 2.0 --duration 3 --steps 30"
make simulate ARGS="--circuit data/circuits/<id>.json --stimulate <neuron_id> --intensity 2.0 --duration 5 --steps 50 --simulation-id demo"
make smoke-simulation      # fixture propagation demo (+ technical MaleCNS simulation when the P2 circuit exists)
```

Outputs go to `data/simulations/`: `<id>.report.json` (run summary + spike raster, tracked)
and `<id>.snapshot.json` (full state, git-ignored). `--config-json '{"threshold": 1.5}'`
overrides `SimulationConfig` fields.

## 4e. Escape behaviour pipeline (P4)

APPLICATION DECODING layer: `backend/app/sensors/` (LoomingStimulus, StimulusMapper),
`backend/app/motor/` (MotorDecoder: `NO_ACTION` / `ESCAPE`), `backend/app/behavior/`
(versioned config `configs/escape_v1.json` + `EscapeExperiment` runner). The biological
mapping (LC4 + LPLC2 → DNp01/GF) and its evidence live in `docs/circuits/escape_v1.md`.

```bash
make build-escape-config   # regenerate escape_v1.json + data/circuits/escape_v1.{json,parquet} from the canonical graph
make smoke-escape          # TECHNICAL CONNECTOME-GROUNDED ESCAPE DEMO -> data/simulations/escape_v1_demo.report.json
```

Disclaimer carried by every result: STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL
ACTIVITY IS SIMULATED. STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS.

## 4f. Interactive web demo (P5)

Backend (`backend/app/api/escape.py`, thin layer over the P4 `EscapeExperiment`; no
simulation logic of its own):

| Endpoint | Purpose |
|---|---|
| `GET /escape/config` | circuit id/hash (verified against the configured hash), biological status, groups (`LC4_L`, …, `DNp01_R`) and aggregated group edges from the artifact, mapping/decoder rules, simulation parameters, layers, limitations, citations, disclaimer |
| `POST /escape/run` | body `{"stimulus":"looming","direction":"left|center|right","intensity":0..1,"steps"?:n}`; returns `experiment_id`, `stimulus`, `circuit_id`, `circuit_hash`, `timeline`, `sensory_activity`, `group_activity` (per-step SIMULATED spike counts per group), `output_activity`, `gf_activity` (Left/Right/Both/None, metadata), `action` (`NO_ACTION`/`ESCAPE`), `decision`, `disclaimer` |
| `WS /ws/escape` | send the same body (optionally `pace_ms`); receive `stimulus_started` → `neural_activity` (per step) → `sensory_activation` → `output_activation` → `action_decoded` → `experiment_finished` (full result); `error` events carry the same codes as HTTP |

Error contract (`detail: {error, message}`): `invalid_request` 422, `config_unavailable` /
`circuit_unavailable` / `circuit_mismatch` 503, `simulation_error` 500, `timeout` 504.
Settings: `FLYBRAIN_ESCAPE_CONFIG` (name or path), `FLYBRAIN_ESCAPE_MAX_STEPS`,
`FLYBRAIN_ESCAPE_RUN_TIMEOUT_SECONDS`.

Frontend (`frontend/src`): `demo/useEscapeDemo.ts` (state machine: idle → requesting →
replaying → finished | error; WebSocket first, REST fallback only when the socket cannot be
opened), `environment/EnvironmentPanel.tsx` (virtual fly, looming disc, direction, intensity,
TRIGGER LOOMING / RESET), `brain/BrainPanel.tsx` (group nodes + artifact edges, glow = fraction
of the group firing at the replayed step, "SIMULATED ACTIVITY"), `dashboard/ActionPanel.tsx`
(NO ACTION / ESCAPE, GF activity metadata, timeline, error states),
`dashboard/HowItWorks.tsx` (three layers, BIOLOGICAL CIRCUIT STATUS). The replay advances one
backend step per tick (`?pace=<ms>`, default 140 ms; `?transport=rest` forces REST). Nothing is
animated from a client-side clock alone: every glow, disc size and label comes from the
backend result's per-step data.

## 4g. Brain inspector (P6)

Read-only API over the P2 artifact (`backend/app/api/circuits.py`; every field is read from
`data/circuits/<circuit_id>.json`, hash-verified; nothing is reconstructed):

| Endpoint | Purpose |
|---|---|
| `GET /circuits` | loadable artifacts (id, dataset, hash, sizes, biological status when an escape config uses it) |
| `GET /circuits/{id}` | summary: canonical graph reference, extractor config, targets, sizes, cell-type counts |
| `GET /circuits/{id}/provenance` | dataset, license, source/download URLs, raw file digests, source vs canonical counts, loaded circuit, hash verification, citations |
| `GET /circuits/{id}/nodes?offset&limit&cell_type&search&id_prefix` | neurons (`search` = exact id) with degrees within the circuit and side/role from the escape config |
| `GET /circuits/{id}/edges?offset&limit&pre&post&min_synapses&include_simulation_weight` | structural edges (`Structural connection — biological data`); the optional simulation weight is labelled computational |
| `GET /circuits/{id}/edges/{pre}/{post}` | one edge: `BIOLOGICAL STRUCTURAL CONNECTION` + circuit id/hash + computational weight |
| `GET /circuits/{id}/neurons/{neuron_id}` | `biological` vs `circuit` metadata blocks + connectivity summary (404 `neuron_not_found`) |
| `GET /circuits/{id}/neurons/{neuron_id}/neighbors?direction&offset&limit` | upstream / downstream partners *within the loaded circuit* |

`POST /escape/run` now also returns `neuron_activity` (per-neuron, per-step SIMULATED membrane
potential / fired / refractory) which the inspector replays.

Frontend (`frontend/src/inspector/`): `useCircuitData.ts` (loads nodes + edges + provenance once
and builds indexes + a deterministic d3-force layout in `layout.ts`), `CircuitGraph.tsx`
(SVG + d3-zoom; identity colour = cell type, activity = ring/glow channel), `SearchBar.tsx`,
`NeuronInspector.tsx`, `EdgeInspector.tsx`, `ProvenancePanel.tsx`, `ReplayControls.tsx`
(`useReplay.ts`). Open it with the *Brain Inspector* tab or `http://127.0.0.1:5173/#inspector`.

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
| `FLYBRAIN_MALECNS_RAW_SUBDIR` | `male-cns/v1.0/connectome-data/flat-connectome` | MaleCNS files under `raw/` (mirrors the bucket prefix) |

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
backend/app/connectome   BIOLOGICAL STRUCTURE  (P1): schema, normalize, adapter, malecns, fixture, provenance, inspect
backend/app/circuits     BIOLOGICAL STRUCTURE  (P2): graph (CSR), extractor, artifact, errors
backend/app/simulation   COMPUTATIONAL DYNAMICS (P3): config, weights, engine, state, errors
backend/app/sensors      APPLICATION DECODING  (P4): LoomingStimulus, StimulusMapper, sensor adapter
backend/app/motor        APPLICATION DECODING  (P4): MotorDecoder, Action
backend/app/behavior     APPLICATION DECODING  (P4): escape_v1 config + EscapeExperiment runner
backend/tests            pytest suite (+ fixtures/tiny_connectome.json, SYNTHETIC)
frontend/src/api         typed API client + hooks
frontend/src/components  UI components
frontend/src/{environment,brain,dashboard}  reserved for P5/P6
frontend/tests           Playwright smoke tests
data/{raw,processed,circuits}  gitkept; raw data is never committed
scripts/smoke_test.py    backend smoke test
scripts/normalize_dataset.py  raw -> normalized parquet + provenance.json
scripts/inspect_dataset.py    DATA.md §7 validation report
scripts/extract_circuit.py    bounded circuit extraction -> data/circuits/<id>.{json,parquet}
scripts/smoke_circuit.py      P2 smoke (fixture + technical MaleCNS extraction)
scripts/run_simulation.py     run the LIF-like model on a circuit artifact
scripts/smoke_simulation.py   P3 smoke (fixture propagation + technical MaleCNS simulation)
scripts/build_escape_config.py escape_v1 config + circuit artifact builder (Phase B)
scripts/smoke_escape.py       TECHNICAL CONNECTOME-GROUNDED ESCAPE DEMO (Phase G)
docs/circuits/escape_v1.md    P4 research gate and circuit definition
docs/dataset_research.md      dataset verification record (P1 gate)
```

## 7. Data policy reminder

`data/raw/` is git-ignored and must stay that way (see `DATA.md`). Tests never download data.
The normalization never invents biological fields: unknown optional columns are null, and
every dataset-specific column is carried through verbatim under the `mcns_` prefix.
