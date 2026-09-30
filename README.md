# DormMate Final（nova-dormmate-final-2026）

宿舍环境助手：温湿度输入 → 统一规则判断 → 状态与建议 → 带时间历史（单宿舍 dorm-a）；Camera / ASR / TTS 本机交互；CSV 导出 + Python 离线分析。

## 运行方式

- **Python 依赖（离线分析 / 模拟节点 / 验证脚本 / 演示视频）**：`python -m pip install pandas matplotlib paho-mqtt numpy playwright imageio-ffmpeg edge-tts`；Playwright 另需首次执行 `python -m playwright install chromium`（下载浏览器内核）
- **主应用（M3 起必须用 Live Server，不能用 file:// 双击打开）**：VS Code 安装 Live Server 扩展 → 右键 `web/index.html` → "Open with Live Server" → 浏览器打开 `http://127.0.0.1:5500/web/index.html`。原因：Camera（getUserMedia）要求 localhost / https，file:// 下会被浏览器安全策略禁用
- **回归测试**：打开 `web/test.html`（直接双击即可，也可用 Live Server），四组统一回归数据（SPEC §6）应全部显示通过
- **离线分析（M2）**：Web 页"导出 CSV"得到 dormmate.csv 放到 `data/` 后，在项目根目录运行（需 Python 3 + pandas + matplotlib）：
  - `python analysis/analyze.py` —— 自动选择 `data/` 中**最新的 CSV**（"更换 CSV"即新文件生效，旧文件保留），输出统计并生成 `data/trend.png`、`data/report.html`
  - `python analysis/analyze.py 其他CSV路径` —— 指定某个 CSV 全量重新生成统计与两产物（验收要求，禁止手工修改）
  - `python analysis/analyze.py --watch` —— 监控 `data/`：放入或更换 CSV 后**自动重新生成**，无需手动运行（Ctrl+C 停止）
  - `python analysis/analyze.py --selftest` —— SPEC §6 四组回归自测
- **微信小程序（M4）**：微信开发者工具 → "导入项目"选择 `mobile/` 目录 → AppID 选"测试号"（工具会自动填入测试 AppID，无需注册、无需真机）→ 编译运行。核心页面：输入温湿度 → 状态 / 建议 + 带时间历史（含"载入演示数据"按钮）；打开项目时 Console 自动打印四组回归自测结果（4 行 PASS）与 ADVICE / 校验 / formatTime 附加校验行
- **实时看板（M5）**：① 启动 Broker：`<Mosquitto安装目录>\mosquitto.exe -c <同目录>\mosquitto.conf -v`（本机为 `D:\Mosquitto\`；conf 需含 listener 1883 / listener 8083 + protocol websockets / allow_anonymous true，见 `docs/C01_Plans/M5_PLAN.md` S1）② 启动模拟节点：`python simulator/simulate.py`（三节点 dorm-a/b/c 定时发布）③ Live Server 打开 `dashboard/index.html` → 三卡片同屏 + Chart.js 趋势（浏览器经 `ws://localhost:8083` 连 Broker）④ MQTTX 连接 `127.0.0.1:1883`、订阅 `dormmate/#` 验证
- **3D 可视化（M6）**：① 启动 Broker ② `python simulator/simulate.py` ③ Live Server 打开 `three3d/index.html` → Three.js 3D 宿舍场景（三栋楼：状态色 / 指示球 / 粒子 / 标牌四类可见变化）由 MQTT 实时驱动；鼠标拖拽旋转 / 滚轮缩放 / 右键平移，点击楼查看详情；侧栏"演示"按钮可在无 Broker 时用 SPEC §6 四组回归数据打出四状态。Three.js r128 为本地 vendor（three3d/vendor/，防 CDN 网络不稳），必须用 Live Server 以项目根为工作区打开
- **A 组业务闭环（A1-A4）**：① 启动 Broker ② `python simulator/simulate.py` ③ Live Server 打开 `dashboard/index.html`（可并排再开 `three3d/index.html` 对照）→ 顶部"优先关注"横幅按 A1 规则实时计算（另有测试页 `dashboard/test-priority.html`；现场演示脚本 `python simulator/test_a1.py --group 1|2|3|4|all` 可逐组发布预设三节点序列）④ 选中异常节点 → 点"开启风扇/通风" → Dashboard 显示"处理中"、3D 风扇转动+窗开、simulator 该节点降温（MQTT 动作通道 dormmate/{nodeId}/action）⑤ 连续 ≥2 条正常新数据 → "已恢复"+自动关扇（规则见"已知限制"）⑥"今日事件"面板自动生成完整事件（复盘叙事）→ 点"导出 events.json"存入 `data/` → `python analysis/analyze.py` → report.html 出现"事件复盘（A4）"区
- **B 组信息闭环（B1-B4）**：① B1/B2 同 Dashboard（测试页 `dashboard/test-priority.html` 含 A1/B1/B2 断言；验证脚本 `python simulator/test_b1.py` / `test_b2.py`）② B3 今日摘要：`python analysis/make_day_data.py --out data/sim-day-1 --seed 1` → `python analysis/daily_summary.py --day data/sim-day-1` → 控制台今日摘要 + `summary.md` + 当日 `report.html`（换 seed 重新生成；验证脚本 `python simulator/test_b3.py`）③ B4：Dashboard"朗读提醒"按钮（TTS 只读当前提醒，分工说明见"主要功能"B 组表）

