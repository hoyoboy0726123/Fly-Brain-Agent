"""Fail-loud error types of the COMPUTATIONAL DYNAMICS layer."""

from __future__ import annotations

from collections.abc import Sequence


class SimulationError(Exception):
    """Base class for every simulation failure."""


class CircuitCompatibilityError(SimulationError):
    """The circuit artifact cannot be simulated (e.g. edges reference unknown nodes)."""


class UnknownNeuronError(SimulationError):
    """A stimulus or query names a neuron that is not part of the circuit."""

    def __init__(self, missing: Sequence[str]) -> None:
        self.missing = list(missing)
        shown = ", ".join(self.missing[:10]) + (" …" if len(self.missing) > 10 else "")
        super().__init__(f"{len(self.missing)} neuron id(s) not in the circuit: {shown}")


class InvalidStimulusError(SimulationError, ValueError):
    """Stimulus arguments are out of range (negative duration, non-finite intensity, …)."""


class NumericalInstabilityError(SimulationError):
    """A membrane potential became NaN/Inf; the simulation is stopped."""


class SimulationLimitError(SimulationError):
    """A requested run exceeds ``max_steps_per_run``."""


class SnapshotMismatchError(SimulationError):
    """A snapshot references a different circuit than the one supplied."""


class InterventionError(SimulationError):
    """A computational intervention (P7.2) is invalid or not implemented."""
