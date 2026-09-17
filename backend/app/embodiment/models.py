"""Embodiment domain models (P7.0) — APPLICATION / EMBODIMENT INTERPRETATION layer.

Every model here describes a *virtual* world, a *virtual* body, a *computational* sensor
reading or a *computational* motor command. None of these values is a measured biological
property, and none of them is produced by the biological structure (``app.connectome``,
``app.circuits``) or the simulated dynamics (``app.simulation``) layers.

    Structural connectivity is biological data. Neural activity is simulated.
    Virtual sensing, motor mapping, body dynamics, and world physics are computational
    interpretations.

All models are frozen (immutable) and reject NaN / Inf, so a state can only change by
constructing a new one through an adapter. World units are dimensionless computational
units; time is the loop's computational ``dt`` (see ``SimulationClock`` and
docs/EMBODIMENT.md, "Timing").
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.embodiment.errors import InvalidTimestepError

EMBODIMENT_DISCLAIMER = (
    "Structural connectivity is biological data. Neural activity is simulated. "
    "Virtual sensing, motor mapping, body dynamics, and world physics are computational "
    "interpretations."
)
VIRTUAL_WORLD_LABEL = (
    "VIRTUAL WORLD — computational environment state; not a biological measurement"
)
COMPUTATIONAL_SENSOR_INPUT = (
    "COMPUTATIONAL SENSOR INPUT — virtual-world state converted into a neural stimulus; "
    "not a biological measurement"
)
COMPUTATIONAL_MOTOR_MAPPING = (
    "COMPUTATIONAL MOTOR MAPPING — decoded simulated neural output converted into a body "
    "command; not observed behaviour"
)
SIMPLIFIED_COMPUTATIONAL_BODY = (
    "SIMPLIFIED COMPUTATIONAL BODY — virtual-body movement is not claimed to reproduce real "
    "Drosophila biomechanics"
)
COMPUTATIONAL_PARAMETERS = "COMPUTATIONAL PARAMETERS — not biological measurements"

Finite = Annotated[float, Field(allow_inf_nan=False)]
NonNegative = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
Unit = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def validate_dt(dt: float) -> float:
    """Return ``dt`` if it is a positive finite number; raise :class:`InvalidTimestepError`."""
    if isinstance(dt, bool) or not isinstance(dt, int | float):
        raise InvalidTimestepError(f"dt must be a number, got {dt!r}")
    if not math.isfinite(dt) or dt <= 0:
        raise InvalidTimestepError(f"dt must be a positive finite number, got {dt!r}")
    return float(dt)


# ----------------------------------------------------------------------------- geometry
class Vector3(Frozen):
    """A finite 3-vector in dimensionless world units."""

    x: Finite = 0.0
    y: Finite = 0.0
    z: Finite = 0.0

    def add(self, other: Vector3) -> Vector3:
        return Vector3(x=self.x + other.x, y=self.y + other.y, z=self.z + other.z)

    def sub(self, other: Vector3) -> Vector3:
        return Vector3(x=self.x - other.x, y=self.y - other.y, z=self.z - other.z)

    def scale(self, factor: float) -> Vector3:
        return Vector3(x=self.x * factor, y=self.y * factor, z=self.z * factor)

    def norm(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def distance_to(self, other: Vector3) -> float:
        return self.sub(other).norm()


# ----------------------------------------------------------------------------- world
class WorldObject(Frozen):
    object_id: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    position: Vector3
    velocity: Vector3 = Field(default_factory=Vector3)
    #: characteristic radius in world units (computational, not a biological measurement)
    size: NonNegative = 0.0
    properties: dict[str, float | int | str | bool] = Field(default_factory=dict)


class WorldState(Frozen):
    label: str = VIRTUAL_WORLD_LABEL
    simulation_time: NonNegative
    step_index: int = Field(ge=0)
    objects: list[WorldObject] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _unique_ids(self) -> WorldState:
        ids = [o.object_id for o in self.objects]
        if len(ids) != len(set(ids)):
            raise ValueError("world object ids must be unique")
        return self

    def get(self, object_id: str) -> WorldObject | None:
        return next((o for o in self.objects if o.object_id == object_id), None)

    def of_type(self, object_type: str) -> list[WorldObject]:
        return [o for o in self.objects if o.object_type == object_type]


# ----------------------------------------------------------------------------- body
class BodyState(Frozen):
    """Pose of the virtual body. Only a ``BodyAdapter`` produces new instances."""

    label: str = SIMPLIFIED_COMPUTATIONAL_BODY
    position: Vector3
    #: heading angle in radians in the x-y plane (0 = +x, counter-clockwise positive)
    heading: Finite
    linear_velocity: Vector3 = Field(default_factory=Vector3)
    grounded: bool = True
    simulation_time: NonNegative
    step_index: int = Field(ge=0)

    @property
    def heading_vector(self) -> Vector3:
        return Vector3(x=math.cos(self.heading), y=math.sin(self.heading), z=0.0)


# ----------------------------------------------------------------------------- sensing
class SensoryObservation(Frozen):
    """Generic observation envelope. Produced by a ``SensorAdapter`` from virtual state."""

    sensor_type: str = Field(min_length=1)
    simulation_time: NonNegative
    step_index: int = Field(ge=0)
    #: which adapter / world object produced the observation
    source: str = Field(min_length=1)
    values: dict[str, Finite] = Field(default_factory=dict)
    interpretation_label: Literal[
        "COMPUTATIONAL SENSOR INPUT — virtual-world state converted into a neural stimulus; "
        "not a biological measurement"
    ] = COMPUTATIONAL_SENSOR_INPUT
    metadata: dict[str, float | int | str | bool] = Field(default_factory=dict)


# ----------------------------------------------------------------------------- motor
class MotorCommandType(StrEnum):
    """Command vocabulary available in P7.0.

    Only IDLE and ESCAPE exist because the escape_v1 decoder exposes NO_ACTION / ESCAPE and the
    giant fiber is azimuth-invariant (no direction is decoded). Names reserved for later
    phases — FORWARD, TURN_LEFT, TURN_RIGHT, JUMP — are deliberately NOT members yet
    (see ``RESERVED_FUTURE_COMMANDS``).
    """

    IDLE = "IDLE"
    ESCAPE = "ESCAPE"


RESERVED_FUTURE_COMMANDS: tuple[str, ...] = ("FORWARD", "TURN_LEFT", "TURN_RIGHT", "JUMP")


class MotorCommand(Frozen):
    command: MotorCommandType
    #: 0..1 command strength (computational; 0 for IDLE)
    magnitude: Unit = 0.0
    #: the decoded FlyBrain action this command was translated from (e.g. "ESCAPE")
    source_action: str = Field(min_length=1)
    simulation_time: NonNegative
    step_index: int = Field(ge=0)
    label: str = COMPUTATIONAL_MOTOR_MAPPING
    metadata: dict[str, float | int | str | bool] = Field(default_factory=dict)


# ----------------------------------------------------------------------------- timing
class SimulationClock(Frozen):
    """Explicit loop timing: ``dt`` seconds of computational time per loop step."""

    dt: Positive
    step_index: int = Field(ge=0, default=0)
    simulation_time: NonNegative = 0.0

    @field_validator("dt", mode="before")
    @classmethod
    def _strict_dt(cls, value: object) -> float:
        return validate_dt(value)  # type: ignore[arg-type]

    def advance(self) -> SimulationClock:
        return SimulationClock(
            dt=self.dt,
            step_index=self.step_index + 1,
            simulation_time=self.simulation_time + self.dt,
        )


class TimingInfo(Frozen):
    """Records the (possibly different) time bases of the loop and the neural simulation."""

    loop_dt: Positive
    neural_dt: Positive
    neural_steps_per_loop_step: int = Field(ge=1)
    note: str = (
        "P7.0 uses one common deterministic loop timestep for the world and the body; each "
        "loop step runs a fresh neural experiment of neural_steps_per_loop_step model steps "
        "(neural dt = SimulationConfig.dt, a dimensionless model unit). The two time bases are "
        "recorded separately and are not claimed to be physically related."
    )


# ----------------------------------------------------------------------------- configs
class LoopConfig(Frozen):
    label: str = "COMPUTATIONAL LOOP PARAMETERS — not biological timing"
    dt: Positive = 0.1

    @field_validator("dt", mode="before")
    @classmethod
    def _strict_dt(cls, value: object) -> float:
        return validate_dt(value)  # type: ignore[arg-type]

    max_steps: int = Field(default=1000, ge=1)
    #: neural model steps per loop step (None → the escape config's simulation_steps)
    brain_steps_per_loop_step: int | None = Field(default=None, ge=1)
    #: keep the full EscapeResult (large) in every step record
    keep_full_brain_results: bool = False
    #: loop-level seed, recorded for reproducibility (SimpleWorld / SimpleBody are
    #: deterministic and do not draw random numbers; the neural seed lives in SimulationConfig)
    random_seed: int = 0


class SimpleWorldConfig(Frozen):
    label: str = (
        "COMPUTATIONAL WORLD PARAMETERS — dimensionless world units, not biological measurements"
    )
    looming_object: bool = True
    object_id: str = "looming_1"
    object_type: str = "looming_object"
    #: initial distance from the world origin, along the approach direction
    start_distance: Positive = 20.0
    #: approach speed towards the origin, world units per second of loop time
    approach_speed: NonNegative = 10.0
    #: object radius in world units
    object_size: Positive = 1.0
    #: azimuth of the approach direction in degrees (0 = +x, counter-clockwise positive)
    azimuth_deg: Finite = 0.0
    height: Finite = 0.0


class VirtualLoomingSensorConfig(Frozen):
    label: str = "COMPUTATIONAL SENSOR PARAMETERS — angular-size rule, not a retinal model"
    object_type: str = "looming_object"
    #: angular size (radians) at which the stimulus intensity saturates at 1.0
    saturation_angle_rad: Positive = math.pi / 2
    #: |bearing| below this (radians) is reported as "center"
    center_half_angle_rad: NonNegative = math.radians(20.0)
    #: objects with |bearing| above half of this (radians) are not visible
    field_of_view_rad: Positive = math.pi


class EscapeMotorConfig(Frozen):
    label: str = "COMPUTATIONAL MOTOR PARAMETERS — NO_ACTION → IDLE, ESCAPE → ESCAPE; no direction"
    escape_magnitude: Unit = 1.0


class SimpleBodyConfig(Frozen):
    label: str = "COMPUTATIONAL BODY PARAMETERS — not biological measurements"
    initial_position: Vector3 = Field(default_factory=Vector3)
    initial_heading: Finite = 0.0
    #: horizontal speed along the body heading during an escape (world units / s)
    escape_speed: NonNegative = 5.0
    #: vertical speed at the start of an escape (world units / s)
    escape_vertical_speed: NonNegative = 3.0
    #: time (s) the body stays airborne after an escape command
    airborne_duration: NonNegative = 0.3
    #: fraction of horizontal velocity removed per second while grounded
    ground_drag: Unit = 1.0


# ----------------------------------------------------------------------------- records
class BrainStepSummary(Frozen):
    """Compact summary of one FlyBrain run inside a loop step (all activity SIMULATED)."""

    escape_config_version: str
    neural_steps: int = Field(ge=1)
    neural_dt: Positive
    action: str
    output_spike_count: int = Field(ge=0)
    first_output_fire_step: int | None = None
    #: which giant fiber(s) fired — metadata only, never used for direction
    fired_output_sides: list[str] = Field(default_factory=list)
    firing_events: int = Field(ge=0)
    neurons_activated: int = Field(ge=0)
    activity_label: str


class EmbodiedStepRecord(Frozen):
    step_index: int = Field(ge=0)
    simulation_time: NonNegative
    dt: Positive
    observation: SensoryObservation
    stimulus: dict[str, Any]
    brain: BrainStepSummary
    command: MotorCommand
    body_state: BodyState
    world_state: WorldState
    brain_result: dict[str, Any] | None = None


class EmbodimentProvenance(Frozen):
    disclaimer: str = EMBODIMENT_DISCLAIMER
    dataset: str
    dataset_version: str
    canonical_selection_rule: str
    circuit_id: str
    circuit_hash: str
    biological_status: str
    escape_config_version: str
    simulation_config: dict[str, Any]
    random_seed: int
    world_adapter: str
    world_config: dict[str, Any]
    sensor_adapter: str
    sensor_config: dict[str, Any]
    motor_adapter: str
    motor_config: dict[str, Any]
    body_adapter: str
    body_config: dict[str, Any]
    loop_config: LoopConfig
    timing: TimingInfo


class EmbodiedExperimentRecord(Frozen):
    label: str = "TECHNICAL EMBODIED EXPERIMENT — SIMPLIFIED COMPUTATIONAL BODY"
    created_at: str
    runner_version: str
    provenance: EmbodimentProvenance
    initial_world: WorldState
    initial_body: BodyState
    steps: list[EmbodiedStepRecord]
    summary: dict[str, Any]
    runtime_seconds: NonNegative
