# DormMate Final 执行计划（PLAN）

> 本文件是**活文档**：每阶段结束更新第 2 节总览表的状态列与第 4 节看板。唯一事实源见 DORMMATE_SPEC.md，冲突时以 SPEC 为准；A/B/C/Final 详细执行步骤与契约见 MASTER_PLAN.md。

## 1. 计划原则

1. **唯一事实源**：docs/DORMMATE_SPEC.md + 本文件；冲突以 SPEC 为准，SPEC 变更须用户确认
2. **一次只做一个阶段**：按看板"当前阶段"执行，不并行推进多个阶段
3. **每阶段有门禁**：完成线全部满足才算完成，未完成不进下一阶段
4. **每阶段至少一次 Commit**：阶段产物 + 证据一并提交
5. **M1-M4 单宿舍**：M1-M4 可只使用一个宿舍节点
6. **M5 起三节点**：M5 及以后必须 dorm-a / dorm-b / dorm-c 三个节点，且不能串线
7. **A / B 可交叉**：A 组（优先关注 / 处理动作 / 恢复判断 / 事件复盘，依赖 M5/M6）与 B 组之间可交叉推进；各组内部按模块顺序
8. **C 最后**：轻量 ML 应用闭环必须在 A、B 完成之后做
9. **最终关闭重启验证**：Final 阶段关闭所有进程后重启，两条链端到端复跑通过才算收尾
10. **MASTER_PLAN**：剩余阶段（A/B/C/Final）详细步骤、契约扩展与验收总表以 docs/MASTER_PLAN.md 为准，本文件看板与其状态同步

## 2. 阶段总览表

| 阶段 | 目标 | 依赖 | 完成线 | 证据 | 状态 |
|---|---|---|---|---|---|
| 阶段0 | 建立 docs/ 两份唯一事实源文档 | 无 | 文档通过自检 | docs/ 两文件 | 已完成 |
| M1 | Web 主应用（输入 / 判断 / 记录）+ 统一规则 | 阶段0 | 四组回归全对 + 任务书 5 条验收 | 页面 + test.html + 历史截图 | 已完成 |
| M2 | 离线数据分析与报告（CSV -> Python -> trend.png / report.html） | M1 | 任务书 6-10 条；换 CSV 全量重生成 | CSV + 脚本 + 两产物 | 已完成 |
| M3 | Camera / ASR / TTS + Git / GitHub | M1 | 任务书 11-15 条；≥3 次有意义 Commit | 快照 / 识别 / 提交记录 / README | 已完成 |
| M4 | 移动端小程序核心页面（单宿舍） | M1 | 微信开发者工具稳定运行 | 开发者工具截图 | 已完成 |
| M5 | 本机 Broker + 模拟节点三宿舍 + Dashboard | M1（M4 可交叉） | 三节点同屏不串线 | 运行截图 | 已完成 |
| M6 | Three.js 3D 三节点联动 | M5 | 3D 实时更新 | 截图 / 录屏 | 已完成 |
| A | 优先关注 / 处理动作 / 恢复判断 / 事件复盘（A1-A4） | M5 / M6 | A1-A4 全过 | 逐项证据 | 已完成 |
| B | 把已有信息讲清楚：当前总览 / 判断依据 / 今日摘要 / 合适表达（B1-B4，不新增 LLM/VLM） | M1-M6 / A | B1-B4 全过；内容全部由程序生成 | 程序输出截图 | 已完成 |
| C | 轻量 ML 应用闭环 C1-C4（从历史数据中发现异常，固定规则 / ML 对照） | A、B 之后（最后做） | C1-C4 全过；结果与固定规则并排接回 report.html；保留 1 个不理想案例 | 模型 / 展示 / 说明 | 已完成 |
| Final | 关闭重启验证 + 稳定版同步 GitHub | A / B / C | 重启后两条链跑通 | 复验截图 + Git | 已完成 |

## 3. 每阶段详情

