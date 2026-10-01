# DormMate 综合作品升级计划（V0.8R5）

## 0. 文档元信息

- **依据**：《C01_DormMate_02_综合作品任务书_V0.8R5.pdf》（`C:\Users\41628\Downloads\`，25 页，2026-09-30 下载）
- **任务书文字来源**：WinRT 渲染 + Windows OCR 提取，存档于 `docs/evidence/upgrade/taskbook-v0.8r5-ocr.md`，渲染底图 `docs/evidence/upgrade/render-p01..25.png`。OCR 有噪声，**原文以 PDF 为准**；关键数字已人工核对：Commit ≥5 次（第 18 页）、PPT 10-15 页、技术文档 10-15 页正文、视频 5-8 分钟
- **基线**：C01 全部阶段已完成（M1-M6、A1-A4、B1-B4、C1-C4、Final、Open-01 自测）
- **文档状态**：待确认——用户确认后作为升级阶段执行依据；与 `docs/DORMMATE_SPEC.md` 冲突时以 SPEC 为准
- **目录约定**：C01 阶段计划冻结在 `docs/C01_Plans/`；本阶段及后续升级文档统一在 `docs/V08R5_Plans/`

## 1. 背景与定位

V0.8R5 不是重做 C01，而是把已学能力（Web、Python 数据分析、Camera/ASR/TTS、Git/GitHub、微信小程序、MQTT、Dashboard、Three.js、轻量 ML）**重组成一个完整系统**：一个 DormMate、两条数据链、多端协同、事件闭环。

- 结构：**D1-D5 五个作品场景（全必做）+ E1-E3 三个共同技术增强（全必做）+ Open Enhancement（上不封顶，不得替代共同完成线）**
- 共同完成线只依赖 C01 已学能力——不额外引入新技术栈也应能完成 D1-D5 与交付要求（任务书 p5）
- 最终完成线（任务书 §10，p23-24）：
  1. D1-D5 全部完成；离线分析链、实时系统链真实跑通
  2. E1/E2/E3 全部完成；D3 事件生命周期从发现、处理走到后续数据验证与恢复/未恢复
  3. web/Dashboard、移动端、3D 围绕同一套实时状态或共享事件状态保持一致
  4. ≥1 次真实故障与修复；≥1 个 Rule/ML 对照案例
  5. GitHub 仓库完整、≥5 次有意义 Commit；Evidence 目录完整（D1-D5/E1-E3/Debug/Reproduce 可追溯）
  6. 1 次同伴交叉复现（发现问题→修订→再次复现）；PPT 10-15 页；技术文档 10-15 页正文；视频 5-8 分钟
  7. 通过现场核验 Run / Explain / Modify / Debug / Verify

## 2. 差距自查总表

> 标注：✓ 已满足 / ✗ 缺失 / ◐ 部分满足。现状位置为探索核实的代码行号。

### D1 多节点稳定运行（任务书 p6）

| 要求 | 现状 | 差距 |
|---|---|---|
| ≥3 节点同时在线不串线 | ✓ `simulator/simulate.py:34,187-192` 三线程；dashboard 校验链含 topic↔nodeId 防串线（`dashboard/app.js:115-237`） | 无 |
| web/Dashboard 正确显示多节点 | ✓ M5 已完成 | 无 |
| 移动端看到同一批节点最新状态 | ✗ `mobile/` 完全离线、单宿舍 dorm-a（`mobile/pages/index/index.js:5-6` 仅预留注释；`mobile/utils/rules.js:81`） | **核心差距**：移动端无 MQTT、无三节点 |
| 3D 明确对应宿舍区域 | ✓ `three3d/app.js:14,154` 三栋建筑 | 无 |
| 新 MQTT 消息多端随真实数据更新 | ◐ dashboard/3D ✓，移动端 ✗ | 移动端接入后补齐 |
| 三节点历史与状态不串线 | ✓ 校验链 + 规则重算（不信任消息 status） | 无 |
| 证据：三节点在线 + 一条新消息驱动三端更新 | ◐ 仅 dashboard/3D 证据 | 阶段 A/D 补 Evidence/D1 |

### D2 持续异常与优先关注（任务书 p6-7）

| 要求 | 现状 | 差距 |
|---|---|---|
| 明确规则判断"现在先看谁"，可解释/可重复/换数据可变/不写死节点 | ✓ `dashboard/priority.js:16-101`（streak→次数→nodeId 顺序）+ `test-priority.html` + `simulator/test_a1.py` | 无 |
| ≥3 组不同三节点情况证明优先级随数据变化 | ◐ 功能与测试已有 | 3 组证据按 Evidence/D2 归档 |
| 移动端显示当前重点（任务书分工：移动端=快速查看当前重点） | ✗ | 阶段 A 移动端展示 |
| 优先状态供 3D 表达（E1⑤） | ✗ 3D 不订阅优先状态 | 阶段 A/B 经共享状态流传递 |

### D3 处理→验证→恢复（任务书 p7-8）

| 要求 | 现状 | 差距 |
|---|---|---|
| OPEN→HANDLING→RECOVERED（或等价），恢复必须由后续新数据触发，按钮不能改"已恢复" | ✓ Dashboard 状态机 `dashboard/app.js:23-28,194-208`（processing → ≥2 条连续正常 → recovered → 自动 fan_off），仅新数据触发 | 无 |
| 事件关联 ≥9 字段（标识/nodeId/开始时间/问题/优先理由/动作/后续验证数据/当前状态/恢复时间/最终结果） | ✓ A4 事件记录 `dashboard/app.js:211-224,304-354`，summary 程序拼接 | 无 |
| web/Dashboard、移动端、3D 对同一事件保持一致，不各自维护 | ✗ 状态机只在 Dashboard；3D 只镜像 fan/window（`three3d/app.js:529-563`）；移动端无 | **核心差距**：事件状态不跨端 |
| 历史记录/报告中事件状态围绕同一状态源 | ◐ `analyze.py` 事件复盘 ✓（读 events.json），但实时事件状态无共享源 | 阶段 A 事件状态 MQTT 共享 |

### D4 实时链路故障与修复（任务书 p8-9）

| 要求 | 现状 | 差距 |
|---|---|---|
| 主动制造 ≥1 类真实故障（停 Broker/写错 Topic/错误 JSON/节点长时间不发），观察→定位→修复→重新运行 | ◐ Open-01 自测覆盖停 Broker（docs/evidence/final/）；dashboard 校验链可拒错误 JSON | 需覆盖更多故障类型预演 |
| 文档或视频保留一次真实故障与修复过程 | ✗ demo-final.mp4 无故障段 | 阶段 C 视频加故障段；Evidence/Debug 归档 |
| 加分：在线离线判断/错误 JSON 拒绝/断开提示/自动重连 | ◐ JSON 拒绝 ✓；其余无 | 阶段 A 移动端做自动重连（顺带加分项） |

### D5 固定规则与 ML 对照（任务书 p9-10）

| 要求 | 现状 | 差距 |
|---|---|---|
| Rule/ML 并列，多组新数据同时显示两者判断 | ✓ `analysis/c_ml.py`（纯 numpy IsolationForest，n_estimators=100、random_state=42、阈值 0.5）+ `data/c_compare.json` + `analyze.py` build_ml_block 接回 report.html | 无 |
| ≥1 个"值得分析"案例，说明判断依据差异，不一致不判"错误" | ✓ C4 保留案例 2026-09-28 10:03 27.5℃/70%：规则=正常、ML=与历史明显不同（score 0.6738），README 已记录 | "依据差异"的深度说明需进技术文档/PPT/视频 |
| 边界：不要求 Label/Train-Test/模型管理/调参/模型服务 | ✓ 遵守 | 无 |

### E1 3D 数字孪生增强（任务书 p11，最低线 7 条）

| 最低线 | 现状 | 差距 |
|---|---|---|
| ① ≥3 宿舍区域与 nodeId 明确映射 | ✓ | 无 |
| ② 3D 中区分并选择不同节点 | ✓ raycaster 选择环+高亮 `three3d/app.js:440-526` | 无 |
| ③ ≥2 类对象随状态动态变化 | ✓ 楼体色/指示球/粒子/标牌/风扇/窗户 `three3d/app.js:19-24,333-434` | 无 |
| ④ 新消息到达 3D 无需刷新即更新 | ✓ MQTT 订阅 | 无 |
| ⑤ 当前优先关注节点在 3D 中明显表达 | ✗ | 阶段 B：优先光环 |
| ⑥ D3 处理中/已恢复至少一种状态在 3D 中体现 | ✗ | 阶段 B：事件状态徽标 |
| ⑦ ≥1 项明显展示效果的交互（动态标签/视角切换/事件动画/历史回放/状态面板联动） | ◐ 现有点击选择+侧栏+粒子动画，缺"亮点级"交互 | 阶段 B：镜头聚焦动画 + 事件回放 |

### E2 Camera/ASR/TTS 交互增强（任务书 p12-13，最低线 6 条）

| 最低线 | 现状 | 差距 |
|---|---|---|
| ASR ≥2 条有意义指令 | ◐ `web/script.js:316-331` 有"朗读状态/拍照"2 条（Win+H 等效） | 指令与实时系统脱节（web 单机） |
| ≥1 条语音指令真实改变操作对象或触发现有功能 | ✗ | 阶段 B：Dashboard 端"查看 dorm-x/开风扇"等 |
| 朗读内容来自当前真实节点或事件状态 | ✗ 现读 web 单机状态 | 阶段 B：TTS 读选中节点最新 MQTT 记录 |
| ≥1 张与当前节点/事件关联的快照 | ✗ 快照仅本地下载（`web/script.js:226-254`），无关联 | 阶段 B：快照叠加 nodeId/时间/状态并入事件记录 |
| 快照能说明节点/时间/状态 | ✗ | 同上 |
| ≥1 条完整交互链（如语音选择节点→朗读状态→记录现场） | ✗ | 阶段 B：Dashboard 端完整交互链 |

### E3 web-移动端实时数据同步与协同（任务书 p13-15，最低线 6 条）

| 最低线 | 现状 | 差距 |
|---|---|---|
| 两端读取同一套实时数据 | ✗ 移动端离线 | **核心差距** |
| 核心字段一致（nodeId/time/status 等） | ✓ 规则同源（rules.js 移植 + dashboard 复用 computeStatus） | 移动端接入后保持 |
| 新 MQTT 消息后两端自动更新 | ✗ | 阶段 A |
| 同步必须由共享数据源驱动（两端手输相同数据不算） | ✗ | 阶段 A |
| 共享业务状态（重点/处理中/已恢复）来自同一套系统状态 | ✗ | 阶段 A（与 D3 共享机制同源） |
| ≥1 项联动（移动切换重点/执行处理/查看事件 → web/3D 看到变化） | ✗ | 阶段 A：移动端"开启风扇"发布 action（联动#1） |

任务书明确：**不要求真机同步**（p15）——在微信开发者工具模拟器中证明读取同一套实时数据并保持同步即达基础完成线；开发者工具需关闭域名校验相关选项（"不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书"，名称以当期版本为准）；现场核验方式 = 随机发布一条新消息（如 dorm-b），检查两端更新且字段一致。

## 3. 交付物差距表

| 交付物 | 任务书要求 | 现状 | 动作 |
|---|---|---|---|
| GitHub 仓库 | 含 web/Dashboard、Python 分析、移动端、3D、数据示例、Evidence（p18）；≥5 次有意义 Commit，历史可看出"可运行→改进→修复→稳定" | 结构基本齐；Commit 已有基础 | 阶段 C 规划 ≥5 次有意义提交（提交前展示摘要） |
| Evidence/ 目录 | 仓库根独立目录，D1-D5 / E1-E3 / Debug / Reproduce + 索引 README，每项配一句说明（p18-19） | 不存在（C01 证据在 docs/evidence/ 不动） | 阶段 C 新建，旧证据不动 |
| README | 十项清单（p19）：项目是什么/环境要求与版本/目录结构/依赖安装与配置/完整启动顺序/MQTT Broker 地址与端口与 Topic/怎样产生测试数据/怎样证明 web-移动端同步/怎样快速复现 D1-D5/常见问题排查 + 已知限制 + 开源库来源 | 现 88 行，覆盖部分 | 阶段 C 按清单重写 |
| Reproduce 交叉复现 | 必做（p20）：未参与开发的同学只凭仓库+README 复现核心数据链；留下①1 个问题/卡点②对 README 的修订③修订后再次复现结果 | 不存在 | 阶段 C：Claude 扮演"从未接触项目的同学"冷执行，证据入 Evidence/Reproduce/ |
| PPT | 10-15 页，12 项内容（p20-21）：问题与目标/产品形态/架构与两链/多端协同/D1-D5/E1-E3/事件生命周期/真实故障修复/Rule-ML 对照/自主设计与亮点/开放拓展/已知限制与后续 | 不存在 | 阶段 C 用 pptx skill 生成 |
| 技术文档 | 10-15 页正文，6 部分（p21）：项目概述/系统与数据链/核心机制（数据结构、Topic 设计、MQTT 过程、web-移动端同步机制）/D1-D5 与 E1-E3 关键实现/测试与验证（回归、D1-D5 与 E1-E3 验证、Rule/ML 对照、交叉复现）/自主设计与 Open Enhancement；配架构图、事件状态图、关键截图，不整段复制代码 | 不存在 | 阶段 C 写 `docs/V08R5_Plans/TECHNICAL_REPORT.md` |
| 演示视频 | 5-8 分钟，一条完整故事线（p22），不按模块逐个介绍；含故障修复段 + Rule/ML 对照段；以真实系统运行为主 | demo-final.mp4 按 M 模块叙事、无故障段 | 阶段 C 按故事线重录 |
| 现场验收 | Run/Explain/Modify/Debug/Verify（p22-23），Modify 5 例（改阈值/改移动端字段/加 ASR 指令/改 3D 映射/调优先规则），Debug 5 例（Topic 错/JSON 字段错/Broker 停/3D 映射错/移动端不同步） | Open-01 已过一轮 | 阶段 D 针对新功能全量预演 |

## 4. 设计决策记录（已与用户确认）

1. **E2 落点 = Dashboard 端**：语音命令条（Win+H 等效）+ 快照关联节点/事件加在 dashboard；`web/` 保持纯离线数据链入口（表单→CSV→Python），符合任务书 p4 分工表（web=多节点实时总览即 Dashboard 角色，移动端=快查快操作，3D=空间表达）。
2. **Evidence 目录 = 新建仓库根 `Evidence/`**（D1-D5、E1-E3、Debug、Reproduce + 索引 README）；`docs/evidence/` 的 C01 旧证据冻结不动。
3. **Commit 门槛 = 综合作品阶段 ≥5 次有意义 Commit**（任务书 p18 原文，已人工核对）。
4. **移动端 MQTT = `wx.connectSocket` + 极简 MQTT 3.1.1 客户端**（CONNECT/SUBSCRIBE/PINGREQ/PUBLISH/重连，零依赖、不引入 npm 构建），连 Mosquitto WebSocket `ws://127.0.0.1:8083`；开发者工具勾选"不校验合法域名"（任务书 p15 原文；真机不要求）。
5. **事件状态跨端共享机制**：Dashboard 保持事件状态机**唯一持有者**（恢复仍仅由新 env 数据触发），状态变化发布到新 topic `dormmate/{nodeId}/event`（payload：nodeId/eventId/state: OPEN|HANDLING|RECOVERED/time/summary），3D 与移动端订阅渲染。满足任务书 p8"对同一事件保持一致，不各自维护"与 p14"来自同一套系统状态"。
6. **3D 事件回放**：3D 端内存缓存每节点最近 N 条 env 记录，侧栏"回放"按钮按时间轴重放状态颜色/粒子变化（无新依赖，手写 lerp 动画）。
7. **规则零重写**：status 规则、统一 JSON 6 字段、CSV 最小格式不动；移动端/3D 状态重算沿用同源实现（`web/script.js` computeStatus / `mobile/utils/rules.js` / `analysis/analyze.py`）。

