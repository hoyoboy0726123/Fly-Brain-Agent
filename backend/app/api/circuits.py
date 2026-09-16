"""Read-only circuit inspection API (P6): the biological structure behind the demo.

Every neuron and edge served here is read from a P2 circuit artifact
(``data/circuits/<circuit_id>.json``, hash-verified on load). Nothing is reconstructed,
inferred or completed: a field the artifact does not carry is returned as ``null`` and the
UI shows "Not available". Only the loaded circuit is ever served — never the canonical
graph (165,122 neurons / 25.56 M connections).

Labels are part of the payloads so that clients cannot present structure as activity or
simulation weights as biological strengths:

- structural fields  → ``STRUCTURAL_LABEL`` (biological data)
- ``simulation_weight`` → ``SIMULATION_WEIGHT_LABEL`` (computational transformation)
"""

from __future__ import annotations

import re
import threading
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ValidationError

from app.api.escape import EscapeService, EscapeServiceError, _holder
from app.behavior import DISCLAIMER, Citation
from app.circuits import Circuit
from app.circuits.artifact import CanonicalGraphRef, CircuitNode, ExtractorConfig, TargetReport
from app.circuits.errors import ArtifactIntegrityError
from app.config import Settings, get_settings
from app.simulation import PARAMETER_LABEL, SimulationConfig
from app.simulation.weights import normalize_weight

router = APIRouter(tags=["circuits"])

CIRCUIT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
STRUCTURAL_LABEL = "Structural connection — biological data (MaleCNS circuit artifact)"
NEURON_LABEL = "BIOLOGICAL METADATA — neuron identity from the dataset annotations"
CIRCUIT_META_LABEL = "CIRCUIT / SIMULATION METADATA — extractor and behaviour configuration"
SYNAPSE_COUNT_LABEL = "Biological structural observation (synapse count in the dataset)"
SIMULATION_WEIGHT_LABEL = (
    "Computational simulation weight — transform(synapse_count) × weight_scale; "
    "not a biological synaptic strength"
)
NEIGHBORS_LABEL = "Connections within loaded circuit (not the complete MaleCNS neighbourhood)"
NOT_AVAILABLE = "Not available"
MAX_NODES_PAGE = 1000
MAX_EDGES_PAGE = 2000

Direction = Literal["upstream", "downstream", "both"]


# ----------------------------------------------------------------------------- schemas
class CircuitListItem(BaseModel):
    circuit_id: str
    dataset: str
    dataset_version: str
    circuit_hash: str
    neurons: int
    edges: int
    biological_status: str | None = None


class BiologicalMetadata(BaseModel):
    label: str = NEURON_LABEL
    neuron_id: str
    cell_type: str | None
    cell_class: str | None
    neurotransmitter_prediction: str | None
    dataset: str
    dataset_version: str


class CircuitMetadata(BaseModel):
    label: str = CIRCUIT_META_LABEL
    minimum_hop_from_seed: int
    is_seed: bool
    is_target: bool
    side: str | None = None
    role: str | None = None
    stimulated_by_config: bool | None = None


class ConnectivitySummary(BaseModel):
    label: str = NEIGHBORS_LABEL
    in_degree: int
    out_degree: int
    in_synapses: int
    out_synapses: int


class NodeRecord(BaseModel):
    neuron_id: str
    cell_type: str | None
    cell_class: str | None
    neurotransmitter_prediction: str | None
    dataset: str
    dataset_version: str
    minimum_hop_from_seed: int
    is_seed: bool
    is_target: bool
    side: str | None
    role: str | None
    in_degree: int
    out_degree: int
    in_synapses: int
    out_synapses: int


class NodesPage(BaseModel):
    circuit_id: str
    circuit_hash: str
    label: str = NEURON_LABEL
    total: int
    offset: int
    limit: int
    items: list[NodeRecord]


