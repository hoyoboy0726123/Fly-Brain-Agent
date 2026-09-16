# escape_v1 — Research gate and circuit definition (P4)

Recorded 2026-09-16. Scope: the first biologically interpreted pipeline
(looming-like stimulus → supported visual input neurons → MaleCNS circuit → simulated
activity → supported descending neurons → motor decoder → action).

Verification tags used below:
- **[data]** verified directly in the canonical simulation graph of this repository
  (MaleCNS v1.0, `status == "Traced"`, 165,122 neurons / 25,563,197 edges; columns
  `cell_type` = MaleCNS `type`, `mcns_somaSide`, `mcns_instance`, `mcns_hemibrainType`,
  `mcns_flywireType`, `mcns_superclass`).
- **[lit-meta]** literature claim verified through search-result metadata (title, venue,
  year, authors, DOI/URL and the indexed abstract/summary). Every journal site (eLife,
  Nature, Cell/ScienceDirect, JEB, PubMed/PMC, FlyBase, bioRxiv, NSF PAR, ModelDB) is
  blocked by this environment's egress proxy, so full texts could not be read here.
  A human should spot-check the cited passages.
- **[not verified]** background knowledge that could not be checked online; not used for
  any implementation decision.

---

## 1. Research questions

### Q1. Which visual neuron types are documented as responding to looming / approaching objects?

| Claim | Source | Dataset / type | MaleCNS identifier(s) | Mapping method | Confidence | Limitations |
|---|---|---|---|---|---|---|
| LPLC2 is an ultra-selective looming detector (radial motion opponency) and provides input to the giant fiber escape pathway | Klapoetke et al. 2017, *Nature* 551:237–241, doi:10.1038/nature24626 [lit-meta] | Drosophila; LPLC2 | `cell_type == "LPLC2"`: 185 neurons (L 94 / R 91), `mcns_superclass = visual_projection` [data] | exact `cell_type` match | high | full text not readable here |
| LC4 conveys looming angular expansion **velocity** to the GF; other input(s) encode angular **size**; the GF integrates both linearly, including inhibitory components | von Reyn et al. 2017, *Neuron* 94(6):1190–1204 (cell.com S0896-6273(17)30474-9) [lit-meta] | Drosophila; LC4, GF | `cell_type == "LC4"`: 126 neurons (L 71 / R 55), `visual_projection` [data] | exact `cell_type` match | high | inhibitory components are **not** modelled (P3 is unsigned) |
| LC4 and LPLC2 are the GF inputs encoding looming velocity and size; GF drives takeoff (leg extension + wing depression) | Ache et al. 2019, *Current Biology* 29(6) (sciencedirect S0960982219301381) [lit-meta] | Drosophila; LC4, LPLC2, GF | as above | exact `cell_type` match | high | full text not readable here |
| Optogenetic activation of LC4, LC6, LPLC1 and LPLC2 evokes jumping/takeoff with high penetrance; LC6 and LC16 respond to looming; LC16 evokes backward walking; LC neurons project to optic glomeruli | Wu et al. 2016, *eLife* 5:e21022, doi:10.7554/eLife.21022 [lit-meta] | Drosophila; LC types | LC6: 124 (L 59 / R 65); LPLC1: 134; LC16: 182 [data] | exact `cell_type` match | high | see Q4: LC6/LC16/LPLC1 have **no direct edge** to GF |
| LC6 looming location is read out by central-brain neurons downstream of the LC6 glomerulus | Morimoto et al. 2020, *eLife* 9:e57685 [lit-meta] | Drosophila; LC6 | `LC6` present [data] | — | medium | pathway to descending neurons not part of escape_v1 |

### Q2. Which descending neuron types are associated with escape / takeoff?

