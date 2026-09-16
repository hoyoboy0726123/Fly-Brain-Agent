import math

import pytest
from pydantic import ValidationError

from app.sensors import DIRECTION_TO_SIDES, LoomingSensorAdapter, LoomingStimulus, StimulusMapper

GROUPS = {"L": ["a2", "a1"], "R": ["b1"]}


def test_stimulus_schema_and_bounds() -> None:
    s = LoomingStimulus(direction="left", intensity=0.5)
    assert s.stimulus == "looming" and s.direction == "left" and s.intensity == 0.5
    for bad in (
        {"direction": "up", "intensity": 0.5},
        {"direction": "left", "intensity": 1.5},
        {"direction": "left", "intensity": -0.1},
        {"direction": "left", "intensity": math.nan},
        {"direction": "left", "intensity": 0.5, "stimulus": "odor"},
        {"direction": "left", "intensity": 0.5, "speed": 3},
        {"intensity": 0.5},
    ):
        with pytest.raises(ValidationError):
            LoomingStimulus(**bad)
    assert LoomingStimulus(direction="center", intensity=0.0).intensity == 0.0
    assert LoomingStimulus(direction="right", intensity=1.0).intensity == 1.0


def test_mapper_direction_handling() -> None:
    mapper = StimulusMapper(GROUPS, mapping_gain=2.0, duration_steps=3)
    left = mapper.map(LoomingStimulus(direction="left", intensity=0.5))
    assert left.neuron_ids == ["a1", "a2"] and left.sides == ["L"]
    assert left.injected_current == pytest.approx(1.0) and left.duration_steps == 3
    right = mapper.map(LoomingStimulus(direction="right", intensity=1.0))
    assert right.neuron_ids == ["b1"] and right.injected_current == pytest.approx(2.0)
    center = mapper.map(LoomingStimulus(direction="center", intensity=0.25))
    assert center.neuron_ids == ["a1", "a2", "b1"] and center.sides == ["L", "R"]
    assert "not a measured firing rate" in center.label and "gain 2.0" in center.mapping_rule
    assert DIRECTION_TO_SIDES == {"left": ("L",), "right": ("R",), "center": ("L", "R")}


def test_intensity_scales_current_linearly_and_zero_is_allowed() -> None:
    mapper = StimulusMapper(GROUPS)
    assert mapper.map(LoomingStimulus(direction="left", intensity=0.0)).injected_current == 0.0
    a = mapper.map(LoomingStimulus(direction="left", intensity=0.3)).injected_current
    b = mapper.map(LoomingStimulus(direction="left", intensity=0.6)).injected_current
    assert b == pytest.approx(2 * a)


def test_mapper_validation() -> None:
    with pytest.raises(ValueError, match="missing"):
        StimulusMapper({"L": ["a"]})
    with pytest.raises(ValueError, match="empty"):
        StimulusMapper({"L": [], "R": ["b"]})
    with pytest.raises(ValueError, match="mapping_gain"):
        StimulusMapper(GROUPS, mapping_gain=0.0)
    with pytest.raises(ValueError, match="duration_steps"):
        StimulusMapper(GROUPS, duration_steps=0)


def test_sensor_adapter_parses_events() -> None:
    adapter = LoomingSensorAdapter(StimulusMapper(GROUPS))
    stimulus = adapter.parse({"stimulus": "looming", "direction": "right", "intensity": 0.8})
    assert stimulus.direction == "right"
    assert adapter.map_to_stimulus(stimulus).neuron_ids == ["b1"]
    with pytest.raises(ValidationError):
        adapter.parse({"stimulus": "looming", "direction": "right", "intensity": 2})
