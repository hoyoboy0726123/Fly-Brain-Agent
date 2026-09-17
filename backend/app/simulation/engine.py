"""Simplified discrete-time leaky-integrate-and-fire engine over a P2 circuit artifact.

COMPUTATIONAL DYNAMICS layer. The circuit's connectivity (BIOLOGICAL STRUCTURE) is read
once and never modified; everything the engine produces (membrane potentials, firing
events, spike timing) is SIMULATED and must never be presented as measured activity.

Update rule per step t → t+1 (model units), for every neuron i that is not refractory::

    V_i ← V_rest + (V_i − V_rest)·(1 − leak·dt)          leak toward rest
          + Σ_j w_ji · fired_j(t)                          synaptic input from spikes of step t
          + gain · Σ_active_stimuli intensity_i            generic external input
          + N(0, noise_std)                                optional seeded noise
    V_i ← min(V_i, max_potential)                          hard clamp
    fired_i(t+1) = V_i ≥ threshold  →  V_i = V_reset, refractory_i = refractory_steps

Refractory neurons hold V_reset, ignore all input and count down. Synaptic transmission
has a fixed one-step delay. Weights are ``normalize_weights(synapse_count)`` — positive
only (``unsigned_excitatory_only``).
"""

from __future__ import annotations

import resource
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np

from app.circuits.artifact import Circuit
from app.simulation.config import SimulationConfig
from app.simulation.errors import (
    CircuitCompatibilityError,
    InterventionError,
    InvalidStimulusError,
    NumericalInstabilityError,
    SimulationLimitError,
    SnapshotMismatchError,
    UnknownNeuronError,
)
from app.simulation.intervention import NO_INTERVENTION, InterventionConfig, InterventionType
from app.simulation.state import (
    NeuronState,
    RunSummary,
    SimulationSnapshot,
    SimulationState,
    StepSummary,
    StimulusRecord,
)
from app.simulation.weights import normalize_weights


