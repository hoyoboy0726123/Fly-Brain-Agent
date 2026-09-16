"""SimulationConfig — COMPUTATIONAL MODEL PARAMETERS, NOT MEASURED MALECNS PARAMETERS.

Every value below is a modelling assumption of the simplified discrete-time
leaky-integrate-and-fire (LIF-like) engine. None of them is measured from the fly; the
only biological input to the simulation is the structural connectivity of the circuit
artifact (neuron ids, edge direction, synapse counts).
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PARAMETER_LABEL = "COMPUTATIONAL MODEL PARAMETERS — NOT MEASURED MALECNS PARAMETERS"

WeightTransform = Literal["log1p", "linear", "sqrt", "binary"]
#: Only mode implemented in P3: every synaptic weight is positive. No excitatory/inhibitory
#: sign is derived from the dataset (neurotransmitter predictions are metadata only).
SignMode = Literal["unsigned_excitatory_only"]


class SimulationConfig(BaseModel):
    """Global parameters of the simplified LIF-like model (units are model units, not mV/ms)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Literal["COMPUTATIONAL MODEL PARAMETERS — NOT MEASURED MALECNS PARAMETERS"] = (
        PARAMETER_LABEL
    )

    dt: float = Field(default=1.0, gt=0, allow_inf_nan=False, description="model time per step")
    resting_potential: float = Field(default=0.0, allow_inf_nan=False)
    reset_potential: float = Field(default=0.0, allow_inf_nan=False)
    threshold: float = Field(default=1.0, allow_inf_nan=False)
    #: fraction of the deviation from rest lost per unit model time; decay per step = 1 - leak*dt
    leak: float = Field(default=0.2, ge=0, allow_inf_nan=False)
    refractory_steps: int = Field(default=2, ge=0)
    weight_transform: WeightTransform = "log1p"
    weight_scale: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    #: multiplies stimulus intensity into injected input per step
    stimulus_gain: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    #: standard deviation of optional additive membrane noise (0 = purely deterministic dynamics)
    noise_std: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    #: hard clamp preventing numerical explosion
    max_potential: float = Field(default=100.0, allow_inf_nan=False)
    max_steps_per_run: int = Field(default=10_000, ge=1)
    random_seed: int = Field(default=0, ge=0)
    sign_mode: SignMode = "unsigned_excitatory_only"

    @model_validator(mode="after")
    def _consistent(self) -> SimulationConfig:
        if self.threshold <= self.reset_potential:
            raise ValueError("threshold must be greater than reset_potential")
        if self.threshold <= self.resting_potential:
            raise ValueError("threshold must be greater than resting_potential")
        if self.max_potential <= self.threshold:
            raise ValueError("max_potential must be greater than threshold")
        decay = 1.0 - self.leak * self.dt
        if not (0.0 <= decay <= 1.0) or not math.isfinite(decay):
            raise ValueError("leak * dt must lie in [0, 1] so the leak is stable (no overshoot)")
        return self

    @property
    def decay_factor(self) -> float:
        """Per-step multiplier applied to (V - resting_potential)."""
        return 1.0 - self.leak * self.dt
