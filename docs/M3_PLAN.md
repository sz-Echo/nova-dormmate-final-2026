# M3 详细执行计划 — 本机交互 + 版本记录

> 依据：docs/DORMMATE_SPEC.md、docs/PLAN.md、任务书 M3 原文（第 11-15 条）。本文件是 M3 期间的执行依据，随进度更新；与 SPEC/PLAN 冲突时以 SPEC 为准。

## 1. 决策记录（已与用户确认）

- **ASR 等价方案**：原生 SpeechRecognition 因国内网络无法连接 Google → 系统语音输入法（Win+H）把识别文字打进页面输入框，程序捕获并匹配固定指令；原因 / 替代方案 / 测试结果写入 README（SPEC §13 约定 3）
- **GitHub 仓库**：Private，`nova-dormmate-final-2026`（账号 sz-Echo）
- **Git 策略**：沿用 F:\AIcoding 现有仓库（阶段0 起真实提交，"git init"语义等效满足，现场演示 status / add / commit / log）；git add scoped 到本项目子目录（仓库含 mini_mall 等其他项目，裸 `git add .` 会误加）；GitHub 用 git subtree push 推送本项目子目录（保留本项目全部提交历史）
- **Commit Message（用户指定，现场答辩用）**：Commit A `feat: 加入Camera预览与快照`；Commit B `feat: 加入ASR语音指令与动态TTS`
- **顺序红线**：S1-S3 全流程在 localhost 走通、浏览器无报错、用户确认后才执行 S5/S6（避免提交未完成代码）
- **push 兜底**：任何报错先停下给用户看，不强行 push；备选：临时分支验证 / git bundle 本地打包
- **安全红线**：绝不提交或在对话中输入 API Key / 密码 / Token

## 2. 范围红线（M3 不做）

- Camera 不连续采集、不自动开启（点击才请求权限）
- 不做多节点（M5 起）、不做数据库 / 传感器 / LLM
- 运行方式固定 Live Server（localhost），不用 file://

## 3. 执行步骤（每步完成停下等用户确认）

### S0 文档对齐 ✅ 已完成（本文档 + PLAN 看板更新）

### S1 Camera（任务书第 11 条）✅ 已完成（用户实测通过：权限 / 预览 / 快照下载 / 关闭摄像头 / 刷新不自动开启）

- web/index.html：加摄像头区（video 预览 + 打开 / 保存快照 / 关闭按钮 + 提示区）
- web/script.js（沿用"顶层无 DOM"约定，逻辑挂 DOMContentLoaded）：
  - `startCamera()`：点击才请求 getUserMedia（video 流），video 预览；权限拒绝 / 无设备 / 非 localhost 环境均给具体提示
  - `saveSnapshot()`：canvas 抓帧 → toBlob → 复用 M2 的 Blob+download 模式下载 `dormmate-snapshot-时间.png`
  - `stopCamera()`：停止轨道、释放摄像头
- web/style.css：摄像头区样式
- **检查点（用户实测）**：Live Server 打开 http://127.0.0.1:5500/web/index.html → 点击打开摄像头 → 预览 → 保存一张现场快照；刷新页面后摄像头不自动开启

### S2 TTS（任务书第 12 条后半）✅ 已完成（用户实测通过：朗读随状态变化、未分析有提示、控制台无报错）

- `speakStatus()`：speechSynthesis + zh-CN 朗读当前状态与建议（取 analyze() 返回的 status + ADVICE，**随状态动态变化**，如偏热读"偏热，注意通风"）
- **中文语音检查**：`speechSynthesis.getVoices()` 检查 zh-CN；没有则页面提示"系统未装中文语音包"；保底使用 Edge（自带较稳定的在线中文语音）
- 页面加"朗读状态"按钮（语音指令不可用也能现场演示 TTS）
- 检查点：分别输入 16/60、31/60 等，朗读内容随之变化

### S3 ASR（任务书第 12 条前半，等价方案）✅ 已完成（用户实测通过：Win+H 说"朗读状态"/"拍照"闭环、未定义指令提示、打字回车同样匹配）

- 先实测原生 SpeechRecognition（webkitSpeechRecognition，Chrome/Edge + localhost）；可用则用原生，不可用走既定等价方案
- 等价方案：页面加"语音指令"输入框，监听 input 事件捕获系统输入法（Win+H）打进的文字 → 匹配固定指令："朗读状态" → 调用 M1 的 `analyze()` → `speakStatus()`；"拍照" → 触发 `saveSnapshot()`
- **识别结果显示在页面**（指令结果区显示捕获文字与匹配结果），不只打印控制台；未匹配提示可用指令
- **Win+H 测试步骤（测试前先给用户）**：① 先打开记事本按 Win+H 说话，确认系统能把文字打出来；② 再在浏览器页面输入框测；③ 若完全无反应：设置→辅助功能→键盘 检查语音输入开关；仍不行 → 备用方案（搜狗等输入法语音输入，或用户录制一段含指令的音频由程序导入）
- README 记录原因 / 替代方案 / 测试结果（成功识别指令并触发 TTS / analyze）

### S4 README 完整版（任务书第 14 条）✅ 已完成（README 重写：运行方式 / 主要功能 / 已知限制三部分，ASR 兜底含原因+替代方案+测试结果；现场演示剧本见 §6）

### S5 本地 Git 提交拆分（任务书第 13 条）——**前提：S1-S3 全流程 localhost 走通、无报错、用户确认后执行**

