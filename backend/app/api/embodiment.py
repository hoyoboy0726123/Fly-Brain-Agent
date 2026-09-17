"""Virtual Threat Lab API (P7.1): ``GET /embodiment/config``, ``POST /embodiment/run``.

A thin layer over the P7.0 ``EmbodiedAgentLoop``. Every timeline step is the P7.0
``EmbodiedStepRecord`` reshaped for replay; nothing is simulated, decoded or moved here.
The frontend renders these states — it never generates behaviour.

    Structural connectivity is biological data. Neural activity is simulated.
    Virtual sensing, motor mapping, body dynamics, and world physics are computational
    interpretations.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from app.api.escape import EscapeService, EscapeServiceError, _holder
from app.behavior import ActivityGroup, GroupEdge
from app.config import Settings, get_settings
from app.embodiment import (
    COMPUTATIONAL_MOTOR_MAPPING,
    COMPUTATIONAL_SENSOR_INPUT,
    EMBODIMENT_DISCLAIMER,
    SIMPLIFIED_COMPUTATIONAL_BODY,
    EmbodiedAgentLoop,
    EmbodiedStepRecord,
    EmbodimentError,
    EmbodimentProvenance,
    EscapeMotorAdapter,
    EscapeMotorConfig,
    LoopConfig,
    MotorCommand,
    SimpleBodyAdapter,
    SimpleBodyConfig,
    SimpleWorldAdapter,
    SimpleWorldConfig,
    TimingInfo,
    Vector3,
    VirtualLoomingSensor,
    VirtualLoomingSensorConfig,
)
from app.simulation.errors import SimulationError

router = APIRouter(tags=["embodiment"])

EXPERIMENT_NAME = "virtual_threat_lab_v1"
MAX_LOOP_STEPS = 200
WORLD_UNITS_NOTE = (
    "Positions, sizes and speeds are dimensionless computational world units; no physical "
    "unit (mm / cm / m) is claimed."
)

#: Labels the UI shows next to each panel (never weakened for presentation).
LABELS: dict[str, str] = {
    "world_physics": "COMPUTATIONAL",
    "virtual_sensing": "COMPUTATIONAL SENSOR INPUT",
    "neural_activity": "SIMULATED",
    "structural_connectivity": "BIOLOGICAL DATA",
    "body": "SIMPLIFIED COMPUTATIONAL BODY",
    "motor_mapping": "COMPUTATIONAL MOTOR MAPPING",
}


def _boundary(label: str, *scope: str) -> dict[str, str]:
    return {"label": label, "scope": " ".join(scope)}


SCIENTIFIC_BOUNDARIES: list[dict[str, str]] = [
    _boundary(
        "BIOLOGICAL DATA",
        "MaleCNS structural connectivity (neuron ids, cell types, edges, synapse counts).",
    ),
    _boundary(
        "SIMULATED",
        "Neural activity: membrane potential, firing, refractory state",
        "(simplified LIF-like model).",
    ),
    _boundary(
        "COMPUTATIONAL SENSOR INPUT",
        "Virtual looming mapping: angular size and bearing of a virtual object",
        "→ stimulus intensity and direction.",
    ),
    _boundary(
        "COMPUTATIONAL MOTOR MAPPING",
        "Decoded action → body command (NO_ACTION → IDLE, ESCAPE → ESCAPE;",
        "no direction decoded).",
    ),
    _boundary(
        "SIMPLIFIED COMPUTATIONAL BODY",
        "Body dynamics: a point body with a heading; not Drosophila biomechanics.",
    ),
    _boundary(
        "COMPUTATIONAL WORLD",
        "Virtual-world physics: a straight-line object in dimensionless units; no collisions.",
    ),
]


# ----------------------------------------------------------------------------- request / response
class WorldOverrides(BaseModel):
    """Application-level world parameters a user may change (never neural parameters)."""

    model_config = ConfigDict(extra="forbid")

    start_distance: float = Field(default=20.0, ge=1.0, le=100.0, allow_inf_nan=False)
    approach_speed: float = Field(default=10.0, ge=0.0, le=50.0, allow_inf_nan=False)
    azimuth_deg: float = Field(default=0.0, ge=-180.0, le=180.0, allow_inf_nan=False)


class ThreatLabRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment: Literal["virtual_threat_lab_v1"] = EXPERIMENT_NAME
    seed: int = Field(default=0, ge=0)
    max_steps: int = Field(default=30, ge=1, le=MAX_LOOP_STEPS)
    world: WorldOverrides = Field(default_factory=WorldOverrides)


class CircuitInfo(BaseModel):
    circuit_id: str
    circuit_hash: str
    dataset: str
    dataset_version: str
    canonical_selection_rule: str
    neurons: int
    edges: int
    biological_status: str
    research_document: str


class ThreatLabConfigResponse(BaseModel):
    experiment_name: str = EXPERIMENT_NAME
    disclaimer: str = EMBODIMENT_DISCLAIMER
    labels: dict[str, str] = Field(default_factory=lambda: dict(LABELS))
    scientific_boundaries: list[dict[str, str]] = Field(
        default_factory=lambda: list(SCIENTIFIC_BOUNDARIES)
    )
    units_note: str = WORLD_UNITS_NOTE
    world_config: SimpleWorldConfig
    sensor_config: VirtualLoomingSensorConfig
    body_config: SimpleBodyConfig
    motor_config: EscapeMotorConfig
    loop_config: LoopConfig
    timing: TimingInfo
    circuit: CircuitInfo
    dataset: str
    dataset_version: str
    escape_config_version: str
    groups: list[ActivityGroup]
    group_edges: list[GroupEdge]
    max_loop_steps: int = MAX_LOOP_STEPS
    run_request_limits: dict[str, Any]


class WorldObjectView(BaseModel):
    object_id: str
    object_type: str
    position: Vector3
    velocity: Vector3
    size: float


class WorldView(BaseModel):
    label: str = "COMPUTATIONAL WORLD"
    simulation_time: float
    step_index: int
    objects: list[WorldObjectView]


class BodyView(BaseModel):
    label: str = SIMPLIFIED_COMPUTATIONAL_BODY
    position: Vector3
    velocity: Vector3
    heading: float
    grounded: bool


class SensorView(BaseModel):
    label: str = COMPUTATIONAL_SENSOR_INPUT
    sensor_type: str
    source: str
    intensity: float
    direction: str
    distance: float | None = None
    bearing_rad: float | None = None
    angular_size_rad: float | None = None
    visible: bool


class BrainView(BaseModel):
    label: str = "SIMULATED NEURAL ACTIVITY"
    stimulus: dict[str, Any]
    neural_steps: int
    neural_dt: float
    group_fired_counts: dict[str, list[int]]
    group_peak_fired: dict[str, int]
    sensory_first_fire_step: int | None
    first_output_fire_step: int | None
    output_spike_count: int
    fired_output_sides: list[str]
    firing_events: int
    neurons_activated: int
    action: str
    activity_label: str


class MotorView(BaseModel):
    label: str = COMPUTATIONAL_MOTOR_MAPPING
    command: str
    magnitude: float
    source_action: str
    direction_decoded: bool = False


class ThreatLabStep(BaseModel):
    step_index: int
    simulation_time: float
    dt: float
    world: WorldView
    body: BodyView
    sensor: SensorView
    brain: BrainView
    motor: MotorView


class TimelineEventView(BaseModel):
    step_index: int
    kind: Literal["first_escape", "escape", "landed"]
    description: str


class ThreatLabOutcome(BaseModel):
    loop_steps: int
    actions: dict[str, int]
    commands: dict[str, int]
    first_escape_step: int | None
    escape_steps: list[int]
    final_action: str
    final_body_position: Vector3
    displacement: float
    final_grounded: bool
    events: list[TimelineEventView]


class ThreatLabRunResponse(BaseModel):
    experiment_id: str
    experiment_name: str = EXPERIMENT_NAME
    created_at: str
    disclaimer: str = EMBODIMENT_DISCLAIMER
    labels: dict[str, str] = Field(default_factory=lambda: dict(LABELS))
    units_note: str = WORLD_UNITS_NOTE
    request: ThreatLabRunRequest
    provenance: EmbodimentProvenance
    groups: list[ActivityGroup]
    initial_world: WorldView
    initial_body: BodyView
    timeline: list[ThreatLabStep]
    outcome: ThreatLabOutcome
    runtime_seconds: float


# ----------------------------------------------------------------------------- reshaping (no logic)
def _world_view(state) -> WorldView:
    return WorldView(
        simulation_time=state.simulation_time,
        step_index=state.step_index,
        objects=[
            WorldObjectView(
                object_id=o.object_id,
                object_type=o.object_type,
                position=o.position,
                velocity=o.velocity,
                size=o.size,
            )
            for o in state.objects
        ],
    )


def _body_view(state) -> BodyView:
    return BodyView(
        position=state.position,
        velocity=state.linear_velocity,
        heading=state.heading,
        grounded=state.grounded,
    )


def _motor_view(command: MotorCommand) -> MotorView:
    return MotorView(
        command=str(command.command),
        magnitude=command.magnitude,
        source_action=command.source_action,
        direction_decoded=bool(command.metadata.get("direction_decoded", False)),
    )


def _step_view(record: EmbodiedStepRecord, world_before, body_before) -> ThreatLabStep:
    """One replay step = the states the sensor observed + the brain/motor results.

    ``world_before`` / ``body_before`` are the states observed at this step (P7.0 loop steps
    1–3, ``step_index`` = number of loop advances so far, ``simulation_time`` = observation
    time); ``record.world_state`` / ``record.body_state`` are the states *after* the step and
    appear as the observed states of step ``N + 1``. The replay therefore shows the geometry
    the sensor actually saw, and a motor command's effect on the body one loop step later —
    exactly the P7.0 closed-loop order.
    """
    o = record.observation
    b = record.brain
    return ThreatLabStep(
        step_index=record.step_index,
        simulation_time=record.simulation_time,
        dt=record.dt,
        world=_world_view(world_before),
        body=_body_view(body_before),
        sensor=SensorView(
            sensor_type=o.sensor_type,
            source=o.source,
            intensity=o.values.get("intensity", 0.0),
            direction=str(o.metadata.get("direction", "center")),
            distance=o.values.get("distance"),
            bearing_rad=o.values.get("bearing_rad"),
            angular_size_rad=o.values.get("angular_size_rad"),
            visible=bool(o.values.get("visible", 0.0)),
        ),
        brain=BrainView(
            stimulus=record.stimulus,
            neural_steps=b.neural_steps,
            neural_dt=b.neural_dt,
            group_fired_counts=b.group_fired_counts,
            group_peak_fired={k: max(v) if v else 0 for k, v in b.group_fired_counts.items()},
            sensory_first_fire_step=b.sensory_first_fire_step,
            first_output_fire_step=b.first_output_fire_step,
            output_spike_count=b.output_spike_count,
            fired_output_sides=b.fired_output_sides,
            firing_events=b.firing_events,
            neurons_activated=b.neurons_activated,
            action=b.action,
            activity_label=b.activity_label,
        ),
        motor=_motor_view(record.command),
    )


# ----------------------------------------------------------------------------- service
class ThreatLabService:
    """Builds fresh P7.0 loops on top of the shared escape_v1 brain (EscapeService)."""

    def __init__(self, escape: EscapeService) -> None:
        self.escape = escape

    @staticmethod
    def default_config_response(escape: EscapeService, loop: LoopConfig) -> ThreatLabConfigResponse:
        circuit = escape.circuit
        cfg = escape.config
        sim = escape.experiment.simulation_config
        return ThreatLabConfigResponse(
            world_config=SimpleWorldConfig(),
            sensor_config=VirtualLoomingSensorConfig(),
            body_config=SimpleBodyConfig(),
            motor_config=EscapeMotorConfig(),
            loop_config=loop,
            timing=TimingInfo(
                loop_dt=loop.dt, neural_dt=sim.dt, neural_steps_per_loop_step=cfg.simulation_steps
            ),
            circuit=CircuitInfo(
                circuit_id=circuit.circuit_id,
                circuit_hash=escape.circuit_hash,
                dataset=circuit.dataset,
                dataset_version=circuit.dataset_version,
                canonical_selection_rule=circuit.canonical_graph.selection_rule,
                neurons=len(circuit.nodes),
                edges=len(circuit.edges),
                biological_status=cfg.biological_status,
                research_document=cfg.research_document,
            ),
            dataset=circuit.dataset,
            dataset_version=circuit.dataset_version,
            escape_config_version=cfg.config_version,
            groups=escape.experiment.groups,
            group_edges=escape.experiment.group_edges,
            run_request_limits={
                "seed": {"min": 0},
                "max_steps": {"min": 1, "max": MAX_LOOP_STEPS, "default": 30},
                "world.start_distance": {"min": 1.0, "max": 100.0, "default": 20.0},
                "world.approach_speed": {"min": 0.0, "max": 50.0, "default": 10.0},
                "world.azimuth_deg": {"min": -180.0, "max": 180.0, "default": 0.0},
                "neural_parameters": "not exposed (escape_v1 configuration is fixed)",
            },
        )

    def config_response(self) -> ThreatLabConfigResponse:
        return self.default_config_response(self.escape, LoopConfig())

    def run(self, request: ThreatLabRunRequest) -> ThreatLabRunResponse:
        started = datetime.now(UTC)
        world_config = SimpleWorldConfig(
            start_distance=request.world.start_distance,
            approach_speed=request.world.approach_speed,
            azimuth_deg=request.world.azimuth_deg,
        )
        loop = EmbodiedAgentLoop(
            world=SimpleWorldAdapter(world_config),
            sensor=VirtualLoomingSensor(),
            brain=self.escape.experiment,
            motor=EscapeMotorAdapter(),
            body=SimpleBodyAdapter(),
            config=LoopConfig(dt=0.1, max_steps=request.max_steps, random_seed=request.seed),
        )
        initial_world, initial_body = loop.reset()
        timeline: list[ThreatLabStep] = []
        world_before, body_before = initial_world, initial_body
        for _ in range(request.max_steps):
            record = loop.step()
            timeline.append(_step_view(record, world_before, body_before))
            world_before, body_before = record.world_state, record.body_state
        record_all = loop.record()
        summary = record_all.summary
        escape_steps = [s.step_index for s in timeline if s.motor.command == "ESCAPE"]
        events: list[TimelineEventView] = []
        if escape_steps:
            events.append(
                TimelineEventView(
                    step_index=escape_steps[0],
                    kind="first_escape",
                    description=(
                        "first ESCAPE command (decoded from simulated giant-fiber activity)"
                    ),
                )
            )
            events.extend(
                TimelineEventView(step_index=s, kind="escape", description="ESCAPE command")
                for s in escape_steps[1:]
            )
            landed = next(
                (
                    step.step_index
                    for previous, step in zip(timeline, timeline[1:], strict=False)
                    if not previous.body.grounded and step.body.grounded
                ),
                None,
            )
            if landed is not None:
                events.append(
                    TimelineEventView(
                        step_index=landed, kind="landed", description="body back on the ground"
                    )
                )
        return ThreatLabRunResponse(
            experiment_id=str(uuid.uuid4()),
            created_at=started.isoformat(timespec="seconds"),
            request=request,
            provenance=record_all.provenance,
            groups=self.escape.experiment.groups,
            initial_world=_world_view(initial_world),
            initial_body=_body_view(initial_body),
            timeline=timeline,
            outcome=ThreatLabOutcome(
                loop_steps=summary["loop_steps"],
                actions=summary["actions"],
                commands=summary["commands"],
                first_escape_step=summary["first_escape_step"],
                escape_steps=escape_steps,
                final_action=timeline[-1].brain.action,
                final_body_position=Vector3(**summary["final_body_position"]),
                displacement=summary["displacement"],
                final_grounded=summary["final_grounded"],
                events=events,
            ),
            runtime_seconds=record_all.runtime_seconds,
        )


def get_threat_lab(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> ThreatLabService:
    try:
        escape = _holder(request.app.state, settings).get()
    except EscapeServiceError as exc:
        raise exc.http() from exc
    return ThreatLabService(escape)


# ----------------------------------------------------------------------------- endpoints
@router.get(
    "/embodiment/config",
    response_model=ThreatLabConfigResponse,
    summary="Virtual Threat Lab configuration, labels and scientific boundaries",
    responses={503: {"description": "escape_v1 brain unavailable"}},
)
def get_embodiment_config(
    service: Annotated[ThreatLabService, Depends(get_threat_lab)],
) -> ThreatLabConfigResponse:
    return service.config_response()


@router.post(
    "/embodiment/run",
    response_model=ThreatLabRunResponse,
    summary="Run one deterministic closed-loop Virtual Threat Lab experiment (P7.0 loop)",
    responses={
        422: {"description": "invalid request"},
        500: {"description": "embodiment or simulation error (no partial timeline)"},
        503: {"description": "escape_v1 brain unavailable"},
        504: {"description": "run timed out"},
    },
)
async def post_embodiment_run(
    body: ThreatLabRunRequest,
    service: Annotated[ThreatLabService, Depends(get_threat_lab)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ThreatLabRunResponse:
    timeout = settings.escape_run_timeout_seconds * 3
    try:
        return await asyncio.wait_for(run_in_threadpool(service.run, body), timeout=timeout)
    except TimeoutError as exc:
        raise HTTPException(
            504, detail={"error": "timeout", "message": f"run exceeded {timeout:g}s"}
        ) from exc
    except SimulationError as exc:
        raise HTTPException(500, detail={"error": "simulation_error", "message": str(exc)}) from exc
    except EmbodimentError as exc:
        raise HTTPException(500, detail={"error": "embodiment_error", "message": str(exc)}) from exc


__all__ = [
    "EXPERIMENT_NAME",
    "LABELS",
    "MAX_LOOP_STEPS",
    "SCIENTIFIC_BOUNDARIES",
    "ThreatLabConfigResponse",
    "ThreatLabRunRequest",
    "ThreatLabRunResponse",
    "ThreatLabService",
    "router",
]
