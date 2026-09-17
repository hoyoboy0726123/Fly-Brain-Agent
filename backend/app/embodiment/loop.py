"""EmbodiedAgentLoop (P7.0): orchestration of World → Sensor → FlyBrain → Motor → Body → World.

The loop contains no biological logic. It coordinates existing components:

1. read WorldState            2. read BodyState              3. SensorAdapter.observe()
4. encode → LoomingStimulus   5. FlyBrain (P4 EscapeExperiment.run)   6. decoded action
7. MotorAdapter.translate()   8. BodyAdapter.apply_command() 9. BodyAdapter.step()
10. WorldAdapter.step()       11. record the step

The brain only ever receives a ``LoomingStimulus`` and only ever returns an ``EscapeResult``;
body coordinates change exclusively inside the ``BodyAdapter``.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from app import __version__
from app.behavior import EscapeResult
from app.embodiment.body import BodyAdapter
from app.embodiment.errors import AdapterError, LoopLimitError
from app.embodiment.models import (
    BodyState,
    BrainStepSummary,
    EmbodiedExperimentRecord,
    EmbodiedStepRecord,
    EmbodimentProvenance,
    LoopConfig,
    SimulationClock,
    TimingInfo,
    WorldState,
)
from app.embodiment.motor import MotorAdapter
from app.embodiment.sensors import SensorAdapter, StimulusEncoder
from app.embodiment.world import WorldAdapter
from app.sensors import LoomingStimulus


@runtime_checkable
class BrainAdapter(Protocol):
    """What the loop needs from FlyBrain — satisfied by the P4 ``EscapeExperiment``."""

    config: Any
    circuit: Any
    simulation_config: Any

    def run(
        self,
        stimulus: LoomingStimulus,
        steps: int | None = None,
        *,
        record_neuron_states: bool = True,
    ) -> EscapeResult: ...


class EmbodiedAgentLoop:
    def __init__(
        self,
        *,
        world: WorldAdapter,
        sensor: SensorAdapter,
        brain: BrainAdapter,
        motor: MotorAdapter,
        body: BodyAdapter,
        config: LoopConfig | None = None,
        encoder: StimulusEncoder | None = None,
    ) -> None:
        self.world = world
        self.sensor = sensor
        self.brain = brain
        self.motor = motor
        self.body = body
        self.config = config or LoopConfig()
        self.encoder = encoder or StimulusEncoder()
        self.clock = SimulationClock(dt=self.config.dt)
        self.records: list[EmbodiedStepRecord] = []
        self.initial_world: WorldState | None = None
        self.initial_body: BodyState | None = None
        self._started = time.perf_counter()

    # ------------------------------------------------------------------ lifecycle
    @property
    def neural_steps(self) -> int:
        return self.config.brain_steps_per_loop_step or int(self.brain.config.simulation_steps)

    def reset(self) -> tuple[WorldState, BodyState]:
        self.initial_world = self.world.reset()
        self.initial_body = self.body.reset()
        self.clock = SimulationClock(dt=self.config.dt)
        self.records = []
        self._started = time.perf_counter()
        return self.initial_world, self.initial_body

    def step(self) -> EmbodiedStepRecord:
        if self.initial_world is None or self.initial_body is None:
            raise AdapterError("EmbodiedAgentLoop.reset() must be called before step()")
        if self.clock.step_index >= self.config.max_steps:
            raise LoopLimitError(f"loop reached max_steps={self.config.max_steps}")
        clock = self.clock
        world_state = self.world.get_state()  # 1
        body_state = self.body.get_state()  # 2
        observation = self.sensor.observe(world_state, body_state)  # 3
        stimulus = self.encoder.encode(observation)  # 4
        result = self.brain.run(  # 5
            stimulus,
            steps=self.neural_steps,
            record_neuron_states=self.config.keep_full_brain_results,
        )
        decision = result.decision  # 6
        command = self.motor.translate(decision, clock)  # 7
        self.body.apply_command(command, clock.dt)  # 8
        body_after = self.body.step(clock.dt)  # 9
        world_after = self.world.step(clock.dt)  # 10
        record = EmbodiedStepRecord(  # 11
            step_index=clock.step_index,
            simulation_time=clock.simulation_time,
            dt=clock.dt,
            observation=observation,
            stimulus=stimulus.model_dump(mode="json"),
            brain=BrainStepSummary(
                escape_config_version=result.config_version,
                neural_steps=result.steps,
                neural_dt=result.simulation_config.dt,
                action=str(decision.action),
                output_spike_count=decision.output_spike_count,
                first_output_fire_step=decision.first_output_fire_step,
                fired_output_sides=list(decision.fired_output_sides),
                firing_events=result.firing_events,
                neurons_activated=result.neurons_activated,
                activity_label=result.activity_label,
            ),
            command=command,
            body_state=body_after,
            world_state=world_after,
            brain_result=result.model_dump(mode="json")
            if self.config.keep_full_brain_results
            else None,
        )
        self.records.append(record)
        self.clock = clock.advance()
        return record

    def run(self, steps: int) -> list[EmbodiedStepRecord]:
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise ValueError(f"steps must be a positive integer, got {steps!r}")
        return [self.step() for _ in range(steps)]

    # ------------------------------------------------------------------ provenance
    def provenance(self) -> EmbodimentProvenance:
        cfg = self.brain.config
        circuit = self.brain.circuit
        sim = self.brain.simulation_config
        return EmbodimentProvenance(
            dataset=circuit.dataset,
            dataset_version=circuit.dataset_version,
            canonical_selection_rule=circuit.canonical_graph.selection_rule,
            circuit_id=circuit.circuit_id,
            circuit_hash=circuit.provenance.circuit_hash or circuit.compute_hash(),
            biological_status=cfg.biological_status,
            escape_config_version=cfg.config_version,
            simulation_config=sim.model_dump(mode="json"),
            random_seed=self.config.random_seed,
            world_adapter=self.world.name,
            world_config=self.world.config_dict(),
            sensor_adapter=self.sensor.name,
            sensor_config=self.sensor.config_dict(),
            motor_adapter=self.motor.name,
            motor_config=self.motor.config_dict(),
            body_adapter=self.body.name,
            body_config=self.body.config_dict(),
            loop_config=self.config,
            timing=TimingInfo(
                loop_dt=self.config.dt,
                neural_dt=sim.dt,
                neural_steps_per_loop_step=self.neural_steps,
            ),
        )

    def record(self) -> EmbodiedExperimentRecord:
        if self.initial_world is None or self.initial_body is None:
            raise AdapterError("EmbodiedAgentLoop.reset() must be called before record()")
        actions = [r.brain.action for r in self.records]
        commands = [str(r.command.command) for r in self.records]
        first_escape = next(
            (r.step_index for r in self.records if r.command.command == "ESCAPE"), None
        )
        final_body = self.records[-1].body_state if self.records else self.initial_body
        return EmbodiedExperimentRecord(
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            runner_version=__version__,
            provenance=self.provenance(),
            initial_world=self.initial_world,
            initial_body=self.initial_body,
            steps=list(self.records),
            summary={
                "loop_steps": len(self.records),
                "actions": {a: actions.count(a) for a in sorted(set(actions))},
                "commands": {c: commands.count(c) for c in sorted(set(commands))},
                "first_escape_step": first_escape,
                "final_body_position": final_body.position.model_dump(),
                "displacement": final_body.position.distance_to(self.initial_body.position),
                "final_grounded": final_body.grounded,
            },
            runtime_seconds=round(time.perf_counter() - self._started, 6),
        )