| Claim | Source | MaleCNS identifier(s) | Mapping method | Confidence | Limitations |
|---|---|---|---|---|---|
| DNp01 is the giant fiber (GF); DNs receive input from visual projection neurons and project to the VNC (nomenclature DNp01, DNp02, …) | Namiki et al. 2018, *eLife* 7:e34272 [lit-meta] | `cell_type == "DNp01"`: **`10010`** (L, instance `DNp01(GF)_L`) and **`10001`** (R, instance `DNp01(GF)_R`), `mcns_hemibrainType = "Giant Fiber"`, `mcns_flywireType = "DNp01"`, `mcns_superclass = descending_neuron` [data] | exact `cell_type` + explicit `(GF)` / "Giant Fiber" labels | high | — |
| The GF drives synchronized wing depression and leg extension regardless of stimulus azimuth; looming-responsive DNs integrate both eyes although dendrites are unilateral; the contralateral pathway is unidentified | Jang, Goodman, Ausborn & von Reyn 2023, *J Exp Biol* 226(8):jeb244790, doi:10.1242/jeb.244790 [lit-meta] | DNp01 | — | high | **left/right cannot be decoded from GF activity**; contralateral route not in escape_v1 |
| LC4 → DNp02 / DNp11 synaptic-number gradients map looming location to takeoff direction (forward vs backward); DNp04 also analysed | Dombrovski et al. 2023, *Nature* 613, doi:10.1038/s41586-022-05562-8 [lit-meta] | DNp02: `10197` L / `10117` R; DNp04: `531898` L / `11137` R; DNp11: `10259` L / `10106` R [data] | exact `cell_type` match | medium | **not used in escape_v1** (forward/backward decoding deferred; see §6) |
| DNp01 controls a fast escape; DNp02+DNp04 a slower backward escape; DNp11 a forward escape | search-summary statement attributed to the DN literature above [lit-meta, secondary] | as above | — | low–medium | secondary wording; not used for decisions |

### Q3. Can these types be identified in MaleCNS v1.0 with the columns we possess? — YES [data]

| Type | Neurons | L / R | superclass | Notes |
|---|---:|---|---|---|
| LC4 | 126 | 71 / 55 | visual_projection | |
| LPLC2 | 185 | 94 / 91 | visual_projection | |
| LC6 | 124 | 59 / 65 | visual_projection | candidate, excluded (Q4) |
| LPLC1 | 134 | 68 / 66 | visual_projection | candidate, excluded (Q4) |
| LC16 | 182 | 88 / 94 | visual_projection | candidate, excluded (Q4) |
| DNp01 (GF) | 2 | `10010` / `10001` | descending_neuron | instance `DNp01(GF)_L/R`, hemibrainType "Giant Fiber" |
| DNp02 / DNp04 / DNp11 | 2 each | see Q2 | descending_neuron | reference only |

Identification method: exact string match on `cell_type`; side from `mcns_somaSide`; the
GF label is corroborated by `mcns_instance` and `mcns_hemibrainType`. No identifier was
guessed; all ids above are read from `data/processed/neurons.parquet`.

### Q4. Structural paths in the canonical graph (P2 extractor and direct-edge scan) [data]

Direct edges visual-projection type → descending type (all synapses, ipsilateral / contralateral):

| pre → post | ipsi synapses | ipsi pairs | contra | per-GF totals |
|---|---:|---:|---:|---|
| **LC4 → DNp01** | **6,362** | **126 / 126 LC4** | 0 | R `10001`: 2,580; L `10010`: 3,782 |
| **LPLC2 → DNp01** | **4,862** | **185 / 185 LPLC2** | 0 | R: 2,220; L: 2,642 |
| LC4 → DNp04 | 11,597 | 126 | 0 | reference |
| LC4 → DNp02 | 4,209 | 125 | 0 | reference |
| LC4 → DNp11 | 3,666 | 122 | 0 | reference |
| LPLC2 → DNp04 | 3,398 | 185 | 0 | reference |
| LPLC1 → DNp03 / DNp06 / DNp11 | 3,602 / 2,773 / 1,041 | 134 / 134 / 107 | 0 | LPLC1 → DNp01: **1 synapse** (NO usable path) |
| LC6 → DNp01 | 0 | 0 | 0 | **NO DIRECT EDGE** (LC6 → DNp11 3 syn, → DNp06 10 syn) |
| LC16 → DNp01 | 0 | 0 | 0 | **NO DIRECT EDGE** (LC16 → DNp11 2 syn) |

Per-pair synapse counts: LC4→GF min 21, median 51, max 86 (all 126 pairs ≥ 20);
LPLC2→GF min 1, median 27, max 64 (176 pairs ≥ 5; 158 ≥ 10; 117 ≥ 20).

GF inputs overall: `10001` (R) receives 16,051 synapses from 695 neurons, `10010` (L)
20,684 from 760; the two largest presynaptic types of both GFs are **LC4** and **LPLC2**.
GF outputs include TTMn (jump motor neuron), GFC2–GFC4, DNp11 and weak feedback onto LC4
(< 5 synapses per pair) — consistent with the GF takeoff pathway.

P2 extraction, seeds = all LC4 + LPLC2 (311), targets = DNp01 L + R:

