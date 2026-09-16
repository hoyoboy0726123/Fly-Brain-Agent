import json

import numpy as np
import pyarrow as pa
import pytest

from app.circuits import ConnectivityGraph, GraphBuildError, MissingNeuronError
from app.connectome.normalize import build_connections_table, build_neurons_table, write_parquet
from tests.circuit_fixtures import FIXTURE_EDGES, fixture_graph, fixture_tables, random_graph


def test_fixture_graph_dimensions_and_metadata() -> None:
    graph = fixture_graph()
    assert graph.num_nodes == 8 and graph.num_edges == len(FIXTURE_EDGES)
    assert graph.dataset == "synthetic_tiny_connectome" and graph.dataset_version == "fixture-v1"
    assert "synthetic" in graph.selection_rule
    assert graph.memory_bytes() > 0
    assert graph.ids_of(np.array([0, 7])) == ["syn_001", "syn_008"]


def test_successors_and_predecessors_follow_edge_direction() -> None:
    graph = fixture_graph()
    nbrs, weights = graph.successors(graph.index_of("syn_001"))
    assert graph.ids_of(nbrs) == ["syn_003", "syn_004"] and weights.tolist() == [12, 3]
    nbrs, weights = graph.predecessors(graph.index_of("syn_007"))
    assert graph.ids_of(nbrs) == ["syn_004", "syn_005", "syn_007"] and weights.tolist() == [
        15,
        5,
        1,
    ]
    assert graph.successors(graph.index_of("syn_008"))[0].size == 0
    assert graph.predecessors(graph.index_of("syn_001"))[0].size == 0


def test_min_synapses_filters_neighbors() -> None:
    graph = fixture_graph()
    nbrs, weights = graph.successors(graph.index_of("syn_001"), min_synapses=5)
    assert graph.ids_of(nbrs) == ["syn_003"] and weights.tolist() == [12]
    nbrs, _ = graph.neighbors(graph.index_of("syn_007"), "upstream", min_synapses=5)
    assert graph.ids_of(nbrs) == ["syn_004", "syn_005"]


def test_edge_weight_lookup_and_degree() -> None:
    graph = fixture_graph()
    a, b = graph.index_of("syn_003"), graph.index_of("syn_006")
    assert graph.edge_weight(a, b) == 20
    assert graph.edge_weight(b, a) == 1
    assert graph.edge_weight(graph.index_of("syn_001"), graph.index_of("syn_007")) is None
    assert graph.degree(graph.index_of("syn_004"), "downstream") == 2
    assert graph.degree(graph.index_of("syn_007"), "upstream") == 3


def test_resolve_fails_loudly_on_missing_ids() -> None:
    graph = fixture_graph()
    with pytest.raises(MissingNeuronError, match="seed") as info:
        graph.resolve(["syn_001", "nope_1", "nope_2"], "seed")
    assert info.value.missing == ["nope_1", "nope_2"]
    with pytest.raises(MissingNeuronError):
        graph.index_of("missing")
    assert graph.resolve(["syn_004", "syn_001", "syn_004"], "seed").tolist() == [0, 3]


def test_node_metadata_comes_from_neurons_table() -> None:
    graph = fixture_graph()
    metadata = graph.node_metadata(np.array([graph.index_of("syn_001"), graph.index_of("syn_008")]))
    assert metadata["cell_type"] == ["SYN_input_A", None]
    assert metadata["cell_class"] == ["synthetic_input", None]
    assert metadata["neurotransmitter"] == [None, None]


def test_build_rejects_duplicate_neuron_ids() -> None:
    neurons = build_neurons_table(pa.array(["a", "a"]), dataset="d", dataset_version="v")
    connections = build_connections_table(
        pa.array([], pa.string()),
        pa.array([], pa.string()),
        pa.array([], pa.int64()),
        dataset="d",
        dataset_version="v",
    )
    with pytest.raises(GraphBuildError, match="unique"):
        ConnectivityGraph.from_tables(neurons, connections)


