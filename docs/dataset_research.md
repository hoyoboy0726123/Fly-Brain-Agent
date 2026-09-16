# Dataset research — MaleCNS v1.0 (P1 gate)

Recorded 2026-09-16 before writing the production adapter, as required by `DATA.md` §2 and
`TASKS.md` P1 "First Action". Every fact below is tagged with how it was verified:

- **[bucket]** read directly from the official release bucket `gs://flyem-male-cns` over
  `https://storage.googleapis.com` (object listing, `README_RELEASE_BUCKET.md`, file footers/contents).
- **[site-src]** read from the official website source repository
  `github.com/janelia-flyem/male-cns` (`docs/download.md`, `docs/release.md`, `docs/index.md`,
  `mkdocs.yml`, copyright "Howard Hughes Medical Institute"), which builds `male-cns.janelia.org`.
  Copies are kept under `data/raw/male-cns/website-source/` (git-ignored except by request).
- **[empirical]** computed from the downloaded v1.0 files in this repository.
- **[search-only]** seen only in search-engine result snippets; **not** independently verified
  because the page itself is unreachable from this environment (see §9).

No dataset other than the male CNS connectome was considered. FlyWire/FAFB, hemibrain and MANC
appear below only where the official annotation table cross-references them.

## 1. Identity

| Item | Value | Verified |
|---|---|---|
| Official name | "Male CNS" / "MaleCNS" connectome (Janelia FlyEM, Cambridge Dept. of Zoology, MRC LMB, Google Research) | [site-src] |
| neuPrint dataset id | `male-cns:v1.0` | [site-src] `download.md` ("The complete neo4j database backing the `male-cns:v1.0` neuprint dataset"), [bucket] `Neuprint_Meta.csv`: `dataset = male-cns`, `tag = v1.0` |
| Current version | v1.0, released June 8, 2026 ("Minor proofreading changes", "Refinement of neuron annotations") | [site-src] `release.md`, `index.md` (2026-06-08) |
| Previous version | v0.9, "Initial release" — October 5, 2025 per `release.md`; `index.md` news item dated 2025-10-03 | [site-src] |
| Other bucket prefixes | `v0.9/`, `v0.11/`, `v0.13/`, `versions-special/` (algorithm-development exports; not public releases) | [bucket] |
| Specimen | a single male *Drosophila melanogaster* CNS (brain + VNC) | [site-src] |
| Publication | "MaleCNS paper published" in *Cell*, 2026-09-03, `https://www.cell.com/cell/fulltext/S0092-8674(26)00942-6`; preprint v2 `https://www.biorxiv.org/content/10.1101/2025.10.09.680999v2` | [site-src] `index.md` |
| Paper title / DOI | "Sexual dimorphism in the complete Drosophila male central nervous system connectome", DOI `10.1016/j.cell.2026.08.015`, reported counts 166,691 neurons / 11,691 types (PRD/DATA.md) | [search-only] — cell.com, doi.org, Crossref, bioRxiv, PMC all blocked |
| Neuprint_Meta description | "The complete MaleCNS connectome from the Janelia FlyEM Team Project, the Cambridge Drosophila Connectomics Group, and Go[ogle] …" | [bucket] |

## 2. License / redistribution

