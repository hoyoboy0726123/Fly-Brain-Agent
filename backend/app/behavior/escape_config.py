"""Versioned behaviour configuration (escape_v1): which MaleCNS neurons play which role.

Every biological choice recorded here must be backed by ``docs/circuits/escape_v1.md``.
The config carries the identifiers, the extractor parameters, the citations, the mapping
confidence and the expected circuit hash so that tests can verify the whole chain.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.circuits.artifact import ExtractorConfig

CONFIG_DIR = Path(__file__).resolve().parent / "configs"
BiologicalStatus = Literal["SUPPORTED", "PARTIALLY SUPPORTED", "UNSUPPORTED"]
Side = Literal["L", "R"]


class Citation(BaseModel):
    key: str
    authors: str
    year: int
    title: str
    venue: str
    doi: str | None = None
    url: str | None = None
    claim: str
    verification: str
    confidence: Literal["high", "medium", "low"]


class ExtractorParams(BaseModel):
    max_hops: int = Field(ge=0)
    min_synapses: int = Field(ge=0)
    max_neurons: int = Field(ge=1)
    direction: Literal["downstream", "upstream"] = "downstream"
    restrict_to_target_paths: bool = True


class StimulusMappingParams(BaseModel):
    mapping_gain: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    duration_steps: int = Field(default=5, ge=1)
    rule: str


class DecoderParams(BaseModel):
    min_output_spikes: int = Field(default=1, ge=1)
    actions: list[str] = Field(default_factory=lambda: ["NO_ACTION", "ESCAPE"])
    rule: str


class EscapeCircuitConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_version: str
    circuit_id: str
    synthetic: bool = False
    dataset: str
    dataset_version: str
    canonical_selection_rule: str
    biological_status: BiologicalStatus
    research_document: str
    sensory_cell_types: list[str]
    output_cell_types: list[str]
    #: full biological population per side (extraction seeds; the mapping claim)
    sensory_population: dict[Side, list[str]] | None = None
    #: population members kept in the circuit (these receive the stimulus current)
    sensory_groups: dict[Side, list[str]]
    #: population members not in the circuit (recorded, never silently dropped)
    excluded_sensory_ids: dict[Side, list[str]] = Field(default_factory=lambda: {"L": [], "R": []})
    exclusion_reason: str = ""
    output_groups: dict[Side, list[str]]
    extractor: ExtractorParams
    stimulus_mapping: StimulusMappingParams
    decoder: DecoderParams
    #: overrides applied on top of P3 ``SimulationConfig`` defaults ({} = defaults, unchanged)
    simulation_config_overrides: dict[str, Any] = Field(default_factory=dict)
    simulation_steps: int = Field(default=30, ge=1)
    expected_circuit_hash: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    mapping_confidence: dict[str, str] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def _consistency(self) -> EscapeCircuitConfig:
        for name, groups in (
            ("sensory_groups", self.sensory_groups),
            ("output_groups", self.output_groups),
        ):
            if set(groups) != {"L", "R"}:
                raise ValueError(f"{name} must define exactly the sides L and R")
            if not any(groups.values()):
                raise ValueError(f"{name} must contain at least one neuron id")
        if self.sensory_population is None:
            object.__setattr__(
                self, "sensory_population", {s: list(v) for s, v in self.sensory_groups.items()}
            )
        population = self.sensory_population or {}
        if set(population) != {"L", "R"}:
            raise ValueError("sensory_population must define exactly the sides L and R")
        for side in ("L", "R"):
            groups = set(self.sensory_groups[side])
            excluded = set(self.excluded_sensory_ids.get(side, []))
            if not groups <= set(population[side]):
                raise ValueError(f"sensory_groups[{side}] must be a subset of sensory_population")
            if groups & excluded:
                raise ValueError(f"ids cannot be both stimulated and excluded on side {side}")
            if groups | excluded != set(population[side]):
                raise ValueError(
                    "sensory_groups + excluded_sensory_ids must equal "
                    f"sensory_population on side {side}"
                )
        if any(self.excluded_sensory_ids.values()) and not self.exclusion_reason:
            raise ValueError("excluded sensory ids require an exclusion_reason")
        overlap = set(self.all_sensory_ids()) & set(self.all_output_ids())
        if overlap:
            raise ValueError(f"neuron ids cannot be both sensory and output: {sorted(overlap)[:5]}")
        if not self.synthetic:
            if self.dataset.lower().startswith("synthetic"):
                raise ValueError("a biological config cannot reference a synthetic dataset")
            bad = [
                nid
                for nid in self.all_sensory_ids() + self.all_output_ids()
                if nid.startswith("syn_")
            ]
            if bad:
                raise ValueError(f"synthetic ids inside a biological configuration: {bad[:5]}")
            if not self.citations:
                raise ValueError("a biological config requires at least one citation")
            if self.biological_status == "UNSUPPORTED":
                raise ValueError("an UNSUPPORTED mapping must not be configured as biological")
        return self

    # ------------------------------------------------------------------ helpers
    def sensory_ids_for(self, sides: tuple[str, ...] | list[str]) -> list[str]:
        return sorted({nid for side in sides for nid in self.sensory_groups[side]})  # type: ignore[index]

    def all_sensory_ids(self) -> list[str]:
        return self.sensory_ids_for(("L", "R"))

    def all_output_ids(self) -> list[str]:
        return sorted({nid for ids in self.output_groups.values() for nid in ids})

    def all_population_ids(self) -> list[str]:
        population = self.sensory_population or self.sensory_groups
        return sorted({nid for ids in population.values() for nid in ids})

    def extractor_config(self) -> ExtractorConfig:
        return ExtractorConfig(
            seed_neuron_ids=self.all_population_ids(),
            target_neuron_ids=self.all_output_ids(),
            max_hops=self.extractor.max_hops,
            min_synapses=self.extractor.min_synapses,
            max_neurons=self.extractor.max_neurons,
            direction=self.extractor.direction,
            restrict_to_target_paths=self.extractor.restrict_to_target_paths,
        )

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> EscapeCircuitConfig:
        return cls.model_validate_json(Path(path).read_text())


def load_escape_config(name_or_path: str | Path = "escape_v1") -> EscapeCircuitConfig:
    path = Path(name_or_path)
    if not path.suffix:
        path = CONFIG_DIR / f"{name_or_path}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return EscapeCircuitConfig.load(path)
