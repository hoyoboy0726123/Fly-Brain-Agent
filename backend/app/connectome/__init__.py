"""BIOLOGICAL STRUCTURE layer: dataset adapters and normalized tables (P1).

- ``schema``      normalized data model (SDD §3) and fail-loud validation
- ``normalize``   pure raw → normalized transformations, dangling-edge accounting
- ``adapter``     ``DatasetAdapter`` interface and descriptors
- ``malecns``     production adapter for the MaleCNS v1.0 release files
- ``fixture``     SYNTHETIC tiny fixture adapter for tests (never biological data)
- ``provenance``  ``provenance.json`` model (DATA.md §3)
- ``inspect``     DATA.md §7 validation report
"""

from app.connectome.adapter import (
    ConnectionsResult,
    DatasetAdapter,
    DatasetInfo,
    InspectionResult,
    RawFileRecord,
)
from app.connectome.fixture import SyntheticFixtureAdapter
from app.connectome.inspect import InspectionReport, inspect_tables
from app.connectome.malecns import MaleCnsConfig, MaleCnsV1Adapter
from app.connectome.normalize import DanglingReport, filter_dangling, read_parquet, write_parquet
from app.connectome.provenance import Provenance, RawFileEntry
from app.connectome.schema import (
    SchemaValidationError,
    validate_connections_table,
    validate_neurons_table,
)

__all__ = [
    "ConnectionsResult",
    "DanglingReport",
    "DatasetAdapter",
    "DatasetInfo",
    "InspectionReport",
    "InspectionResult",
    "MaleCnsConfig",
    "MaleCnsV1Adapter",
    "Provenance",
    "RawFileEntry",
    "RawFileRecord",
    "SchemaValidationError",
    "SyntheticFixtureAdapter",
    "filter_dangling",
    "inspect_tables",
    "read_parquet",
    "validate_connections_table",
    "validate_neurons_table",
    "write_parquet",
]
