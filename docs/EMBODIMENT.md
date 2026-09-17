# Embodiment architecture (P7.0), Virtual Threat Lab (P7.1), Neural Intervention Lab (P7.2)

> Structural connectivity is biological data. Neural activity is simulated.
> Virtual sensing, motor mapping, body dynamics, and world physics are computational
> interpretations.

P7.0 introduces the architecture that lets the existing FlyBrain neural system control a
body — first a simple virtual body, later a Three.js visual body, NeuroMechFly / FlyGym /
MuJoCo, and potentially a physical robot — **without rewriting the biological circuit or the
neural simulation layers**. It is a foundation: no visual world, no physics engine, no
locomotion and no new biology are part of it.

## 1. From open loop to closed loop

Up to P6 the system was `Stimulus → Brain → Action`. The embodiment layer closes the loop:

```mermaid
flowchart TD
    W["Virtual World<br/>WorldAdapter · WorldState (objects, positions, velocities, sizes)"]
    S["Sensor Adapter<br/>VirtualLoomingSensor · angular size + bearing"]
    O["Sensory Observation<br/>COMPUTATIONAL SENSOR INPUT"]
    E["Stimulus Encoder<br/>→ LoomingStimulus (direction, intensity)"]
    B["FlyBrain<br/>escape_v1 circuit (BIOLOGICAL STRUCTURE) + simulated dynamics (P3/P4, unchanged)"]
    D["Motor Decoder<br/>NO_ACTION / ESCAPE (P4, unchanged)"]
    M["Motor Adapter<br/>NO_ACTION → IDLE · ESCAPE → ESCAPE"]
    C["Motor Command<br/>COMPUTATIONAL MOTOR MAPPING"]
    A["Body Adapter<br/>SimpleBodyAdapter (SIMPLIFIED COMPUTATIONAL BODY)"]
    P["Body State<br/>position · heading · velocity · grounded"]
    W --> S --> O --> E --> B --> D --> M --> C --> A --> P --> W
```

`EmbodiedAgentLoop` (`backend/app/embodiment/loop.py`) coordinates one step in this order and
contains no biological logic:

| # | call | layer |
|---|---|---|
| 1 | `WorldAdapter.get_state()` | virtual world |
| 2 | `BodyAdapter.get_state()` | virtual body |
| 3 | `SensorAdapter.observe(world_state, body_state)` → `SensoryObservation` | computational sensor mapping |
| 4 | `StimulusEncoder.encode(observation)` → P4 `LoomingStimulus` | application input |
| 5 | `EscapeExperiment.run(stimulus)` — existing P4 pipeline, unchanged | biological structure + simulated dynamics |
| 6 | `EscapeResult.decision` — existing P4 `MotorDecoder` output | application decoding |
| 7 | `MotorAdapter.translate(decision, clock)` → `MotorCommand` | computational motor mapping |
| 8 | `BodyAdapter.apply_command(command, dt)` | virtual body |
| 9 | `BodyAdapter.step(dt)` → `BodyState` | virtual body |
| 10 | `WorldAdapter.step(dt)` → `WorldState` | virtual world |
| 11 | `EmbodiedStepRecord` appended, clock advanced | record |

The brain receives **only** a `LoomingStimulus` and returns **only** an `EscapeResult`. Every
state model is frozen (immutable) and rejects NaN / Inf, so body coordinates (x, y, z,
heading, velocity) can change **only** inside a `BodyAdapter`.

## 2. Boundaries

| Layer | Examples | Where | Status |
|---|---|---|---|
| **BIOLOGICAL STRUCTURE** | MaleCNS neuron ids, cell types, structural edges, synapse counts | `app.connectome`, `app.circuits`, `data/circuits/escape_v1.json` | biological data (CC-BY 4.0) |
| **COMPUTATIONAL DYNAMICS** | membrane potential, simulated firing, refractory state, simulation weights | `app.simulation` | SIMULATED |
| **APPLICATION / EMBODIMENT INTERPRETATION** | looming object geometry, virtual sensor mapping, ESCAPE → body command, body velocity / position / heading, world "physics" | `app.embodiment`, `app.sensors`, `app.motor`, `app.behavior` | computational interpretation |

