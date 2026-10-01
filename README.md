# DormMate Final（nova-dormmate-final-2026）

## 项目是什么、解决什么问题

宿舍环境助手——**一个系统、两条数据链、多端协同、事件闭环**：

- **解决的问题**：宿舍温湿度"现在该看谁、怎么处理、处理完怎么验证、事后怎么复盘"，从单条记录判断到多宿舍持续监测的完整闭环。
- **两条数据链**：
  - **离线分析链**：Web 页输入温湿度 → 统一规则判断 → CSV 导出 → Python 离线分析 → report.html 报告（摘要 / 趋势 / 事件复盘 / ML 异常分析）
  - **实时系统链**：simulator 三节点（dorm-a/b/c）模拟温湿度 → MQTT Broker → Dashboard（实时看板）/ 3D（数字孪生）/ 移动端（微信小程序）三端订阅同一套实时状态
- **核心能力**（V0.8R5 综合作品阶段）：
  - D1 多节点稳定运行：三节点同时在线不串线，多端随新消息实时更新
  - D2 持续异常与优先关注：程序化规则判断"现在先看谁"，可解释、可重复、换数据可变
  - D3 处理→验证→恢复：异常事件从发现、处理走到后续数据验证与恢复/未恢复的完整生命周期
  - D4 实时链路故障与修复：坏 JSON 拦截告警、自动重连、真实故障可定位可修复
  - D5 固定规则与 ML 对照：IsolationForest 与固定规则双判断并排展示（辅助判断，不替代规则）
  - E1 3D 数字孪生：三栋宿舍楼 + 状态色/粒子/标牌 + 优先光环 + 事件徽标 + 镜头聚焦 + 事件回放
  - E2 Camera/ASR/TTS：Dashboard 语音命令条（查看节点 / 朗读状态 / 拍照 / 开关风扇），快照与事件关联
  - E3 web-移动端同步：移动端订阅同一 MQTT 数据流，共享事件状态，移动操作可联动到 web/3D

## 一、环境要求与关键软件版本

| 软件 | 版本 | 用途 |
|---|---|---|
| Windows | 11 | 本机开发与运行环境 |
| Python | 3.14 | analysis/ + simulator/ 全部脚本 |
| Mosquitto | 2.1.2 | 本机 MQTT Broker（安装目录 `D:\Mosquitto\`） |
| 浏览器 | Edge（最新） | Dashboard / 3D / web 页运行；TTS 中文语音、Camera 需要浏览器支持 |
| 微信开发者工具 | 官方最新版 | mobile/ 小程序运行与验收（无需注册 AppID，选"测试号"） |
| MQTTX | 1.13.0 便携版 | MQTT 客户端工具（手动发消息验证/演示，可选） |

## 二、项目目录结构

```
nova-dormmate-final-2026/
├── web/                离线链入口：温湿度输入 → 状态判断 → CSV 导出（单宿舍表单页）
├── analysis/           离线分析脚本：analyze.py（报告管线）/ c_ml.py（IsolationForest）/ 数据生成脚本
├── simulator/          三节点模拟器（simulate.py）+ 全部验证脚本（test_*.py）+ 演示录制脚本
├── dashboard/          实时看板：三卡片 + 优先横幅 + 事件面板 + 语音命令条（纯静态 HTML/JS）
├── three3d/            3D 数字孪生：三栋宿舍楼 + 状态可视化 + 回放（Three.js 本地 vendor）
├── mobile/             微信小程序：三节点快查 + 事件徽标 + 开风扇操作（手写极简 MQTT 客户端）
├── data/               数据产物：CSV、trend.png、report.html、c_compare.json、events.json、sim-day-*/
├── docs/               规格与计划：SPEC、PLAN、各阶段计划、升级计划、技术文档、C01 证据
├── Evidence/           综合作品阶段证据：D1-D5 / E1-E3 / Debug / Reproduce（含索引 README）
└── README.md           本文件
```

## 三、依赖安装与必要配置

### Python 依赖（离线分析 / 模拟器 / 验证脚本 / 演示录制）

```
python -m pip install pandas matplotlib paho-mqtt numpy playwright imageio-ffmpeg edge-tts
python -m playwright install chromium
```

### Mosquitto Broker 配置

`D:\Mosquitto\mosquitto.conf` 需包含：

```
listener 1883
listener 8083
protocol websockets
allow_anonymous true
```

### 微信开发者工具配置

"导入项目"选择 `mobile/` 目录（项目已带测试 appid `wxd7c27e7d8b4c53e1`，导入时保持默认即可，无需改选）；详情 → 本地设置 → 勾选"不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书"（选项名称以当期版本为准）。移动端编译与同步核验需人工 GUI 操作（导入 → 勾选 → 编译），无法脚本化自动验证。

## 四、完整启动顺序（冷启动清单）

1. **启动 Broker**：`D:\Mosquitto\mosquitto.exe -c D:\Mosquitto\mosquitto.conf -v` → 预期看到 1883 / 8083 两个 listener 就绪日志
2. **启动模拟节点**：项目根目录运行 `python simulator/simulate.py` → 预期控制台约每 2.5 秒滚动三条 `dormmate/{nodeId}/env -> {...}` 发布日志
3. **启动静态服务**：项目根目录运行 `python -m http.server 5510` → 预期 `Serving HTTP on :: port 5510`
4. **打开 Dashboard**：浏览器访问 `http://127.0.0.1:5510/dashboard/` → 预期三卡片约每 2.5 秒刷新一次温湿度
5. **打开 3D**：浏览器访问 `http://127.0.0.1:5510/three3d/` → 预期三栋楼颜色随状态变化、粒子动画运行
6. **打开移动端**：微信开发者工具编译 `mobile/` → 预期三节点卡片与 Dashboard 数值一致，随新消息刷新

