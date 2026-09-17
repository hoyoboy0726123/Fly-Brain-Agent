"""Serializable simulation state and snapshot models (SIMULATED activity, never measured).

Snapshots reference the circuit artifact (``circuit_id`` / ``circuit_hash``); biological
provenance stays in the circuit artifact and is not copied here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.simulation.config import SimulationConfig
from app.simulation.intervention import InterventionConfig

ACTIVITY_LABEL = (
    "SIMULATED neural activity (simplified LIF-like model); not measured biological activity"
)
SNAPSHOT_LABEL = (
    "SIMULATION SNAPSHOT — simulated state only; biological structure and provenance live in "
    "the referenced circuit artifact"
)


class NeuronState(BaseModel):
    neuron_id: str
    membrane_potential: float
    threshold: float
    reset_potential: float
    leak: float
    refractory_remaining: int = Field(ge=0)
    fired: bool
    #: dataset-provided prediction carried as metadata; it does NOT influence the dynamics
    neurotransmitter_prediction: str | None = None
    #: P7.2: simulated firing of this neuron is suppressed by a computational intervention
    suppressed: bool = False


class StimulusRecord(BaseModel):
    """A generic input injection (no sensory or behavioural meaning)."""

    neuron_ids: list[str] = Field(min_length=1)
    intensity: float = Field(ge=0, allow_inf_nan=False)
    start_step: int = Field(ge=0)
    duration_steps: int = Field(ge=1)

    @property
    def end_step(self) -> int:
        """Exclusive end: the stimulus is applied for steps start_step <= step < end_step."""
        return self.start_step + self.duration_steps

    def is_active(self, step: int) -> bool:
        return self.start_step <= step < self.end_step


class SimulationState(BaseModel):
    label: Literal[
        "SIMULATED neural activity (simplified LIF-like model); not measured biological activity"
    ] = ACTIVITY_LABEL
    step: int = Field(ge=0)
    simulation_time: float
    sign_mode: str
    neurons: list[NeuronState]
    fired_neuron_ids: list[str]


class StepSummary(BaseModel):
    step: int
    simulation_time: float
    fired_count: int
    fired_neuron_ids: list[str]
    max_membrane_potential: float
    external_input_neurons: int
    #: P7.2: neurons whose simulated threshold crossing was suppressed by an intervention
    suppressed_count: int = 0
    suppressed_neuron_ids: list[str] = Field(default_factory=list)


class RunSummary(BaseModel):
    start_step: int
    end_step: int
    steps_run: int
    firing_events: int
    neurons_activated: int
    activated_neuron_ids: list[str]
    first_fire_step: dict[str, int]
    per_step_fired_counts: list[int]
    runtime_seconds: float
    mean_step_seconds: float
    #: P7.2: total suppressed threshold crossings during the run (0 without intervention)
    suppressed_events: int = 0


class SimulationSnapshot(BaseModel):
    label: Literal[
        "SIMULATION SNAPSHOT — simulated state only; biological structure and provenance live in "
        "the referenced circuit artifact"
    ] = SNAPSHOT_LABEL
    simulation_id: str
    circuit_id: str
    circuit_hash: str
    dataset: str
    dataset_version: str
    simulation_config: SimulationConfig
    random_seed: int
    current_step: int
    simulation_time: float
    stimuli: list[StimulusRecord]
    neuron_states: list[NeuronState]
    firing_events_total: int
    #: P7.2: intervention active in the engine (None / NONE = control)
    intervention: InterventionConfig | None = None
    rng_state: dict[str, Any] | None = None
    created_at: str

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=2) + "\n")
        return path

    @classmethod
    def load(cls, path: Path) -> SimulationSnapshot:
        return cls.model_validate_json(Path(path).read_text())
