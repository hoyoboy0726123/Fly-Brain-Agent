"""P7.0 embodiment architecture: models, adapters, closed loop, determinism, boundaries.

Fast tests use the synthetic escape fixture (no dataset); one closed-loop test uses the
committed escape_v1 artifact. Nothing here changes or asserts new biology.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from app.behavior import EscapeExperiment, load_escape_circuit, load_escape_config
from app.config import Settings
from app.embodiment import (
    COMPUTATIONAL_SENSOR_INPUT,
    EMBODIMENT_DISCLAIMER,
    RESERVED_FUTURE_COMMANDS,
    SIMPLIFIED_COMPUTATIONAL_BODY,
    AdapterError,
    BodyState,
    EmbodiedAgentLoop,
    EscapeMotorAdapter,
    InvalidTimestepError,
    LoopConfig,
    LoopLimitError,
    MotorCommand,
    MotorCommandType,
    SensoryObservation,
    SimpleBodyAdapter,
    SimpleBodyConfig,
    SimpleWorldAdapter,
    SimpleWorldConfig,
    SimulationClock,
    StimulusEncoder,
    UnsupportedActionError,
    Vector3,
    VirtualLoomingSensor,
    VirtualLoomingSensorConfig,
    WorldObject,
    WorldState,
    validate_dt,
)
from app.motor import Action, MotorDecision
from app.sensors import LoomingStimulus
from tests.behavior_fixtures import synthetic_escape_circuit, synthetic_escape_config

# ----------------------------------------------------------------------------- helpers


def obj(object_id="o1", x=10.0, y=0.0, z=0.0, size=1.0, vx=0.0, object_type="looming_object"):
    return WorldObject(
        object_id=object_id,
        object_type=object_type,
        position=Vector3(x=x, y=y, z=z),
        velocity=Vector3(x=vx),
        size=size,
    )


def body(x=0.0, y=0.0, heading=0.0, t=0.0, step=0):
    return BodyState(
        position=Vector3(x=x, y=y), heading=heading, simulation_time=t, step_index=step
    )


def decision(action: Action, sides=()) -> MotorDecision:
    return MotorDecision(
        action=action,
        rule="test",
        output_spike_count=1 if action is Action.ESCAPE else 0,
        first_output_fire_step=3 if action is Action.ESCAPE else None,
        fired_output_sides=list(sides),
    )


@pytest.fixture(scope="module")
def synthetic_brain() -> EscapeExperiment:
    config = synthetic_escape_config()
    return EscapeExperiment(config, synthetic_escape_circuit(config))


def make_loop(brain, *, world=None, body_adapter=None, loop_config=None, sensor=None):
    return EmbodiedAgentLoop(
        world=world
        or SimpleWorldAdapter(SimpleWorldConfig(start_distance=6.0, approach_speed=10.0)),
        sensor=sensor or VirtualLoomingSensor(),
        brain=brain,
        motor=EscapeMotorAdapter(),
        body=body_adapter or SimpleBodyAdapter(),
        config=loop_config or LoopConfig(dt=0.1, max_steps=50),
    )


# ----------------------------------------------------------------------------- 1-4 models
def test_world_state_validation() -> None:
    state = WorldState(simulation_time=0.0, step_index=0, objects=[obj()])
    assert state.get("o1") is not None and state.of_type("looming_object")
    assert "VIRTUAL WORLD" in state.label and "not a biological measurement" in state.label
    with pytest.raises(ValidationError):
        WorldState(simulation_time=-1.0, step_index=0)
    with pytest.raises(ValidationError):
        WorldState(simulation_time=0.0, step_index=0, objects=[obj(), obj()])  # duplicate id
    with pytest.raises(ValidationError):
        WorldObject(object_id="", object_type="x", position=Vector3())
    with pytest.raises(ValidationError):
        obj(size=-1.0)
    with pytest.raises(ValidationError):
        state.step_index = 3  # frozen


def test_body_state_validation_and_immutability() -> None:
    state = body(heading=math.pi / 2)
    assert state.grounded and state.label == SIMPLIFIED_COMPUTATIONAL_BODY
    assert abs(state.heading_vector.y - 1.0) < 1e-12
    with pytest.raises(ValidationError):
        state.position = Vector3(x=1.0)  # the brain (or anyone) cannot mutate a BodyState
    with pytest.raises(ValidationError):
        BodyState(position=Vector3(), heading=0.0, simulation_time=-0.1, step_index=0)
    with pytest.raises(ValidationError):
        BodyState(position=Vector3(), heading=0.0, simulation_time=0.0, step_index=-1)


def test_sensory_observation_validation() -> None:
    observation = SensoryObservation(
        sensor_type="virtual_looming", simulation_time=0.0, step_index=0, source="test",
        values={"intensity": 0.4},
    )  # fmt: skip
    assert observation.interpretation_label == COMPUTATIONAL_SENSOR_INPUT
    assert "COMPUTATIONAL SENSOR INPUT" in observation.interpretation_label
    with pytest.raises(ValidationError):
        SensoryObservation(
            sensor_type="virtual_looming", simulation_time=0.0, step_index=0, source="test",
            interpretation_label="measured retinal signal",
        )  # fmt: skip
    with pytest.raises(ValidationError):
        SensoryObservation(sensor_type="", simulation_time=0.0, step_index=0, source="test")


def test_motor_command_validation_and_vocabulary() -> None:
    command = MotorCommand(
        command=MotorCommandType.ESCAPE, magnitude=1.0, source_action="ESCAPE",
        simulation_time=0.0, step_index=0,
    )  # fmt: skip
    assert command.command == "ESCAPE" and "COMPUTATIONAL MOTOR MAPPING" in command.label
    assert {m.value for m in MotorCommandType} == {"IDLE", "ESCAPE"}
    for reserved in RESERVED_FUTURE_COMMANDS:
        assert reserved not in MotorCommandType.__members__
    assert not any("LEFT" in m.value or "RIGHT" in m.value for m in MotorCommandType)
    with pytest.raises(ValidationError):
        MotorCommand(
            command="ESCAPE_LEFT", source_action="ESCAPE", simulation_time=0.0, step_index=0
        )
    with pytest.raises(ValidationError):
        MotorCommand(
            command=MotorCommandType.ESCAPE, magnitude=1.5, source_action="ESCAPE",
            simulation_time=0.0, step_index=0,
        )  # fmt: skip


# ----------------------------------------------------------------------------- 5-6 adapters
def test_simple_world_adapter_is_deterministic() -> None:
    config = SimpleWorldConfig(start_distance=20.0, approach_speed=10.0, azimuth_deg=0.0)
    a, b = SimpleWorldAdapter(config), SimpleWorldAdapter(config)
    first = a.reset()
    assert first.objects[0].position.x == 20.0 and first.objects[0].velocity.x == -10.0
    trajectory_a = [a.step(0.1).objects[0].position.x for _ in range(5)]
    b.reset()
    trajectory_b = [b.step(0.1).objects[0].position.x for _ in range(5)]
    assert trajectory_a == trajectory_b
    assert trajectory_a == pytest.approx([19.0, 18.0, 17.0, 16.0, 15.0])
    assert a.get_state().step_index == 5 and a.get_state().simulation_time == pytest.approx(0.5)
    assert "COMPUTATIONAL WORLD PARAMETERS" in config.label
    with pytest.raises(AdapterError):
        SimpleWorldAdapter(config).get_state()  # before reset


def test_simple_body_adapter_is_deterministic_and_labelled() -> None:
    config = SimpleBodyConfig(escape_speed=5.0, escape_vertical_speed=3.0, airborne_duration=0.3)
    clock = SimulationClock(dt=0.1)
    idle = MotorCommand(
        command=MotorCommandType.IDLE, source_action="NO_ACTION", simulation_time=0, step_index=0
    )
    escape = MotorCommand(
        command=MotorCommandType.ESCAPE, magnitude=1.0, source_action="ESCAPE",
        simulation_time=0, step_index=0,
    )  # fmt: skip

    def trajectory():
        adapter = SimpleBodyAdapter(config)
        adapter.reset()
        adapter.apply_command(idle, clock.dt)
        states = [adapter.step(clock.dt)]
        adapter.apply_command(escape, clock.dt)
        states += [adapter.step(clock.dt) for _ in range(4)]
        return [(s.position.x, s.position.z, s.grounded) for s in states]

    first, second = trajectory(), trajectory()
    assert first == second
    assert first[0] == (0.0, 0.0, True)  # IDLE: no movement
    assert first[1] == pytest.approx((0.5, 0.3, False))  # ESCAPE: deterministic displacement
    assert first[2] == pytest.approx((1.0, 0.6, False))
    assert first[3][2] is True and first[3][1] == 0.0  # landed after airborne_duration
    assert first[4] == first[3]  # at rest after landing
    assert SimpleBodyAdapter(config).reset().label == SIMPLIFIED_COMPUTATIONAL_BODY
    assert "not biological measurements" in config.label


def test_escape_while_airborne_is_recorded_but_adds_no_impulse() -> None:
    adapter = SimpleBodyAdapter(SimpleBodyConfig(airborne_duration=1.0))
    adapter.reset()
    escape = MotorCommand(
        command=MotorCommandType.ESCAPE, magnitude=1.0, source_action="ESCAPE",
        simulation_time=0, step_index=0,
    )  # fmt: skip
    adapter.apply_command(escape, 0.1)
    adapter.step(0.1)
    before = adapter.get_state()
    adapter.apply_command(escape, 0.1)
    assert adapter.get_state() == before
    assert adapter.escapes_applied == 1 and adapter.escapes_ignored_airborne == 1


# ----------------------------------------------------------------------------- 7-8 motor mapping
def test_no_action_maps_to_idle_and_escape_maps_to_escape() -> None:
    adapter = EscapeMotorAdapter()
    clock = SimulationClock(dt=0.1, step_index=4, simulation_time=0.4)
    idle = adapter.translate(decision(Action.NO_ACTION), clock)
    assert idle.command is MotorCommandType.IDLE and idle.magnitude == 0.0
    assert idle.source_action == "NO_ACTION" and idle.step_index == 4
    escape = adapter.translate(decision(Action.ESCAPE, sides=("L",)), clock)
    assert escape.command is MotorCommandType.ESCAPE and escape.magnitude == 1.0
    assert escape.metadata["direction_decoded"] is False
    assert escape.metadata["gf_sides_metadata_only"] == "L"
    both = adapter.translate(decision(Action.ESCAPE, sides=("L", "R")), clock)
    right = adapter.translate(decision(Action.ESCAPE, sides=("R",)), clock)
    assert escape.command == both.command == right.command  # GF side never changes the command
    bad = decision(Action.ESCAPE).model_copy(update={"action": "ESCAPE_LEFT"})
    with pytest.raises(UnsupportedActionError):
        adapter.translate(bad, clock)


# ----------------------------------------------------------------------------- sensor
def test_virtual_sensor_geometry_rules() -> None:
    sensor = VirtualLoomingSensor(VirtualLoomingSensorConfig(saturation_angle_rad=math.pi / 2))
    world = WorldState(simulation_time=0.0, step_index=0, objects=[obj(x=10.0, size=1.0)])
    observation = sensor.observe(world, body())
    expected = min(2 * math.atan(1.0 / 10.0) / (math.pi / 2), 1.0)
    assert observation.values["intensity"] == pytest.approx(expected)
    assert observation.metadata["direction"] == "center"
    assert observation.interpretation_label == COMPUTATIONAL_SENSOR_INPUT
    left = sensor.observe(
        WorldState(simulation_time=0, step_index=0, objects=[obj(x=5.0, y=5.0)]), body()
    )
    right = sensor.observe(
        WorldState(simulation_time=0, step_index=0, objects=[obj(x=5.0, y=-5.0)]), body()
    )
    assert left.metadata["direction"] == "left" and right.metadata["direction"] == "right"
    behind = sensor.observe(
        WorldState(simulation_time=0, step_index=0, objects=[obj(x=-5.0)]), body()
    )
    assert behind.values["intensity"] == 0.0 and behind.values["visible"] == 0.0
    inside = sensor.observe(
        WorldState(simulation_time=0, step_index=0, objects=[obj(x=0.5, size=1.0)]), body()
    )
    assert inside.values["intensity"] == 1.0
    empty = sensor.observe(WorldState(simulation_time=0, step_index=0), body())
    assert empty.values["intensity"] == 0.0 and empty.metadata["direction"] == "center"
    stimulus = StimulusEncoder().encode(left)
    assert isinstance(stimulus, LoomingStimulus) and stimulus.direction == "left"


# ----------------------------------------------------------------------------- 9 boundary
def test_brain_cannot_directly_mutate_body_state(synthetic_brain) -> None:
    calls: list[tuple] = []
    body_adapter = SimpleBodyAdapter()

    class SpyBrain:
        config = synthetic_brain.config
        circuit = synthetic_brain.circuit
        simulation_config = synthetic_brain.simulation_config

        def run(self, stimulus, steps=None, *, record_neuron_states=True):
            calls.append((type(stimulus).__name__, steps, body_adapter.get_state()))
            return synthetic_brain.run(
                stimulus, steps=steps, record_neuron_states=record_neuron_states
            )

    loop = make_loop(
        SpyBrain(),
        body_adapter=body_adapter,
        world=SimpleWorldAdapter(SimpleWorldConfig(start_distance=1.5, approach_speed=0.0)),
    )
    loop.reset()
    before = body_adapter.get_state()
    record = loop.step()
    stimulus_type, _, body_seen_by_brain = calls[0]
    assert stimulus_type == "LoomingStimulus"  # the brain only receives a stimulus
    assert body_seen_by_brain == before  # unchanged while the brain ran
    assert record.command.command is MotorCommandType.ESCAPE  # object is close → ESCAPE
    assert record.body_state != before  # …and only the BodyAdapter moved the body afterwards
    with pytest.raises(ValidationError):
        record.body_state.position = Vector3(x=99.0)


# ----------------------------------------------------------------------------- 10 ordering
def test_closed_loop_step_ordering(synthetic_brain) -> None:
    order: list[str] = []

    class SpyWorld(SimpleWorldAdapter):
        def get_state(self):
            order.append("world.get_state")
            return super().get_state()

        def step(self, dt):
            order.append("world.step")
            return super().step(dt)

    class SpyBody(SimpleBodyAdapter):
        def get_state(self):
            order.append("body.get_state")
            return super().get_state()

        def apply_command(self, command, dt):
            order.append("body.apply_command")
            return super().apply_command(command, dt)

        def step(self, dt):
            order.append("body.step")
            return super().step(dt)

    class SpySensor(VirtualLoomingSensor):
        def observe(self, world_state, body_state):
            order.append("sensor.observe")
            return super().observe(world_state, body_state)

    class SpyMotor(EscapeMotorAdapter):
        def translate(self, decision, clock):
            order.append("motor.translate")
            return super().translate(decision, clock)

    class SpyBrain:
        config = synthetic_brain.config
        circuit = synthetic_brain.circuit
        simulation_config = synthetic_brain.simulation_config

        def run(self, stimulus, steps=None, *, record_neuron_states=True):
            order.append("brain.run")
            return synthetic_brain.run(
                stimulus, steps=steps, record_neuron_states=record_neuron_states
            )

    loop = EmbodiedAgentLoop(
        world=SpyWorld(SimpleWorldConfig()), sensor=SpySensor(), brain=SpyBrain(),
        motor=SpyMotor(), body=SpyBody(), config=LoopConfig(dt=0.1),
    )  # fmt: skip
    loop.reset()
    order.clear()
    loop.step()
    expected = [
        "world.get_state", "body.get_state", "sensor.observe", "brain.run", "motor.translate",
        "body.apply_command", "body.step", "world.step",
    ]  # fmt: skip
    first_seen = list(dict.fromkeys(order))  # adapters call their own get_state() internally
    assert first_seen == expected
    assert order[0] == "world.get_state" and order[1] == "body.get_state"
    assert order.index("sensor.observe") < order.index("brain.run") < order.index("motor.translate")
    assert (
        order.index("motor.translate")
        < order.index("body.apply_command")
        < order.index("body.step")
    )
    assert order.index("body.step") < order.index("world.step")
    assert loop.clock.step_index == 1 and loop.records[0].step_index == 0


# ----------------------------------------------------------------------------- 11 reproducibility
def test_closed_loop_is_reproducible(synthetic_brain) -> None:
    def run_once():
        loop = make_loop(synthetic_brain)
        loop.reset()
        loop.run(8)
        record = loop.record()
        return record.model_dump(mode="json", exclude={"created_at", "runtime_seconds"})

    first, second = run_once(), run_once()
    assert first == second
    provenance = first["provenance"]
    required = (
        "dataset", "dataset_version", "canonical_selection_rule", "circuit_id", "circuit_hash",
        "simulation_config", "random_seed", "world_config", "sensor_config", "motor_config",
        "body_config", "loop_config", "timing",
    )  # fmt: skip
    assert all(key in provenance for key in required)
    assert provenance["disclaimer"] == EMBODIMENT_DISCLAIMER
    assert provenance["timing"]["loop_dt"] == 0.1 and provenance["timing"]["neural_dt"] == 1.0
    assert (
        provenance["timing"]["neural_steps_per_loop_step"]
        == synthetic_brain.config.simulation_steps
    )


def test_closed_loop_produces_escape_when_the_object_arrives(synthetic_brain) -> None:
    loop = make_loop(
        synthetic_brain,
        world=SimpleWorldAdapter(SimpleWorldConfig(start_distance=6.0, approach_speed=10.0)),
    )
    loop.reset()
    records = loop.run(6)
    actions = [r.brain.action for r in records]
    commands = [r.command.command for r in records]
    assert actions[0] == "NO_ACTION" and commands[0] == "IDLE"
    assert "ESCAPE" in actions and MotorCommandType.ESCAPE in commands
    assert records[-1].body_state.position.x > 0.0  # the SIMPLE body moved only after ESCAPE
    first_escape = next(i for i, c in enumerate(commands) if c == MotorCommandType.ESCAPE)
    assert all(r.body_state.position == Vector3() for r in records[:first_escape])
    summary = loop.record().summary
    assert summary["first_escape_step"] == first_escape and summary["displacement"] > 0


# ----------------------------------------------------------------------------- 12 world differences
def test_different_initial_world_changes_the_observation(synthetic_brain) -> None:
    def first_observation(**world_kwargs):
        loop = make_loop(
            synthetic_brain, world=SimpleWorldAdapter(SimpleWorldConfig(**world_kwargs))
        )
        loop.reset()
        return loop.step().observation

    near = first_observation(start_distance=3.0, approach_speed=0.0)
    far = first_observation(start_distance=30.0, approach_speed=0.0)
    assert near.values["intensity"] > far.values["intensity"]
    left = first_observation(start_distance=5.0, approach_speed=0.0, azimuth_deg=60.0)
    right = first_observation(start_distance=5.0, approach_speed=0.0, azimuth_deg=-60.0)
    assert left.metadata["direction"] == "left" and right.metadata["direction"] == "right"
    none = first_observation(looming_object=False)
    assert none.values["intensity"] == 0.0


# ----------------------------------------------------------------------------- 13 reset
def test_reset_restores_initial_state(synthetic_brain) -> None:
    loop = make_loop(synthetic_brain)
    initial_world, initial_body = loop.reset()
    loop.run(5)
    assert loop.world.get_state() != initial_world and loop.clock.step_index == 5
    world_again, body_again = loop.reset()
    assert world_again == initial_world and body_again == initial_body
    assert loop.clock.step_index == 0 and loop.clock.simulation_time == 0.0 and loop.records == []
    assert loop.body.get_state() == initial_body


# ----------------------------------------------------------------------------- 14-15 fail loudly
@pytest.mark.parametrize("dt", [0.0, -0.1, math.nan, math.inf, "0.1", True])
def test_invalid_dt_fails_loudly(dt) -> None:
    with pytest.raises(InvalidTimestepError):
        validate_dt(dt)
    with pytest.raises((InvalidTimestepError, ValidationError)):
        LoopConfig(dt=dt)
    world = SimpleWorldAdapter()
    world.reset()
    with pytest.raises(InvalidTimestepError):
        world.step(dt)
    body_adapter = SimpleBodyAdapter()
    body_adapter.reset()
    with pytest.raises(InvalidTimestepError):
        body_adapter.step(dt)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_state_fails_loudly(value) -> None:
    with pytest.raises(ValidationError):
        Vector3(x=value)
    with pytest.raises(ValidationError):
        BodyState(position=Vector3(), heading=value, simulation_time=0.0, step_index=0)
    with pytest.raises(ValidationError):
        WorldState(
            simulation_time=value if value > 0 else 0.0, step_index=0, objects=[obj(size=value)]
        )
    with pytest.raises(ValidationError):
        SensoryObservation(
            sensor_type="s",
            simulation_time=0.0,
            step_index=0,
            source="x",
            values={"intensity": value},
        )
    with pytest.raises(ValidationError):
        SimpleBodyConfig(escape_speed=value)


def test_loop_limits_and_misuse_fail_loudly(synthetic_brain) -> None:
    loop = make_loop(synthetic_brain, loop_config=LoopConfig(dt=0.1, max_steps=2))
    with pytest.raises(AdapterError):
        loop.step()  # reset() first
    loop.reset()
    loop.run(2)
    with pytest.raises(LoopLimitError):
        loop.step()
    with pytest.raises(ValueError):
        loop.run(0)


# ----------------------------------------------------------------------------- escape_v1 loop
def test_closed_loop_with_committed_escape_v1_artifact() -> None:
    settings = Settings(_env_file=None, environment="test")
    config = load_escape_config("escape_v1")
    circuit = load_escape_circuit(config, settings.circuits_data_dir, save_if_extracted=False)
    brain = EscapeExperiment(config, circuit)
    loop = make_loop(
        brain,
        world=SimpleWorldAdapter(SimpleWorldConfig(start_distance=20.0, approach_speed=10.0)),
        loop_config=LoopConfig(dt=0.1, max_steps=40),
    )
    loop.reset()
    records = loop.run(25)
    record = loop.record()
    assert record.provenance.circuit_id == "escape_v1"
    assert record.provenance.circuit_hash == config.expected_circuit_hash
    assert record.provenance.biological_status == "PARTIALLY SUPPORTED"
    assert record.provenance.dataset == "male-cns" and record.provenance.dataset_version == "v1.0"
    assert record.provenance.canonical_selection_rule == 'status == "Traced"'
    actions = [r.brain.action for r in records]
    assert set(actions) <= {"NO_ACTION", "ESCAPE"}
    assert all(not r.command.command.endswith(("LEFT", "RIGHT")) for r in records)
    intensities = [r.observation.values["intensity"] for r in records[:18]]
    assert intensities == sorted(intensities)  # approaching object → non-decreasing intensity
    # the same escape_v1 model as P4/P5: NO_ACTION at low intensity, ESCAPE once the object is close
    assert actions[0] == "NO_ACTION" and "ESCAPE" in actions
    assert record.summary["displacement"] > 0.0
    assert all("SIMULATED" in r.brain.activity_label for r in records)