## 主要功能

- **输入判断（M1）**：温湿度输入 → 校验（空值 / 非数字 / 超出范围（温度 −50~50、湿度 0~100）拦截，不进入分析、不追加历史）→ 统一状态规则（`<18 偏冷 → ≥30 偏热 → ≥75 偏湿 → 其余 正常`，顺序固定）→ 状态 + 建议（偏冷→注意保暖 / 偏热→注意通风 / 偏湿→注意除湿 / 正常→环境舒适）→ 带时间历史
- **CSV 导出（M2）**：历史一键导出 `dormmate.csv`（4 列最小格式、UTF-8 带 BOM、time 全格式）；历史仅存内存（统一 JSON 结构），刷新页面后清空，导出 CSV 落盘
- **离线分析（M2）**：Python（pandas + matplotlib）重跑统一规则 → 统计（记录数 / 温湿度最高最低 / 各状态数量 / 关注记录）→ `data/trend.png` + `data/report.html`；换新 CSV 全量重新生成
- **Camera（M3）**：点击请求权限 → video 预览 → 保存一张现场快照（不连续采集、不自动开启）
- **ASR 语音指令（M3）**：系统语音输入（Win+H）识别文字进入"语音指令"输入框 → 程序匹配固定指令并触发已有功能："朗读状态" → TTS 朗读当前状态；"拍照" → 保存快照（原因与替代方案见"已知限制"）
- **动态 TTS（M3）**：朗读内容随当前状态变化（如偏热 → "当前状态：偏热，注意通风"）
- **MQTT 实时系统（M5）**：本机 Mosquitto Broker（1883 TCP + 8083 WebSocket）→ simulator/ 三节点按 `dormmate/{nodeId}/env` 发布统一 JSON（status 复用 M2 Python 规则计算）→ dashboard/（mqtt.js + Chart.js）三卡片同屏实时刷新 + tab 切换各节点趋势图；topic/nodeId 双校验防串线，坏 JSON / 缺字段拦截告警，Broker 重启后自动重连
- **Three.js 3D 可视化（M6）**：three3d/ 简化 3D 宿舍场景（scene/camera/renderer + 三栋楼 mesh/material）——四状态映射为 4 类可见变化（建筑主色 / 发光指示球颜色+高度 / 楼顶粒子（偏冷飘雪·偏湿下雨·偏热热气·正常平静）/ CanvasTexture 中文标牌）；订阅与 dashboard 同一 MQTT 数据流（dormmate/+/env、ws://localhost:8083），消息经同款校验链（JSON.parse 容错 / 对象守卫 / 六字段 / 范围 / topic↔nodeId 串线防线）后由 updateScene 唯一入口驱动 3D，status 一律本地规则重算（不信任消息值）；点击选中楼 + 详情侧栏（A1 预留），屋顶风扇 mesh 预留（A2 挂点）
- **A 组业务闭环（A1-A4）**：
  - **A1 优先关注**：dashboard/priority.js 按"连续异常时长 → 异常次数 → nodeId 顺序"程序计算，顶部横幅实时显示"优先关注 X：已连续… 分钟"及原因；测试页 dashboard/test-priority.html（3 组三节点数据断言）；现场演示脚本 simulator/test_a1.py（--group 1|2|3|4|all）
  - **A2 处理动作**：Dashboard"开启风扇/通风"经 MQTT 动作通道（dormmate/{nodeId}/action）发布 actionState；three3d 风扇转动 + 窗开，simulator 对该节点模拟降温趋势；动作成为系统状态的一部分（env 记录 action 字段写入动作值），不直接改状态
  - **A3 恢复判断**：恢复必须由新数据触发（点击按钮不算）；恢复状态机见"已知限制"第 1 条
  - **A4 事件复盘**：完整处理流程（异常开始 → 优先原因 → 处理动作 → 恢复）由程序组装成事件记录，Dashboard"今日事件"面板展示并可导出 `events.json` → 存入 data/ → `python analysis/analyze.py` 后 report.html 出现"事件复盘"区（事件表格 + 复盘叙事，全部程序生成）
