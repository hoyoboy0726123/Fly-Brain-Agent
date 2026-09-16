#!/usr/bin/env python3
"""Data validation report (DATA.md §7).

    scripts/inspect_dataset.py --fixture                 # synthetic fixture, in memory
    scripts/inspect_dataset.py                           # data/processed (production data)
    scripts/inspect_dataset.py --processed-dir PATH --json

Reports: neurons, directed connections, synapse_count min/max/median, missing IDs,
duplicate IDs, dangling edges, annotation columns, dataset/version/source/license.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.connectome import (  # noqa: E402
    InspectionReport,
    Provenance,
    SyntheticFixtureAdapter,
    inspect_tables,
    read_parquet,
)
from app.connectome.fixture import DEFAULT_FIXTURE_PATH  # noqa: E402


def report_fixture(path: Path, keep_dangling: bool) -> InspectionReport:
    adapter = SyntheticFixtureAdapter(path)
    adapter.validate_schema()
    neurons = adapter.load_neurons()
    result = adapter.load_connections(neurons["neuron_id"], keep_dangling=keep_dangling)
    provenance = {
        "dataset_name": adapter.info.dataset,
        "dataset_version": adapter.info.dataset_version,
        "license": adapter.info.license,
        "synthetic": True,
        "source_page": None,
        "download_url": None,
    }
    return inspect_tables(neurons, result.table, provenance=provenance)


def report_processed(processed_dir: Path) -> InspectionReport:
    neurons_path = processed_dir / "neurons.parquet"
    connections_path = processed_dir / "connections.parquet"
    provenance_path = processed_dir / "provenance.json"
    for path in (neurons_path, connections_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    provenance = (
        Provenance.read(provenance_path).model_dump(mode="json")
        if provenance_path.is_file()
        else None
    )
    return inspect_tables(
        read_parquet(neurons_path), read_parquet(connections_path), provenance=provenance
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="inspect the synthetic fixture instead of processed data",
    )
    parser.add_argument("--fixture-path", default=str(DEFAULT_FIXTURE_PATH))
    parser.add_argument(
        "--keep-dangling",
        action="store_true",
        help="(fixture) keep dangling edges so they show up in the report",
    )
    parser.add_argument(
        "--processed-dir", help="directory with neurons.parquet/connections.parquet/provenance.json"
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="exit 0 with a notice when processed data is absent",
    )
    args = parser.parse_args(argv)

    if args.fixture:
        report = report_fixture(Path(args.fixture_path), args.keep_dangling)
    else:
        processed_dir = (
            Path(args.processed_dir) if args.processed_dir else get_settings().processed_data_dir
        )
        try:
            report = report_processed(processed_dir)
        except FileNotFoundError as exc:
            message = (
                f"[inspect] no normalized data at {exc} (run scripts/normalize_dataset.py first)"
            )
            if args.allow_missing:
                print(message)
                return 0
            print(message, file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
    else:
        print(report.to_markdown(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
