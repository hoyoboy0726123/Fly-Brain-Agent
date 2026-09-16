# DATA — Dataset & Provenance Rules

## 1. Authoritative Starting Points
Use official or project-authorized sources first.

Google Research:
- https://sites.research.google/gr/neural-mapping/datasets/
- https://www.research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/
- https://research.google/pubs/sexual-dimorphism-in-the-complete-connectome-of-the-drosophila-male-central-nervous-system/

The 2026 paper reports 166,691 neurons and 11,691 annotated types across the male brain and nerve cord.

## 2. Critical Rule
The coding agent MUST inspect the current official dataset/download documentation before implementing the production adapter.

Do not assume a filename, API endpoint, table schema, dataset version, license, or download URL from this document.

Dataset access can evolve.

## 3. Provenance Manifest
Create:
`data/processed/provenance.json`

Example:

```json
{
  "dataset_name": "",
  "dataset_version": "",
  "source_page": "",
  "download_url": "",
  "retrieved_at": "",
  "license": "",
  "raw_files": [],
  "transform_script": "",
  "notes": ""
}
```

Do not leave license blank in a distributable release.

## 4. Raw Data Policy
- data/raw is gitignored.
- Never silently modify raw files.
- Transform raw → normalized through scripts.
- Record hashes when practical.
- Processing must be repeatable.

## 5. Normalization
Normalize identifiers to strings to avoid integer-width/serialization surprises.

Never fabricate:
- cell type
- neurotransmitter
- region
- synapse count
- biological direction

Unknown is represented as null/unknown.

## 6. Demo Fixtures
Tests must NOT require downloading the full connectome.

Create a small synthetic fixture:
`backend/tests/fixtures/tiny_connectome.*`

Synthetic fixture edges must be clearly labeled synthetic and must never appear in the production demo as biological evidence.

## 7. Data Validation Report
`scripts/inspect_dataset.py` should produce:
- number of neurons
- number of directed connections
- min/max/median synapse_count
- missing IDs
- duplicate IDs
- dangling edges
- available annotation columns
- dataset/version/source

## 8. Source Dataset vs Canonical Simulation Graph
Two different things must never be conflated:

| | SOURCE DATASET | CANONICAL SIMULATION GRAPH |
|---|---|---|
| What | MaleCNS v1.0 as published (Janelia FlyEM et al.) | The subset this project simulates on |
| Neurons | approximately **166,700** (release figure; the Cell paper reports 166,691) | **165,122** |
| Selection | none (the dataset) | `status == "Traced"` in `body-annotations-male-cns-v1.0` |
| Connections | 151,856,684 raw body→body rows in `connectome-weights` | **25,563,197** directed edges with both endpoints in the neuron set |

Rules:
- The canonical graph count (165,122) is **not** the MaleCNS neuron census and must not be
  presented as such in code, docs, UI or reports.
- `data/processed/provenance.json` must carry both a `source_dataset` block (name, version,
  official neuron count and its basis, annotated bodies, raw connection rows, status counts)
  and a `canonical_graph` block (selection rule, neuron count, connection count, dropped
  dangling edges). Provenance for biological data is invalid without both.
- `scripts/inspect_dataset.py` reports both blocks and whether the canonical counts match
  the normalized tables.
- The selection rule is configuration (`scripts/normalize_dataset.py --status …`), recorded in
  provenance and in the parquet schema metadata; changing it changes the canonical graph, not
  the source dataset.
- `neurons.parquet` / `connections.parquet` ARE the canonical graph. Circuits extracted in
  later phases are subsets of the canonical graph and inherit this provenance.
