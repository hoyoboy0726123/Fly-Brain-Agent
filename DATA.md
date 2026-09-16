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
