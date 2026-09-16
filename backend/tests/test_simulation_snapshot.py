import json

import pytest

from app.simulation import (
    SimulationConfig,
    SimulationEngine,
    SimulationSnapshot,
    SnapshotMismatchError,
)
from tests.simulation_fixtures import chain_circuit, fixture_circuit


def test_snapshot_serializes_and_round_trips(tmp_path) -> None:
    circuit = fixture_circuit()
    engine = SimulationEngine(circuit, SimulationConfig(noise_std=0.1, random_seed=3))
    engine.stimulate(["syn_001"], 2.0, 3)
    engine.run(7)
    snapshot = engine.snapshot("unit_snapshot")
    path = snapshot.save(tmp_path / "unit_snapshot.snapshot.json")
    loaded = SimulationSnapshot.load(path)
    assert loaded == snapshot
    data = json.loads(path.read_text())
    for key in (
        "simulation_id",
        "circuit_id",
        "circuit_hash",
        "simulation_config",
        "random_seed",
        "current_step",
        "stimuli",
        "neuron_states",
    ):
        assert key in data, key
    assert data["current_step"] == 7 and data["random_seed"] == 3
    assert data["simulation_config"]["label"].startswith("COMPUTATIONAL MODEL PARAMETERS")
    assert "SIMULATION SNAPSHOT" in data["label"]


def test_snapshot_references_circuit_but_carries_no_biological_provenance() -> None:
    circuit = fixture_circuit()
    engine = SimulationEngine(circuit, SimulationConfig())
    snapshot = engine.snapshot("ref")
    assert snapshot.circuit_id == circuit.circuit_id
    assert snapshot.circuit_hash == circuit.provenance.circuit_hash == circuit.compute_hash()
    dumped = snapshot.model_dump()
    for forbidden in (
        "raw_files",
        "license",
        "source_dataset",
        "canonical_graph",
        "edges",
        "synapse_count",
    ):
        assert forbidden not in json.dumps(dumped), forbidden


def test_resume_from_snapshot_matches_uninterrupted_run() -> None:
    circuit = fixture_circuit()
    config = SimulationConfig(noise_std=0.2, random_seed=11)
    continuous = SimulationEngine(circuit, config)
    continuous.stimulate(["syn_001"], 1.5, 4)
    continuous.run(20)

    interrupted = SimulationEngine(circuit, config)
    interrupted.stimulate(["syn_001"], 1.5, 4)
    interrupted.run(8)
    resumed = SimulationEngine.from_snapshot(circuit, interrupted.snapshot("mid"))
    assert resumed.step_index == 8 and resumed.stimuli == interrupted.stimuli
    resumed.run(12)

    assert resumed.membrane_potential.tolist() == continuous.membrane_potential.tolist()
    assert resumed.refractory_remaining.tolist() == continuous.refractory_remaining.tolist()
    assert resumed.fired.tolist() == continuous.fired.tolist()
    assert resumed.firing_events == continuous.firing_events
    assert resumed.get_state() == continuous.get_state()


def test_snapshot_for_different_circuit_is_rejected() -> None:
    engine = SimulationEngine(fixture_circuit(), SimulationConfig())
    snapshot = engine.snapshot("x")
    with pytest.raises(SnapshotMismatchError, match="references circuit"):
        SimulationEngine.from_snapshot(chain_circuit(), snapshot)
    tampered = snapshot.model_copy(update={"circuit_hash": "0" * 64})
    with pytest.raises(SnapshotMismatchError):
        SimulationEngine.from_snapshot(fixture_circuit(), tampered)
