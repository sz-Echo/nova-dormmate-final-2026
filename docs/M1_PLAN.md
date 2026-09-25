# M1 详细执行计划 — Web 主应用：输入、判断、记录

> 依据：docs/DORMMATE_SPEC.md、docs/PLAN.md、任务书 M1 原文。本文件是 M1 期间的执行依据，随进度更新；与 SPEC/PLAN 冲突时以 SPEC 为准。

## 1. 决策记录（已与用户确认）

- **合并口径**：M1 = Web 主应用（index.html + style.css + script.js）+ 统一规则与四组回归测试；CSV 落盘延后到 M2
- **建议文案**：偏冷→注意保暖；偏热→注意通风；偏湿→注意除湿；正常→环境舒适
- **事实源裁定**：任务书原文为最高事实源；SPEC/PLAN 已按任务书修正 M2/M3/A 组定义（S0-b 已完成）

## 2. 范围红线（M1 不做）

- 不做 CSV 落盘（M2）、语音（M3）、多节点（M5 起）；无数据库 / 传感器 / LLM
- 历史仅存内存，刷新后可消失——持久化是 M2 CSV 的事
- M1-M4 单宿舍：页面固定 nodeId = "dorm-a"

## 3. 执行步骤（每步完成停下等用户确认）

### S0 文档对齐 ✅ 已完成

SPEC/PLAN 按任务书原文修正（M1 合并口径、§3.1 校验范围、M2/M3 重定义、A 组重定义、B 组程序化说明、C 组 IsolationForest、action 预留字段、GitHub 仓库名 nova-dormmate-final-2026）；CLAUDE.md 工作步骤加入本文件；创建本文件。

### S1 静态骨架（任务书①）✅ 已完成（用户浏览器确认布局齐全）

- 新建 web/：index.html + style.css + script.js（空实现）
- 元素：标题 DormMate、温度输入、湿度输入、分析环境按钮、错误提示区、当前状态/建议区、历史区
- 输入框 type="text" + inputmode="decimal"（便于演示非数字校验）
- **检查点**：Chrome/Edge 打开页面，布局齐全

### S2 统一规则 + 回归测试（PLAN M1 核心）✅ 已完成（node 自检 + 用户浏览器确认四组全过，随 Commit 1 提交）

- **script.js 结构要求（保证 test.html 能安全引入）**：
  - `computeStatus(temperature, humidity)` 纯函数，严格按 SPEC §3 顺序（<18 偏冷 → ≥30 偏热 → ≥75 偏湿 → 正常），命中即返回，直接暴露到全局
  - `ADVICE` 建议映射表（偏冷→注意保暖；偏热→注意通风；偏湿→注意除湿；正常→环境舒适），直接暴露
  - `analyze()` 暴露到 window（供 M3 语音指令调用）
  - **DOM 操作一律包在 DOMContentLoaded 或存在性判断里**——test.html 引入 script.js 时没有页面元素，顶层 DOM 操作会报 null 导致回归测试跑不起来
- web/test.html：引入同一 script.js，跑四组回归（25/60→正常、16/60→偏冷、31/60→偏热、25/80→偏湿）显示通过/失败
- **检查点**：test.html 四组全过
- **提交**：Commit 1 `feat(nova-dormmate-final-2026): M1 skeleton and status rule with regression tests`（先展示变更摘要，用户确认后提交）

### S3 接入输入 + 建议（任务书②）✅ 已完成（代码落地，node 桩测通过，待用户浏览器确认）

- `analyze()`：读取输入 → Number() 转换 → computeStatus → 显示状态与建议（ADVICE 映射表）
- analyze() 为命名函数、可外部调用——M3 语音指令直接调它，不另写流程
- **检查点**：输入 31/78 得偏热+注意通风；25/55 得正常+环境舒适

### S4 输入校验（任务书③）✅ 已完成（代码落地，node 桩测通过，待用户浏览器确认）

- 空值 / 非数字（Number() 后 isNaN）/ 明显异常值（SPEC §3.1：温度 −50~50、湿度 0~100 之外）→ 错误提示区显示具体原因；不分析、不追加历史
- **检查点**：三类非法输入均被拦截且有提示

### S5 历史记录（任务书⑤）✅ 已完成（代码落地，node 桩测通过，待用户浏览器确认）

