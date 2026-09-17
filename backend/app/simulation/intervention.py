"""Computational neural intervention (P7.2) — COMPUTATIONAL DYNAMICS layer.

    Computational intervention suppresses simulated firing of selected neurons while
    preserving the biological structural connectivity.

An ``InterventionConfig`` is applied *inside* the simulation engine, at the moment a
neuron's simulated membrane potential crosses threshold. Exact semantics of
``SUPPRESS_FIRING`` for a targeted neuron:

1. the neuron, its biological id, its structural edges and their synapse counts stay
   exactly as in the circuit artifact (the engine never mutates the ``Circuit``);
2. synaptic and external input are still accumulated and the membrane potential still
   integrates and leaks exactly as for any other neuron;
3. when the potential reaches threshold, ``fired`` is forced to ``False`` — no spike is
   recorded, the neuron is neither reset nor made refractory, and therefore no
   spike-driven input is propagated along its outgoing edges at the next step.

Nothing downstream (decoder, motor mapping, body, world) is touched: whatever happens
after the suppression emerges from the unchanged model. This is a computational
manipulation of simulated dynamics; it is NOT optogenetic, genetic (Kir2.1 / TNT),
pharmacological silencing, nor a biological lesion or ablation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

INTERVENTION_LAYER = "COMPUTATIONAL DYNAMICS"
INTERVENTION_LABEL = "COMPUTATIONAL FIRING SUPPRESSION"
INTERVENTION_SEMANTICS = (
    "Computational intervention suppresses simulated firing of selected neurons while "
    "preserving the biological structural connectivity."
)
INTERVENTION_DISCLAIMER = (
    "Neural interventions in this lab are computational manipulations of simulated neural "
    "dynamics. They do not reproduce a specific biological silencing, optogenetic, genetic, "
    "pharmacological, or lesion technique. Biological structural connectivity remains "
    "unchanged."
)
#: Documented for future phases; NOT implemented in P7.2 (the engine rejects them).
FUTURE_INTERVENTION_TYPES: tuple[str, ...] = (
    "STIMULATE",
    "CLAMP",
    "LESION",
    "REMOVE_CONNECTION",
    "SYNAPTIC_BLOCK",
)


class InterventionType(StrEnum):
    NONE = "NONE"
    SUPPRESS_FIRING = "SUPPRESS_FIRING"


class InterventionConfig(BaseModel):
    """Immutable description of one computational intervention (default: none)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intervention_type: InterventionType = InterventionType.NONE
    #: biological neuron ids (from the circuit artifact) whose simulated firing is suppressed
    target_neuron_ids: tuple[str, ...] = ()
    #: cell-type annotations the targets were resolved from (informational)
    target_cell_types: tuple[str, ...] = ()
    label: str = "CONTROL"
    description: str = "no computational intervention (control trial)"
    layer: Literal["COMPUTATIONAL DYNAMICS"] = INTERVENTION_LAYER
    semantics: Literal[
        "Computational intervention suppresses simulated firing of selected neurons while "
        "preserving the biological structural connectivity."
    ] = INTERVENTION_SEMANTICS

    @field_validator("target_neuron_ids", "target_cell_types", mode="before")
    @classmethod
    def _canonical(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            value = [value]
        items = [str(v).strip() for v in value]
        if any(not item for item in items):
            raise ValueError("identifiers must be non-empty strings")
        return tuple(sorted(set(items)))

    @model_validator(mode="after")
    def _consistent(self) -> InterventionConfig:
        if self.intervention_type is InterventionType.NONE and self.target_neuron_ids:
            raise ValueError("intervention_type NONE must not carry target neuron ids")
        if (
            self.intervention_type is InterventionType.SUPPRESS_FIRING
            and not self.target_neuron_ids
        ):
            raise ValueError("SUPPRESS_FIRING requires at least one target neuron id")
        return self

    @property
    def is_active(self) -> bool:
        return self.intervention_type is not InterventionType.NONE

    @property
    def target_count(self) -> int:
        return len(self.target_neuron_ids)

    @classmethod
    def none(cls) -> InterventionConfig:
        return cls()

    @classmethod
    def suppress_firing(
        cls,
        target_neuron_ids: Any,
        *,
        target_cell_types: Any = (),
        label: str = INTERVENTION_LABEL,
        description: str | None = None,
    ) -> InterventionConfig:
        return cls(
            intervention_type=InterventionType.SUPPRESS_FIRING,
            target_neuron_ids=target_neuron_ids,
            target_cell_types=target_cell_types,
            label=label,
            description=description
            or "simulated firing of the target neurons is suppressed inside the simulation "
            "engine; structure, inputs and membrane integration are unchanged",
        )

    def summary(self) -> dict[str, Any]:
        """Provenance block (ids included so the trial is fully reproducible)."""
        return {
            "intervention_type": str(self.intervention_type),
            "label": self.label,
            "description": self.description,
            "target_cell_types": list(self.target_cell_types),
            "target_neuron_ids": list(self.target_neuron_ids),
            "target_neuron_count": self.target_count,
            "layer": self.layer,
            "semantics": self.semantics,
        }


NO_INTERVENTION = InterventionConfig()

__all__ = [
    "FUTURE_INTERVENTION_TYPES",
    "INTERVENTION_DISCLAIMER",
    "INTERVENTION_LABEL",
    "INTERVENTION_LAYER",
    "INTERVENTION_SEMANTICS",
    "NO_INTERVENTION",
    "InterventionConfig",
    "InterventionType",
]
