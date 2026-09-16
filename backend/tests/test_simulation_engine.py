import math

import numpy as np
import pytest

from app.simulation import (
    CircuitCompatibilityError,
    InvalidStimulusError,
    NumericalInstabilityError,
    SimulationConfig,
    SimulationEngine,
    SimulationLimitError,
    UnknownNeuronError,
)
from tests.simulation_fixtures import (
    chain_circuit,
    fixture_circuit,
    make_circuit,
    single_neuron_circuit,
)

REST, THRESHOLD = 0.0, 1.0


def solo(**overrides) -> SimulationEngine:
    return SimulationEngine(single_neuron_circuit(), SimulationConfig(**overrides))


def potentials(engine: SimulationEngine) -> dict[str, float]:
    return {n.neuron_id: n.membrane_potential for n in engine.get_state().neurons}


# ------------------------------------------------------------------ reset
def test_reset_returns_to_initial_state() -> None:
    engine = SimulationEngine(fixture_circuit(), SimulationConfig())
    fresh_state = engine.get_state()
    engine.stimulate(["syn_001"], 2.0, 3)
    engine.run(5)
    assert engine.step_index == 5 and engine.firing_events > 0 and engine.stimuli
    engine.reset()
    assert engine.step_index == 0 and engine.simulation_time == 0.0
    assert engine.stimuli == [] and engine.firing_events == 0 and engine.spike_history == []
    assert np.all(engine.membrane_potential == REST) and np.all(engine.refractory_remaining == 0)
    assert not engine.fired.any()
    assert engine.get_state() == fresh_state


# ------------------------------------------------------------ single neuron / threshold / leak
def test_single_neuron_fires_with_sufficient_input() -> None:
    engine = solo()
    engine.stimulate(["solo"], intensity=1.0, duration_steps=1)
    summary = engine.step()
    assert summary.fired_neuron_ids == ["solo"] and summary.fired_count == 1
    state = engine.get_state().neurons[0]
    assert state.fired is True and state.membrane_potential == engine.config.reset_potential
    assert state.refractory_remaining == engine.config.refractory_steps
    assert engine.first_fire_step == {"solo": 1}


def test_insufficient_input_does_not_fire_and_then_leaks() -> None:
    engine = solo()
    engine.stimulate(["solo"], intensity=0.5, duration_steps=1)
    assert engine.step().fired_count == 0
    assert potentials(engine)["solo"] == pytest.approx(0.5)
    engine.step()
    assert potentials(engine)["solo"] == pytest.approx(0.5 * engine.config.decay_factor)


def test_threshold_is_inclusive() -> None:
    at = solo()
    at.stimulate(["solo"], THRESHOLD, 1)
    assert at.step().fired_count == 1
    below = solo()
    below.stimulate(["solo"], THRESHOLD - 1e-9, 1)
    assert below.step().fired_count == 0


def test_leak_is_geometric_and_configurable() -> None:
    engine = solo(leak=0.25)
    engine.stimulate(["solo"], 0.8, 1)
    engine.step()
    expected = 0.8
    for _ in range(5):
        engine.step()
        expected *= 0.75
        assert potentials(engine)["solo"] == pytest.approx(expected)
    no_leak = solo(leak=0.0)
    no_leak.stimulate(["solo"], 0.8, 1)
    no_leak.run(4)
    assert potentials(no_leak)["solo"] == pytest.approx(0.8)
    full_leak = solo(leak=1.0)
    full_leak.stimulate(["solo"], 0.8, 1)
    full_leak.run(2)
    assert potentials(full_leak)["solo"] == pytest.approx(REST)


def test_leak_decays_toward_non_zero_resting_potential() -> None:
    engine = solo(resting_potential=-1.0, reset_potential=-1.5, threshold=0.5, leak=0.5)
    engine.stimulate(["solo"], 1.0, 1)
    engine.step()  # V = -1 + 1 = 0 < 0.5
    assert potentials(engine)["solo"] == pytest.approx(0.0)
    engine.step()
    assert potentials(engine)["solo"] == pytest.approx(-0.5)


# ------------------------------------------------------------------ refractory
def test_refractory_blocks_firing_for_configured_steps() -> None:
    engine = solo(refractory_steps=2)
    engine.stimulate(["solo"], 5.0, 6)
    summary = engine.run(8)
    assert summary.per_step_fired_counts == [1, 0, 0, 1, 0, 0, 0, 0]
    no_refractory = solo(refractory_steps=0)
    no_refractory.stimulate(["solo"], 5.0, 6)
    assert no_refractory.run(8).per_step_fired_counts == [1, 1, 1, 1, 1, 1, 0, 0]