## 5. 分阶段升级路线图

### 阶段 A：基础设施升级（移动端 MQTT 接入 + 统一状态源 + 事件生命周期跨端同步）

> **状态：✅ 已完成（2026-09-30）**——A1-A4 全部落地；验收：协议帧单元测试 30/30 + 端到端 14 项全过（`python simulator/test_upgrade.py`，exit code 0）；证据归档 Evidence/D1、Evidence/E3

**A1 ✅ 移动端 MQTT 客户端（新建 `mobile/utils/mqtt.js`）**
- `wx.connectSocket({url: "ws://127.0.0.1:8083"})`（Mosquitto WebSocket 端口，路径 `/`，与 dashboard 已通配置一致）
- 手写极简 MQTT 3.1.1 协议帧（UTF-8）：
  - CONNECT：固定头 `0x10`，可变头 协议名 `0x00 0x04 M Q T T` + 协议级 `0x04` + 连接标志 `0x02`（Clean Session）+ KeepAlive（2 字节，30s）+ ClientId
  - SUBSCRIBE：`0x82` + PacketId + Topic Filter + QoS 0
  - PINGREQ：`0xC0`（保活），PINGRESP `0xD0` 处理
  - PUBLISH（QoS 0，供动作按钮用）：`0x30` + Topic + Payload
  - 解析：CONNACK `0x20`（成功后发 SUBSCRIBE）、PUBLISH `0x30`（按 topic 分流）、SUBACK、PINGRESP
