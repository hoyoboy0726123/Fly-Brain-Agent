"""MotorAdapter interface and the escape_v1 action → command mapping (P7.0).

COMPUTATIONAL MOTOR MAPPING: the decoded FlyBrain action (``NO_ACTION`` / ``ESCAPE``) becomes
a generic ``MotorCommand`` (``IDLE`` / ``ESCAPE``). The giant-fiber side reported by the
decoder is metadata and is deliberately NOT used: current evidence does not support
directional (left / right) escape decoding from DNp01 activity.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.embodiment.errors import UnsupportedActionError
from app.embodiment.models import EscapeMotorConfig, MotorCommand, MotorCommandType, SimulationClock
from app.motor import Action, MotorDecision


class MotorAdapter(ABC):
    name: str = "MotorAdapter"

    @abstractmethod
    def translate(self, decision: MotorDecision, clock: SimulationClock) -> MotorCommand: ...

    @abstractmethod
    def config_dict(self) -> dict: ...


class EscapeMotorAdapter(MotorAdapter):
    name = "EscapeMotorAdapter"
    MAPPING: dict[Action, MotorCommandType] = {
        Action.NO_ACTION: MotorCommandType.IDLE,
        Action.ESCAPE: MotorCommandType.ESCAPE,
    }

    def __init__(self, config: EscapeMotorConfig | None = None) -> None:
        self.config = config or EscapeMotorConfig()

    def config_dict(self) -> dict:
        return self.config.model_dump(mode="json")

    def translate(self, decision: MotorDecision, clock: SimulationClock) -> MotorCommand:
        try:
            command = self.MAPPING[Action(decision.action)]
        except (KeyError, ValueError) as exc:
            raise UnsupportedActionError(
                f"no motor mapping for action {decision.action!r}"
            ) from exc
        magnitude = self.config.escape_magnitude if command is MotorCommandType.ESCAPE else 0.0
        return MotorCommand(
            command=command,
            magnitude=magnitude,
            source_action=str(decision.action),
            simulation_time=clock.simulation_time,
            step_index=clock.step_index,
            metadata={
                "rule": "NO_ACTION → IDLE, ESCAPE → ESCAPE (application interpretation)",
                "output_spike_count": decision.output_spike_count,
                "gf_sides_metadata_only": ",".join(decision.fired_output_sides),
                "direction_decoded": False,
            },
        )
