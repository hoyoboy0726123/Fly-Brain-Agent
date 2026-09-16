# PRD — FlyBrain Agent

## 1. Product Vision
建立一個讓一般使用者可以直觀看懂「生物神經網路如何從感知走到行動」的互動式平台。

產品不是單純 3D connectome viewer，而是讓真實 connectome connectivity 成為 agent controller 的結構基礎。

## 2. Target Users
### Primary
- AI / Agent 教學者
- 對 AI Coding、Agentic AI、仿生運算感興趣的開發者
- Hackathon / Demo 觀眾

### Secondary
- 神經科學教育使用者
- Connectome data explorer

## 3. Core User Story
身為使用者，我希望在虛擬環境製造一個危險刺激，看到 sensory neurons 被刺激、訊號經 connectome circuit 傳播、output population 活化，最後讓虛擬果蠅逃跑。

## 4. MVP Experience
### Main screen
三欄：
1. Environment
2. Fly Brain
3. Action

### Demo Flow
1. 使用者按下 `Danger` 或啟動 looming object。
2. Environment 產生 stimulus event。
3. Sensor Adapter 將 stimulus mapping 到已配置的 sensory population。
4. Simulation Engine 執行固定時間步數。
5. UI 即時顯示 activated/firing neurons。
6. Motor Decoder 根據 output population activity 產生 action。
7. Virtual Fly 移動。
8. 使用者可點擊 neuron 查看 provenance。

## 5. MVP Functional Requirements

### FR-01 Dataset Loader
系統可載入官方/授權 connectome metadata 與 connectivity table。

### FR-02 Provenance
每一個 neuron/edge 必須可追溯：
- dataset name
- dataset version
- source
- neuron ID
- pre/post ID
- synapse count / connection weight source

### FR-03 Circuit Extractor
支援：
- seed population
- target population
- max hops
- minimum connection threshold
- maximum neuron count

### FR-04 Simulation
提供 deterministic simplified neural simulation。
第一版允許 LIF 或明確記錄的等效簡化模型。

### FR-05 Stimulus Mapping
virtual stimulus 可 mapping 到 sensory population。

### FR-06 Motor Decoder
output population activity 可轉成有限 action set：
- IDLE
- FORWARD
- LEFT
- RIGHT
- ESCAPE_LEFT
- ESCAPE_RIGHT

### FR-07 Visualization
顯示目前 circuit 與 activation propagation。

### FR-08 Neuron Inspector
點 neuron 顯示：
- ID
- type/class（若資料有）
- region（若資料有）
- upstream/downstream summary
- current simulated state
- source/provenance

### FR-09 Reproducibility
同一 dataset、config、seed、stimulus 應可重現結果。

## 6. Non-functional Requirements
- 本機開發環境可執行。
- MVP circuit 建議 <= 2,000 neurons。
- UI 不因 simulation blocking 而凍結。
- raw dataset 不 commit 到 Git。
- 所有 simulation parameters 必須 config 化。
- 核心計算有 unit tests。
- API 有 smoke tests。
- 前端主流程有 Playwright smoke test。

## 7. Success Criteria
MVP demo 能在一台一般開發筆電上完成：
Danger → neural activity → motor output → virtual escape。

且任一展示的 biological edge 可追溯到來源資料。

## 8. Future Scope
- Food seeking / olfactory circuit
- 多刺激競爭
- Webcam looming detector
- ESP32 / robot body
- 3D morphology
- Male vs female circuit comparison
- Different simulation models
