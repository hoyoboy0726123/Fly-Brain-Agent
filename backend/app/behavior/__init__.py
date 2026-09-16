"""APPLICATION DECODING layer (orchestration): versioned behaviour configs and the
end-to-end runner (stimulus → mapper → simulation → decoder → action) — P4.

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
    "CONFIG_DIR",
    "DISCLAIMER",
    "ActivityGroup",
    "Citation",
    "EscapeCircuitConfig",
    "EscapeExperiment",
    "EscapeResult",
    "GroupActivity",
    "GroupEdge",
    "NeuronActivity",
    "TimelineEvent",
    "load_escape_circuit",
    "load_escape_config",
]
