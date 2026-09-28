# M5 详细执行计划 — MQTT 实时系统（本机 Broker + 三节点 + Dashboard）

> 依据：docs/DORMMATE_SPEC.md、docs/PLAN.md、任务书 M5 原文（第 20 条起，条目编号 S0 已按用户截图确认口径）。本文件是 M5 期间的执行依据，随进度更新；与 SPEC/PLAN 冲突时以 SPEC 为准。

## 1. 决策记录（已与用户确认）

- **模拟节点方式**：simulator/ 程序自动发布 3 节点（SPEC §7/§8 设计）+ MQTTX 现场演示手动发布一条消息模拟节点（兼顾任务书关键词"用 MQTTX 模拟至少 3 个宿舍节点"）
- **技术栈**：Python + paho-mqtt（`pip install paho-mqtt`）；**规则零重写**——simulator 直接 import analysis/analyze.py 的 `compute_status` / `selftest`（四组回归经 selftest 复用 M2 同一组 REGRESSION_CASES）
- **Dashboard**：单页 HTML + mqtt.js + Chart.js（本地 vendor 文件，防国内 CDN 不稳）；**规则零重写**——直接 `<script src="../web/script.js">` 复用 M1 的 `window.computeStatus` / `ADVICE`（script.js 顶层无 DOM 操作、绑定均有存在性检查）
- **Broker**：Mosquitto Windows 版（装 D 盘，mosquitto.conf 以实际探测路径为准，不假定 C:\Program Files）；`listener 1883`（TCP，模拟节点发布）+ `listener 8083` + `protocol websockets`（浏览器 Dashboard）+ `allow_anonymous true`（本机演示）
- **端口冲突防范（评审修正 ①）**：S1 先执行 `netstat -ano | findstr 8083` 检查占用；被占用则换端口，并在 mosquitto.conf 与 dashboard/app.js 同步修改
- **断线重连（评审修正 ②）**：mqtt.js 连接配置 `reconnectPeriod: 2000`——S5 演示"关闭 Broker 再重启"时浏览器自动恢复连接（冷启动验收必需）
- **JSON 容错（评审修正 ③）**：收到消息 JSON.parse 包 try...catch + 字段齐全校验（nodeId/temperature/humidity/status/time/action 六字段）；坏消息在页面明确警告并计数，不白屏
- **内存清理（评审修正 ④）**：每节点历史缓存上限 60 条，代码实际裁剪（超出 shift 移除最旧），防长期运行内存溢出
- **验收口径**：按任务书条目组织验收清单（编号 S0 对照截图核对）；三节点必须同时在线、互不串线（SPEC §12）

## 2. 范围红线（M5 不做）

- 不做公网 / 共享 Broker（SPEC §13 约定 4）；不做数据库、不落盘 CSV（实时链内存态）
- 不做 A1 优先关注计算（A 组阶段做；M5 只提供每节点历史数据基础）；action 仍恒 ""（A2 起写入）
- 不改 web/、mobile/、analysis/、data/ 代码（analysis/analyze.py 仅被 import，零改动）
- M5 起三节点 dorm-a / dorm-b / dorm-c 必须同时在线、互不串线（SPEC §12）

## 3. 执行步骤（每步完成停下等用户确认）

### S0 文档对齐 ✅ 已完成（2026-09-27：本文件创建 + PLAN 看板更新；3 项决策 + 4 项评审修正经用户确认）

### S1 环境（用户 + 我配合；安装包已下载、paho-mqtt 已装，待配置与启动）

