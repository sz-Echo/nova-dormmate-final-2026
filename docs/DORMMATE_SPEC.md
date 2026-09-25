# DormMate Final 项目规格说明（DORMMATE_SPEC）

> **唯一事实源**：本文件与 PLAN.md 是 DormMate Final 的唯一事实源。两者冲突时以本文件为准；本文件变更须用户确认。所有模块、所有实现语言必须遵守本文件第 3-6 节的统一规范。

## 1. 项目一句话

DormMate Final —— 多节点宿舍环境助手：至少 dorm-a / dorm-b / dorm-c 三个模拟节点，跑通"离线分析"与"实时系统"两条数据链。

## 2. 两条必须跑通的数据链

| 链 | 数据流 | 说明 |
|---|---|---|
| 离线分析链 | Web -> CSV -> Python -> trend.png / report.html | Web 采集数据落 CSV，Python 读取分析并产出趋势图与报告 |
| 实时系统链 | 模拟节点 -> MQTT -> Dashboard -> 3D | 模拟节点经 MQTT 发布，Dashboard 订阅展示，3D 场景联动 |

两条链都必须端到端跑通，最终以"关闭所有进程后重启复跑"验证（见 PLAN 的 Final 阶段）。

## 3. 统一状态规则（顺序不可改）

status 必须按以下顺序判断，命中即返回，禁止调换顺序：

1. `temperature < 18` → **偏冷**
2. 否则 `temperature >= 30` → **偏热**
3. 否则 `humidity >= 75` → **偏湿**
4. 其余 → **正常**

### 3.1 输入校验范围（编程练习用）

- `temperature` 合法范围：−50 ~ 50（含边界）
- `humidity` 合法范围：0 ~ 100（含边界）
- 超出范围视为明显异常值，必须提示且不进入分析；各模块（Web / 小程序 / 模拟节点）统一复用此范围

## 4. 统一 JSON 字段

```json
{"nodeId":"dorm-a","temperature":31,"humidity":78,"status":"偏热","time":"2026-09-22 20:30:00","action":""}
```

- 字段名全项目统一：`nodeId` / `temperature` / `humidity` / `status` / `time` / `action`（禁止 id、room、temp、hum 等其他写法）
- **`status` 必须由 temperature / humidity 按第 3 节规则计算得出，禁止手填、硬编码或由输入直接带入**
- `nodeId` 取值：dorm-a / dorm-b / dorm-c
- `time` 格式：YYYY-MM-DD HH:MM:SS
- `action` 为预留字段：M1-M4 恒为空字符串 ""；A2（用户处理动作）起按节点写入动作（如 "fan_on"），避免后期改 JSON 结构

## 5. CSV 最小格式

```
time,temperature,humidity,status
```

- 最小格式为上述 4 列（表头 + 数据行），编码统一 UTF-8
- 单宿舍阶段（M1-M4）：严格 4 列；M2 离线链导出文件命名为 data/dormmate.csv（任务书原文）
- 三节点阶段（M5 起）：推荐每节点一个 CSV 文件（如 data/dorm-a.csv、data/dorm-b.csv、data/dorm-c.csv），保持 4 列不变；如确需混存，增加 nodeId 列——两种方案全项目二选一并统一，禁止混用
- status 列同样必须按第 3 节规则计算

## 6. 统一回归测试数据

| temperature | humidity | 期望 status |
|---|---|---|
| 25 | 60 | 正常 |
| 16 | 60 | 偏冷 |
| 31 | 60 | 偏热 |
| 25 | 80 | 偏湿 |

这四组是任何 status 计算实现的回归测试，必须全部通过；各模块复用同一实现，不得各自重写规则。

## 7. 推荐目录结构

```
nova-dormmate-final-2026/    # 项目根（本机：F:\AIcoding\nova-dormmate-final-2026）
├── docs/          # 唯一事实源：DORMMATE_SPEC.md、PLAN.md
├── web/           # M1 Web 主应用（输入/判断/记录）；M2 CSV 导出；M3 Camera/ASR/TTS
├── analysis/      # M2 Python 离线分析（CSV -> trend.png / report.html）
├── mobile/        # M4 移动端小程序（微信开发者工具）
├── simulator/     # M5 模拟节点发布器（dorm-a / dorm-b / dorm-c）
├── dashboard/     # M5 MQTT 看板
├── three3d/       # M6 Three.js 3D 场景
└── data/          # CSV 数据与产物（trend.png、report.html）
```

目录随阶段解锁创建（M1 创建 web/，M2 创建 data/ 与 analysis/，以此类推），不在未解锁阶段提前建目录。

