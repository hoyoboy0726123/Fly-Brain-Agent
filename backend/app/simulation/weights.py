"""Structural synapse counts → computational synaptic weights.

``synapse_count`` is a biological structural observation (number of synaptic connections
between two bodies in MaleCNS). The simulation weight is a *computational transformation*
of it, chosen for numerical convenience; it is not an electrophysiological synaptic
strength. The transform and scale are configuration (``SimulationConfig.weight_transform``,
``weight_scale``) and every weight is positive (``sign_mode = unsigned_excitatory_only``).
"""

from __future__ import annotations

import numpy as np

from app.simulation.config import WeightTransform

TRANSFORMS: tuple[str, ...] = ("log1p", "linear", "sqrt", "binary")


def normalize_weights(
    synapse_counts: np.ndarray | list[int],
    transform: WeightTransform,
    weight_scale: float,
) -> np.ndarray:
    """Vectorised weight transform; returns float64 weights >= 0."""
    counts = np.asarray(synapse_counts, dtype=np.float64)
    if counts.size and (not np.all(np.isfinite(counts)) or np.any(counts < 0)):
        raise ValueError("synapse counts must be finite and non-negative")
    if not np.isfinite(weight_scale) or weight_scale <= 0:
        raise ValueError("weight_scale must be a positive finite number")
    if transform == "log1p":
        base = np.log1p(counts)
    elif transform == "linear":
        base = counts
    elif transform == "sqrt":
        base = np.sqrt(counts)
    elif transform == "binary":
        base = (counts > 0).astype(np.float64)
    else:
        raise ValueError(f"unknown weight transform {transform!r}; expected one of {TRANSFORMS}")
    with np.errstate(over="ignore", invalid="ignore"):
        weights = base * float(weight_scale)
    if weights.size and not np.all(np.isfinite(weights)):
        raise ValueError("weight transform produced non-finite values")
    return weights


def normalize_weight(synapse_count: int, transform: WeightTransform, weight_scale: float) -> float:
    """Scalar convenience wrapper around :func:`normalize_weights`."""
    return float(normalize_weights([synapse_count], transform, weight_scale)[0])