### 阶段0 初始化
- **阶段**：阶段0
- **目标**：在 F:\AIcoding\nova-dommate-final-2026\docs\ 建立 SPEC 与 PLAN 两份唯一事实源文档
- **输入**：任务书信息提取包（统一规则 / JSON / CSV / 回归测试数据 / 统一约定）
- **输出**：docs/DORMMATE_SPEC.md、docs/PLAN.md
- **依赖**：无
- **完成线**：两份文档存在且通过自检（规则顺序 / nodeId / CSV 列 / 四组测试数据 / M5 三节点 / C 轻量 ML）
- **证据**：docs/ 两文件
- **不要做什么**：不写业务代码；不创建 web/、analysis/、mobile/、dashboard/、three3d/、simulator/、data/ 等代码目录；不进入 M1
- **风险**：提取包与任务书原文不一致 → 以用户确认的提取包为准，冲突时暂停询问
- **交接接口**：M1 读取 SPEC 第 3-6 节（状态规则 / JSON / CSV / 测试数据）

### M1 Web 主应用：输入、判断、记录
- **阶段**：M1
- **目标**：web/ 单页面应用（index.html + style.css + script.js）：温湿度输入 → 校验 → 统一规则判断 → 状态 + 建议 → 带时间历史（单宿舍 dorm-a）；落地统一状态规则与统一 JSON 作为全项目统一实现
- **输入**：SPEC 第 3-6 节；详细步骤见 docs/M1_PLAN.md
- **输出**：web/ 三文件 + web/test.html（四组回归）+ 历史截图
- **依赖**：阶段0
- **完成线**：四组回归测试数据全部算对（25/60→正常、16/60→偏冷、31/60→偏热、25/80→偏湿）+ 任务书 M1 验收条目（见 docs/M1_PLAN.md 验收清单）
- **证据**：test.html 通过截图 + 页面运行截图 + 历史截图（docs/evidence/m1/）
- **不要做什么**：不做 CSV 落盘（M2）、语音（M3）、多节点（M5 起）；无数据库 / 传感器 / LLM；历史仅存内存（刷新后可消失）
- **风险**：规则顺序写反（偏冷 / 偏热颠倒会导致 16 与 31 都判错）→ 以四组回归测试守住；test.html 引入 script.js 时 DOM 为 null → script.js 纯函数与 DOM 操作分离（见 M1_PLAN）
- **交接接口**：M2 复用 computeStatus() 与历史 JSON（导出 CSV）；M3 复用 analyze() 入口（语音指令）；M4、M5 复用同一 status 计算逻辑，禁止各自重写

### M2 离线数据分析与报告
- **阶段**：M2
- **目标**：M1 历史 → 导出 data/dormmate.csv → analysis/ Python 读取 → 统计（记录数、温湿度最高 / 最低）→ 对全部记录重跑统一规则（各状态数量、关注记录）→ matplotlib 生成 trend.png → 自动生成 report.html（摘要、关注记录、趋势图）
- **注**：任务书未明确定义"需要关注的记录"，本项目暂按 status 非正常（偏冷 / 偏热 / 偏湿）为准
- **输入**：M1 的 computeStatus() 与历史 JSON；SPEC 第 5 节 CSV 格式；详细步骤见 docs/M2_PLAN.md
- **输出**：data/dormmate.csv；analysis/ Python 脚本；data/trend.png；data/report.html
- **依赖**：M1
- **完成线**：任务书 M2 验收条目全部满足；**换一份新 CSV 后统计、图、报告全部由程序重新生成**，禁止手工修改结果冒充程序生成
- **证据**：CSV 内容截图（Excel / WPS 打开核对）+ Python 脚本 + 两个产物文件
- **不要做什么**：不做 M3 Camera/ASR/TTS；不做多节点；不做数据库；不手工改 CSV / 报告结果
- **风险**：CSV 中文 status 乱码 → 统一 UTF-8 编码；产物与 CSV 不一致 → 一律以程序重新生成为准
- **交接接口**：trend.png / report.html 数据供 C 组复用；历史 JSON 结构供 A 组（优先关注）复用