- Commit A `feat: 加入Camera预览与快照`（S1 后）；Commit B `feat: 加入ASR语音指令与动态TTS`（S4 后）；加 M1/M2 已有 6 次 = Challenge 期间 ≥3 次满足
- 流程演示：git status（**用户先在 VS Code 确认只列 DormMate 目录**）→ git add（scoped 项目子目录）→ git commit → git log --oneline
- 本文件记录每次 Commit 改了什么（现场能说明 2 次修改内容）

### S6 GitHub Private 仓库 + 推送（任务书第 15 条）

- gh CLI 创建 Private 仓库 `nova-dormmate-final-2026` → git subtree push 推送子目录（**命令先给用户确认再执行**）→ GitHub 网页确认可见 Challenge 期间提交记录
- 报错先停下给用户看，不强行 push；备选临时分支 / git bundle

### S7 验收 + 交接

- 现场演示剧本完整跑一遍；证据 docs/evidence/m3/（快照、识别结果、TTS、git log、GitHub 记录）；PLAN 看板更新；按 PLAN §6 输出交接摘要

## 4. 关键设计 — 与后续阶段衔接

| 阶段 | 联系 |
|---|---|
| M1 | ASR 指令直接调用 analyze()（既有契约：支持传值、返回记录 JSON）；TTS 朗读内容取 analyze() 的 status + ADVICE；computeStatus 不变 |
| M2 | 复用 Blob + download 模式保存快照；离线链（CSV / analyze.py）不受影响 |
| M4 | 小程序不要求 Camera/ASR；M3 不改变 analyze() 契约 |
| M5/M6 | 无直接接口；M3 打通 GitHub 仓库与推送流程，Final 只需再推最新稳定版 |
| A2 | M3"固定指令触发已有功能"与 A2"用户操作改变系统状态"同构，为 A 组提供交互模式参考；action 字段仍预留空串 |
| B | README 测试结果、git log 提交记录是 B 组程序化说明的素材来源 |
| C | 无直接接口（C3 扩展点 M2 已在 report.html 预留） |
| Final | M3 建立 GitHub 同步机制；Camera / ASR / TTS 纳入 Final 重启复验 |

## 5. 验收清单（完成线）

1. localhost（Live Server）运行，非 file://
2. Camera：点击请求权限 → 预览 → 保存一张现场快照；不连续采集、不自动开启
3. ASR：识别结果显示在页面；≥1 条固定指令真实触发已有功能（调用 analyze()）
4. TTS：朗读内容随当前状态动态变化
5. 本地 Git ≥3 次有意义 Commit（M1/M2 已有 + M3 新增），能说明其中 2 次分别改了什么
6. GitHub Private 仓库 nova-dormmate-final-2026 可见 Challenge 期间提交记录；最新 Commit 对应当前可运行项目
7. README：运行方式（Live Server）、主要功能、已知限制（原生 SpeechRecognition 无法连 Google → 系统输入法等价 ASR 的原因 + 替代方案 + 测试结果）
8. 无 API Key / 密码 / Token 入库

## 6. 现场演示剧本（S7 照着走）

**准备**：VS Code Live Server 打开 web/index.html（确认地址栏 `http://127.0.0.1:5500/...`）；关闭占用摄像头的软件（腾讯会议 / 钉钉 / Zoom）。

1. **输入判断（M1）**：输入 31/60 → 点"分析环境" → 状态"偏热"、建议"注意通风"，历史多一条
2. **动态 TTS（M3）**：点"朗读状态" → 听到"当前状态：偏热，注意通风"
3. **等价 ASR（M3）**：点击"语音指令"输入框聚焦 → 按 Win+H → 说"朗读状态" → 输入框出现识别文字 → 页面显示"识别结果：朗读状态 → 已触发：朗读当前状态" → 再次听到朗读
4. **Camera（M3）**：点"打开摄像头" → 允许权限 → 视频预览 → 点"保存快照" → 下载目录出现 `dormmate-snapshot-时间.png` → 点"关闭摄像头"
5. **CSV 导出 + 离线分析（M1/M2）**：点"导出 CSV" → 下载 dormmate.csv 放进 data/ → 终端运行 `python analysis/analyze.py` → 控制台统计 + `data/trend.png` + `data/report.html`
6. **版本记录（M3）**：修改一处固定指令或提示文字 → VS Code 终端 `git status`（只列 DormMate 目录）→ `git add` → `git commit` → `git log --oneline`（指出 M1 提交、Camera 提交、ASR/TTS 提交）→ GitHub 网页展示 Private 仓库 `nova-dormmate-final-2026` 的提交记录

**现场问答口径**：

- 哪个功能调用了 Camera/ASR/TTS：第 3 步输入框捕获系统语音识别文字（等价 ASR）触发 speakStatus()（TTS）；第 4 步按钮走 getUserMedia（Camera）
- 指令实际触发了什么："朗读状态" → speakStatus() 朗读当前状态与建议（读 analyze() 的结果）；"拍照" → saveSnapshot() canvas 抓帧下载
- 本地 Git 有哪些真实提交：`git log --oneline`（M1/M2/M3 各阶段提交）
- 两次修改分别改了什么：Commit A（Camera）加了视频预览与快照保存；Commit B（ASR/TTS）加了语音指令输入框匹配与动态朗读

## 7. 验证方式

- Live Server 打开 http://127.0.0.1:5500/web/index.html，确认地址栏是 localhost
- 现场演示剧本完整走查；证据截图 → docs/evidence/m3/；git log --oneline 与 GitHub 网页记录对照
