"""Provenance manifest (DATA.md §3), extended with integrity and normalization details."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RawFileEntry(BaseModel):
    role: str
    path: str
    size_bytes: int
    sha256: str
    md5: str | None = None
    expected_md5: str | None = None
    md5_matches_expected: bool | None = None
    source_url: str | None = None
    columns: list[str] = Field(default_factory=list)


class SourceDataset(BaseModel):
    """The published dataset as released (DATA.md §8). Counts here describe the SOURCE."""

    name: str
    version: str
    official_neuron_count: int | None = None
    official_neuron_count_source: str | None = None
    annotated_bodies_total: int | None = None
    raw_connection_rows: int | None = None
    status_counts: dict[str, int] = Field(default_factory=dict)
    description: str = (
        "The source dataset as published. The canonical simulation graph is a selected subset "
        "of it; its counts must never be presented as the dataset's neuron census."
    )


class CanonicalGraph(BaseModel):
    """The subset of the source dataset used as the simulation graph (DATA.md §8)."""

    selection_rule: str = Field(min_length=1)
    neuron_count: int = Field(ge=0)
    connection_count: int = Field(ge=0)
    dropped_dangling_edges: int | None = None
    includes_dangling_edges: bool = False
    description: str = (
        "Canonical simulation graph: neurons selected by selection_rule and the directed "
        "connections between them. NOT the complete neuron census of the source dataset."
    )


class Provenance(BaseModel):
    """Contents of ``provenance.json``. Field names follow the DATA.md example."""

    dataset_name: str
    dataset_version: str
    source_page: str | None = None
    download_url: str | None = None
    retrieved_at: str | None = None
    license: str | None = None
    raw_files: list[RawFileEntry] = Field(default_factory=list)
    transform_script: str = ""
    notes: str = ""

    # Extensions (not in the DATA.md example, additive only)
    synthetic: bool = False
    citation: str | None = None
    generated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    generator: dict[str, Any] = Field(default_factory=dict)
    normalization: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)

    # DATA.md §8: the source dataset and the canonical simulation graph are distinct things.
    source_dataset: SourceDataset | None = None
    canonical_graph: CanonicalGraph | None = None

    @model_validator(mode="after")
    def _requirements_for_biological_data(self) -> Provenance:
        if self.synthetic:
            return self
        if not (self.license or "").strip():
            raise ValueError("license must not be blank for a non-synthetic dataset (DATA.md §3)")
        if self.source_dataset is None or self.canonical_graph is None:
            raise ValueError(
                "source_dataset and canonical_graph are required for a non-synthetic dataset "
                "(DATA.md §8: the canonical graph is a subset, not the dataset census)"
            )
        return self

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
        )
        return path

    @classmethod
    def read(cls, path: Path) -> Provenance:
        return cls.model_validate_json(path.read_text())
