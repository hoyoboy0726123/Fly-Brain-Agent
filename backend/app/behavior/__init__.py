"""APPLICATION DECODING layer (orchestration): versioned behaviour configs and the
end-to-end runner (stimulus → mapper → simulation → decoder → action) — P4.

P7.2 adds intervention target selectors (``intervention``): user-facing selectors are
resolved to biological neuron ids from the circuit's cell-type annotations; the suppression
itself lives in the simulation engine (COMPUTATIONAL DYNAMICS).

Disclaimer carried by every result:
STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED.
STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS.
"""

from app.behavior.escape_config import (
    CONFIG_DIR,
    Citation,
    EscapeCircuitConfig,
    load_escape_config,
)
from app.behavior.intervention import (
    BIOLOGICAL_CONTEXT,
    INTERVENTION_SELECTORS,
    SELECTOR_CELL_TYPES,
    SELECTOR_LABELS,
    InterventionSelector,
    ResolvedTargets,
    TargetResolutionError,
    build_intervention,
    resolve_targets,
    structural_signature,
)
from app.behavior.runner import (
    DISCLAIMER,
    ActivityGroup,
    EscapeExperiment,
    EscapeResult,
    GroupActivity,
    GroupEdge,
    NeuronActivity,
    TimelineEvent,
    load_escape_circuit,
)

__all__ = [
    "BIOLOGICAL_CONTEXT",
    "CONFIG_DIR",
    "DISCLAIMER",
    "INTERVENTION_SELECTORS",
    "SELECTOR_CELL_TYPES",
    "SELECTOR_LABELS",
    "ActivityGroup",
    "Citation",
    "EscapeCircuitConfig",
    "EscapeExperiment",
    "EscapeResult",
    "GroupActivity",
    "GroupEdge",
    "InterventionSelector",
    "NeuronActivity",
    "ResolvedTargets",
    "TargetResolutionError",
    "TimelineEvent",
    "build_intervention",
    "load_escape_circuit",
    "load_escape_config",
    "resolve_targets",
    "structural_signature",
]
