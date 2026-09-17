"""BodyAdapter interface and the SIMPLIFIED COMPUTATIONAL BODY (P7.0).

All body movement passes through a ``BodyAdapter``; ``BodyState`` is immutable, so nothing
else can change x, y, z, heading or velocity. ``SimpleBodyAdapter`` implements just enough
to verify the closed loop: IDLE keeps the body still, ESCAPE produces a deterministic
displacement along the current heading with a brief airborne phase. The numbers are
computational parameters, not Drosophila measurements; no legs, wings or physics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.embodiment.errors import AdapterError
from app.embodiment.models import (
    BodyState,
    MotorCommand,
    MotorCommandType,
    SimpleBodyConfig,
    Vector3,
    validate_dt,
)


class BodyAdapter(ABC):
    name: str = "BodyAdapter"

    @abstractmethod
    def reset(self) -> BodyState: ...

    @abstractmethod
    def apply_command(self, command: MotorCommand, dt: float) -> BodyState: ...

    @abstractmethod
    def step(self, dt: float) -> BodyState: ...

    @abstractmethod
    def get_state(self) -> BodyState: ...

    @abstractmethod
    def config_dict(self) -> dict: ...


class SimpleBodyAdapter(BodyAdapter):
    """SIMPLIFIED COMPUTATIONAL BODY: point body with heading, jump-like escape response."""

    name = "SimpleBodyAdapter"

    def __init__(self, config: SimpleBodyConfig | None = None) -> None:
        self.config = config or SimpleBodyConfig()
        self._state: BodyState | None = None
        self._airborne_remaining = 0.0
        self.escapes_applied = 0
        self.escapes_ignored_airborne = 0

    def config_dict(self) -> dict:
        return self.config.model_dump(mode="json")

    def reset(self) -> BodyState:
        cfg = self.config
        self._airborne_remaining = 0.0
        self.escapes_applied = 0
        self.escapes_ignored_airborne = 0
        self._state = BodyState(
            position=cfg.initial_position,
            heading=cfg.initial_heading,
            linear_velocity=Vector3(),
            grounded=True,
            simulation_time=0.0,
            step_index=0,
        )
        return self._state

    def get_state(self) -> BodyState:
        if self._state is None:
            raise AdapterError("SimpleBodyAdapter.reset() must be called before use")
        return self._state

    def apply_command(self, command: MotorCommand, dt: float) -> BodyState:
        validate_dt(dt)
        state = self.get_state()
        if command.command is MotorCommandType.IDLE:
            return state
        if command.command is MotorCommandType.ESCAPE:
            if not state.grounded:
                self.escapes_ignored_airborne += 1  # already airborne: no second impulse
                return state
            cfg = self.config
            forward = state.heading_vector.scale(cfg.escape_speed * command.magnitude)
            velocity = Vector3(
                x=forward.x, y=forward.y, z=cfg.escape_vertical_speed * command.magnitude
            )
            self._airborne_remaining = cfg.airborne_duration
            self.escapes_applied += 1
            self._state = state.model_copy(
                update={"linear_velocity": velocity, "grounded": cfg.airborne_duration <= 0}
            )
            return self._state
        raise AdapterError(f"SimpleBodyAdapter cannot execute {command.command!r}")

    def step(self, dt: float) -> BodyState:
        dt = validate_dt(dt)
        state = self.get_state()
        cfg = self.config
        position = state.position.add(state.linear_velocity.scale(dt))
        velocity = state.linear_velocity
        grounded = state.grounded
        if not grounded:
            self._airborne_remaining -= dt
            if self._airborne_remaining <= 1e-12:
                # landing: back on the ground plane, motion stops (computational rule)
                self._airborne_remaining = 0.0
                grounded = True
                position = Vector3(x=position.x, y=position.y, z=cfg.initial_position.z)
                velocity = Vector3()
        else:
            keep = max(0.0, 1.0 - cfg.ground_drag * dt)
            velocity = Vector3(x=velocity.x * keep, y=velocity.y * keep, z=0.0)
        self._state = state.model_copy(
            update={
                "position": position,
                "linear_velocity": velocity,
                "grounded": grounded,
                "simulation_time": state.simulation_time + dt,
                "step_index": state.step_index + 1,
            }
        )
        return self._state
