# DormMate 总计划（MASTER_PLAN）— M1-M6 + A/B/C 联系与执行路线图

> 依据：任务书截图（M6 条目 26-30、A1-A4、B1-B4、C1-C4）+ docs/DORMMATE_SPEC.md + docs/PLAN.md。
> 本文件是 M6 收口之后 A / B / C / Final 阶段的执行依据与全项目联系总览；与 SPEC/PLAN 冲突时以 SPEC 为准。
> 活文档：阶段状态随进度更新；SPEC 是稳定契约（已含 A1-A4 / B1-B4 / C1-C4 细化条款）。

## 1. 文档定位与原则

1. **唯一事实源**：docs/DORMMATE_SPEC.md + docs/PLAN.md；本文件提供 M1-M6 与 A/B/C 的联系矩阵、剩余阶段的详细步骤与验收总表
2. **一次只做一个阶段**：线性执行 A1→A2→A3→A4→B1→B2→B3→B4→C1→C2→C3→C4→Final；截图允许 B 与 A 交叉推进，作为可选优化，启用前须用户同意
3. **每阶段有门禁**：完成线全部满足才算完成，未完成不进下一阶段；每步停下等用户确认
4. **规则零重写**：状态规则一律经现有三端口实现（见 §11）；新功能复用现有校验链 / MQTT 样板 / 报告管线
5. **技术边界不变**：无数据库、无真实传感器、无 LLM/RAG/Agent、无正式 ML 训练流程、不新建后端服务（SPEC §10）

## 2. 全景图：两条数据链 + A 业务闭环 + B 信息闭环 + C 应用闭环

### 2.1 两条必须跑通的数据链（SPEC §2）

| 链 | 数据流 | 状态 |
|---|---|---|
| 离线分析链 | Web(M1) → CSV(M2) → Python(M2) → trend.png / report.html | 已跑通（M1-M2） |
| 实时系统链 | 模拟节点(M5) → MQTT → Dashboard(M5) → 3D(M6) | 已跑通（M5-M6） |

离线链在 A/B/C 阶段继续加长：report.html 依次接入 **A4 事件复盘 → B3 今日摘要 → C3 ML 异常分析** 三个新区块。

### 2.2 A 业务闭环（图 A.1：一次问题怎样从发现走到复盘）

```
发现异常 → 判断优先(A1) → 采取动作(A2) → 验证效果(A3) → 记录复盘(A4)
（dorm-b 连续偏热）（为什么先处理它）（开启风扇/通风）（新数据有没有改善）（事件进入 report.html）
```

- A 不增加新技术：把现有数据、Dashboard、3D 和报告组成一次完整的"发现 → 处理 → 验证 → 复盘"
- 关键点：用户点了"开启风扇"不等于问题已经解决——必须继续接收新数据，再判断"仍需关注 / 处理中 / 已恢复"，最后把整件事留下记录
- 新增动作通道（MQTT）：Dashboard 发布 `dormmate/{nodeId}/action` → three3d 联动（风扇转/窗开）+ simulator 响应（降温趋势）→ 新 env 数据 → A3 恢复判定 → A4 事件 → report.html

### 2.3 B 信息闭环（图 B.1：同一批事实怎样变成更清楚的信息）

```
事实（三节点真实状态）→ 提炼重点（B1 现在最该看谁）→ 说明依据（B2 持续多久/几次异常）
→ 总结过程（B3 今天发生了什么）→ 合适表达（B4 不同入口承担不同信息任务）
```

- B 不新增 LLM/VLM：只用已有真实数据，把"当前重点、判断依据、今日过程"组织成用户能快速看懂的信息
- B4 分工：Dashboard 看当前重点 / 3D 看空间状态 / TTS 读当前提醒 / report.html 看历史复盘（移动端简报为可选扩展）
- 所有摘要、依据和事件必须由程序根据真实数据生成，不能手工写死

### 2.4 C 应用闭环（图 C.1：固定规则和轻量 ML 怎样一起工作）

```
历史数据（模拟，单节点）→ IsolationForest + 固定规则（18/30/75 阈值）双判断
→ 对照结果（固定规则：正常 / ML：与历史明显不同）→ 写回 report.html（可选接 Web/Dashboard）
→ 保留 1 个"判断不太理想"的真实例子
```

- Rule 和 ML 必须并列保留：模型输出只是辅助判断
- 只做一次轻量 ML 应用，重点是把结果接回 DormMate，不要求理解算法推导

## 3. 任务书要求 → 模块/完成线/证据 全映射表

