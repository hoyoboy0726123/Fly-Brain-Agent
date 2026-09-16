import math

import numpy as np
import pytest

from app.simulation import normalize_weight, normalize_weights


def test_log1p_transform() -> None:
    weights = normalize_weights([0, 1, 9, 99], "log1p", 1.0)
    assert weights.tolist() == pytest.approx([0.0, math.log(2), math.log(10), math.log(100)])
    assert normalize_weight(12, "log1p", 2.0) == pytest.approx(2 * math.log1p(12))


def test_other_transforms() -> None:
    assert normalize_weights([0, 4, 9], "linear", 0.5).tolist() == [0.0, 2.0, 4.5]
    assert normalize_weights([0, 4, 9], "sqrt", 1.0).tolist() == [0.0, 2.0, 3.0]
    assert normalize_weights([0, 4, 9], "binary", 3.0).tolist() == [0.0, 3.0, 3.0]


def test_weights_are_monotonic_and_non_negative() -> None:
    counts = np.arange(0, 3000)
    for transform in ("log1p", "linear", "sqrt", "binary"):
        weights = normalize_weights(counts, transform, 1.3)
        assert np.all(weights >= 0)
        assert np.all(np.diff(weights) >= 0)
        assert weights.dtype == np.float64


def test_scale_is_applied_linearly() -> None:
    base = normalize_weights([3, 7], "log1p", 1.0)
    scaled = normalize_weights([3, 7], "log1p", 4.0)
    assert scaled.tolist() == pytest.approx((base * 4).tolist())


@pytest.mark.parametrize("bad", [[-1], [math.nan], [math.inf]])
def test_invalid_counts_rejected(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        normalize_weights(bad, "log1p", 1.0)


def test_invalid_scale_and_transform_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_weights([1], "log1p", 0.0)
    with pytest.raises(ValueError):
        normalize_weights([1], "log1p", math.inf)
    with pytest.raises(ValueError, match="unknown weight transform"):
        normalize_weights([1], "cubic", 1.0)  # type: ignore[arg-type]


def test_empty_input() -> None:
    assert normalize_weights([], "log1p", 1.0).shape == (0,)
