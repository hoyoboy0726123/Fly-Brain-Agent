"""Guards on the committed escape_v1 biological configuration and circuit artifact.

Checks that only need the committed files run always; checks that need the canonical graph
skip when data/processed is absent (tests never require the dataset).
"""

from pathlib import Path

import pytest

from app.behavior import load_escape_config
from app.circuits import Circuit

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = PROJECT_ROOT / "data" / "circuits" / "escape_v1.json"
PROCESSED = PROJECT_ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def config():
    return load_escape_config("escape_v1")


@pytest.fixture(scope="module")
def circuit():
    if not ARTIFACT.is_file():
        pytest.skip("data/circuits/escape_v1.json not present")
    return Circuit.load(ARTIFACT)  # verifies the artifact hash


def test_config_is_biological_and_evidenced(config) -> None:
    assert config.synthetic is False
    assert config.dataset == "male-cns" and config.dataset_version == "v1.0"
    assert config.canonical_selection_rule == 'status == "Traced"'
    assert config.biological_status in ("SUPPORTED", "PARTIALLY SUPPORTED")
    assert config.research_document == "docs/circuits/escape_v1.md"
    assert (PROJECT_ROOT / config.research_document).is_file()
    assert config.sensory_cell_types == ["LC4", "LPLC2"] and config.output_cell_types == ["DNp01"]
    assert len(config.citations) >= 5
    for citation in config.citations:
        assert citation.doi or citation.url, citation.key
        assert citation.claim and citation.verification
    assert config.limitations and config.mapping_confidence
    assert config.decoder.actions == ["NO_ACTION", "ESCAPE"]


def test_no_synthetic_ids_and_ids_are_numeric_body_ids(config) -> None:
    ids = config.all_sensory_ids() + config.all_output_ids()
    assert ids and all(nid.isdigit() for nid in ids)
    assert not any(nid.startswith("syn_") for nid in ids)
    assert config.output_groups == {"L": ["10010"], "R": ["10001"]}
    assert config.sensory_population is not None
    assert len(config.sensory_population["L"]) == 165
    assert len(config.sensory_population["R"]) == 146
    for side in ("L", "R"):
        kept, excluded = set(config.sensory_groups[side]), set(config.excluded_sensory_ids[side])
        assert kept | excluded == set(config.sensory_population[side]) and not kept & excluded
    assert sum(len(v) for v in config.excluded_sensory_ids.values()) > 0
    assert config.exclusion_reason


def test_artifact_matches_config_and_canonical_provenance(config, circuit) -> None:
    assert circuit.circuit_id == config.circuit_id == "escape_v1"
    assert circuit.provenance.circuit_hash == config.expected_circuit_hash == circuit.compute_hash()
    assert circuit.dataset == "male-cns" and circuit.dataset_version == "v1.0"
    assert circuit.canonical_graph.selection_rule == 'status == "Traced"'
    assert circuit.canonical_graph.neuron_count == 165_122
    assert circuit.canonical_graph.connection_count == 25_563_197
    node_ids = {n.neuron_id for n in circuit.nodes}
    assert set(config.all_sensory_ids()) <= node_ids and set(config.all_output_ids()) <= node_ids
    assert circuit.extractor_config.max_hops == 1 and circuit.extractor_config.min_synapses == 10
    assert circuit.extractor_config.restrict_to_target_paths is True
    for edge in circuit.edges:
        assert edge.dataset == "male-cns" and edge.dataset_version == "v1.0"
        assert edge.synapse_count >= 10
        assert edge.pre_neuron_id in node_ids and edge.post_neuron_id in node_ids
    for target in circuit.target_neurons:
        assert target.reachable is True and target.minimum_path_length == 1


def test_artifact_cell_types_match_the_configured_roles(config, circuit) -> None:
    type_of = {n.neuron_id: n.cell_type for n in circuit.nodes}
    assert {type_of[nid] for nid in config.all_sensory_ids()} == {"LC4", "LPLC2"}
    assert not any(nid in type_of for ids in config.excluded_sensory_ids.values() for nid in ids)
    assert {type_of[nid] for nid in config.all_output_ids()} == {"DNp01"}
    # every sensory neuron kept in the circuit projects directly onto an output neuron
    outputs = set(config.all_output_ids())
    sensory_in_circuit = {n.neuron_id for n in circuit.nodes if n.cell_type in ("LC4", "LPLC2")}
    pre_with_output_edge = {e.pre_neuron_id for e in circuit.edges if e.post_neuron_id in outputs}
    assert sensory_in_circuit <= pre_with_output_edge


def test_configured_ids_exist_in_canonical_graph_when_available(config) -> None:
    if not (PROCESSED / "neurons.parquet").is_file():
        pytest.skip("canonical graph not available")
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    table = pq.read_table(
        PROCESSED / "neurons.parquet", columns=["neuron_id", "cell_type", "mcns_somaSide"]
    )
    by_id = dict(
        zip(
            table["neuron_id"].to_pylist(),
            zip(table["cell_type"].to_pylist(), table["mcns_somaSide"].to_pylist(), strict=True),
            strict=True,
        )
    )
    for side, ids in config.sensory_population.items():  # type: ignore[union-attr]
        for nid in ids:
            assert nid in by_id, nid
            assert by_id[nid][0] in ("LC4", "LPLC2") and by_id[nid][1] == side
    for side, ids in config.output_groups.items():
        for nid in ids:
            assert by_id[nid] == ("DNp01", side)
    # the config covers every LC4/LPLC2 neuron of the canonical graph, none invented
    canonical = {nid for nid, (ty, _) in by_id.items() if ty in ("LC4", "LPLC2")}
    assert set(config.all_population_ids()) == canonical
    assert pc.sum(pc.equal(table["cell_type"], "DNp01")).as_py() == 2
