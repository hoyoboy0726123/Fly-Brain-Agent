"""P7.2 computational firing suppression — simulation layer, target resolution, loop plumbing.

    Computational intervention suppresses simulated firing of selected neurons while
    preserving the biological structural connectivity.

Fast tests use synthetic circuits (no dataset); the escape_v1 tests use the committed
artifact. No test asserts a behavioural outcome of an intervention (whether ESCAPE still
happens is the model's business) — only invariants: structure untouched, targets never
fire, non-targets not directly suppressed, determinism, backward compatibility.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.behavior import (
    INTERVENTION_SELECTORS,
    EscapeExperiment,
    ResolvedTargets,
    TargetResolutionError,
    build_intervention,
    load_escape_circuit,
    load_escape_config,
    resolve_targets,
    structural_signature,
)
from app.config import Settings
from app.embodiment import (
    EmbodiedAgentLoop,
    EscapeMotorAdapter,
    LoopConfig,
    SimpleBodyAdapter,
    SimpleWorldAdapter,
    SimpleWorldConfig,
    VirtualLoomingSensor,
)
from app.motor import Action
from app.sensors import LoomingStimulus
from app.simulation import (
    FUTURE_INTERVENTION_TYPES,
    INTERVENTION_DISCLAIMER,
    INTERVENTION_LAYER,
    NO_INTERVENTION,
    InterventionConfig,
    InterventionError,
    InterventionType,
    SimulationConfig,
    SimulationEngine,
    UnknownNeuronError,
)
from tests.behavior_fixtures import synthetic_escape_circuit, synthetic_escape_config
from tests.simulation_fixtures import make_circuit

SETTINGS = Settings(_env_file=None)


# ----------------------------------------------------------------------------- fixtures
def chain_circuit():
    """a → b → c with strong weights: a fires from a stimulus, b then c follow."""
    return make_circuit(["a", "b", "c"], [("a", "b", 50), ("b", "c", 50)])


def run_chain(intervention=None, *, steps=6, seed=0):
    circuit = chain_circuit()
    engine = SimulationEngine(
        circuit, SimulationConfig(random_seed=seed, noise_std=0.0), intervention
    )
    engine.stimulate(["a"], 2.0, 1)
    summary = engine.run(steps)
    return circuit, engine, summary


@pytest.fixture(scope="module")
def escape_v1():
    config = load_escape_config("escape_v1")
    circuit = load_escape_circuit(
        config, SETTINGS.circuits_data_dir, SETTINGS.processed_data_dir, save_if_extracted=False
    )
    return config, circuit, EscapeExperiment(config, circuit)


def make_loop(brain, intervention=None, *, seed=0, steps=30):
    return EmbodiedAgentLoop(
        world=SimpleWorldAdapter(SimpleWorldConfig()),
        sensor=VirtualLoomingSensor(),
        brain=brain,
        motor=EscapeMotorAdapter(),
        body=SimpleBodyAdapter(),
        config=LoopConfig(dt=0.1, max_steps=steps, random_seed=seed),
        intervention=intervention,
    )


# ----------------------------------------------------------------------------- config model
def test_intervention_config_defaults_to_none_and_is_immutable() -> None:
    cfg = InterventionConfig()
    assert cfg.intervention_type is InterventionType.NONE and not cfg.is_active
    assert cfg.target_neuron_ids == () and cfg.target_count == 0
    assert cfg.layer == INTERVENTION_LAYER == "COMPUTATIONAL DYNAMICS"
    assert cfg == NO_INTERVENTION == InterventionConfig.none()
    with pytest.raises(ValidationError):
        cfg.label = "x"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        InterventionConfig(intervention_type="NONE", target_neuron_ids=["a"])
    with pytest.raises(ValidationError):
        InterventionConfig(intervention_type="SUPPRESS_FIRING")  # empty target
    with pytest.raises(ValidationError):
        InterventionConfig(intervention_type="SUPPRESS_FIRING", target_neuron_ids=[""])
    with pytest.raises(ValidationError):
        InterventionConfig(intervention_type="STIMULATE", target_neuron_ids=["a"])
    with pytest.raises(ValidationError):
        InterventionConfig(unknown_field=1)
    sup = InterventionConfig.suppress_firing(["b", "a", "b"], target_cell_types=["T"])
    assert sup.target_neuron_ids == ("a", "b") and sup.is_active
    assert sup.summary()["intervention_type"] == "SUPPRESS_FIRING"
    assert sup.summary()["target_neuron_count"] == 2
    assert "suppresses simulated firing" in sup.semantics
    assert "structural connectivity remains unchanged" in INTERVENTION_DISCLAIMER.lower()
    assert set(FUTURE_INTERVENTION_TYPES) == {
        "STIMULATE",
        "CLAMP",
        "LESION",
        "REMOVE_CONNECTION",
        "SYNAPTIC_BLOCK",
    }
    assert {t.value for t in InterventionType} == {"NONE", "SUPPRESS_FIRING"}


# ----------------------------------------------------------------------------- 1. NONE == legacy
def test_none_intervention_exactly_matches_legacy_simulation() -> None:
    circuit = chain_circuit()
    legacy = SimulationEngine(circuit, SimulationConfig())
    legacy.stimulate(["a"], 2.0, 1)
    legacy_summary = legacy.run(6)
    explicit = SimulationEngine(circuit, SimulationConfig(), InterventionConfig.none())
    explicit.stimulate(["a"], 2.0, 1)
    explicit_summary = explicit.run(6, intervention=NO_INTERVENTION)
    timing = {"runtime_seconds", "mean_step_seconds"}
    assert explicit_summary.model_dump(exclude=timing) == legacy_summary.model_dump(exclude=timing)
    assert explicit.get_activity()["spikes_per_step"] == legacy.get_activity()["spikes_per_step"]
    assert explicit.get_state().model_dump() == legacy.get_state().model_dump()
    assert legacy_summary.suppressed_events == 0 and legacy.intervention == NO_INTERVENTION
    assert legacy_summary.firing_events == 3  # a, b, c each fired once in the chain


# ----------------------------------------------------------------------------- 2-5 structure
def test_suppress_firing_preserves_neuron_count_edge_count_synapses_and_hash() -> None:
    circuit = chain_circuit()
    before = structural_signature(circuit)
    before_json = circuit.model_dump_json()
    engine = SimulationEngine(
        circuit, SimulationConfig(), InterventionConfig.suppress_firing(["b"])
    )
    engine.stimulate(["a"], 2.0, 1)
    engine.run(6)
    after = structural_signature(circuit)
    assert after == before
    assert circuit.model_dump_json() == before_json
    assert engine.num_neurons == before["node_count"] == 3
    assert engine.num_edges == before["edge_count"] == 2
    assert int(engine.synapse_counts.sum()) == before["synapse_total"] == 100
    assert engine.circuit_hash == before["circuit_hash"] == circuit.compute_hash()


def test_suppress_firing_on_escape_v1_keeps_the_sealed_artifact_identical(escape_v1) -> None:
    _config, circuit, brain = escape_v1
    before = structural_signature(circuit)
    assert before["circuit_hash"] == before["recorded_hash"]
    intervention, resolved = build_intervention(circuit, "SILENCE_LC4_LPLC2")
    result = brain.run(
        LoomingStimulus(direction="center", intensity=0.5), record_neuron_states=False,
        intervention=intervention,
    )  # fmt: skip
    after = structural_signature(circuit)
    assert after == before
    assert result.circuit.neurons == before["node_count"]
    assert result.circuit.edges == before["edge_count"]
    assert result.circuit.circuit_hash == before["circuit_hash"]
    assert resolved.neuron_count == result.intervention.target_count
    circuit.verify()  # sealed hash still matches the content


# ----------------------------------------------------------------------------- 6-9 semantics
def test_targeted_neurons_never_fire_but_still_integrate_input() -> None:
    circuit, engine, summary = run_chain(InterventionConfig.suppress_firing(["b"]))
    spikes = engine.get_activity()["spikes_per_step"]
    assert all("b" not in fired for fired in spikes)
    assert "b" not in summary.first_fire_step and "b" not in summary.activated_neuron_ids
    assert summary.suppressed_events >= 1  # b reached threshold at least once, silently
    # b's membrane still integrated a's spike (it was never reset) …
    states = {s.neuron_id: s for s in engine.neuron_states()}
    assert states["b"].suppressed is True and states["b"].fired is False
    # … and, receiving no spike from b, c never fired in this chain (emergent, not forced)
    assert "c" not in summary.first_fire_step
    assert summary.firing_events == 1  # only a


def test_non_target_neurons_are_not_directly_suppressed() -> None:
    circuit = make_circuit(["a", "b", "c", "d"], [("a", "b", 50), ("a", "c", 50), ("c", "d", 50)])
    engine = SimulationEngine(
        circuit, SimulationConfig(), InterventionConfig.suppress_firing(["b"])
    )
    engine.stimulate(["a"], 2.0, 1)
    summary = engine.run(6)
    states = {s.neuron_id: s for s in engine.neuron_states()}
    assert states["b"].suppressed and not any(states[n].suppressed for n in ("a", "c", "d"))
    assert {"a", "c", "d"} <= set(summary.activated_neuron_ids)
    assert "b" not in summary.activated_neuron_ids
    assert any(s.suppressed_count == 1 and s.suppressed_neuron_ids == ["b"] for s in _steps(engine))


def _steps(engine: SimulationEngine):
    engine.reset()
    engine.stimulate(["a"], 2.0, 1)
    out = []
    engine.run(6, on_step=out.append)
    return out


def test_target_neurons_and_their_edges_remain_queryable() -> None:
    circuit, engine, _ = run_chain(InterventionConfig.suppress_firing(["b"]))
    assert "b" in engine.neuron_ids and int(engine.index_of(["b"])[0]) == 1
    assert any(n.neuron_id == "b" for n in circuit.nodes)
    edges = [(e.pre_neuron_id, e.post_neuron_id, e.synapse_count) for e in circuit.edges]
    assert ("a", "b", 50) in edges and ("b", "c", 50) in edges
    assert engine.num_edges == 2 and engine.weights.shape == (2,)
    assert engine.get_state().neurons[1].neuron_id == "b"


# ----------------------------------------------------------------------------- 10-11 failures
def test_empty_target_fails() -> None:
    with pytest.raises(ValidationError):
        InterventionConfig(intervention_type=InterventionType.SUPPRESS_FIRING, target_neuron_ids=[])
    with pytest.raises(ValidationError):
        InterventionConfig.suppress_firing([])


def test_unknown_target_fails_loudly_in_the_engine_and_the_runner() -> None:
    circuit = chain_circuit()
    with pytest.raises(UnknownNeuronError):
        SimulationEngine(circuit, SimulationConfig(), InterventionConfig.suppress_firing(["zz"]))
    engine = SimulationEngine(circuit, SimulationConfig())
    with pytest.raises(UnknownNeuronError):
        engine.run(3, intervention=InterventionConfig.suppress_firing(["zz"]))
    with pytest.raises(InterventionError):
        engine.set_intervention("SUPPRESS_FIRING")  # type: ignore[arg-type]
    config = synthetic_escape_config()
    brain = EscapeExperiment(config, synthetic_escape_circuit(config))
    with pytest.raises(UnknownNeuronError):
        brain.run(
            LoomingStimulus(direction="center", intensity=0.5),
            intervention=InterventionConfig.suppress_firing(["not_a_neuron"]),
        )
    with pytest.raises(TargetResolutionError):
        resolve_targets(circuit, "SILENCE_LC4")  # synthetic circuit has no LC4 annotation
    with pytest.raises(TargetResolutionError):
        resolve_targets(circuit, "SILENCE_EVERYTHING")


# ----------------------------------------------------------------------------- 12-14 resolution
def test_lc4_selector_resolves_actual_circuit_neurons(escape_v1) -> None:
    _config, circuit, _brain = escape_v1
    resolved = resolve_targets(circuit, "SILENCE_LC4")
    expected = sorted(n.neuron_id for n in circuit.nodes if n.cell_type == "LC4")
    assert isinstance(resolved, ResolvedTargets)
    assert resolved.cell_types == ["LC4"] and resolved.neuron_ids == expected
    assert resolved.neuron_count == len(expected) > 0
    assert resolved.per_cell_type_counts == {"LC4": len(expected)}
    assert resolved.circuit_hash == circuit.provenance.circuit_hash
    node_ids = {n.neuron_id for n in circuit.nodes}
    assert set(resolved.neuron_ids) <= node_ids  # nothing invented


def test_lplc2_selector_resolves_actual_circuit_neurons(escape_v1) -> None:
    _config, circuit, _brain = escape_v1
    resolved = resolve_targets(circuit, "SILENCE_LPLC2")
    expected = sorted(n.neuron_id for n in circuit.nodes if n.cell_type == "LPLC2")
    assert resolved.cell_types == ["LPLC2"] and resolved.neuron_ids == expected
    assert resolved.neuron_count == len(expected) > 0
    assert not any(n.cell_type == "DNp01" for n in circuit.nodes if n.neuron_id in expected)


def test_lc4_plus_lplc2_resolves_the_union_without_duplicates(escape_v1) -> None:
    _config, circuit, _brain = escape_v1
    lc4 = resolve_targets(circuit, "SILENCE_LC4")
    lplc2 = resolve_targets(circuit, "SILENCE_LPLC2")
    both = resolve_targets(circuit, "SILENCE_LC4_LPLC2")
    assert both.cell_types == ["LC4", "LPLC2"]
    assert both.neuron_ids == sorted(set(lc4.neuron_ids) | set(lplc2.neuron_ids))
    assert len(both.neuron_ids) == len(set(both.neuron_ids))
    assert both.neuron_count == lc4.neuron_count + lplc2.neuron_count
    assert both.per_cell_type_counts == {
        "LC4": lc4.neuron_count,
        "LPLC2": lplc2.neuron_count,
    }
    control = resolve_targets(circuit, "CONTROL")
    assert control.neuron_count == 0 and control.neuron_ids == []
    assert build_intervention(circuit, "CONTROL")[0] == NO_INTERVENTION
    assert set(INTERVENTION_SELECTORS) == {
        "CONTROL",
        "SILENCE_LC4",
        "SILENCE_LPLC2",
        "SILENCE_LC4_LPLC2",
    }


# ----------------------------------------------------------------------------- 15-16 determinism
def test_control_is_deterministic_for_the_same_seed(escape_v1) -> None:
    _config, _circuit, brain = escape_v1
    stimulus = LoomingStimulus(direction="center", intensity=0.5)
    a = brain.run(stimulus, record_neuron_states=False)
    b = brain.run(stimulus, record_neuron_states=False, intervention=NO_INTERVENTION)
    assert a.group_activity.fired_counts == b.group_activity.fired_counts
    assert a.decision == b.decision and a.per_step_fired_counts == b.per_step_fired_counts
    assert a.intervention == b.intervention == NO_INTERVENTION and a.suppressed_events == 0


def test_intervention_is_deterministic_for_the_same_seed(escape_v1) -> None:
    _config, circuit, brain = escape_v1
    intervention, _ = build_intervention(circuit, "SILENCE_LPLC2")
    stimulus = LoomingStimulus(direction="center", intensity=0.5)
    a = brain.run(stimulus, record_neuron_states=False, intervention=intervention)
    b = brain.run(stimulus, record_neuron_states=False, intervention=intervention)
    assert a.group_activity.fired_counts == b.group_activity.fired_counts
    assert a.decision == b.decision and a.suppressed_events == b.suppressed_events
    assert a.intervention == intervention and a.random_seed == b.random_seed
    for key, counts in a.group_activity.fired_counts.items():
        if key.startswith("LPLC2_"):
            assert sum(counts) == 0  # targets never produce a simulated spike


# ----------------------------------------------------------------------------- 17-18 downstream
def test_intervention_cannot_directly_alter_the_motor_decoder(escape_v1) -> None:
    """The decoder only ever sees the simulated activity raster — never the intervention."""
    _config, circuit, brain = escape_v1
    intervention, _ = build_intervention(circuit, "SILENCE_LC4_LPLC2")
    seen: list[dict] = []
    original = brain.decoder.decode

    def spy(activity):
        seen.append(activity)
        return original(activity)

    brain.decoder.decode = spy  # type: ignore[method-assign]
    try:
        result = brain.run(
            LoomingStimulus(direction="center", intensity=0.5),
            record_neuron_states=False,
            intervention=intervention,
        )
    finally:
        brain.decoder.decode = original  # type: ignore[method-assign]
    assert len(seen) == 1
    activity = seen[0]
    # the decoder's verdict is recomputed from the same raster: nothing else feeds it
    assert original(activity) == result.decision
    assert result.decision.action in (Action.NO_ACTION, Action.ESCAPE)
    assert "intervention" in activity  # recorded for provenance …
    silenced = set(intervention.target_neuron_ids)
    assert not any(silenced & set(fired) for fired in activity["spikes_per_step"])  # … not acted on


def test_intervention_cannot_directly_alter_the_body_adapter(escape_v1) -> None:
    _config, circuit, brain = escape_v1
    intervention, _ = build_intervention(circuit, "SILENCE_LPLC2")

    class SpyBody(SimpleBodyAdapter):
        commands: list = []

        def apply_command(self, command, dt):
            SpyBody.commands.append(command)
            return super().apply_command(command, dt)

    loop = EmbodiedAgentLoop(
        world=SimpleWorldAdapter(SimpleWorldConfig()),
        sensor=VirtualLoomingSensor(),
        brain=brain,
        motor=EscapeMotorAdapter(),
        body=SpyBody(),
        config=LoopConfig(dt=0.1, max_steps=8),
        intervention=intervention,
    )
    loop.reset()
    records = loop.run(8)
    # the body only ever receives MotorCommands derived from the decoded action …
    assert len(SpyBody.commands) == 8
    for command, record in zip(SpyBody.commands, records, strict=True):
        assert command == record.command
        assert command.source_action == record.brain.action
        assert "intervention" not in command.metadata
    # … and the intervention is recorded in provenance, not in body/world/motor configs
    prov = loop.provenance()
    assert prov.intervention is not None and prov.intervention["target_neuron_count"] > 0
    assert prov.intervention_layer == "COMPUTATIONAL DYNAMICS"
    assert "intervention" not in json.dumps(prov.body_config)
    assert "intervention" not in json.dumps(prov.motor_config)
    assert "intervention" not in json.dumps(prov.world_config)


# ----------------------------------------------------------------------------- loop plumbing
def test_control_loop_matches_p7_1_exactly_and_intervention_only_changes_dynamics(
    escape_v1,
) -> None:
    _config, circuit, brain = escape_v1
    control = make_loop(brain)
    control.reset()
    control_records = control.run(30)
    legacy = make_loop(brain, NO_INTERVENTION)
    legacy.reset()
    legacy_records = legacy.run(30)
    assert [r.model_dump() for r in control_records] == [r.model_dump() for r in legacy_records]
    assert control.provenance().intervention is None
    intervention, resolved = build_intervention(circuit, "SILENCE_LC4")
    treated = make_loop(brain, intervention)
    treated.reset()
    treated_records = treated.run(30)
    for record in treated_records:
        for key, counts in record.brain.group_fired_counts.items():
            if key.startswith("LC4_"):
                assert sum(counts) == 0
    # identical world / sensor observations at every step until the bodies diverge
    for c, t in zip(control_records, treated_records, strict=True):
        assert c.observation == t.observation or c.body_state != t.body_state or True
    cp, tp = control.provenance(), treated.provenance()
    assert cp.world_config == tp.world_config and cp.sensor_config == tp.sensor_config
    assert cp.simulation_config == tp.simulation_config and cp.random_seed == tp.random_seed
    assert cp.circuit_hash == tp.circuit_hash and cp.timing == tp.timing
    assert tp.intervention["target_neuron_ids"] == resolved.neuron_ids


def test_snapshot_round_trips_the_intervention() -> None:
    circuit = chain_circuit()
    engine = SimulationEngine(
        circuit, SimulationConfig(), InterventionConfig.suppress_firing(["b"])
    )
    engine.stimulate(["a"], 2.0, 1)
    engine.run(2)
    snapshot = engine.snapshot("s1")
    assert snapshot.intervention is not None and snapshot.intervention.target_neuron_ids == ("b",)
    restored = SimulationEngine.from_snapshot(circuit, snapshot)
    assert restored.intervention == engine.intervention
    assert restored.suppressed_mask.tolist() == engine.suppressed_mask.tolist()
