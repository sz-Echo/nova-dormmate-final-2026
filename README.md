# DormMate Final（nova-dormmate-final-2026）

宿舍环境助手：温湿度输入 → 统一规则判断 → 状态与建议 → 带时间历史（单宿舍 dorm-a）；Camera / ASR / TTS 本机交互；CSV 导出 + Python 离线分析。

## 运行方式

- **主应用（M3 起必须用 Live Server，不能用 file:// 双击打开）**：VS Code 安装 Live Server 扩展 → 右键 `web/index.html` → "Open with Live Server" → 浏览器打开 `http://127.0.0.1:5500/web/index.html`。原因：Camera（getUserMedia）要求 localhost / https，file:// 下会被浏览器安全策略禁用
- **回归测试**：打开 `web/test.html`（直接双击即可，也可用 Live Server），四组统一回归数据（SPEC §6）应全部显示通过
- **离线分析（M2）**：Web 页"导出 CSV"得到 dormmate.csv 放到 `data/` 后，在项目根目录运行（需 Python 3 + pandas + matplotlib）：
  - `python analysis/analyze.py` —— 自动选择 `data/` 中**最新的 CSV**（"更换 CSV"即新文件生效，旧文件保留），输出统计并生成 `data/trend.png`、`data/report.html`
  - `python analysis/analyze.py 其他CSV路径` —— 指定某个 CSV 全量重新生成统计与两产物（验收要求，禁止手工修改）
  - `python analysis/analyze.py --watch` —— 监控 `data/`：放入或更换 CSV 后**自动重新生成**，无需手动运行（Ctrl+C 停止）
  - `python analysis/analyze.py --selftest` —— SPEC §6 四组回归自测
- **微信小程序（M4）**：微信开发者工具 → "导入项目"选择 `mobile/` 目录 → AppID 选"测试号"（工具会自动填入测试 AppID，无需注册、无需真机）→ 编译运行。核心页面：输入温湿度 → 状态 / 建议 + 带时间历史（含"载入演示数据"按钮）；打开项目时 Console 自动打印四组回归自测结果（4 行 PASS）与 ADVICE / 校验 / formatTime 附加校验行
- **实时看板（M5）**：① 启动 Broker：`<Mosquitto安装目录>\mosquitto.exe -c <同目录>\mosquitto.conf -v`（本机为 `D:\Mosquitto\`；conf 需含 listener 1883 / listener 8083 + protocol websockets / allow_anonymous true，见 `docs/M5_PLAN.md` S1）② 启动模拟节点：`python simulator/simulate.py`（三节点 dorm-a/b/c 定时发布）③ Live Server 打开 `dashboard/index.html` → 三卡片同屏 + Chart.js 趋势（浏览器经 `ws://localhost:8083` 连 Broker）④ MQTTX 连接 `127.0.0.1:1883`、订阅 `dormmate/#` 验证
- **3D 可视化（M6）**：① 启动 Broker ② `python simulator/simulate.py` ③ Live Server 打开 `three3d/index.html` → Three.js 3D 宿舍场景（三栋楼：状态色 / 指示球 / 粒子 / 标牌四类可见变化）由 MQTT 实时驱动；鼠标拖拽旋转 / 滚轮缩放 / 右键平移，点击楼查看详情；侧栏"演示"按钮可在无 Broker 时用 SPEC §6 四组回归数据打出四状态。Three.js r128 为本地 vendor（three3d/vendor/，防 CDN 网络不稳），必须用 Live Server 以项目根为工作区打开

## 主要功能