Verbatim from the official website source (three pages agree): **"The Male CNS is
[licensed under CC-BY](https://creativecommons.org/licenses/by/4.0/)."** — `download.md`
line 247/288, `release.md` line 44, `index.md` line 126 [site-src]. The link target is
Creative Commons Attribution 4.0. Attribution is therefore required whenever this project
shows or redistributes MaleCNS-derived data; `provenance.json` carries the license string and
the citation links. Third-party search snippets of janelia.org say the same ("The FlyEM Male
CNS dataset is licensed under CC-BY") [search-only].

## 3. Access mechanisms

| Mechanism | Details | Verified |
|---|---|---|
| Bulk download (used here) | Public GCS bucket `gs://flyem-male-cns`; flat tables at `gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/`; each file also served at `https://storage.googleapis.com/flyem-male-cns/<object>`; anonymous HTTPS listing and download work | [site-src] `download.md`, [bucket] |
| neuPrint | `https://neuprint.janelia.org`, dataset `male-cns:v1.0`; requires an account and API token (`neuprint-python`, `neuprintr`) — not usable anonymously and blocked from this environment | [site-src] |
| neo4j dump + inputs | `gs://flyem-male-cns/v1.0/database/neo4j` (neo4j 4.4.16), `gs://flyem-male-cns/v1.0/database/neuprint-inputs` (CSV/feather inputs incl. `Neuprint_Meta.csv`, `Neuprint_Neurons.feather` 4.6 GB, `Neuprint_Neuron_Connections.feather` 3.5 GB) | [site-src], [bucket] |
| Neuroglancer | scene `gs://flyem-male-cns/v1.0/male-cns-v1.0.json` (title "MaleCNS v1.0") | [bucket] |
| Clio | `https://clio.janelia.org/ws/annotate?dataset=male-cns:v1.0-v1.0&tab=bodies` | [site-src] |

## 4. Actual files (v1.0 flat-connectome) [bucket listing, 2026-06-03/08]

| File | Size (bytes) | md5 (base64, as listed) | Rows | Columns |
|---|---:|---|---:|---|
| `body-annotations-male-cns-v1.0-minconf-0.5.feather` | 14,483,314 | `UKdxh3DFciDxYLpPQxq4ng==` | 211,577 | 36 (see §5.1) |
| `body-neurotransmitters-male-cns-v1.0.feather` | 43,282,834 | `PYQrEv5cSe763lKNfdJKHw==` | 1,835,518 | 10 (see §5.3) |
| `body-stats-male-cns-v1.0-minconf-0.5.feather` | 778,062,826 | `QEwzScKFgBSOFoFeuZ84Kg==` | 88,384,522 | …, `class`, `type`, `instance`, `downstream`, `synweight`, `rank` (footer only; not downloaded) |
| `connectome-weights-male-cns-v1.0-minconf-0.5.feather` | 1,051,241,946 | `8w6dzKJc/QIb8eez2XVZng==` | 151,856,684 | `body_pre`, `body_post`, `weight` (int64) |
| `connectome-weights-…-traced-only.feather` | 508,025,642 | `ZgHUrQr6mf0D6wh5Ze8kIw==` | 25,563,197 | + `type_pre`, `type_post` |
| `connectome-weights-…-significant-only.feather` | 502,169,298 | `CfL4M/cWGkatM81vnJBy9g==` | 25,568,639 | + `type_pre`, `type_post` (not documented on the download page; not used) |
| `syn-partners-male-cns-v1.0-minconf-0.5.feather` | 6,777,179,098 | `pbz0…` (see listing) | 311,833,243 | `x_pre,y_pre,z_pre,body_pre,conf_pre,x_post,y_post,z_post,body_post,conf_post,primary_post` |
| `syn-points-male-cns-v1.0-minconf-0.5.feather` | 13,061,489,098 | — | (index `point_id`) | 41 columns incl. `kind`, `conf`, `body`, ROI/column/layer labels |
| `tbar-neurotransmitters-male-cns-v1.0.feather` | 2,651,680,218 | — | 45,656,140 | per-presynapse NT probabilities |

Row counts come from the pandas `RangeIndex` stored in each file's Arrow footer [bucket] and,
for the four downloaded files, from reading them [empirical]. Format: Apache Arrow Feather
(IPC file), as stated by the download page.

Downloaded into `data/raw/male-cns/v1.0/connectome-data/flat-connectome/` (git-ignored) with
md5 verified against the bucket listing [empirical]: body-annotations, body-neurotransmitters,
connectome-weights (full), connectome-weights-traced-only.

## 5. Actual schema

### 5.1 `body-annotations-…` (211,577 rows) [bucket footer + empirical]

`assignedOlHex1` f64, `assignedOlHex2` f64, **`bodyId` i64** (unique, min 10001, max
1,571,825,087), `flywireType` str, `group` f64, `instance` str, `somaSide` str {L, R, M},
`statusLabel` dict<str>, `superclass` str (27 values, e.g. `ol_intrinsic`, `cb_intrinsic`,
`vnc_intrinsic`, `visual_projection`, `descending_neuron`, `vnc_motor`), **`type` str**
(11,751 distinct), `vfbId` str (166,686 non-null), `hemibrainType` str, `itoleeHl` str,
`supertype` str, `birthtime` str, `mancBodyid` f64, `mancGroup` f64, `mancType` str,
`subclass` str, `synonyms` str, **`class` str** (21 values, e.g. `visual`, `Kenyon_Cell`,
`CX`, `olfactory`), `rootSide` str, `somaNeuromere` str, `trumanHl` str, `dimorphism` str,
`matchingNotes` str, `entryNerve` str, `mancSerial` f64, `mcnsSerial` f64, `serialMotif` str,
`fruDsx` str, `exitNerve` str, `receptorType` str, `somaLocation` list<i64>,
`tosomaLocation` list<i64>, **`status` str**.

`status` distribution [empirical]: Traced 165,122 · Orphan 15,925 · Glia 11,864 ·
Unimportant 10,751 · Assign 1,832 · null 5,472 · other 611. Coverage: `type` non-null 164,506
(162,517 of them Traced); `superclass` non-null 166,700; `vfbId` non-null 166,686.

Download-page description: "Curated neuron annotations (classes, types, sides, etc.),
excluding neurotransmitter properties." [site-src]

### 5.2 `connectome-weights-…` [bucket footer + empirical]

Columns `body_pre` i64, `body_post` i64, `weight` i64. Download page (v0.9 wording in the
bucket README, same file family): "segment-to-segment connection strengths for all segments in
the dataset (excluding those with no synapses) — This is the full connection graph." [bucket]

Meaning of `weight`, cross-checked [empirical]: Σ`weight` over all 151,856,684 rows =
**311,833,243** = `Neuprint_Meta.totalPostCount` = number of rows of `syn-partners`. So
`weight` is the number of synaptic (pre→post partner) connections between the two bodies in
the `minconf-0.5` tables. `min = 1`, `max = 2,591`; 123 self-loop rows. Weight histogram:
w=1 94,185,919 · w=2 34,656,359 · w=3–4 15,391,542 · w=5–9 4,822,954 · w≥10 2,799,910.

`-traced-only` variant [empirical]: identical (row count 25,563,197 and Σweight 124,025,046)
to the full table filtered to edges whose **both** endpoints have `status == "Traced"`. That
is how "traced" is interpreted in this project. `-significant-only` is not described on the
download page and is **not used**.

`minconf-0.5`: file-name suffix; `Neuprint_Meta.postHighAccuracyThreshold = 0.5`
[bucket]. The `syn-partners` table carries `conf_pre`/`conf_post`. Interpretation
(consistent with neuPrint conventions, not separately documented on the page): the tables
count synapses with confidence ≥ 0.5.

### 5.3 `body-neurotransmitters-…` (1,835,518 rows) [empirical]

`body` i64, `cell_type` str, `total_nt_predictions` i32, `predicted_nt_confidence` f64,
`predicted_nt` str {acetylcholine, glutamate, gaba, dopamine, histamine, serotonin,
octopamine, unclear}, `ground_truth` str, `celltype_total_nt_predictions` i32,
`celltype_predicted_nt` str, `celltype_predicted_nt_confidence` f64, `consensus_nt` str.
Download page: "Aggregate neurotransmitter predictions for each neuron. See manuscript
methods section for details." [site-src] → these are **model predictions by the dataset
providers**, not measurements. 164,620 of the 165,122 Traced bodies have a row.

### 5.4 Identifiers and representation

- Neuron identifier: **body ID** (`bodyId` / `body_pre` / `body_post`), int64 segment id of the
  v1.0 proofread segmentation ("Voxels are stored as uint64, but the upper 32 bits are never
  used") [bucket README]. Normalized to strings per `DATA.md` §5.
- Connectivity: directed body→body edge list with integer weight (§5.2). Synapse-level detail
  exists in `syn-partners` / `syn-points` (not ingested in P1).
- Region: **not present** in the flat annotation table. Per-neuron ROI membership lives in the
  neuPrint database (`roiInfo`; `Neuprint_Meta.primaryRois` lists compartments such as
  `AL(L)`, `AOTU(R)`, …) and in `Neuprint_Neurons.feather` (4.6 GB), which P1 does not ingest.
  `region` is therefore **null** in `neurons.parquet` (nothing invented).

## 6. Normalization decisions (P1)

| SDD column | Source | Note |
|---|---|---|
| `neuron_id` | `bodyId` → string | |
| `dataset`, `dataset_version` | constants `male-cns`, `v1.0` | |
| `cell_type` | `type` | null where the publisher left it null |
| `cell_class` | `class` | `superclass`/`subclass` kept as `mcns_superclass`/`mcns_subclass` |
| `region` | null | see §5.4 |
| `neurotransmitter` | `body-neurotransmitters.predicted_nt` | prediction, not measurement; confidence etc. kept as `mcns_nt_*` |
| `sex` | constant `male` | dataset-level specimen fact |
| `source_url` | HTTPS URL of the annotation file | dataset-level; no per-neuron URL pattern was verified |
| `synapse_count` | `weight` | see §5.2 |
| `mcns_*` | every other annotation column, verbatim | preserves provenance; dictionary columns decoded to strings |

**Neuron set rule (configurable, recorded in `provenance.json`):** default `status == "Traced"`
(165,122 bodies) — the publishers' own rule for the `-traced-only` connectivity table, and
"Traced" = proofread body per the bucket's special-versions README. Alternatives available via
`--status …` / `--all-statuses`: all annotated bodies (211,577) or e.g. Traced+Assign (166,954).
The paper's headline "166,691 neurons" [search-only] and the 166,700 bodies with a
`superclass` [empirical] are close to, but not identical with, any single status rule; the
exact neuPrint `:Neuron` criterion could not be read (neuPrint blocked). This is recorded as
an open question (§10), not silently resolved.

**Edges:** by default only edges whose both endpoints are in the neuron set are kept
(25,563,197 with the default rule, matching the official traced-only table); all others are
counted per category and reported (`--keep-dangling` retains them).

### 6.1 Production run result (2026-09-16, `make normalize`) [empirical]

| Output | Value |
|---|---:|
| `neurons.parquet` rows / columns | 165,122 / 49 (9 SDD columns + 35 `mcns_*` annotation columns + 5 `mcns_nt_*`) |
| `connections.parquet` rows | 25,563,197 (= official `-traced-only` table) |
| raw edges scanned | 151,856,684 |
| dropped: pre unknown / post unknown / both unknown | 4,802,106 / 112,538,237 / 8,953,144 (total 126,293,487) |
| `synapse_count` min / max / median / Σ | 1 / 2,591 / 2.0 / 124,025,046 |
| self-loops kept | 101 |
| duplicate neuron IDs / duplicate edge pairs / dangling after filter | 0 / 0 / 0 |
| `cell_type` non-null / distinct | 162,517 / 11,751 |
| `cell_class` non-null / distinct | 24,524 / 21 |
| `neurotransmitter` non-null / distinct | 164,620 / 8 |
| raw checksums | all three md5 match the bucket listing |
| runtime | 67 s (hashing 1.1 GB + streaming 2,318 record batches) |

## 7. Raw data policy compliance

- `data/raw/` is git-ignored; raw files are read-only inputs; sha256 + md5 are recorded and md5
  is compared with the bucket listing; normalization refuses to run on a checksum mismatch.
- Transformations run only through `scripts/normalize_dataset.py` (repeatable, deterministic
  ordering by body id).
- Tests use `backend/tests/fixtures/tiny_connectome.json` (SYNTHETIC) and synthetic files with
  the verified MaleCNS schema written to pytest temp dirs; no download is needed.

## 8. Reproduction commands

```bash
# list the official bucket (anonymous)
curl "https://storage.googleapis.com/storage/v1/b/flyem-male-cns/o?prefix=v1.0/connectome-data/flat-connectome/"
# download the four files used in P1 (≈1.6 GB) into data/raw (paths mirror the bucket)
B=https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome
D=data/raw/male-cns/v1.0/connectome-data/flat-connectome; mkdir -p $D
for f in body-annotations-male-cns-v1.0-minconf-0.5.feather body-neurotransmitters-male-cns-v1.0.feather \
         connectome-weights-male-cns-v1.0-minconf-0.5.feather; do curl -o $D/$f $B/$f; done
make normalize   # -> data/processed/{neurons,connections}.parquet, provenance.json, inspection_report.*
make inspect
```

## 9. Environment limitations during this research

Blocked by the network egress policy of the coding environment (HTTP 403 at the proxy):
`research.google`, `sites.research.google`, `www.research.google`, `janelia.org`,
`male-cns.janelia.org`, `janelia-flyem.github.io`, `neuprint.janelia.org`, `cell.com`,
`biorxiv.org`, `ncbi.nlm.nih.gov`, `natverse.org`, `doi.org`, `api.crossref.org`.
Reachable: `storage.googleapis.com` (the official data bucket) and `raw.githubusercontent.com`
(the official website source). Consequently the three Google Research pages listed in
`DATA.md` §1 could not be read; the Janelia bucket and website source were used as the
authoritative sources instead. A human should spot-check `https://male-cns.janelia.org/download/`
once; the content used here is the page's own source file.

## 10. Open questions (non-blocking for P1, recorded for the human)

1. Neuron definition for the MVP: keep `status == "Traced"` (165,122) or align with the paper's
   "166,691 neurons" / neuPrint `:Neuron` set (criterion not readable offline)? Configurable.
2. Should `neurotransmitter` use `predicted_nt` (per-body aggregate, chosen) or `consensus_nt`
   (semantics only described in the paper's methods, which are blocked)? Both are kept.
3. `region`: ingest neuPrint ROI membership (`Neuprint_Neurons.feather`, 4.6 GB) in a later
   phase if the circuit extractor or inspector needs regions.
4. Verify DOI `10.1016/j.cell.2026.08.015` from the publisher page (blocked here).