- 状态（2026-09-27）：Mosquitto 2.1.2 已装 **D 盘**；MQTTX 1.13.0 便携版已就绪；paho-mqtt 2.1.0 已 pip 装好 ✅
- **先探测实际 mosquitto.conf 路径**（改配置与冷启动命令都用实际路径，不再假定 C:\Program Files）
- **端口冲突检查**：`netstat -ano | findstr 8083` 与 `netstat -ano | findstr 1883`（任一被占用则换端口，mosquitto.conf 与 dashboard/app.js 同步修改）
- 注意：安装时若勾选了"作为 Windows 服务运行"，先停用该服务（services.msc → Mosquitto Broker → 停止），否则手动 `-v` 启动会端口冲突
- mosquitto.conf 末尾追加：`listener 1883` / `listener 8083` + `protocol websockets` / `allow_anonymous true`
- 冷启动验证：`mosquitto -c "<实际路径>\mosquitto.conf" -v` → 关闭后重新启动正常
- MQTTX：解压后运行 → 连接 127.0.0.1:1883 → 手动收发互测（MQTTX 发一条 → 自己订阅收到，验证 broker 通）

### S2 simulator/simulate.py ✅ 已完成（2026-09-27：--selftest 四组回归 4/4；真实 Broker 发布经 mosquitto_sub 订阅验证通过）

- 3 节点发布（threading，每节点独立 topic / JSON / 随机游走）；统一 JSON = SPEC §4（status 由 compute_status 计算，action ""，time 全格式）
- 数据生成：每节点随机游走，温度 15~35、湿度 40~90 范围内波动（SPEC §3.1 子集），间隔 2-3 秒（`--interval` 可调）
- `--selftest`：SPEC §6 四组回归（import analysis 的 selftest，与 M2 同一组回归数据）
- Ctrl+C 停止；控制台输出每条发布日志（topic + JSON）

### S3 dashboard 骨架 ✅ 已完成（2026-09-27 用户浏览器实测：绿色已连接 ws://localhost:8083、收到数增长、三卡片实时数据）

- vendor：`dashboard/vendor/mqtt.min.js`（mqtt.js v5 UMD）+ `chart.umd.min.js`（Chart.js v4，S4 用）本地文件（下载指引由我给，备选 CDN）
- dashboard/index.html + style.css + app.js：
  - mqtt.js 连 `ws://localhost:8083`，`reconnectPeriod: 2000` 断线自动重连
  - 订阅 `dormmate/+/env`；从 topic 提取 nodeId；**串线防线**：校验消息内 nodeId 与 topic 一致，不一致丢弃并警告计数
  - **JSON 容错**：JSON.parse try...catch + 六字段齐全校验，坏消息页面警告 + 计数，不白屏
  - 三卡片同屏（节点名 / 状态大字 / 最新温湿度 / 建议 / 更新时间）实时刷新

### S4 趋势与切换 ✅ 已完成（2026-09-27 用户实测：tab 切换趋势、串线拦截红色横幅+丢弃计数、缺字段拦截均通过；首测失败排查结论：MQTTX 未连接时发送消息根本没进 Broker，app.js 无 bug——粘性横幅 + payload 解码加固后复测通过；MQTTX 自动重连默认关闭，演示时先确认连接为绿色）

- Chart.js 每节点趋势图（温度 + 湿度双线），tab 切换查看节点
- 每节点历史缓存上限 60 条，超出 shift 裁剪最旧记录
- 页面顶部状态栏：连接状态 / 收到消息数 / 丢弃（坏 JSON + 串线）消息计数

### S5 验收 + 交接 🔄 进行中（README / 看板 / 证据已更新；待用户确认提交与 GitHub 同步）

- 验收清单走查 + 冷启动全链路复跑（关闭所有进程 → Broker → simulator → Dashboard → MQTTX）
- 截图证据 docs/evidence/m5/（三节点同屏 / MQTTX 订阅日志 / 切换趋势 / 冷启动 / 手动发 16/60 → 偏冷）
- README 补 M5 运行方式（Broker 启动命令、simulator、Dashboard ws 地址、MQTTX 验证）
- PLAN 看板收口；提交（先展示变更摘要，用户确认）；GitHub 同步（先展示命令，用户确认）