class SimulationWeight(BaseModel):
    label: str = SIMULATION_WEIGHT_LABEL
    value: float
    weight_transform: str
    weight_scale: float
    parameter_label: str = PARAMETER_LABEL


class EdgeRecord(BaseModel):
    label: str = STRUCTURAL_LABEL
    pre_neuron_id: str
    post_neuron_id: str
    synapse_count: int
    synapse_count_label: str = SYNAPSE_COUNT_LABEL
    dataset: str
    dataset_version: str
    simulation_weight: SimulationWeight | None = None


class EdgesPage(BaseModel):
    circuit_id: str
    circuit_hash: str
    label: str = STRUCTURAL_LABEL
    total: int
    offset: int
    limit: int
    items: list[EdgeRecord]


class EdgeDetail(BaseModel):
    label: Literal["BIOLOGICAL STRUCTURAL CONNECTION"] = "BIOLOGICAL STRUCTURAL CONNECTION"
    pre: BiologicalMetadata
    post: BiologicalMetadata
    synapse_count: int
    synapse_count_label: str = SYNAPSE_COUNT_LABEL
    dataset: str
    dataset_version: str
    circuit_id: str
    circuit_hash: str
    simulation_weight: SimulationWeight | None


class NeuronDetail(BaseModel):
    circuit_id: str
    circuit_hash: str
    biological: BiologicalMetadata
    circuit: CircuitMetadata
    connectivity: ConnectivitySummary
    not_available_marker: str = NOT_AVAILABLE


class NeighborRecord(BaseModel):
    neuron_id: str
    cell_type: str | None
    synapse_count: int
    pre_neuron_id: str
    post_neuron_id: str
    dataset: str
    dataset_version: str


