# START HERE — 給 Codex / Claude Code 的第一個指令

把整個 `flybrain_agent_docs` 文件內容放到新 repository 根目錄後，對 Coding Agent 下：

```text
請先完整閱讀 README.md、PRD.md、SDD.md、DATA.md、NEUROSCIENCE.md、AGENTS.md、TASKS.md、PROGRESS.md。

你現在是 FlyBrain Agent 專案的實作工程師。

規則：
1. 嚴格依 TASKS.md 的 Phase 順序施工。
2. 現在只執行 P0。
3. 不得提前做 P1 之後的功能。
4. 每個 Phase 都必須完成 implementation、unit test、smoke test。
5. Acceptance Criteria 沒有全部通過，不得宣告完成。
6. 不可捏造任何 biological neuron ID、edge、cell type、synapse count 或 dataset schema。
7. 遇到資料來源或 neuroscience mapping 不確定時，停止並清楚列出問題，不要猜。
8. 完成後更新 PROGRESS.md，列出：
   - 新增/修改檔案
   - 測試結果
   - smoke test 結果
   - 已知限制
   - 下一階段建議
9. 完成 P0 後停止，等待我確認。

開始執行 P0。
```

## P0 完成後
先人工確認結果，再下：

```text
讀取目前 repository 與 PROGRESS.md。
確認 P0 Acceptance Criteria。
若全部通過，執行 TASKS.md 的 P1。
嚴格遵守 DATA.md：先確認目前官方資料取得方式與實際 schema，不准猜測。
完成 P1 測試與 smoke test、更新 PROGRESS.md 後停止。
```

不要一次叫 Agent 做 P0-P9。