> 注：① Dashboard/3D/web 均为纯静态页面，任何 localhost 静态服务皆可（第 3 步的 5510 端口为项目验收脚本统一约定）；VS Code Live Server 也可用，但注意其监视工作区文件变化，证据截图写入会触发页面重载（见"常见问题"）。② web 页的 Camera 功能要求 localhost 或 https，file:// 双击打开会被浏览器禁用。

### 演示前重置系统状态（正式演示/现场验收必做）

演示效果依赖干净的系统状态，按以下顺序重置，确保事件面板从空白开始实时生成、横幅干净、丢弃计数为 0：

1. **清空事件数据**：`git checkout -- data/events.json`（或删除该文件后重新导出）——清除历史演示/测试遗留的事件，报告"事件复盘"区不再混入旧数据
2. **重启 Broker 与模拟节点**：停掉再按冷启动清单第 1-2 步重启——页面内存态（事件/丢弃计数/横幅）随刷新清零
3. **刷新页面**：Dashboard / 3D 浏览器标签重新加载（Ctrl+F5）——丢弃计数归零、错误横幅消失
4. **核对**：事件面板空白、顶部无红色告警横幅、丢弃计数 0、"当前 3 个宿舍均正常"横幅——确认干净后才开始演示

> 演示视频录制脚本 `record_demo.py` 已内置此重置（录制前自动清空 events.json、每幕全新页面实例），录制产物不携带残留状态。

## 五、MQTT Broker 与 Topic 结构

Broker 地址：`127.0.0.1`，TCP 端口 `1883`，WebSocket 端口 `8083`（浏览器端经 `ws://localhost:8083` 连接）。

| Topic | 方向 | Payload 要点 |
|---|---|---|
| `dormmate/{nodeId}/env` | simulator → 各端 | 统一 JSON 六字段：`{nodeId, temperature, humidity, status, time, action}`；status 由统一规则计算（`<18 偏冷 → ≥30 偏热 → ≥75 偏湿 → 其余 正常`，顺序固定），各端一律本地重算、不信任消息值 |
| `dormmate/{nodeId}/action` | Dashboard / 移动端 → simulator、3D | `{nodeId, action: "fan_on"\|"fan_off", actionTime}`；fan_on 后 simulator 对该节点模拟降温趋势 |
| `dormmate/{nodeId}/event` | Dashboard → 移动端、3D | `{nodeId, eventId, state: "OPEN"\|"HANDLING"\|"RECOVERED", time, summary}`；事件状态机唯一持有者是 Dashboard，同一事件各状态共用 eventId |
| `dormmate/priority` | Dashboard → 移动端、3D | `{nodeId, reason, time}`；当前优先关注节点（nodeId 为空串 = 无重点） |