class SimulationEngine:
    """Runs the LIF-like model on one ``Circuit``; see the module docstring for the equations."""

    def __init__(
        self,
        circuit: Circuit,
        config: SimulationConfig,
        intervention: InterventionConfig | None = None,
    ) -> None:
        self.config = config
        # --- reference to the biological structure (read once, never mutated) ---
        self.circuit_id = circuit.circuit_id
        self.circuit_hash = circuit.provenance.circuit_hash or circuit.compute_hash()
        self.dataset = circuit.dataset
        self.dataset_version = circuit.dataset_version
        self.neuron_ids: list[str] = [node.neuron_id for node in circuit.nodes]
        if len(set(self.neuron_ids)) != len(self.neuron_ids):
            raise CircuitCompatibilityError("circuit nodes must have unique neuron ids")
        self._index: dict[str, int] = {nid: i for i, nid in enumerate(self.neuron_ids)}
        self.neurotransmitter_prediction: list[str | None] = [
            node.neurotransmitter for node in circuit.nodes
        ]
        missing = sorted(
            {e.pre_neuron_id for e in circuit.edges if e.pre_neuron_id not in self._index}
            | {e.post_neuron_id for e in circuit.edges if e.post_neuron_id not in self._index}
        )
        if missing:
            raise CircuitCompatibilityError(
                f"{len(missing)} edge endpoint(s) are not circuit nodes, e.g. {missing[:5]}"
            )
        self.pre_index = np.fromiter(
            (self._index[e.pre_neuron_id] for e in circuit.edges),
            dtype=np.int64,
            count=len(circuit.edges),
        )
        self.post_index = np.fromiter(
            (self._index[e.post_neuron_id] for e in circuit.edges),
            dtype=np.int64,
            count=len(circuit.edges),
        )
        self.synapse_counts = np.fromiter(
            (e.synapse_count for e in circuit.edges), dtype=np.int64, count=len(circuit.edges)
        )
        # --- computational transformation of the structural counts ---
        self.weights = normalize_weights(
            self.synapse_counts, config.weight_transform, config.weight_scale
        )
        n = len(self.neuron_ids)
        # per-neuron parameters (initialised from the global config; heterogeneity hook)
        self.threshold = np.full(n, config.threshold, dtype=np.float64)
        self.reset_potential = np.full(n, config.reset_potential, dtype=np.float64)
        self.leak = np.full(n, config.leak, dtype=np.float64)
        # --- mutable simulated state ---
        self.membrane_potential = np.empty(n, dtype=np.float64)
        self.refractory_remaining = np.empty(n, dtype=np.int32)
        self.fired = np.empty(n, dtype=bool)
        self.step_index = 0
        self.simulation_time = 0.0
        self.stimuli: list[StimulusRecord] = []
        self.spike_history: list[np.ndarray] = []
        self.firing_events = 0
        self.first_fire_step: dict[str, int] = {}
        self.rng = np.random.default_rng(config.random_seed)
        # --- P7.2 computational intervention (COMPUTATIONAL DYNAMICS; structure untouched) ---
        self.intervention: InterventionConfig = NO_INTERVENTION
        self.suppressed_mask = np.zeros(n, dtype=bool)
        self.suppressed_events = 0
        self.set_intervention(intervention or NO_INTERVENTION)
        self.reset()

    # ------------------------------------------------------------------ properties
    @property
    def num_neurons(self) -> int:
        return len(self.neuron_ids)

    @property
    def num_edges(self) -> int:
        return int(self.pre_index.shape[0])

    def index_of(self, neuron_ids: Sequence[str]) -> np.ndarray:
        missing = [nid for nid in neuron_ids if nid not in self._index]
        if missing:
            raise UnknownNeuronError(missing)
        return np.fromiter(
            (self._index[nid] for nid in neuron_ids), dtype=np.int64, count=len(neuron_ids)
        )

    # ------------------------------------------------------------------ control
    def set_intervention(self, intervention: InterventionConfig | None) -> InterventionConfig:
        """Install a computational intervention (P7.2). Only SUPPRESS_FIRING / NONE exist.

        Targets must be circuit neurons (unknown ids fail loudly). The circuit itself, the
        edge arrays and the weights are not touched — only a boolean mask is built.
        """
        intervention = intervention or NO_INTERVENTION
        if not isinstance(intervention, InterventionConfig):
            raise InterventionError("intervention must be an InterventionConfig")
        if intervention.intervention_type not in (
            InterventionType.NONE,
            InterventionType.SUPPRESS_FIRING,
        ):
            raise InterventionError(
                f"intervention type {intervention.intervention_type!r} is not implemented"
            )
        mask = np.zeros(self.num_neurons, dtype=bool)
        if intervention.is_active:
            mask[self.index_of(list(intervention.target_neuron_ids))] = True
        self.intervention = intervention
        self.suppressed_mask = mask
        return intervention

    def reset(self) -> None:
        """Return to the initial state: rest potential, no refractory, no stimuli, reseeded RNG."""
        self.membrane_potential[:] = self.config.resting_potential
        self.refractory_remaining[:] = 0
        self.fired[:] = False
        self.step_index = 0
        self.simulation_time = 0.0
        self.stimuli = []
        self.spike_history = []
        self.firing_events = 0
        self.suppressed_events = 0
        self.first_fire_step = {}
        self.rng = np.random.default_rng(self.config.random_seed)

    def stimulate(
        self, neuron_ids: Sequence[str], intensity: float, duration_steps: int
    ) -> StimulusRecord:
        """Register a GENERIC input injection starting at the current step."""
        if isinstance(neuron_ids, str):
            neuron_ids = [neuron_ids]
        ids = sorted(set(str(nid) for nid in neuron_ids))
        if not ids:
            raise InvalidStimulusError("stimulate() needs at least one neuron id")
        self.index_of(ids)  # fail loudly on unknown ids
        if isinstance(intensity, bool) or not isinstance(intensity, int | float):
            raise InvalidStimulusError("intensity must be a number")
        if not np.isfinite(intensity) or intensity < 0:
            raise InvalidStimulusError(
                f"intensity must be finite and >= 0 in unsigned mode, got {intensity!r}"
            )
        if isinstance(duration_steps, bool) or not isinstance(duration_steps, int):
            raise InvalidStimulusError("duration_steps must be an integer")
        if duration_steps < 1:
            raise InvalidStimulusError(f"duration_steps must be >= 1, got {duration_steps}")
        record = StimulusRecord(
            neuron_ids=ids,
            intensity=float(intensity),
            start_step=self.step_index,
            duration_steps=duration_steps,
        )
        self.stimuli.append(record)
        return record

    def _external_input(self) -> tuple[np.ndarray, int]:
        current = np.zeros(self.num_neurons, dtype=np.float64)
        touched = 0
        for stimulus in self.stimuli:
            if stimulus.is_active(self.step_index):
                idx = self.index_of(stimulus.neuron_ids)
                current[idx] += stimulus.intensity * self.config.stimulus_gain
                touched += len(idx)
        return current, touched

    def step(self) -> StepSummary:
        """Advance the model by one step of ``dt`` (see module docstring)."""
        cfg = self.config
        n = self.num_neurons
        if not np.all(np.isfinite(self.membrane_potential)):
            raise NumericalInstabilityError("membrane potential is not finite before the step")

        previous_spikes = self.fired.astype(np.float64)
        if self.num_edges:
            synaptic = np.bincount(
                self.post_index, weights=self.weights * previous_spikes[self.pre_index], minlength=n
            )
        else:
            synaptic = np.zeros(n, dtype=np.float64)
        external, touched = self._external_input()
        noise = self.rng.normal(0.0, cfg.noise_std, n) if cfg.noise_std > 0 else 0.0

        active = self.refractory_remaining <= 0
        rest = cfg.resting_potential
        integrated = rest + (self.membrane_potential - rest) * (1.0 - self.leak * cfg.dt)
        integrated = integrated + synaptic + external + noise
        potential = np.where(active, integrated, self.reset_potential)
        potential = np.minimum(potential, cfg.max_potential)
        if not np.all(np.isfinite(potential)):
            raise NumericalInstabilityError("membrane potential became NaN/Inf during the step")

        fired = active & (potential >= self.threshold)
        # P7.2 COMPUTATIONAL FIRING SUPPRESSION: a targeted neuron that reaches threshold emits
        # no spike (so it is neither reset nor made refractory and propagates nothing);
        # its membrane state, inputs, id and edges are untouched.
        suppressed = fired & self.suppressed_mask
        fired = fired & ~self.suppressed_mask
        potential = np.where(fired, self.reset_potential, potential)
        refractory = np.where(active, 0, self.refractory_remaining - 1)
        refractory = np.where(fired, cfg.refractory_steps, refractory)

        self.membrane_potential = potential
        self.refractory_remaining = refractory.astype(np.int32)
        self.fired = fired
        self.step_index += 1
        self.simulation_time = self.step_index * cfg.dt

        fired_idx = np.flatnonzero(fired)
        suppressed_idx = np.flatnonzero(suppressed)
        self.spike_history.append(fired_idx)
        self.firing_events += int(fired_idx.size)
        self.suppressed_events += int(suppressed_idx.size)
        for i in fired_idx.tolist():
            self.first_fire_step.setdefault(self.neuron_ids[i], self.step_index)
        return StepSummary(
            step=self.step_index,
            simulation_time=self.simulation_time,
            fired_count=int(fired_idx.size),
            fired_neuron_ids=[self.neuron_ids[i] for i in fired_idx.tolist()],
            max_membrane_potential=float(potential.max()) if n else float(rest),
            external_input_neurons=touched,
            suppressed_count=int(suppressed_idx.size),
            suppressed_neuron_ids=[self.neuron_ids[i] for i in suppressed_idx.tolist()],
        )

    def run(
        self,
        steps: int,
        on_step: Callable[[StepSummary], None] | None = None,
        *,
        intervention: InterventionConfig | None = None,
    ) -> RunSummary:
        """Advance ``steps`` times; ``on_step`` (if given) sees every ``StepSummary`` in order.

        ``intervention`` (P7.2) installs a computational intervention for this and later
        steps; omitted → the engine's current intervention (default NONE) is kept, so every
        pre-P7.2 caller behaves exactly as before.
        """
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise SimulationLimitError(f"steps must be a positive integer, got {steps!r}")
        if steps > self.config.max_steps_per_run:
            raise SimulationLimitError(
                f"steps={steps} exceeds max_steps_per_run={self.config.max_steps_per_run}"
            )
        if intervention is not None:
            self.set_intervention(intervention)
        start_step = self.step_index
        events_before = self.firing_events
        suppressed_before = self.suppressed_events
        activated: dict[str, int] = {}
        counts: list[int] = []
        started = time.perf_counter()
        for _ in range(steps):
            summary = self.step()
            counts.append(summary.fired_count)
            for nid in summary.fired_neuron_ids:
                activated.setdefault(nid, summary.step)
            if on_step is not None:
                on_step(summary)
        elapsed = time.perf_counter() - started
        return RunSummary(
            start_step=start_step,
            end_step=self.step_index,
            steps_run=steps,
            firing_events=self.firing_events - events_before,
            neurons_activated=len(activated),
            activated_neuron_ids=sorted(activated),
            first_fire_step=dict(sorted(activated.items())),
            per_step_fired_counts=counts,
            runtime_seconds=elapsed,
            mean_step_seconds=elapsed / steps,
            suppressed_events=self.suppressed_events - suppressed_before,
        )

    # ------------------------------------------------------------------ inspection
    def neuron_states(self) -> list[NeuronState]:
        return [
            NeuronState(
                neuron_id=nid,
                membrane_potential=float(self.membrane_potential[i]),
                threshold=float(self.threshold[i]),
                reset_potential=float(self.reset_potential[i]),
                leak=float(self.leak[i]),
                refractory_remaining=int(self.refractory_remaining[i]),
                fired=bool(self.fired[i]),
                neurotransmitter_prediction=self.neurotransmitter_prediction[i],
                suppressed=bool(self.suppressed_mask[i]),
            )
            for i, nid in enumerate(self.neuron_ids)
        ]

    def get_state(self) -> SimulationState:
        return SimulationState(
            step=self.step_index,
            simulation_time=self.simulation_time,
            sign_mode=self.config.sign_mode,
            neurons=self.neuron_states(),
            fired_neuron_ids=[self.neuron_ids[i] for i in np.flatnonzero(self.fired).tolist()],
        )

    def get_activity(self) -> dict[str, Any]:
        """Spike raster of the current run: per-step fired ids plus totals (all SIMULATED)."""
        return {
            "label": SimulationState.model_fields["label"].default,
            "steps": self.step_index,
            "firing_events": self.firing_events,
            "neurons_activated": len(self.first_fire_step),
            "first_fire_step": dict(sorted(self.first_fire_step.items())),
            "spikes_per_step": [
                [self.neuron_ids[i] for i in fired.tolist()] for fired in self.spike_history
            ],
            "intervention": self.intervention.summary(),
            "suppressed_events": self.suppressed_events,
        }

    # ------------------------------------------------------------------ snapshots
    def snapshot(self, simulation_id: str) -> SimulationSnapshot:
        return SimulationSnapshot(
            simulation_id=simulation_id,
            circuit_id=self.circuit_id,
            circuit_hash=self.circuit_hash,
            dataset=self.dataset,
            dataset_version=self.dataset_version,
            simulation_config=self.config,
            random_seed=self.config.random_seed,
            current_step=self.step_index,
            simulation_time=self.simulation_time,
            stimuli=list(self.stimuli),
            neuron_states=self.neuron_states(),
            firing_events_total=self.firing_events,
            intervention=self.intervention,
            rng_state=self.rng.bit_generator.state,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )

    @classmethod
    def from_snapshot(cls, circuit: Circuit, snapshot: SimulationSnapshot) -> SimulationEngine:
        """Rebuild an engine at the snapshot's step; the circuit must match the referenced hash."""
        circuit_hash = circuit.provenance.circuit_hash or circuit.compute_hash()
        if circuit.circuit_id != snapshot.circuit_id or circuit_hash != snapshot.circuit_hash:
            raise SnapshotMismatchError(
                f"snapshot references circuit {snapshot.circuit_id} "
                f"({snapshot.circuit_hash[:12]}…) but got {circuit.circuit_id} "
                f"({circuit_hash[:12]}…)"
            )
        engine = cls(circuit, snapshot.simulation_config, snapshot.intervention)
        by_id = {state.neuron_id: state for state in snapshot.neuron_states}
        missing = [nid for nid in engine.neuron_ids if nid not in by_id]
        if missing or len(by_id) != engine.num_neurons:
            raise SnapshotMismatchError("snapshot neuron states do not match the circuit nodes")
        for i, nid in enumerate(engine.neuron_ids):
            state = by_id[nid]
            engine.membrane_potential[i] = state.membrane_potential
            engine.refractory_remaining[i] = state.refractory_remaining
            engine.fired[i] = state.fired
            engine.threshold[i] = state.threshold
            engine.reset_potential[i] = state.reset_potential
            engine.leak[i] = state.leak
        engine.step_index = snapshot.current_step
        engine.simulation_time = snapshot.simulation_time
        engine.stimuli = list(snapshot.stimuli)
        engine.firing_events = snapshot.firing_events_total
        if snapshot.rng_state is not None:
            engine.rng.bit_generator.state = snapshot.rng_state
        return engine


def peak_rss_bytes() -> int | None:
    try:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (OSError, ValueError):
        return None
    return int(rss) if sys.platform == "darwin" else int(rss) * 1024