Wording used in code, payloads and docs:

- **BIOLOGICAL DATA** — MaleCNS structural connectivity.
- **SIMULATED NEURAL ACTIVITY** — simplified neural dynamics (P3).
- **COMPUTATIONAL SENSOR MAPPING** — virtual-world state converted into a neural stimulus (`SensoryObservation.interpretation_label = "COMPUTATIONAL SENSOR INPUT …"`).
- **COMPUTATIONAL MOTOR MAPPING** — decoded neural output converted into a body command (`MotorCommand.label`).
- **SIMPLIFIED COMPUTATIONAL BODY** — virtual-body movement is not claimed to reproduce real *Drosophila* biomechanics (`BodyState.label`, `SimpleBodyConfig.label`).

None of the embodiment values is a measured biological property.

## 3. Domain models (`backend/app/embodiment/models.py`)

All models are pydantic, `frozen=True`, `extra="forbid"`, finite-only.

| Model | Fields (minimum) | Notes |
|---|---|---|
| `Vector3` | x, y, z | dimensionless world units |
| `WorldObject` | object_id, object_type, position, velocity, size, properties | generic; no food / odor biology |
| `WorldState` | simulation_time, step_index, objects, metadata | unique object ids; label "VIRTUAL WORLD" |
| `BodyState` | position, heading (rad), linear_velocity, grounded, simulation_time, step_index | label SIMPLIFIED COMPUTATIONAL BODY; no legs |
| `SensoryObservation` | sensor_type, simulation_time, step_index, source, values, interpretation_label, metadata | label is a fixed literal: COMPUTATIONAL SENSOR INPUT |
| `MotorCommandType` | `IDLE`, `ESCAPE` | `FORWARD`, `TURN_LEFT`, `TURN_RIGHT`, `JUMP` are reserved names only (`RESERVED_FUTURE_COMMANDS`), **not** members |
| `MotorCommand` | command, magnitude 0..1, source_action, simulation_time, step_index, label, metadata | `metadata.direction_decoded = False` always |
| `SimulationClock` | dt, step_index, simulation_time | immutable; `advance()` returns a new clock |
| `TimingInfo` | loop_dt, neural_dt, neural_steps_per_loop_step, note | the two time bases, recorded separately |
| configs | `LoopConfig`, `SimpleWorldConfig`, `VirtualLoomingSensorConfig`, `EscapeMotorConfig`, `SimpleBodyConfig` | every config carries a "COMPUTATIONAL … PARAMETERS" label |
| records | `BrainStepSummary`, `EmbodiedStepRecord`, `EmbodimentProvenance`, `EmbodiedExperimentRecord` | reproducibility, see §6 |

## 4. Adapter interfaces

| Interface | Responsibilities | P7.0 implementation |
|---|---|---|
| `WorldAdapter` | `reset()`, `step(dt)`, `get_state()`; owns environment state | `SimpleWorldAdapter` — one looming object approaching the origin in a straight line at constant speed (deterministic, no randomness) |
| `SensorAdapter` | `observe(world_state, body_state) → SensoryObservation`; never touches the brain | `VirtualLoomingSensor` — nearest looming object: distance, bearing, angular size `2·atan(size / distance)`, `intensity = min(angular_size / saturation_angle, 1)`, direction left / center / right by bearing with a center band; out of the field of view → intensity 0 |
| `StimulusEncoder` | observation → existing P4 `LoomingStimulus` | reads `intensity` and `direction` from the observation |
| `BrainAdapter` (Protocol) | `run(stimulus) → EscapeResult` | satisfied by the existing P4 `EscapeExperiment`; no new brain code |
| `MotorAdapter` | `translate(decision, clock) → MotorCommand` | `EscapeMotorAdapter` — `NO_ACTION → IDLE`, `ESCAPE → ESCAPE`; giant-fiber side is metadata only, **no direction is decoded** |
| `BodyAdapter` | `reset()`, `apply_command(command, dt)`, `step(dt)`, `get_state()`; the only place body coordinates change | `SimpleBodyAdapter` — IDLE: no movement; ESCAPE: deterministic displacement along the current heading plus a brief airborne phase; an ESCAPE while airborne adds no second impulse |