### M3 本机交互 + 版本记录
- **阶段**：M3
- **目标**：Camera 现场快照（不连续采集）+ ASR 固定指令触发已有功能 + TTS 朗读随状态变化 + 本地 Git ≥3 次有意义 Commit 并 Push GitHub + README
- **输入**：M1 的 web/ 页面（analyze() 入口）
- **输出**：Camera 快照；ASR/TTS 交互；本地 Git 提交历史；GitHub 仓库；README.md
- **依赖**：M1（Camera/ASR/TTS 作用于 M1 页面；Git 提交贯穿全程）
- **完成线**：任务书 M3 验收条目全部满足（Camera + ASR/TTS 现场可运行；≥1 条固定指令真实触发已有功能；≥3 次有意义 Commit；README 完整；最终稳定版本与本地 / GitHub 最新 Commit 对应）
- **证据**：现场快照、ASR 识别结果截图、TTS、git log、GitHub Commit 记录、README
- **不要做什么**：不连续采集 Camera；不把 API Key / 密码提交进仓库；不能跳过"识别文字 + 固定指令触发功能"
- **风险**：SpeechRecognition 浏览器兼容 / 在线服务不可用 → 按 SPEC 第 13 节约定等价替代并在 README 记录；Camera 需 localhost + 权限
- **交接接口**：最终稳定版本对应 GitHub 最新 Commit；A 组与 B 组依赖其版本记录

### M4 移动端小程序
- **阶段**：M4
- **目标**：mobile/ 微信小程序核心页面（查看宿舍状态 / 数据，单宿舍即可）；复用 M1 同一套业务规则（computeStatus 纯函数），不复制 Web DOM 代码
- **输入**：M1 的 status 计算逻辑；CSV 或模拟数据
- **输出**：小程序核心页面（微信开发者工具可运行）
- **依赖**：M1
- **完成线**：微信开发者工具稳定运行核心页面（不要求 AppID / 真机账号）
- **证据**：微信开发者工具运行截图
- **不要做什么**：不把 AppID / 真机作为完成线；不做 M5 实时订阅（可预留）
- **风险**：工具版本 / 基础库兼容 → 使用微信开发者工具默认基础库
- **交接接口**：M5 起可选订阅 MQTT

### M5 MQTT 实时系统
- **阶段**：M5
- **目标**：本机 Broker（如 mosquitto）+ 模拟节点 dorm-a / dorm-b / dorm-c 按统一 JSON 发布 + dashboard/ 订阅同屏展示三节点；Topic 命名统一 dormmate/{nodeId}/env（如 dormmate/dorm-a/env）
- **输入**：M1 的规则与统一 JSON；本机 MQTT Broker
- **输出**：simulator/ 三节点发布器；dashboard/ 看板；本机 Broker 启动说明
- **依赖**：M1（M4 可交叉）
- **完成线**：三节点同屏、实时刷新、互不串线；status 按规则计算
- **证据**：Dashboard 三节点同屏运行截图 + 订阅日志
- **不要做什么**：不要求公网 / 共享 Broker；不引入数据库
- **风险**：三节点数据串线（topic / nodeId 混用）→ 每节点独立 topic（dormmate/{nodeId}/env）
- **交接接口**：M6 消费同一 MQTT 数据流

### M6 Three.js 3D 可视化
- **阶段**：M6
- **目标**：three3d/ 3D 场景展示三个宿舍（状态映射为视觉表现，如颜色 / 图标），由 MQTT 实时数据驱动
- **输入**：M5 的 MQTT 数据流
- **输出**：3D 场景（三节点独立展示）
- **依赖**：M5
- **完成线**：3D 中三节点状态随实时数据更新、不串线
- **证据**：3D 截图 / 录屏
- **不要做什么**：不做游戏级渲染；不做新数据源
- **风险**：性能 / 浏览器兼容 → 保持场景轻量
- **交接接口**：Final 复验