class NeighborList(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[NeighborRecord]


class NeighborsResponse(BaseModel):
    label: str = NEIGHBORS_LABEL
    circuit_id: str
    circuit_hash: str
    neuron_id: str
    direction: Direction
    upstream: NeighborList | None
    downstream: NeighborList | None


class CircuitSummary(BaseModel):
    circuit_id: str
    dataset: str
    dataset_version: str
    circuit_hash: str
    canonical_graph: CanonicalGraphRef
    extractor_config: ExtractorConfig
    seed_neurons: int
    target_neurons: list[TargetReport]
    neurons: int
    edges: int
    synapses_total: int
    cell_type_counts: dict[str, int]
    extracted_at: str
    extractor_version: str
    biological_interpretation: str
    biological_status: str | None
    research_document: str | None
    config_version: str | None
    disclaimer: str = DISCLAIMER


class SourceDatasetInfo(BaseModel):
    name: str
    version: str
    official_neuron_count: int | None
    official_neuron_count_source: str | None
    description: str | None


class CanonicalGraphInfo(BaseModel):
    selection_rule: str
    neuron_count: int
    connection_count: int
    description: str | None


class RawFileInfo(BaseModel):
    role: str
    path: str
    sha256: str | None


class ProvenanceResponse(BaseModel):
    disclaimer: str = DISCLAIMER
    circuit_id: str
    circuit_hash: str
    expected_circuit_hash: str | None
    circuit_verified: bool
    biological_status: str | None
    research_document: str | None
    dataset: str
    dataset_version: str
    license: str | None
    source_page: str | None
    download_url: str | None
    source_dataset: SourceDatasetInfo | None
    canonical_graph: CanonicalGraphInfo
    canonical_graph_note: str = (
        "The canonical simulation graph is a selected subset of the source dataset; its "
        "counts are NOT the complete MaleCNS neuron census."
    )
    loaded_circuit: dict[str, int]
    raw_files: list[RawFileInfo]
    graph_fingerprint: str
    extracted_at: str
    extractor_version: str
    citations: list[Citation]
    mapping_confidence: dict[str, str]
    limitations: list[str]


# ----------------------------------------------------------------------------- catalog
class LoadedCircuit:
    """A hash-verified artifact with the indexes the endpoints need."""

    def __init__(self, circuit: Circuit) -> None:
        self.circuit = circuit
        self.circuit_hash = circuit.provenance.circuit_hash or circuit.compute_hash()
        self.nodes: dict[str, CircuitNode] = {n.neuron_id: n for n in circuit.nodes}
        self.out_edges: dict[str, list[int]] = {nid: [] for nid in self.nodes}
        self.in_edges: dict[str, list[int]] = {nid: [] for nid in self.nodes}
        self.edge_index: dict[tuple[str, str], int] = {}
        for index, edge in enumerate(circuit.edges):
            self.out_edges.setdefault(edge.pre_neuron_id, []).append(index)
            self.in_edges.setdefault(edge.post_neuron_id, []).append(index)
            self.edge_index[(edge.pre_neuron_id, edge.post_neuron_id)] = index

    def degree(self, neuron_id: str) -> ConnectivitySummary:
        edges = self.circuit.edges
        ins = self.in_edges.get(neuron_id, [])
        outs = self.out_edges.get(neuron_id, [])
        return ConnectivitySummary(
            in_degree=len(ins),
            out_degree=len(outs),
            in_synapses=sum(edges[i].synapse_count for i in ins),
            out_synapses=sum(edges[i].synapse_count for i in outs),
        )


class CircuitCatalog:
    """Loads artifacts from ``circuits_data_dir`` on demand and caches them by id."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._loaded: dict[str, LoadedCircuit] = {}

    def get(self, circuit_id: str) -> LoadedCircuit:
        if not CIRCUIT_ID_PATTERN.match(circuit_id) or ".." in circuit_id:
            raise HTTPException(
                404, detail={"error": "circuit_not_found", "message": "invalid circuit id"}
            )
        with self._lock:
            cached = self._loaded.get(circuit_id)
            if cached is not None:
                return cached
            path = self.settings.circuits_data_dir / f"{circuit_id}.json"
            if not path.is_file():
                raise HTTPException(
                    404,
                    detail={"error": "circuit_not_found", "message": f"{path.name} not found"},
                )
            try:
                circuit = Circuit.load(path, verify=True)
            except ArtifactIntegrityError as exc:
                raise HTTPException(
                    503, detail={"error": "circuit_mismatch", "message": str(exc)}
                ) from exc
            except (ValidationError, ValueError, OSError) as exc:
                raise HTTPException(
                    503, detail={"error": "circuit_unavailable", "message": str(exc)}
                ) from exc
            loaded = self._loaded[circuit_id] = LoadedCircuit(circuit)
            return loaded

    def list(self) -> list[str]:
        directory = self.settings.circuits_data_dir
        if not directory.is_dir():
            return []
        ids = []
        for path in sorted(directory.glob("*.json")):
            if path.name.endswith(".perf.json"):
                continue
            ids.append(path.stem)
        return ids


def get_catalog(request: Request, settings: Annotated[Settings, Depends(get_settings)]):
    catalog = getattr(request.app.state, "circuits", None)
    if catalog is None:
        catalog = request.app.state.circuits = CircuitCatalog(settings)
    return catalog


CatalogDep = Annotated[CircuitCatalog, Depends(get_catalog)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


# ----------------------------------------------------------------------------- behaviour context
class BehaviourContext:
    """Sides / roles / simulation parameters from the escape config that uses a circuit."""

    def __init__(self, service: EscapeService | None) -> None:
        self.service = service
        self.side_of: dict[str, str] = {}
        self.role_of: dict[str, str] = {}
        self.stimulated: set[str] = set()
        if service is not None:
            cfg = service.config
            population = cfg.sensory_population or cfg.sensory_groups
            for side, ids in population.items():
                for nid in ids:
                    self.side_of[nid] = side
                    self.role_of[nid] = "sensory"
            for side, ids in cfg.output_groups.items():
                for nid in ids:
                    self.side_of[nid] = side
                    self.role_of[nid] = "output"
            self.stimulated = set(cfg.all_sensory_ids())

    @property
    def simulation_config(self) -> SimulationConfig:
        if self.service is not None:
            return self.service.experiment.simulation_config
        return SimulationConfig()

    @property
    def biological_status(self) -> str | None:
        return self.service.config.biological_status if self.service else None

    @property
    def research_document(self) -> str | None:
        return self.service.config.research_document if self.service else None

    @property
    def config_version(self) -> str | None:
        return self.service.config.config_version if self.service else None


def behaviour_context(request: Request, settings: Settings, circuit_id: str) -> BehaviourContext:
    try:
        service = _holder(request.app.state, settings).get()
    except EscapeServiceError:
        return BehaviourContext(None)
    if service.circuit.circuit_id != circuit_id:
        return BehaviourContext(None)
    return BehaviourContext(service)


# ----------------------------------------------------------------------------- helpers
def _biological(node: CircuitNode, circuit: Circuit) -> BiologicalMetadata:
    return BiologicalMetadata(
        neuron_id=node.neuron_id,
        cell_type=node.cell_type,
        cell_class=node.cell_class,
        neurotransmitter_prediction=node.neurotransmitter,
        dataset=circuit.dataset,
        dataset_version=circuit.dataset_version,
    )


def _node_record(loaded: LoadedCircuit, node: CircuitNode, ctx: BehaviourContext) -> NodeRecord:
    degree = loaded.degree(node.neuron_id)
    circuit = loaded.circuit
    return NodeRecord(
        neuron_id=node.neuron_id,
        cell_type=node.cell_type,
        cell_class=node.cell_class,
        neurotransmitter_prediction=node.neurotransmitter,
        dataset=circuit.dataset,
        dataset_version=circuit.dataset_version,
        minimum_hop_from_seed=node.minimum_hop_from_seed,
        is_seed=node.is_seed,
        is_target=node.is_target,
        side=ctx.side_of.get(node.neuron_id),
        role=ctx.role_of.get(node.neuron_id),
        in_degree=degree.in_degree,
        out_degree=degree.out_degree,
        in_synapses=degree.in_synapses,
        out_synapses=degree.out_synapses,
    )


def _simulation_weight(synapse_count: int, ctx: BehaviourContext) -> SimulationWeight:
    cfg = ctx.simulation_config
    return SimulationWeight(
        value=normalize_weight(synapse_count, cfg.weight_transform, cfg.weight_scale),
        weight_transform=cfg.weight_transform,
        weight_scale=cfg.weight_scale,
    )


def _edge_record(edge, ctx: BehaviourContext, with_weight: bool) -> EdgeRecord:
    return EdgeRecord(
        pre_neuron_id=edge.pre_neuron_id,
        post_neuron_id=edge.post_neuron_id,
        synapse_count=edge.synapse_count,
        dataset=edge.dataset,
        dataset_version=edge.dataset_version,
        simulation_weight=_simulation_weight(edge.synapse_count, ctx) if with_weight else None,
    )


def _require_node(loaded: LoadedCircuit, neuron_id: str) -> CircuitNode:
    node = loaded.nodes.get(neuron_id)
    if node is None:
        raise HTTPException(
            404,
            detail={
                "error": "neuron_not_found",
                "message": f"neuron {neuron_id!r} is not in circuit {loaded.circuit.circuit_id}",
            },
        )
    return node


def _page(items: list[Any], offset: int, limit: int) -> list[Any]:
    return items[offset : offset + limit]


# ----------------------------------------------------------------------------- endpoints
@router.get("/circuits", response_model=list[CircuitListItem], summary="Loadable circuit artifacts")
def list_circuits(
    request: Request, catalog: CatalogDep, settings: SettingsDep
) -> list[CircuitListItem]:
    items: list[CircuitListItem] = []
    for circuit_id in catalog.list():
        try:
            loaded = catalog.get(circuit_id)
        except HTTPException:
            continue
        ctx = behaviour_context(request, settings, circuit_id)
        items.append(
            CircuitListItem(
                circuit_id=circuit_id,
                dataset=loaded.circuit.dataset,
                dataset_version=loaded.circuit.dataset_version,
                circuit_hash=loaded.circuit_hash,
                neurons=len(loaded.circuit.nodes),
                edges=len(loaded.circuit.edges),
                biological_status=ctx.biological_status,
            )
        )
    return items


@router.get(
    "/circuits/{circuit_id}", response_model=CircuitSummary, summary="Circuit artifact summary"
)
def get_circuit(
    circuit_id: str, request: Request, catalog: CatalogDep, settings: SettingsDep
) -> CircuitSummary:
    loaded = catalog.get(circuit_id)
    circuit = loaded.circuit
    ctx = behaviour_context(request, settings, circuit_id)
    counts: dict[str, int] = {}
    for node in circuit.nodes:
        key = node.cell_type or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return CircuitSummary(
        circuit_id=circuit.circuit_id,
        dataset=circuit.dataset,
        dataset_version=circuit.dataset_version,
        circuit_hash=loaded.circuit_hash,
        canonical_graph=circuit.canonical_graph,
        extractor_config=circuit.extractor_config,
        seed_neurons=len(circuit.seed_neurons),
        target_neurons=circuit.target_neurons,
        neurons=len(circuit.nodes),
        edges=len(circuit.edges),
        synapses_total=sum(e.synapse_count for e in circuit.edges),
        cell_type_counts=dict(sorted(counts.items())),
        extracted_at=circuit.provenance.extracted_at,
        extractor_version=circuit.provenance.extractor_version,
        biological_interpretation=circuit.provenance.biological_interpretation,
        biological_status=ctx.biological_status,
        research_document=ctx.research_document,
        config_version=ctx.config_version,
    )


@router.get(
    "/circuits/{circuit_id}/provenance",
    response_model=ProvenanceResponse,
    summary="Where the displayed structure comes from",
)
def get_provenance(
    circuit_id: str, request: Request, catalog: CatalogDep, settings: SettingsDep
) -> ProvenanceResponse:
    loaded = catalog.get(circuit_id)
    circuit = loaded.circuit
    ctx = behaviour_context(request, settings, circuit_id)
    source = circuit.provenance.source_provenance or {}
    source_dataset = source.get("source_dataset") or None
    canonical_source = source.get("canonical_graph") or {}
    expected = ctx.service.config.expected_circuit_hash if ctx.service else None
    return ProvenanceResponse(
        circuit_id=circuit.circuit_id,
        circuit_hash=loaded.circuit_hash,
        expected_circuit_hash=expected,
        circuit_verified=expected in (None, loaded.circuit_hash),
        biological_status=ctx.biological_status,
        research_document=ctx.research_document,
        dataset=circuit.dataset,
        dataset_version=circuit.dataset_version,
        license=source.get("license"),
        source_page=source.get("source_page"),
        download_url=source.get("download_url"),
        source_dataset=SourceDatasetInfo(
            name=source_dataset.get("name", circuit.dataset),
            version=source_dataset.get("version", circuit.dataset_version),
            official_neuron_count=source_dataset.get("official_neuron_count"),
            official_neuron_count_source=source_dataset.get("official_neuron_count_source"),
            description=source_dataset.get("description"),
        )
        if source_dataset
        else None,
        canonical_graph=CanonicalGraphInfo(
            selection_rule=circuit.canonical_graph.selection_rule,
            neuron_count=circuit.canonical_graph.neuron_count,
            connection_count=circuit.canonical_graph.connection_count,
            description=canonical_source.get("description"),
        ),
        loaded_circuit={"neurons": len(circuit.nodes), "edges": len(circuit.edges)},
        raw_files=[
            RawFileInfo(role=f.get("role", "?"), path=f.get("path", "?"), sha256=f.get("sha256"))
            for f in source.get("raw_files", [])
        ],
        graph_fingerprint=circuit.provenance.graph_fingerprint,
        extracted_at=circuit.provenance.extracted_at,
        extractor_version=circuit.provenance.extractor_version,
        citations=list(ctx.service.config.citations) if ctx.service else [],
        mapping_confidence=dict(ctx.service.config.mapping_confidence) if ctx.service else {},
        limitations=list(ctx.service.config.limitations) if ctx.service else [],
    )


@router.get(
    "/circuits/{circuit_id}/nodes", response_model=NodesPage, summary="Neurons of the circuit"
)
def list_nodes(
    circuit_id: str,
    request: Request,
    catalog: CatalogDep,
    settings: SettingsDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_NODES_PAGE)] = MAX_NODES_PAGE,
    cell_type: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(description="exact neuron id")] = None,
    id_prefix: Annotated[str | None, Query(description="neuron id prefix")] = None,
) -> NodesPage:
    loaded = catalog.get(circuit_id)
    ctx = behaviour_context(request, settings, circuit_id)
    nodes = loaded.circuit.nodes
    if cell_type is not None:
        nodes = [n for n in nodes if (n.cell_type or "") == cell_type]
    if search:
        term = search.strip()
        nodes = [n for n in nodes if n.neuron_id == term]
    if id_prefix:
        prefix = id_prefix.strip()
        nodes = [n for n in nodes if n.neuron_id.startswith(prefix)]
    return NodesPage(
        circuit_id=loaded.circuit.circuit_id,
        circuit_hash=loaded.circuit_hash,
        total=len(nodes),
        offset=offset,
        limit=limit,
        items=[_node_record(loaded, n, ctx) for n in _page(nodes, offset, limit)],
    )


@router.get(
    "/circuits/{circuit_id}/edges",
    response_model=EdgesPage,
    summary="Structural edges of the circuit (biological data)",
)
def list_edges(
    circuit_id: str,
    request: Request,
    catalog: CatalogDep,
    settings: SettingsDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_EDGES_PAGE)] = MAX_EDGES_PAGE,
    pre: Annotated[str | None, Query()] = None,
    post: Annotated[str | None, Query()] = None,
    min_synapses: Annotated[int, Query(ge=0)] = 0,
    include_simulation_weight: bool = False,
) -> EdgesPage:
    loaded = catalog.get(circuit_id)
    ctx = behaviour_context(request, settings, circuit_id)
    edges = loaded.circuit.edges
    if pre is not None:
        edges = [e for e in edges if e.pre_neuron_id == pre]
    if post is not None:
        edges = [e for e in edges if e.post_neuron_id == post]
    if min_synapses:
        edges = [e for e in edges if e.synapse_count >= min_synapses]
    return EdgesPage(
        circuit_id=loaded.circuit.circuit_id,
        circuit_hash=loaded.circuit_hash,
        total=len(edges),
        offset=offset,
        limit=limit,
        items=[
            _edge_record(e, ctx, include_simulation_weight) for e in _page(edges, offset, limit)
        ],
    )


@router.get(
    "/circuits/{circuit_id}/edges/{pre_neuron_id}/{post_neuron_id}",
    response_model=EdgeDetail,
    summary="One structural edge with its provenance",
)
def get_edge(
    circuit_id: str,
    pre_neuron_id: str,
    post_neuron_id: str,
    request: Request,
    catalog: CatalogDep,
    settings: SettingsDep,
) -> EdgeDetail:
    loaded = catalog.get(circuit_id)
    index = loaded.edge_index.get((pre_neuron_id, post_neuron_id))
    if index is None:
        raise HTTPException(
            404,
            detail={
                "error": "edge_not_found",
                "message": f"no edge {pre_neuron_id} → {post_neuron_id} in {circuit_id}",
            },
        )
    edge = loaded.circuit.edges[index]
    ctx = behaviour_context(request, settings, circuit_id)
    return EdgeDetail(
        pre=_biological(loaded.nodes[edge.pre_neuron_id], loaded.circuit),
        post=_biological(loaded.nodes[edge.post_neuron_id], loaded.circuit),
        synapse_count=edge.synapse_count,
        dataset=edge.dataset,
        dataset_version=edge.dataset_version,
        circuit_id=loaded.circuit.circuit_id,
        circuit_hash=loaded.circuit_hash,
        simulation_weight=_simulation_weight(edge.synapse_count, ctx),
    )


@router.get(
    "/circuits/{circuit_id}/neurons/{neuron_id}",
    response_model=NeuronDetail,
    summary="One neuron: biological metadata vs circuit/simulation metadata",
)
def get_neuron(
    circuit_id: str,
    neuron_id: str,
    request: Request,
    catalog: CatalogDep,
    settings: SettingsDep,
) -> NeuronDetail:
    loaded = catalog.get(circuit_id)
    node = _require_node(loaded, neuron_id)
    ctx = behaviour_context(request, settings, circuit_id)
    return NeuronDetail(
        circuit_id=loaded.circuit.circuit_id,
        circuit_hash=loaded.circuit_hash,
        biological=_biological(node, loaded.circuit),
        circuit=CircuitMetadata(
            minimum_hop_from_seed=node.minimum_hop_from_seed,
            is_seed=node.is_seed,
            is_target=node.is_target,
            side=ctx.side_of.get(neuron_id),
            role=ctx.role_of.get(neuron_id),
            stimulated_by_config=(neuron_id in ctx.stimulated) if ctx.service else None,
        ),
        connectivity=loaded.degree(neuron_id),
    )


@router.get(
    "/circuits/{circuit_id}/neurons/{neuron_id}/neighbors",
    response_model=NeighborsResponse,
    summary="Upstream / downstream partners within the loaded circuit",
)
def get_neighbors(
    circuit_id: str,
    neuron_id: str,
    request: Request,
    catalog: CatalogDep,
    settings: SettingsDep,
    direction: Direction = "both",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_EDGES_PAGE)] = MAX_EDGES_PAGE,
) -> NeighborsResponse:
    loaded = catalog.get(circuit_id)
    _require_node(loaded, neuron_id)
    edges = loaded.circuit.edges

    def records(indexes: list[int], partner: str) -> NeighborList:
        rows = []
        for i in sorted(indexes, key=lambda k: -edges[k].synapse_count):
            edge = edges[i]
            pid = edge.pre_neuron_id if partner == "pre" else edge.post_neuron_id
            node = loaded.nodes.get(pid)
            rows.append(
                NeighborRecord(
                    neuron_id=pid,
                    cell_type=node.cell_type if node else None,
                    synapse_count=edge.synapse_count,
                    pre_neuron_id=edge.pre_neuron_id,
                    post_neuron_id=edge.post_neuron_id,
                    dataset=edge.dataset,
                    dataset_version=edge.dataset_version,
                )
            )
        return NeighborList(
            total=len(rows), offset=offset, limit=limit, items=_page(rows, offset, limit)
        )

    upstream = (
        records(loaded.in_edges.get(neuron_id, []), "pre")
        if direction in ("upstream", "both")
        else None
    )
    downstream = (
        records(loaded.out_edges.get(neuron_id, []), "post")
        if direction in ("downstream", "both")
        else None
    )
    return NeighborsResponse(
        circuit_id=loaded.circuit.circuit_id,
        circuit_hash=loaded.circuit_hash,
        neuron_id=neuron_id,
        direction=direction,
        upstream=upstream,
        downstream=downstream,
    )


__all__ = [
    "NEIGHBORS_LABEL",
    "SIMULATION_WEIGHT_LABEL",
    "STRUCTURAL_LABEL",
    "CircuitCatalog",
    "router",
]
