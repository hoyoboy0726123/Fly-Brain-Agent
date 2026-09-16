# ruff: noqa: E501  (long literal citation strings)
#!/usr/bin/env python3
"""Build the versioned escape_v1 configuration and its P2 circuit artifact from the canonical
MaleCNS graph (Phase B). Every neuron id is read from ``neurons.parquet``; nothing is typed
by hand. Rationale and evidence: docs/circuits/escape_v1.md.

Outputs:
  backend/app/behavior/configs/escape_v1.json   (config incl. expected_circuit_hash)
  data/circuits/escape_v1.json / .parquet       (P2 artifact, edges from canonical graph only)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.behavior import CONFIG_DIR, Citation, EscapeCircuitConfig  # noqa: E402
from app.behavior.escape_config import (  # noqa: E402
    DecoderParams,
    ExtractorParams,
    StimulusMappingParams,
)
from app.circuits import CircuitExtractor, ConnectivityGraph  # noqa: E402
from app.config import get_settings  # noqa: E402

SENSORY_TYPES = ("LC4", "LPLC2")
OUTPUT_TYPES = ("DNp01",)
RESEARCH_DOC = "docs/circuits/escape_v1.md"

CITATIONS = [
    Citation(
        key="klapoetke2017",
        authors="Klapoetke NC, Nern A, Peek MY, Rogers EM, Breads P, Rubin GM, Reiser MB, Card GM",
        year=2017,
        title="Ultra-selective looming detection from radial motion opponency",
        venue="Nature 551(7679):237-241",
        doi="10.1038/nature24626",
        url="https://www.nature.com/articles/nature24626",
        claim="LPLC2 is an ultra-selective looming detector providing input to the giant fiber escape pathway",
        verification="search-result metadata (title, venue, authors, DOI); full text blocked in the coding environment",
        confidence="high",
    ),
    Citation(
        key="vonreyn2017",
        authors="von Reyn CR, Nern A, Williamson WR, Breads P, Wu M, Namiki S, Card GM",
        year=2017,
        title="Feature Integration Drives Probabilistic Behavior in the Drosophila Escape Response",
        venue="Neuron 94(6):1190-1204",
        doi=None,
        url="https://www.cell.com/neuron/fulltext/S0896-6273(17)30474-9",
        claim="LC4 conveys looming angular velocity to the GF; other inputs encode angular size; the GF integrates both (with inhibitory components)",
        verification="search-result metadata; full text blocked",
        confidence="high",
    ),
    Citation(
        key="ache2019",
        authors="Ache JM et al. (Card GM lab)",
        year=2019,
        title="Neural Basis for Looming Size and Velocity Encoding in the Drosophila Giant Fiber Escape Pathway",
        venue="Current Biology 29(6)",
        doi=None,
        url="https://www.sciencedirect.com/science/article/pii/S0960982219301381",
        claim="LC4 and LPLC2 are GF inputs encoding looming velocity and size; the GF drives takeoff (leg extension and wing depression)",
        verification="search-result metadata; full text blocked",
        confidence="high",
    ),
    Citation(
        key="wu2016",
        authors="Wu M, Nern A, Williamson WR, Morimoto MM, Reiser MB, Card GM, Rubin GM",
        year=2016,
        title="Visual projection neurons in the Drosophila lobula link feature detection to distinct behavioral programs",
        venue="eLife 5:e21022",
        doi="10.7554/eLife.21022",
        url="https://elifesciences.org/articles/21022",
        claim="Optogenetic activation of LC4, LC6, LPLC1 and LPLC2 evokes takeoff/jumping; LC neurons project to ipsilateral optic glomeruli",
        verification="search-result metadata and indexed summary; full text blocked",
        confidence="high",
    ),
    Citation(
        key="namiki2018",
        authors="Namiki S, Dickinson MH, Wong AM, Korff W, Card GM",
        year=2018,
        title="The functional organization of descending sensory-motor pathways in Drosophila",
        venue="eLife 7:e34272",
        doi="10.7554/eLife.34272",
        url="https://elifesciences.org/articles/34272",
        claim="DN nomenclature (DNp01 = giant fiber); DNs receive visual projection neuron input and project to the VNC",
        verification="search-result metadata; full text blocked",
        confidence="high",
    ),
    Citation(
        key="jang2023",
        authors="Jang H, Goodman DP, Ausborn J, von Reyn CR",
        year=2023,
        title="Azimuthal invariance to looming stimuli in the Drosophila giant fiber escape circuit",
        venue="Journal of Experimental Biology 226(8):jeb244790",
        doi="10.1242/jeb.244790",
        url="https://journals.biologists.com/jeb/article/226/8/jeb244790/307120",
        claim="The GF responds invariantly across stimulus azimuth and integrates both eyes; therefore no left/right action is decoded from GF activity",
        verification="search-result metadata and indexed summary; full text blocked",
        confidence="high",
    ),
    Citation(
        key="dombrovski2023",
        authors="Dombrovski M et al. (Card GM lab)",
        year=2023,
        title="Synaptic gradients transform object location to action",
        venue="Nature 613",
        doi="10.1038/s41586-022-05562-8",
        url="https://www.nature.com/articles/s41586-022-05562-8",
        claim="LC4 -> DNp02/DNp11 synaptic gradients map looming location to forward/backward takeoff (reference for a future escape_v2; not used here)",
        verification="search-result metadata; full text blocked",
        confidence="medium",
    ),
]

LIMITATIONS = [
    "Literature verified through search-result metadata only (journal sites blocked in the coding environment); a human should spot-check the cited passages.",
    "Monosynaptic LC4/LPLC2 -> GF pathway only; contralateral routes to the GF (Jang et al. 2023) and inhibitory size-encoding inputs (von Reyn et al. 2017) are not represented.",
    "P3 dynamics are unsigned (excitatory-only) with computational parameters; simulated activity is not measured activity.",
    "Left/right is used only to select the ipsilateral sensory group; no directional action is decoded (GF is azimuth-invariant).",
    "LC6, LC16 and LPLC1 are documented escape-related types but have no direct edge to the GF in MaleCNS v1.0 and are excluded (NO PATH recorded).",
]


def build(processed_dir: Path, circuits_dir: Path, config_path: Path) -> EscapeCircuitConfig:
    graph = ConnectivityGraph.load(processed_dir)
    neurons = graph.neurons
    types = neurons["cell_type"].to_pylist()
    sides = neurons["mcns_somaSide"].to_pylist()
    ids = neurons["neuron_id"].to_pylist()

    def group_by_side(cell_types: tuple[str, ...]) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {"L": [], "R": []}
        for nid, ty, side in zip(ids, types, sides, strict=True):
            if ty in cell_types:
                if side not in groups:
                    raise ValueError(f"neuron {nid} ({ty}) has somaSide {side!r}; expected L or R")
                groups[side].append(nid)
        return {side: sorted(v, key=int) for side, v in groups.items()}

    population = group_by_side(SENSORY_TYPES)
    output = group_by_side(OUTPUT_TYPES)
    sensory = population  # refined below to the population members kept in the circuit
    print(
        f"[escape_v1] sensory {SENSORY_TYPES}: L={len(sensory['L'])} R={len(sensory['R'])}; output {OUTPUT_TYPES}: L={output['L']} R={output['R']}"
    )

    config = EscapeCircuitConfig(
        config_version="escape_v1",
        circuit_id="escape_v1",
        synthetic=False,
        dataset=graph.dataset,
        dataset_version=graph.dataset_version,
        canonical_selection_rule=graph.selection_rule,
        biological_status="PARTIALLY SUPPORTED",
        research_document=RESEARCH_DOC,
        sensory_cell_types=list(SENSORY_TYPES),
        output_cell_types=list(OUTPUT_TYPES),
        sensory_population=population,
        sensory_groups=sensory,
        output_groups=output,
        extractor=ExtractorParams(
            max_hops=1,
            min_synapses=10,
            max_neurons=2000,
            direction="downstream",
            restrict_to_target_paths=True,
        ),
        stimulus_mapping=StimulusMappingParams(
            mapping_gain=1.0,
            duration_steps=5,
            rule="current = intensity x mapping_gain injected each step into the ipsilateral sensory group (left->L, right->R, center->both); computational rule, not a measured firing rate",
        ),
        decoder=DecoderParams(
            min_output_spikes=1,
            actions=["NO_ACTION", "ESCAPE"],
            rule="ESCAPE if >= 1 simulated DNp01 spike during the run, else NO_ACTION; GF side reported as metadata only (no left/right action; Jang et al. 2023)",
        ),
        simulation_config_overrides={},
        simulation_steps=30,
        citations=CITATIONS,
        mapping_confidence={
            "sensory_types": "high (Klapoetke 2017, von Reyn 2017, Ache 2019, Wu 2016; exact MaleCNS cell_type match)",
            "output_type": "high (Namiki 2018, Ache 2019, Jang 2023; MaleCNS instance 'DNp01(GF)', hemibrainType 'Giant Fiber')",
            "structural_path": "high (all 126 LC4 and 185 LPLC2 synapse onto the ipsilateral GF in MaleCNS v1.0)",
            "laterality_rule": "medium (ipsilateral LC->GF edges only; contralateral pathway unidentified in literature)",
            "directional_action": "unsupported (GF azimuth-invariant) -> not decoded",
        },
        limitations=LIMITATIONS,
        notes="Built by scripts/build_escape_config.py from the canonical graph; do not edit ids by hand.",
    )

    circuit = CircuitExtractor(graph).extract(
        config.extractor_config(),
        circuit_id=config.circuit_id,
        notes=f"escape_v1: see {RESEARCH_DOC}",
    )
    json_path, parquet_path = circuit.save(circuits_dir)
    in_circuit = {n.neuron_id for n in circuit.nodes}
    kept = {side: [nid for nid in ids if nid in in_circuit] for side, ids in population.items()}
    excluded = {
        side: [nid for nid in ids if nid not in in_circuit] for side, ids in population.items()
    }
    min_syn = config.extractor.min_synapses
    print(
        f"[escape_v1] sensory kept in circuit: L={len(kept['L'])} R={len(kept['R'])}; "
        f"excluded (edge to GF < {min_syn} synapses): L={len(excluded['L'])} R={len(excluded['R'])}"
    )
    config = EscapeCircuitConfig(
        **{
            **config.model_dump(),
            "sensory_groups": kept,
            "excluded_sensory_ids": excluded,
            "exclusion_reason": (
                f"population member whose direct edge onto a DNp01 has fewer than min_synapses={min_syn} "
                "synapses; not part of the path-restricted circuit, so it receives no stimulus current"
                if any(excluded.values())
                else ""
            ),
            "expected_circuit_hash": circuit.provenance.circuit_hash,
        }
    )
    config.save(config_path)
    kinds: dict[str, int] = {}
    type_of = {n.neuron_id: n.cell_type for n in circuit.nodes}
    for e in circuit.edges:
        k = f"{type_of[e.pre_neuron_id]}->{type_of[e.post_neuron_id]}"
        kinds[k] = kinds.get(k, 0) + 1
    print(
        f"[escape_v1] circuit: {circuit.stats.returned_neurons} neurons / {circuit.stats.returned_edges} edges; edge kinds {kinds}"
    )
    print(
        f"[escape_v1] targets: {[(t.neuron_id, t.reachable, t.minimum_path_length) for t in circuit.target_neurons]}"
    )
    print(f"[escape_v1] circuit_hash={circuit.provenance.circuit_hash}")
    print(f"[escape_v1] wrote {json_path}, {parquet_path}, {config_path}")
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--processed-dir")
    parser.add_argument("--circuits-dir")
    parser.add_argument("--config-path", default=str(CONFIG_DIR / "escape_v1.json"))
    args = parser.parse_args(argv)
    settings = get_settings()
    processed_dir = Path(args.processed_dir) if args.processed_dir else settings.processed_data_dir
    circuits_dir = Path(args.circuits_dir) if args.circuits_dir else settings.circuits_data_dir
    if not (processed_dir / "neurons.parquet").is_file():
        print(f"[escape_v1] FAIL: canonical graph not found in {processed_dir}", file=sys.stderr)
        return 1
    build(processed_dir, circuits_dir, Path(args.config_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
