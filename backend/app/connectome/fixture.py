"""Synthetic tiny-connectome adapter for tests and smoke tests (DATA.md §6).

EVERYTHING produced by this adapter is SYNTHETIC. Identifiers, types and edges are made
up for testing the pipeline and must never be presented as biological data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa

from app.connectome.adapter import (
    ConnectionsResult,
    DatasetAdapter,
    DatasetInfo,
    InspectionResult,
    RawFileRecord,
)
from app.connectome.normalize import (
    build_connections_table,
    build_neurons_table,
    filter_dangling,
    sha256_file,
)
from app.connectome.schema import SchemaValidationError

SYNTHETIC_MARKER = "SYNTHETIC"
FIXTURE_REQUIRED_TOP_LEVEL = ("dataset", "dataset_version", "synthetic", "neurons", "connections")
FIXTURE_NEURON_REQUIRED = ("neuron_id",)
FIXTURE_CONNECTION_REQUIRED = ("pre_neuron_id", "post_neuron_id", "synapse_count")

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "tiny_connectome.json"
)


class SyntheticFixtureAdapter(DatasetAdapter):
    def __init__(self, path: Path = DEFAULT_FIXTURE_PATH) -> None:
        self.path = Path(path)
        self._data: dict[str, Any] | None = None
        data = self._load()
        self.info = DatasetInfo(
            dataset=str(data["dataset"]),
            dataset_version=str(data["dataset_version"]),
            display_name=str(data.get("display_name", "Synthetic tiny connectome")),
            synthetic=True,
            source_page=None,
            download_url=None,
            license=str(
                data.get(
                    "license", "synthetic test fixture; no biological data; project license applies"
                )
            ),
            citation=None,
            notes=str(data.get("notes", "")),
        )

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            if not self.path.is_file():
                raise FileNotFoundError(f"fixture not found: {self.path}")
            self._data = json.loads(self.path.read_text())
        return self._data

    def inspect(self) -> InspectionResult:
        data = self._load()
        record = RawFileRecord(
            role="fixture",
            path=self.path,
            size_bytes=self.path.stat().st_size,
            sha256=sha256_file(self.path),
            columns=tuple(sorted({key for row in data["neurons"] for key in row})),
        )
        return InspectionResult(
            info=self.info,
            raw_files=[record],
            details={
                "neurons": len(data["neurons"]),
                "connections": len(data["connections"]),
                "synthetic_marker": SYNTHETIC_MARKER,
            },
        )

    def validate_schema(self) -> None:
        data = self._load()
        missing = [key for key in FIXTURE_REQUIRED_TOP_LEVEL if key not in data]
        if missing:
            raise SchemaValidationError(
                f"fixture {self.path.name}: missing top-level key(s) {missing}"
            )
        if data["synthetic"] is not True:
            raise SchemaValidationError(f"fixture {self.path.name}: 'synthetic' must be true")
        for index, row in enumerate(data["neurons"]):
            missing = [key for key in FIXTURE_NEURON_REQUIRED if key not in row]
            if missing:
                raise SchemaValidationError(f"fixture neuron #{index}: missing {missing}")
        for index, row in enumerate(data["connections"]):
            missing = [key for key in FIXTURE_CONNECTION_REQUIRED if key not in row]
            if missing:
                raise SchemaValidationError(f"fixture connection #{index}: missing {missing}")

    def load_neurons(self) -> pa.Table:
        self.validate_schema()
        rows = self._load()["neurons"]

        def column(name: str) -> pa.Array:
            return pa.array([row.get(name) for row in rows], pa.string())

        return build_neurons_table(
            column("neuron_id"),
            dataset=self.info.dataset,
            dataset_version=self.info.dataset_version,
            optional={
                "cell_type": column("cell_type"),
                "cell_class": column("cell_class"),
                "region": column("region"),
                "neurotransmitter": column("neurotransmitter"),
                "sex": column("sex"),
                "source_url": None,
            },
            extra_columns={"synthetic": pa.array([True] * len(rows), pa.bool_())},
        )

    def load_connections(
        self,
        neuron_ids: pa.Array | pa.ChunkedArray | None = None,
        *,
        keep_dangling: bool = False,
    ) -> ConnectionsResult:
        self.validate_schema()
        rows = self._load()["connections"]
        table = build_connections_table(
            pa.array([str(row["pre_neuron_id"]) for row in rows], pa.string()),
            pa.array([str(row["post_neuron_id"]) for row in rows], pa.string()),
            pa.array([int(row["synapse_count"]) for row in rows], pa.int64()),
            dataset=self.info.dataset,
            dataset_version=self.info.dataset_version,
        )
        if neuron_ids is None:
            return ConnectionsResult(table=table, dangling=None)
        filtered, report = filter_dangling(table, neuron_ids, keep_dangling=keep_dangling)
        return ConnectionsResult(table=filtered, dangling=report)