- **B 组信息闭环（B1-B4）**：当前总览（B1，程序成句自动更新）；判断依据（B2，三项指标附来源 + 优先标注）；今日摘要（B3，模拟日数据程序生成，换数据重新生成）。信息分工（B4）：

  | 入口 | 承担的信息任务 | 为什么放在这里 |
  |---|---|---|
  | Dashboard | 当前重点（总览条 / 优先横幅 / 依据卡片 / 处理状态） | 实时数据在此汇聚，盯屏时一眼看到"现在最该看谁" |
  | 3D | 空间状态（楼色 / 粒子 / 风扇 / 窗） | 空间位置用空间表达，哪个宿舍异常一眼定位 |
  | TTS | 只读当前提醒（"朗读提醒"按钮，读 B1 总览） | 语音适合短提醒，不适合长数据；听一句即可决策 |
  | report.html | 历史复盘（事件复盘 / 今日摘要 / ML 异常分析） | 复盘要完整记录，静态报告可回看、可归档 |

  （移动端三节点简报为可选扩展，不纳入最低完成线）
- **演示视频（A/B/C 达成效果）**：① `python simulator/record_demo.py` —— 全自动录制 A/B/C 三段演示（Playwright 录屏 + 双 iframe 同屏，A：Dashboard+3D 业务闭环；B：总览/依据/朗读/今日摘要；C：报告 ML 区+控制台+数据分离+不理想案例），再用 imageio-ffmpeg 自带 ffmpeg 合并为 `docs/demo/demo-full.webm`（含段间标题卡）并转码 `demo-full.mp4` ② `python simulator/add_dub.py` —— edge-tts 自动配音（Xiaoxiao 女声）+ 硬字幕烧录 + 结尾收尾，产出成品 `docs/demo/demo-final.mp4`（约 2:17，含 .srt 软字幕与配音台词表）③ `python simulator/capture_abc.py` —— 一键重出 16 张 A/B/C 运行截图到 `docs/demo/screenshots/`；旁白文案见 `docs/demo/demo-script.md`（按时间轴逐镜头）。录制无需手工启动 Broker（脚本自启自停），结束后自动恢复 data/ 程序产物，可随时重录
- **C 组轻量 ML（C1-C4）**：数据准备（C1）——`data/c_history.csv`（dorm-a 40 条**模拟**历史：24~26℃ / 55~65%，random_state=42 可复现）+ `data/c_new.csv`（8 组待判断新数据，与历史严格分离，含"规则正常但与历史明显不同"候选 29℃/72%）。**数据来源**：历史数据 = `analysis/make_c_data.py` 按 dorm-a"平时"画像程序生成的模拟值（非真实传感器）；待判断新数据 = 同脚本生成的独立文件（截图 C1：历史与新数据要分开，不能先混入再判断自己）；换新历史 CSV 重跑即可
  - 模型与对照（C2）：`python analysis/c_ml.py` —— IsolationForest（n_estimators=100、random_state=42）用 c_history fit、对 c_new predict（1=接近历史常态 / -1=与历史明显不同），与固定规则并排对照输出控制台 + `data/c_compare.json`；"规则正常、ML 不同"未出现则如实记录"本次测试未出现"。实现方式与替代原因见"已知限制"
  - 结果接回 DormMate（C3）：`python analysis/analyze.py` 生成 `data/report.html` 时自动加入"ML 异常分析（C3）"区——C2 对照结果并排（当前值 / 固定规则 / ML 判断 + 异常分数，数据来自 `data/c_compare.json`）；c_history / c_new 有更新时报告生成前自动重跑对照（复用 c_ml 同一实现，零重写）；"规则正常、ML 明显不同"的差异行高亮。换一份新数据：`python analysis/make_c_data.py --variant 2` → 重跑 `python analysis/analyze.py` → 报告全量重新生成 ML 结果（验证脚本 `python simulator/test_c3.py`）
  - 不理想案例（C4）：从实际对照结果中保留 1 个"判断不太理想"的例子（数据 + 模型输出已保留在 `data/c_new.csv` 与 `data/c_compare.json`）——**2026-09-28 10:03 的 27.5℃ / 70%**：固定规则判"正常"，ML 判"与历史明显不同"（分数 0.6738，比规则异常组 16/60 的 0.5641、31/60 的 0.5967、25/80 的 0.6219 都高，与 29℃/72% 并列最高分）。**可能原因**：模拟历史只有 40 条且全部落在 24~26℃ / 55~65% 窄区间，模型学到的"常态"范围过窄——现实宿舍只是略偏热偏湿（27.5℃ 尚在舒适范围），却因历史里从没出现过这样的值而被标"明显不同"；ML 的语义是"与历史不同"而非"规则异常"，直接当异常提醒使用时会对轻微偏离过于敏感。**C4 明确不做的口径**（截图 C4 不要求）：不引入 Label / Train / Test / Accuracy / F1 / 混淆矩阵，不调参凑指标，不做模型版本管理（验证脚本 `python simulator/test_c4.py`）