### S6 评审修复（code-review 10 角度，8 项确认发现） ✅ 已完成（2026-09-27 用户复测通过：4 种坏消息矩阵——null / 非对象 / time 非法 / 越界数值 / 串线——每种均红色横幅 + 丢弃计数、页面不崩不白屏；边界自洽性 29.96→30.0 偏热 等验证通过；证据 s5-badmessage-matrix.png）

- simulator/simulate.py：① build_message 先 round 再用舍入值算 status（修边界自相矛盾，如 29.96→30.0 却 status 正常）② connect_async + max_queued_messages=5（修 Broker 未启动时启动崩溃 + 断连期无界排队）③ publish 返回值检查，未连接如实提示丢弃 ④ --interval 校验 >0 ⑤ join 替代 sleep 循环（线程死亡不假装存活）⑥ Ctrl+C 优雅断开 DISCONNECT
- dashboard/app.js：① JSON 解析结果加对象类型守卫（null/数字/字符串不再抛 TypeError）② time 类型 + 格式校验（防趋势图冻结）③ 范围校验复用 window.validateInputs（含 NaN/Infinity 拦截，与全项目 §3.1 口径统一）④ record 恢复 SPEC §4 六字段（action 保留，advice 改为渲染时查表）⑤ 卡片/tab 建一次增量更新、图表增量追加（去全量重建）⑥ TextDecoder 单例 ⑦ 规则模块缺失防御提示 ⑧ drop 带时间戳
- dashboard/index.html：注释修正（script.js 实际导出 computeStatus / ADVICE / validateInputs）
- 不采纳（理由）：analysis/analyze.py 加 TIME_FORMAT 常量（M5 红线不改 analysis/）；window.showMsg 导出复用（红线不改 web/script.js）；dropLog 明细数组（时间戳横幅已满足演示证据需要）；decodePayload 三分支删除（已简化为单例直解）
- **检查点（用户）**：模拟器/看板复测 + 按 S5 演示剧本重走串线/坏消息/冷启动
- **追加修复（2026-09-28，用户实测模拟器报错后）**：① 删除 `max_queued_messages` 构造参数（paho 2.x 无此参数且已移除队列，H 角度建议按 1.x 老 API 写出，落地报 TypeError）② publish 检查改回 `result.rc != MQTT_ERR_SUCCESS`（`is_published()` 失败时抛 RuntimeError 而非返回 False）③ connect_async 后等待首次连接成功再启动发布线程（防首批消息赶在连接建立前被丢弃）。教训：评审建议落地前须过 API 文档核验

## 4. 关键设计 — 与 M1-M6 / A / B / C 联系

| 阶段 | 联系 |
|---|---|
| M1 | Dashboard 直接引入 web/script.js 复用 computeStatus / ADVICE（同一实现，非移植）；四组回归同一组数据 |
| M2 | simulator import analysis/analyze.py 的 compute_status（Python 规则单源，零重写）；离线链（CSV→trend/report）不受影响 |
| M3 | 无直接接口；GitHub 同步沿用 M3 建立的 nova remote + subtree push 机制 |
| M4 | 小程序 M5 起可选订阅 MQTT（mobile/pages/index/index.js 已留注释预留点）；M5 不强制做小程序订阅 |
| M6 | 3D 场景订阅同一 MQTT 数据流（dormmate/+/env）；Dashboard 的 mqtt.js WebSocket 连接为 M6 提供样板 |
| A | A1 优先关注依赖 M5 三节点数据（Dashboard 每节点历史按 time 分组，供 A1 计算连续异常时长）；action 字段 M5 仍 ""，A2 起写入；M5 不做 A1 本身 |
| B | M5 证据（截图 / MQTTX 订阅日志）是 B 组程序化说明素材 |
| C | 无直接接口（C 复用离线链 CSV + report.html） |
| Final | 实时链 = 模拟节点→MQTT→Dashboard→3D；冷启动复验从 Broker 开始 |