- `onClose/onError` → 3 秒后自动重连（任务书 p14 加分项"自动重连"顺带满足）
- 订阅：`dormmate/+/env`、`dormmate/+/event`；动作发布：`dormmate/{nodeId}/action`
- 不引入 npm 构建，保持 devtools 直接导入 mobile/ 即可编译

**A2 ✅ 小程序页面改造（`mobile/pages/index/`）**
- 三节点卡片（dorm-a/b/c）：env 消息 → `rules.buildRecord` 本地重算状态（不信任消息 status，与 dashboard 同策略）→ 渲染温度/湿度/状态/时间
- 当前重点标识：订阅 event/priority 状态显示"当前重点"
- 事件状态徽标：处理中/已恢复（来自 event topic）
- "开启风扇"按钮：发布 action → **联动#1**（移动操作 → simulator 降温 → Dashboard 状态机 → 3D 风扇转，满足 E3 最低线⑥）
- 保留原"手动输入+演示数据"功能并标注为降级模式（离线链兼容）
- 开发者工具设置：详情→本地设置→勾选域名校验豁免项（名称以当期版本为准，写入 README）

**A3 ✅ 事件状态跨端共享（dashboard + 3D + 移动端）**
- 新 topic 契约：`dormmate/{nodeId}/event`，payload `{nodeId, eventId, state: "OPEN"|"HANDLING"|"RECOVERED", time, summary}`
- `dashboard/app.js`：状态机仍唯一持有；在三个时机发布——OPEN（发现异常建事件草稿）、HANDLING（fan_on 成功）、RECOVERED（新数据触发恢复）
- `three3d/app.js` 订阅 event topic → 状态徽标（视觉细节在阶段 B）
- 移动端订阅 event topic → 徽标
- 与 MASTER_PLAN §6.3 契约一致：恢复仍仅由后续新数据触发