| 来源 | 要求条目 | 对应模块 | 完成线 | 证据 | 状态 |
|---|---|---|---|---|---|
| M1-M5 任务书 | 验收条目（各阶段） | web/ analysis/ mobile/ simulator/ dashboard/ | 各 docs/Mx_PLAN.md 验收清单 | docs/evidence/m1-m5/ | 已完成 |
| M6-26 | 用 Three.js 官方资料/示例/搜索或 AI，自主形成可运行的简化 3D 宿舍 | three3d/ | 场景稳定打开 | docs/evidence/m6/ | 已完成 |
| M6-27 | 场景中至少两个可区分对象；能说明 object、camera、renderer 的基本作用 | three3d/（35+ 对象） | 现场可数、可指认 | docs/evidence/m6/ | 已完成 |
| M6-28 | 至少 3 组 DormMate 状态让某个 3D 对象产生明显可见变化 | three3d/（4 类：主色/指示球/粒子/标牌） | 四状态逐一打出 | docs/evidence/m6/ | 已完成 |
| M6-29 | 把 MQTT/实时状态接入 3D：至少一个模拟节点消息驱动 3D 变化 | three3d/ handleMessage→updateScene | MQTTX 手发一条即变 | docs/evidence/m6/ | 已完成 |
| M6-30 | 1 个自主有用改进 + 记录 1 个真实 Bug 及修复 | three3d/（Edge 鼠标手势防御等） | 改进理由 + 2-3 组数据验证 + Bug 记录 | docs/evidence/m6/ | 已完成 |
| A1 | 哪个宿舍现在最值得关注：优先规则（连续异常时长→异常次数→nodeId 顺序）+ 可解释原因 + 总览进详情 + Dashboard/3D 明确当前节点 | dashboard/ + three3d/ | ≥3 组三节点测试数据通过；时长由程序计算禁人工 | docs/evidence/a1/ | 已完成 |
| A2 | 发现问题后能做什么：≥1 真实用户操作（开启风扇/通风），动作成为系统状态，Dashboard/3D 状态一致 | dashboard/ + three3d/ + simulator/ | 操作后内部状态、Dashboard、3D 一致；能说明"用户做了什么、系统因此改变了什么" | docs/evidence/a2/ | 已完成 |
| A3 | 我处理以后真的变好了吗："仍需关注/处理中/已恢复"；恢复必须由新数据触发，不能按钮直改 | dashboard/ + simulator/ | ≥1 次"异常→措施→≥2 组新数据→判断"完整反馈过程 | docs/evidence/a3/ | 已完成 |
| A4 | 能不能把一次问题完整留下来并复盘：事件字段齐全 + 进入 report.html"事件复盘"区 | dashboard/ + analysis/ | ≥1 条完整事件；能重新讲清"发现→判断→处理→验证→恢复" | docs/evidence/a4/ | 已完成 |
| B1 | 现在发生了什么：程序根据三节点真实状态自动形成"当前总览" | dashboard/ | 状态变化总览自动变；节点/状态/重点可回到真实数据；不写死 | docs/evidence/b/ | 未开始 |
| B2 | 为什么值得关注：依据（持续时间/异常次数/当前状态）讲清，能指出依据来自哪里 | dashboard/ | ≥3 组三节点情况；优先对象与依据合理变化 | docs/evidence/b/ | 未开始 |
| B3 | 今天发生了什么：程序自动生成"今日摘要"（谁出问题/做了什么/结果） | analysis/ + report.html | ≥2 事件模拟日数据；换数据摘要必须重新生成 | docs/evidence/b/ | 未开始 |
| B4 | 这些信息应该放在哪里：≥3 类表达方式承担不同信息任务，能说明放置理由 | dashboard/ 3D/ TTS/ report.html | 核心四类分工落地 + 分工说明；不复制同一段文字 | docs/evidence/b/ | 未开始 |
| C1 | 先让模型认识"平时"：单节点 30-50 条模拟历史；历史与新数据分开；random_state 固定可复现 | analysis/ + data/ | 换新历史 CSV 能重跑；README 写清"模拟"与数据来源 | docs/evidence/c/ | 未开始 |
| C2 | 固定规则没发现的 ML 能不能发现：多组新数据双判断对照 | analysis/ | 对照结果保留；不一致保留 ≥1 组解释，未出现如实记录；不调参不伪造 | docs/evidence/c/ | 未开始 |
| C3 | 不要停在 Python：结果接回 report.html"ML 异常分析"（当前值/固定规则/ML 判断并排） | analysis/ + report.html | 换新 CSV 重新生成 ML 结果并与固定规则并排 | docs/evidence/c/ | 未开始 |
| C4 | ML 会不会也判断不好：保留 ≥1 个不理想例子（数据+模型结果+可能原因） | README + report.html | 例子与原因落地；做到 C4 完成 C 闭环 | docs/evidence/c/ | 未开始 |
| Final | 关闭重启验证 + 稳定版同步 GitHub | 全部 | 重启后两条链 + A/B/C 闭环复验通过 | docs/evidence/final/ | 未开始 |

