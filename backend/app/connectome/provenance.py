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

    @model_validator(mode="after")
    def _license_required_for_biological_data(self) -> Provenance:
        if not self.synthetic and not (self.license or "").strip():
            raise ValueError("license must not be blank for a non-synthetic dataset (DATA.md §3)")
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