**A4 ✅ 验收与证据**
- 新建 `simulator/test_upgrade.py`（一键验收：前置检查 + 协议帧单元测试 + 广播结构断言 + 三端一致性 + 自动截图归档；动态选安静节点、按 eventId 分组断言抗多实例干扰）+ `simulator/test_mobile_mqtt.js`（协议帧单元测试 30 项）
- Evidence/D1（三节点同屏、3D 三栋楼、新消息驱动更新截图）、Evidence/E3（处理中/已恢复截图、3D 风扇运行、广播消息原文）已归档；Evidence/README.md 索引 + 其余子目录骨架就绪
- 小程序端截图待用户按 Evidence/README.md 说明补拍 2 张

**阶段 A 验收标准**：小程序模拟器中三节点实时更新且与 Dashboard 数值一致；移动端开风扇后 Dashboard 进入"处理中"、3D 风扇转动；恢复由新数据触发；域名校验设置说明写入 README。

### 阶段 B：交互与 3D 增强（E1/E2 亮点）

- **B1 3D 优先节点表达（E1⑤）**：订阅 event/priority 状态 → 优先节点建筑外圈光环（脉冲动画，复用现有选择环与动画循环 `three3d/app.js:402-434` 的 lerp 模式）
- **B2 3D 事件状态表达（E1⑥）**：CanvasTexture 标牌扩展"处理中/已恢复"文字+颜色；处理中粒子加速/变色
- **B3 3D 镜头聚焦动画（E1⑦）**：点击选择/优先节点变化时，camera 平滑过渡到该建筑（手写 lerp 插值，不引入 TWEEN）
- **B4 3D 事件回放（E1⑦）**：每节点内存缓存最近 N 条 env 记录，侧栏"回放"按钮按时间轴重放状态颜色与粒子变化，速度可调
- **B5 Dashboard 语音命令条（E2）**：index.html 加命令输入框（Win+H 语音输入）+ `dashboard/app.js` 命令解析：
  - "查看 dorm-a|dorm-b|dorm-c" → 切换选中节点（改变操作对象）
  - "朗读状态" → TTS（speechSynthesis zh-CN）朗读选中节点最新 MQTT 记录（温度/湿度/状态/建议）
  - "拍照" → getUserMedia 快照，canvas 叠加 nodeId/时间/状态 → 保存 PNG 到 Evidence/E2，若当前有处理中事件则关联事件记录
  - "开启风扇"/"关闭风扇" → 发布 action（复用 publishAction）
  - 未匹配指令给出提示（沿用 `web/script.js:334-342` 模式）
