"""Fail-loud error types for graph building and circuit extraction (SDD §10)."""

from __future__ import annotations

from collections.abc import Sequence


class CircuitExtractionError(Exception):
    """Base class for every extractor failure."""


class GraphBuildError(CircuitExtractionError):
    """The normalized tables cannot be turned into a consistent graph."""


class MissingNeuronError(CircuitExtractionError):
    """A seed or target identifier does not exist in the canonical graph."""

    def __init__(self, role: str, missing: Sequence[str]) -> None:
        self.role = role
        self.missing = list(missing)
        shown = ", ".join(self.missing[:10]) + (" …" if len(self.missing) > 10 else "")
        super().__init__(f"{len(self.missing)} {role} neuron id(s) not found in the graph: {shown}")


class MaxNeuronsExceededError(CircuitExtractionError):
    """Traversal would exceed the hard ``max_neurons`` limit; nothing was truncated."""

    def __init__(self, limit: int, attempted: int, hop: int) -> None:
        self.limit = limit
        self.attempted = attempted
        self.hop = hop
        super().__init__(
            f"extraction aborted: adding hop {hop} would include {attempted:,} neurons, "
            f"exceeding the hard limit max_neurons={limit:,}"
        )


class ArtifactIntegrityError(CircuitExtractionError):
    """A stored circuit artifact does not match its recorded hash or schema."""