## 5. 验收清单（任务书条目 + SPEC §8 完成线 + 项目门禁）

1. **本机 Broker 从关闭状态启动**（冷启动：关闭 mosquitto → 重新启动 → Dashboard 自动重连恢复实时数据）
2. **3 个节点的 JSON 实时进入 Dashboard**（三节点同屏、实时刷新、互不串线）
3. **正确区分 / 切换**（topic + nodeId 双校验防串线；tab 切换查看各节点）
4. **分别显示当前状态和趋势**（状态大字 + 建议随规则；Chart.js 每节点温度/湿度趋势图）
5. **关键词落地**（MQTT / local Broker / Mosquitto / Topic / Publish-Subscribe / JSON / MQTTX / mqtt.js / WebSocket / Chart.js / Dashboard，现场能指出每个对应哪段代码 / 配置）
6. **项目门禁**：SPEC §6 四组回归（simulator --selftest + Dashboard 复用 script.js）；证据截图 + MQTTX 订阅日志 docs/evidence/m5/；README 补 M5；提交 + GitHub 同步

（条目编号 S0 已按用户截图确认口径组织；如截图编号有出入，以截图为准修正。）

## 6. 现场演示剧本（S5 照着走）

**准备**：关闭所有进程（mosquitto / simulator / Dashboard）；确认 mosquitto.conf 三行配置在。

1. **冷启动（任务书）**：`mosquitto -c "<实际路径>\mosquitto.conf" -v`（D 盘安装目录探测到的实际路径）→ 日志显示监听 1883 / 8083
2. **模拟节点**：`python simulator/simulate.py` → 日志显示 dorm-a / dorm-b / dorm-c 按 topic 定时发布统一 JSON
3. **Dashboard**：Live Server 打开 dashboard/index.html → 三卡片同屏实时刷新（状态 / 建议随数据变化）
4. **MQTTX 订阅（证据）**：MQTTX 连接 127.0.0.1:1883 → 订阅 `dormmate/#` → 看到 3 节点 JSON 流（截图作订阅日志）
5. **MQTTX 模拟节点（任务书关键词）**：MQTTX 手动 publish 一条 `dormmate/dorm-c/env` 消息 → Dashboard dorm-c 卡片即时更新
6. **区分 / 切换**：点 tab 切换 dorm-a / dorm-b / dorm-c → 各节点独立趋势图；MQTTX 发一条 topic 与 nodeId 不一致的消息 → Dashboard 丢弃并在状态栏警告（不串线演示）
7. **状态正确性亮点**：MQTTX 手动发 16/60 → dorm-a 变"偏冷 + 注意保暖"（规则实时生效）

## 7. 验证方式

- simulator：`python simulator/simulate.py --selftest` 四组回归全过
- Dashboard：浏览器 Console 无报错；三卡片内容与 MQTTX 订阅一致；坏 JSON / 串线消息被丢弃且页面警告
- 冷启动全链路复跑（Broker→simulator→Dashboard→MQTTX）＋ 证据截图 → docs/evidence/m5/

## 8. 风险

- **8083 WebSocket 未配置 / 端口冲突**（最关键，浏览器连不上会卡住）→ S1 先 `netstat -ano | findstr 8083` 查占用，冲突换端口并同步两处配置
- 端口占用 / 防火墙 → 本机 127.0.0.1 回环一般不受拦；跨设备才需放行 1883/8083
- 三节点串线 → topic + nodeId 双校验 + 独立 topic（SPEC §12）
- Broker 重启后浏览器不自动重连 → mqtt.js `reconnectPeriod: 2000`（已内置）
- mqtt.js / Chart.js CDN 不稳 → vendor 本地文件
- paho-mqtt 未装 → `pip install paho-mqtt`（S1 完成）
- 模拟数据越界 → 生成范围约束在 SPEC §3.1 内