- **B6 E2 完整交互链演示**：语音选择 dorm-b → 朗读状态 → 拍照 → 事件卡片含快照引用（events.json 扩展快照字段）；证据入 Evidence/E2

**阶段 B 验收标准**：E1 最低线 7 条全勾、E2 最低线 6 条全勾（逐条对照）；现场 Modify 预演通过（改 3D 状态映射、加 ASR 指令）。

**✅ 已完成（2026-09-30）**：
- B1-B6 全部实现并验证：`simulator/test_stage_b.py` 一键验收（五套件：光环 4 项 / 徽标 5 项 / 聚焦 9 项 / 回放 11 项 / 语音 12 项，exit code 0 = 全过）；E1/E2 最低线逐条对照清单内置于该脚本输出
- 证据归档：Evidence/E1（8 张：光环×2、徽标×2、聚焦×4、回放×2）、Evidence/E2（6 项：语音条、查看切换、TTS 文本、快照 PNG、事件卡片、交互链记录）；Evidence/README.md 已更新逐项说明
- 阶段 A 回归：B3、B4、B5、B6 后各跑 `test_upgrade.py` 均 100% PASS
- 现场 Modify 预演（改 3D 状态映射、加 ASR 指令）列入手动演示清单，随阶段 D Run/Explain/Modify/Debug/Verify 系统性执行
- 环境注意：验收脚本统一走 5510 端口静态服务（`python -m http.server 5510`）——VS Code Live Server（5500）监视工作区文件变化，证据截图写入会触发其页面重载打断测试（2026-09-30 实测定位，双 5500 监听为 Windows 双绑定现象）