- 成功分析后追加历史，连续 ≥5 条，追加不覆盖；仅存内存，刷新后可消失
- 历史记录内部结构 = SPEC §4 统一 JSON：`{nodeId:"dorm-a", temperature, humidity, status, time, action:""}`（action 预留空字符串，A2 起按节点追加；time 用 YYYY-MM-DD HH:MM:SS 全格式）
- **检查点**：连续 5 次分析后历史 5 条，顺序与内容正确

### S6 样式收尾（任务书⑥）✅ 已完成（待用户浏览器确认）

- 整理 CSS；保留至少一处明确自定义的布局/样式（验收第 5 条），在本文档记录它来自哪段 CSS
- **自定义样式记录（验收第 5 条）**，全部在 web/style.css，未使用任何第三方样式库：
  - ① 卡片式三区块布局：`.input-area, .result-area, .history-area` 的白底圆角卡片规则（含背景/边框/圆角/内边距）
  - ② 输入区双列网格：`.input-fields { display: grid; grid-template-columns: 1fr 1fr; }`，窄屏（≤420px）媒体查询降为单列
  - ③ 状态大字高亮 `#statusText`（1.6rem 加粗）、建议灰字 `#adviceText`、历史虚线分隔、空历史"暂无记录"占位（`#historyList:empty::after`）
- **检查点**：界面可用、样式标注清楚（本记录即标注）

### S7 验收 + 交接 ✅ 已完成（现场 3 组新数据、关闭重开验证、历史截图均通过，随 Commit 2 提交）

- 对照验收清单逐条走查 + 现场输入 3 组新数据（状态/建议正确变化）
- 关闭重开验证：关闭浏览器 → 重新打开 web/index.html → 页面正常、历史为空（不持久化）→ 输入一组新数据仍正确
- README.md 最小初稿：项目名 + 运行方式（Chrome/Edge 打开 web/index.html；回归测试打开 web/test.html）
- 截图留存 docs/evidence/m1/
- 更新 PLAN.md §4 看板（M1 完成）与 §2 状态列；按 PLAN §6 模板输出交接摘要
- **提交**：Commit 2 `feat(nova-dormmate-final-2026): M1 web input judge history acceptance`（先展示变更摘要，用户确认后提交）

## 4. 关键设计 — 与后续阶段衔接

| M1 产物 | 后续谁用 | 怎么用 |
|---|---|---|
| computeStatus() | M4 小程序 | 迁移业务规则：复用纯函数与统一规则，不复制 Web DOM 代码 |
| computeStatus() | M5 simulator/dashboard | 全项目唯一实现，禁止重写 |
| computeStatus() | Python 侧（M2 离线分析） | Python 移植须过同一四组回归测试 |
| analyze() 入口 | M3 ASR 固定指令 | 语音识别到指令直接调用 |
| 历史记录 JSON（含 action 预留） | M2 CSV 导出 / A 组优先关注 | 序列化即 4 列 CSV；A1 按 time 分组算连续异常时长 |
| nodeId:"dorm-a" 固定 | M5 三节点 | 单宿舍阶段占位，M5 起按节点区分 |
| web/test.html 回归证据 | M2 Python 移植 / A 组 | 证据直接复用 |

## 5. 验收清单（完成线）

1. index.html + style.css + script.js 三文件，浏览器稳定运行
2. 输入 → 校验 → 统一规则判断 → 状态 + 建议 全流程可用
3. 空值、非数字、明显异常值有提示，不进入分析、不追加历史
4. 每次成功分析生成一条带日期时间历史，连续 ≥5 条，刷新后可消失
5. 至少一处自定义布局/样式，能指出来自哪段 CSS
6. 现场输入 3 组新数据，状态/建议正确变化
7. 四组回归测试 test.html 全部通过（额外质量门禁，不替代上述任务书验收）
8. 能解释：输入在哪里读入、规则在哪里判断、历史在哪里加入
9. 关闭浏览器重开后：页面正常、历史为空、输入新数据仍正确

## 6. 验证方式

- Chrome/Edge 打开 web/index.html 走查全流程；打开 web/test.html 确认四组全过
- 关闭浏览器重开验证（验收第 9 条）
- 截图 → docs/evidence/m1/，随 M1 提交
