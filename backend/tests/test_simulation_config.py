import math

import pytest
from pydantic import ValidationError

from app.simulation import PARAMETER_LABEL, SimulationConfig


def test_defaults_are_labelled_computational() -> None:
    config = SimulationConfig()
    assert config.label == PARAMETER_LABEL
    assert "NOT MEASURED MALECNS PARAMETERS" in config.label
    assert config.sign_mode == "unsigned_excitatory_only"
    assert config.decay_factor == pytest.approx(1 - 0.2 * 1.0)


def test_config_is_frozen_and_forbids_unknown_fields() -> None:
    config = SimulationConfig()
    with pytest.raises(ValidationError):
        config.threshold = 5.0  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SimulationConfig(measured_from_fly=True)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "overrides",
    [
        {"dt": 0.0},
        {"dt": -1.0},
        {"dt": math.nan},
        {"dt": math.inf},
        {"threshold": 0.0},  # == reset_potential
        {"threshold": -1.0},
        {"threshold": math.nan},
        {"reset_potential": 1.0},  # >= threshold
        {"max_potential": 1.0},  # <= threshold
        {"leak": -0.1},
        {"leak": 1.5},  # leak*dt > 1 -> unstable
        {"dt": 2.0, "leak": 0.75},  # leak*dt = 1.5
        {"refractory_steps": -1},
        {"weight_scale": 0.0},
        {"weight_scale": math.inf},
        {"stimulus_gain": 0.0},
        {"noise_std": -0.1},
        {"max_steps_per_run": 0},
        {"random_seed": -1},
        {"weight_transform": "cubic"},
        {"sign_mode": "signed_by_neurotransmitter"},
        {"label": "MEASURED"},
    ],
)
def test_invalid_configurations_are_rejected(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        SimulationConfig(**overrides)


def test_boundary_values_allowed() -> None:
    assert SimulationConfig(leak=0.0).decay_factor == 1.0
    assert SimulationConfig(leak=1.0, dt=1.0).decay_factor == 0.0
    assert SimulationConfig(refractory_steps=0).refractory_steps == 0
    assert (
        SimulationConfig(reset_potential=-2.0, resting_potential=-1.0, threshold=0.5).threshold
        == 0.5
    )


def test_round_trip_json() -> None:
    config = SimulationConfig(threshold=1.5, weight_transform="sqrt", random_seed=7)
    assert SimulationConfig.model_validate_json(config.model_dump_json()) == config
