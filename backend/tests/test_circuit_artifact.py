import json

import pytest

from app.circuits import (
    ArtifactIntegrityError,
    Circuit,
    CircuitExtractor,
    ExtractorConfig,
    TargetReport,
)
from tests.circuit_fixtures import fixture_graph


def make_circuit(circuit_id: str = "fixture_demo") -> Circuit:
    config = ExtractorConfig(
        seed_neuron_ids=["syn_001"],
        target_neuron_ids=["syn_007"],
        max_hops=2,
        min_synapses=1,
        max_neurons=50,
    )
    return CircuitExtractor(fixture_graph()).extract(
        config, circuit_id=circuit_id, notes="test artifact"
    )


def test_export_import_round_trip(tmp_path) -> None:
    circuit = make_circuit()
    json_path, parquet_path = circuit.save(tmp_path)
    assert (
        json_path == tmp_path / "fixture_demo.json"
        and parquet_path == tmp_path / "fixture_demo.parquet"
    )

    loaded = Circuit.load(json_path)
    assert loaded == circuit
    assert loaded.provenance.circuit_hash == circuit.compute_hash()

    edges = Circuit.load_edges(parquet_path)
    assert edges.num_rows == len(circuit.edges)
    assert edges.column_names == [
        "pre_neuron_id",
        "post_neuron_id",
        "synapse_count",
        "dataset",
        "dataset_version",
    ]
    assert edges.equals(circuit.edges_table(), check_metadata=False)
    metadata = edges.schema.metadata
    assert metadata[b"flybrain.circuit_id"] == b"fixture_demo"
    assert metadata[b"flybrain.circuit_hash"].decode() == circuit.provenance.circuit_hash
    assert json.loads(metadata[b"flybrain.extractor_config"])["max_hops"] == 2


def test_json_artifact_has_required_sections(tmp_path) -> None:
    circuit = make_circuit()
    json_path, _ = circuit.save(tmp_path)
    data = json.loads(json_path.read_text())
    for key in (
        "circuit_id",
        "dataset",
        "dataset_version",
        "canonical_graph",
        "extractor_config",
        "seed_neurons",
        "target_neurons",
        "nodes",
        "edges",
        "provenance",
        "stats",
    ):
        assert key in data, key
    assert data["canonical_graph"]["selection_rule"]
    assert set(data["edges"][0]) == {
        "pre_neuron_id",
        "post_neuron_id",
        "synapse_count",
        "dataset",
        "dataset_version",
    }
    assert {"neuron_id", "minimum_hop_from_seed", "is_seed", "is_target"} <= set(data["nodes"][0])
    assert data["provenance"]["circuit_hash"] and data["provenance"]["graph_fingerprint"]


def test_tampered_artifact_is_rejected(tmp_path) -> None:
    circuit = make_circuit()
    json_path, _ = circuit.save(tmp_path)
    data = json.loads(json_path.read_text())
    data["edges"][0]["synapse_count"] += 1
    json_path.write_text(json.dumps(data))
    with pytest.raises(ArtifactIntegrityError, match="hash"):
        Circuit.load(json_path)
    assert (
        Circuit.load(json_path, verify=False).edges[0].synapse_count
        == circuit.edges[0].synapse_count + 1
    )


def test_edge_with_foreign_dataset_is_rejected(tmp_path) -> None:
    circuit = make_circuit()
    circuit.edges[0].dataset = "another-dataset"
    circuit.seal()
    with pytest.raises(ArtifactIntegrityError, match="dataset"):
        circuit.save(tmp_path)


def test_circuit_id_must_be_filesystem_safe() -> None:
    with pytest.raises(ValueError, match="circuit_id"):
        make_circuit("../escape")
    with pytest.raises(ValueError, match="circuit_id"):
        make_circuit("has space")
    assert make_circuit("Escape_v1.smoke-01").circuit_id == "Escape_v1.smoke-01"


def test_target_report_consistency() -> None:
    with pytest.raises(ValueError):
        TargetReport(neuron_id="x", reachable=True, minimum_path_length=None)
    with pytest.raises(ValueError):
        TargetReport(neuron_id="x", reachable=False, minimum_path_length=2)


def test_hash_is_stable_and_content_sensitive() -> None:
    a, b = make_circuit(), make_circuit()
    assert a.compute_hash() == b.compute_hash()
    b.nodes[0].minimum_hop_from_seed += 1
    assert a.compute_hash() != b.compute_hash()
