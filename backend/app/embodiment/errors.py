"""Fail-loud error types of the embodiment layer (P7.0)."""

from __future__ import annotations


class EmbodimentError(Exception):
    """Base class for every embodiment failure."""


class InvalidTimestepError(EmbodimentError, ValueError):
    """``dt`` is not a positive finite number."""


class InvalidStateError(EmbodimentError, ValueError):
    """A world / body / observation state is not finite or violates its invariants."""


class AdapterError(EmbodimentError):
    """An adapter was used before ``reset()`` or produced an inconsistent result."""


class UnsupportedActionError(EmbodimentError, ValueError):
    """The motor adapter has no mapping for a decoded action."""


class LoopLimitError(EmbodimentError):
    """The closed loop exceeded its configured number of steps."""
