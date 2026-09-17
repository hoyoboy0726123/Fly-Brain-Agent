"""SensorAdapter interface, the virtual looming sensor and the stimulus encoder (P7.0).

COMPUTATIONAL SENSOR MAPPING: virtual-world geometry is converted into the existing P4
``LoomingStimulus`` (direction left | center | right, intensity 0..1). The rule is a plain
angular-size heuristic chosen for the architecture demo; it is not a model of the fly retina
or of LC4 / LPLC2 tuning. A sensor never touches the brain: it only returns an observation.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from app.embodiment.models import (
    BodyState,
    SensoryObservation,
    VirtualLoomingSensorConfig,
    WorldState,
)
from app.sensors import LoomingStimulus

Direction = str  # "left" | "center" | "right"


class SensorAdapter(ABC):
    name: str = "SensorAdapter"

    @abstractmethod
    def observe(self, world_state: WorldState, body_state: BodyState) -> SensoryObservation: ...

    @abstractmethod
    def config_dict(self) -> dict: ...


def _wrap_angle(angle: float) -> float:
    """Wrap to (-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


class VirtualLoomingSensor(SensorAdapter):
    """Angular size + bearing of the nearest looming object → normalized observation."""

    name = "VirtualLoomingSensor"
    sensor_type = "virtual_looming"
    RULE = (
        "intensity = min(angular_size / saturation_angle, 1); angular_size = "
        "2·atan(size / distance); direction by bearing sign with a center band; objects "
        "outside the field of view give intensity 0"
    )

    def __init__(self, config: VirtualLoomingSensorConfig | None = None) -> None:
        self.config = config or VirtualLoomingSensorConfig()

    def config_dict(self) -> dict:
        return self.config.model_dump(mode="json")

    def observe(self, world_state: WorldState, body_state: BodyState) -> SensoryObservation:
        cfg = self.config
        candidates = world_state.of_type(cfg.object_type)
        base = {
            "sensor_type": self.sensor_type,
            "simulation_time": world_state.simulation_time,
            "step_index": world_state.step_index,
        }
        if not candidates:
            return SensoryObservation(
                **base,
                source=f"{self.name}: no {cfg.object_type} in world",
                values={"intensity": 0.0, "visible": 0.0},
                metadata={"direction": "center", "object_id": "", "rule": "no object → 0"},
            )
        nearest = min(candidates, key=lambda o: o.position.distance_to(body_state.position))
        offset = nearest.position.sub(body_state.position)
        distance = offset.norm()
        bearing = _wrap_angle(math.atan2(offset.y, offset.x) - body_state.heading)
        visible = abs(bearing) <= cfg.field_of_view_rad / 2.0
        if distance <= nearest.size:
            angular_size = math.pi  # inside the object: fills the field
        else:
            angular_size = 2.0 * math.atan(nearest.size / distance)
        intensity = min(angular_size / cfg.saturation_angle_rad, 1.0) if visible else 0.0
        if not visible or abs(bearing) <= cfg.center_half_angle_rad:
            direction: Direction = "center"  # out of view → no lateral cue (intensity is 0)
        elif bearing > 0:
            direction = "left"
        else:
            direction = "right"
        return SensoryObservation(
            **base,
            source=f"{self.name}: {nearest.object_id}",
            values={
                "intensity": intensity,
                "distance": distance,
                "angular_size_rad": angular_size,
                "bearing_rad": bearing,
                "visible": 1.0 if visible else 0.0,
            },
            metadata={"direction": direction, "object_id": nearest.object_id, "rule": self.RULE},
        )


class StimulusEncoder:
    """Observation → existing P4 ``LoomingStimulus`` (APPLICATION INPUT). No brain access."""

    name = "StimulusEncoder"

    def encode(self, observation: SensoryObservation) -> LoomingStimulus:
        direction = str(observation.metadata.get("direction", "center"))
        intensity = float(observation.values.get("intensity", 0.0))
        return LoomingStimulus(direction=direction, intensity=intensity)  # type: ignore[arg-type]