## 4. M1-M6 ↔ A/B/C 联系矩阵

| 阶段 | 给什么（现有资产，锚定代码位置） | 接什么（A/B/C 依赖） |
|---|---|---|
| M1 | `window.computeStatus/ADVICE/validateInputs`（web/script.js:6-51、159-168）被 dashboard/three3d 直接引入复用；历史 JSON 的 action 预留字段（web/script.js:102）；TTS 实现模式（web/script.js:268-306） | A2 写入 action；A/B 全部 status 计算零重写；B4 Dashboard 朗读提醒复用 TTS 模式 |
| M2 | analysis/analyze.py：`compute_status/load_csv/compute_stats/render_report`（line 39/71/103/178）；report.html 模板含 C3 扩展点注释（line 232）；data/ 下 CSV + trend.png | A4"事件复盘"区、B3"今日摘要"区、C3"ML 异常分析"区都挂在 render_report 管线；C1 复用 CSV |
| M3 | Git/GitHub 机制（nova remote + subtree push）；README 结构；ASR"等价替代"先例（SPEC §13-3） | A/B/C/Final 每阶段提交与 Final 同步沿用；README 记录 A3 恢复规则、B4 分工说明、C1 数据来源与模拟标记、C4 不理想案例；C2 sklearn 失败时自实现兜底同款记录 |
| M4 | mobile/utils/rules.js 同规则端口（与 web/script.js 逐行对齐） | 与 A/B/C 无直接接口；B4 移动端三节点简报为可选扩展（不纳入最低完成线） |
| M5 | simulator/simulate.py 三节点发布 dormmate/{nodeId}/env（line 45-83）；dashboard/app.js 每节点 latest/history（line 21-24）、校验链（line 98-181）、MQTT 样板（line 203-224） | A1 数据源与连续异常时长计算；B1/B2 依据计算；action 消息走同款校验链；simulator 订阅 action → 降温 → A3 新数据 |
| M6 | three3d/app.js：selectedNodeId + 点击选中（line 26、413-459）= "3D 明确知道当前看谁"；fanBlades 风扇挂点（line 221-239）；STATUS_STYLE 四状态视觉（line 18-23）；updateScene 唯一入口（line 338-369） | A1 3D 侧"当前查看的宿舍"；A2 风扇转动/窗开挂点；A3 恢复后 3D 自动回正常（数据驱动，零改动）；B4 3D 角色零改动 |
| A1→B1/B2 | computeStreak/computePriority 纯函数与三节点 streak 数据 | B1 总览的"当前重点"、B2 依据明细直接复用，零重写 |
| A2/A3→B4 | Dashboard 处理状态显示"dorm-b \| 处理中 温度正在下降" | B4 Dashboard 角色内容 |
| A4→B3 | 事件记录 data/events.json | 今日摘要的输入 |
| M2/A4/B3→C | CSV + report.html 管线 | C1 数据源、C3 落点；C3 进阶（可选）接 web/Dashboard 用 JSON/结果文件，不新增后端 |

## 5. 阶段路线图与依赖

```
M6 看板收口 → A1 → A2 → A3 → A4 → B1 → B2 → B3 → B4 → C1 → C2 → C3 → C4 → Final
                └─ B1/B2 只依赖 A1；B3 依赖 A4（截图允许 B 与 A 交叉，本项目默认线性，交叉须用户同意）
```

- C 严格最后（SPEC §10）；Final 在 A/B/C 全部完成之后
- 当前状态：M1-M6 已完成；A 组（A1-A4）已完成（提交 d0da90d、a88ca0c、2b96f8d、78b7e37、08952d2、c92ede4，证据 docs/evidence/a1-a4/）；B/C 未开始

## 6. 统一契约扩展（执行时与 SPEC 对齐）

### 6.1 actionState JSON（A2 起，SPEC §4 action 字段的落点）

```json
{"nodeId":"dorm-b","action":"fan_on","actionTime":"2026-09-28 20:45:00"}
```

