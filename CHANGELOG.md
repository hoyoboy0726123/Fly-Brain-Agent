# Changelog

All notable changes to FlyBrain Agent are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow semantic versioning.

## [0.1.0] — 2026-09-16 — FlyBrain Agent v0.1.0 (MVP)

Release candidate prepared in P6.1. No Git tag or GitHub Release has been created yet
(pending explicit authorization); the project code license is still to be chosen.

### Added
- **MaleCNS ingestion (P1)** — `DatasetAdapter` for the official MaleCNS v1.0 flat-connectome
  release (`body-annotations`, `connectome-weights`, `body-neurotransmitters` Feather files),
  md5/sha256 verification, normalized `neurons.parquet` / `connections.parquet`,
  `provenance.json` with license (CC-BY 4.0), source and download URLs, and a synthetic
  fixture so nothing needs a download to test.
- **Canonical graph (P1.1)** — explicit *source dataset* (≈166,700 neurons) vs *canonical
  simulation graph* (`status == "Traced"`, 165,122 neurons / 25,563,197 directed connections)
  distinction in provenance, inspection report, parquet metadata and tests.
- **Circuit extraction (P2)** — CSR graph over 25.56 M edges with a memory-mapped cache,
  deterministic bounded BFS extractor (max hops, min synapses, hard neuron limit, target
  reachability, path restriction), hash-sealed circuit artifacts (`data/circuits/<id>.json`).
- **LIF-like simulation (P3)** — simplified discrete-time leaky-integrate-and-fire engine on a
  circuit artifact; parameters labelled COMPUTATIONAL MODEL PARAMETERS — NOT MEASURED MALECNS
  PARAMETERS; weights = `log1p(synapse_count) × scale`, unsigned / excitatory-only; snapshots.
- **escape_v1 (P4)** — research-gated escape circuit: LC4 + LPLC2 → DNp01 (giant fiber),
  286 neurons / 932 edges, BIOLOGICAL CIRCUIT STATUS: PARTIALLY SUPPORTED; `LoomingStimulus`
  (direction, intensity 0–1), stimulus mapper, motor decoder (`NO_ACTION` / `ESCAPE` only),
  runner with a t0–t4 timeline and the disclaimer on every result.
- **Interactive demo (P5)** — FastAPI `GET /escape/config`, `POST /escape/run`,
  `WS /ws/escape`; React dashboard (Environment / Fly Brain / Action) replaying the backend's
  per-step simulated activity; error contract; Playwright tests.
- **Brain inspector (P6)** — read-only `/circuits/*` API over the artifact (nodes, edges,
  neuron, neighbours, provenance; every served edge exists in the artifact), D3 graph with
  zoom / pan / search / hover, neuron and edge inspectors separating BIOLOGICAL METADATA from
  CIRCUIT / SIMULATION METADATA and SIMULATED STATE, upstream / downstream highlight,
  per-neuron activity replay (PLAY / PAUSE / STEP / RESET).
- **Provenance explorer (P6)** — dataset, canonical graph, loaded circuit, circuit hash
  verification, biological status, license, official URLs, raw file digests and citations,
  in the UI and via `GET /circuits/escape_v1/provenance`.
- **Release polish (P6.1)** — GitHub Actions CI (backend / frontend / Playwright, no dataset
  download), one-command `make demo` / `scripts/run_demo.py` with startup validation, landing
  hero with RUN LOOMING DEMO / EXPLORE THE BRAIN, four-step demo story, LOW / MEDIUM / HIGH
  presets ("expected current model result"), presentation-ready README with architecture
  diagrams and scientific boundaries, this changelog, release screenshots.

### Known limitations
See `PROGRESS.md` (per-phase "Known limitations") and `README.md` → Scientific Boundaries.
