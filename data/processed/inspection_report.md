# Dataset inspection report

- dataset / version: `male-cns` / `v1.0`
- source page: https://male-cns.janelia.org/download/
- download url: gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/
- license: CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Official statement on male-cns.janelia.org/download: 'The Male CNS is licensed under CC-BY.'
- synthetic fixture: False

## Source dataset
- name / version: MaleCNS v1.0
- official neuron count (approx.): 166,700
  - basis: MaleCNS v1.0 is described as approximately 166,700 neurons (project figure supplied at review); it equals the 166,700 bodies with a non-null 'superclass' in body-annotations v1.0 (empirical). The Cell paper reports 166,691 (search-only). Not the canonical graph count.
- annotated bodies in release table: 211,577
- raw connection rows: 151,856,684
- status counts: Traced 165,122 · Orphan 15,925 · Glia 11,864 · Unimportant 10,751 · null 5,472 · Assign 1,832 · Anchor 611

## Canonical simulation graph
- selection rule: `status == "Traced"`
- neurons: 165,122 (subset of the source dataset, NOT its complete neuron census)
- directed connections: 25,563,197
- dropped dangling edges: 126,293,487
- consistent with the normalized tables: True

## Normalized tables
- canonical graph neurons: 165,122
- directed connections: 25,563,197 (self-loops: 101)
- synapse_count min/max/median: 1 / 2591 / 2.0 (total 124,025,046)
- missing IDs (dangling edges): pre 0, post 0, either 0
- duplicate neuron IDs: 0 (0 rows)
- duplicate (pre, post) edge pairs: 0

## Available annotation columns (non-null / distinct)
- `cell_type`: 162,517 / 11,751
- `cell_class`: 24,524 / 21
- `region`: 0 / 0
- `neurotransmitter`: 164,620 / 8
- `sex`: 165,122 / 1
- `source_url`: 165,122 / 1
- `mcns_assignedOlHex1`: 23,720 / 36
- `mcns_assignedOlHex2`: 23,720 / 39
- `mcns_flywireType`: 141,169 / 8,199
- `mcns_group`: 145,524 / 13,746
- `mcns_instance`: 158,082 / 23,848
- `mcns_somaSide`: 149,042 / 3
- `mcns_statusLabel`: 165,122 / 7
- `mcns_superclass`: 164,606 / 26
- `mcns_type`: 162,517 / 11,751
- `mcns_vfbId`: 164,595 / 164,595
- `mcns_hemibrainType`: 32,919 / 4,495
- `mcns_itoleeHl`: 37,745 / 203
- `mcns_supertype`: 34,096 / 1,925
- `mcns_birthtime`: 7,903 / 2
- `mcns_mancBodyid`: 18,557 / 18,146
- `mcns_mancGroup`: 14,553 / 5,830
- `mcns_mancType`: 22,743 / 3,893
- `mcns_subclass`: 21,924 / 49
- `mcns_synonyms`: 3,954 / 280
- `mcns_class`: 24,524 / 21
- `mcns_rootSide`: 15,903 / 3
- `mcns_somaNeuromere`: 21,802 / 21
- `mcns_trumanHl`: 19,737 / 76
- `mcns_dimorphism`: 2,368 / 4
- `mcns_matchingNotes`: 3,411 / 276
- `mcns_entryNerve`: 11,781 / 21
- `mcns_mancSerial`: 5,422 / 939
- `mcns_mcnsSerial`: 3,945 / 707
- `mcns_serialMotif`: 902 / 8
- `mcns_fruDsx`: 5,012 / 6
- `mcns_exitNerve`: 1,005 / 28
- `mcns_receptorType`: 752 / 3
- `mcns_somaLocation`: 140,024 / -
- `mcns_tosomaLocation`: 995 / -
- `mcns_status`: 165,122 / 1
- `mcns_nt_predicted_nt_confidence`: 163,763 / 96,710
- `mcns_nt_total_nt_predictions`: 164,620 / 3,164
- `mcns_nt_consensus_nt`: 164,620 / 8
- `mcns_nt_celltype_predicted_nt`: 164,620 / 8
- `mcns_nt_ground_truth`: 83,496 / 7
