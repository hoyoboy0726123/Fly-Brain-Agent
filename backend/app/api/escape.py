"""Escape demo API (P5): ``GET /escape/config``, ``POST /escape/run``, ``WS /ws/escape``.

A thin layer over the P4 ``EscapeExperiment``. No simulation, mapping or decoding logic
lives here: the handlers validate input, call the experiment and reshape its result for
the web demo. Every payload carries the P4 disclaimer.

Error contract (HTTP ``detail`` object and WebSocket ``error`` events share the codes):

- ``invalid_request``      422  body/stimulus fails validation (intensity outside 0..1, …)
- ``config_unavailable``   503  behaviour config missing or invalid
- ``circuit_unavailable``  503  circuit artifact missing (and no canonical graph to build it)
- ``circuit_mismatch``     503  artifact hash / id differs from the configured expectation
- ``simulation_error``     500  the P3 engine raised during the run
- ``timeout``              504  the run exceeded ``escape_run_timeout_seconds``
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.behavior import (
    DISCLAIMER,
    ActivityGroup,
    Citation,
    EscapeCircuitConfig,
    EscapeExperiment,
    EscapeResult,
    GroupActivity,
    GroupEdge,
    TimelineEvent,
    load_escape_circuit,
    load_escape_config,
)
from app.behavior.runner import CircuitReference, OutputActivity
from app.circuits import Circuit
from app.circuits.errors import ArtifactIntegrityError, CircuitExtractionError
from app.config import Settings, get_settings
from app.motor import Action, MotorDecision
from app.sensors import MAPPING_LABEL, LoomingStimulus
from app.sensors.looming import Direction
from app.simulation import ACTIVITY_LABEL, SimulationConfig
from app.simulation.errors import SimulationError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["escape"])

ErrorCode = Literal[
    "invalid_request",
    "config_unavailable",
    "circuit_unavailable",
    "circuit_mismatch",
    "simulation_error",
    "timeout",
]
GfActivity = Literal["None", "Left", "Right", "Both"]

#: Wording required by NEUROSCIENCE.md §3 / PRD; shown verbatim in the UI header.
SCIENTIFIC_LABELS: tuple[str, ...] = (
    "Structural connectivity: biological data",
    "Neural activity: simulated",
    "Behavior decoding: computational interpretation",
)

GF_ACTIVITY_BY_SIDES: dict[frozenset[str], GfActivity] = {
    frozenset(): "None",
    frozenset({"L"}): "Left",
    frozenset({"R"}): "Right",
    frozenset({"L", "R"}): "Both",
}


# ----------------------------------------------------------------------------- errors
class EscapeServiceError(Exception):
    """Raised when the escape demo cannot be served; maps 1:1 onto the error contract."""

    def __init__(self, code: ErrorCode, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.status_code = status_code

    def detail(self) -> dict[str, str]:
        return {"error": self.code, "message": str(self)}

    def http(self) -> HTTPException:
        return HTTPException(status_code=self.status_code, detail=self.detail())


# ----------------------------------------------------------------------------- schemas
class EscapeRunRequest(BaseModel):
    """Body of ``POST /escape/run`` (mirrors ``LoomingStimulus``; unknown fields rejected)."""

    model_config = ConfigDict(extra="forbid")

    stimulus: Literal["looming"] = "looming"
    direction: Direction
    intensity: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    #: optional override of the configured number of simulation steps
    steps: int | None = Field(default=None, ge=1)

    def to_stimulus(self) -> LoomingStimulus:
        return LoomingStimulus(
            stimulus=self.stimulus, direction=self.direction, intensity=self.intensity
        )


class EscapeSocketRequest(EscapeRunRequest):
    """WebSocket variant: ``pace_ms`` delays consecutive per-step events server-side."""

    pace_ms: int = Field(default=0, ge=0, le=2000)


class LayerDescription(BaseModel):
    layer: str
    kind: Literal["BIOLOGICAL STRUCTURE", "COMPUTATIONAL DYNAMICS", "APPLICATION DECODING"]
    modules: list[str]
    description: str


class EscapeConfigResponse(BaseModel):
    disclaimer: str = DISCLAIMER
    scientific_labels: list[str] = Field(default_factory=lambda: list(SCIENTIFIC_LABELS))
    config_version: str
    circuit_id: str
    circuit_hash: str
    expected_circuit_hash: str | None
    circuit_verified: bool
    biological_status: str
    research_document: str
    dataset: str
    dataset_version: str
    canonical_selection_rule: str
    circuit_neurons: int
    circuit_edges: int
    sensory_cell_types: list[str]
    output_cell_types: list[str]
    sensory_population_counts: dict[str, int]
    stimulated_sensory_counts: dict[str, int]
    excluded_sensory_counts: dict[str, int]
    exclusion_reason: str
    output_groups: dict[str, list[str]]
    groups: list[ActivityGroup]
    group_edges: list[GroupEdge]
    actions: list[str]
    decoder_rule: str
    mapping_rule: str
    mapping_label: str = MAPPING_LABEL
    mapping_gain: float
    stimulus_duration_steps: int
    simulation_steps: int
    max_steps: int
    simulation_config: SimulationConfig
    activity_label: str = ACTIVITY_LABEL
    layers: list[LayerDescription]
    mapping_confidence: dict[str, str]
    limitations: list[str]
    citations: list[Citation]


class SensoryActivity(BaseModel):
    """Stimulated group (APPLICATION INPUT) and its SIMULATED response."""

    label: str = ACTIVITY_LABEL
    stimulated_neuron_ids: list[str]
    stimulated_count: int
    stimulated_sides: list[str]
    injected_current: float
    duration_steps: int
    mapping_rule: str
    mapping_label: str = MAPPING_LABEL
    first_fire_step: int | None
    fired_count_at_first_step: int
    fired_counts_per_step: list[int]


class EscapeRunResponse(BaseModel):
    experiment_id: str
    created_at: str
    disclaimer: str = DISCLAIMER
    activity_label: str = ACTIVITY_LABEL
    config_version: str
    stimulus: LoomingStimulus
    circuit_id: str
    circuit_hash: str
    circuit: CircuitReference
    biological_status: str
    steps: int
    stimulus_duration_steps: int
    timeline: list[TimelineEvent]
    sensory_activity: SensoryActivity
    group_activity: GroupActivity
    per_step_fired_counts: list[int]
    firing_events: int
    neurons_activated: int
    output_activity: list[OutputActivity]
    #: which giant fiber(s) fired — metadata only, never an action
    gf_activity: GfActivity
    action: Action
    decision: MotorDecision
    simulation_config: SimulationConfig
    random_seed: int
    runtime_seconds: float


LAYERS: tuple[LayerDescription, ...] = (
    LayerDescription(
        layer="Structural connectivity",
        kind="BIOLOGICAL STRUCTURE",
        modules=["app.connectome", "app.circuits"],
        description=(
            "Neurons and synaptic connections come from the MaleCNS v1.0 connectome "
            '(canonical simulation graph, status == "Traced"). The escape circuit is a '
            "hash-sealed structural subgraph; no neuron, edge or synapse count is invented."
        ),
    ),
    LayerDescription(
        layer="Neural activity",
        kind="COMPUTATIONAL DYNAMICS",
        modules=["app.simulation"],
        description=(
            "Activity is produced by a simplified discrete-time LIF-like model with "
            "computational parameters (not measured MaleCNS parameters). Every spike shown "
            "in the demo is simulated, not recorded."
        ),
    ),
    LayerDescription(
        layer="Behavior decoding",
        kind="APPLICATION DECODING",
        modules=["app.sensors", "app.motor", "app.behavior"],
        description=(
            "The looming stimulus is mapped to injected current (intensity × gain) and the "
            "giant-fiber output is decoded into NO_ACTION or ESCAPE by a rule. These are "
            "computational interpretations, not observed behaviour."
        ),
    ),
)


# ----------------------------------------------------------------------------- service
class EscapeService:
    """Loaded config + verified circuit + P4 experiment, shared by REST and WebSocket."""

    def __init__(
        self, config: EscapeCircuitConfig, circuit: Circuit, experiment: EscapeExperiment
    ) -> None:
        self.config = config
        self.circuit = circuit
        self.experiment = experiment
        self.circuit_hash = circuit.provenance.circuit_hash or circuit.compute_hash()

    @classmethod
    def load(cls, settings: Settings) -> EscapeService:
        try:
            config = load_escape_config(settings.escape_config)
        except FileNotFoundError as exc:
            raise EscapeServiceError("config_unavailable", str(exc), 503) from exc
        except (ValidationError, ValueError) as exc:
            raise EscapeServiceError(
                "config_unavailable", f"invalid escape config: {exc}", 503
            ) from exc
        try:
            circuit = load_escape_circuit(
                config, settings.circuits_data_dir, settings.processed_data_dir
            )
        except FileNotFoundError as exc:
            raise EscapeServiceError("circuit_unavailable", str(exc), 503) from exc
        except ArtifactIntegrityError as exc:
            raise EscapeServiceError("circuit_mismatch", str(exc), 503) from exc
        except (CircuitExtractionError, ValidationError, ValueError, OSError) as exc:
            raise EscapeServiceError(
                "circuit_unavailable", f"could not load circuit: {exc}", 503
            ) from exc
        try:
            experiment = EscapeExperiment(config, circuit)
        except ArtifactIntegrityError as exc:
            raise EscapeServiceError("circuit_mismatch", str(exc), 503) from exc
        except (SimulationError, ValueError) as exc:
            raise EscapeServiceError("simulation_error", str(exc), 500) from exc
        return cls(config, circuit, experiment)

    # -- read side --------------------------------------------------------------
    def max_steps(self, settings: Settings) -> int:
        return min(settings.escape_max_steps, self.experiment.simulation_config.max_steps_per_run)

    def config_response(self, settings: Settings) -> EscapeConfigResponse:
        cfg = self.config
        population = cfg.sensory_population or cfg.sensory_groups
        return EscapeConfigResponse(
            config_version=cfg.config_version,
            circuit_id=self.circuit.circuit_id,
            circuit_hash=self.circuit_hash,
            expected_circuit_hash=cfg.expected_circuit_hash,
            circuit_verified=cfg.expected_circuit_hash in (None, self.circuit_hash),
            biological_status=cfg.biological_status,
            research_document=cfg.research_document,
            dataset=self.circuit.dataset,
            dataset_version=self.circuit.dataset_version,
            canonical_selection_rule=self.circuit.canonical_graph.selection_rule,
            circuit_neurons=len(self.circuit.nodes),
            circuit_edges=len(self.circuit.edges),
            sensory_cell_types=list(cfg.sensory_cell_types),
            output_cell_types=list(cfg.output_cell_types),
            sensory_population_counts={s: len(ids) for s, ids in population.items()},
            stimulated_sensory_counts={s: len(ids) for s, ids in cfg.sensory_groups.items()},
            excluded_sensory_counts={s: len(ids) for s, ids in cfg.excluded_sensory_ids.items()},
            exclusion_reason=cfg.exclusion_reason,
            output_groups={s: list(ids) for s, ids in cfg.output_groups.items()},
            groups=self.experiment.groups,
            group_edges=self.experiment.group_edges,
            actions=list(cfg.decoder.actions),
            decoder_rule=cfg.decoder.rule,
            mapping_rule=cfg.stimulus_mapping.rule,
            mapping_gain=cfg.stimulus_mapping.mapping_gain,
            stimulus_duration_steps=cfg.stimulus_mapping.duration_steps,
            simulation_steps=cfg.simulation_steps,
            max_steps=self.max_steps(settings),
            simulation_config=self.experiment.simulation_config,
            layers=list(LAYERS),
            mapping_confidence=dict(cfg.mapping_confidence),
            limitations=list(cfg.limitations),
            citations=list(cfg.citations),
        )

    # -- run side ---------------------------------------------------------------
    def run(self, request: EscapeRunRequest, settings: Settings) -> EscapeRunResponse:
        limit = self.max_steps(settings)
        if request.steps is not None and request.steps > limit:
            raise EscapeServiceError(
                "invalid_request", f"steps must be <= {limit} for this deployment", 422
            )
        try:
            result = self.experiment.run(request.to_stimulus(), steps=request.steps)
        except ArtifactIntegrityError as exc:
            raise EscapeServiceError("circuit_mismatch", str(exc), 503) from exc
        except SimulationError as exc:
            raise EscapeServiceError("simulation_error", str(exc), 500) from exc
        return build_run_response(result)


def build_run_response(result: EscapeResult) -> EscapeRunResponse:
    """Reshape a P4 ``EscapeResult`` for the web demo (no new computation)."""
    sensory_keys = [g.key for g in result.group_activity.groups if g.role == "sensory"]
    sensory_per_step = [
        sum(result.group_activity.fired_counts[key][i] for key in sensory_keys)
        for i in range(result.steps)
    ]
    t1 = next(e for e in result.timeline if e.tag == "t1_sensory_activation")
    drive = result.sensory_drive
    return EscapeRunResponse(
        experiment_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        config_version=result.config_version,
        stimulus=result.stimulus,
        circuit_id=result.circuit.circuit_id,
        circuit_hash=result.circuit.circuit_hash,
        circuit=result.circuit,
        biological_status=result.circuit.biological_status,
        steps=result.steps,
        stimulus_duration_steps=drive.duration_steps,
        timeline=result.timeline,
        sensory_activity=SensoryActivity(
            stimulated_neuron_ids=list(drive.neuron_ids),
            stimulated_count=len(drive.neuron_ids),
            stimulated_sides=list(drive.sides),
            injected_current=drive.injected_current,
            duration_steps=drive.duration_steps,
            mapping_rule=drive.mapping_rule,
            first_fire_step=t1.step,
            fired_count_at_first_step=t1.count,
            fired_counts_per_step=sensory_per_step,
        ),
        group_activity=result.group_activity,
        per_step_fired_counts=result.per_step_fired_counts,
        firing_events=result.firing_events,
        neurons_activated=result.neurons_activated,
        output_activity=result.output_activity,
        gf_activity=GF_ACTIVITY_BY_SIDES[frozenset(result.decision.fired_output_sides)],
        action=result.decision.action,
        decision=result.decision,
        simulation_config=result.simulation_config,
        random_seed=result.random_seed,
        runtime_seconds=result.runtime_seconds,
    )


class EscapeServiceHolder:
    """Lazily loads the service once; a failed load is retried on the next request."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._service: EscapeService | None = None

    def get(self) -> EscapeService:
        with self._lock:
            if self._service is None:
                self._service = EscapeService.load(self.settings)
            return self._service

    def warm_up(self) -> None:
        """Load at startup without failing the app; requests report the error instead."""
        try:
            service = self.get()
        except EscapeServiceError as exc:
            logger.warning("escape demo not available: [%s] %s", exc.code, exc)
            return
        logger.info(
            "escape demo ready: %s circuit=%s hash=%s… (%d neurons / %d edges) status=%s",
            service.config.config_version,
            service.circuit.circuit_id,
            service.circuit_hash[:12],
            len(service.circuit.nodes),
            len(service.circuit.edges),
            service.config.biological_status,
        )


