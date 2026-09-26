# DormMate Final（nova-dormmate-final-2026）

宿舍环境助手：温湿度输入 → 统一规则判断 → 状态与建议 → 带时间历史（单宿舍 dorm-a）；Camera / ASR / TTS 本机交互；CSV 导出 + Python 离线分析。

## 运行方式

- **主应用（M3 起必须用 Live Server，不能用 file:// 双击打开）**：VS Code 安装 Live Server 扩展 → 右键 `web/index.html` → "Open with Live Server" → 浏览器打开 `http://127.0.0.1:5500/web/index.html`。原因：Camera（getUserMedia）要求 localhost / https，file:// 下会被浏览器安全策略禁用
- **回归测试**：Live Server 下打开 `web/test.html`，四组统一回归数据（SPEC §6）应全部显示通过
- **离线分析（M2）**：Web 页"导出 CSV"得到 dormmate.csv 放到 `data/` 后，在项目根目录运行（需 Python 3 + pandas + matplotlib）：
  - `python analysis/analyze.py` —— 自动选择 `data/` 中**最新的 CSV**（"更换 CSV"即新文件生效，旧文件保留），输出统计并生成 `data/trend.png`、`data/report.html`
  - `python analysis/analyze.py 其他CSV路径` —— 指定某个 CSV 全量重新生成统计与两产物（验收要求，禁止手工修改）
  - `python analysis/analyze.py --watch` —— 监控 `data/`：放入或更换 CSV 后**自动重新生成**，无需手动运行（Ctrl+C 停止）
  - `python analysis/analyze.py --selftest` —— SPEC §6 四组回归自测

## 主要功能

- **输入判断（M1）**：温湿度输入 → 校验（空值 / 非数字 / 超出范围拦截）→ 统一状态规则（`<18 偏冷 → ≥30 偏热 → ≥75 偏湿 → 其余 正常`，顺序固定）→ 状态 + 建议（偏冷→注意保暖 / 偏热→注意通风 / 偏湿→注意除湿 / 正常→环境舒适）→ 带时间历史
- **CSV 导出（M2）**：历史一键导出 `dormmate.csv`（4 列最小格式、UTF-8 带 BOM、time 全格式）
- **离线分析（M2）**：Python（pandas + matplotlib）重跑统一规则 → 统计（记录数 / 温湿度最高最低 / 各状态数量 / 关注记录）→ `data/trend.png` + `data/report.html`；换新 CSV 全量重新生成
- **Camera（M3）**：点击请求权限 → video 预览 → 保存一张现场快照（不连续采集、不自动开启）
- **ASR 语音指令（M3）**：系统语音输入（Win+H）识别文字进入"语音指令"输入框 → 程序匹配固定指令并触发已有功能："朗读状态" → TTS 朗读当前状态；"拍照" → 保存快照（原因与替代方案见"已知限制"）
- **动态 TTS（M3）**：朗读内容随当前状态变化（如偏热 → "当前状态：偏热，注意通风"）

## 已知限制

- **ASR（M3，等价方案）**：原生 SpeechRecognition（webkitSpeechRecognition）依赖 Google 在线识别服务，国内网络无法连接，实测不可用。**替代方案**：改用 Windows 系统语音输入（Win+H）作为等价 ASR——识别文字进入页面"语音指令"输入框，由程序捕获并匹配固定指令（"朗读状态" / "拍照"）触发已有功能。**测试结果**：Win+H 说"朗读状态" → 页面显示识别结果 → TTS 动态朗读"偏热，注意通风"；说"拍照" → 成功触发快照下载；未定义指令正确提示（2026-09-26 实测通过）
- **TTS 中文语音**：若系统未装中文语音包，朗读可能异常（页面会提示）；建议使用 Edge（自带较稳定的中文语音）
- **Camera**：需 localhost + 摄像头权限；被其他软件（腾讯会议 / 钉钉 / Zoom 等）占用时无法打开
- **移动端 iOS 数字键盘**无负号键（`inputmode="decimal"` 所致），负温度需全键盘输入；桌面浏览器无此问题

## 文档

- 项目规格：`docs/DORMMATE_SPEC.md`
- 执行计划：`docs/PLAN.md`（M1 见 `docs/M1_PLAN.md`，M2 见 `docs/M2_PLAN.md`，M3 详细步骤与现场演示剧本见 `docs/M3_PLAN.md`）
