# NEUROSCIENCE — Scientific Claims & Guardrails

## 1. What Is Real
When loaded from the official dataset:
- neuron identity
- annotated type/class/region when present
- structural connection direction
- synapse/connection counts when present
- morphology only if explicitly loaded from an authoritative source

## 2. What Is Modeled
Unless directly supported by separate experimental data:
- membrane potential
- firing threshold
- leak constant
- temporal dynamics
- simulated spike timing
- sensory stimulus intensity
- mapping from stimulus intensity to input current
- motor decision threshold

These are computational assumptions.

## 3. Required UI Language
Use wording such as:
- "Connectome-grounded simulation"
- "Structural connectivity from biological dataset"
- "Neural activity shown here is simulated"
- "Simplified neural dynamics"

Avoid:
- "This is exactly what the fly is thinking"
- "We recreated the complete fly mind"
- "These are measured real-time spikes" unless they actually are.

## 4. Behavior Claims
A path from sensory to descending/motor populations does not by itself prove that the simulated behavior reproduces the animal's true behavior.

For MVP, describe output as:
"an action decoded from simulated activity on a biologically grounded structural circuit."

## 5. Circuit Selection
For the Escape MVP:
1. Search current annotations/literature for defensible visual/looming-related input and descending/output populations.
2. Record why each seed/target population was selected.
3. Store citations/URLs in `docs/circuits/escape_v1.md`.
4. If the exact MCNS annotation mapping is uncertain, stop and document uncertainty rather than inventing neuron IDs.

P4 outcome: `docs/circuits/escape_v1.md` — LC4 + LPLC2 (visual projection) → DNp01 (giant
fiber), monosynaptic, **PARTIALLY SUPPORTED** (structure and identities supported; literature
metadata-verified only; unsigned dynamics; no left/right decoding because the GF is
azimuth-invariant). The decoded output is `ESCAPE` / `NO_ACTION`, described as "an action
decoded from simulated activity on a biologically grounded structural circuit".

## 6. Reproducibility
Every experiment records:
- dataset/version
- circuit artifact hash/id
- simulation config
- random seed
- stimulus
- output summary

## 7. Scientific Separation
The codebase should visually and architecturally separate:
BIOLOGICAL STRUCTURE
from
COMPUTATIONAL DYNAMICS
from
APPLICATION DECODING.

This separation is a core product requirement.

## 8. Simulation Model (P3) — what is modeled, exactly

The P3 engine (`backend/app/simulation/`) is a **simplified discrete-time
leaky-integrate-and-fire (LIF-like) model**. Every quantity it produces is SIMULATED.

| Layer | Content | Source |
|---|---|---|
| BIOLOGICAL STRUCTURE | neuron ids, directed edges, `synapse_count` | MaleCNS v1.0 canonical graph → P2 circuit artifact |
| COMPUTATIONAL DYNAMICS | membrane potential, threshold, leak, refractory period, spike events, weights, stimulus current, noise | `SimulationConfig` — **COMPUTATIONAL MODEL PARAMETERS, NOT MEASURED MALECNS PARAMETERS** |
| APPLICATION DECODING | motor decoding, behaviour labels | not implemented yet (P4+) |

Update rule (model units, one step = `dt`), for a non-refractory neuron *i*:

```text
V_i ← V_rest + (V_i − V_rest)·(1 − leak·dt)        leak toward rest (0 ≤ leak·dt ≤ 1)
      + Σ_j w_ji · fired_j(previous step)            synaptic input, one-step delay
      + stimulus_gain · Σ intensity                  GENERIC external input
      + N(0, noise_std)                              optional, seeded (default 0)
V_i ← min(V_i, max_potential)                       clamp; NaN/Inf aborts the run
fired_i ← V_i ≥ threshold  ⇒  V_i = V_reset, refractory_i = refractory_steps
```

Refractory neurons hold `V_reset`, ignore input and count down.

**Weights.** `synapse_count` is a biological structural observation. The simulation weight
is a computational transformation of it: `w = transform(synapse_count) × weight_scale` with
`transform ∈ {log1p (default), linear, sqrt, binary}`. It is *not* an electrophysiological
synaptic strength.

**Signs.** The dataset gives no authoritative excitatory/inhibitory sign per connection, so
P3 runs in `unsigned_excitatory_only` mode: every weight is positive. The publishers'
neurotransmitter *predictions* travel with each neuron as metadata
(`neurotransmitter_prediction`) but are **not** converted into signs. Any future signed mode
must be explicitly implemented, documented and justified before use.

**Stimulus.** `stimulate(neuron_ids, intensity, duration_steps)` is generic input injection.
It is not a visual, looming, danger, odor or food stimulus; those interpretations belong to
later phases.

**Stability is a model property.** With positive-only weights and no inhibition, a dense
induced subgraph can reverberate indefinitely under one parameter set and stay silent under
another (P3 technical smoke: the default parameters on a 1,992-neuron MaleCNS subgraph gave
a self-sustained period-3 oscillation; `weight_scale = 0.05` gave no propagation at all).
Such outcomes describe the computational model, not the fly. Parameters used for any
experiment must be recorded with the run (NEUROSCIENCE.md §6) and must never be tuned to
"make the fly behave" without saying so.

**Required wording** for anything derived from the engine: "simulated activity on a
connectome-grounded structural circuit"; never "measured", "recorded" or "real spikes".