## 8. M1-M6 模块要求（目标 / 最低完成线 / 证据）

### M1 Web 主应用：输入、判断、记录
- **目标**：web/ 单页面应用（index.html + style.css + script.js）：温湿度输入 → 校验（第 3.1 节范围）→ 统一规则判断（第 3 节）→ 状态 + 建议 → 带时间历史（单宿舍 dorm-a）；落地统一状态规则与统一 JSON（第 4 节）作为全项目统一实现
- **最低完成线**：四组回归测试数据（第 6 节）全部算对 + 任务书 M1 验收条目（校验拦截、≥5 条历史、一处自定义 CSS、现场 3 组新数据、能指出输入 / 规则 / 历史位置）
- **证据**：web/test.html 四组通过截图 + 页面运行截图 + 历史截图

### M2 离线数据分析与报告
- **目标**：M1 历史 → 导出 data/dormmate.csv（4 列最小格式，UTF-8）→ analysis/ Python 读取 → 基础统计（记录数、温湿度最高 / 最低）→ 对全部记录重跑统一规则（统计各状态数量、列出需要关注的记录）→ matplotlib 生成 trend.png → 自动生成 report.html（摘要、关注记录、趋势图）
- **注**：任务书未明确定义"需要关注的记录"，本项目暂按 status 非正常（偏冷 / 偏热 / 偏湿）为准
- **最低完成线**：任务书 M2 验收条目全部满足；**换一份新 CSV 后统计、trend.png、report.html 必须全部由程序重新生成**，禁止手工修改结果冒充程序生成
- **证据**：Web 导出的 CSV（Excel / WPS 打开核对）+ Python 脚本 + trend.png + report.html

### M3 本机交互 + 版本记录
- **目标**：
  - Camera：用户主动打开预览并保存一张现场快照（不连续采集）
  - ASR：至少识别 1 条固定语音指令并把识别结果显示在页面中，指令真正触发已有功能（如"朗读状态"→TTS、"拍照"→Camera）；默认桌面版 Chrome / Edge + localhost 的 SpeechRecognition，不可用时按第 13 节约定等价替代并在 README 记录
  - TTS：朗读内容随当前状态变化
  - Git / GitHub：Challenge 期间至少 3 次有意义 Commit；本地提交历史 + Push 到自己的 GitHub 仓库；能说明其中 2 次 Commit 分别改了什么；最终稳定版本与本地 / GitHub 最新 Commit 对应
  - README：运行方式、主要功能、已知限制
- **最低完成线**：任务书 M3 验收条目全部满足（Camera + ASR/TTS 现场可运行；至少 1 条固定指令真实触发已有功能；**不能跳过"识别文字 + 固定指令触发功能"**）
- **证据**：现场快照、ASR 识别结果截图、TTS、git log、GitHub Commit 记录、README

### M4 移动端小程序
- **目标**：mobile/ 微信小程序核心页面（查看宿舍状态 / 数据，单宿舍即可）；复用 M1 同一套业务规则（computeStatus 纯函数），不复制 Web DOM 代码
- **最低完成线**：微信开发者工具能稳定运行核心页面；**不把 AppID / 真机账号作为最低完成线**
- **证据**：微信开发者工具运行截图

### M5 MQTT 实时系统（三节点起）
- **目标**：在笔记本本机启动 Broker（不要求公网 / 共享 Broker）；模拟节点 dorm-a / dorm-b / dorm-c 按统一 JSON 发布；dashboard/ 订阅并同屏展示三节点；Topic 命名统一 `dormmate/{nodeId}/env`（如 dormmate/dorm-a/env）
- **最低完成线**：三节点同屏、实时刷新、互不串线；status 按规则计算
- **证据**：Dashboard 三节点同屏运行截图 + 订阅日志

### M6 Three.js 3D 可视化
- **目标**：three3d/ 3D 场景展示三个宿舍（状态映射为视觉表现，如颜色 / 图标），由 MQTT 实时数据驱动
- **最低完成线**：3D 中三节点状态随实时数据更新、互不串线
- **证据**：3D 截图 / 录屏

## 9. A / B / C 收口要求

### A 组：优先关注、处理动作与恢复判断（依赖 M5/M6，M1-M4 不实现）