## 已知限制

- **C2 IsolationForest 实现（C 组，等价替代）**：任务书建议 scikit-learn，但本机 Python 3.14 + Windows 下 sklearn 安装成功却无法导入（依赖的 scipy 1.18.1 编译扩展 DLL 加载失败：`cython_blas` / `_rank_filter_1d` ImportError，PyPI 与清华镜像重装均复现）。**替代方案**：`analysis/c_ml.py` 自实现 IsolationForest（纯 numpy、确定性 random_state=42，n_estimators=100、深度上限 ceil(log2(n))，阈值 s>0.5 判"与历史明显不同"，同参数口径与截图 58 最小代码路线一致）。**测试结果**：test_c2.py 全过（对照表 8 组、可复现、如实记录）——沿 M3 ASR"等价替代"先例（SPEC §13-3）
- **A3 恢复规则（A 组）**：本项目采用比统一规则更严格的恢复判定——动作（fan_on）之后，**连续 ≥2 条新数据 status==正常** 才判"已恢复"并自动发布 fan_off（SPEC §9 A3：更严格规则须在 README 写清）；期间仍异常则保持"处理中"继续提示。Dashboard 内存态（actionState / recovery / 事件 / streak）刷新即失，现场演示请按剧本一气呵成（demo 演示记录带 demo 标记，不参与 A1 计算）
- **ASR（M3，等价方案）**：原生 SpeechRecognition（webkitSpeechRecognition）依赖 Google 在线识别服务，国内网络无法连接，实测不可用。**替代方案**：改用 Windows 系统语音输入（Win+H）作为等价 ASR——识别文字进入页面"语音指令"输入框，由程序捕获并匹配固定指令（"朗读状态" / "拍照"）触发已有功能。**测试结果**：Win+H 说"朗读状态" → 页面显示识别结果 → TTS 动态朗读"偏热，注意通风"；说"拍照" → 成功触发快照下载；未定义指令正确提示（2026-09-26 实测通过）
- **TTS 中文语音**：若系统未装中文语音包，朗读可能异常（页面会提示）；建议使用 Edge（自带较稳定的中文语音）
- **Camera**：需 localhost + 摄像头权限；被其他软件（腾讯会议 / 钉钉 / Zoom 等）占用时无法打开
- **移动端 iOS 数字键盘**无负号键（`inputmode="decimal"` 所致），负温度需全键盘输入；桌面浏览器无此问题
- **小程序（M4）**：温度输入框用 `type="text"` 而非数字键盘——小程序数字键盘无负号键，温度范围 −50~50 含负数，需要能输入负号与非数字（演示校验拦截）
- **小程序（M4）**：历史列表以秒级时间为 `wx:key`，同一秒内连续两条记录会触发 duplicate key 控制台警告（仅提示，不影响功能）；SPEC §4 统一 JSON 禁止额外字段，故不引入唯一 id
- **3D 页（M6）右键拖动**：Edge 浏览器默认开启「鼠标手势」（按住右键左划 = 返回上一页），会拦截 OrbitControls 的右键平移并退出页面——这是浏览器级手势，网页代码无法屏蔽。**解决**：Edge 设置 → 外观 → 鼠标手势 → 关闭（或地址栏 `edge://settings/appearance`）；非 Edge 则检查「鼠标手势」类扩展并禁用。关闭后右键拖动 = 平移视角（页面已加 `touch-action: none` 等防御，触摸屏「边缘滑动返回」同样被屏蔽，关闭页面仅右上角叉）

## 开源组件

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

## 文档

- 项目规格：`docs/DORMMATE_SPEC.md`
- 执行计划：`docs/PLAN.md`（M1 见 `docs/C01_Plans/M1_PLAN.md`，M2 见 `docs/C01_Plans/M2_PLAN.md`，M3 详细步骤与现场演示剧本见 `docs/C01_Plans/M3_PLAN.md`，M4 见 `docs/C01_Plans/M4_PLAN.md`，M5 见 `docs/C01_Plans/M5_PLAN.md`，M6 见 `docs/C01_Plans/M6_PLAN.md`）
- 综合作品升级计划（V0.8R5）：`docs/V08R5_Plans/UPGRADE_PLAN.md`
