"""MotorDecoder: simulated output-neuron activity → a small action set (APPLICATION DECODING).

Only actions the evidence supports are exposed. For escape_v1 the giant fiber responds
invariantly to stimulus azimuth (Jang et al. 2023), so no left/right direction is decoded:
the action set is ``NO_ACTION`` and ``ESCAPE``. The side of the firing output neuron is
reported as metadata only.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

DECODER_LABEL = (
    "APPLICATION DECODING of SIMULATED output activity; an action decoded from simulated "
    "activity on a biologically grounded structural circuit, not an observed behaviour"
)


class Action(StrEnum):
    NO_ACTION = "NO_ACTION"
    ESCAPE = "ESCAPE"


class MotorDecision(BaseModel):
    action: Action
    rule: str
    output_spike_count: int = Field(ge=0)
    first_output_fire_step: int | None = None
    fired_output_neuron_ids: list[str] = Field(default_factory=list)
    fired_output_sides: list[str] = Field(default_factory=list)
    label: str = DECODER_LABEL


class MotorDecoder:
    """``decode(activity) -> MotorDecision`` over the configured output groups."""

    def __init__(self, output_groups: dict[str, list[str]], *, min_output_spikes: int = 1) -> None:
        if min_output_spikes < 1:
            raise ValueError("min_output_spikes must be >= 1")
        self.output_groups = {side: sorted(set(ids)) for side, ids in output_groups.items()}
        self.side_of = {nid: side for side, ids in self.output_groups.items() for nid in ids}
        if not self.side_of:
            raise ValueError("output_groups must contain at least one neuron id")
        self.min_output_spikes = int(min_output_spikes)

    @property
    def output_neuron_ids(self) -> list[str]:
        return sorted(self.side_of)

    def decode(self, activity: dict[str, Any]) -> MotorDecision:
        """``activity`` is ``SimulationEngine.get_activity()`` (per-step lists of fired ids)."""
        spikes_per_step: list[list[str]] = activity.get("spikes_per_step", [])
        count = 0
        first_step: int | None = None
        fired: set[str] = set()
        for index, fired_ids in enumerate(spikes_per_step):
            hits = [nid for nid in fired_ids if nid in self.side_of]
            if hits:
                count += len(hits)
                fired.update(hits)
                if first_step is None:
                    first_step = index + 1  # steps are 1-based after the first update
        action = Action.ESCAPE if count >= self.min_output_spikes else Action.NO_ACTION
        return MotorDecision(
            action=action,
            rule=(
                f"ESCAPE if >= {self.min_output_spikes} simulated spike(s) in output neurons "
                f"{self.output_neuron_ids} during the run, else NO_ACTION; no left/right decoding"
            ),
            output_spike_count=count,
            first_output_fire_step=first_step,
            fired_output_neuron_ids=sorted(fired),
            fired_output_sides=sorted({self.side_of[nid] for nid in fired}),
        )
