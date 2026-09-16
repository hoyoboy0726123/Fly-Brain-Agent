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
