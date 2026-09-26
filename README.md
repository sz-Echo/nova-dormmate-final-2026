# DormMate Final（nova-dormmate-final-2026）

宿舍环境助手：温湿度输入 → 统一规则判断 → 状态与建议 → 带时间历史（单宿舍 dorm-a）。

## 运行方式

- **主应用**：Chrome / Edge 打开 `web/index.html`（也可用 VS Code Live Server 起 http://127.0.0.1:5500/web/index.html）
- **回归测试**：打开 `web/test.html`，四组统一回归数据（SPEC §6）应全部显示通过
- **离线分析（M2）**：Web 页"导出 CSV"得到 dormmate.csv 放到 `data/` 后，在项目根目录运行（需 Python 3 + pandas + matplotlib）：
  - `python analysis/analyze.py` —— 读取 `data/dormmate.csv`，输出统计并生成 `data/trend.png`、`data/report.html`
  - `python analysis/analyze.py 其他CSV路径` —— 换一份新 CSV 后全量重新生成统计与两产物（验收要求，禁止手工修改）
  - `python analysis/analyze.py --selftest` —— SPEC §6 四组回归自测

## 当前进度（M2 完成；最新看板见 docs/PLAN.md §4）

- 输入校验：空值 / 非数字 / 超出范围（温度 −50~50、湿度 0~100）均有红字提示，不进入分析、不追加历史
- 状态规则：`<18 偏冷 → ≥30 偏热 → ≥75 偏湿 → 其余 正常`（顺序固定不可改，见 docs/DORMMATE_SPEC.md §3）
- 建议：偏冷→注意保暖 / 偏热→注意通风 / 偏湿→注意除湿 / 正常→环境舒适
- 历史记录：仅存内存（统一 JSON 结构），刷新页面后清空；通过"导出 CSV"落盘
- 离线分析（M2）：CSV 导出（Blob + download、UTF-8 带 BOM、4 列最小格式）→ pandas 读取并重跑统一规则 → 统计（记录数 / 温湿度最高最低 / 各状态数量 / 关注记录）+ `data/trend.png` + `data/report.html`；换新 CSV 全量重新生成

## 已知限制

- 移动端 iOS 数字键盘无负号键（`inputmode="decimal"` 所致），负温度需用全键盘输入；桌面浏览器无此问题

## 文档

- 项目规格：`docs/DORMMATE_SPEC.md`
- 执行计划：`docs/PLAN.md`（M1 详细步骤与验收记录见 `docs/M1_PLAN.md`，M2 见 `docs/M2_PLAN.md`）
