# FlyBrain Agent

> 用真實果蠅 connectome 作為結構基礎，建立可感知、傳遞神經訊號並產生行動的 Biological Agent。

## 目標
第一版 MVP 不追求完整重現果蠅生理，也不直接模擬全部 166,691 個神經元。
目標是建立一條可驗證的：

**Stimulus → Sensory Population → Connectome-grounded Circuit → Simplified Neural Dynamics → Output Population → Action**

並在 Web UI 中讓使用者看見刺激、神經活動與行動結果。

## 科學基礎
2026 年 Google Research、HHMI Janelia 與合作團隊發布完整雄性果蠅中樞神經系統 connectome：
- 166,691 neurons
- 11,691 annotated types
- 超過 125 million synaptic connections
- 涵蓋 central brain、optic lobes、ventral nerve cord
- 可用於 sensory-to-motor circuit analysis

官方來源：
- https://www.research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/
- https://research.google/pubs/sexual-dimorphism-in-the-complete-connectome-of-the-drosophila-male-central-nervous-system/
- https://sites.research.google/gr/neural-mapping/datasets/

## MVP 完成定義
使用者打開網頁後：
1. 看見 Virtual Fly 與環境。
2. 觸發 Danger / Looming stimulus。
3. 系統刺激指定 sensory population。
4. 訊號沿由真實 connectome 萃取出的 circuit 傳播。
5. 簡化 neural dynamics 計算神經活動。
6. Output / descending population 活化。
7. Motor Decoder 產生 action（v0.1 的 escape_v1 只解碼 NO_ACTION / ESCAPE；GF 為方位不變，左右不解碼）。
8. Virtual Fly 執行動作。
9. 使用者可查看 neuron ID、type、connectivity、dataset provenance。

## 非目標
- 不宣稱模擬結果等同真實果蠅神經活動。
- 不以人工編造 edge 冒充 connectome connection。
- MVP 不要求 166K neurons 全腦即時 simulation。
- MVP 不要求實體 robot。
- MVP 不要求 neuroscience-grade membrane model。

## 建議技術棧
Backend: Python 3.11+, FastAPI, NumPy, Pandas/Polars, SciPy, NetworkX/igraph, PyArrow
Frontend: React, TypeScript, Vite, D3.js，必要時 Three.js
Storage: Parquet + SQLite
Realtime: WebSocket
Tests: pytest + Playwright

## 開發順序
P0 Bootstrap
P1 Data ingestion
P2 Graph & circuit extraction
P3 Neural simulation
P4 Escape behavior
P5 Web UI
P6 Brain visualization & inspector
P7 Food seeking
P8 Webcam
P9 Robot adapter

**規則：前一階段 Acceptance Criteria 全部通過，才能進下一階段。**

## FlyBrain Agent MVP v0.1（P0–P6 完成）

**Architecture**

```
MaleCNS v1.0 (source dataset, ≈166,700 neurons, CC-BY 4.0)
  ↓  P1  DatasetAdapter → neurons.parquet / connections.parquet / provenance.json
Canonical Graph (status == "Traced": 165,122 neurons / 25,563,197 directed connections)
  ↓  P2  CircuitExtractor (bounded BFS, hash-sealed artifact)
Circuit artifact escape_v1 (286 neurons / 932 edges, LC4 + LPLC2 → DNp01/GF)
  ↓  P3  SimulationEngine (simplified LIF-like model — SIMULATED activity)
Simulated activity (spikes, membrane potentials per step)
  ↓  P4  LoomingStimulus → StimulusMapper → MotorDecoder (NO_ACTION / ESCAPE)
Behavior (computational interpretation; BIOLOGICAL CIRCUIT STATUS: PARTIALLY SUPPORTED)
  ↓  P5  FastAPI (/escape/*, WS /ws/escape) + React dashboard
Interactive Web Demo (Environment / Fly Brain / Action)
  ↓  P6  read-only /circuits/* API + D3 graph
Brain Inspector (neuron / edge / connectivity / provenance / activity replay)
```

Three layers stay visually and programmatically separate everywhere:
**BIOLOGICAL STRUCTURE** (neuron identity + structural edges from the artifact) ·
**SIMULATED ACTIVITY** (firing / membrane potential from the model) ·
**COMPUTATIONAL INTERPRETATION** (looming mapping + ESCAPE decoder).

**How to run**

```bash
make install            # backend/.venv + frontend/node_modules (Playwright: npx playwright install chromium)
make backend            # FastAPI  http://127.0.0.1:8000  (OpenAPI at /docs)
make frontend           # Vite     http://127.0.0.1:5173
make test               # pytest (294) + frontend typecheck
make smoke              # backend/data/circuit/simulation/escape/web smokes + Playwright (47 tests)
```

The committed `data/circuits/escape_v1.json` is enough for the demo and the inspector; the raw
MaleCNS files are only needed to rebuild it (`make normalize`, `make build-escape-config`).

