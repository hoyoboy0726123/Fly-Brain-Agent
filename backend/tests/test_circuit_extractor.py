import numpy as np
import pytest

from app.circuits import (
    CircuitExtractor,
    ExtractorConfig,
    MaxNeuronsExceededError,
    MissingNeuronError,
)
from tests.circuit_fixtures import FIXTURE_EDGES, fixture_graph, naive_bfs, random_graph

DEFAULTS = {"seed_neuron_ids": ["syn_001"], "max_hops": 2, "min_synapses": 1, "max_neurons": 50}


def extract(**overrides):
    config = ExtractorConfig(**{**DEFAULTS, **overrides})
    return CircuitExtractor(fixture_graph()).extract(config, circuit_id="t")


def hops(circuit) -> dict[str, int]:
    return {n.neuron_id: n.minimum_hop_from_seed for n in circuit.nodes}


def edges(circuit) -> set[tuple[str, str, int]]:
    return {(e.pre_neuron_id, e.post_neuron_id, e.synapse_count) for e in circuit.edges}


def induced(node_ids: set[str], min_synapses: int) -> set[tuple[str, str, int]]:
    return {
        (p, q, w)
        for p, q, w in FIXTURE_EDGES
        if p in node_ids and q in node_ids and w >= min_synapses
    }


# ------------------------------------------------------------------ downstream / hops
def test_downstream_one_hop() -> None:
    circuit = extract(max_hops=1)
    assert hops(circuit) == {"syn_001": 0, "syn_003": 1, "syn_004": 1}
    assert edges(circuit) == {("syn_001", "syn_003", 12), ("syn_001", "syn_004", 3)}


def test_downstream_two_hops_returns_induced_subgraph() -> None:
    circuit = extract(max_hops=2)
    assert hops(circuit) == {
        "syn_001": 0, "syn_003": 1, "syn_004": 1, "syn_005": 2, "syn_006": 2, "syn_007": 2
    }  # fmt: skip
    assert edges(circuit) == induced(set(hops(circuit)), 1)
    assert len(circuit.edges) == 9
    # nodes are ordered by (hop, index) and every node id is unique
    node_hops = [n.minimum_hop_from_seed for n in circuit.nodes]
    assert node_hops == sorted(node_hops)
    assert len({n.neuron_id for n in circuit.nodes}) == len(circuit.nodes)


def test_max_hops_zero_returns_seeds_only() -> None:
    circuit = extract(seed_neuron_ids=["syn_003", "syn_006"], max_hops=0)
    assert hops(circuit) == {"syn_003": 0, "syn_006": 0}
    assert edges(circuit) == {("syn_003", "syn_006", 20), ("syn_006", "syn_003", 1)}


# ------------------------------------------------------------------ thresholds
def test_min_synapses_filters_traversal_and_induced_edges() -> None:
    circuit = extract(max_hops=2, min_synapses=5)
    assert hops(circuit) == {"syn_001": 0, "syn_003": 1, "syn_006": 2}
    assert edges(circuit) == {("syn_001", "syn_003", 12), ("syn_003", "syn_006", 20)}
    assert all(e.synapse_count >= 5 for e in circuit.edges)


# ------------------------------------------------------------------ upstream / direction
def test_upstream_follows_incoming_edges() -> None:
    circuit = extract(seed_neuron_ids=["syn_007"], direction="upstream", max_hops=1)
    assert hops(circuit) == {"syn_007": 0, "syn_004": 1, "syn_005": 1}
    assert edges(circuit) == {
        ("syn_004", "syn_007", 15), ("syn_005", "syn_007", 5), ("syn_007", "syn_007", 1)
    }  # fmt: skip
    two = extract(seed_neuron_ids=["syn_007"], direction="upstream", max_hops=2)
    assert hops(two) == {
        "syn_007": 0, "syn_004": 1, "syn_005": 1, "syn_001": 2, "syn_002": 2, "syn_003": 2
    }  # fmt: skip
    assert "syn_006" not in hops(two)


