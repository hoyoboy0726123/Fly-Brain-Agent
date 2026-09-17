"""WorldAdapter interface and the SIMPLIFIED computational test world (P7.0).

The world owns the environment state. ``SimpleWorldAdapter`` is a deterministic, non-visual
stand-in used to verify the architecture: one optional looming object approaches the origin
in a straight line at constant speed. Nothing here is biology.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from app.embodiment.errors import AdapterError
from app.embodiment.models import SimpleWorldConfig, Vector3, WorldObject, WorldState, validate_dt


class WorldAdapter(ABC):
    """Owns the environment state; advanced only through ``step(dt)``."""

    name: str = "WorldAdapter"

    @abstractmethod
    def reset(self) -> WorldState: ...

    @abstractmethod
    def step(self, dt: float) -> WorldState: ...

    @abstractmethod
    def get_state(self) -> WorldState: ...

    @abstractmethod
    def config_dict(self) -> dict: ...


class SimpleWorldAdapter(WorldAdapter):
    """Deterministic straight-line looming object (SIMPLIFIED COMPUTATIONAL WORLD)."""

    name = "SimpleWorldAdapter"

    def __init__(self, config: SimpleWorldConfig | None = None) -> None:
        self.config = config or SimpleWorldConfig()
        self._state: WorldState | None = None

    def config_dict(self) -> dict:
        return self.config.model_dump(mode="json")

    def reset(self) -> WorldState:
        cfg = self.config
        objects: list[WorldObject] = []
        if cfg.looming_object:
            azimuth = math.radians(cfg.azimuth_deg)
            direction = Vector3(x=math.cos(azimuth), y=math.sin(azimuth), z=0.0)
            objects.append(
                WorldObject(
                    object_id=cfg.object_id,
                    object_type=cfg.object_type,
                    position=Vector3(
                        x=direction.x * cfg.start_distance,
                        y=direction.y * cfg.start_distance,
                        z=cfg.height,
                    ),
                    velocity=direction.scale(-cfg.approach_speed),
                    size=cfg.object_size,
                    properties={
                        "approach_speed": cfg.approach_speed,
                        "azimuth_deg": cfg.azimuth_deg,
                    },
                )
            )
        self._state = WorldState(
            simulation_time=0.0,
            step_index=0,
            objects=objects,
            metadata={"adapter": self.name, "label": cfg.label},
        )
        return self._state

    def get_state(self) -> WorldState:
        if self._state is None:
            raise AdapterError("SimpleWorldAdapter.reset() must be called before use")
        return self._state

    def step(self, dt: float) -> WorldState:
        dt = validate_dt(dt)
        state = self.get_state()
        moved = [
            obj.model_copy(update={"position": obj.position.add(obj.velocity.scale(dt))})
            for obj in state.objects
        ]
        self._state = state.model_copy(
            update={
                "simulation_time": state.simulation_time + dt,
                "step_index": state.step_index + 1,
                "objects": moved,
            }
        )
        return self._state