def test_refractory_neuron_holds_reset_potential_and_ignores_input() -> None:
    engine = solo(refractory_steps=3, reset_potential=-0.5, resting_potential=0.0)
    engine.stimulate(["solo"], 5.0, 4)
    engine.step()
    assert engine.get_state().neurons[0].refractory_remaining == 3
    for remaining in (2, 1, 0):
        engine.step()
        state = engine.get_state().neurons[0]
        assert state.membrane_potential == -0.5 and state.fired is False
        assert state.refractory_remaining == remaining


# ------------------------------------------------------------------ propagation
def test_weighted_propagation_across_one_edge() -> None:
    strong = SimulationEngine(chain_circuit((20, 20)), SimulationConfig())
    strong.stimulate(["A"], 2.0, 1)
    assert strong.run(3).first_fire_step == {"A": 1, "B": 2, "C": 3}  # one-step delay per edge
    weak = SimulationEngine(make_circuit(["A", "B"], [("A", "B", 1)]), SimulationConfig())
    weak.stimulate(["A"], 2.0, 1)
    summary = weak.run(3)
    assert summary.first_fire_step == {"A": 1}
    assert weak.weights.tolist() == pytest.approx([math.log1p(1)])  # 0.69 < threshold 1.0


def test_multi_hop_propagation_and_decay_on_fixture_circuit() -> None:
    circuit = fixture_circuit()
    hop = {n.neuron_id: n.minimum_hop_from_seed for n in circuit.nodes}
    engine = SimulationEngine(circuit, SimulationConfig())
    engine.stimulate(["syn_001"], 2.0, 3)
    summary = engine.run(30)
    assert summary.first_fire_step == {
        "syn_001": 1, "syn_003": 2, "syn_004": 2, "syn_005": 3, "syn_006": 3, "syn_007": 3
    }  # fmt: skip
    assert all(summary.first_fire_step[n] == hop[n] + 1 for n in summary.first_fire_step)
    assert summary.per_step_fired_counts[:3] == [1, 2, 3]
    assert not any(summary.per_step_fired_counts[3:])  # activity stops after stimulation
    assert all(abs(v - REST) < 1e-9 for v in potentials(engine).values())
    assert summary.firing_events == 6 and summary.neurons_activated == 6


def test_weight_transform_changes_dynamics_explicitly() -> None:
    circuit = make_circuit(["A", "B"], [("A", "B", 1)])
    log_engine = SimulationEngine(circuit, SimulationConfig(weight_transform="log1p"))
    binary_engine = SimulationEngine(circuit, SimulationConfig(weight_transform="binary"))
    for engine in (log_engine, binary_engine):
        engine.stimulate(["A"], 2.0, 1)
    assert "B" not in log_engine.run(3).first_fire_step
    assert binary_engine.run(3).first_fire_step == {"A": 1, "B": 2}
    scaled = SimulationEngine(circuit, SimulationConfig(weight_transform="log1p", weight_scale=2.0))
    scaled.stimulate(["A"], 2.0, 1)
    assert scaled.run(3).first_fire_step == {"A": 1, "B": 2}


def test_stimulus_timing_and_additivity() -> None:
    engine = solo()
    engine.step()  # step 0 -> 1 with no stimulus
    record = engine.stimulate(["solo"], 0.6, 2)
    assert record.start_step == 1 and record.end_step == 3
    engine.stimulate(["solo"], 0.6, 1)  # overlaps the first stimulus at step 1 -> 1.2 total
    assert engine.step().fired_count == 1
    engine.step()  # only the first stimulus (0.6) is still active; neuron is refractory
    engine.step()
    engine.step()  # no stimulus left
    assert not engine.stimuli[0].is_active(engine.step_index)


# ------------------------------------------------------------------ signs / metadata
def test_unsigned_mode_has_no_negative_weights_and_ignores_nt_metadata() -> None:
    plain = make_circuit(["A", "B"], [("A", "B", 20)])
    labelled = make_circuit(
        ["A", "B"], [("A", "B", 20)], neurotransmitters={"A": "gaba", "B": "acetylcholine"}
    )
    engines = [SimulationEngine(c, SimulationConfig()) for c in (plain, labelled)]
    for engine in engines:
        assert np.all(engine.weights > 0)
        engine.stimulate(["A"], 2.0, 1)
        engine.run(4)
    assert engines[0].get_state().model_dump(
        exclude={"neurons": {"__all__": {"neurotransmitter_prediction"}}}
    ) == engines[1].get_state().model_dump(
        exclude={"neurons": {"__all__": {"neurotransmitter_prediction"}}}
    )
    state = engines[1].get_state()
    assert {n.neuron_id: n.neurotransmitter_prediction for n in state.neurons} == {
        "A": "gaba",
        "B": "acetylcholine",
    }
    assert engines[1].config.sign_mode == "unsigned_excitatory_only"