def test_directionality_downstream_vs_upstream_differ() -> None:
    down = extract(seed_neuron_ids=["syn_006"], max_hops=3)
    up = extract(seed_neuron_ids=["syn_006"], direction="upstream", max_hops=3)
    assert hops(down) == {"syn_006": 0, "syn_003": 1, "syn_005": 2, "syn_007": 3}
    assert hops(up) == {"syn_006": 0, "syn_003": 1, "syn_004": 1, "syn_001": 2, "syn_002": 2}
    # edges are always stored pre -> post, whatever the traversal direction
    for e in up.edges:
        assert (e.pre_neuron_id, e.post_neuron_id, e.synapse_count) in set(FIXTURE_EDGES)


# ------------------------------------------------------------------ targets
def test_target_reachability_is_reported_not_fabricated() -> None:
    circuit = extract(target_neuron_ids=["syn_007", "syn_002"], max_hops=2)
    reports = {t.neuron_id: (t.reachable, t.minimum_path_length) for t in circuit.target_neurons}
    assert reports == {"syn_002": (False, None), "syn_007": (True, 2)}
    by_id = {n.neuron_id: n for n in circuit.nodes}
    assert by_id["syn_007"].is_target is True and by_id["syn_001"].is_seed is True
    assert "syn_002" not in by_id


def test_target_beyond_max_hops_is_unreachable() -> None:
    circuit = extract(target_neuron_ids=["syn_007"], max_hops=1)
    assert circuit.target_neurons[0].reachable is False
    assert circuit.target_neurons[0].minimum_path_length is None


def test_seed_that_is_also_target_has_path_length_zero() -> None:
    circuit = extract(target_neuron_ids=["syn_001"], max_hops=1)
    report = circuit.target_neurons[0]
    assert report.reachable is True and report.minimum_path_length == 0


def test_restrict_to_target_paths_prunes_off_path_neurons() -> None:
    circuit = extract(target_neuron_ids=["syn_007"], max_hops=2, restrict_to_target_paths=True)
    assert hops(circuit) == {"syn_001": 0, "syn_004": 1, "syn_007": 2}
    assert edges(circuit) == {
        ("syn_001", "syn_004", 3), ("syn_004", "syn_007", 15), ("syn_007", "syn_007", 1)
    }  # fmt: skip
    assert circuit.stats.visited_neurons == 6 and circuit.stats.returned_neurons == 3


def test_restrict_to_target_paths_requires_targets() -> None:
    with pytest.raises(ValueError, match="requires at least one target"):
        ExtractorConfig(
            seed_neuron_ids=["a"], max_hops=1, min_synapses=1, max_neurons=5,
            restrict_to_target_paths=True,
        )  # fmt: skip


# ------------------------------------------------------------------ fail loudly
def test_missing_seed_fails_loudly() -> None:
    with pytest.raises(MissingNeuronError, match="seed") as info:
        extract(seed_neuron_ids=["syn_001", "ghost"])
    assert info.value.missing == ["ghost"]


def test_missing_target_fails_loudly() -> None:
    with pytest.raises(MissingNeuronError, match="target") as info:
        extract(target_neuron_ids=["nope"])
    assert info.value.missing == ["nope"]


