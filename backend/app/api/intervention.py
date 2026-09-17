"""Neural Intervention Lab API (P7.2): ``GET /embodiment/intervention/config`` and
``POST /embodiment/intervention/compare``.

    Computational intervention suppresses simulated firing of selected neurons while
    preserving the biological structural connectivity.

The endpoint runs two P7.0 closed-loop trials through the P7.1 ``ThreatLabService`` under
identical conditions — CONTROL and one computational intervention — and reports
*descriptive* differences. Nothing here suppresses anything: the intervention is resolved
into an ``InterventionConfig`` and handed down to the simulation engine. No expected
outcome is encoded; whatever the model produces is returned as observed.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from app.api.embodiment import (
    EXPERIMENT_NAME,
    MAX_LOOP_STEPS,
    ThreatLabRunRequest,
    ThreatLabRunResponse,
    ThreatLabService,
    WorldOverrides,
    get_threat_lab,
)
from app.behavior import (
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
from app.config import Settings, get_settings
from app.embodiment import EMBODIMENT_DISCLAIMER, EmbodimentError
from app.simulation import (
    FUTURE_INTERVENTION_TYPES,
    INTERVENTION_DISCLAIMER,
    INTERVENTION_LABEL,
    INTERVENTION_LAYER,
    INTERVENTION_SEMANTICS,
    InterventionConfig,
)
from app.simulation.errors import SimulationError

router = APIRouter(tags=["intervention"])

COMPARISON_LABEL = "COMPUTATIONAL NEURAL INTERVENTION — A/B COMPARISON (descriptive only)"
COMPUTATIONAL_RESULT_LABEL = (
    "CURRENT COMPUTATIONAL RESULT — not a validation of the biological study"
)
#: cell types whose simulated firing totals are compared (GF = DNp01 in escape_v1)
COMPARED_CELL_TYPES: tuple[str, ...] = ("LC4", "LPLC2", "DNp01")
#: exact SUPPRESS_FIRING semantics (mirrors app/simulation/intervention.py)
SUPPRESSION_SEMANTICS: tuple[str, ...] = (
    "the neuron, its biological id, its edges and their synapse counts remain in the circuit",
    "synaptic and external input are still accumulated; the membrane still integrates and leaks",
    "when the membrane reaches threshold, fired is forced to False: no spike is recorded, no "
    "reset, no refractory period, no spike-driven propagation along its outgoing edges",
    "decoder, motor mapping, body and world are untouched; downstream effects emerge from "
    "the model",
)


# ----------------------------------------------------------------------------- request / response
class InterventionCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention: InterventionSelector
    seed: int = Field(default=0, ge=0)
    max_steps: int = Field(default=30, ge=1, le=MAX_LOOP_STEPS)
    world: WorldOverrides = Field(default_factory=WorldOverrides)


class SelectorInfo(BaseModel):
    selector: str
    label: str
    cell_types: list[str]
    resolved: ResolvedTargets


class InterventionConfigResponse(BaseModel):
    label: str = INTERVENTION_LABEL
    layer: str = INTERVENTION_LAYER
    semantics: str = INTERVENTION_SEMANTICS
    intervention_disclaimer: str = INTERVENTION_DISCLAIMER
    disclaimer: str = EMBODIMENT_DISCLAIMER
    implemented_types: list[str] = Field(default_factory=lambda: ["NONE", "SUPPRESS_FIRING"])
    future_types_not_implemented: list[str] = Field(
        default_factory=lambda: list(FUTURE_INTERVENTION_TYPES)
    )
    suppression_semantics: list[str]
    selectors: list[SelectorInfo]
    structural_signature: dict[str, Any]
    circuit_id: str
    dataset: str
    dataset_version: str
    biological_context: dict[str, Any] = Field(default_factory=lambda: dict(BIOLOGICAL_CONTEXT))
    computational_result_label: str = COMPUTATIONAL_RESULT_LABEL
    experiment_name: str = EXPERIMENT_NAME
    max_loop_steps: int = MAX_LOOP_STEPS


class TrialView(BaseModel):
    role: Literal["control", "intervention"]
    intervention_config: InterventionConfig
    resolved_targets: ResolvedTargets
    experiment: ThreatLabRunResponse
    structural_signature: dict[str, Any]
    #: SIMULATED spikes summed over all loop steps and neural steps, per compared cell type
    simulated_firing_totals: dict[str, int]
    suppressed_events: int
    runtime_seconds: float


class MatchedConditions(BaseModel):
    same_seed: bool
    same_world: bool
    same_initial_body: bool
    same_sensor_config: bool
    same_body_config: bool
    same_motor_config: bool
    same_simulation_config: bool
    same_circuit: bool
    same_dataset_version: bool
    same_timing: bool
    same_loop_config: bool
    same_decoder_and_mapping: bool
    all_matched: bool
    only_difference: str = "intervention_config"


class FiringDelta(BaseModel):
    control: int
    intervention: int
    delta: int


class Differences(BaseModel):
    label: str = COMPUTATIONAL_RESULT_LABEL
    control_first_escape_step: int | None
    intervention_first_escape_step: int | None
    first_escape_step_delta: int | None
    control_escape_occurred: bool
    intervention_escape_occurred: bool
    control_escape_steps: list[int]
    intervention_escape_steps: list[int]
    control_actions: dict[str, int]
    intervention_actions: dict[str, int]
    simulated_firing_totals: dict[str, FiringDelta]
    control_final_displacement: float
    intervention_final_displacement: float
    displacement_delta: float
    first_divergent_step: int | None
    summary: list[str]


class Synchronization(BaseModel):
    control_steps: int
    intervention_steps: int
    shared_steps: int
    cursor_max: int
    note: str = (
        "one replay cursor drives both trials; a step beyond a trial's timeline means that "
        "trial has ended (its last state must not be reused)"
    )


class StructuralIntegrity(BaseModel):
    before: dict[str, Any]
    after: dict[str, Any]
    unchanged: bool


class Comparison(BaseModel):
    matched_conditions: MatchedConditions
    differences: Differences
    synchronization: Synchronization
    structural_integrity: StructuralIntegrity


class InterventionCompareResponse(BaseModel):
    comparison_id: str
    created_at: str
    label: str = COMPARISON_LABEL
    disclaimer: str = EMBODIMENT_DISCLAIMER
    intervention_disclaimer: str = INTERVENTION_DISCLAIMER
    semantics: str = INTERVENTION_SEMANTICS
    layer: str = INTERVENTION_LAYER
    request: InterventionCompareRequest
    control: TrialView
    intervention: TrialView
    comparison: Comparison
    biological_context: dict[str, Any] = Field(default_factory=lambda: dict(BIOLOGICAL_CONTEXT))
    runtime: dict[str, float]


# ----------------------------------------------------------------------------- helpers
def firing_totals(experiment: ThreatLabRunResponse) -> dict[str, int]:
    totals = dict.fromkeys(COMPARED_CELL_TYPES, 0)
    for step in experiment.timeline:
        for key, counts in step.brain.group_fired_counts.items():
            cell_type = key.rsplit("_", 1)[0]
            if cell_type in totals:
                totals[cell_type] += int(sum(counts))
    return totals


def first_divergent_step(a: ThreatLabRunResponse, b: ThreatLabRunResponse) -> int | None:
    for sa, sb in zip(a.timeline, b.timeline, strict=False):
        if (
            sa.brain.action != sb.brain.action
            or sa.motor.command != sb.motor.command
            or sa.brain.group_fired_counts != sb.brain.group_fired_counts
        ):
            return sa.step_index
    return None


def matched_conditions(a: ThreatLabRunResponse, b: ThreatLabRunResponse) -> MatchedConditions:
    pa, pb = a.provenance, b.provenance
    values = {
        "same_seed": pa.random_seed == pb.random_seed == a.request.seed == b.request.seed,
        "same_world": pa.world_config == pb.world_config
        and a.initial_world == b.initial_world
        and a.request.world == b.request.world,
        "same_initial_body": a.initial_body == b.initial_body,
        "same_sensor_config": pa.sensor_config == pb.sensor_config
        and pa.sensor_adapter == pb.sensor_adapter,
        "same_body_config": pa.body_config == pb.body_config and pa.body_adapter == pb.body_adapter,
        "same_motor_config": pa.motor_config == pb.motor_config
        and pa.motor_adapter == pb.motor_adapter,
        "same_simulation_config": pa.simulation_config == pb.simulation_config,
        "same_circuit": pa.circuit_id == pb.circuit_id and pa.circuit_hash == pb.circuit_hash,
        "same_dataset_version": pa.dataset == pb.dataset
        and pa.dataset_version == pb.dataset_version,
        "same_timing": pa.timing == pb.timing,
        "same_loop_config": pa.loop_config == pb.loop_config
        and a.request.max_steps == b.request.max_steps,
        "same_decoder_and_mapping": pa.escape_config_version == pb.escape_config_version,
    }
    return MatchedConditions(**values, all_matched=all(values.values()))


def describe(control: TrialView, treated: TrialView, diff: dict[str, Any]) -> list[str]:
    target = treated.resolved_targets
    if not treated.intervention_config.is_active:
        return [
            "The intervention arm is CONTROL (no computational intervention): both trials ran "
            "the same model under the same conditions (A/A check).",
            "Descriptive comparison of one simulation; not a biological interpretation.",
        ]
    lines = [
        f"In the current computational model, suppressing simulated firing of "
        f"{target.neuron_count} {' + '.join(target.cell_types)} neuron(s) "
        + (
            "changed the first ESCAPE step from "
            f"{diff['control_first_escape_step']} to {diff['intervention_first_escape_step']}."
            if diff["control_first_escape_step"] != diff["intervention_first_escape_step"]
            else (
                f"left the first ESCAPE step unchanged ({diff['control_first_escape_step']})."
                if diff["control_first_escape_step"] is not None
                else "produced no ESCAPE in either trial."
            )
        )
    ]
    for cell_type, values in diff["simulated_firing_totals"].items():
        lines.append(
            f"Simulated {cell_type} spikes over the run: control {values['control']}, "
            f"intervention {values['intervention']} (delta {values['delta']:+d})."
        )
    lines.append(
        f"Final body displacement: control {diff['control_final_displacement']:.2f} units, "
        f"intervention {diff['intervention_final_displacement']:.2f} units."
    )
    lines.append(
        "Descriptive comparison of one simulation; not a biological interpretation and not a "
        "validation of the cited experiments."
    )
    return lines


# ----------------------------------------------------------------------------- service
class InterventionService:
    def __init__(self, lab: ThreatLabService) -> None:
        self.lab = lab

    @property
    def circuit(self):
        return self.lab.escape.circuit

    def config_response(self) -> InterventionConfigResponse:
        circuit = self.circuit
        selectors = [
            SelectorInfo(
                selector=selector,
                label=SELECTOR_LABELS[selector],
                cell_types=list(SELECTOR_CELL_TYPES[selector]),
                resolved=resolve_targets(circuit, selector),
            )
            for selector in INTERVENTION_SELECTORS
        ]
        return InterventionConfigResponse(
            suppression_semantics=list(SUPPRESSION_SEMANTICS),
            selectors=selectors,
            structural_signature=structural_signature(circuit),
            circuit_id=circuit.circuit_id,
            dataset=circuit.dataset,
            dataset_version=circuit.dataset_version,
        )

    def _trial(
        self,
        role: Literal["control", "intervention"],
        run_request: ThreatLabRunRequest,
        selector: str,
    ) -> TrialView:
        circuit = self.circuit
        config, resolved = build_intervention(circuit, selector)
        before = structural_signature(circuit)
        experiment = self.lab.run(run_request, intervention=config if config.is_active else None)
        after = structural_signature(circuit)
        if after != before:
            raise EmbodimentError("biological structure changed during a trial — aborting")
        return TrialView(
            role=role,
            intervention_config=config,
            resolved_targets=resolved,
            experiment=experiment,
            structural_signature=after,
            simulated_firing_totals=firing_totals(experiment),
            suppressed_events=sum(s.brain.suppressed_events for s in experiment.timeline),
            runtime_seconds=experiment.runtime_seconds,
        )

    def compare(self, request: InterventionCompareRequest) -> InterventionCompareResponse:
        started = datetime.now(UTC)
        run_request = ThreatLabRunRequest(
            seed=request.seed, max_steps=request.max_steps, world=request.world
        )
        signature_before = structural_signature(self.circuit)
        control = self._trial("control", run_request, "CONTROL")
        treated = self._trial("intervention", run_request, request.intervention)
        signature_after = structural_signature(self.circuit)
        matched = matched_conditions(control.experiment, treated.experiment)
        if not matched.all_matched:
            raise EmbodimentError(
                "control and intervention trials did not run under matched conditions: "
                + ", ".join(k for k, v in matched.model_dump().items() if v is False)
            )
        co, io = control.experiment.outcome, treated.experiment.outcome
        totals = {
            cell_type: FiringDelta(
                control=control.simulated_firing_totals[cell_type],
                intervention=treated.simulated_firing_totals[cell_type],
                delta=treated.simulated_firing_totals[cell_type]
                - control.simulated_firing_totals[cell_type],
            )
            for cell_type in COMPARED_CELL_TYPES
        }
        diff: dict[str, Any] = {
            "control_first_escape_step": co.first_escape_step,
            "intervention_first_escape_step": io.first_escape_step,
            "first_escape_step_delta": (
                io.first_escape_step - co.first_escape_step
                if co.first_escape_step is not None and io.first_escape_step is not None
                else None
            ),
            "control_escape_occurred": co.first_escape_step is not None,
            "intervention_escape_occurred": io.first_escape_step is not None,
            "control_escape_steps": co.escape_steps,
            "intervention_escape_steps": io.escape_steps,
            "control_actions": co.actions,
            "intervention_actions": io.actions,
            "simulated_firing_totals": {k: v.model_dump() for k, v in totals.items()},
            "control_final_displacement": co.displacement,
            "intervention_final_displacement": io.displacement,
            "displacement_delta": io.displacement - co.displacement,
            "first_divergent_step": first_divergent_step(control.experiment, treated.experiment),
        }
        differences = Differences(**diff, summary=describe(control, treated, diff))
        control_steps = len(control.experiment.timeline)
        treated_steps = len(treated.experiment.timeline)
        return InterventionCompareResponse(
            comparison_id=str(uuid.uuid4()),
            created_at=started.isoformat(timespec="seconds"),
            request=request,
            control=control,
            intervention=treated,
            comparison=Comparison(
                matched_conditions=matched,
                differences=differences,
                synchronization=Synchronization(
                    control_steps=control_steps,
                    intervention_steps=treated_steps,
                    shared_steps=min(control_steps, treated_steps),
                    cursor_max=max(control_steps, treated_steps) - 1,
                ),
                structural_integrity=StructuralIntegrity(
                    before=signature_before,
                    after=signature_after,
                    unchanged=signature_before == signature_after
                    and control.structural_signature
                    == treated.structural_signature
                    == signature_before,
                ),
            ),
            runtime={
                "control_seconds": control.runtime_seconds,
                "intervention_seconds": treated.runtime_seconds,
                "combined_seconds": round(control.runtime_seconds + treated.runtime_seconds, 6),
                "wall_seconds": round((datetime.now(UTC) - started).total_seconds(), 6),
            },
        )


def get_intervention_service(
    lab: Annotated[ThreatLabService, Depends(get_threat_lab)],
) -> InterventionService:
    return InterventionService(lab)


# ----------------------------------------------------------------------------- endpoints
@router.get(
    "/embodiment/intervention/config",
    response_model=InterventionConfigResponse,
    summary="Neural Intervention Lab: resolved selectors, semantics, disclaimers",
    responses={503: {"description": "escape_v1 brain unavailable"}},
)
def get_intervention_config(
    service: Annotated[InterventionService, Depends(get_intervention_service)],
) -> InterventionConfigResponse:
    try:
        return service.config_response()
    except TargetResolutionError as exc:
        raise HTTPException(
            503, detail={"error": "target_resolution_failed", "message": str(exc)}
        ) from exc


@router.post(
    "/embodiment/intervention/compare",
    response_model=InterventionCompareResponse,
    summary="Run CONTROL and one computational intervention under matched conditions (A/B)",
    responses={
        422: {"description": "invalid request (unknown selector, out-of-range parameter)"},
        500: {"description": "trial failed or conditions could not be matched (no comparison)"},
        503: {"description": "escape_v1 brain unavailable / targets unresolvable"},
        504: {"description": "comparison timed out"},
    },
)
async def post_intervention_compare(
    body: InterventionCompareRequest,
    service: Annotated[InterventionService, Depends(get_intervention_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterventionCompareResponse:
    timeout = settings.escape_run_timeout_seconds * 6
    try:
        return await asyncio.wait_for(run_in_threadpool(service.compare, body), timeout=timeout)
    except TimeoutError as exc:
        raise HTTPException(
            504, detail={"error": "timeout", "message": f"comparison exceeded {timeout:g}s"}
        ) from exc
    except TargetResolutionError as exc:
        raise HTTPException(
            503, detail={"error": "target_resolution_failed", "message": str(exc)}
        ) from exc
    except SimulationError as exc:
        raise HTTPException(500, detail={"error": "simulation_error", "message": str(exc)}) from exc
    except EmbodimentError as exc:
        raise HTTPException(500, detail={"error": "embodiment_error", "message": str(exc)}) from exc


__all__ = [
    "COMPARED_CELL_TYPES",
    "InterventionCompareRequest",
    "InterventionCompareResponse",
    "InterventionConfigResponse",
    "InterventionService",
    "router",
]
