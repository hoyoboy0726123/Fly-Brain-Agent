"""Intervention target selectors for the escape_v1 behaviour (P7.2, application layer).

User-facing selectors (``CONTROL``, ``SILENCE_LC4``, ``SILENCE_LPLC2``,
``SILENCE_LC4_LPLC2``) are resolved into biological neuron ids using ONLY the cell-type
annotations already present in the loaded circuit artifact (MaleCNS ``cell_type``). No id
is invented and no count is assumed; resolution fails loudly when a cell type is absent.

The literature below motivates *target selection only*. It does not validate the
computational intervention implemented by FlyBrain Agent, and the current simulation
result must never be presented as validation of the biological study.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.circuits import Circuit
from app.simulation import INTERVENTION_LABEL, InterventionConfig

InterventionSelector = Literal["CONTROL", "SILENCE_LC4", "SILENCE_LPLC2", "SILENCE_LC4_LPLC2"]
INTERVENTION_SELECTORS: tuple[str, ...] = (
    "CONTROL",
    "SILENCE_LC4",
    "SILENCE_LPLC2",
    "SILENCE_LC4_LPLC2",
)
SELECTOR_CELL_TYPES: dict[str, tuple[str, ...]] = {
    "CONTROL": (),
    "SILENCE_LC4": ("LC4",),
    "SILENCE_LPLC2": ("LPLC2",),
    "SILENCE_LC4_LPLC2": ("LC4", "LPLC2"),
}
SELECTOR_LABELS: dict[str, str] = {
    "CONTROL": "CONTROL",
    "SILENCE_LC4": "SILENCE LC4",
    "SILENCE_LPLC2": "SILENCE LPLC2",
    "SILENCE_LC4_LPLC2": "SILENCE LC4 + LPLC2",
}
RESOLUTION_RULE = (
    "circuit nodes whose MaleCNS cell_type annotation equals the selected cell type(s); "
    "union without duplicates; ids sorted"
)

#: Compact literature context (BIOLOGICAL EVIDENCE — separate from any computational result).
BIOLOGICAL_CONTEXT: dict[str, Any] = {
    "label": "BIOLOGICAL EVIDENCE (literature) — motivates target selection only",
    "citation": {
        "authors": "Ache JM et al.",
        "year": 2019,
        "title": (
            "Neural Basis for Looming Size and Velocity Encoding in the Drosophila Giant "
            "Fiber Escape Pathway"
        ),
        "journal": "Current Biology 29(6):1073-1081.e4",
        "doi": "10.1016/j.cub.2019.01.079",
    },
    "LC4": (
        "Biological literature supports direct LC4 → GF input and a contribution related to "
        "looming angular velocity."
    ),
    "LPLC2": (
        "Biological literature supports direct LPLC2 → GF input and a contribution related "
        "to looming angular size. Ache et al. 2019 reported that experimental LPLC2 silencing "
        "removed the GF size component and impaired GF-mediated escape."
    ),
    "scope": (
        "These experiments motivate TARGET SELECTION only. They do NOT validate the "
        "computational firing suppression implemented here, and the current simulation result "
        "is never a validation of the biological study."
    ),
}


class TargetResolutionError(ValueError):
    """A selector could not be resolved from the loaded circuit's metadata."""


class ResolvedTargets(BaseModel):
    """Biological neuron ids a selector resolved to (from the circuit artifact)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    selector: str
    label: str
    cell_types: list[str]
    neuron_ids: list[str]
    neuron_count: int = Field(ge=0)
    per_cell_type_counts: dict[str, int]
    circuit_id: str
    circuit_hash: str
    resolution_rule: str = RESOLUTION_RULE


def resolve_targets(circuit: Circuit, selector: str) -> ResolvedTargets:
    """Resolve ``selector`` against ``circuit.nodes[*].cell_type``; fail loudly otherwise."""
    if selector not in SELECTOR_CELL_TYPES:
        raise TargetResolutionError(
            f"unknown intervention selector {selector!r}; expected one of {INTERVENTION_SELECTORS}"
        )
    circuit_hash = circuit.provenance.circuit_hash or circuit.compute_hash()
    cell_types = SELECTOR_CELL_TYPES[selector]
    if not cell_types:
        return ResolvedTargets(
            selector=selector,
            label=SELECTOR_LABELS[selector],
            cell_types=[],
            neuron_ids=[],
            neuron_count=0,
            per_cell_type_counts={},
            circuit_id=circuit.circuit_id,
            circuit_hash=circuit_hash,
        )
    nodes = circuit.nodes
    if not nodes:
        raise TargetResolutionError(f"circuit {circuit.circuit_id} has no nodes")
    annotated = [node for node in nodes if isinstance(node.cell_type, str) and node.cell_type]
    if not annotated:
        raise TargetResolutionError(
            f"circuit {circuit.circuit_id} carries no cell_type annotations (unexpected schema)"
        )
    per_type: dict[str, list[str]] = {}
    for cell_type in cell_types:
        ids = sorted({node.neuron_id for node in annotated if node.cell_type == cell_type})
        if not ids:
            raise TargetResolutionError(
                f"cell type {cell_type!r} resolves to zero neurons in circuit {circuit.circuit_id}"
            )
        per_type[cell_type] = ids
    union = sorted({nid for ids in per_type.values() for nid in ids})
    if not union:
        raise TargetResolutionError(f"selector {selector!r} resolved to zero neurons")
    return ResolvedTargets(
        selector=selector,
        label=SELECTOR_LABELS[selector],
        cell_types=list(cell_types),
        neuron_ids=union,
        neuron_count=len(union),
        per_cell_type_counts={ct: len(ids) for ct, ids in per_type.items()},
        circuit_id=circuit.circuit_id,
        circuit_hash=circuit_hash,
    )


def build_intervention(
    circuit: Circuit, selector: str
) -> tuple[InterventionConfig, ResolvedTargets]:
    """Selector → (engine-level ``InterventionConfig``, provenance of the resolution)."""
    resolved = resolve_targets(circuit, selector)
    if resolved.neuron_count == 0:
        return InterventionConfig.none(), resolved
    config = InterventionConfig.suppress_firing(
        resolved.neuron_ids,
        target_cell_types=resolved.cell_types,
        label=f"{INTERVENTION_LABEL} — {resolved.label}",
        description=(
            f"simulated firing of {resolved.neuron_count} circuit neuron(s) annotated "
            f"{' + '.join(resolved.cell_types)} is suppressed inside the simulation engine; "
            "their ids, edges and synapse counts are unchanged"
        ),
    )
    return config, resolved


def structural_signature(circuit: Circuit) -> dict[str, Any]:
    """Counts and content hash of the biological structure (for before/after checks)."""
    return {
        "node_count": len(circuit.nodes),
        "edge_count": len(circuit.edges),
        "synapse_total": int(sum(edge.synapse_count for edge in circuit.edges)),
        "circuit_hash": circuit.compute_hash(),
        "recorded_hash": circuit.provenance.circuit_hash,
    }


__all__ = [
    "BIOLOGICAL_CONTEXT",
    "INTERVENTION_SELECTORS",
    "RESOLUTION_RULE",
    "SELECTOR_CELL_TYPES",
    "SELECTOR_LABELS",
    "InterventionSelector",
    "ResolvedTargets",
    "TargetResolutionError",
    "build_intervention",
    "resolve_targets",
    "structural_signature",
]