## 六、怎样产生一条测试数据

三种方式任选：

1. **MQTTX 手工发布**：连接 `127.0.0.1:1883`，向 `dormmate/dorm-b/env` 发布：

   ```json
   {"nodeId": "dorm-b", "temperature": 29.0, "humidity": 72.0, "status": "正常", "time": "2026-09-30 10:00:00", "action": ""}
   ```

   发布后 Dashboard / 3D / 移动端应同时更新 dorm-b 卡片。

   未安装 MQTTX 时，可用 paho-mqtt 一行等价发布（同一 Broker、同一 topic、同一 payload）：

   ```
   python -c "import paho.mqtt.client as mqtt, json, time; c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2); c.connect_async('127.0.0.1',1883); c.loop_start(); time.sleep(0.5); c.publish('dormmate/dorm-b/env', json.dumps({'nodeId':'dorm-b','temperature':29.0,'humidity':72.0,'status':'正常','time':'2026-09-30 10:00:00','action':''}, ensure_ascii=False)); time.sleep(1)"
   ```

2. **预设序列脚本**：`python simulator/test_a1.py --group 1`（另有 `--group 2|3|4|all`）逐组发布预设三节点序列，适合演示优先级变化。

3. **simulator 自然流**：`python simulator/simulate.py` 随机游走产生的常规数据（约每 2.5 秒一条/节点）。

## 七、怎样证明 web-移动端实时同步

1. 移动端按"依赖安装"章节完成域名校验豁免设置并编译运行。
2. 用"产生一条测试数据"的方式 1（MQTTX 手工发布），向 `dormmate/dorm-b/env` 发一条新消息。
3. 核验：Dashboard 与移动端的 dorm-b 卡片同时更新，且 nodeId / time / temperature / humidity / status 字段一致（两端均本地重算 status，规则同源）。

任务书口径：同步必须由共享数据源（MQTT）驱动，两端手输相同数据不算。

## 八、怎样快速复现 D1-D5

| 场景 | 最少操作 | 预期画面 | 对应验证脚本 |
|---|---|---|---|
| D1 多节点稳定运行 | 冷启动清单 1-6 步全部跑起 | 三端同屏显示 dorm-a/b/c 三节点最新状态，互不串线 | `python simulator/test_upgrade.py`（端到端 14 项） |
| D2 持续异常与优先关注 | `python simulator/test_a1.py --group 1` 后看 Dashboard 顶部横幅 | 优先横幅显示"优先关注 X"及原因，换 group 后优先节点随数据变化 | `python simulator/test_a1.py --group all` |
| D3 处理→验证→恢复 | Dashboard 选中异常节点 → 点"开启风扇/通风" → 等 2 条正常新数据 | "处理中"→ 连续 ≥2 条正常 → "已恢复"+自动关扇，事件面板生成完整事件（9 字段） | `python simulator/test_upgrade.py` |
| D4 故障与修复 | MQTTX 向 `dormmate/dorm-b/env` 发布一条坏 JSON（如 `{bad`） | Dashboard 控制台拦截告警、页面不受影响；重发合法消息即恢复更新 | `python simulator/test_upgrade.py` |
| D5 Rule/ML 对照 | `python analysis/c_ml.py` → `python analysis/analyze.py` → 打开 `data/report.html` | "ML 异常分析"区：当前值 / 固定规则 / ML 判断并排，差异行高亮 | `python simulator/test_c2.py` / `test_c3.py` / `test_c4.py` |

## 九、主要功能

### 离线分析链