### SimpleBodyAdapter — SIMPLIFIED COMPUTATIONAL BODY

Point body with a heading. Parameters (`SimpleBodyConfig`, computational, not measurements):
`escape_speed` 5.0 units/s along the heading, `escape_vertical_speed` 3.0 units/s,
`airborne_duration` 0.3 s, `ground_drag` 1.0/s. On landing the body returns to the ground
plane and stops. The escape direction is the body's current heading — an application
choice, because DNp01 / giant-fiber activity does not encode direction (Jang et al. 2023) and
current evidence does not justify `ESCAPE_LEFT` / `ESCAPE_RIGHT`.

## 5. Timing

- The loop uses **one common deterministic timestep** `LoopConfig.dt` (default 0.1 s of
  computational time) for the world and the body. Nothing depends on browser animation timing.
- Each loop step runs a **fresh** neural experiment of `neural_steps_per_loop_step` model
  steps (default: the escape config's `simulation_steps` = 30) with the model's own
  `SimulationConfig.dt` (1.0, a dimensionless model unit). Neural state is **not** carried
  across loop steps in P7.0 (the P4 runner builds a new engine per run).
- Both time bases are recorded in `EmbodimentProvenance.timing` (`loop_dt`, `neural_dt`,
  `neural_steps_per_loop_step`) and are not claimed to be physically related. Making them
  differ explicitly (e.g. neural sub-steps per loop step tied to `dt`) is a later decision.

## 6. Determinism and provenance

Given the same initial `WorldState`, `BodyState`, random seed, FlyBrain configuration and
sequence of observations, the closed-loop result is reproducible (tested: two runs produce
identical `EmbodiedExperimentRecord`s apart from wall-clock fields). `SimpleWorldAdapter` and
`SimpleBodyAdapter` draw no random numbers; the neural seed lives in `SimulationConfig`.

`EmbodimentProvenance` records: dataset, dataset_version, canonical graph selection rule,
circuit_id, circuit_hash, biological status, escape config version, simulation config,
loop random seed, world / sensor / motor / body adapter names and configs, loop config and
timing. `scripts/smoke_embodiment.py` writes a full record to
`data/simulations/embodiment_smoke.report.json`.

## 7. Future adapters (documented, NOT implemented in P7.0)

| Adapter | Role | Notes |
|---|---|---|
| `SimpleBodyAdapter` | point body for architecture tests and the P7.1 Virtual Threat Lab | **implemented** (P7.0) |
| `ThreeJSBodyAdapter` | drives a visual body in the browser from `BodyState` / `MotorCommand` | later phase; the browser renders, it never owns the state |
| `FlyGymAdapter` (NeuroMechFly / MuJoCo) | maps `MotorCommand` to a physics-based fly body and reads its pose back into `BodyState` | later phase; requires an explicit biomechanics provenance record |
| `RobotAdapter` | maps `MotorCommand` to a physical actuator with safety limits | later phase; safety gate first |

All of them implement the same `BodyAdapter` interface; the brain, decoder and motor
mapping stay unchanged.

## 8. What P7.0 does not do

No Three.js / 3D model, no MuJoCo / FlyGym / NeuroMechFly, no robotics, no food seeking, no
odor, no locomotion or six-leg gait, no collision physics, no new circuits, no new
endpoints (embodiment is additive and purely backend in P7.0; P7.1 adds the read-only
replay API below), no change to P0–P6 behaviour (`escape_v1` produces the same deterministic
results under the same configuration).

## 9. Running it

```bash
make smoke-embodiment      # scripts/smoke_embodiment.py: looming object → virtual fly, 30 loop steps
make smoke-threat-lab      # scripts/smoke_threat_lab.py: the same loop through the P7.1 API over HTTP
make smoke-intervention    # scripts/smoke_intervention.py: CONTROL vs SILENCE_LPLC2 through the P7.2 A/B API
make test-backend          # includes test_embodiment.py, test_api_embodiment.py, test_intervention.py, test_api_intervention.py
make demo                  # then open "Virtual Threat Lab" (/#threat-lab) or "Neural Intervention Lab" (/#intervention)
```

## 10. Virtual Threat Lab (P7.1)

P7.1 makes the P7.0 loop **visible, interactive and replayable** without touching its
scientific logic. Roles of the three P7 sub-phases:

| Phase | Role | Status |
|---|---|---|
| P7.0 | embodiment architecture: models, adapters, `EmbodiedAgentLoop` | done |
| P7.1 | Virtual Threat Lab: replayable API + 2D arena / brain / loop-story UI | done |
| P7.2 | Neural Intervention Lab: COMPUTATIONAL FIRING SUPPRESSION inside the engine, A/B comparison UI | done (SUPPRESS_FIRING only) |

### 10.1 API (`backend/app/api/embodiment.py`)

`ThreatLabService` builds a **fresh** `EmbodiedAgentLoop` per request from the shared
escape_v1 brain (`EscapeService.experiment`, unchanged parameters) and the P7.0 adapters
(`SimpleWorldAdapter` with the requested world geometry, `VirtualLoomingSensor`,
`EscapeMotorAdapter`, `SimpleBodyAdapter`, `LoopConfig(dt=0.1, max_steps, random_seed)`).
It does not duplicate any embodiment logic: each timeline entry is the P7.0
`EmbodiedStepRecord` reshaped for replay.

| Endpoint | Returns |
|---|---|
| `GET /embodiment/config` | `experiment_name` (`virtual_threat_lab_v1`), `disclaimer`, `labels` (world physics COMPUTATIONAL · virtual sensing COMPUTATIONAL SENSOR INPUT · neural activity SIMULATED · structural connectivity BIOLOGICAL DATA · body SIMPLIFIED COMPUTATIONAL BODY · motor mapping COMPUTATIONAL MOTOR MAPPING), `scientific_boundaries`, `units_note`, world / sensor / body / motor / loop configs, `timing`, `circuit` (id, hash, dataset, neurons, edges, biological status, research document), `groups`, `group_edges`, `max_loop_steps` (200), `run_request_limits` |
| `POST /embodiment/run` | `experiment_id`, `created_at`, `disclaimer`, `labels`, `request`, `provenance` (P7.0 `EmbodimentProvenance`), `groups`, `initial_world`, `initial_body`, `timeline[]`, `outcome`, `runtime_seconds` |

Request (`extra="forbid"`; anything else, including any neural parameter, is a 422):
`seed ≥ 0`, `max_steps 1…200` (default 30), `world.start_distance 1…100`,
`world.approach_speed 0…50`, `world.azimuth_deg −180…180`. Errors: 422 `invalid_request`,
503 `circuit_unavailable` / `circuit_mismatch` / `config_unavailable` (same holder as
`/escape`), 500 `simulation_error` / `embodiment_error` (no partial timeline is returned),
504 `timeout`.

Each `timeline[i]` (`step_index = i`, 0-based; `simulation_time = i · dt`) carries:

| Key | Source (P7.0) | Content |
|---|---|---|
| `world` | state observed at loop step 1 (`WorldState`) | `simulation_time`, `step_index`, objects (`position`, `velocity`, `size`, type) — label COMPUTATIONAL WORLD |
| `body` | state observed at loop step 2 (`BodyState`) | `position`, `velocity`, `heading`, `grounded` — label SIMPLIFIED COMPUTATIONAL BODY |
| `sensor` | `SensoryObservation` (step 3) | `intensity`, `direction`, `distance`, `bearing_rad`, `angular_size_rad`, `visible` — label COMPUTATIONAL SENSOR INPUT |
| `brain` | `BrainStepSummary` (step 5–6) | `stimulus`, `neural_steps`, `neural_dt`, `group_fired_counts` (per group, per neural step — the P4 `group_activity`), `group_peak_fired`, `sensory_first_fire_step`, `first_output_fire_step`, `output_spike_count`, `fired_output_sides`, `firing_events`, `neurons_activated`, decoded `action` — label SIMULATED NEURAL ACTIVITY |
| `motor` | `MotorCommand` (step 7) | `command` (IDLE / ESCAPE), `magnitude`, `source_action`, `direction_decoded = false` — label COMPUTATIONAL MOTOR MAPPING |

Replay semantics: step *N* shows the geometry the sensor actually saw at *N* and the
brain / motor results computed from it; the body movement caused by that command is the
**observed body of step N + 1** (exactly the P7.0 order World → Sensor → Brain → Motor → Body
→ World). `outcome.events` marks `first_escape`, further `escape` steps and `landed` (first
observed step back on the ground). To keep payloads small, **no per-neuron state** is
returned (a 30-step run is ≈ 66 KiB); per-neuron traces remain in the P5 API and P6 inspector.

Additive P7.0 change for this: `BrainStepSummary` gained `sensory_first_fire_step` and
`group_fired_counts` (copied from the P4 result; no computation).

### 10.2 UI (`frontend/src/threatlab/`)

- `useThreatLab.ts` — loads the config, runs one experiment, keeps a replay cursor
  (`step`), PLAY / PAUSE / STEP / seek / RESET (rewinds to step 0). Phases: `idle`
  (WAITING FOR EXPERIMENT) → `running` → `ready` | `error` (NO RESULT). `?pace=<ms>` sets the
  replay pace (default 140 ms per loop step).
- `Arena.tsx` — SVG top-down world (no Three.js): object = `WorldState`, fly = `BodyState`
  (heading, airborne lift from `z`), fly's-eye inset radius = recorded `angular_size_rad`.
  Nothing is drawn before a run or after a failure. **Interpolation is presentation only**:
  a 110 ms CSS transition tweens between two recorded positions (disabled under
  `prefers-reduced-motion`); the DOM `data-x/y/z/heading/grounded` attributes always hold the
  exact recorded values (the Playwright tests assert on them).
- `Panels.tsx` — DISTANCE (units) / LOOMING INPUT / BODY POSITION / ACTION metrics and the
  WORLD / BODY / SENSOR read-outs; `ThreatLabBrain.tsx` — group nodes (identity = biological
  structure, glow = simulated peak activity of the loop step) plus per-neural-step spike bars,
  labelled SIMULATED NEURAL ACTIVITY; `LoopStory.tsx` — WORLD ↓ SENSOR ↓ BRAIN ↓ MOTOR ↓ BODY
  ↺ WORLD with the highlighted stage derived from the record (deepest stage carrying signal:
  looming input > 0, simulated spikes > 0, ESCAPE command, body moving); `ReplayControls.tsx`
  — RUN / PLAY / PAUSE / STEP / RESET, slider, ⚡ ESCAPE and ▼ landed markers (click = jump);
  `Boundaries.tsx` — labels, scientific boundaries, provenance and the disclaimer served by the
  backend; `ParamsForm.tsx` — world geometry, steps, seed only.
- Selecting step *N* (slider, markers, STEP, PLAY) re-renders every panel from
  `timeline[N]`; the P5 demo and the P6 inspector are untouched.

### 10.3 What P7.1 does not do

No neural intervention (added in P7.2 as computational firing suppression), no food or odor,
no Three.js / 3D body, no FlyGym / NeuroMechFly / MuJoCo, no six-leg gait, no robotics, no
change to the P0–P7.0 scientific logic, no frontend-generated activity or movement, no
default outcome when the backend fails. The v0.1.0 tag / release are not touched.

## 11. Neural Intervention Lab (P7.2)

> Computational intervention suppresses simulated firing of selected neurons while
> preserving the biological structural connectivity.

> Neural interventions in this lab are computational manipulations of simulated neural
> dynamics. They do not reproduce a specific biological silencing, optogenetic, genetic,
> pharmacological, or lesion technique. Biological structural connectivity remains unchanged.

### 11.1 STRUCTURE ≠ DYNAMICS ≠ INTERVENTION ≠ BEHAVIOR

| Layer | What it is | Where | Touched by P7.2? |
|---|---|---|---|
| STRUCTURE | MaleCNS neuron ids, cell types, edges, synapse counts (circuit artifact, sealed hash) | `app/circuits` | **never** — verified before / after every trial (node count, edge count, synapse total, content hash) |
| DYNAMICS | simplified LIF-like simulation of activity on that structure | `app/simulation` | yes — this is the only place the intervention acts |
| INTERVENTION | a computational manipulation of the dynamics (`InterventionConfig`, layer COMPUTATIONAL DYNAMICS) | `app/simulation/intervention.py` | new |
| BEHAVIOR | decoded action → motor command → body → world | `app/motor`, `app/embodiment` | **never** — whatever changes downstream emerges from the model |

### 11.2 Exact suppression semantics (`SUPPRESS_FIRING`)

Implemented in `SimulationEngine.step()`; the engine builds a boolean mask from the target ids
(unknown ids fail loudly) and never touches the `Circuit`, the edge arrays or the weights.
For a targeted neuron at every step:

1. it remains in the circuit with its biological id; its structural edges and their
   `synapse_count` are unchanged (the P2 artifact is read-only);
2. synaptic input from spikes of the previous step and external stimulus input are still
   accumulated; the membrane potential still integrates, leaks and is clamped as for any
   other neuron;
3. when `potential ≥ threshold`, `fired` is forced to `False`: no spike is recorded in the
   raster, the neuron is **not** reset and **not** made refractory, and therefore no
   spike-driven input propagates along its outgoing edges at the next step.

`StepSummary.suppressed_count` / `RunSummary.suppressed_events` count these silent threshold
crossings (they are large: a suppressed neuron that stays above threshold is counted every
step). `NeuronState.suppressed` flags targeted neurons in `get_state()`. `NONE` (the default
for every existing caller) is byte-for-byte the pre-P7.2 behaviour (tested). Other mechanisms
(`STIMULATE`, `CLAMP`, `LESION`, `REMOVE_CONNECTION`, `SYNAPTIC_BLOCK`) are documented in
`FUTURE_INTERVENTION_TYPES` and rejected by the engine — **not implemented**.

Forbidden and absent: deleting neurons or edges, zeroing `synapse_count`, rewriting the
artifact, touching `MotorDecoder`, `MotorAdapter`, `BodyAdapter`, `WorldAdapter`, the
frontend or `ThreatLabService` with any suppression logic, and any `if intervention == …:
action = …` rule.

### 11.3 Target resolution (`app/behavior/intervention.py`)

User-facing selectors `CONTROL`, `SILENCE_LC4`, `SILENCE_LPLC2`, `SILENCE_LC4_LPLC2` are
resolved with `resolve_targets(circuit, selector)`: circuit nodes whose MaleCNS `cell_type`
annotation equals the selected type(s), union without duplicates, sorted. It fails loudly when
the selector is unknown, the circuit carries no annotations, a cell type resolves to zero
neurons or the union is empty. The result (`ResolvedTargets`: cell types, ids, count,
per-type counts, circuit hash, resolution rule) is recorded in provenance. On the committed
escape_v1 artifact this resolves to LC4 126, LPLC2 158, both 284 — read from the artifact,
never hard-coded.

### 11.4 Plumbing (no logic)

`EscapeExperiment.run(…, intervention=None)` hands the config to `SimulationEngine`;
`EmbodiedAgentLoop(…, intervention=None)` passes it to the brain at every loop step (only
when active, so pre-P7.2 brains keep their call signature) and writes it into
`EmbodimentProvenance.intervention` (`intervention_layer = "COMPUTATIONAL DYNAMICS"`);
`BrainStepSummary.suppressed_events` and `BrainView.suppressed_events` carry the counts.
`ThreatLabService.run(request, intervention=None)` forwards it to the loop.

### 11.5 A/B API (`app/api/intervention.py`)

| Endpoint | Returns |
|---|---|
| `GET /embodiment/intervention/config` | label, layer, semantics, both disclaimers, implemented types (`NONE`, `SUPPRESS_FIRING`), future types (not implemented), the four suppression rules, `selectors[]` with resolved targets from the loaded circuit, `structural_signature`, circuit / dataset, `biological_context` (Ache et al. 2019), the "CURRENT COMPUTATIONAL RESULT — not a validation" label |
| `POST /embodiment/intervention/compare` `{intervention, seed, max_steps ≤ 200, world}` | `comparison_id`, `control` and `intervention` trials (`intervention_config`, `resolved_targets`, the full P7.1 `experiment` incl. provenance, `structural_signature`, `simulated_firing_totals` per LC4 / LPLC2 / DNp01, `suppressed_events`), `comparison` = **verified** `matched_conditions` (seed, world, initial body, sensor / body / motor / simulation configs, circuit hash, dataset version, timing, loop config, decoder version; the server refuses to answer if any is false), descriptive `differences` (first ESCAPE steps, occurrence, escape steps, action counts, per-cell-type simulated spikes with deltas, displacements, first divergent step, plain-language summary that never interprets biology), `synchronization` (steps per trial, shared steps, cursor max, "TRIAL ENDED" rule), `structural_integrity` (signature before / after, `unchanged`), `biological_context`, `runtime` |

Both trials are fresh P7.0 loops on the shared escape_v1 brain with the same
`ThreatLabRunRequest`; the only difference is the `InterventionConfig`. Errors: 422 for an
unknown selector or extra field, 503 when the brain or the targets are unavailable, 500
(no partial comparison) when a trial fails or conditions do not match, 504 on timeout.

### 11.6 UI (`frontend/src/intervention/`)

`useInterventionLab` (config, one comparison call, one shared cursor), `InterventionLabView`
(selector, seed / steps / world, RUN CONTROL + INTERVENTION, "SAME WORLD • SAME SEED • SAME
MODEL" only once the backend has verified it), two `TrialPanel`s (arena, metrics, ACTION, brain
panel; a trial past its timeline shows **TRIAL ENDED** and nothing else), shared replay
(◀ STEP / PLAY / PAUSE / STEP ▶ / RESET / slider with ⚡A and ⚡B first-ESCAPE markers),
`ComparisonPanel` (verified conditions + descriptive table + summary), `BiologicalContext`
(BIOLOGICAL EVIDENCE column vs CURRENT COMPUTATIONAL RESULT column, both disclaimers).
Suppressed groups in `ThreatLabBrain` are crossed out and labelled SUPPRESSED with their
neuron count (structure present, glow off, raster hatched) — never hidden. The Brain
Inspector's neuron panel shows BIOLOGICAL STRUCTURE present · INTERVENTION COMPUTATIONAL
FIRING SUPPRESSION · SIMULATED FIRED false for neurons targeted by the last comparison; the
structural graph is unchanged.

### 11.7 Observed with the current model (descriptive, not biological validation)

Default world (object radius 1 at 20 units, 10 units/s, azimuth 0°), seed 0, 30 loop steps:

| Trial | first ESCAPE | LC4 spikes | LPLC2 spikes | GF (DNp01) spikes | displacement |
|---|---|---|---|---|---|
| CONTROL | step 16 | 378 | 474 | 6 | 1.50 |
| SILENCE LC4 (126 neurons) | step 16 | 0 | 474 | 6 | 1.50 |
| SILENCE LPLC2 (158 neurons) | step 16 | 378 | 0 | 6 | 1.50 |
| SILENCE LC4 + LPLC2 (284 neurons) | none | 0 | 0 | 0 | 0.00 |

In the current computational model either population alone still drives the simulated giant
fiber over threshold; only suppressing both removes the ESCAPE. This is reported as observed
and says nothing about real flies.

### 11.8 What P7.2 does not do

No STIMULATE / CLAMP / LESION / synapse editing, no food seeking, olfaction, reward or
learning, no Three.js / FlyGym / NeuroMechFly / MuJoCo / robotics, no change to P0–P7.1
scientific logic, no tuning to reproduce literature. The v0.1.0 tag / release are not touched.
