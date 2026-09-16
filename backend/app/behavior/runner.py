"""End-to-end runner: LoomingStimulus → StimulusMapper → P3 SimulationEngine → MotorDecoder.

Every activity value in the result is SIMULATED. Biological provenance is referenced
through the circuit artifact (``circuit_id`` / ``circuit_hash``), never restated as fact.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app import __version__
from app.behavior.escape_config import EscapeCircuitConfig
from app.circuits import Circuit, CircuitExtractor, ConnectivityGraph
from app.circuits.errors import ArtifactIntegrityError
from app.motor import MotorDecision, MotorDecoder
from app.sensors import LoomingStimulus, SensoryDrive, StimulusMapper
from app.simulation import ACTIVITY_LABEL, SimulationConfig, SimulationEngine

DISCLAIMER = (
    "STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED. "
    "STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS."
)

EventTag = Literal[
    "t0_stimulus",
    "t1_sensory_activation",
    "t2_intermediate_activity",
    "t3_output_activation",
    "t4_decoded_action",
]


class TimelineEvent(BaseModel):
    tag: EventTag
    step: int | None
    label: str
    description: str
    neuron_ids: list[str] = Field(default_factory=list)
    count: int = 0


class CircuitReference(BaseModel):
    circuit_id: str
    circuit_hash: str
    dataset: str
    dataset_version: str
    canonical_selection_rule: str
    neurons: int
    edges: int
    biological_status: str
    research_document: str


class OutputActivity(BaseModel):
    neuron_id: str
    side: str
    spike_count: int
    fire_steps: list[int]
    label: str = ACTIVITY_LABEL


class EscapeResult(BaseModel):
    disclaimer: Literal[
        "STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED. "
        "STIMULUS MAPPING AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS."
    ] = DISCLAIMER
    config_version: str
    created_at: str
    runner_version: str
    stimulus: LoomingStimulus
    sensory_drive: SensoryDrive
    circuit: CircuitReference
    simulation_config: SimulationConfig
    random_seed: int
    steps: int
    firing_events: int
    neurons_activated: int
    per_step_fired_counts: list[int]
    activity_label: str = ACTIVITY_LABEL
    output_activity: list[OutputActivity]
    decision: MotorDecision
    timeline: list[TimelineEvent]
    runtime_seconds: float


class EscapeExperiment:
    """Runs one configured behaviour pipeline on one circuit artifact."""

    def __init__(
        self,
        config: EscapeCircuitConfig,
        circuit: Circuit,
        simulation_config: SimulationConfig | None = None,
    ) -> None:
        self.config = config
        self.circuit = circuit
        circuit_hash = circuit.provenance.circuit_hash or circuit.compute_hash()
        if circuit.circuit_id != config.circuit_id:
            raise ArtifactIntegrityError(
                f"circuit {circuit.circuit_id} does not match config circuit_id {config.circuit_id}"
            )
        if config.expected_circuit_hash and config.expected_circuit_hash != circuit_hash:
            raise ArtifactIntegrityError(
                f"circuit hash {circuit_hash[:12]}… differs from the configured "
                f"expected_circuit_hash {config.expected_circuit_hash[:12]}…"
            )
        node_ids = {node.neuron_id for node in circuit.nodes}
        missing = [
            nid for nid in config.all_sensory_ids() + config.all_output_ids() if nid not in node_ids
        ]
        if missing:
            raise ArtifactIntegrityError(
                f"{len(missing)} configured neuron id(s) are not in the circuit, e.g. {missing[:5]}"
            )
        self.simulation_config = simulation_config or SimulationConfig(
            **config.simulation_config_overrides
        )
        self.mapper = StimulusMapper(
            config.sensory_groups,
            mapping_gain=config.stimulus_mapping.mapping_gain,
            duration_steps=config.stimulus_mapping.duration_steps,
        )
        self.decoder = MotorDecoder(
            config.output_groups, min_output_spikes=config.decoder.min_output_spikes
        )
        self.sensory_ids = set(config.all_sensory_ids())
        self.output_side = {nid: side for side, ids in config.output_groups.items() for nid in ids}

    def run(self, stimulus: LoomingStimulus, steps: int | None = None) -> EscapeResult:
        started = time.perf_counter()
        steps = steps or self.config.simulation_steps
        drive = self.mapper.map(stimulus)
        engine = SimulationEngine(self.circuit, self.simulation_config)
        engine.stimulate(drive.neuron_ids, drive.injected_current, drive.duration_steps)
        summary = engine.run(steps)
        activity = engine.get_activity()
        decision = self.decoder.decode(activity)
        spikes_per_step: list[list[str]] = activity["spikes_per_step"]

        # --- timeline ---
        first_sensory = _first_step(spikes_per_step, self.sensory_ids)
        intermediate_steps = [
            (i + 1, [n for n in fired if n not in self.sensory_ids and n not in self.output_side])
            for i, fired in enumerate(spikes_per_step)
        ]
        intermediate_steps = [(s, ids) for s, ids in intermediate_steps if ids]
        first_output = _first_step(spikes_per_step, set(self.output_side))
        intermediate_events = sum(len(ids) for _, ids in intermediate_steps)
        timeline = [
            TimelineEvent(
                tag="t0_stimulus",
                step=0,
                label="APPLICATION INPUT",
                description=(
                    f"looming stimulus direction={stimulus.direction} "
                    f"intensity={stimulus.intensity} → {drive.mapping_rule}"
                ),
                neuron_ids=drive.neuron_ids,
                count=len(drive.neuron_ids),
            ),
            TimelineEvent(
                tag="t1_sensory_activation",
                step=first_sensory[0],
                label=ACTIVITY_LABEL,
                description="first simulated spike(s) in the sensory group"
                if first_sensory[0]
                else "no sensory neuron fired",
                neuron_ids=first_sensory[1],
                count=len(first_sensory[1]),
            ),
            TimelineEvent(
                tag="t2_intermediate_activity",
                step=intermediate_steps[0][0] if intermediate_steps else None,
                label=ACTIVITY_LABEL,
                description=(
                    f"simulated spikes in {intermediate_events} intermediate neuron-events "
                    f"over {len(intermediate_steps)} step(s)"
                    if intermediate_steps
                    else "no intermediate neuron fired (monosynaptic sensory→output pathway)"
                ),
                neuron_ids=intermediate_steps[0][1][:20] if intermediate_steps else [],
                count=sum(len(ids) for _, ids in intermediate_steps),
            ),
            TimelineEvent(
                tag="t3_output_activation",
                step=first_output[0],
                label=ACTIVITY_LABEL,
                description="first simulated spike(s) in the output group"
                if first_output[0]
                else "no output neuron fired",
                neuron_ids=first_output[1],
                count=decision.output_spike_count,
            ),
            TimelineEvent(
                tag="t4_decoded_action",
                step=steps,
                label="APPLICATION DECODING",
                description=f"{decision.action.value}: {decision.rule}",
                neuron_ids=decision.fired_output_neuron_ids,
                count=decision.output_spike_count,
            ),
        ]
        output_activity = [
            OutputActivity(
                neuron_id=nid,
                side=side,
                spike_count=sum(1 for fired in spikes_per_step if nid in fired),
                fire_steps=[i + 1 for i, fired in enumerate(spikes_per_step) if nid in fired],
            )
            for nid, side in sorted(self.output_side.items())
        ]
        return EscapeResult(
            config_version=self.config.config_version,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            runner_version=__version__,
            stimulus=stimulus,
            sensory_drive=drive,
            circuit=CircuitReference(
                circuit_id=self.circuit.circuit_id,
                circuit_hash=engine.circuit_hash,
                dataset=self.circuit.dataset,
                dataset_version=self.circuit.dataset_version,
                canonical_selection_rule=self.circuit.canonical_graph.selection_rule,
                neurons=engine.num_neurons,
                edges=engine.num_edges,
                biological_status=self.config.biological_status,
                research_document=self.config.research_document,
            ),
            simulation_config=self.simulation_config,
            random_seed=self.simulation_config.random_seed,
            steps=steps,
            firing_events=summary.firing_events,
            neurons_activated=summary.neurons_activated,
            per_step_fired_counts=summary.per_step_fired_counts,
            output_activity=output_activity,
            decision=decision,
            timeline=timeline,
            runtime_seconds=round(time.perf_counter() - started, 6),
        )


def load_escape_circuit(
    config: EscapeCircuitConfig,
    circuits_dir: Path,
    processed_dir: Path | None = None,
    *,
    save_if_extracted: bool = True,
) -> Circuit:
    """Load ``<circuits_dir>/<circuit_id>.json``, else extract it with P2 from the canonical graph.

    Extraction requires ``processed_dir`` with the normalized tables.
    """
    path = Path(circuits_dir) / f"{config.circuit_id}.json"
    if path.is_file():
        return Circuit.load(path)
    if processed_dir is None or not (Path(processed_dir) / "neurons.parquet").is_file():
        raise FileNotFoundError(
            f"{path} not found and no canonical graph available to extract it from"
        )
    graph = ConnectivityGraph.load(Path(processed_dir))
    circuit = CircuitExtractor(graph).extract(
        config.extractor_config(),
        circuit_id=config.circuit_id,
        notes=f"{config.config_version}: see {config.research_document}",
    )
    if save_if_extracted:
        circuit.save(Path(circuits_dir))
    return circuit


def _first_step(spikes_per_step: list[list[str]], group: set[str]) -> tuple[int | None, list[str]]:
    """First 1-based step at which any neuron of ``group`` fired, with those ids."""
    for index, fired in enumerate(spikes_per_step):
        hits = [nid for nid in fired if nid in group]
        if hits:
            return index + 1, hits
    return None, []


def result_to_dict(result: EscapeResult) -> dict[str, Any]:
    return result.model_dump(mode="json")
