"""BIOLOGICAL STRUCTURE layer: graph builder and bounded circuit extraction (P2).

- ``graph``      ``ConnectivityGraph``: CSR out/in adjacency over the canonical graph
- ``extractor``  ``CircuitExtractor``: deterministic bounded traversal, induced subgraph
- ``artifact``   ``Circuit`` JSON/Parquet artifact with provenance and integrity hash
- ``errors``     fail-loud exceptions
"""

from app.circuits.artifact import (
    CanonicalGraphRef,
    Circuit,
    CircuitEdge,
    CircuitNode,
    CircuitProvenance,
    ExtractionStats,
    ExtractorConfig,
    TargetReport,
)
from app.circuits.errors import (
    ArtifactIntegrityError,
    CircuitExtractionError,
    GraphBuildError,
    MaxNeuronsExceededError,
    MissingNeuronError,
)
from app.circuits.extractor import CircuitExtractor, TraversalResult, graph_source_paths
from app.circuits.graph import ConnectivityGraph, GraphLoadInfo

__all__ = [
    "ArtifactIntegrityError",
    "CanonicalGraphRef",
    "Circuit",
    "CircuitEdge",
    "CircuitExtractionError",
    "CircuitExtractor",
    "CircuitNode",
    "CircuitProvenance",
    "ConnectivityGraph",
    "ExtractionStats",
    "ExtractorConfig",
    "GraphBuildError",
    "GraphLoadInfo",
    "MaxNeuronsExceededError",
    "MissingNeuronError",
    "TargetReport",
    "TraversalResult",
    "graph_source_paths",
]
