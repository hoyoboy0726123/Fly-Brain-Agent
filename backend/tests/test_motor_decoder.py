import pytest

from app.motor import Action, MotorDecoder

GROUPS = {"L": ["gfL"], "R": ["gfR"]}


def activity(*steps: list[str]) -> dict:
    return {"spikes_per_step": list(steps)}


def test_no_action_without_output_spikes() -> None:
    decision = MotorDecoder(GROUPS).decode(activity(["s1"], ["s2", "x"], []))
    assert decision.action is Action.NO_ACTION and decision.output_spike_count == 0
    assert decision.first_output_fire_step is None and decision.fired_output_neuron_ids == []
    assert "APPLICATION DECODING" in decision.label and "no left/right" in decision.rule


def test_escape_when_output_fires_and_side_is_metadata_only() -> None:
    decision = MotorDecoder(GROUPS).decode(activity(["s1"], ["gfL"], ["gfL", "gfR"]))
    assert decision.action is Action.ESCAPE
    assert decision.output_spike_count == 3 and decision.first_output_fire_step == 2
    assert decision.fired_output_neuron_ids == ["gfL", "gfR"] and decision.fired_output_sides == [
        "L",
        "R",
    ]
    assert set(Action) == {Action.NO_ACTION, Action.ESCAPE}  # no directional actions exposed


def test_min_output_spikes_threshold() -> None:
    strict = MotorDecoder(GROUPS, min_output_spikes=2)
    assert strict.decode(activity(["gfL"])).action is Action.NO_ACTION
    assert strict.decode(activity(["gfL"], ["gfR"])).action is Action.ESCAPE
    with pytest.raises(ValueError):
        MotorDecoder(GROUPS, min_output_spikes=0)
    with pytest.raises(ValueError):
        MotorDecoder({"L": [], "R": []})


def test_decoder_is_deterministic_and_ignores_non_output_neurons() -> None:
    decoder = MotorDecoder(GROUPS)
    raster = activity(["a", "b"], ["gfR", "c"], ["d"])
    assert decoder.decode(raster) == decoder.decode(raster)
    assert decoder.output_neuron_ids == ["gfL", "gfR"]