- **输入判断（M1）**：温湿度输入 → 校验（空值 / 非数字 / 超出范围（温度 −50~50、湿度 0~100）拦截，不进入分析、不追加历史）→ 统一状态规则（`<18 偏冷 → ≥30 偏热 → ≥75 偏湿 → 其余 正常`，顺序固定）→ 状态 + 建议（偏冷→注意保暖 / 偏热→注意通风 / 偏湿→注意除湿 / 正常→环境舒适）→ 带时间历史
- **CSV 导出（M2）**：历史一键导出 `dormmate.csv`（4 列最小格式、UTF-8 带 BOM、time 全格式）；历史仅存内存（统一 JSON 结构），刷新页面后清空，导出 CSV 落盘
- **离线分析（M2）**：Python（pandas + matplotlib）重跑统一规则 → 统计（记录数 / 温湿度最高最低 / 各状态数量 / 关注记录）→ `data/trend.png` + `data/report.html`；换新 CSV 全量重新生成
- **Camera（M3）**：点击请求权限 → video 预览 → 保存一张现场快照（不连续采集、不自动开启）
- **ASR 语音指令（M3）**：系统语音输入（Win+H）识别文字进入"语音指令"输入框 → 程序匹配固定指令并触发已有功能："朗读状态" → TTS 朗读当前状态；"拍照" → 保存快照（原因与替代方案见"已知限制"）
- **动态 TTS（M3）**：朗读内容随当前状态变化（如偏热 → "当前状态：偏热，注意通风"）
- **MQTT 实时系统（M5）**：本机 Mosquitto Broker（1883 TCP + 8083 WebSocket）→ simulator/ 三节点按 `dormmate/{nodeId}/env` 发布统一 JSON（status 复用 M2 Python 规则计算）→ dashboard/（mqtt.js + Chart.js）三卡片同屏实时刷新 + tab 切换各节点趋势图；topic/nodeId 双校验防串线，坏 JSON / 缺字段拦截告警，Broker 重启后自动重连
- **Three.js 3D 可视化（M6）**：three3d/ 简化 3D 宿舍场景（scene/camera/renderer + 三栋楼 mesh/material）——四状态映射为 4 类可见变化（建筑主色 / 发光指示球颜色+高度 / 楼顶粒子（偏冷飘雪·偏湿下雨·偏热热气·正常平静）/ CanvasTexture 中文标牌）；订阅与 dashboard 同一 MQTT 数据流（dormmate/+/env、ws://localhost:8083），消息经同款校验链（JSON.parse 容错 / 对象守卫 / 六字段 / 范围 / topic↔nodeId 串线防线）后由 updateScene 唯一入口驱动 3D，status 一律本地规则重算（不信任消息值）；点击选中楼 + 详情侧栏（A1 预留），屋顶风扇 mesh 预留（A2 挂点）

## 已知限制

- **ASR（M3，等价方案）**：原生 SpeechRecognition（webkitSpeechRecognition）依赖 Google 在线识别服务，国内网络无法连接，实测不可用。**替代方案**：改用 Windows 系统语音输入（Win+H）作为等价 ASR——识别文字进入页面"语音指令"输入框，由程序捕获并匹配固定指令（"朗读状态" / "拍照"）触发已有功能。**测试结果**：Win+H 说"朗读状态" → 页面显示识别结果 → TTS 动态朗读"偏热，注意通风"；说"拍照" → 成功触发快照下载；未定义指令正确提示（2026-09-26 实测通过）
- **TTS 中文语音**：若系统未装中文语音包，朗读可能异常（页面会提示）；建议使用 Edge（自带较稳定的中文语音）
- **Camera**：需 localhost + 摄像头权限；被其他软件（腾讯会议 / 钉钉 / Zoom 等）占用时无法打开
- **移动端 iOS 数字键盘**无负号键（`inputmode="decimal"` 所致），负温度需全键盘输入；桌面浏览器无此问题
- **小程序（M4）**：温度输入框用 `type="text"` 而非数字键盘——小程序数字键盘无负号键，温度范围 −50~50 含负数，需要能输入负号与非数字（演示校验拦截）
- **小程序（M4）**：历史列表以秒级时间为 `wx:key`，同一秒内连续两条记录会触发 duplicate key 控制台警告（仅提示，不影响功能）；SPEC §4 统一 JSON 禁止额外字段，故不引入唯一 id
- **3D 页（M6）右键拖动**：Edge 浏览器默认开启「鼠标手势」（按住右键左划 = 返回上一页），会拦截 OrbitControls 的右键平移并退出页面——这是浏览器级手势，网页代码无法屏蔽。**解决**：Edge 设置 → 外观 → 鼠标手势 → 关闭（或地址栏 `edge://settings/appearance`）；非 Edge 则检查「鼠标手势」类扩展并禁用。关闭后右键拖动 = 平移视角（页面已加 `touch-action: none` 等防御，触摸屏「边缘滑动返回」同样被屏蔽，关闭页面仅右上角叉）

## 文档

- 项目规格：`docs/DORMMATE_SPEC.md`
- 执行计划：`docs/PLAN.md`（M1 见 `docs/M1_PLAN.md`，M2 见 `docs/M2_PLAN.md`，M3 详细步骤与现场演示剧本见 `docs/M3_PLAN.md`，M4 见 `docs/M4_PLAN.md`，M5 见 `docs/M5_PLAN.md`，M6 见 `docs/M6_PLAN.md`）