def _holder(app_state: Any, settings: Settings) -> EscapeServiceHolder:
    holder = getattr(app_state, "escape", None)
    if holder is None:
        holder = app_state.escape = EscapeServiceHolder(settings)
    return holder


def get_escape_service(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> EscapeService:
    try:
        return _holder(request.app.state, settings).get()
    except EscapeServiceError as exc:
        raise exc.http() from exc


# ----------------------------------------------------------------------------- REST
@router.get(
    "/escape/config",
    response_model=EscapeConfigResponse,
    summary="Escape demo configuration (circuit, groups, parameters, disclaimer)",
    responses={503: {"description": "config or circuit unavailable / mismatch"}},
)
def get_escape_config(
    service: Annotated[EscapeService, Depends(get_escape_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EscapeConfigResponse:
    return service.config_response(settings)


@router.post(
    "/escape/run",
    response_model=EscapeRunResponse,
    summary="Run one looming → escape experiment (SIMULATED activity, decoded action)",
    responses={
        422: {"description": "invalid stimulus"},
        500: {"description": "simulation error"},
        503: {"description": "config or circuit unavailable / mismatch"},
        504: {"description": "run timed out"},
    },
)
async def post_escape_run(
    body: EscapeRunRequest,
    service: Annotated[EscapeService, Depends(get_escape_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EscapeRunResponse:
    try:
        return await asyncio.wait_for(
            run_in_threadpool(service.run, body, settings),
            timeout=settings.escape_run_timeout_seconds,
        )
    except TimeoutError as exc:
        raise EscapeServiceError(
            "timeout", f"run exceeded {settings.escape_run_timeout_seconds:g}s", 504
        ).http() from exc
    except EscapeServiceError as exc:
        raise exc.http() from exc


# ----------------------------------------------------------------------------- WebSocket
SocketEvent = Literal[
    "stimulus_started",
    "sensory_activation",
    "neural_activity",
    "output_activation",
    "action_decoded",
    "experiment_finished",
    "error",
]


def socket_events(result: EscapeRunResponse) -> list[dict[str, Any]]:
    """The event sequence for one finished run, in replay order.

    Per-step ``neural_activity`` events carry the SIMULATED per-group spike counts of that
    step; ``sensory_activation`` / ``output_activation`` follow the step at which the
    first sensory / output spike occurred (from the P4 timeline, not recomputed).
    """
    t1 = next(e for e in result.timeline if e.tag == "t1_sensory_activation")
    t3 = next(e for e in result.timeline if e.tag == "t3_output_activation")
    base = {"experiment_id": result.experiment_id, "activity_label": ACTIVITY_LABEL}
    events: list[dict[str, Any]] = [
        {
            "event": "stimulus_started",
            **base,
            "stimulus": result.stimulus.model_dump(mode="json"),
            "steps": result.steps,
            "stimulus_duration_steps": result.stimulus_duration_steps,
            "stimulated_count": result.sensory_activity.stimulated_count,
            "stimulated_sides": result.sensory_activity.stimulated_sides,
            "injected_current": result.sensory_activity.injected_current,
            "groups": [g.model_dump(mode="json") for g in result.group_activity.groups],
            "disclaimer": result.disclaimer,
        }
    ]
    fired_counts = result.group_activity.fired_counts
    for index in range(result.steps):
        step = index + 1
        events.append(
            {
                "event": "neural_activity",
                **base,
                "step": step,
                "stimulus_active": step <= result.stimulus_duration_steps,
                "fired_total": result.per_step_fired_counts[index],
                "fired_by_group": {key: counts[index] for key, counts in fired_counts.items()},
            }
        )
        if t1.step == step:
            events.append(
                {
                    "event": "sensory_activation",
                    **base,
                    "step": step,
                    "count": t1.count,
                    "sides": result.sensory_activity.stimulated_sides,
                    "description": t1.description,
                }
            )
        if t3.step == step:
            events.append(
                {
                    "event": "output_activation",
                    **base,
                    "step": step,
                    "neuron_ids": t3.neuron_ids,
                    "sides": result.decision.fired_output_sides,
                    "description": t3.description,
                }
            )
    events.append(
        {
            "event": "action_decoded",
            **base,
            "action": result.action.value,
            "gf_activity": result.gf_activity,
            "rule": result.decision.rule,
            "output_spike_count": result.decision.output_spike_count,
            "first_output_fire_step": result.decision.first_output_fire_step,
            "label": result.decision.label,
        }
    )
    events.append(
        {"event": "experiment_finished", **base, "result": result.model_dump(mode="json")}
    )
    return events


async def _send_error(websocket: WebSocket, code: str, message: str) -> None:
    await websocket.send_json({"event": "error", "error": code, "message": message})


@router.websocket("/ws/escape")
async def escape_socket(websocket: WebSocket) -> None:
    """Send ``{"stimulus":"looming","direction":..,"intensity":..}``; receive the event stream.

    The connection stays open so the client can trigger several experiments. Invalid input
    yields an ``error`` event and keeps the connection; the client decides what to do.
    """
    await websocket.accept()
    settings = get_settings()
    override = websocket.app.dependency_overrides.get(get_settings)
    if override is not None:
        settings = override()
    holder = _holder(websocket.app.state, settings)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                request = EscapeSocketRequest.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                await _send_error(websocket, "invalid_request", str(exc))
                continue
            try:
                service = holder.get()
                result = await asyncio.wait_for(
                    run_in_threadpool(service.run, request, settings),
                    timeout=settings.escape_run_timeout_seconds,
                )
            except EscapeServiceError as exc:
                await _send_error(websocket, exc.code, str(exc))
                continue
            except TimeoutError:
                await _send_error(
                    websocket, "timeout", f"run exceeded {settings.escape_run_timeout_seconds:g}s"
                )
                continue
            pace = request.pace_ms / 1000.0
            for event in socket_events(result):
                await websocket.send_json(event)
                if pace and event["event"] == "neural_activity":
                    await asyncio.sleep(pace)
    except WebSocketDisconnect:
        return


__all__ = [
    "SCIENTIFIC_LABELS",
    "EscapeConfigResponse",
    "EscapeRunRequest",
    "EscapeRunResponse",
    "EscapeService",
    "EscapeServiceError",
    "EscapeServiceHolder",
    "build_run_response",
    "get_escape_service",
    "router",
    "socket_events",
]
