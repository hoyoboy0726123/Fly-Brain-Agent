"""Synthetic circuits for P3 tests (no dataset required)."""

from __future__ import annotations

from app.circuits import (
    CanonicalGraphRef,
    Circuit,
    CircuitEdge,
    CircuitExtractor,
    CircuitNode,
    CircuitProvenance,
    ExtractionStats,
    ExtractorConfig,
)
from tests.circuit_fixtures import fixture_graph


def make_circuit(
    node_ids: list[str],
    edges: list[tuple[str, str, int]],
    *,
    circuit_id: str = "synthetic_test_circuit",
    seeds: list[str] | None = None,
    neurotransmitters: dict[str, str] | None = None,
) -> Circuit:
    """Build a sealed synthetic ``Circuit`` directly (dataset 'synthetic_unit')."""
    seeds = seeds or node_ids[:1]
    neurotransmitters = neurotransmitters or {}
    nodes = [
        CircuitNode(
            neuron_id=nid,
            minimum_hop_from_seed=0 if nid in seeds else 1,
            is_seed=nid in seeds,
            is_target=False,
            cell_type=f"SYN_{nid}",
            neurotransmitter=neurotransmitters.get(nid),
        )
        for nid in node_ids
    ]
    circuit = Circuit(
        circuit_id=circuit_id,
        dataset="synthetic_unit",
        dataset_version="test",
        canonical_graph=CanonicalGraphRef(
            selection_rule="synthetic unit test",
            neuron_count=len(node_ids),
            connection_count=len(edges),
            fingerprint="test",
        ),
        extractor_config=ExtractorConfig(
            seed_neuron_ids=seeds, max_hops=1, min_synapses=1, max_neurons=100
        ),
        seed_neurons=sorted(seeds),
        target_neurons=[],
        nodes=nodes,
        edges=[
            CircuitEdge(
                pre_neuron_id=p,
                post_neuron_id=q,
                synapse_count=w,
                dataset="synthetic_unit",
                dataset_version="test",
            )
            for p, q, w in edges
        ],
        stats=ExtractionStats(
            visited_neurons=len(node_ids),
            returned_neurons=len(node_ids),
            returned_edges=len(edges),
            examined_edges=len(edges),
            extraction_seconds=0.0,
        ),
        provenance=CircuitProvenance(
            extracted_at="2026-01-01T00:00:00+00:00",
            extractor_version="test",
            graph_fingerprint="test",
            notes="synthetic unit-test circuit",
        ),
    )
    return circuit.seal()


def chain_circuit(weights: tuple[int, int] = (20, 20)) -> Circuit:
    """A -> B -> C with the given synapse counts."""
    return make_circuit(
        ["A", "B", "C"], [("A", "B", weights[0]), ("B", "C", weights[1])], circuit_id="chain"
    )


def single_neuron_circuit() -> Circuit:
    return make_circuit(["solo"], [], circuit_id="solo")


def fixture_circuit() -> Circuit:
    """The P2 fixture extraction (6 nodes / 9 edges, downstream from syn_001)."""
    config = ExtractorConfig(
        seed_neuron_ids=["syn_001"], max_hops=2, min_synapses=1, max_neurons=50
    )
    return CircuitExtractor(fixture_graph()).extract(config, circuit_id="fixture_sim")
