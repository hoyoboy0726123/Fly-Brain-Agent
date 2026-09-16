# SDD — FlyBrain Agent

## 1. Architecture

```text
Environment
    ↓
Sensor Adapter
    ↓
Stimulus Mapper
    ↓
Circuit Runtime
    ↓
Neural Simulation Engine
    ↓
Output Population Activity
    ↓
Motor Decoder
    ↓
Action
    ↓
Environment
```

Data plane:

```text
Official Dataset
    ↓
Raw Adapter
    ↓
Normalized Tables
    ↓
Graph Builder
    ↓
Circuit Extractor
    ↓
Circuit Artifact
```

## 2. Repository Structure

```text
flybrain-agent/
├── README.md
├── PRD.md
├── SDD.md
├── DATA.md
├── NEUROSCIENCE.md
├── AGENTS.md
├── TASKS.md
├── PROGRESS.md
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── connectome/
│   │   ├── circuits/
│   │   ├── simulation/
│   │   ├── sensors/
│   │   ├── motor/
│   │   ├── models/
│   │   └── config/
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── environment/
│   │   ├── brain/
│   │   ├── dashboard/
│   │   ├── api/
│   │   └── components/
│   └── tests/
├── data/
│   ├── raw/.gitkeep
│   ├── processed/.gitkeep
│   └── circuits/.gitkeep
├── scripts/
└── docs/
```

## 3. Normalized Data Model

### neurons.parquet
Required:
- neuron_id: string
- dataset: string
- dataset_version: string

Optional nullable:
- cell_type
- cell_class
- region
- neurotransmitter
- sex
- source_url

### connections.parquet
- pre_neuron_id: string
- post_neuron_id: string
- synapse_count: integer
- dataset: string
- dataset_version: string

Never invent missing biological fields.

## 4. Circuit Artifact

```json
{
  "circuit_id": "escape_v1",
  "dataset": "...",
  "dataset_version": "...",
  "extractor_config": {
    "max_hops": 5,
    "min_synapses": 10,
    "max_neurons": 1000
  },
  "seed_neurons": [],
  "target_neurons": [],
  "nodes": [],
  "edges": []
}
```

Artifacts must include source IDs and extraction configuration.

## 5. Core Interfaces

### DatasetAdapter
- inspect()
- load_neurons()
- load_connections()
- validate_schema()

### CircuitExtractor
- extract(seed_ids, target_ids, max_hops, min_synapses, max_neurons)
- export()

### SimulationEngine
- reset(seed)
- stimulate(neuron_ids, intensity)
- step(dt)
- run(steps)
- get_activity()

### SensorAdapter
- parse(event)
- map_to_stimulus()

### MotorDecoder
- decode(activity) -> Action

## 6. Simulation Model
MVP default: simplified discrete-time LIF (implemented in P3, `backend/app/simulation/`).

Conceptual state per neuron (all SIMULATED): membrane potential V, threshold, reset
potential, leak, refractory_remaining, fired. Global `SimulationConfig` (pydantic, frozen,
labelled **COMPUTATIONAL MODEL PARAMETERS — NOT MEASURED MALECNS PARAMETERS**): `dt`,
`resting_potential`, `reset_potential`, `threshold`, `leak`, `refractory_steps`,
`weight_transform`, `weight_scale`, `stimulus_gain`, `noise_std`, `max_potential`,
`max_steps_per_run`, `random_seed`, `sign_mode`.

Update per step (see NEUROSCIENCE.md §8 for the full rule): leak toward rest with factor
`1 − leak·dt`, add synaptic input from spikes of the previous step (one-step delay), add
generic external input, clamp to `max_potential`, fire when `V ≥ threshold` (reset + refractory).

Connection strength is derived from `synapse_count` through the documented, configurable
normalization `w = transform(synapse_count) × weight_scale` (`log1p` default). Signs are not
derived from the dataset: `sign_mode = unsigned_excitatory_only`.

Engine interface (`SimulationEngine(circuit, config)`): `reset()`,
`stimulate(neuron_ids, intensity, duration_steps)`, `step()`, `run(steps)`, `get_state()`,
`get_activity()`, `snapshot(simulation_id)` / `from_snapshot(circuit, snapshot)`.
Snapshots reference the circuit artifact by `circuit_id` + `circuit_hash`; biological
provenance is never copied into them.

Safeguards: validated configuration (finite values, `threshold > reset`, `max_potential >
threshold`, `0 ≤ leak·dt ≤ 1`), unknown neuron ids / negative durations / non-finite
intensities fail loudly, NaN/Inf aborts, `max_steps_per_run` bounds each run.

All parameters live in configuration, not hard-coded in UI/API handlers.

Important: structural connectivity is biological data; simulated voltage/spiking is model-generated.

## 7. API Sketch
- GET /health
- GET /datasets
- GET /circuits
- GET /circuits/{id}
- POST /circuits/extract
- POST /simulation/reset
- POST /simulation/stimulate
- POST /simulation/step
- GET /simulation/state
- GET /neurons/{id}
- WS /ws/simulation

## 8. Frontend
Main layout:
- left: virtual environment
- center: active circuit
- right: action/activity dashboard

Do not render full connectome in MVP.
Render current extracted circuit and optionally only active neighborhood.

## 9. Performance Strategy
- Parquet for normalized data.
- Avoid pandas object-heavy graph representation for full dataset when possible.
- Use vectorized arrays / sparse structures for simulation.
- NetworkX acceptable for MVP extraction on reduced graphs; consider igraph/scipy sparse for larger workloads.
- Simulation runs outside UI main thread/process boundary as appropriate.

## 10. Error Handling
Fail loudly when:
- dataset version unknown
- required columns missing
- seed neuron not found
- edge references missing node
- requested circuit exceeds max_neurons
- provenance unavailable for an edge intended for biological visualization

## 11. Testing
Unit:
- schema validation
- graph extraction
- weight normalization
- LIF state transition
- motor decoder

Integration:
- fixture dataset → extract → stimulate → action

E2E:
- open page
- trigger danger
- observe non-empty activity
- observe escape action