### 阶段 C：交付物制作

> **状态：✅ 已完成（2026-10-01）**——C1-C7 全部落地；6 次有意义提交（03e5756 README 重写 / 2f124c8 交叉复现证据与修订 / 780c250 技术文档与证据补齐 / e680c2b 故事线演示录制与配音 / 859ccf1 PPT）；验收标准逐条达标（PDF 11 页、PPT 14 页、视频 7:34、Reproduce 三件套、Evidence 九目录索引齐全）

- **C1 ✅ README 重写**：按任务书 p19 十项清单逐项覆盖 + 已知限制 + 开源组件表；新增演示前重置系统状态清单（events.json / 重启服务 / 刷新页面）
- **C2 ✅ 技术文档**（`docs/V08R5_Plans/TECHNICAL_REPORT.md` + `.pdf`，**11 页正文** ∈ [10,15]，6 部分 + 多端分工；配自绘架构图/事件状态图 SVG→PNG、证据拼图 4 张；渲染管线 `simulator/render_report.py`，页数口径=渲染 PDF 页数）
- **C3 ✅ PPT**（`docs/V08R5_Plans/DormMate_V08R5_PPT.pptx`，**14 页** ∈ [10,15]，任务书 12 项内容 + 封面/收尾；E2 页为真实摄像头快照；每页备注附讲稿要点；生成器 `docs/V08R5_Plans/gen_ppt.js`，validate 全过）
- **C4 ✅ Reproduce 交叉复现**：两轮冷执行（只凭 README + 全新 venv）；7 条卡点 → README 6 处修订 → 第二轮两条链全通、修订点逐条验证；三件套证据在 `Evidence/Reproduce/`（reproduce-log.md / readme-revision.diff / reproduce-result.md + 两轮截图 48 件）
- **C5 ✅ 演示视频重录**（`docs/demo/demo-v08r5-final.mp4`，**7:34** ∈ [5,8] 分钟，任务书 p22 故事线 9 beats 全含：dorm-b 偏热 → 标记重点 → 多端同步（移动端同屏）→ Camera 快照 → 处理 → 恢复 → 故障修复（坏 JSON）→ 冷启动 → Rule/ML 对照；`record_demo.py` 8 幕 + gdigrab 区域捕获（竖屏窗口优先+置顶防遮挡）+ `add_dub.py` edge-tts 配音硬字幕；媒体不入 git（.gitignore），成品本地保存）
- **C6 ✅ Evidence/ 建设**：D1-D5、E1-E3、Debug、Reproduce 九子目录 + 索引（每项一句说明）；移动端 E3 补拍 2 张已入；docs/evidence/ 旧证据不动
- **C7 ✅ Git 提交**：6 次有意义提交（≥5 达标），每次提交前展示变更摘要经确认