def test_max_neurons_is_a_hard_abort() -> None:
    with pytest.raises(MaxNeuronsExceededError) as info:
        extract(max_hops=2, max_neurons=3)
    assert (info.value.limit, info.value.attempted, info.value.hop) == (3, 6, 2)
    with pytest.raises(MaxNeuronsExceededError) as info:
        extract(max_hops=1, max_neurons=2)
    assert (info.value.limit, info.value.attempted, info.value.hop) == (2, 3, 1)
    with pytest.raises(MaxNeuronsExceededError) as info:
        extract(seed_neuron_ids=["syn_001", "syn_002", "syn_003"], max_hops=0, max_neurons=2)
    assert info.value.hop == 0 and info.value.attempted == 3
    # exactly at the limit is allowed
    assert extract(max_hops=1, max_neurons=3).stats.returned_neurons == 3


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        ExtractorConfig(seed_neuron_ids=[], max_hops=1, min_synapses=1, max_neurons=5)
    with pytest.raises(ValueError):
        ExtractorConfig(seed_neuron_ids=["a"], max_hops=-1, min_synapses=1, max_neurons=5)
    with pytest.raises(ValueError):
        ExtractorConfig(seed_neuron_ids=["a"], max_hops=1, min_synapses=1, max_neurons=0)
    config = ExtractorConfig(
        seed_neuron_ids=["b", "a", "b"], max_hops=1, min_synapses=1, max_neurons=5
    )
    assert config.seed_neuron_ids == ["a", "b"]  # deduplicated + sorted


# ------------------------------------------------------------------ determinism / provenance
def test_extraction_is_deterministic_regardless_of_seed_order() -> None:
    a = extract(seed_neuron_ids=["syn_001", "syn_002"], target_neuron_ids=["syn_007"])
    b = extract(seed_neuron_ids=["syn_002", "syn_001"], target_neuron_ids=["syn_007"])

    def strip(circuit):
        return circuit.model_dump(exclude={"stats": True, "provenance": {"extracted_at": True}})

    assert strip(a) == strip(b)
    assert a.provenance.circuit_hash == b.provenance.circuit_hash
    assert a.seed_neurons == ["syn_001", "syn_002"]


def test_every_edge_is_a_verbatim_canonical_edge_with_provenance() -> None:
    circuit = extract(seed_neuron_ids=["syn_001", "syn_002"], max_hops=3)
    canonical = {(p, q): w for p, q, w in FIXTURE_EDGES}
    assert circuit.edges, "expected a non-empty circuit"
    for e in circuit.edges:
        assert canonical[(e.pre_neuron_id, e.post_neuron_id)] == e.synapse_count
        assert e.dataset == "synthetic_tiny_connectome" and e.dataset_version == "fixture-v1"
    node_ids = set(hops(circuit))
    assert edges(circuit) == induced(node_ids, 1)  # nothing missing, nothing invented
    assert circuit.canonical_graph.selection_rule.startswith("all fixture neurons")
    assert circuit.canonical_graph.neuron_count == 8
    assert circuit.canonical_graph.connection_count == 11
    assert circuit.provenance.biological_interpretation.startswith("NONE")
    assert circuit.nodes[0].cell_type == "SYN_input_A"


def test_stats_are_recorded() -> None:
    circuit = extract(max_hops=2)
    stats = circuit.stats
    assert stats.visited_neurons == 6 and stats.returned_neurons == 6 and stats.returned_edges == 9
    assert stats.examined_edges == 2 + 2 + 2  # out-degrees of syn_001, syn_003, syn_004
    assert stats.extraction_seconds >= 0
    assert stats.graph_memory_bytes is not None and stats.graph_memory_bytes > 0


# ------------------------------------------------------------------ reference comparison
@pytest.mark.parametrize("direction", ["downstream", "upstream"])
@pytest.mark.parametrize("min_synapses", [1, 10, 25])
def test_traversal_matches_naive_bfs_on_random_graph(direction: str, min_synapses: int) -> None:
    graph, edge_dict = random_graph()
    extractor = CircuitExtractor(graph)
    sources = [3, 77, 150]
    result = extractor.traverse(
        np.array(sources),
        direction=direction,
        max_hops=3,
        min_synapses=min_synapses,
        max_neurons=10**6,
    )
    expected = naive_bfs(
        edge_dict, sources, direction=direction, max_hops=3, min_synapses=min_synapses
    )
    actual = {int(i): int(result.hop[i]) for i in result.reached()}
    assert actual == expected
    assert result.discovered == len(expected)