| max_hops | min_synapses | restrict_to_target_paths | result |
|---|---|---|---|
| 1 | 1 | – | ABORT (10,931 > 2,000/3,000 neurons) |
| 1 | 5 | no | 1,111 neurons / 33,221 edges; both GFs reachable at hop 1 |
| 1 | 10 | no | 723 / 11,982; both reachable |
| 1 | 5 | yes | **304 neurons / 5,025 edges** (126 LC4, 176 LPLC2, 2 GF) |
| **1** | **10** | **yes** | **286 neurons / 932 edges** (126 LC4, 158 LPLC2, 2 GF; LC4→GF 126, LPLC2→GF 158, LC4→LC4 204, LPLC2→LPLC2 435, LPLC2→LC4 9) |
| 2 | 5–20 | any | ABORT (4,193–32,597 neurons at hop 2) |

Laterality [data]: left-side seeds (L LC4 + LPLC2, 165) reach only GF **L** (`10010`);
right-side seeds (146) reach only GF **R** (`10001`). There are zero contralateral LC→GF
edges.

### Q5. Negative results (recorded, not substituted)

- LC6 → DNp01: NO DIRECT EDGE (LC6's documented escape contribution is not via a direct GF synapse in this data).
- LC16 → DNp01: NO DIRECT EDGE (backward-walking pathway; not escape_v1).
- LPLC1 → DNp01: 1 synapse in one pair; NO usable path (LPLC1 targets DNp03/DNp06/DNp11 instead).
- Two-hop circuits from LC4+LPLC2 exceed the 2,000-neuron safety limit at every tested threshold; escape_v1 is therefore the documented **monosynaptic** LC4/LPLC2 → GF pathway.
- Contralateral eye → GF pathway (Jang et al. 2023) is not represented (no direct edges; identity unknown in the literature).

---

## 2. Research gate decision

| Component | Status | Basis |
|---|---|---|
| Sensory mapping (LC4, LPLC2 = looming inputs of the GF) | SUPPORTED | Klapoetke 2017, von Reyn 2017, Ache 2019, Wu 2016 [lit-meta]; exact MaleCNS types [data] |
| Output mapping (DNp01 = GF = takeoff escape DN) | SUPPORTED | Namiki 2018, Ache 2019, Jang 2023 [lit-meta]; explicit `(GF)` labels [data] |
| MaleCNS identifiers | SUPPORTED | all ids read from the canonical table [data] |
| Structural connectivity / path | SUPPORTED | 311/311 LC4+LPLC2 neurons synapse onto the ipsilateral GF [data] |
| Citations | PARTIALLY | metadata-verified only; full texts blocked in this environment |
| Directional (left/right) decoding | UNSUPPORTED | GF is azimuth-invariant (Jang 2023) → decoder exposes only NO_ACTION / ESCAPE |
| Signed (inhibitory) dynamics | UNSUPPORTED in P3 | von Reyn 2017 describes inhibitory components; the model is unsigned |

**BIOLOGICAL CIRCUIT STATUS: PARTIALLY SUPPORTED** — the structural circuit and the
identity of its input/output populations are supported by MaleCNS annotations and the
cited literature; implementation proceeds with the limits above stated in the config,
the artifact and every report. Nothing in escape_v1 is called a validated biological
escape behaviour; results are "an action decoded from simulated activity on a biologically
grounded structural circuit" (NEUROSCIENCE.md §4).

---

## 3. escape_v1 configuration (`backend/app/behavior/configs/escape_v1.json`)

| Field | Value | Rationale |
|---|---|---|
| sensory cell types | LC4, LPLC2 | Q1 |
| sensory groups | L: LC4+LPLC2 with `mcns_somaSide == "L"`; R: same for "R" | laterality [data]; LC dendrites are in the ipsilateral lobula (Wu 2016) |
| output cell type | DNp01 | Q2 |
| output groups | L: `10010`; R: `10001` | [data] |
| extractor | max_hops 1, min_synapses 10, max_neurons 2000, downstream, restrict_to_target_paths | monosynaptic documented pathway; 10 keeps every LC4→GF pair (min 21) and 158/185 LPLC2→GF pairs, and trims lateral LC↔LC edges from 5,025 to 932; both 5 and 10 reach both GFs (recorded alternative) |
| stimulus → current | `current = intensity × mapping_gain (1.0)` injected into the side group(s) for `duration_steps` (5); left → L group, right → R group, center → both | computational rule; intensity is **not** a measured firing rate |
| simulation | P3 `SimulationConfig` defaults, unchanged (dt 1, threshold 1, leak 0.2, refractory 2, log1p weights, weight_scale 1, unsigned) | no tuning toward an outcome; any change must be recorded here |
| decoder | `ESCAPE` if ≥ 1 simulated spike in any DNp01 within the run, else `NO_ACTION`; the side of the firing GF is reported as metadata, not as an action | Q2 / Jang 2023 |
| expected circuit hash | filled by `scripts/build_escape_config.py` from the P2 artifact `data/circuits/escape_v1.json` | tests verify the match |

## 4. Deferred / future (not in escape_v1)

- Forward/backward takeoff decoding via DNp02 / DNp04 / DNp11 (Dombrovski 2023; all three receive strong direct LC4 input [data]) — would need its own research gate (`escape_v2`).
- LC6 / LC16 / LPLC1 pathways to escape or avoidance behaviours.
- Contralateral routes to the GF; inhibitory size-encoding inputs to the GF.

## 5. Built configuration and artifact [data]

`scripts/build_escape_config.py` → `backend/app/behavior/configs/escape_v1.json` and
`data/circuits/escape_v1.json` (P2 artifact, hash `db7c46e6a165354d7aed499525e303131bd8d6367e492b2e4fc31117cdc2c78d`).

| Item | Value |
|---|---|
| sensory population (extraction seeds) | 311 = LC4 126 + LPLC2 185 (L 165 / R 146) |
| sensory group stimulated (in circuit) | 284 (L 155 / R 129): all 126 LC4 + 158 LPLC2 |
| excluded sensory ids (recorded) | 27 LPLC2 (L 10 / R 17) whose direct edge onto a DNp01 has < 10 synapses |
| output group | DNp01 L `10010`, R `10001` |
| circuit | 286 neurons / 932 edges: LC4→DNp01 126, LPLC2→DNp01 158, LC4→LC4 204, LPLC2→LPLC2 435, LPLC2→LC4 9 |
| targets | both DNp01 reachable, minimum_path_length 1 |

## 6. TECHNICAL CONNECTOME-GROUNDED ESCAPE DEMO (2026-09-16)

STRUCTURAL CONNECTIVITY IS BIOLOGICAL DATA. NEURAL ACTIVITY IS SIMULATED. STIMULUS MAPPING
AND MOTOR DECODING ARE COMPUTATIONAL INTERPRETATIONS.

Simulation: P3 `SimulationConfig` defaults, **unchanged** (dt 1, threshold 1, leak 0.2,
refractory 2, log1p weights, weight_scale 1, unsigned, seed 0); stimulus for 5 steps;
30 steps per run. Report: `data/simulations/escape_v1_demo.report.json`.

| direction | intensity | sensory fired (step, n) | GF spikes R `10001` / L `10010` | first GF step | decoded action |
|---|---|---|---|---|---|
| left | 0.2 | none | 0 / 0 | – | NO_ACTION |
| left | 0.5 | step 3, 155 | 0 / 1 | 4 | ESCAPE |
| left | 1.0 | step 1, 155 | 0 / 2 | 2 | ESCAPE |
| center | 0.2 | none | 0 / 0 | – | NO_ACTION |
| center | 0.5 | step 3, 284 | 1 / 1 | 4 | ESCAPE |
| center | 1.0 | step 1, 284 | 2 / 2 | 2 | ESCAPE |
| right | 0.2 | none | 0 / 0 | – | NO_ACTION |
| right | 0.5 | step 3, 129 | 1 / 0 | 4 | ESCAPE |
| right | 1.0 | step 1, 129 | 2 / 0 | 2 | ESCAPE |

Observations (properties of the computational model, not biological findings):
- Intensity 0.2 never reaches the firing threshold (0.2 → 0.36 → 0.49 → 0.59 → 0.67, then decay); 0.5 accumulates over three steps (0.5, 0.9, 1.22) → latency; 1.0 fires immediately. The intensity→latency relation is emergent from the leak/threshold parameters.
- The GF fires one step after the sensory group (one-step synaptic delay, monosynaptic path); no intermediate neuron exists in the circuit.
- The side of the firing GF follows the stimulated side (ipsilateral connectivity in the data). This is reported as metadata only; the decoded action is `ESCAPE` without direction (Jang et al. 2023).
- Activity stops when the stimulus ends: lateral LC→LC input arrives while the synchronously fired LC neurons are refractory, so no reverberation occurs here (contrast: P3 technical circuit).
- Each run takes ≈ 1.5 ms; the whole 9-run demo ≈ 0.02 s.
