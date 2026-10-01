# DormMate Open-01 现场自测指南（OPEN01_GUIDE）

> 对应任务书截图：62 提交清单 / 63 C01 完成线 / 64 Open-01 四项自测 / 65 最终检查 / 61 A/B/C 收口确认。
> 本文件是自测陪跑文档：第一章冷启动指令、第二章四项自测操作（说明/修改/排错）、第三章验收核对清单。
> 所有练习完成后的收尾要求：**改动的代码必须还原、回归测试必须复跑、git 状态必须干净**。

---

## 第一章 冷启动指令清单（自测①：从关闭状态重新启动作品）

### 0. 确认处于关闭状态

- 任务管理器（或 PowerShell `Get-Process mosquitto,python -ErrorAction SilentlyContinue`）确认没有 mosquitto.exe 和 simulator 的 python.exe 进程；浏览器关掉 Dashboard / 3D 页面

### 1. 离线链：Web 输入 → CSV → Python 分析 → 报告

1. VS Code 右键 `web/index.html` → Open with Live Server → 打开 `http://127.0.0.1:5500/web/index.html`
2. 依次输入四组回归数据并点"分析环境"：25/60 → 正常；16/60 → 偏冷；31/60 → 偏热；25/80 → 偏湿。**预期**：状态/建议逐条正确，底部带时间戳历史逐条追加
3. 点"导出 CSV" → 保存到 `data/open01.csv`（输入、处理、输出真实发生的第一段证据）
4. 终端运行：`python analysis/analyze.py data/open01.csv --out data`
5. **验证**：控制台打印统计（记录数/温湿度最高最低/各状态数量/关注记录）；`data/trend.png` 重新生成；打开 `data/report.html` —— 摘要、关注记录、事件复盘（A4）、ML 异常分析（C3）、趋势图五区齐全。若先做完第三章 A 闭环再跑本步，"事件复盘"区会出现刚处理的事件

### 2. 本机交互抽查（Camera / ASR / TTS）

- Camera：web 页点"打开摄像头" → 授权 → 点"保存快照"得到现场照片
- ASR：按 Win+H 开系统语音输入，说"朗读状态" → 语音指令框出现识别文字 → TTS 朗读当前状态（如"当前状态：偏热，注意通风"）；说"拍照" → 触发快照下载。ASR 等价方案原因见 README 已知限制

### 3. 实时链：Broker → simulator → Dashboard → 3D → MQTTX

1. 启动 Broker：`D:\Mosquitto\mosquitto.exe -c D:\Mosquitto\mosquitto.conf -v`（conf 需含 listener 1883、listener 8083 + protocol websockets、allow_anonymous true；启动日志出现两个端口）
2. 启动模拟节点：`python simulator/simulate.py` → 控制台可见 dorm-a/b/c 每 2.5s 发布一条六字段 JSON
3. Live Server 打开 `dashboard/index.html` → 三卡片同屏实时刷新、tab 切换各节点趋势图、顶部总览条成句；**预期**：卡片显示的宿舍与数据源严格对应（不串线）
4. Live Server 打开 `three3d/index.html` → 三栋楼状态色随消息变化（正常绿/偏冷蓝/偏热橙/偏湿青），点击楼选中并显示侧栏详情
5. MQTTX：新建连接 `127.0.0.1:1883` → 订阅 `dormmate/#` → 手发一条六字段 JSON（如 `{"nodeId":"dorm-b","temperature":31,"humidity":60,"status":"","time":"2026-09-30 10:00:00","action":""}`）到 `dormmate/dorm-b/env` → **预期**：Dashboard 卡片与 3D 楼色立刻变化（实时 JSON 驱动 3D 的直接证据）

### 4. 移动端独立运行

- 微信开发者工具 → 导入 `mobile/` 目录 → AppID 选"测试号" → 编译运行 → 输入 31/60 → **预期**：偏热 + 注意通风；Console 自动打印 4 行回归 PASS。移动端复用同一套统一规则（mobile/utils/rules.js）

### 5. A/B/C 闭环复验（一键自动，均 0 失败才算过）

- A 闭环（14 项断言）：`python simulator/test_final.py --a-loop` —— 偏热 → 优先横幅 → 开风扇 → 3D 联动 → 降温新数据 → 已恢复 → 自动关扇 → 事件导出 → 报告复盘
- B 信息闭环（11 项断言）：`python simulator/test_final.py --b-loop`
- C 对照复现（8 项断言）：`python simulator/test_final.py --c-repro`（random_state=42，与已提交 c_compare.json 逐字段一致）
- 手工重演版见 README 运行方式 A/B/C 段（Dashboard 剧本 ①-⑥）；运行截图一键重出：`python simulator/capture_abc.py`

