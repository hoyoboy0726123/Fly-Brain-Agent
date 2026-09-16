# TASKS — Phase-by-Phase Execution Plan

# P0 — Bootstrap

## Goal
Create runnable backend/frontend skeleton and development tooling.

## Implement
- repository folders
- FastAPI app
- React/Vite/TypeScript app
- GET /health
- pytest setup
- Playwright or minimal frontend smoke setup
- .gitignore for data/raw, caches, node_modules, env
- config module
- developer run instructions

## Smoke Test
Backend `/health` returns success.
Frontend loads and can display backend health.

## Acceptance Criteria
- backend starts
- frontend starts
- tests run
- no raw dataset required

## Agent Prompt
"Read all root project documents. Execute P0 only. Build the smallest runnable skeleton. Run tests and smoke tests, update PROGRESS.md, then stop."

---

# P1 — Dataset Ingestion

## Goal
Establish trustworthy connectome data ingestion.

## First Action
Inspect current official dataset/download documentation and actual files/schema.

## Implement
- DatasetAdapter abstraction
- production adapter based on verified current source
- normalization script
- provenance manifest
- inspect_dataset.py
- tiny synthetic fixture adapter for tests

## Smoke Test
Run inspect script against fixture and, if available locally, production normalized data.

## Acceptance Criteria
- normalized neurons/connections generated
- dangling edges reported
- provenance exists
- no biological fields invented
- tests do not require full download

## Agent Prompt
"Execute P1 only. Before writing the production adapter, verify the current official dataset access/schema. Never guess URLs or columns. Build repeatable raw-to-normalized ingestion plus provenance and tests. Stop after acceptance criteria."

---

# P2 — Graph & Circuit Extractor

## Goal
Extract bounded sensory-to-output subgraphs.

## Implement
- graph builder
- seed/target resolution
- directed traversal
- max_hops
- min_synapses
- max_neurons hard safety limit
- export JSON/Parquet circuit artifact
- extraction metadata

## Tests
- hop limit
- threshold filtering
- directionality
- deterministic output
- max-neuron abort
- missing seed

## Smoke Test
Tiny fixture produces known expected circuit.

## Acceptance Criteria
No edge in exported biological circuit exists without source provenance.

---

# P3 — Neural Simulation

## Goal
Run deterministic simplified neural dynamics on an extracted circuit.

## Implement
- SimulationConfig
- LIF-like engine
- weight normalization function
- stimulus injection
- step/run/reset
- activity snapshots
- deterministic seed
- refractory/leak behavior as configured

## Tests
- no input decays
- sufficient input can fire
- spike propagates across fixture edge
- reset is deterministic
- inhibitory behavior only if dataset/model explicitly supports how sign is derived; otherwise do not invent it

## Acceptance Criteria
Simulation semantics documented and clearly labeled modeled, not measured.

---

# P4 — Escape Behavior

## Goal
Produce first end-to-end action.

## Research Gate
Identify defensible current MCNS visual/looming-related input and descending/output population mappings from authoritative annotations/literature.

Create:
`docs/circuits/escape_v1.md`

If mappings cannot be verified, implement the application pipeline with synthetic fixture but DO NOT call it a biological escape circuit.

## Implement
- LoomingStimulus
- stimulus mapper
- selected circuit config
- MotorDecoder
- action enum
- end-to-end experiment runner

## Acceptance Criteria
A documented stimulus can lead through simulation to an action.
Biological claims are traceable.

---

# P5 — Web UI

## Goal
Make the complete flow visible.

## Layout
Left: Environment
Center: Circuit
Right: Action

## Implement
- virtual fly
- looming object / Danger button
- simulation controls
- current action
- activity counters
- reset
- WebSocket or appropriate streaming mechanism

## Acceptance Criteria
User can trigger danger and see stimulus → activity → action without terminal interaction.

---

# P6 — Brain Visualization & Inspector

## Goal
Make biological grounding inspectable.

## Implement
- circuit graph visualization
- active/firing state
- edge direction
- neuron click inspector
- provenance panel
- upstream/downstream local view
- model-vs-data labels

## Performance
Do not attempt full 166K graph rendering.
Use extracted circuit / active neighborhood.

## Acceptance Criteria
Any displayed biological edge can be inspected to its source identifiers.

### MVP RELEASE GATE
P0-P6 passing = MVP v0.1 candidate.

---

# P7 — Food Seeking

## Goal
Add a second behavior demonstrating reusable architecture.

## Gate
Select olfactory/food-related circuit only from verified annotations/literature.

## Implement
- food stimulus
- olfactory mapper
- approach output decoder
- conflict behavior rules if danger and food coexist

## Acceptance Criteria
Architecture reuses existing SensorAdapter/Simulation/Motor interfaces without special-case rewrite.

---

# P8 — Webcam

## Goal
Replace virtual looming stimulus with camera-derived event.

## Implement
- webcam permission UX
- local frame processing
- simple looming detector
- WebcamVisionSensor
- privacy note: no upload by default

## Acceptance Criteria
Approaching object can generate the same normalized stimulus schema used by virtual environment.

---

# P9 — Robot Adapter

## Goal
Give the agent a physical body.

## Implement
- RobotAdapter interface
- ESP32 serial or Wi-Fi protocol
- safety timeout
- stop command
- bounded motor commands

## Acceptance Criteria
Disconnect/error defaults to STOP.
Simulation/application remains usable without robot hardware.
