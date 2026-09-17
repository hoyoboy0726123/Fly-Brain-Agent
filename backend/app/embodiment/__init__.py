"""APPLICATION / EMBODIMENT INTERPRETATION layer (P7.0): closed-loop architecture.

    World → SensorAdapter → SensoryObservation → FlyBrain → MotorDecoder → MotorCommand
          → BodyAdapter → BodyState → World

Boundaries kept explicit (see docs/EMBODIMENT.md):
- BIOLOGICAL STRUCTURE (app.connectome, app.circuits): MaleCNS ids, cell types, edges, synapses
- COMPUTATIONAL DYNAMICS (app.simulation): membrane potentials, spikes, refractory state
- APPLICATION / EMBODIMENT (this package, app.sensors, app.motor, app.behavior): virtual
  world, sensor mapping, motor mapping, simplified computational body

Structural connectivity is biological data. Neural activity is simulated. Virtual sensing,
motor mapping, body dynamics, and world physics are computational interpretations.
"""

from app.embodiment.body import BodyAdapter, SimpleBodyAdapter
from app.embodiment.errors import (
    AdapterError,
    EmbodimentError,
    InvalidStateError,
    InvalidTimestepError,
    LoopLimitError,
    UnsupportedActionError,
)
from app.embodiment.loop import BrainAdapter, EmbodiedAgentLoop
from app.embodiment.models import (
    COMPUTATIONAL_MOTOR_MAPPING,
    COMPUTATIONAL_SENSOR_INPUT,
    EMBODIMENT_DISCLAIMER,
    RESERVED_FUTURE_COMMANDS,
    SIMPLIFIED_COMPUTATIONAL_BODY,
    BodyState,
    BrainStepSummary,
    EmbodiedExperimentRecord,
    EmbodiedStepRecord,
    EmbodimentProvenance,
    EscapeMotorConfig,
    LoopConfig,
    MotorCommand,
    MotorCommandType,
    SensoryObservation,
    SimpleBodyConfig,
    SimpleWorldConfig,
    SimulationClock,
    TimingInfo,
    Vector3,
    VirtualLoomingSensorConfig,
    WorldObject,
    WorldState,
    validate_dt,
)
from app.embodiment.motor import EscapeMotorAdapter, MotorAdapter
from app.embodiment.sensors import SensorAdapter, StimulusEncoder, VirtualLoomingSensor
from app.embodiment.world import SimpleWorldAdapter, WorldAdapter

__all__ = [
    "COMPUTATIONAL_MOTOR_MAPPING",
    "COMPUTATIONAL_SENSOR_INPUT",
    "EMBODIMENT_DISCLAIMER",
    "RESERVED_FUTURE_COMMANDS",
    "SIMPLIFIED_COMPUTATIONAL_BODY",
    "AdapterError",
    "BodyAdapter",
    "BodyState",
    "BrainAdapter",
    "BrainStepSummary",
    "EmbodiedAgentLoop",
    "EmbodiedExperimentRecord",
    "EmbodiedStepRecord",
    "EmbodimentError",
    "EmbodimentProvenance",
    "EscapeMotorAdapter",
    "EscapeMotorConfig",
    "InvalidStateError",
    "InvalidTimestepError",
    "LoopConfig",
    "LoopLimitError",
    "MotorAdapter",
    "MotorCommand",
    "MotorCommandType",
    "SensorAdapter",
    "SensoryObservation",
    "SimpleBodyAdapter",
    "SimpleBodyConfig",
    "SimpleWorldAdapter",
    "SimpleWorldConfig",
    "SimulationClock",
    "StimulusEncoder",
    "TimingInfo",
    "UnsupportedActionError",
    "Vector3",
    "VirtualLoomingSensor",
    "VirtualLoomingSensorConfig",
    "WorldAdapter",
    "WorldObject",
    "WorldState",
    "validate_dt",
]