- **A1 优先关注哪个宿舍**
  - 依赖 M5 三节点 Dashboard；能从总览进入对应宿舍详情，Dashboard / 3D 明确知道当前查看的是谁
  - 优先规则（顺序不可改）：① 连续异常时长最长者优先 ② 相同时比异常次数 ③ 仍相同按 nodeId 固定顺序（dorm-a → dorm-b → dorm-c）
  - **连续异常时长必须由程序从历史记录（按 time 分组）计算，禁止人工判断**；结果与原因一起显示，例："优先关注 dorm-b：已连续偏热 20 分钟；dorm-c 虽然偏湿但只持续 5 分钟"
  - 最低完成线：至少 3 组三节点测试数据通过（① 只有 dorm-b 异常 ② dorm-b、dorm-c 都异常且 dorm-b 持续更久 ③ 三节点都异常，验证次数 / nodeId 兜底顺序）
- **A2 发现问题后能做什么**
  - 依赖 A1 与 M5/M6；至少 1 个真实用户操作（如"开启风扇 / 通风"），操作后 Dashboard / 3D 状态一致
  - 动作必须是系统状态的一部分，不能只改按钮文字：内部维护 actionState `{"nodeId":"dorm-b","action":"fan_on","actionTime":"..."}`
  - 与 A3 解耦：A2 只负责"用户做了什么、系统因此改变了什么"，不因点击操作直接把状态改为"已恢复"
  - M1 历史 JSON 已预留 action 字段（第 4 节），避免后期改 JSON 结构
- **A3 恢复判断**
  - 依赖 A2；处理之后用**新数据**判断状态，显示"仍需关注 / 处理中 / 已恢复"；**恢复必须由新数据触发**，不能由点击操作直接改状态

### B 组：程序化说明（事实、重点、依据、摘要）
- **事实、重点、依据、摘要均由程序生成，不手写**；输出内容以生成脚本 / 程序实际输出为准

### C 组：轻量 ML 应用闭环（最后做）
- **C1 数据准备**：复用离线链积累的 CSV，最小特征 temperature / humidity
- **C2 轻量模型**：仅做 IsolationForest（不做正式 ML 训练流程），小数据跑通即可
- **C3 应用落地**：结果接回 report.html 展示
- **C4 闭环说明**：给出简单评估指标、一句话结论与局限说明；**保留 1 个不理想案例**并说明原因

## 10. 技术边界

M1-M6 不要求：
- 数据库（CSV 即存储）
- 真实传感器（全部使用模拟节点）
- LLM / RAG / Agent
- 正式 ML 训练流程

C 只做轻量 ML 应用闭环：小数据、简单模型，跑通"数据 → 模型 → 应用 → 说明"闭环即可，不追求精度指标。

## 11. 最终提交清单

- **代码目录**：web/、analysis/、mobile/、simulator/、dashboard/、three3d/（及 M1 规则实现所在位置）
- **数据与产物**：data/ 下的 CSV、trend.png、report.html
- **文档**：docs/DORMMATE_SPEC.md、docs/PLAN.md、README.md（含 M3 ASR 兜底记录：原因 / 替代方案 / 测试结果）
- **证据**：各阶段完成线对应的截图 / 录屏 / 日志
- **Git**：每阶段至少一次有意义提交；Final 稳定版同步到用户 GitHub 账号的 `nova-dormmate-final-2026` 仓库

## 12. 节点约束

- **M1-M4 可只使用单宿舍**（如 dorm-a）
- **M5 起必须三节点**：dorm-a / dorm-b / dorm-c 同时在线
- **三个节点不能串线**：各自使用独立的 nodeId、数据流（topic / 文件），数据不得互相覆盖、串台

## 13. 统一约定

| # | 约定 | 内容 |
|---|---|---|
| 1 | GitHub 仓库 | 统一命名 `nova-dormmate-final-2026`（任务书 Page 3 & 11 原文拼写）；使用用户自己的 GitHub 账号 |
| 2 | M4 移动端 | 不把 AppID / 真机账号作为最低完成线；微信开发者工具能稳定运行核心页面即可 |
| 3 | M3 ASR | 优先桌面版 Chrome / Edge + localhost；若 SpeechRecognition 因浏览器兼容性或在线识别服务不可用，可改用等价 ASR，并在 README 中记录原因、替代方案与测试结果；不能跳过"识别文字 + 固定指令触发功能" |
| 4 | M5 MQTT | 从 M5 开始在自己的笔记本启动本机 Broker；不要求公网 / 共享 Broker |
| 5 | 不会时怎么做 | 先按"建议检索关键词"查官方文档 / 搜索 / 问 AI，再根据实际报错逐步排查；不等待完整代码或成品教程 |
| 6 | 工具 | Chrome / Edge + VS Code（或熟悉的编辑器），用于 Web、Camera、ASR/TTS、Dashboard、3D；ASR 默认使用桌面版 Chrome / Edge + localhost |