- topic：`dormmate/{nodeId}/action`（QoS 0，本机 Broker 同 M5）；动作值：`fan_on` / `fan_off`
- 校验同款 topic↔nodeId 串线防线（dashboard/app.js:98-181 同款）：JSON.parse 容错 → 对象守卫 → nodeId 字符串 → topic 第二段 == nodeId → action ∈ {fan_on, fan_off}，否则丢弃+计数
- 节点下一条 env 消息的 record.action 写入当前动作值（如 "fan_on"），M1-M4 恒空不变

### 6.2 事件记录 JSON（A4）

```json
{"nodeId":"dorm-b","startTime":"2026-09-28 20:30:00","problem":"偏热",
 "priorityReason":"连续异常时长最长(20分钟)","action":"fan_on",
 "actionTime":"2026-09-28 20:45:00","recoverTime":"2026-09-28 21:10:00",
 "result":"已恢复","summary":"20:30 dorm-b 连续偏热 → 20:35 优先关注 dorm-b → 20:45 开启风扇并通风 → 20:55 温度开始下降 → 21:10 恢复正常"}
```

- 存放：data/events.json（数组）；summary 由程序拼接，禁手写
- result 取值：已恢复 / 仍需关注（未恢复）

### 6.3 A3 恢复状态机（每节点）

```
idle ──(动作)──> processing(actionTime, normalStreak=0) ──(新数据 status==正常)──> normalStreak+1
                    └──(新数据 status!=正常)──> normalStreak=0，保持"处理中"
processing ──(normalStreak>=2)──> recovered(recoverTime) → 发布 fan_off
```

- 恢复规则：**连续 ≥2 条新数据 status==正常 才判"已恢复"**（比统一规则更严格，README 写清，SPEC §9 A3）
- 三态显示：仍需关注 / 处理中 / 已恢复；状态机只由新 env 数据推进，按钮只发动作

### 6.4 A1 优先规则（程序计算，禁人工）

1. 连续异常时长（按 time 分组：最新记录 time − 异常链起点 time，单位分钟）降序
2. 相同时比异常次数（该节点历史中 status != 正常的条数）降序
3. 仍相同按 nodeId 固定顺序：dorm-a → dorm-b → dorm-c

原因文案由程序拼接，例："优先关注 dorm-b：已连续偏热 20 分钟；dorm-c 虽然偏湿但只持续 5 分钟"

### 6.5 B 组信息生成契约

