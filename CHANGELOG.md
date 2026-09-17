# Changelog

All notable changes to FlyBrain Agent are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow semantic versioning.

## [Unreleased]

P7 is delivered in three parts: **P7.0** (embodiment architecture), **P7.1** (the visual
Virtual Threat Lab) and **P7.2** (the computational Neural Intervention Lab), all below.

### Added
- **Neural Intervention Lab (P7.2)** — computational firing suppression at the simulation
  layer: `app/simulation/intervention.py` (`InterventionConfig`: `NONE` | `SUPPRESS_FIRING`,
  layer COMPUTATIONAL DYNAMICS; future mechanisms documented, not implemented),
  `SimulationEngine(…, intervention=)` / `run(…, intervention=)` — a targeted neuron keeps its
  biological id, edges and synapse counts, still integrates input, but never emits a spike
  (no reset, no refractory period, no propagation); `NONE` is byte-for-byte the previous
  behaviour. `app/behavior/intervention.py` resolves `CONTROL` / `SILENCE_LC4` /
  `SILENCE_LPLC2` / `SILENCE_LC4_LPLC2` from the circuit artifact's cell-type annotations
  (fails loudly, no invented ids), records `ResolvedTargets`, exposes `structural_signature`
  and the Ache et al. 2019 literature context. `EscapeExperiment.run(…, intervention=)`,
  `EmbodiedAgentLoop(…, intervention=)` and `ThreatLabService.run(…, intervention=)` only pass
  it through; provenance gains `intervention` / `intervention_layer`, results gain
  `suppressed_events`. `GET /embodiment/intervention/config` and
  `POST /embodiment/intervention/compare` (`app/api/intervention.py`): CONTROL and one
  intervention under **verified** matched conditions (seed, world, initial body, sensor / body
  / motor / simulation configs, circuit hash, dataset version, timing, loop, decoder), structural
  integrity before / after, descriptive differences (first ESCAPE steps, per-cell-type simulated
  spikes, displacement, first divergent step, plain-language summary — no biological
  interpretation, no expected outcome). New frontend tab **Neural Intervention Lab**
  (`frontend/src/intervention/`): selector, RUN CONTROL + INTERVENTION, two trial panels with
  one shared cursor (TRIAL ENDED past a timeline), SUPPRESSED groups crossed out but
  structurally present, comparison panel, BIOLOGICAL EVIDENCE vs CURRENT COMPUTATIONAL RESULT,
  both disclaimers; the Brain Inspector shows the intervention state of a selected neuron.
  `scripts/smoke_intervention.py` / `make smoke-intervention` (CI), `tests/test_intervention.py`
  (18), `tests/test_api_intervention.py` (27), `frontend/tests/intervention-lab.spec.ts`,
  `frontend/tests/smoke-intervention.spec.ts` (screenshots `docs/screenshots/intervention-A…C.png`),
  `docs/EMBODIMENT.md` §11. `CURRENT_PHASE = "P7.2"`. No scientific logic of P0–P7.1 changed.
- **Virtual Threat Lab (P7.1)** — `GET /embodiment/config` and `POST /embodiment/run`
  (`backend/app/api/embodiment.py`): one deterministic P7.0 closed-loop experiment per request
  (safe parameters only: seed, `max_steps ≤ 200`, world start distance / approach speed /
  azimuth; no neural parameter), returning a replayable timeline (world, body, sensor,
  simulated brain group activity, decoded action, motor command per loop step), outcome events
  (`first_escape`, `escape`, `landed`), provenance and the disclaimer; failures return no
  partial timeline. New frontend tab **Virtual Threat Lab** (`frontend/src/threatlab/`): SVG
  top-down arena (object = `WorldState`, fly = `BodyState`, fly's-eye angular-size inset),
  DISTANCE / LOOMING INPUT / BODY POSITION / ACTION metrics, WORLD / BODY / SENSOR read-outs,
  brain panel labelled SIMULATED NEURAL ACTIVITY with per-neural-step spike bars, closed-loop
  story WORLD ↓ SENSOR ↓ BRAIN ↓ MOTOR ↓ BODY ↺ WORLD, replay controls (RUN, PLAY, PAUSE,
  RESET, STEP, slider, ⚡ ESCAPE markers), WAITING FOR EXPERIMENT / NO RESULT states,
  scientific boundaries and disclaimer served by the backend. The frontend renders recorded
  states only (tween between steps is presentation only). `scripts/smoke_threat_lab.py` /
  `make smoke-threat-lab` (also in CI), `backend/tests/test_api_embodiment.py`,
  `frontend/tests/threat-lab.spec.ts`, `frontend/tests/smoke-threat-lab.spec.ts`
  (screenshots `docs/screenshots/threatlab-A…E.png`), `docs/EMBODIMENT.md` §10.
  `BrainStepSummary` (P7.0) gained the additive fields `sensory_first_fire_step` and
  `group_fired_counts`. `CURRENT_PHASE = "P7.1"`. No scientific logic of P0–P7.0 changed.
- **Embodiment architecture foundation (P7.0)** — `backend/app/embodiment/`: frozen domain
  models (`WorldState`, `BodyState`, `SensoryObservation`, `MotorCommand`, `SimulationClock`,
  configs, records, provenance), adapter interfaces (`WorldAdapter`, `SensorAdapter`,
  `MotorAdapter`, `BodyAdapter`) and `EmbodiedAgentLoop` (World → Sensor → Brain → Motor →
  Body → World). Deterministic `SimpleWorldAdapter` / `SimpleBodyAdapter` (SIMPLIFIED
  COMPUTATIONAL BODY), `VirtualLoomingSensor` (computational angular-size rule),
  `EscapeMotorAdapter` (NO_ACTION → IDLE, ESCAPE → ESCAPE; no direction decoded).
  `scripts/smoke_embodiment.py` / `make smoke-embodiment`, `docs/EMBODIMENT.md`, 26 tests.
  Additive and backend-only: no new endpoints, P0–P6 behaviour unchanged.

## [0.1.0] — 2026-09-16 — FlyBrain Agent v0.1.0 (MVP)

Release candidate prepared in P6.1. No Git tag or GitHub Release has been created yet
(pending explicit authorization).

Project code license: **Apache License 2.0** (root `LICENSE`, SPDX `Apache-2.0`), selected by
the project owner. The MaleCNS v1.0 source dataset remains under its own **CC-BY 4.0** license;
the two licensing domains are kept separate (README → License, DATA.md §9).

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
  diagrams and scientific boundaries, this changelog, release screenshots; root `LICENSE`
  (Apache-2.0) and license metadata in the backend and frontend packages.

### Known limitations
See `PROGRESS.md` (per-phase "Known limitations") and `README.md` → Scientific Boundaries.