**How to trigger looming** — open http://127.0.0.1:5173 (tab *Demo*): pick LEFT / CENTER /
RIGHT, set the intensity (0–1) and press **TRIGGER LOOMING**. The looming disc grows in the
Environment panel, the Fly Brain panel replays the backend's per-step SIMULATED activity
(LC4 / LPLC2 → DNp01), and the Action panel shows **NO ACTION** or **ESCAPE** (GF side is
metadata only). Reference outcomes: CENTER 0.2 → NO ACTION, CENTER 0.5 → ESCAPE, LEFT 1.0 → ESCAPE.

**How to inspect a neuron** — tab *Brain Inspector*: the whole `escape_v1` circuit
(286 neurons / 932 edges, never the canonical graph) is drawn with D3. Zoom/pan, hover, click a
neuron or an edge, or type an exact neuron id (e.g. `10010`) in *Search neuron id*; filter by
cell type (`LC4`, `LPLC2`, `DNp01`). The inspector separates **BIOLOGICAL METADATA**
(neuron_id, cell_type, cell_class, neurotransmitter_prediction, dataset, dataset_version —
"Not available" when the artifact has no value) from **CIRCUIT / SIMULATION METADATA**
(minimum_hop_from_seed, is_seed, is_target, side/role from the escape config) and from
**SIMULATED STATE** (membrane potential / fired / refractory at the replayed step). *Connections
within loaded circuit* lists upstream and downstream partners with synapse counts; *Highlight
upstream / downstream* marks them on the graph. Clicking an edge shows the **BIOLOGICAL
STRUCTURAL CONNECTION** (FROM, TO, synapse_count = biological structural observation, dataset,
circuit_id, circuit_hash) and, separately, the **computational simulation weight**. Press
**RUN LOOMING** in the inspector and use PLAY / PAUSE / STEP / RESET or the timeline slider to
replay the simulated activity on the graph.

**How to inspect provenance** — the *Provenance* panel of the inspector (and
`GET /api/circuits/escape_v1/provenance`) reports the dataset (MaleCNS v1.0),
the canonical graph (`status == "Traced"`: 165,122 neurons / 25,563,197 connections — a canonical
subset, not the complete census), the loaded circuit (escape_v1, 286 / 932), the circuit hash and its verification, the
biological status (PARTIALLY SUPPORTED, `docs/circuits/escape_v1.md`), the license, the official
source/download URLs, the raw file sha256 digests and the seven literature citations.

Screenshots: `docs/screenshots/mvp-A-p5-main-demo.png`, `mvp-B-inspector-full-graph.png`,
`mvp-C-neuron-DNp01.png`, `mvp-D-edge-LC4-DNp01.png`, `mvp-E-activity-replay.png`.

## 快速開始（開發者）

完整說明見 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

```bash
make install     # backend/.venv + frontend/node_modules
make backend     # FastAPI  http://127.0.0.1:8000  (GET /health)
make frontend    # Vite     http://127.0.0.1:5173
make test        # pytest + frontend typecheck
make smoke       # backend /health smoke + data smoke (fixture) + Playwright frontend smoke
make normalize   # MaleCNS v1.0 raw files (data/raw) -> data/processed parquet + provenance.json
make inspect     # DATA.md §7 validation report
make extract ARGS="--circuit-id demo --seeds <id> --max-hops 2 --min-synapses 10 --max-neurons 2000"
make smoke-circuit  # P2 extractor smoke (fixture + technical MaleCNS run when data present)
make simulate ARGS="--fixture --stimulate syn_001 --intensity 2.0 --duration 3 --steps 30"
make smoke-simulation  # P3 simulated-activity smoke (模擬活動，非量測資料)
make smoke-escape      # P4 TECHNICAL CONNECTOME-GROUNDED ESCAPE DEMO（結構為生物資料、活動為模擬、解碼為計算詮釋）
make smoke-web         # P5 web demo smoke：escape API（REST + WebSocket）三個示範情境
make backend && make frontend  # 開 http://127.0.0.1:5173 → 互動式示範（Demo）與 Brain Inspector（#inspector）
```

測試與 smoke test 不需要下載任何 connectome 資料集；`data/raw/` 已被 git 忽略。真實資料的取得方式、schema 與授權（CC-BY）驗證紀錄見 [docs/dataset_research.md](docs/dataset_research.md)。

## 來源資料集 vs Canonical 模擬圖（重要區分）

| | 來源資料集（Source Dataset） | Canonical 模擬圖（Canonical Simulation Graph） |
|---|---|---|
| 是什麼 | MaleCNS v1.0 官方發布的完整資料集 | 本專案實際用來模擬的子集 |
| 神經元 | 約 166,700（論文報告 166,691） | 165,122（canonical 子集，非完整總數） |
| 選取規則 | 無（就是資料集本身） | `status == "Traced"` |
| 連結 | 151,856,684 筆原始 body→body 列 | 25,563,197 條有向邊 |

**165,122 是 canonical 模擬圖的神經元數，不是 MaleCNS 的完整神經元總數。** 兩者都記錄在
`data/processed/provenance.json`（`source_dataset` / `canonical_graph`）並由 `make inspect` 同時列出；規則見 [DATA.md](DATA.md) §8。