### A 优先关注、处理动作、恢复判断与事件复盘（A1-A4）
- **阶段**：A
- **目标**：A1 优先关注哪个宿舍（连续异常时长 → 次数 → nodeId 顺序，程序计算）；A2 发现问题后能做什么（至少 1 个真实用户操作，actionState 经 MQTT 动作通道进系统状态）；A3 恢复判断（后续新数据是否让状态恢复，处理中 / 已恢复）；A4 完整事件记录与复盘（事件进 report.html"事件复盘"区）
- **输入**：M5 Dashboard / M6 3D；历史 JSON（action 预留字段）；simulator 动作响应（降温趋势）
- **输出**：A 组逐项验收记录 + data/events.json + report.html 事件复盘区
- **依赖**：M5 / M6（M1-M4 不实现）
- **完成线**：A1 至少 3 组三节点测试数据通过；A2 动作后 Dashboard / 3D 状态一致且不直接改状态；A3 处理之后用新数据判断"仍需关注 / 处理中 / 已恢复"，恢复必须由新数据触发（本项目规则：连续 ≥2 条正常，README 写清）；A4 至少 1 条完整事件可复盘"发现 → 判断 → 处理 → 验证 → 恢复"
- **证据**：逐项截图 / 日志 / 录屏
- **不要做什么**：不把"点击处理"直接当成"已恢复"；连续异常时长禁止人工判断；事件、动作和结果必须由程序真实产生
- **风险**：三节点串线 → 优先规则以程序计算为准，action 消息走同款 topic↔nodeId 防线；A2/A3 耦合 → 严格解耦
- **交接接口**：B1/B2 复用 A1 优先规则与 streak；B3 复用 A4 事件记录；C 依赖 A 的数据与展示端
- **详细步骤**：docs/MASTER_PLAN.md §7.3（S0-S7）

### B 把已有信息讲清楚（B1-B4）
- **阶段**：B
- **目标**：B1 当前总览（三节点真实状态自动成句，不写死）；B2 判断依据（持续时间 / 异常次数 / 当前状态，来源可指）；B3 今日摘要（≥2 事件模拟日数据，程序生成，换数据重生成）；B4 合适表达（Dashboard 当前重点 / 3D 空间状态 / TTS 当前提醒 / report.html 历史复盘，四类分工，移动端简报可选扩展）
- **输入**：M1-M6 / A 组产物（Dashboard 实时数据、events.json、report.html 管线）
- **输出**：Dashboard 总览与依据卡片 + 朗读提醒按钮；今日摘要生成脚本与输出
- **依赖**：M1-M6 / A（B1-B4 可与 A 交叉推进，本项目默认线性）
- **完成线**：B1-B4 全过；内容全部由程序生成，不手写、不新增 LLM/VLM
- **证据**：程序输出截图 / 文件
- **不要做什么**：不手写说明内容；不把同一段信息复制到多个页面
- **风险**：程序输出与实际情况脱节 → 以程序输出为准并保留生成脚本；总览/摘要写死 → 换数据自动变化留证
- **交接接口**：C 依赖 B 的展示端（report.html）
- **详细步骤**：docs/MASTER_PLAN.md §7.4（S0-S5）

### C 轻量 ML 应用闭环（C1-C4，从历史数据中发现异常）
- **阶段**：C
- **目标**：C1 数据准备（单节点 30-50 条模拟历史，历史与新数据严格分离，random_state=42 可复现）；C2 固定规则 / ML 对照（多组新数据双判断，不一致保留解释、未出现如实记录）；C3 结果接回 report.html"ML 异常分析"区（当前值 / 固定规则 / ML 判断并排，换 CSV 重新生成）；C4 保留 ≥1 个不理想案例及可能原因
- **输入**：离线链 CSV（data/）；report.html 管线（C3 扩展点注释 analysis/analyze.py:232）
- **输出**：c_history.csv / c_new.csv + c_ml.py + c_compare.json + report.html ML 异常分析区 + 闭环说明
- **依赖**：A、B 之后（最后做）
- **完成线**：C1-C4 全过（小数据跑通闭环即可，不追求精度）；结果与固定规则并排出现在 report.html；保留至少 1 个不理想案例并说明；不伪造"规则正常 / ML 不同"结果
- **证据**：模型输出 / 对照表 / 展示截图 / 说明文档
- **不要做什么**：不做 Label / Train-Test / Accuracy-F1 / 混淆矩阵 / 模型版本管理 / 调参；不新建后端（FastAPI / Flask / 数据库 / 模型服务）；sklearn 安装失败用纯 Python 自实现兜底并 README 记录（pip install 前征得用户同意）
- **风险**：sklearn 在 Python 3.14 无 wheel / 安装失败 → 自实现兜底；数据量小易过拟合 → 以"跑通闭环"为完成线，不追求指标
- **交接接口**：Final 复验（同数据同 random_state=42 同结果）
- **详细步骤**：docs/MASTER_PLAN.md §7.5（S0-S5）