- **输入判断（M1）**：温湿度输入 → 校验（空值 / 非数字 / 超出范围（温度 −50~50、湿度 0~100）拦截，不进入分析、不追加历史）→ 统一状态规则 → 状态 + 建议（偏冷→注意保暖 / 偏热→注意通风 / 偏湿→注意除湿 / 正常→环境舒适）→ 带时间历史（`web/index.html`；回归测试 `web/test.html` 四组数据全过）
- **CSV 导出（M2）**：历史一键导出 `dormmate.csv`（4 列最小格式 `time,temperature,humidity,status`、UTF-8 带 BOM）；历史仅存内存，刷新清空，导出 CSV 落盘
- **离线分析（M2）**：将 Web 页导出的 CSV 放入 `data/` 后，运行 `python analysis/analyze.py` 自动选 `data/` 最新 CSV 重跑统一规则 → 统计（记录数 / 温湿度最高最低 / 各状态数量 / 关注记录）→ `data/trend.png` + `data/report.html`；换新 CSV 全量重新生成；`--watch` 监控自动重跑；`--selftest` 四组回归自测
- **C 组轻量 ML（C1-C4）**：`analysis/make_c_data.py` 生成历史（40 条模拟，random_state=42）与新数据（8 组，严格分离）→ `python analysis/c_ml.py` 自实现 IsolationForest（纯 numpy，n_estimators=100、random_state=42）双判断对照 → 结果接回 report.html"ML 异常分析"区（与固定规则并排、差异高亮）。不理想案例已保留：2026-09-28 10:03 的 27.5℃ / 70%，规则判"正常"、ML 判"与历史明显不同"（分数 0.6738）——历史只有 40 条且全在 24~26℃ / 55~65% 窄区间，模型"常态"边界过窄，对轻微偏离过于敏感。ML 输出只是辅助判断，不替代固定规则

### 实时系统链

- **MQTT 实时系统（M5）**：simulator 三节点按 `dormmate/{nodeId}/env` 发布统一 JSON → Dashboard（mqtt.js + Chart.js）三卡片同屏实时刷新 + tab 切换趋势图；topic/nodeId 双校验防串线，坏 JSON / 缺字段拦截告警，Broker 重启后自动重连
- **优先关注（D2 / A1）**：按"连续异常时长 → 异常次数 → nodeId 顺序"程序计算，Dashboard 顶部横幅实时显示"优先关注 X"及原因，并经 `dormmate/priority` 广播给 3D 与移动端（测试页 `dashboard/test-priority.html`）
- **处理动作（D3 / A2）**：Dashboard"开启风扇/通风"（移动端同样可发）经 `dormmate/{nodeId}/action` 发布 → simulator 对该节点模拟降温趋势，3D 风扇转动 + 窗开；动作不直接改状态
- **恢复判断（D3 / A3）**：恢复必须由新数据触发（点击按钮不算）——fan_on 后连续 ≥2 条新数据 status==正常 才判"已恢复"并自动 fan_off；期间仍异常则保持"处理中"
- **事件生命周期（D3 / A3）**：异常开始 → 优先原因 → 处理动作 → 后续验证数据 → 恢复时间 → 最终结果由程序组装成事件记录（≥9 字段）；Dashboard 状态机唯一持有事件状态，经 `dormmate/{nodeId}/event` 广播，3D 与移动端订阅渲染同一事件（不各自维护）；"今日事件"面板可导出 `events.json` → 存入 `data/` → `python analysis/analyze.py` 后 report.html 出现"事件复盘"区
- **3D 数字孪生（M6 + E1）**：Three.js 三栋宿舍楼，四状态映射为四类可见变化（建筑主色 / 发光指示球 / 楼顶粒子（偏冷飘雪·偏湿下雨·偏热热气·正常平静）/ 中文标牌）；优先节点脉冲光环、事件状态徽标（处理中粒子加速变色）、点击/优先变化时镜头聚焦动画、侧栏"回放"按时间轴重放每节点最近记录；status 一律本地规则重算，updateScene 唯一入口驱动
- **移动端（E3 / 阶段 A）**：`mobile/utils/mqtt.js` 手写极简 MQTT 3.1.1 客户端（CONNECT/SUBSCRIBE/PINGREQ/PUBLISH/3 秒自动重连，零依赖）连 `ws://127.0.0.1:8083`；三节点卡片本地重算状态 + 当前重点标识 + 事件徽标 + "开启风扇"按钮（移动操作 → simulator 降温 → Dashboard 状态机 → 3D 风扇转，联动#1）；保留原手动输入 + 演示数据功能为降级模式
- **语音命令条（E2 / B5）**：Dashboard 顶部命令输入框（Windows 系统语音输入 Win+H 等效 ASR）匹配固定指令："查看 dorm-a|b|c"（切换选中节点）、"朗读状态"（TTS 朗读选中节点最新 MQTT 记录）、"拍照"（Camera 快照，canvas 叠加 nodeId/时间/状态）、"开启/关闭风扇"（发布 action）；未匹配指令给出提示
- **快照与事件关联（E2 / B6）**：快照文件名含 nodeId + eventId + 时间戳，若当前节点有处理中事件则事件卡片显示快照引用（events.json 扩展快照字段）