def test_engine_never_mutates_the_circuit() -> None:
    circuit = fixture_circuit()
    before = circuit.model_dump()
    engine = SimulationEngine(circuit, SimulationConfig())
    engine.stimulate(["syn_001"], 2.0, 3)
    engine.run(20)
    engine.weights *= 10  # touching the engine's computational copy must not reach the circuit
    assert circuit.model_dump() == before
    assert circuit.compute_hash() == circuit.provenance.circuit_hash
    assert engine.synapse_counts.tolist() == [e.synapse_count for e in circuit.edges]


# ------------------------------------------------------------------ determinism
def test_deterministic_replay() -> None:
    def run(seed: int, noise: float) -> list[float]:
        engine = SimulationEngine(
            fixture_circuit(), SimulationConfig(noise_std=noise, random_seed=seed)
        )
        engine.stimulate(["syn_001"], 1.5, 3)
        engine.run(25)
        return engine.membrane_potential.tolist() + [float(engine.firing_events)]

    assert run(1, 0.0) == run(1, 0.0)
    assert run(1, 0.3) == run(1, 0.3)
    assert run(1, 0.3) != run(2, 0.3)


# ------------------------------------------------------------------ fail loudly
def test_unknown_neuron_ids_fail_loudly() -> None:
    engine = SimulationEngine(fixture_circuit(), SimulationConfig())
    with pytest.raises(UnknownNeuronError) as info:
        engine.stimulate(["syn_001", "ghost", "phantom"], 1.0, 1)
    assert info.value.missing == ["ghost", "phantom"]
    assert engine.stimuli == []


@pytest.mark.parametrize(
    ("intensity", "duration"),
    [
        (1.0, 0),
        (1.0, -3),
        (1.0, 2.5),
        (1.0, True),
        (-1.0, 1),
        (math.nan, 1),
        (math.inf, 1),
        ("1", 1),
    ],
)
def test_invalid_stimuli_are_rejected(intensity, duration) -> None:
    engine = solo()
    with pytest.raises(InvalidStimulusError):
        engine.stimulate(["solo"], intensity, duration)
    with pytest.raises(InvalidStimulusError):
        engine.stimulate([], 1.0, 1)


def test_run_limits() -> None:
    engine = solo(max_steps_per_run=10)
    with pytest.raises(SimulationLimitError):
        engine.run(11)
    for bad in (0, -1, 2.5, "5", True):
        with pytest.raises(SimulationLimitError):
            engine.run(bad)  # type: ignore[arg-type]
    assert engine.run(10).steps_run == 10


def test_nan_and_inf_protection() -> None:
    engine = solo()
    engine.membrane_potential[0] = math.nan
    with pytest.raises(NumericalInstabilityError):
        engine.step()
    with pytest.raises(ValueError):  # non-finite weights are rejected at construction
        SimulationEngine(
            chain_circuit((2591, 1)),
            SimulationConfig(weight_transform="linear", weight_scale=1e308),
        )
    clamped = SimulationEngine(
        chain_circuit((2591, 2591)),
        SimulationConfig(
            weight_transform="linear", weight_scale=1e6, threshold=1e9, max_potential=1e10
        ),
    )
    clamped.stimulate(["A"], 5e9, 1)
    clamped.run(3)
    assert np.all(np.isfinite(clamped.membrane_potential))
    assert clamped.membrane_potential.max() <= clamped.config.max_potential


def test_incompatible_circuits_are_rejected() -> None:
    dangling = make_circuit(["A", "B"], [("A", "Z", 5)])
    with pytest.raises(CircuitCompatibilityError, match="edge endpoint"):
        SimulationEngine(dangling, SimulationConfig())


# ------------------------------------------------------------------ state / activity
def test_get_state_exposes_required_fields() -> None:
    engine = SimulationEngine(fixture_circuit(), SimulationConfig(dt=0.5))
    engine.stimulate(["syn_001"], 2.0, 1)
    engine.run(2)
    state = engine.get_state()
    assert state.step == 2 and state.simulation_time == pytest.approx(1.0)
    assert "SIMULATED" in state.label and state.sign_mode == "unsigned_excitatory_only"
    assert len(state.neurons) == engine.num_neurons
    neuron = state.neurons[0]
    for field in (
        "neuron_id",
        "membrane_potential",
        "threshold",
        "reset_potential",
        "leak",
        "refractory_remaining",
        "fired",
    ):
        assert hasattr(neuron, field)
    assert sorted(state.fired_neuron_ids) == ["syn_003", "syn_004"]


def test_activity_raster() -> None:
    engine = SimulationEngine(chain_circuit(), SimulationConfig())
    engine.stimulate(["A"], 2.0, 1)
    engine.run(4)
    activity = engine.get_activity()
    assert activity["spikes_per_step"] == [["A"], ["B"], ["C"], []]
    assert activity["firing_events"] == 3 and activity["neurons_activated"] == 3
    assert "SIMULATED" in activity["label"]
