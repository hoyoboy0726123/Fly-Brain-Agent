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
7. Motor Decoder 產生 ESCAPE_LEFT / ESCAPE_RIGHT 等 action。
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