### 6. 收尾关闭

- Ctrl+C 停 simulator → Ctrl+C 或任务管理器停 Broker → 关闭浏览器页面

---

## 第二章 Open-01 四项自测操作（自测②③④）

### 自测②【说明】选一个模块讲数据流 —— 现场话术（约 1 分钟，照读）

> 我讲"实时系统链"这个模块。数据从哪里来：`simulator/simulate.py` 模拟三个宿舍节点，每个节点用随机游走生成温湿度，再用统一规则算出状态，组装成六字段 JSON（nodeId、temperature、humidity、status、time、action），通过 paho-mqtt 发布到 `dormmate/{nodeId}/env` 主题，本机 Mosquitto Broker 负责转发。数据经过哪些步骤：Dashboard 和 3D 页面各自通过 mqtt.js 走 WebSocket（8083 端口）订阅这三个主题；每条消息先过一道校验链——是不是合法 JSON、六个字段齐不齐、topic 里的节点名和消息里的 nodeId 对不对得上，非法消息直接丢弃并计数；通过校验后，页面重新计算状态并更新界面。产生什么结果：Dashboard 三张卡片、总览句、依据卡片实时刷新；3D 里楼的颜色、粒子、标牌跟着状态变。所以你在 MQTTX 手发一条 31 度的消息，两秒内两张页面都会同时反应——这就是这条链路的输入、处理和输出。

### 自测③【修改】改 3D 状态颜色映射（改完必须还原）

1. **改哪**：`three3d/app.js` 第 22 行，状态映射表 `STATUS_STYLE` 里"偏热"的楼体主色：`"偏热": { body: 0xe67e22, ... }` —— 把橙色 `0xe67e22` 改成红色 `0xff0000`，保存
2. **验证**：浏览器**刷新** `three3d/index.html`（必须刷新）；用 MQTTX 向 `dormmate/dorm-b/env` 手发一条 31℃/60% 的六字段 JSON → **预期**：dorm-b 楼体从橙色变成红色（楼顶热气粒子同色）——截图留证
3. **还原**：把 `0xff0000` 改回 `0xe67e22` → 保存 → 刷新页面确认恢复橙色
4. **收尾**：终端 `git status` 确认 three3d/app.js 无改动（`git diff -- three3d/app.js` 为空）

### 自测④【排错】停止 Broker（可控故障，练完恢复）

1. **制造故障**：任务管理器结束 `mosquitto.exe`（或启动 Broker 的终端按 Ctrl+C）
2. **现象**：Dashboard 与 3D 页顶部的连接状态在几秒内变红"未连接 / 重连中"，三卡片与 3D 停止刷新——系统失去数据源
3. **定位原因**：两个页面都通过 `ws://localhost:8083` 连 Broker（MQTT over WebSocket）；Broker 停止 = 转发中断。控制台 Network 面板可见 WebSocket 断开重连循环；页面横幅会显示断线提示
4. **修复**：重新执行 `D:\Mosquitto\mosquitto.exe -c D:\Mosquitto\mosquitto.conf -v`
5. **确认恢复**：两个页面**自动**回到"已连接"（不用刷新页面），三卡片恢复刷新、3D 恢复响应——截图留证"断开→恢复"两个瞬间
6. **收尾**：`python simulator/test_b1.py` 回归 0 失败

> 练习红线：自测③④ 都是"为测试而改"的改动，完成后必须还原、回归通过，保证提交的稳定版不受影响。

---

## 第三章 验收核对清单（提交前最后一遍，对应截图 61/62/65）

### A | 项目与版本

| 条目 | 状态 | 证据 |
|---|---|---|
| GitHub 仓库可访问 | ✅ 已同步 | 仓库 sz-Echo/nova-dormmate-final-2026，master = 9b2f093（网络时断时通，若当天不可达则稍后重试 push） |
| Challenge 期间 ≥3 次有意义 Commit | ✅ 38 个 | 本地 git log（09-25~09-29 五天分布）；GitHub 同步后远端一致 |
| README 含运行方法/功能说明/开源组件来源/已知限制 | ✅ | README 四节 + 新增"开源组件"15 行表格 |
| 当前最终稳定版已提交并同步 GitHub；关闭状态能按 README 重启 | ✅ | 84e0fb4 + 本指南第一章（Final 复验 62 断言全过） |

### B | M1-M6 工程链（截图 62 逐条）

