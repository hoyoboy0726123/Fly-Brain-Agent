# Embodiment architecture (P7.0)

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
| `SimpleBodyAdapter` | point body for architecture tests | **implemented** (P7.0) |
| `ThreeJSBodyAdapter` | drives a visual body in the browser from `BodyState` / `MotorCommand` | later phase; the browser renders, it never owns the state |
| `FlyGymAdapter` (NeuroMechFly / MuJoCo) | maps `MotorCommand` to a physics-based fly body and reads its pose back into `BodyState` | later phase; requires an explicit biomechanics provenance record |
| `RobotAdapter` | maps `MotorCommand` to a physical actuator with safety limits | later phase; safety gate first |

All of them implement the same `BodyAdapter` interface; the brain, decoder and motor
mapping stay unchanged.

## 8. What P7.0 does not do

No Three.js / 3D model, no MuJoCo / FlyGym / NeuroMechFly, no robotics, no food seeking, no
odor, no locomotion or six-leg gait, no collision physics, no new circuits, no new
endpoints (embodiment is additive and purely backend in P7.0), no change to P0–P6 behaviour
(`escape_v1` produces the same deterministic results under the same configuration).

## 9. Running it

```bash
make smoke-embodiment      # scripts/smoke_embodiment.py: looming object → virtual fly, 30 loop steps
make test-backend          # includes backend/tests/test_embodiment.py
```