### 信息分工（B4）

| 入口 | 承担的信息任务 | 为什么放在这里 |
|---|---|---|
| Dashboard | 当前重点（总览条 / 优先横幅 / 依据卡片 / 处理状态） | 实时数据在此汇聚，盯屏时一眼看到"现在最该看谁" |
| 移动端 | 快查快操作（三节点状态 / 当前重点 / 事件徽标 / 开风扇） | 随身场景快速定位，不复制 Dashboard 图表 |
| 3D | 空间状态（楼色 / 粒子 / 风扇 / 窗 / 光环 / 徽标 / 回放） | 空间位置用空间表达，哪个宿舍异常一眼定位 |
| TTS | 只读当前提醒（语音命令"朗读状态"读选中节点最新记录） | 语音适合短提醒，不适合长数据；听一句即可决策 |
| report.html | 历史复盘（摘要 / 事件复盘 / ML 异常分析） | 复盘要完整记录，静态报告可回看、可归档 |

## 十、测试与验证

| 测试 | 命令 | 覆盖 |
|---|---|---|
| 统一规则回归 | 打开 `web/test.html`（双击即可）；或 `python analysis/analyze.py --selftest`；或 `python simulator/simulate.py --selftest` | SPEC §6 四组：25/60→正常、16/60→偏冷、31/60→偏热、25/80→偏湿 |
| V0.8R5 阶段 A 验收 | `python simulator/test_upgrade.py` | 前置检查 + 端到端 14 项（三端一致性 / 事件贯穿 / 联动），需先完成冷启动清单 1-3 步 |
| 移动端协议帧单测 | 微信开发者工具运行 `simulator/test_mobile_mqtt.js`（或浏览器 Console） | 极简 MQTT 3.1.1 协议帧 30 项 |
| V0.8R5 阶段 B 验收 | `python simulator/test_stage_b.py` | 五套件：光环 4 / 徽标 5 / 聚焦 9 / 回放 11 / 语音 12 项，含 E1/E2 最低线逐条对照 |
| C 组 ML 验收 | `python simulator/test_c1.py` ~ `test_c4.py` | 数据分离 / 对照表 / 报告接回 / 红线口径 |
| 全项目最终复验 | `python simulator/test_final.py` | 62 项断言（--realtime/--offline/--a-loop/--b-loop/--c-repro） |

> 验收脚本统一要求 5510 端口有静态服务（冷启动清单第 3 步），工作区根 = 项目根。

## 十一、演示视频

- 录制：`python simulator/record_demo.py` —— 按故事线全自动录制 8 幕（Playwright 双 iframe 录屏 + 移动端 gdigrab 区域录窗合成；脚本自启自停 Broker / 静态服务、录制前自动重置 events.json、结束后恢复基线）。单幕重录 `--scene s3`；S3/S5 幕需微信开发者工具模拟器窗口在屏幕可见（录制时自动置顶）
- 配音：`python simulator/add_dub.py` —— edge-tts 自动配音（Xiaoxiao 女声）+ 硬字幕烧录 + SRT 软字幕 + 结尾收尾；台词时间轴按 `scene-timing.json` 各幕实际时长自动校正
- 成品：`docs/demo/demo-v08r5-final.mp4`（**7:34**，故事线：dorm-b 偏热 → 标记重点 → 多端同步 → Camera 快照 → 执行处理 → 新数据恢复 → 故障修复（坏 JSON）→ 冷启动 → Rule/ML 对照与不理想案例）；旁白文案见 `docs/demo/demo-script.md`，台词校对表 `docs/demo/dub-lines.txt`，软字幕 `docs/demo/demo-v08r5-subtitles.srt`
- 成品视频文件不入 git，本地保存在 `docs/demo/`（录制方法见上，随时可重录）

