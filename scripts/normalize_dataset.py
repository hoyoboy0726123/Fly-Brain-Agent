#!/usr/bin/env python3
"""Raw → normalized ingestion (P1): neurons.parquet, connections.parquet, provenance.json.

Examples
--------
Production (MaleCNS v1.0 files already downloaded into data/raw):
    backend/.venv/bin/python scripts/normalize_dataset.py --adapter malecns

Synthetic fixture (no download needed):
    backend/.venv/bin/python scripts/normalize_dataset.py --adapter fixture --out-dir /tmp/fx

Raw files are never modified. Outputs are written to --out-dir (default: data/processed).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import pyarrow as pa  # noqa: E402

from app import __version__  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.connectome import (  # noqa: E402
    DatasetAdapter,
    MaleCnsConfig,
    MaleCnsV1Adapter,
    Provenance,
    RawFileEntry,
    SyntheticFixtureAdapter,
    inspect_tables,
    write_parquet,
)
from app.connectome.fixture import DEFAULT_FIXTURE_PATH  # noqa: E402


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_adapter(args: argparse.Namespace) -> DatasetAdapter:
    if args.adapter == "fixture":
        return SyntheticFixtureAdapter(Path(args.fixture))
    settings = get_settings()
    raw_dir = Path(args.raw_dir) if args.raw_dir else settings.malecns_raw_dir
    status_filter: tuple[str, ...] = (
        tuple(args.status) if args.status is not None else MaleCnsConfig.neuron_status_filter
    )
    if args.all_statuses:
        status_filter = ()
    return MaleCnsV1Adapter(
        MaleCnsConfig(
            raw_dir=raw_dir,
            weights_file=args.weights_file or MaleCnsConfig.weights_file,
            neurotransmitters_file=None
            if args.no_neurotransmitters
            else MaleCnsConfig.neurotransmitters_file,
            neuron_status_filter=status_filter,
            compute_hashes=not args.no_hash,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--adapter", choices=("malecns", "fixture"), required=True)
    parser.add_argument("--raw-dir", help="directory containing the MaleCNS flat-connectome files")
    parser.add_argument("--out-dir", help="output directory (default: <repo>/data/processed)")
    parser.add_argument(
        "--fixture", default=str(DEFAULT_FIXTURE_PATH), help="fixture JSON path (adapter=fixture)"
    )
    parser.add_argument(
        "--status", nargs="*", help="status values defining the neuron set (default: Traced)"
    )
    parser.add_argument(
        "--all-statuses", action="store_true", help="keep every annotated body regardless of status"
    )
    parser.add_argument(
        "--weights-file", help="alternative weights file name (e.g. the -traced-only variant)"
    )
    parser.add_argument(
        "--no-neurotransmitters", action="store_true", help="skip the body-neurotransmitters table"
    )
    parser.add_argument(
        "--keep-dangling",
        action="store_true",
        help="keep edges whose endpoints are not in the neuron set",
    )
    parser.add_argument(
        "--no-hash", action="store_true", help="skip sha256/md5 of raw files (faster)"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    out_dir = Path(args.out_dir) if args.out_dir else settings.processed_data_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    adapter = build_adapter(args)
    print(
        f"[normalize] adapter={adapter.info.dataset} {adapter.info.dataset_version} "
        f"synthetic={adapter.info.synthetic}"
    )

    adapter.validate_schema()
    print("[normalize] raw schema validated")
    inspection = adapter.inspect()
    for record in inspection.raw_files:
        verdict = {True: "md5 OK", False: "MD5 MISMATCH", None: "md5 n/a"}[
            record.md5_matches_expected
        ]
        print(
            f"[normalize]   {record.role:<18} {record.path.name} "
            f"{record.size_bytes:,} bytes  {verdict}"
        )
    mismatched = [r for r in inspection.raw_files if r.md5_matches_expected is False]
    if mismatched:
        print(
            "[normalize] FAIL: raw file checksum mismatch — refusing to normalize", file=sys.stderr
        )
        return 1

    neurons = adapter.load_neurons()
    print(f"[normalize] neurons: {neurons.num_rows:,} rows, {neurons.num_columns} columns")
    result = adapter.load_connections(neurons["neuron_id"], keep_dangling=args.keep_dangling)
    connections = result.table
    print(f"[normalize] connections: {connections.num_rows:,} rows")
    if result.dangling:
        d = result.dangling
        print(
            f"[normalize] dangling edges: {d.dangling_edges:,} of {d.total_edges_raw:,} raw edges "
            f"(pre unknown {d.pre_unknown_only:,}, post unknown {d.post_unknown_only:,}, "
            f"both {d.both_unknown:,}); {'kept' if d.kept_dangling else 'dropped'}"
        )

    neurons_path = write_parquet(neurons, out_dir / "neurons.parquet")
    connections_path = write_parquet(connections, out_dir / "connections.parquet")

    provenance = Provenance(
        dataset_name=adapter.info.dataset,
        dataset_version=adapter.info.dataset_version,
        source_page=adapter.info.source_page,
        download_url=adapter.info.download_url,
        retrieved_at=inspection.details.get("retrieved_at"),
        license=adapter.info.license,
        raw_files=[
            RawFileEntry(**r.to_dict(relative_to=PROJECT_ROOT)) for r in inspection.raw_files
        ],
        transform_script="scripts/normalize_dataset.py",
        notes=adapter.info.notes,
        synthetic=adapter.info.synthetic,
        citation=adapter.info.citation,
        generator={
            "code_version": __version__,
            "git_commit": git_commit(),
            "pyarrow_version": pa.__version__,
            "python_version": sys.version.split()[0],
            "argv": sys.argv[1:] if argv is None else argv,
        },
        normalization={
            "identifier_policy": "identifiers cast to strings (DATA.md §5)",
            "neuron_set_rule": inspection.details.get("neuron_status_filter", "all rows"),
            "keep_dangling": args.keep_dangling,
            "column_mapping": {
                "neuron_id": "bodyId" if not adapter.info.synthetic else "neuron_id",
                "cell_type": "type" if not adapter.info.synthetic else "cell_type",
                "cell_class": "class" if not adapter.info.synthetic else "cell_class",
                "region": "null (not in flat annotation table)"
                if not adapter.info.synthetic
                else "region",
                "neurotransmitter": (
                    "body-neurotransmitters predicted_nt (prediction by the dataset providers)"
                    if not adapter.info.synthetic
                    else "neurotransmitter"
                ),
                "sex": "constant 'male' (dataset-level specimen sex)"
                if not adapter.info.synthetic
                else "sex",
                "synapse_count": "weight" if not adapter.info.synthetic else "synapse_count",
                "passthrough_prefix": "mcns_" if not adapter.info.synthetic else None,
            },
        },
        counts={
            "neurons": neurons.num_rows,
            "connections": connections.num_rows,
            "dangling": result.dangling.to_dict() if result.dangling else None,
        },
        outputs={
            "neurons": str(neurons_path.relative_to(PROJECT_ROOT))
            if neurons_path.is_relative_to(PROJECT_ROOT)
            else str(neurons_path),
            "connections": str(connections_path.relative_to(PROJECT_ROOT))
            if connections_path.is_relative_to(PROJECT_ROOT)
            else str(connections_path),
        },
    )
    provenance_path = provenance.write(out_dir / "provenance.json")

    report = inspect_tables(neurons, connections, provenance=provenance.model_dump(mode="json"))
    (out_dir / "inspection_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n"
    )
    (out_dir / "inspection_report.md").write_text(report.to_markdown())

    print(f"[normalize] wrote {neurons_path}")
    print(f"[normalize] wrote {connections_path}")
    print(f"[normalize] wrote {provenance_path}")
    print(f"[normalize] wrote {out_dir / 'inspection_report.json'} and .md")
    print(f"[normalize] done in {time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
