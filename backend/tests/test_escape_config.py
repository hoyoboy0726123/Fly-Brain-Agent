import pytest

from app.behavior import CONFIG_DIR, EscapeCircuitConfig, load_escape_config
from tests.behavior_fixtures import synthetic_escape_config


def test_synthetic_config_helpers() -> None:
    config = synthetic_escape_config()
    assert config.all_sensory_ids() == ["syn_001", "syn_002"]
    assert config.sensory_ids_for(("L",)) == ["syn_001"]
    assert config.all_output_ids() == ["syn_006", "syn_007"]
    extractor = config.extractor_config()
    assert extractor.seed_neuron_ids == ["syn_001", "syn_002"]
    assert extractor.target_neuron_ids == ["syn_006", "syn_007"]
    assert extractor.restrict_to_target_paths is True


def test_biological_config_rejects_synthetic_ids_and_missing_evidence() -> None:
    with pytest.raises(ValueError, match="synthetic dataset"):
        synthetic_escape_config(synthetic=False, biological_status="SUPPORTED")
    with pytest.raises(ValueError, match="synthetic ids"):
        synthetic_escape_config(synthetic=False, dataset="male-cns", biological_status="SUPPORTED")
    with pytest.raises(ValueError, match="citation"):
        synthetic_escape_config(
            synthetic=False,
            dataset="male-cns",
            biological_status="SUPPORTED",
            sensory_groups={"L": ["1"], "R": ["2"]},
            output_groups={"L": ["3"], "R": ["4"]},
        )
    with pytest.raises(ValueError, match="UNSUPPORTED"):
        synthetic_escape_config(
            synthetic=False,
            dataset="male-cns",
            biological_status="UNSUPPORTED",
            sensory_groups={"L": ["1"], "R": ["2"]},
            output_groups={"L": ["3"], "R": ["4"]},
            citations=[
                {
                    "key": "k",
                    "authors": "a",
                    "year": 2020,
                    "title": "t",
                    "venue": "v",
                    "claim": "c",
                    "verification": "x",
                    "confidence": "low",
                }
            ],
        )


def test_config_structure_validation() -> None:
    with pytest.raises(ValueError, match="sides L and R"):
        synthetic_escape_config(sensory_groups={"L": ["syn_001"]})
    with pytest.raises(ValueError, match="at least one neuron id"):
        synthetic_escape_config(output_groups={"L": [], "R": []})
    with pytest.raises(ValueError, match="both sensory and output"):
        synthetic_escape_config(output_groups={"L": ["syn_001"], "R": ["syn_007"]})
    with pytest.raises(ValueError):
        synthetic_escape_config(unexpected_field=1)


def test_config_round_trip(tmp_path) -> None:
    config = synthetic_escape_config()
    path = config.save(tmp_path / "cfg.json")
    assert EscapeCircuitConfig.load(path) == config
    assert load_escape_config(path) == config


def test_escape_v1_config_file_loads() -> None:
    config = load_escape_config("escape_v1")
    assert (CONFIG_DIR / "escape_v1.json").is_file()
    assert config.synthetic is False and config.biological_status == "PARTIALLY SUPPORTED"