### Final 关闭重启验证 + 稳定版
- **阶段**：Final
- **目标**：关闭所有进程（Broker / 服务器 / 开发者工具）后重启，两条链端到端复跑通过；稳定版同步 GitHub
- **输入**：全部阶段产物
- **输出**：复验记录；GitHub 仓库 `nova-dommate-final-2026` 同步
- **依赖**：A / B / C 全部完成
- **完成线**：重启后离线链（Web→CSV→Python→trend.png / report.html）与实时链（模拟节点→MQTT→Dashboard→3D）均跑通
- **证据**：复验截图 / 录屏 + git 提交记录
- **不要做什么**：不复验不算 Final；不临时改规则
- **风险**：重启后环境变量 / 服务未自启 → 按文档步骤逐项启动
- **交接接口**：项目收尾

## 4. 当前阶段看板

- **当前阶段**：项目收尾——Final 全部完成（复验 49db648 + 文档收口 8d94eb2 + GitHub 已同步 d384cb5）+ Open-01 前自检（文档修复 bf15203 + 演示资产入库 + 冷启动复验 62 断言全过）
- **当前只做**：Open-01 现场自测（用户按 docs/OPEN01_GUIDE.md 第二章完成 说明/修改/排错 三项练习，完成后留证并回归）
- **已完成**：阶段0 —— docs/DORMMATE_SPEC.md、docs/PLAN.md、CLAUDE.md 已创建并提交（e1b01a7）；S0 文档对齐（SPEC/PLAN 按任务书原文修正 M1 合并口径 / 校验范围 / M2/M3 重定义 / A 组重定义 / B 组程序化说明 / C 组 IsolationForest / action 预留字段 / GitHub 仓库名 nova-dormmate-final-2026）；M1 全部（S1-S7，证据在 docs/evidence/m1/，提交 64e2aa0、f9bcd24、f8eaa47）；M2 全部（S1-S8，证据在 docs/evidence/m2/，提交 e50b815、5909f1c）；M3 全部（S0-S7：文档对齐 / Camera / TTS / 等价 ASR / README / 提交拆分 / GitHub Private 仓库推送 / 验收交接，提交 b2b293a、88aabc2、9fa9e37，GitHub 同步至 a745f96，S1-S3 用户实测通过，证据 docs/evidence/m3/，详细见 docs/M3_PLAN.md）；M4 全部（S0-S6：文档对齐 / 小程序骨架 / 规则移植 / 页面交互 / 冷启动验收 / 交接 / 评审修复，用户实测通过，提交 cb947ff、6b0e91b，GitHub 同步至 f1885a4，证据 = docs/evidence/m4/ review 归档 + 用户实测记录（截图非 M4 完成线要求，无需补拍），详细见 docs/M4_PLAN.md）；M5 S0（docs/M5_PLAN.md 创建 + 看板更新，3 项决策经用户确认：程序发布+MQTTX 演示 / Python paho-mqtt / Dashboard 本地 vendor；评审修正 4 项：端口冲突检查 / 断线重连 / JSON 容错 / 历史上限裁剪）；M5 全部（S0-S5：文档对齐 / 环境 / simulator 三节点发布 / Dashboard 骨架 / 趋势与切换 / 验收交接，S1-S4 用户实测通过——Broker 冷启动、MQTTX 互测、三卡片同屏、串线与坏消息拦截，证据 docs/evidence/m5/ 6 张，详细见 docs/M5_PLAN.md）；M6 全部（S0-S6：文档对齐 / vendor r128 三文件 / 静态场景 / 状态映射+演示按钮 / MQTT 实时驱动 / 验收交接 / 评审修复，提交 415c9db、7e72183、8fb68a4，GitHub 同步至 44b391c，证据 docs/evidence/m6/，详细见 docs/M6_PLAN.md）；A 组 S0 文档对齐（SPEC §9 更新为 A1-A4/B1-B4/C1-C4 + docs/MASTER_PLAN.md 建立，提交 d973401）；A 组全部（S1-S7：simulator 动作响应 / A1 优先关注横幅+测试页+演示脚本 / A2 动作入口 / three3d 动作联动 / A3 恢复状态机 / A4 事件复盘进 report.html / 验收交接，提交 d0da90d、a88ca0c、2b96f8d、78b7e37、08952d2、c92ede4，证据 docs/evidence/a1-a4/，详细见 MASTER_PLAN §7.3）；B 组全部（S1-S5：B1 当前总览 / B2 判断依据卡片 / B3 今日摘要（make_day_data + daily_summary + sim-day-1/2 数据）/ B4 朗读提醒+信息分工 / 验收交接，提交 0da67c1、ff485b5、27efd9f、c8a6771，证据 docs/evidence/b/，详细见 MASTER_PLAN §7.4）；C 组全部（S1-S5：C1 数据准备（c_history/c_new 严格分离 + random_state=42）/ C2 固定规则/ML 对照（sklearn 失败自实现 IsolationForest 兜底，README 记录替代原因）/ C3 结果接回 report.html"ML 异常分析"区（并排+差异高亮+换数据重生成）/ C4 不理想案例（27.5/70 对轻微偏离过敏感 + 可能原因 + 不做指标口径）/ 验收交接，提交 73dd8f8、fcc0f9e、4762947、dda3de1，证据 docs/evidence/c/，详细见 MASTER_PLAN §7.5）；Final 复验（F S1-S7：环境冷启动（Broker 1883/8083 + simulator 三节点）→ 实时链（Dashboard+3D 并排不串线）→ 离线链（Web 录入→CSV→analyze→report 五区）→ A 闭环重演（偏热→优先→开风扇→3D 联动→降温→已恢复→自动关扇→事件→报告复盘）→ B 信息闭环（总览/依据/朗读提醒/换 seed 摘要）→ C 对照复现（random_state=42 与已提交版本逐字段一致），test_final.py 62 项断言全过，证据 docs/evidence/final/，提交 49db648，详细见 MASTER_PLAN §7.6）
- **阻塞**：无
- **下一步**：无（项目全部完成；如需继续可走 SPEC 变更流程）
- **最近Commit**：docs(nova-dormmate-final-2026): Open-01 acceptance docs sweep and guide（bf15203，2026-09-30）+ feat: demo recording/dubbing/screenshots（本次提交）；GitHub 已同步至 d384cb5（2026-09-29），本轮收尾提交推送待网络窗口
- **下一阶段接口**：项目收尾；GitHub 仓库 `nova-dormmate-final-2026` master 与本地一致（subtree push 重写哈希，内容与顺序一致）

