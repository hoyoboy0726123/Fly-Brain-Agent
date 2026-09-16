"""DatasetAdapter interface (SDD §5) and shared descriptor types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa

from app.connectome.normalize import DanglingReport


@dataclass(frozen=True)
class DatasetInfo:
    """Dataset-level facts. Everything here must come from the source, never be guessed."""

    dataset: str
    dataset_version: str
    display_name: str
    synthetic: bool
    source_page: str | None = None
    download_url: str | None = None
    license: str | None = None
    citation: str | None = None
    notes: str = ""
    #: Human-readable name of the SOURCE DATASET (e.g. "MaleCNS"); defaults to ``dataset``.
    source_name: str | None = None
    #: Neuron count of the SOURCE DATASET as published/reported. This is never the count of
    #: the canonical simulation graph, which is a selected subset (DATA.md §8).
    official_neuron_count: int | None = None
    official_neuron_count_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "display_name": self.display_name,
            "synthetic": self.synthetic,
            "source_page": self.source_page,
            "download_url": self.download_url,
            "license": self.license,
            "citation": self.citation,
            "notes": self.notes,
            "source_name": self.source_name,
            "official_neuron_count": self.official_neuron_count,
            "official_neuron_count_source": self.official_neuron_count_source,
        }


@dataclass(frozen=True)
class RawFileRecord:
    """A raw input file as found on disk, with integrity information."""

    role: str
    path: Path
    size_bytes: int
    sha256: str
    md5: str | None = None
    expected_md5: str | None = None
    source_url: str | None = None
    columns: tuple[str, ...] = ()

    @property
    def md5_matches_expected(self) -> bool | None:
        if self.md5 is None or self.expected_md5 is None:
            return None
        return self.md5 == self.expected_md5

    def to_dict(self, relative_to: Path | None = None) -> dict[str, Any]:
        path = self.path
        if relative_to is not None:
            try:
                path = path.relative_to(relative_to)
            except ValueError:
                pass
        return {
            "role": self.role,
            "path": str(path),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "md5": self.md5,
            "expected_md5": self.expected_md5,
            "md5_matches_expected": self.md5_matches_expected,
            "source_url": self.source_url,
            "columns": list(self.columns),
        }


@dataclass(frozen=True)
class ConnectionsResult:
    table: pa.Table
    dangling: DanglingReport | None


@dataclass
class InspectionResult:
    """Raw-level inspection (files, hashes, columns) produced by ``DatasetAdapter.inspect``."""

    info: DatasetInfo
    raw_files: list[RawFileRecord] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, relative_to: Path | None = None) -> dict[str, Any]:
        return {
            "info": self.info.to_dict(),
            "raw_files": [record.to_dict(relative_to) for record in self.raw_files],
            "details": self.details,
        }


class DatasetAdapter(ABC):
    """Turns one dataset's raw files into normalized neurons/connections tables."""

    info: DatasetInfo

    @abstractmethod
    def inspect(self) -> InspectionResult:
        """Describe raw inputs (existence, size, hashes, columns) without transforming them."""

    @abstractmethod
    def validate_schema(self) -> None:
        """Raise ``SchemaValidationError`` if the raw inputs do not have the verified schema."""

    @abstractmethod
    def load_neurons(self) -> pa.Table:
        """Return the normalized neurons table (SDD §3)."""

    @abstractmethod
    def load_connections(
        self,
        neuron_ids: pa.Array | pa.ChunkedArray | None = None,
        *,
        keep_dangling: bool = False,
    ) -> ConnectionsResult:
        """Return the normalized connections table.

        When ``neuron_ids`` is given, edges touching unknown identifiers are counted in the
        dangling report and dropped unless ``keep_dangling`` is true.
        """