def test_build_rejects_dangling_edges_and_duplicate_edges_and_mixed_datasets() -> None:
    neurons = build_neurons_table(pa.array(["a", "b"]), dataset="d", dataset_version="v")
    dangling = build_connections_table(
        pa.array(["a"]),
        pa.array(["zzz"]),
        pa.array([1], pa.int64()),
        dataset="d",
        dataset_version="v",
    )
    with pytest.raises(GraphBuildError, match="missing"):
        ConnectivityGraph.from_tables(neurons, dangling)
    duplicate = build_connections_table(
        pa.array(["a", "a"]),
        pa.array(["b", "b"]),
        pa.array([1, 2], pa.int64()),
        dataset="d",
        dataset_version="v",
    )
    with pytest.raises(GraphBuildError, match="duplicate"):
        ConnectivityGraph.from_tables(neurons, duplicate)
    mixed = build_connections_table(
        pa.array(["a"]),
        pa.array(["b"]),
        pa.array([1], pa.int64()),
        dataset="other",
        dataset_version="v",
    )
    with pytest.raises(GraphBuildError, match="dataset"):
        ConnectivityGraph.from_tables(neurons, mixed)


def test_csr_matches_brute_force_on_random_graph() -> None:
    graph, edges = random_graph()
    out_ref: dict[int, list[tuple[int, int]]] = {}
    in_ref: dict[int, list[tuple[int, int]]] = {}
    for (pre, post), weight in edges.items():
        out_ref.setdefault(pre, []).append((post, weight))
        in_ref.setdefault(post, []).append((pre, weight))
    for node in range(graph.num_nodes):
        nbrs, weights = graph.successors(node)
        assert list(zip(nbrs.tolist(), weights.tolist(), strict=True)) == sorted(
            out_ref.get(node, [])
        )
        nbrs, weights = graph.predecessors(node)
        assert list(zip(nbrs.tolist(), weights.tolist(), strict=True)) == sorted(
            in_ref.get(node, [])
        )
    assert graph.num_edges == len(edges)


def test_load_builds_cache_then_reuses_it(tmp_path) -> None:
    neurons, connections = fixture_tables()
    write_parquet(neurons, tmp_path / "neurons.parquet")
    write_parquet(connections, tmp_path / "connections.parquet")

    first = ConnectivityGraph.load(tmp_path)
    assert first.load_info is not None and first.load_info.cache_hit is False
    assert (tmp_path / "graph_cache" / "meta.json").is_file()
    assert first.selection_rule.startswith("unknown")  # no provenance.json in this directory

    second = ConnectivityGraph.load(tmp_path)
    assert second.load_info is not None and second.load_info.cache_hit is True
    for name in (
        "out_indptr",
        "out_indices",
        "out_weights",
        "in_indptr",
        "in_indices",
        "in_weights",
    ):
        assert np.array_equal(getattr(first, name), getattr(second, name)), name
    assert second.ids_of(np.arange(second.num_nodes)) == first.ids_of(np.arange(first.num_nodes))
    assert second.fingerprint() == first.fingerprint()

    # a changed table invalidates the cache
    write_parquet(connections.slice(0, 5), tmp_path / "connections.parquet")
    third = ConnectivityGraph.load(tmp_path)
    assert third.load_info is not None and third.load_info.cache_hit is False
    assert third.num_edges == 5
    meta = json.loads((tmp_path / "graph_cache" / "meta.json").read_text())
    assert meta["num_edges"] == 5

    without_cache = ConnectivityGraph.load(tmp_path, use_cache=False)
    assert without_cache.load_info is not None and without_cache.load_info.cache_dir is None


def test_load_reads_selection_rule_from_provenance(tmp_path) -> None:
    from app.connectome import CanonicalGraph, Provenance, SourceDataset

    neurons, connections = fixture_tables()
    write_parquet(neurons, tmp_path / "neurons.parquet")
    write_parquet(connections, tmp_path / "connections.parquet")
    Provenance(
        dataset_name="synthetic_tiny_connectome",
        dataset_version="fixture-v1",
        synthetic=True,
        source_dataset=SourceDataset(
            name="synthetic", version="fixture-v1", official_neuron_count=8
        ),
        canonical_graph=CanonicalGraph(
            selection_rule="rule-from-provenance", neuron_count=8, connection_count=11
        ),
    ).write(tmp_path / "provenance.json")
    graph = ConnectivityGraph.load(tmp_path, use_cache=False)
    assert graph.selection_rule == "rule-from-provenance"
    assert graph.provenance is not None and graph.provenance.synthetic is True


def test_load_fails_loudly_without_tables(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        ConnectivityGraph.load(tmp_path)
