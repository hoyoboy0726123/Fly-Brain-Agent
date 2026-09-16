"""Shared helpers for P2 tests: the synthetic fixture graph and a seeded random graph."""

from __future__ import annotations

import numpy as np
import pyarrow as pa

from app.circuits import ConnectivityGraph
from app.connectome import SyntheticFixtureAdapter
from app.connectome.fixture import FIXTURE_SELECTION_RULE
from app.connectome.normalize import build_connections_table, build_neurons_table

#: Edges of the synthetic fixture after dangling edges are dropped: (pre, post, weight).
FIXTURE_EDGES: list[tuple[str, str, int]] = [
    ("syn_001", "syn_003", 12),
    ("syn_001", "syn_004", 3),
    ("syn_002", "syn_004", 9),
    ("syn_002", "syn_005", 1),
    ("syn_003", "syn_006", 20),
    ("syn_003", "syn_005", 2),
    ("syn_004", "syn_006", 7),
    ("syn_004", "syn_007", 15),
    ("syn_005", "syn_007", 5),
    ("syn_006", "syn_003", 1),
    ("syn_007", "syn_007", 1),
]


def fixture_tables() -> tuple[pa.Table, pa.Table]:
    adapter = SyntheticFixtureAdapter()
    neurons = adapter.load_neurons()
    connections = adapter.load_connections(neurons["neuron_id"]).table
    return neurons, connections


def fixture_graph() -> ConnectivityGraph:
    neurons, connections = fixture_tables()
    return ConnectivityGraph.from_tables(
        neurons, connections, selection_rule=FIXTURE_SELECTION_RULE
    )


def random_graph(
    n_nodes: int = 200, n_edges: int = 1500, seed: int = 0
) -> tuple[ConnectivityGraph, dict[tuple[int, int], int]]:
    """Deterministic random directed graph; returns the graph and its edge dict."""
    rng = np.random.default_rng(seed)
    edges: dict[tuple[int, int], int] = {}
    while len(edges) < n_edges:
        pre, post = int(rng.integers(n_nodes)), int(rng.integers(n_nodes))
        edges.setdefault((pre, post), int(rng.integers(1, 40)))
    ids = [f"r{i:04d}" for i in range(n_nodes)]
    neurons = build_neurons_table(pa.array(ids), dataset="random", dataset_version="t")
    pairs = sorted(edges)
    connections = build_connections_table(
        pa.array([ids[p] for p, _ in pairs]),
        pa.array([ids[q] for _, q in pairs]),
        pa.array([edges[k] for k in pairs], pa.int64()),
        dataset="random",
        dataset_version="t",
    )
    graph = ConnectivityGraph.from_tables(neurons, connections, selection_rule="all")
    return graph, edges


def naive_bfs(
    edges: dict[tuple[int, int], int],
    sources: list[int],
    *,
    direction: str,
    max_hops: int,
    min_synapses: int,
) -> dict[int, int]:
    """Reference BFS over a plain edge dict; returns node -> hop."""
    adjacency: dict[int, set[int]] = {}
    for (pre, post), weight in edges.items():
        if weight < min_synapses:
            continue
        if direction == "downstream":
            adjacency.setdefault(pre, set()).add(post)
        else:
            adjacency.setdefault(post, set()).add(pre)
    hop = dict.fromkeys(sources, 0)
    frontier = list(sources)
    for level in range(1, max_hops + 1):
        nxt: set[int] = set()
        for node in frontier:
            for nbr in adjacency.get(node, ()):
                if nbr not in hop:
                    nxt.add(nbr)
        for node in nxt:
            hop[node] = level
        frontier = sorted(nxt)
        if not frontier:
            break
    return hop
