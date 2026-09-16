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


GroupRole = Literal["sensory", "output", "other"]


class ActivityGroup(BaseModel):
    """Circuit neurons sharing a cell type and a side (the unit the web demo animates).

    ``neuron_count`` is the number of circuit neurons in the group (STRUCTURE); which of
    them fire at a step is SIMULATED (see ``GroupActivity``).
    """

    key: str
    cell_type: str
    side: str
    role: GroupRole
    neuron_count: int = Field(ge=0)
    stimulable_count: int = Field(default=0, ge=0)


class GroupEdge(BaseModel):
    """Circuit edges aggregated between two groups (STRUCTURE, from the artifact)."""

    pre_key: str
    post_key: str
    edge_count: int = Field(ge=1)
    synapse_total: int = Field(ge=1)
    dataset: str
    dataset_version: str


class GroupActivity(BaseModel):
    """Per-step SIMULATED spike counts aggregated by group; index 0 is step 1."""

    label: str = ACTIVITY_LABEL
    groups: list[ActivityGroup]
    fired_counts: dict[str, list[int]]


NEURON_STATE_LABEL = (
    "SIMULATED STATE per neuron and step (membrane potential, fired, refractory) from the "
    "simplified LIF-like model; not measured neural recordings"
)


class NeuronActivity(BaseModel):
    """Per-neuron, per-step SIMULATED state for the inspector replay; index 0 is step 1.

    ``membrane_potential_per_step[s][i]`` and ``refractory_per_step[s][i]`` refer to
    ``neuron_ids[i]`` after step ``s + 1``; ``fired_ids_per_step[s]`` lists the ids that
    fired at that step. Model parameters are repeated so the values can be interpreted.
    """

    label: str = NEURON_STATE_LABEL
    neuron_ids: list[str]
    fired_ids_per_step: list[list[str]]
    membrane_potential_per_step: list[list[float]]
    refractory_per_step: list[list[int]]
    resting_potential: float
    reset_potential: float
    threshold: float


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
    group_activity: GroupActivity
    neuron_activity: NeuronActivity | None = None
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
        self.groups, self.group_of = self._build_groups()
        self.group_edges = self._build_group_edges()

    def _build_group_edges(self) -> list[GroupEdge]:
        """Aggregate the artifact's edges by (pre group, post group); nothing is added."""
        totals: dict[tuple[str, str], list[int]] = {}
        for edge in self.circuit.edges:
            pre = self.group_of.get(edge.pre_neuron_id)
            post = self.group_of.get(edge.post_neuron_id)
            if pre is None or post is None:
                continue
            bucket = totals.setdefault((pre, post), [0, 0])
            bucket[0] += 1
            bucket[1] += edge.synapse_count
        return [
            GroupEdge(
                pre_key=pre,
                post_key=post,
                edge_count=count,
                synapse_total=synapses,
                dataset=self.circuit.dataset,
                dataset_version=self.circuit.dataset_version,
            )
            for (pre, post), (count, synapses) in sorted(totals.items())
        ]

    def _build_groups(self) -> tuple[list[ActivityGroup], dict[str, str]]:
        """Group circuit neurons by (cell type, side); sides come from the config only."""
        population = self.config.sensory_population or self.config.sensory_groups
        side_of = {nid: side for side, ids in population.items() for nid in ids}
        side_of.update(self.output_side)
        population_ids = set(self.config.all_population_ids())
        role_rank = {"sensory": 0, "output": 1, "other": 2}
        groups: dict[str, ActivityGroup] = {}
        group_of: dict[str, str] = {}
        for node in self.circuit.nodes:
            nid = node.neuron_id
            role: GroupRole = "other"
            if nid in population_ids:
                role = "sensory"
            elif nid in self.output_side:
                role = "output"
            side = side_of.get(nid, "NA")
            cell_type = node.cell_type or "unknown"
            key = f"{cell_type}_{side}"
            group = groups.get(key)
            if group is None:
                group = groups[key] = ActivityGroup(
                    key=key, cell_type=cell_type, side=side, role=role, neuron_count=0
                )
            group.neuron_count += 1
            if nid in self.sensory_ids:
                group.stimulable_count += 1
            group_of[nid] = key
        ordered = sorted(groups.values(), key=lambda g: (role_rank[g.role], g.cell_type, g.side))
        return ordered, group_of

    def run(
        self,
        stimulus: LoomingStimulus,
        steps: int | None = None,
        *,
        record_neuron_states: bool = True,
    ) -> EscapeResult:
        started = time.perf_counter()
        steps = steps or self.config.simulation_steps
        drive = self.mapper.map(stimulus)
        engine = SimulationEngine(self.circuit, self.simulation_config)
        engine.stimulate(drive.neuron_ids, drive.injected_current, drive.duration_steps)
        potentials: list[list[float]] = []
        refractory: list[list[int]] = []

        def record(_summary: object) -> None:
            potentials.append([round(float(v), 6) for v in engine.membrane_potential.tolist()])
            refractory.append([int(v) for v in engine.refractory_remaining.tolist()])

        summary = engine.run(steps, on_step=record if record_neuron_states else None)
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
        fired_counts = {group.key: [0] * len(spikes_per_step) for group in self.groups}
        for index, fired in enumerate(spikes_per_step):
            for nid in fired:
                key = self.group_of.get(nid)
                if key is not None:
                    fired_counts[key][index] += 1
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
            group_activity=GroupActivity(groups=self.groups, fired_counts=fired_counts),
            neuron_activity=NeuronActivity(
                neuron_ids=list(engine.neuron_ids),
                fired_ids_per_step=spikes_per_step,
                membrane_potential_per_step=potentials,
                refractory_per_step=refractory,
                resting_potential=self.simulation_config.resting_potential,
                reset_potential=self.simulation_config.reset_potential,
                threshold=self.simulation_config.threshold,
            )
            if record_neuron_states
            else None,
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