## 十二、常见问题与基本排查

- **页面没有数据更新**：依次检查 ① Broker 是否在跑（1883/8083 端口）② simulator 是否在跑 ③ 浏览器 Console 是否有 MQTT 连接错误 ④ 静态服务端口与访问端口是否一致
- **发布消息后页面没反应**：消息 JSON 是否合法（可用 JSON.parse 校验）、topic 是否正确（`dormmate/{nodeId}/env`，nodeId 必须为 dorm-a/b/c 且与 payload.nodeId 一致）、字段是否齐全（六字段 + 温湿度在合法范围）
- **证据截图写入触发页面重载**：VS Code Live Server 监视工作区文件变化，向工作区内写文件会触发页面 reload 打断测试/录制——验收与录制统一用 `python -m http.server 5510`（无监视行为）
- **3D 右键拖动触发浏览器返回**：Edge 默认"鼠标手势"拦截右键平移，设置 → 外观 → 鼠标手势 → 关闭（`edge://settings/appearance`）
- **Camera 无法打开**：需 localhost + 摄像头权限；被腾讯会议 / 钉钉 / Zoom 等占用时无法打开
- **TTS 朗读异常**：系统未装中文语音包时可能异常；建议使用 Edge（自带较稳定的中文语音）
- **移动端连不上 Broker**：确认开发者工具已勾选"不校验合法域名…"（见"依赖安装"）；确认 Broker 8083 WebSocket listener 已配置；确认 simulator 正在发布
- **移动端历史列表 duplicate key 警告**：同一秒内连续两条记录所致（wx:key 用秒级时间；SPEC 禁止额外字段故无唯一 id），仅控制台提示不影响功能
- **移动端负温度输入**：温度输入框用 `type="text"`（小程序数字键盘无负号键），温度范围 −50~50 需能输入负号
- **多个 Dashboard 实例同时连接同一 Broker**：各实例独立运行事件状态机与优先规则，会重复广播事件状态并相互覆盖优先节点（3D/小程序跟随"最后广播"）——正式演示与验收时只开一个 Dashboard

## 十三、已知限制

- **C2 IsolationForest 实现（C 组，等价替代）**：任务书建议 scikit-learn，但本机 Python 3.14 + Windows 下 sklearn 安装成功却无法导入（依赖的 scipy 1.18.1 编译扩展 DLL 加载失败：`cython_blas` / `_rank_filter_1d` ImportError，PyPI 与清华镜像重装均复现）。**替代方案**：`analysis/c_ml.py` 自实现 IsolationForest（纯 numpy、确定性 random_state=42，n_estimators=100、深度上限 ceil(log2(n))，阈值 s>0.5 判"与历史明显不同"）。**测试结果**：test_c2.py 全过——沿 M3 ASR"等价替代"先例（SPEC §13-3）
- **ASR（M3，等价方案）**：原生 SpeechRecognition（webkitSpeechRecognition）依赖 Google 在线识别服务，国内网络无法连接。**替代方案**：Windows 系统语音输入（Win+H）作为等价 ASR——识别文字进入页面"语音指令"输入框，程序匹配固定指令触发已有功能。**测试结果**：Win+H 说"朗读状态" → 页面显示识别结果 → TTS 朗读；说"拍照" → 成功触发快照；未定义指令正确提示（实测通过）
- **A3 恢复规则（A 组）**：本项目采用比统一规则更严格的恢复判定——动作（fan_on）之后，**连续 ≥2 条新数据 status==正常** 才判"已恢复"并自动发布 fan_off；期间仍异常则保持"处理中"继续提示
- **Dashboard 内存态**：actionState / recovery / 事件 / streak 刷新即失，现场演示请按剧本一气呵成
- **"已恢复"展示是瞬态**：恢复后下一条异常游走记录会按规则打破恢复（recovery=null），卡片/3D 侧栏的"已恢复"字样可能只持续数秒——这是 D3"恢复必须由新数据触发、异常回归即重新关注"规则的正确行为，非缺陷
- **C 组不做正式 ML**：不引入 Label / Train / Test / Accuracy / F1 / 混淆矩阵，不调参凑指标，不做模型版本管理（验证脚本 `python simulator/test_c4.py`）
- **技术边界**：无数据库（CSV 即存储）、无真实传感器（全部模拟节点）、无 LLM/RAG/Agent、无正式 ML 训练流程、不新建后端服务；真机同步不要求（任务书 p15）
- **验收脚本依赖**：`test_upgrade.py` / `test_stage_b.py` 需要 5510 端口有静态服务，Broker 与 simulator 需先运行

