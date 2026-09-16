"""APPLICATION DECODING layer (input side): stimuli and stimulus → current mapping (P4).

Stimuli are application inputs; the mapping to injected current is a computational rule.
"""

from app.sensors.looming import (
    DIRECTION_TO_SIDES,
    MAPPING_LABEL,
    LoomingSensorAdapter,
    LoomingStimulus,
    SensoryDrive,
    StimulusMapper,
)

__all__ = [
    "DIRECTION_TO_SIDES",
    "MAPPING_LABEL",
    "LoomingSensorAdapter",
    "LoomingStimulus",
    "SensoryDrive",
    "StimulusMapper",
]