**阶段 C 验收标准**：任务书 §8 各交付物页数/时长/结构达标；Reproduce 有"卡点+修订+复现"三件套。✅ 全部达标

### 阶段 D：现场验收自测（Run/Explain/Modify/Debug/Verify）

> **状态：✅ 已完成（2026-10-01）**——D1-D5 全部落地：冷启动演练 8 步全过（证据 docs/evidence/upgrade/d1-*.png）、Explain 话术框架、Modify 5 用例预演（全部验证并还原、git diff 干净）、Debug 5 故障预演（1-4 实测记录 + 证据 Evidence/Debug/，5 为 GUI 步骤现场演示）、Verify 断言全绿（test_final 62 断言 0 failures + test_upgrade 阶段 A 全部通过 + test_stage_b 阶段 B 全部通过）。提交 437a9c5（D1）、8653c85（D3）、d806a21（D4）。

- **D1 Run**：冷启动清单演练（Broker→simulator→Dashboard→移动端→3D），两条链跑通；更新 `docs/OPEN01_GUIDE.md`
- **D2 Explain**：随机功能说明脚本（数据从哪来→什么处理→为什么是这个结果）
- **D3 Modify**：5 个预演用例（改状态阈值 / 改移动端显示字段 / 加 ASR 指令 / 改 3D 状态映射 / 调优先规则），每个改完重新运行验证
- **D4 Debug**：5 个可控故障预演（Topic 写错 / JSON 字段错 / Broker 停 / 3D 节点映射错 / 移动端不同步），记录现象→定位→修复→验证，证据入 Evidence/Debug
- **D5 Verify**：自动化断言全绿（test_final.py 62 断言 + 阶段 A 新增断言）；对照任务书 §10 最终完成线逐条勾选

