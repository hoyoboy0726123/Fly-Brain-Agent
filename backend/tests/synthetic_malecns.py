"""Build SYNTHETIC raw files that mirror the verified MaleCNS v1.0 flat-connectome schema.

Column names and types copy the published files so the production adapter can be tested
offline. Every VALUE is invented (small integers, ``SYNTHETIC_*`` labels). Nothing here is
biological data; these files are written only into pytest temporary directories.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.feather as feather

from app.connectome.malecns import (
    ANNOTATION_COLUMNS,
    ANNOTATIONS_FILE,
    NEUROTRANSMITTER_COLUMNS,
    NEUROTRANSMITTERS_FILE,
    WEIGHTS_FILE,
)

#: bodyId -> (status, type, class, superclass, statusLabel)
SYNTHETIC_BODIES: dict[int, tuple[str | None, str | None, str | None, str | None, str | None]] = {
    1001: ("Traced", "SYNTHETIC_TYPE_A", "synthetic_class_x", "synthetic_super_1", "Reviewed"),
    1002: ("Traced", "SYNTHETIC_TYPE_A", "synthetic_class_x", "synthetic_super_1", "Reviewed"),
    1003: ("Traced", "SYNTHETIC_TYPE_B", None, "synthetic_super_2", "Roughly traced"),
    1004: (
        "Traced",
        "SYNTHETIC_TYPE_C",
        "synthetic_class_y",
        "synthetic_super_2",
        "Roughly traced",
    ),
    1005: ("Traced", None, None, None, "Roughly traced"),
    1006: ("Orphan", None, None, None, "Orphan"),
    1007: ("Glia", None, None, None, "Glia"),
    1008: ("Assign", None, None, None, "0.5assign"),
}
TRACED_IDS = [b for b, row in SYNTHETIC_BODIES.items() if row[0] == "Traced"]

#: (body_pre, body_post, weight)
SYNTHETIC_EDGES: list[tuple[int, int, int]] = [
    (1001, 1003, 12),
    (1002, 1003, 4),
    (1003, 1004, 30),
    (1004, 1005, 2),
    (1005, 1001, 1),
    (1004, 1004, 1),  # self-loop among Traced bodies
    (1001, 1006, 5),  # post is Orphan -> dangling under the Traced rule
    (1007, 1003, 3),  # pre is Glia   -> dangling
    (1006, 1007, 2),  # both unknown  -> dangling
    (1008, 1002, 7),  # pre is Assign -> dangling under the default rule
]
EXPECTED_TRACED_EDGES = [e for e in SYNTHETIC_EDGES if e[0] in TRACED_IDS and e[1] in TRACED_IDS]

#: body -> predicted_nt
SYNTHETIC_NT: dict[int, str] = {
    1001: "synthetic_nt_a",
    1002: "synthetic_nt_a",
    1003: "unclear",
    1006: "synthetic_nt_b",
}


def _annotations_table(drop_columns: tuple[str, ...] = ()) -> pa.Table:
    body_ids = sorted(SYNTHETIC_BODIES)
    n = len(body_ids)
    columns: dict[str, pa.Array] = {}
    for name in ANNOTATION_COLUMNS:
        if name == "bodyId":
            columns[name] = pa.array(body_ids, pa.int64())
        elif name == "status":
            columns[name] = pa.array([SYNTHETIC_BODIES[b][0] for b in body_ids], pa.string())
        elif name == "type":
            columns[name] = pa.array([SYNTHETIC_BODIES[b][1] for b in body_ids], pa.string())
        elif name == "class":
            columns[name] = pa.array([SYNTHETIC_BODIES[b][2] for b in body_ids], pa.string())
        elif name == "superclass":
            columns[name] = pa.array([SYNTHETIC_BODIES[b][3] for b in body_ids], pa.string())
        elif name == "statusLabel":
            columns[name] = pa.array(
                [SYNTHETIC_BODIES[b][4] for b in body_ids], pa.string()
            ).dictionary_encode()
        elif name in ("somaLocation", "tosomaLocation"):
            columns[name] = pa.array([None] * n, pa.list_(pa.int64()))
        elif name in (
            "assignedOlHex1",
            "assignedOlHex2",
            "group",
            "mancBodyid",
            "mancGroup",
            "mancSerial",
            "mcnsSerial",
        ):
            columns[name] = pa.array([None] * n, pa.float64())
        else:
            columns[name] = pa.array([None] * n, pa.string())
    table = pa.table(columns)
    if drop_columns:
        table = table.drop_columns(list(drop_columns))
    return table


def _weights_table() -> pa.Table:
    return pa.table(
        {
            "body_pre": pa.array([e[0] for e in SYNTHETIC_EDGES], pa.int64()),
            "body_post": pa.array([e[1] for e in SYNTHETIC_EDGES], pa.int64()),
            "weight": pa.array([e[2] for e in SYNTHETIC_EDGES], pa.int64()),
        }
    )


def _neurotransmitters_table() -> pa.Table:
    bodies = sorted(SYNTHETIC_NT)
    n = len(bodies)
    columns: dict[str, pa.Array] = {}
    for name in NEUROTRANSMITTER_COLUMNS:
        if name == "body":
            columns[name] = pa.array(bodies, pa.int64())
        elif name == "predicted_nt":
            columns[name] = pa.array([SYNTHETIC_NT[b] for b in bodies], pa.string())
        elif name == "consensus_nt":
            columns[name] = pa.array(["synthetic_consensus"] * n, pa.string())
        elif name in ("total_nt_predictions", "celltype_total_nt_predictions"):
            columns[name] = pa.array([10] * n, pa.int32())
        elif name in ("predicted_nt_confidence", "celltype_predicted_nt_confidence"):
            columns[name] = pa.array([0.5] * n, pa.float64())
        else:
            columns[name] = pa.array([None] * n, pa.string())
    return pa.table(columns)


def write_synthetic_malecns_raw(
    raw_dir: Path,
    *,
    drop_annotation_columns: tuple[str, ...] = (),
    include_weights: bool = True,
    include_neurotransmitters: bool = True,
) -> dict[str, Path]:
    """Write synthetic Feather files with the MaleCNS v1.0 file names into ``raw_dir``."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    path = raw_dir / ANNOTATIONS_FILE
    feather.write_feather(_annotations_table(drop_annotation_columns), path)
    written["annotations"] = path
    if include_weights:
        path = raw_dir / WEIGHTS_FILE
        feather.write_feather(_weights_table(), path)
        written["weights"] = path
    if include_neurotransmitters:
        path = raw_dir / NEUROTRANSMITTERS_FILE
        feather.write_feather(_neurotransmitters_table(), path)
        written["neurotransmitters"] = path
    return written