| 条目 | 状态 | 证据 |
|---|---|---|
| web：输入/校验/规则/状态建议/时间戳历史 | ✅ | web/index.html + test.html 四组回归 |
| web/Python/移动端/MQTT JSON/Dashboard/3D 同一套字段与统一规则 | ✅ | 六端均复用 computeStatus/compute_status/rules.js（零重写） |
| CSV 可打开；Python 能重新读取新 CSV | ✅ | analyze.py 自动选最新 CSV + 指定路径模式 |
| 能重新生成摘要/批量规则结果/trend.png/report.html | ✅ | analyze.py + daily_summary.py |
| camera 现场快照；ASR ≥1 条固定指令触发功能；TTS 朗读动态状态 | ✅ | Win+H 等价 ASR（README 记录原因） |
| 移动端 DormMate 完成输入→判断→状态/建议 | ✅ | mobile/（用户实测通过） |
| 本机 Broker 可从关闭状态启动；≥3 模拟节点；Dashboard 实时更新且不串线 | ✅ | Mosquitto 2.1.2 + simulator 三节点 + 串线防线 |
| 3D ≥2 对象；≥3 类状态可见变化；实时 JSON 驱动 3D | ✅ | 35+ 对象；四类变化（主色/指示球/粒子/标牌）；MQTTX 手发即变 |
| 1 个自主小改进 + 改动前后说明 | ✅ | M6：Edge 鼠标手势防御等（docs/evidence/m6/） |

### C | A/B/C 收口（截图 61）与最终检查（截图 65）

| 条目 | 状态 | 证据 |
|---|---|---|
| A：完整跑通 ≥1 次"发现→判断→处理→新数据验证→复盘" | ✅ | test_final --a-loop 14 断言；events.json + report 事件复盘区 |
| B：总览/依据/今日摘要由真实数据/事件自动生成；≥3 类表达入口分工 | ✅ | Dashboard/3D/TTS/report.html 四入口；--b-loop 11 断言 |
| C：能从历史数据重新产生 ML 判断，与 Rule 对照；结果回到 report.html；≥1 个真实不理想案例 | ✅ | --c-repro 8 断言（逐字段复现）；report ML 异常分析区；27.5℃/70% 案例 |
| 关闭程序后按 README 从头重启 ≥1 次 | ✅ | Final 复验 + 本指南第一章 |
| Open-01 四项自测（启动/说明/修改/排错） | ✅ 已完成（2026-09-30） | 冷启动复验 62 断言全过；改 3D 颜色已还原（git diff 干净）；停 Broker 断连→重启自动恢复（回归 0 失败）；现场截图由本人留存 |
| 通过 Open-01 后不再扩展 DormMate，进入 S03-A（迁移能力而非复制工程） | ✅ 已确认 | 用户确认 |

### 缺口与处理

| 缺口 | 处理 |
|---|---|
| GitHub 远端当日不可达（网络时断时通） | 提交后重试 push（先展示命令）；不重试轰炸 |
| docs/PLAN.md 最近Commit 行 | 本次收尾提交时更新为实际哈希 |
| docs/evidence/m4/ 无截图 | 截图非 M4 完成线要求；证据以 review 归档 + 用户实测记录为准（文档口径已统一） |

---

# V0.8R5 现场验收自测（任务书 p22-23：Run / Explain / Modify / Debug / Verify）

> 2026-10-01 起，随 UPGRADE_PLAN 阶段 D 执行。现场验收五项，本文为陪跑文档。
> 演示前必做：README「演示前重置系统状态」（清空 events.json → 重启 Broker/simulator → 刷新页面）。
> 现场只开一个 Dashboard（多实例会互相覆盖事件广播）。

## 第一章 Run：冷启动演练（D1，2026-10-01 已演练通过）

按 README 第四节冷启动清单从关闭状态执行（每步含预期）：

| 步骤 | 命令 / 操作 | 预期 | 2026-10-01 演练 |
|---|---|---|---|
| 0 关闭状态 | 确认无 mosquitto/simulator/http.server 进程、无 Dashboard 页面 | 端口 1883/8083/5510 无监听 | ✅ |
| 1 Broker | `D:\Mosquitto\mosquitto.exe -c D:\Mosquitto\mosquitto.conf -v` | 1883/8083 listener 就绪 | ✅ |
| 2 模拟节点 | `python simulator/simulate.py` | 约每 2.5 秒三节点发布六字段 JSON | ✅ |
| 3 静态服务 | 项目根 `python -m http.server 5510` | Serving HTTP on port 5510 | ✅ |
| 4 Dashboard | 打开 `http://127.0.0.1:5510/dashboard/` | 已连接 + 三卡片刷新 + 趋势图 | ✅（截图 docs/evidence/upgrade/d1-dashboard.png） |
| 5 3D | 打开 `http://127.0.0.1:5510/three3d/` | 已连接 + 三栋楼状态色随消息变化 | ✅（截图 docs/evidence/upgrade/d1-3d.png） |
| 6 移动端 | 开发者工具编译 mobile/（需人工 GUI） | 三节点卡片与 Dashboard 数值一致 | 人工步骤（E3 补拍证据已覆盖） |
| 7 离线链 | web 页四组回归 + 导出 CSV → `python analysis/analyze.py` | 四组全对 + report.html 生成 | ✅（回归四组全过） |
| 收尾 | 按第 6 章关闭；`git status` 干净 | data/ 无改动 | ✅ |