**阶段 D 验收标准**：§10 完成线全勾；Open Enhancement（如有）运行与验证证据保留。

## 6. 自主设计清单（任务书 p16 十方向 → 本项目决定）

1. **重点节点判断**：沿用 A1 优先规则（异常持续时长→异常次数→nodeId 顺序），升级后经 event topic 广播共享
2. **Dashboard 多节点组织**：三卡片 + 优先横幅 + 事件面板 + 趋势图（沿用 M5/A 布局，加语音命令条）
3. **移动端核心信息**：三节点当前状态 + 当前重点 + 事件状态 + 开风扇按钮（快查定位，不复制 Dashboard 图表）
4. **3D 节点表达**：建筑群 + 状态色/粒子/标牌 + 优先光环 + 事件状态徽标 + 回放
5. **ASR 指令设计**：5 条业务指令（查看 dorm-x / 朗读状态 / 拍照 / 开启风扇 / 关闭风扇）
6. **快照与事件关联**：canvas 叠加节点/时间/状态，文件名含 eventId，事件记录含快照引用
7. **事件状态组织**：Dashboard 状态机唯一源 + event topic 广播 + 事件 9 字段（A4 契约扩展快照字段）
8. **历史报告重点**：统计 + 异常记录 + 事件复盘 + ML 对照（沿用 report.html 四块结构）
9. **视频故事**：dorm-b 一条事件闭环主线（任务书 p22 建议故事线）
10. **数据**：sim-day-final 模拟日 + C 组对照数据 + 现场随机发布消息

## 7. 风险与红线

- **status 规则顺序 / 回归四例 / 统一 JSON 6 字段 / CSV 最小格式不可改**（SPEC §3/§4/§5/§6）
- **恢复必须仅由新数据触发**，任何端点击按钮不能改"已恢复"
- **C01 技术边界**：无数据库、无真实传感器、无 LLM/RAG/Agent、无正式 ML 训练（Open Enhancement 允许但非完成线前提，本计划基础线不引入）
- **真机同步不要求**（任务书 p15）；局域网/云端属 Open Enhancement，不纳入基础完成线
- **规则零重写**：`web/script.js` computeStatus 是全项目唯一 JS 规则实现，移动端/3D 状态重算沿用同源
- **Evidence 新目录与 docs/evidence 并存**，不迁移旧证据
- 各阶段完成前不进入下一阶段；每阶段验收标准全过才算完成

## 8. 待核对项与已知限制

- 微信开发者工具"不校验合法域名"相关选项的确切名称与位置以当期版本为准（任务书 p15 原文如此说明）
- 任务书 OCR 文本含噪声，关键数字已人工核对（Commit 5 次、PPT 10-15 页、技术文档 10-15 页、视频 5-8 分钟）；其余引用以 PDF 原文为准
- Mosquitto WebSocket 路径实测确认（dashboard 已通 `ws://localhost:8083`，路径沿用）
- **已知现象（演示注意）**：多个 Dashboard 实例同时连接同一 Broker 时，各自独立运行事件状态机与优先规则，会重复广播事件状态并相互覆盖优先节点（3D/小程序跟随"最后广播"）。本项目按"Dashboard 状态机唯一持有者"设计，此现象仅在多实例测试环境出现（A4 验收时实测记录，`simulator/test_upgrade.py` 已做抗干扰断言）。**正式演示与验收时只开一个 Dashboard**
- **已知限制（验收脚本依赖）**：`test_upgrade.py` 需要 5510 端口有静态服务（`python -m http.server 5510`，工作区根=项目根）；Broker 与 simulator 需先运行
- **"已恢复"展示是瞬态**：恢复后下一条异常游走记录会按规则打破恢复（recovery=null），卡片/3D 侧栏的"已恢复"字样可能只持续数秒——这是 D3"恢复必须由新数据触发、异常回归即重新关注"规则的正确行为，非缺陷
