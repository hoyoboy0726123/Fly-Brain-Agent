import pytest

from app.behavior import DISCLAIMER, EscapeExperiment, EscapeResult, load_escape_circuit
from app.circuits.errors import ArtifactIntegrityError
from app.motor import Action
from app.sensors import LoomingStimulus
from app.simulation import SimulationConfig
from tests.behavior_fixtures import synthetic_escape_circuit, synthetic_escape_config


@pytest.fixture(scope="module")
def experiment() -> EscapeExperiment:
    config = synthetic_escape_config()
    return EscapeExperiment(config, synthetic_escape_circuit(config))


def event(result: EscapeResult, tag: str):
    return next(e for e in result.timeline if e.tag == tag)


def test_left_stimulus_propagates_to_outputs_and_decodes_escape(experiment) -> None:
    result = experiment.run(LoomingStimulus(direction="left", intensity=1.0))
    assert result.decision.action is Action.ESCAPE
    assert result.sensory_drive.neuron_ids == ["syn_001"] and result.sensory_drive.sides == ["L"]
    assert event(result, "t1_sensory_activation").step == 1
    assert event(result, "t3_output_activation").step == 3
    assert result.decision.first_output_fire_step == 3
    assert set(result.decision.fired_output_neuron_ids) == {"syn_006", "syn_007"}
    assert set(result.decision.fired_output_sides) == {"L", "R"}  # metadata only, not an action


def test_right_and_center_directions(experiment) -> None:
    right = experiment.run(LoomingStimulus(direction="right", intensity=1.0))
    assert right.sensory_drive.neuron_ids == ["syn_002"] and right.decision.action is Action.ESCAPE
    center = experiment.run(LoomingStimulus(direction="center", intensity=1.0))
    assert center.sensory_drive.neuron_ids == ["syn_001", "syn_002"]
    assert center.firing_events >= right.firing_events


def test_zero_intensity_gives_no_action(experiment) -> None:
    result = experiment.run(LoomingStimulus(direction="left", intensity=0.0))
    assert result.decision.action is Action.NO_ACTION
    assert result.firing_events == 0
    assert event(result, "t1_sensory_activation").step is None
    assert event(result, "t3_output_activation").step is None
    assert "no output neuron fired" in event(result, "t3_output_activation").description


def test_sub_threshold_intensity_accumulates_with_latency(experiment) -> None:
    result = experiment.run(LoomingStimulus(direction="left", intensity=0.5))
    # 0.5 per step with leak 0.2: V = 0.5, 0.9, 1.22 -> sensory fires at step 3, outputs at step 5
    assert event(result, "t1_sensory_activation").step == 3
    assert event(result, "t3_output_activation").step == 5
    assert result.decision.action is Action.ESCAPE


def test_timeline_order_labels_and_disclaimer(experiment) -> None:
    result = experiment.run(LoomingStimulus(direction="left", intensity=1.0))
    tags = [e.tag for e in result.timeline]
    assert tags == [
        "t0_stimulus", "t1_sensory_activation", "t2_intermediate_activity",
        "t3_output_activation", "t4_decoded_action",
    ]  # fmt: skip
    activity_tags = ("t1_sensory_activation", "t2_intermediate_activity", "t3_output_activation")
    steps = [e.step for e in result.timeline if e.tag in activity_tags]
    assert steps == sorted(steps)
    assert event(result, "t0_stimulus").label == "APPLICATION INPUT"
    for tag in ("t1_sensory_activation", "t2_intermediate_activity", "t3_output_activation"):
        assert "SIMULATED" in event(result, tag).label
    assert event(result, "t4_decoded_action").label == "APPLICATION DECODING"
    assert result.disclaimer == DISCLAIMER
    assert DISCLAIMER.startswith(
        "STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED."
    )
    assert "SIMULATED" in result.activity_label and all(
        "SIMULATED" in o.label for o in result.output_activity
    )


def test_result_references_circuit_provenance_and_records_reproducibility_fields(
    experiment,
) -> None:
    result = experiment.run(LoomingStimulus(direction="left", intensity=1.0))
    circuit = experiment.circuit
    assert result.circuit.circuit_id == circuit.circuit_id
    assert result.circuit.circuit_hash == circuit.provenance.circuit_hash == circuit.compute_hash()
    assert result.circuit.dataset == "synthetic_tiny_connectome" and result.circuit.neurons == 7
    assert result.simulation_config == experiment.simulation_config and result.random_seed == 0
    assert result.stimulus.direction == "left" and result.steps == 20
    dumped = result.model_dump_json()
    assert "raw_files" not in dumped and "license" not in dumped  # provenance stays in the artifact


def test_determinism(experiment) -> None:
    a = experiment.run(LoomingStimulus(direction="center", intensity=0.7))
    b = experiment.run(LoomingStimulus(direction="center", intensity=0.7))
    exclude = {"created_at", "runtime_seconds"}
    assert a.model_dump(exclude=exclude) == b.model_dump(exclude=exclude)


def test_experiment_rejects_mismatched_circuit_or_hash() -> None:
    config = synthetic_escape_config()
    circuit = synthetic_escape_circuit(config)
    with pytest.raises(ArtifactIntegrityError, match="expected_circuit_hash"):
        EscapeExperiment(config.model_copy(update={"expected_circuit_hash": "0" * 64}), circuit)
    with pytest.raises(ArtifactIntegrityError, match="circuit_id"):
        EscapeExperiment(config.model_copy(update={"circuit_id": "other"}), circuit)
    with pytest.raises(ArtifactIntegrityError, match="not in the circuit"):
        EscapeExperiment(
            config.model_copy(update={"output_groups": {"L": ["syn_008"], "R": ["syn_007"]}}),
            circuit,
        )
    ok = EscapeExperiment(
        config.model_copy(update={"expected_circuit_hash": circuit.provenance.circuit_hash}),
        circuit,
    )
    assert ok.run(LoomingStimulus(direction="left", intensity=1.0)).decision.action is Action.ESCAPE


def test_simulation_config_override_is_recorded() -> None:
    config = synthetic_escape_config(simulation_config_overrides={"weight_scale": 0.01})
    experiment = EscapeExperiment(config, synthetic_escape_circuit(config))
    result = experiment.run(LoomingStimulus(direction="left", intensity=1.0))
    assert result.simulation_config.weight_scale == 0.01
    assert result.decision.action is Action.NO_ACTION  # weights too small to propagate
    explicit = EscapeExperiment(
        config, synthetic_escape_circuit(config), SimulationConfig(weight_scale=1.0)
    )
    assert (
        explicit.run(LoomingStimulus(direction="left", intensity=1.0)).decision.action
        is Action.ESCAPE
    )


def test_load_escape_circuit_from_saved_artifact(tmp_path) -> None:
    config = synthetic_escape_config()
    circuit = synthetic_escape_circuit(config)
    circuit.save(tmp_path)
    assert load_escape_circuit(config, tmp_path) == circuit
    with pytest.raises(FileNotFoundError):
        load_escape_circuit(config, tmp_path / "missing")