## 第二章 Explain：随机功能说明话术（D2）

现场被随机指定一个功能时的回答框架（三步）：

1. **数据从哪来**：`simulator/simulate.py` 三节点随机游走 → 统一规则算 status → 六字段 JSON → `dormmate/{nodeId}/env`（MQTT 1883/8083）。
2. **什么处理**：各端订阅后过校验链（JSON 合法 / 六字段 / topic↔nodeId 一致 / 范围）→ **本地规则重算 status（不信任消息值）** → 更新界面；事件状态经 Dashboard 状态机广播 `dormmate/{nodeId}/event`。
3. **为什么是这个结果**：优先横幅 = 连续异常时长 → 次数 → nodeId 顺序；已恢复 = 连续 ≥2 条正常新数据（按钮不能改）；3D 楼色 = 本地重算的状态映射。

## 第三章 Modify：5 个预演用例（D3，改完必须还原 + 复跑验证）

| # | 用例 | 改哪 | 验证 | 还原 |
|---|---|---|---|---|
| 1 | 改状态阈值 | `web/script.js` computeStatus 的 30 改 29（或 dashboard 同源） | 输入 29.5℃ 由"正常"变"偏热" | 改回 30 |
| 2 | 改移动端显示字段 | `mobile/pages/index/index.wxml` 卡片加一行字段 | 模拟器显示新字段 | 还原 |
| 3 | 加 ASR 指令 | `dashboard/app.js` DASH_VOICE_COMMANDS 加一条（如"查看全部"） | 语音输入新指令有反应 | 删除 |
| 4 | 改 3D 状态映射 | `three3d/app.js` STATUS_STYLE 偏热主色 0xe67e22 → 0xff0000 | 刷新后偏热楼体变红 | 改回 |
| 5 | 调优先规则 | `dashboard/priority.js` 交换 ①② 比较顺序（次数优先） | test-priority.html 对应组结果变化 | 改回 |

## 第四章 Debug：5 个可控故障预演（D4，2026-10-01 已预演 1-4，证据入 Evidence/Debug/）

| # | 故障 | 现象（实测） | 定位 | 修复 | 验证 |
|---|---|---|---|---|---|
| 1 | Topic 写错（`dormmate/dorm-x/env`） | ✅ 预演：丢弃计数 +1 告警——Dashboard 订阅 `+/env` 通配符能收到，校验链"未知节点 dorm-x"防线拦截 | 对比契约表 Topic 格式 + 未知节点防线 | 改回 `dormmate/{nodeId}/env` | 卡片更新（d4-debug1-wrong-topic.png） |
| 2 | JSON 字段错（缺 humidity） | ✅ 预演：横幅"消息缺少字段 humidity" + 丢弃计数 +1 | 校验链六字段检查 | 补全字段重发 | 恢复更新（d4-debug2-missing-field.png） |
| 3 | Broker 停 | ✅ 预演：连接状态变"已断开，重连中…" | ws://8083 断开 | 重启 Broker | 自动重连恢复（d4-debug3-broker-down.png / d4-debug3-broker-recovered.png） |
| 4 | 3D 节点映射错（mesh dormId 篡改） | ✅ 预演：点击 dorm-a 楼位置无法正确选中 | 对照 tagDorm 标签映射 | 还原映射（重载） | 选中恢复 dorm-a（d4-debug4-wrong-mapping.png） |
| 5 | 移动端不同步（域名校验未勾选） | 小程序连不上 8083 报错 | 开发者工具设置 | 勾选"不校验合法域名…" | 卡片实时更新（GUI 步骤，现场演示验证） |

## 第五章 Verify：自动化断言与最终完成线（D5）

- 全绿清单：`python simulator/test_final.py`（62 断言）+ `python simulator/test_upgrade.py`（14 项端到端）+ `python simulator/test_stage_b.py`（五套件）+ 回归四例（web/test.html / --selftest）
- 任务书 §10 最终完成线逐条勾选（D1-D5 全完成 / 两链真实跑通 / E1-E3 全完成 / D3 事件生命周期 / 三端一致 / ≥1 故障修复 / ≥1 Rule-ML 对照 / GitHub 完整 ≥5 commit / Evidence 可追溯 / 交叉复现三件套 / PPT 10-15 页 / 技术文档 10-15 页 / 视频 5-8 分钟 / 现场核验五项）