## 十四、开源组件

| 组件 | 版本 | 来源 / 许可 | 本项目使用位置 |
|---|---|---|---|
| Three.js | r128（本地 vendor） | threejs.org，MIT | three3d/vendor/three.min.js（3D 场景，防 CDN 网络不稳） |
| OrbitControls | r128 配套 | threejs.org examples/js，MIT | three3d/vendor/OrbitControls.js（旋转/缩放/平移） |
| mqtt.js | v5.16.0（本地 vendor） | github.com/mqttjs/MQTT.js，MIT | dashboard/vendor/mqtt.min.js + three3d/vendor/（MQTT over WebSocket 订阅） |
| Chart.js | v4.5.1（本地 vendor） | chartjs.org，MIT | dashboard/vendor/chart.umd.min.js（温湿度趋势图） |
| Mosquitto | 2.1.2 | mosquitto.org，EPL/EDL | 本机 MQTT Broker（D:\Mosquitto，1883 TCP + 8083 WebSocket） |
| MQTTX | 1.13.0 便携版 | mqttx.app | MQTT 客户端工具（手动发消息验证/演示） |
| Python | 3.14 | python.org，PSF | analysis/ + simulator/ 全部脚本 |
| pandas | 3.0.5 | PyPI，BSD | CSV 读取与统计（analysis/analyze.py） |
| matplotlib | （PyPI 最新） | PyPI，PSF 风格 | trend.png 生成（analysis/analyze.py） |
| numpy | （PyPI 最新） | PyPI，BSD | C 组自实现 IsolationForest（analysis/c_ml.py） |
| paho-mqtt | 2.x | PyPI，EPL/EDL | simulator/simulate.py 与 test_*.py 的 MQTT 客户端 |
| Playwright | （PyPI 最新） | playwright.dev，Apache-2.0 | 自动化验证与演示录制（test_*.py / record_demo.py） |
| imageio-ffmpeg | 自带 ffmpeg v7.1 静态二进制 | PyPI，BSD（含 GPL 组件另议） | 演示视频合并/转码/字幕烧录 |
| edge-tts | （PyPI 最新） | github.com/rany2/edge-tts，GPL-3.0 | 演示视频配音（微软 Edge 在线语音，仅本地使用） |
| 微信开发者工具 | 官方工具 | 微信官方 | mobile/ 小程序运行与验收 |

（移动端 MQTT 客户端为手写极简 3.1.1 实现，零第三方依赖，不引入 npm 构建）

## 十五、文档

- 项目规格：`docs/DORMMATE_SPEC.md`
- 执行计划：`docs/PLAN.md`（M1-M6 见 `docs/C01_Plans/M1_PLAN.md` ~ `M6_PLAN.md`）
- 综合作品升级计划（V0.8R5）：`docs/V08R5_Plans/UPGRADE_PLAN.md`
- 技术文档（V0.8R5）：`docs/V08R5_Plans/TECHNICAL_REPORT.md`
- 现场自测指南：`docs/OPEN01_GUIDE.md`
- 综合作品证据索引：`Evidence/README.md`