- **B1 总览模板**（程序拼接，禁写死）："当前 3 个宿舍中，{正常数} 个正常，{异常数} 个需要关注；{重点节点描述}，{其余异常描述}"
- **B2 依据明细**：每节点列出 连续异常时长 / 异常次数 / 当前状态 三项，每项附数据来源（如"依据：dorm-b 最近 12 条记录（20:10-20:30）连续偏热，时长 20 分钟"）
- **B3 今日摘要**：Python 读 data/*.csv + data/events.json 生成，落 report.html 摘要区；≥2 事件的模拟日数据由生成脚本产出；换数据必须重新生成

### 6.6 C 组 ML 契约

- 单节点（dorm-a）；历史 CSV（data/c_history.csv，30-50 条模拟记录）与待判断新数据 CSV（data/c_new.csv）**分开存放、严禁混入**
- **random_state=42 固定**：同一份数据重复运行结果可复现；换新历史 CSV 能重跑
- IsolationForest 参数：n_estimators=100、contamination="auto"；predict 返回 1=接近历史常态、-1=与历史明显不同（截图 58 最小代码路线）
- sklearn 优先（pip install 前征得用户同意）；安装失败 → 纯 Python 自实现同参数版本（README 记录替代原因）
- C2 对照若未出现"规则正常、ML 明显不同"，**如实记录"本次测试未出现"并说明观察**，禁止调参凑结果或手工改模型输出
- C3 输出三列并排：当前值 / 固定规则状态 / ML 判断；不做 Label、Train/Test、Accuracy/F1、混淆矩阵、模型版本管理、正式模型服务或系统调参

## 7. 各阶段详细执行步骤

### 7.1 M1-M5 已完成回顾（现状/产物/证据/交接）

| 阶段 | 现状与关键产物 | 证据 | 交接接口 |
|---|---|---|---|
| M1 | web/ 三文件 + test.html；统一规则源 window.computeStatus/ADVICE/validateInputs；历史 JSON 含 action 预留 | docs/evidence/m1/ | 全部 JS 页面复用规则，禁止各自重写 |
| M2 | analysis/analyze.py + data/dormmate*.csv + trend.png + report.html（C3 扩展点注释在模板 line 232） | docs/evidence/m2/ | A4/B3/C3 都挂在 render_report 管线 |
| M3 | Camera/等价 ASR/TTS + README + Git/GitHub（nova remote） | docs/evidence/m3/ | README 继续补 A/B/C 记录；提交机制沿用 |
| M4 | mobile/ 小程序（rules.js 同规则端口，单宿舍） | 截图待用户补拍 docs/evidence/m4/ | 与 A/B/C 无直接接口 |
| M5 | simulator/simulate.py + dashboard/（三节点同屏、校验链、趋势） | docs/evidence/m5/ | A1/B1/B2 数据源；校验链与 MQTT 样板复用 |
| M6 | three3d/（S0-S6 完成：静态场景/状态映射/MQTT 驱动/评审修复） | docs/evidence/m6/ | fanBlades、selectedNodeId 挂点交 A 组 |

### 7.2 M6 收口

- PLAN.md 看板：M6 状态 → 已完成（代码/证据/提交已齐：415c9db、7e72183、8fb68a4；GitHub 已同步 44b391c）
- 交接摘要按 PLAN 第 6 节模板补记；M6_PLAN.md §9 遗留项（演示记录混入 history）已列入 A S2 处理

### 7.3 A 组：优先关注、处理动作、恢复判断与事件复盘（A1-A4）

**S0 文档对齐** ✅ 已完成（2026-09-28：SPEC §9 A 组更新为 A1-A4，diff 经用户确认）。执行时建证据目录 docs/evidence/a1/-a4/。

**S1 simulator 动作响应**（simulator/simulate.py）
- 新增订阅 `dormmate/+/action`（与发布共用客户端）；动作消息校验：JSON 容错 → nodeId 字段 → topic 第二段 == nodeId → action ∈ {fan_on, fan_off}
- 每节点 fan 状态：fan_on → 随机游走步进偏差改为 温度 −0.4（随机区间约 −0.7~−0.1）、湿度 −0.5；fan_off → 恢复原 ±1.5/±4.0
- 温度保护：降至 ≤26℃ 自动 fan_off（模拟温控停机，避免过度降温产生"偏冷"假异常）；参数常量化可调，README 说明为模拟行为
- 验证点：MQTTX 手发 fan_on → 控制台显示动作生效、该节点 env 数据持续下降；fan_off → 恢复随机游走；--selftest 不受影响

**S2 A1 优先关注**（dashboard/ + three3d/）
- 新建 dashboard/priority.js（纯函数，零 DOM，挂 window）：`computeStreak(history)` → {durationMinutes, abnormalCount, statusType, startTime, endTime}（从最新往回走连续 status != 正常的链）；`computePriority(nodes)` → {nodeId, reason}（§6.4 规则）
- dashboard/index.html 引入 priority.js；顶部新增"优先关注"横幅（每条消息后自动刷新，原因文案程序拼接）
- 新建 dashboard/test-priority.html：web/test.html 同款模式，3 组三节点数据断言（① 只有 dorm-b 异常 ② dorm-b、dorm-c 都异常且 b 更久 ③ 三节点都异常，验证次数/nodeId 兜底顺序）
- simulator/test_a1.py：paho 脚本按剧本发布带可控 time 的预设序列，现场演示 + 截图
- three3d 遗留修复：applyDemoRecord 记录加 demo 标记，A1 计算排除演示记录（M6_PLAN §9 遗留）
- 验证点：横幅出现且原因正确；3 组测试数据断言全过；点击横幅/卡片能进入对应宿舍详情，Dashboard/3D 明确当前查看的节点

**S3 A2 动作入口**（dashboard/）
- 详情面板（选中节点后）新增"开启风扇/通风"按钮 → 构造 actionState（§6.1）→ publish `dormmate/{nodeId}/action` → 本地 nodes[nodeId].actionState 记录 → 卡片显示"处理中 | 风扇已开启"
- 下一条该节点 env 消息：record.action = "fan_on"（SPEC §4）
- 与 A3 解耦：只记录"用户做了什么、系统因此改变了什么"，不因点击直接把状态改为已恢复

**S4 three3d 动作联动**（three3d/）
- 新增订阅 `dormmate/+/action`（校验链与 S1 同款）→ actionState[nodeId] 更新 → `setDormAction(nodeId, action)`：fan_on → fanBlades 在 animate 中 rotation.y 持续转动 + 窗 mesh 开启（rotation 过渡）；fan_off → 停止/关窗
- updateScene 放开 action 硬编码 ""（three3d/app.js:355）→ record.action = actionState[nodeId]?.action ?? ""
- 侧栏显示动作状态（"风扇运行中"）
- 验证点：Dashboard 点按钮 → 3D 风扇转、窗开；两页面并排一致（截图/录屏）

**S5 A3 恢复判断**（dashboard/ + simulator/）
- dashboard/app.js 每节点恢复状态机（§6.3）；卡片三态显示"仍需关注 / 处理中 / 已恢复"；恢复时自动发布 fan_off
- 演示剧本：dorm-b 32/82（偏热）→ 点击开启风扇 → 卡片"处理中 | 风扇已开启"→ simulator 降温 → 新数据 30/76（仍偏热 → 保持处理中）→ 27/65（正常 #1）→ 26/62（正常 #2）→ "已恢复" + fan_off → 录屏
- README 记录恢复规则（连续 ≥2 条正常，比统一规则严格，SPEC §9 A3）

**S6 A4 事件复盘**（dashboard/ + analysis/）
- dashboard：事件跟踪（异常起点 + 优先原因 + 动作 + 恢复 → 组装 eventRecord §6.2）→"今日事件"面板显示 → "导出 events.json"按钮（downloadCsv 同款模式，UTF-8）→ 存入 data/events.json
- analysis/analyze.py：新增 `load_events(path)`（文件缺失容错为空列表）→ render_report 增加"事件复盘"section（事件表格 + summary 复盘文本）
- 完整故事演示：dorm-b 偏热 → 优先关注 → 开风扇 → 降温 → 恢复 → 导出 events.json → python analysis/analyze.py → report.html 出现事件复盘（截图）

**S7 A 组验收交接** ✅ 已完成（2026-09-29：A1-A4 逐条对照 SPEC §9 与截图完成线全过；README 补 A 组运行方式（演示剧本 ①-⑥）；PLAN/MASTER_PLAN 状态列更新；提交与 GitHub 同步待用户确认）

### 7.4 B 组：把已有信息讲清楚（B1-B4）

**S0 文档对齐** ✅ 已完成（2026-09-28：SPEC §9 B 组扩展为 B1-B4，diff 经用户确认）。执行时建 docs/evidence/b/。

**S1 B1 当前总览**（dashboard/priority.js）
- `buildOverview(nodes)` 纯函数：输入每节点 {latest, streak} → 输出总览句子（§6.5 模板）；Dashboard 顶部"当前总览"条，每条消息后自动更新
- 验证点：MQTTX 改变节点状态 → 总览自动变化；节点/状态/重点能回到当前真实数据（截图 2-3 张不同时刻，不写死）

**S2 B2 判断依据**（dashboard/）
- Dashboard"优先级 + 依据"卡片：每节点三指标（连续异常时长/异常次数/当前状态）+ 优先节点原因标注；每项依据附来源（历史记录时间范围，§6.5）
- simulator/test_b2.py：3 组三节点情况（时长/次数/状态各不相同）→ 优先对象与依据合理变化 → 截图 + 现场指认依据来源

**S3 B3 今日摘要**（analysis/）
- analysis/make_day_data.py：程序生成 ≥2 事件的模拟日数据（参数可控/seed，两次不同参数产出两份不同数据，写入 data/sim-day-N/：每节点 CSV + events.json）
- analysis/daily_summary.py：读 CSV + events.json → 生成今日摘要文本（模板见 SPEC §9 B3 例句）→ 输出控制台 + 写入 report.html 摘要区（并入 analyze.py 管线）
- 验证点：两份模拟日数据两次运行 → 摘要不同、全部程序生成（截图对照）；不手工修改文字

**S4 B4 信息分工**（dashboard/ + README）
- Dashboard 新增"朗读提醒"按钮：window.speechSynthesis 朗读 B1 当前总览/提醒文本（复用 web/script.js:268-306 TTS 模式）
- 分工说明表（README + 本文档 §2.3）：Dashboard 当前重点 / 3D 空间状态 / TTS 当前提醒 / report.html 历史复盘——每行写明"为什么这条信息适合放在这里"
- 验证点：四类分工演示截图；能现场说明放置理由

**S5 B 组验收交接**
- 逐条对照 SPEC §9 B1-B4 与截图完成线（§3 表）；证据 docs/evidence/b/；README 补 B 组说明
- 提交 + GitHub 同步（先展示变更摘要/命令，用户确认）

### 7.5 C 组：从历史数据中发现异常（C1-C4，最后做）

**S0 文档对齐** ✅ 已完成（2026-09-28：SPEC §9 C 组细化为截图口径，diff 经用户确认）。执行时建 docs/evidence/c/。

**S1 数据准备 C1**（data/ + analysis/）
- analysis/make_c_data.py：生成 data/c_history.csv（dorm-a 30-50 条模拟历史，可延续现有 dormmate.csv）+ data/c_new.csv（多组待判断新数据，含若干"规则正常但与历史不同"的候选如 29℃/72%）；两份严格分开；生成脚本标记"模拟"
- README/报告写清"模拟"标记与两份数据分别来自哪里；换新历史 CSV 可重跑

**S2 模型与对照 C2**（analysis/c_ml.py）
- 优先 sklearn：pip install scikit-learn（**先征得用户同意**）→ `IsolationForest(n_estimators=100, contamination="auto", random_state=42).fit(X_history)` → `predict(X_new)`；安装失败 → 纯 Python 自实现同参数版本（README 记录替代原因，沿用 M3 ASR 等价替代先例）
- 固定规则列用现有 compute_status（analysis/analyze.py:39，零重写）→ 对照表输出控制台 + data/c_compare.json（当前值/固定规则状态/ML 判定）
- 寻找"规则正常、ML 判明显不同"案例并用自己的话解释；**未出现则如实记录"本次测试未出现"并说明观察**，不调参、不伪造、不改模型输出

**S3 结果接回 C3**（analysis/ + report.html）
- analyze.py render_report 扩展：新增"ML 异常分析"section，三列并排行（"dorm-a | 29℃/72% | 固定规则：正常 | ML：与历史状态明显不同"），数据来自 c_compare.json（C3 扩展点注释 line 232 处落位）
- 验证点：换一份新 CSV → report.html 重新生成 ML 结果并与固定规则并排（截图）
- 进阶（可选，不纳入最低完成线）：c_compare.json 由 dashboard 经 Live Server fetch 展示，不新建后端

**S4 不理想案例 C4**（README + report.html）
- 从实际运行结果中找 1 个"判断不太理想"的例子（如历史太少把普通数据标异常），保留当时数据 + 模型输出，用自己的话说明可能原因（历史太少/过去太单一/数据本身有问题/环境模式已变）
- 写入 README 或 report.html；不做 Label/Train/Test/Accuracy/F1/混淆矩阵/模型版本管理/调参

**S5 C 组验收交接**
- 逐条对照 SPEC §9 C1-C4 与截图完成线（§3 表）；证据 docs/evidence/c/；README 补 C 组说明
- 提交 + GitHub 同步（先展示变更摘要/命令，用户确认）

### 7.6 Final 关闭重启验证 + 稳定版

- 关闭所有进程（Mosquitto / simulator / Live Server / 微信开发者工具）→ 按 README 顺序重启：
  1. 离线链复跑：Web 录入 → 导出 CSV → `python analysis/analyze.py` → trend.png + report.html（含事件复盘/今日摘要/ML 异常分析三区）
  2. 实时链复跑：Broker → simulator → Dashboard + 3D 并排（三节点不串线）
  3. A 闭环重演：偏热 → 优先关注 → 开风扇 → 降温 → 已恢复 → 事件复盘
  4. B 信息闭环演示：总览/依据/今日摘要/四类分工
  5. C 对照复现：同数据同 random_state=42 → 同结果
- 复验截图/录屏 → docs/evidence/final/；稳定版同步用户 GitHub 账号 `nova-dormmate-final-2026` 仓库（先展示命令，用户确认）

## 8. 风险与红线

| 风险 | 对策 |
|---|---|
| action 消息串线（topic↔nodeId 不符） | 同款串线防线（§6.1），丢弃+计数+横幅 |
| 恢复被按钮误触 | A3 状态机只由新 env 数据推进；按钮只发动作（§6.3） |
| three3d 演示记录污染 A1 历史（M6 遗留） | A S2 demo 标记并在 A1 计算排除 |
| 总览/摘要写死 | B1/B3 完成线要求换数据自动变化，演示两次数据对照 |
| events.json/模拟日数据手改冒充程序生成 | 一律由生成脚本产出，换数据重生成留证 |
| 降温模拟过度 → 产生偏冷假异常 | simulator ≤26℃ 自动 fan_off（§7.3 S1） |
| Dashboard 刷新丢内存态（actionState/事件/streak） | 演示剧本一气呵成 + README 记录限制（可选 localStorage 持久化） |
| sklearn 在 Python 3.14 无 wheel/安装失败 | 自实现兜底（README 记录）；pip install 前征得用户同意 |
| C2 为凑"规则正常 ML 不同"而调参 | 完成线明令禁止；未出现则如实记录 |
| 阶段间规则漂移 | 规则零重写（§11）；SPEC §6 四组回归随阶段复跑 |

## 9. 验收总表（截图条目逐条可勾）

| # | 条目（截图原文口径） | 完成线 | 证据 | 状态 |
|---|---|---|---|---|
| M6-26 | 自主形成可运行简化 3D 宿舍 | 场景稳定打开 | evidence/m6/ | ☑ |
| M6-27 | ≥2 对象；说明 object/camera/renderer | 现场指认 | evidence/m6/ | ☑ |
| M6-28 | ≥3 组状态可见变化 | 四状态逐一打出 | evidence/m6/ | ☑ |
| M6-29 | ≥1 条 MQTT 消息驱动 3D | MQTTX 手发即变 | evidence/m6/ | ☑ |
| M6-30 | 1 个自主改进 + 1 个真实 Bug 修复 | 理由+验证+Bug 记录 | evidence/m6/ | ☑ |
| A1 | 优先规则 + 可解释原因 + 总览进详情 | 3 组三节点数据；程序计算 | evidence/a1/ | ☑ |
| A2 | ≥1 真实操作；Dashboard/3D 一致 | 动作成系统状态 | evidence/a2/ | ☑ |
| A3 | 恢复由新数据触发；三态显示 | ≥1 次完整反馈（≥2 组新数据） | evidence/a3/ | ☑ |
| A4 | 完整事件记录进 report.html | ≥1 条完整事件可复盘 | evidence/a4/ | ☑ |
| B1 | 程序自动生成当前总览 | 状态变化自动变；不写死 | evidence/b/ | ☐ |
| B2 | 依据讲清 + 来源可指 | 3 组情况合理变化 | evidence/b/ | ☐ |
| B3 | 程序自动生成今日摘要 | ≥2 事件；换数据重生成 | evidence/b/ | ☐ |
| B4 | ≥3 类表达方式分工（做 4 类） | 分工落地 + 说明理由 | evidence/b/ | ☐ |
| C1 | 单节点模拟历史；数据分离；可复现 | 换 CSV 重跑；来源写清 | evidence/c/ | ☐ |
| C2 | 固定规则/ML 对照 | 对照保留；不一致解释或如实记录 | evidence/c/ | ☐ |
| C3 | ML 结果接回 report.html 并排 | 换 CSV 重新生成 | evidence/c/ | ☐ |
| C4 | ≥1 个不理想案例 + 原因 | README/report 落地 | evidence/c/ | ☐ |
| Final | 关闭重启复验 + GitHub 同步 | 两链 + A/B/C 闭环复验通过 | evidence/final/ | ☐ |

## 10. 现场演示剧本索引（执行到对应阶段时细化）

- **A 组**：三节点在线 → dorm-b 偏热持续 → 优先关注横幅 → 进入详情 → 开风扇 → Dashboard/3D 同步 → 新数据降温 → 已恢复 → 导出 events.json → report.html 事件复盘（完整故事，录屏）
- **B 组**：总览自动变化（3 组情况）→ 依据卡片指认来源 → 两份模拟日数据两次生成今日摘要 → 四类分工演示 + 朗读提醒
- **C 组**：c_history 训练 → c_new 对照表（含"规则正常、ML 明显不同"行或"本次测试未出现"记录）→ report.html ML 异常分析区 → 不理想案例指认

## 11. 关键复用清单（不重写）

| 能力 | 复用位置 |
|---|---|
| 状态规则（JS） | window.computeStatus / ADVICE / validateInputs（web/script.js:6-51、159-168） |
| 状态规则（Python） | compute_status（analysis/analyze.py:39，simulator 已复用） |
| 状态规则（小程序） | mobile/utils/rules.js（逐行对齐端口） |
| MQTT 校验链 | dashboard/app.js:98-181 同款（env 与 action 消息共用） |
| MQTT 客户端样板 | dashboard/app.js:203-224 / three3d/app.js:583-608 |
| 报告管线 | analysis/analyze.py load_csv/compute_stats/render_report + C3 扩展点注释（line 232） |
| TTS 模式 | web/script.js:268-306 → B4 Dashboard 朗读提醒 |
| 测试页模式 | web/test.html → dashboard/test-priority.html |
| 演示发布脚本 | simulator/simulate.py（paho-mqtt）→ test_a1.py / test_b2.py |
| 下载导出模式 | web/script.js downloadCsv（UTF-8 BOM）→ events.json 导出 |

## 12. 文档维护与 Git 策略

- 本文件是活文档：每阶段结束更新 §3/§9 状态列；SPEC 变更仍须用户确认
- 每阶段至少一次有意义 Commit（产物+证据），提交前先展示变更摘要；不自动 commit/push
- Final 稳定版同步用户 GitHub 账号 `nova-dormmate-final-2026` 仓库（任务书原文拼写）
- 每阶段结束按 PLAN 第 6 节模板输出交接摘要；README 随 A/B/C 进度同步补充
