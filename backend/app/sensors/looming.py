"""Looming-like stimulus (APPLICATION INPUT) and its mapping to injected current.

The stimulus schema is application-level and generic: ``stimulus = "looming"``, a
``direction`` (left | center | right) and an ``intensity`` in [0, 1]. The mapper converts
it into current injected into the configured sensory neuron group(s):

    current_per_step = intensity × mapping_gain          (COMPUTATIONAL rule)
    left  → group "L"    right → group "R"    center → both groups

``intensity`` is a dimensionless application quantity; it is NOT a measured firing rate,
luminance or angular velocity, and the injected current is a model input, not a
physiological current.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["left", "center", "right"]
Side = Literal["L", "R"]

DIRECTION_TO_SIDES: dict[str, tuple[Side, ...]] = {
    "left": ("L",),
    "right": ("R",),
    "center": ("L", "R"),
}
MAPPING_LABEL = (
    "COMPUTATIONAL stimulus→current mapping (current = intensity × gain into the ipsilateral "
    "sensory group); intensity is not a measured firing rate"
)


class LoomingStimulus(BaseModel):
    """Normalized application stimulus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stimulus: Literal["looming"] = "looming"
    direction: Direction
    intensity: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


class SensoryDrive(BaseModel):
    """What the mapper hands to the simulation: generic input injection."""

    model_config = ConfigDict(frozen=True)

    neuron_ids: list[str]
    sides: list[Side]
    injected_current: float = Field(ge=0.0, allow_inf_nan=False)
    duration_steps: int = Field(ge=1)
    mapping_rule: str
    label: str = MAPPING_LABEL


class StimulusMapper:
    """Maps a ``LoomingStimulus`` onto the configured sensory groups."""

    def __init__(
        self,
        sensory_groups: dict[str, list[str]],
        *,
        mapping_gain: float = 1.0,
        duration_steps: int = 5,
    ) -> None:
        missing = [side for side in ("L", "R") if side not in sensory_groups]
        if missing:
            raise ValueError(f"sensory_groups must define both sides; missing {missing}")
        if not all(sensory_groups[side] for side in ("L", "R")):
            raise ValueError("sensory groups must not be empty")
        if not (mapping_gain > 0) or mapping_gain != mapping_gain or mapping_gain == float("inf"):
            raise ValueError("mapping_gain must be a positive finite number")
        if duration_steps < 1:
            raise ValueError("duration_steps must be >= 1")
        self.sensory_groups = {side: sorted(set(ids)) for side, ids in sensory_groups.items()}
        self.mapping_gain = float(mapping_gain)
        self.duration_steps = int(duration_steps)

    def map(self, stimulus: LoomingStimulus) -> SensoryDrive:
        sides = DIRECTION_TO_SIDES[stimulus.direction]
        ids = sorted({nid for side in sides for nid in self.sensory_groups[side]})
        return SensoryDrive(
            neuron_ids=ids,
            sides=list(sides),
            injected_current=stimulus.intensity * self.mapping_gain,
            duration_steps=self.duration_steps,
            mapping_rule=(
                f"direction={stimulus.direction} → sides {list(sides)}; "
                f"current = intensity {stimulus.intensity} × gain {self.mapping_gain} = "
                f"{stimulus.intensity * self.mapping_gain:g} for {self.duration_steps} steps"
            ),
        )


class LoomingSensorAdapter:
    """SDD SensorAdapter: ``parse(event)`` → ``LoomingStimulus``; ``map_to_stimulus`` → drive."""

    def __init__(self, mapper: StimulusMapper) -> None:
        self.mapper = mapper

    @staticmethod
    def parse(event: dict[str, Any]) -> LoomingStimulus:
        return LoomingStimulus.model_validate(event)

    def map_to_stimulus(self, stimulus: LoomingStimulus) -> SensoryDrive:
        return self.mapper.map(stimulus)
