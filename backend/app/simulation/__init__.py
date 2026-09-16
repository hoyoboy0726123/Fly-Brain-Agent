"""COMPUTATIONAL DYNAMICS layer: simplified neural simulation engine (P3).

Anything produced here is SIMULATED (modelled) activity, never measured biological activity.
The only biological input is the structural connectivity of a P2 ``Circuit`` artifact.

- ``config``   ``SimulationConfig`` — COMPUTATIONAL MODEL PARAMETERS, NOT MEASURED MALECNS
               PARAMETERS
- ``weights``  synapse_count (structural observation) → simulation weight (computational transform)
- ``engine``   ``SimulationEngine``: reset / stimulate / step / run / get_state / snapshot
- ``state``    serializable state, run summaries and snapshots (reference the circuit artifact)
- ``errors``   fail-loud exceptions
"""

from app.simulation.config import PARAMETER_LABEL, SimulationConfig
from app.simulation.engine import SimulationEngine, peak_rss_bytes
from app.simulation.errors import (
    CircuitCompatibilityError,
    InvalidStimulusError,
    NumericalInstabilityError,
    SimulationError,
    SimulationLimitError,
    SnapshotMismatchError,
    UnknownNeuronError,
)
from app.simulation.state import (
    ACTIVITY_LABEL,
    NeuronState,
    RunSummary,
    SimulationSnapshot,
    SimulationState,
    StepSummary,
    StimulusRecord,
)
from app.simulation.weights import normalize_weight, normalize_weights

__all__ = [
    "ACTIVITY_LABEL",
    "PARAMETER_LABEL",
    "CircuitCompatibilityError",
    "InvalidStimulusError",
    "NeuronState",
    "NumericalInstabilityError",
    "RunSummary",
    "SimulationConfig",
    "SimulationEngine",
    "SimulationError",
    "SimulationLimitError",
    "SimulationSnapshot",
    "SimulationState",
    "SnapshotMismatchError",
    "StepSummary",
    "StimulusRecord",
    "UnknownNeuronError",
    "normalize_weight",
    "normalize_weights",
    "peak_rss_bytes",
]
