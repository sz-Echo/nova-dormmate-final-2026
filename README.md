# DormMate Final（nova-dormmate-final-2026）

宿舍环境助手：温湿度输入 → 统一规则判断 → 状态与建议 → 带时间历史（单宿舍 dorm-a）。

## 运行方式

- **主应用**：Chrome / Edge 打开 `web/index.html`（也可用 VS Code Live Server 起 http://127.0.0.1:5500/web/index.html）
- **回归测试**：打开 `web/test.html`，四组统一回归数据（SPEC §6）应全部显示通过

## 当前进度（M1 完成）

- 输入校验：空值 / 非数字 / 超出范围（温度 −50~50、湿度 0~100）均有红字提示，不进入分析、不追加历史
- 状态规则：`<18 偏冷 → ≥30 偏热 → ≥75 偏湿 → 其余 正常`（顺序固定不可改，见 docs/DORMMATE_SPEC.md §3）
- 建议：偏冷→注意保暖 / 偏热→注意通风 / 偏湿→注意除湿 / 正常→环境舒适
- 历史记录：仅存内存（统一 JSON 结构），刷新页面后清空；M2 起落盘 CSV

## 文档

- 项目规格：`docs/DORMMATE_SPEC.md`
- 执行计划：`docs/PLAN.md`（M1 详细步骤与验收记录见 `docs/M1_PLAN.md`）