## 5. 给 Claude Code 的调用模板

- 每次只做当前阶段（以第 4 节看板为准），不并行推进多个阶段
- 先读 docs/DORMMATE_SPEC.md 与 docs/PLAN.md 再动手
- 不要做未解锁阶段（依赖未完成 / 未通过门禁的阶段一律不做）
- 完成后按第 6 节模板输出交接摘要
- 与 SPEC / PLAN 冲突或遇到规范外决定时，先停下来问用户，不私自改规范

## 6. 交接摘要模板

```
【阶段交接摘要】
阶段：X
状态：完成 / 未完成（附原因）
产出：文件 / 功能清单（含路径）
证据：截图 / 日志 / 文件路径
完成线自检：逐条对照该阶段完成线，注明通过 / 未通过
下一阶段：Y；接口：依赖本阶段的哪些产物 / 规范章节
风险 / 遗留：未解决的问题与影响
最近Commit：hash + 摘要（如已提交）
```

## 7. Git 策略

- 本地沿用 F:\AIcoding 现有仓库（不新建本地仓库）；本项目位于 nova-dormmate-final-2026/
- 提交遵循仓库现有英文 `type(scope): ...` 风格，如 `docs(nova-dormmate-final-2026): add spec and plan`
- 每阶段至少一次有意义 Commit（阶段产物 + 证据）；任务书要求 Challenge 期间至少 3 次有意义的 Commit（M1 规划 2 次：S2 后、S7 后）；提交前先展示变更摘要，仅在用户明确要求时提交
- Final 稳定版同步到用户 GitHub 账号的 `nova-dommate-final-2026` 仓库
- PLAN 是活文档：每阶段结束更新总览表状态列与看板；SPEC 是稳定契约，变更须用户确认
