"""Production adapter for the MaleCNS v1.0 flat-connectome release files.

Every constant below was verified against the official release bucket on 2026-09-16
(object listing, ``README_RELEASE_BUCKET.md``, Arrow IPC footers) and the official
website source (github.com/janelia-flyem/male-cns). See ``docs/dataset_research.md``.

BIOLOGICAL STRUCTURE layer: this module only reads and reshapes published data.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather
import pyarrow.ipc as ipc

from app.connectome.adapter import (
    ConnectionsResult,
    DatasetAdapter,
    DatasetInfo,
    InspectionResult,
    RawFileRecord,
)
from app.connectome.normalize import (
    DanglingReport,
    build_connections_table,
    build_neurons_table,
    classify_edges,
    ids_to_strings,
    md5_file,
    sha256_file,
)
from app.connectome.schema import RAW_PASSTHROUGH_PREFIX, SchemaValidationError

DATASET = "male-cns"
VERSION = "v1.0"
DISPLAY_NAME = "MaleCNS v1.0 (complete male Drosophila CNS connectome, Janelia FlyEM et al.)"
SOURCE_PAGE = "https://male-cns.janelia.org/download/"
BUCKET = "gs://flyem-male-cns"
FLAT_PREFIX = "v1.0/connectome-data/flat-connectome"
DOWNLOAD_URL = f"{BUCKET}/{FLAT_PREFIX}/"
HTTPS_BASE = "https://storage.googleapis.com/flyem-male-cns"
LICENSE = (
    "CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Official statement on "
    "male-cns.janelia.org/download: 'The Male CNS is licensed under CC-BY.'"
)
CITATION = (
    "MaleCNS paper, Cell, published 2026-09-03: "
    "https://www.cell.com/cell/fulltext/S0092-8674(26)00942-6 ; "
    "preprint: https://www.biorxiv.org/content/10.1101/2025.10.09.680999v2"
)
RELEASE_DATE = "2026-06-08"

ANNOTATIONS_FILE = "body-annotations-male-cns-v1.0-minconf-0.5.feather"
NEUROTRANSMITTERS_FILE = "body-neurotransmitters-male-cns-v1.0.feather"
WEIGHTS_FILE = "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
WEIGHTS_TRACED_ONLY_FILE = "connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather"
WEIGHTS_SIGNIFICANT_ONLY_FILE = (
    "connectome-weights-male-cns-v1.0-minconf-0.5-significant-only.feather"
)
BODY_STATS_FILE = "body-stats-male-cns-v1.0-minconf-0.5.feather"

#: md5 hashes exactly as published in the bucket object listing (base64).
BUCKET_MD5_BASE64: dict[str, str] = {
    ANNOTATIONS_FILE: "UKdxh3DFciDxYLpPQxq4ng==",
    NEUROTRANSMITTERS_FILE: "PYQrEv5cSe763lKNfdJKHw==",
    BODY_STATS_FILE: "QEwzScKFgBSOFoFeuZ84Kg==",
    WEIGHTS_FILE: "8w6dzKJc/QIb8eez2XVZng==",
    WEIGHTS_SIGNIFICANT_ONLY_FILE: "CfL4M/cWGkatM81vnJBy9g==",
    WEIGHTS_TRACED_ONLY_FILE: "ZgHUrQr6mf0D6wh5Ze8kIw==",
}

#: Column names read from the v1.0 Arrow IPC footers.
ANNOTATION_COLUMNS: tuple[str, ...] = (
    "assignedOlHex1", "assignedOlHex2", "bodyId", "flywireType", "group", "instance",
    "somaSide", "statusLabel", "superclass", "type", "vfbId", "hemibrainType", "itoleeHl",
    "supertype", "birthtime", "mancBodyid", "mancGroup", "mancType", "subclass", "synonyms",
    "class", "rootSide", "somaNeuromere", "trumanHl", "dimorphism", "matchingNotes",
    "entryNerve", "mancSerial", "mcnsSerial", "serialMotif", "fruDsx", "exitNerve",
    "receptorType", "somaLocation", "tosomaLocation", "status",
)  # fmt: skip
ANNOTATION_REQUIRED_COLUMNS: tuple[str, ...] = ("bodyId", "status", "type", "class")
WEIGHTS_REQUIRED_COLUMNS: tuple[str, ...] = ("body_pre", "body_post", "weight")
NEUROTRANSMITTER_COLUMNS: tuple[str, ...] = (
    "body", "cell_type", "total_nt_predictions", "predicted_nt_confidence", "predicted_nt",
    "ground_truth", "celltype_total_nt_predictions", "celltype_predicted_nt",
    "celltype_predicted_nt_confidence", "consensus_nt",
)  # fmt: skip
NEUROTRANSMITTER_REQUIRED_COLUMNS: tuple[str, ...] = ("body", "predicted_nt")
#: Neurotransmitter columns carried through (prefixed) next to the SDD column.
NEUROTRANSMITTER_PASSTHROUGH: tuple[str, ...] = (
    "predicted_nt_confidence", "total_nt_predictions", "consensus_nt",
    "celltype_predicted_nt", "ground_truth",
)  # fmt: skip

#: Dataset-level fact: the specimen is a single male fly (dataset name "Male CNS").
SPECIMEN_SEX = "male"

#: Default neuron definition: bodies whose ``status`` is "Traced" (proofread bodies; the
#: same rule the publishers use for their ``-traced-only`` connectivity table).
DEFAULT_STATUS_FILTER: tuple[str, ...] = ("Traced",)


def expected_md5_hex(file_name: str) -> str | None:
    encoded = BUCKET_MD5_BASE64.get(file_name)
    return base64.b64decode(encoded).hex() if encoded else None


def https_url(file_name: str) -> str:
    return f"{HTTPS_BASE}/{FLAT_PREFIX}/{file_name}"


@dataclass(frozen=True)
class MaleCnsConfig:
    """Where the raw files live and how neurons are selected."""

    raw_dir: Path
    annotations_file: str = ANNOTATIONS_FILE
    weights_file: str = WEIGHTS_FILE
    neurotransmitters_file: str | None = NEUROTRANSMITTERS_FILE
    #: ``status`` values that define the neuron set; empty tuple keeps every annotated body.
    neuron_status_filter: tuple[str, ...] = DEFAULT_STATUS_FILTER
    compute_hashes: bool = True
    extra_notes: tuple[str, ...] = field(default_factory=tuple)

    def path(self, file_name: str) -> Path:
        return Path(self.raw_dir) / file_name


class MaleCnsV1Adapter(DatasetAdapter):
    """Reads the published v1.0 body annotations, connection weights and NT predictions."""

    def __init__(self, config: MaleCnsConfig) -> None:
        self.config = config
        self.info = DatasetInfo(
            dataset=DATASET,
            dataset_version=VERSION,
            display_name=DISPLAY_NAME,
            synthetic=False,
            source_page=SOURCE_PAGE,
            download_url=DOWNLOAD_URL,
            license=LICENSE,
            citation=CITATION,
            notes=(
                f"Release date {RELEASE_DATE}. Structural connectivity from the published "
                "flat-connectome tables; synapse_count is the published 'weight' column "
                "(number of synaptic connections between the body pair in the minconf-0.5 tables)."
            ),
        )

    # ------------------------------------------------------------------ helpers
    def _roles(self) -> dict[str, str]:
        roles = {"annotations": self.config.annotations_file, "weights": self.config.weights_file}
        if self.config.neurotransmitters_file:
            roles["neurotransmitters"] = self.config.neurotransmitters_file
        return roles

    @staticmethod
    def _schema_of(path: Path) -> pa.Schema:
        with pa.memory_map(str(path), "r") as source:
            return ipc.open_file(source).schema

    def _require(self, path: Path, required: tuple[str, ...], role: str) -> pa.Schema:
        if not path.is_file():
            raise FileNotFoundError(f"MaleCNS {role} file not found: {path}")
        schema = self._schema_of(path)
        missing = [name for name in required if name not in schema.names]
        if missing:
            raise SchemaValidationError(
                f"MaleCNS {role} file {path.name}: missing required column(s) {missing}; "
                f"found {list(schema.names)}"
            )
        return schema

    # ------------------------------------------------------------ DatasetAdapter
    def inspect(self) -> InspectionResult:
        records: list[RawFileRecord] = []
        details: dict[str, Any] = {"missing_files": [], "column_diffs": {}}
        expected_columns = {
            "annotations": ANNOTATION_COLUMNS,
            "weights": WEIGHTS_REQUIRED_COLUMNS,
            "neurotransmitters": NEUROTRANSMITTER_COLUMNS,
        }
        for role, file_name in self._roles().items():
            path = self.config.path(file_name)
            if not path.is_file():
                details["missing_files"].append(str(path))
                continue
            columns = tuple(self._schema_of(path).names)
            expected = expected_columns[role]
            details["column_diffs"][role] = {
                "missing_vs_verified": [c for c in expected if c not in columns],
                "unexpected_vs_verified": [c for c in columns if c not in expected],
            }
            records.append(
                RawFileRecord(
                    role=role,
                    path=path,
                    size_bytes=path.stat().st_size,
                    sha256=sha256_file(path) if self.config.compute_hashes else "",
                    md5=md5_file(path) if self.config.compute_hashes else None,
                    expected_md5=expected_md5_hex(file_name),
                    source_url=https_url(file_name),
                    columns=columns,
                )
            )
        details["retrieved_at"] = (
            min(datetime.fromtimestamp(r.path.stat().st_mtime, tz=UTC) for r in records).isoformat(
                timespec="seconds"
            )
            if records
            else None
        )
        details["neuron_status_filter"] = list(self.config.neuron_status_filter)
        return InspectionResult(info=self.info, raw_files=records, details=details)

    def validate_schema(self) -> None:
        self._require(
            self.config.path(self.config.annotations_file),
            ANNOTATION_REQUIRED_COLUMNS,
            "annotations",
        )
        self._require(
            self.config.path(self.config.weights_file), WEIGHTS_REQUIRED_COLUMNS, "weights"
        )
        if self.config.neurotransmitters_file:
            self._require(
                self.config.path(self.config.neurotransmitters_file),
                NEUROTRANSMITTER_REQUIRED_COLUMNS,
                "neurotransmitters",
            )

    def load_neurons(self) -> pa.Table:
        self.validate_schema()
        annotations = feather.read_table(self.config.path(self.config.annotations_file))
        if self.config.neuron_status_filter:
            mask = pc.is_in(
                annotations["status"],
                value_set=pa.array(self.config.neuron_status_filter, pa.string()),
            )
            annotations = annotations.filter(mask)
        annotations = annotations.sort_by("bodyId")

        if pc.count_distinct(annotations["bodyId"]).as_py() != annotations.num_rows:
            raise SchemaValidationError("MaleCNS annotations: bodyId must be unique")

        if self.config.neurotransmitters_file:
            annotations = self._append_neurotransmitters(annotations)

        extras: dict[str, pa.Array | pa.ChunkedArray] = {}
        for name in annotations.column_names:
            if name == "bodyId":
                continue
            column = annotations[name]
            if pa.types.is_dictionary(column.type):
                column = column.combine_chunks().dictionary_decode()
            if name.startswith("__nt_"):
                extras[f"{RAW_PASSTHROUGH_PREFIX}nt_{name[len('__nt_') :]}"] = column
            else:
                extras[f"{RAW_PASSTHROUGH_PREFIX}{name}"] = column

        neurotransmitter = extras.pop(f"{RAW_PASSTHROUGH_PREFIX}nt_predicted_nt", None)
        return build_neurons_table(
            annotations["bodyId"],
            dataset=DATASET,
            dataset_version=VERSION,
            optional={
                "cell_type": annotations["type"],
                "cell_class": annotations["class"],
                # not present in the flat annotation table (docs/dataset_research.md §5.4)
                "region": None,
                "neurotransmitter": neurotransmitter,
                "sex": SPECIMEN_SEX,
                "source_url": https_url(self.config.annotations_file),
            },
            extra_columns=extras,
        )

    def _append_neurotransmitters(self, annotations: pa.Table) -> pa.Table:
        """Left-join the per-body NT prediction columns, aligned to ``annotations`` order.

        pyarrow joins reject list-typed payload columns (``somaLocation``), so the join runs
        on a ``bodyId``-only table and the aligned columns are appended afterwards.
        """
        path = self.config.path(self.config.neurotransmitters_file or "")
        wanted = ["body", "predicted_nt", *NEUROTRANSMITTER_PASSTHROUGH]
        available = self._schema_of(path).names
        nt = feather.read_table(path, columns=[c for c in wanted if c in available])
        if pc.count_distinct(nt["body"]).as_py() != nt.num_rows:
            raise SchemaValidationError("MaleCNS neurotransmitters: body must be unique")
        nt = nt.rename_columns(
            [f"__nt_{c}" if c != "body" else "__nt_body" for c in nt.column_names]
        )

        keys = annotations.select(["bodyId"])
        joined = keys.join(nt, keys="bodyId", right_keys="__nt_body", join_type="left outer")
        joined = joined.sort_by("bodyId")
        if joined.num_rows != annotations.num_rows:
            raise SchemaValidationError("MaleCNS neurotransmitters: join changed the row count")
        for name in joined.column_names:
            if name != "bodyId":
                annotations = annotations.append_column(name, joined[name])
        return annotations

    def load_connections(
        self,
        neuron_ids: pa.Array | pa.ChunkedArray | None = None,
        *,
        keep_dangling: bool = False,
    ) -> ConnectionsResult:
        self.validate_schema()
        known: pa.Array | None = None
        if neuron_ids is not None:
            known = pc.cast(pa.array(pc.unique(ids_to_strings(neuron_ids))), pa.int64())

        totals = {"kept": 0, "pre_unknown_only": 0, "post_unknown_only": 0, "both_unknown": 0}
        total_rows = 0
        kept: list[pa.Table] = []
        with pa.memory_map(str(self.config.path(self.config.weights_file)), "r") as source:
            reader = ipc.open_file(source)
            for index in range(reader.num_record_batches):
                batch = reader.get_batch(index).select(list(WEIGHTS_REQUIRED_COLUMNS))
                total_rows += batch.num_rows
                if known is None:
                    kept.append(pa.Table.from_batches([batch]))
                    continue
                mask, counts = classify_edges(
                    batch.column("body_pre"), batch.column("body_post"), known
                )
                for key, value in counts.items():
                    totals[key] += value
                table = pa.Table.from_batches([batch])
                kept.append(table if keep_dangling else table.filter(mask))

        combined = (
            pa.concat_tables(kept)
            if kept
            else pa.table(
                {
                    "body_pre": pa.array([], pa.int64()),
                    "body_post": pa.array([], pa.int64()),
                    "weight": pa.array([], pa.int64()),
                }
            )
        )
        combined = combined.sort_by([("body_pre", "ascending"), ("body_post", "ascending")])
        connections = build_connections_table(
            combined["body_pre"],
            combined["body_post"],
            combined["weight"],
            dataset=DATASET,
            dataset_version=VERSION,
        )
        report = None
        if known is not None:
            report = DanglingReport(
                total_edges_raw=total_rows,
                kept_edges=connections.num_rows,
                pre_unknown_only=totals["pre_unknown_only"],
                post_unknown_only=totals["post_unknown_only"],
                both_unknown=totals["both_unknown"],
                kept_dangling=keep_dangling,
            )
        return ConnectionsResult(table=connections, dangling=report)
