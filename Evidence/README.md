# Evidence 索引（V0.8R5 综合作品阶段）

> 任务书 p19：不堆截图，每项保留最能证明结果的截图/短视频/消息记录，并配一句说明。
> C01 阶段证据仍冻结在 `docs/evidence/`，本目录为综合作品升级阶段证据（2026-09-30 起）。
> 截图由验收脚本自动生成：阶段 A `python simulator/test_upgrade.py`（exit code 0 = 全过）；
> 阶段 B `python simulator/test_stage_b.py`（E1/E2 五套件一键验收，exit code 0 = 全过）。
> 验收脚本请走 5510 端口静态服务（python -m http.server 5510）——VS Code Live Server（5500）会因证据文件写入重载页面，打断测试。

## D1 多节点稳定运行

- `d1-three-nodes-online.png` — Dashboard 三节点同屏实时（dorm-a/b/c 卡片均有数据）
- `d1-3d-three-buildings.png` — 3D 场景三栋宿舍楼与三节点一一对应
- `d1-new-message-drives-update.png` — 发布一条新 MQTT 消息（dorm-a 偏热）后 Dashboard 立即更新（任务书"现场随机发布一条新消息，检查各端更新"的核验方式）

## E3 web-移动端实时数据同步与协同

- `e3-handling-dashboard.png` — 移动端式 fan_on（与小程序 onFanOn 发布内容一致）后 Dashboard 卡片"处理中"
- `e3-fan-running-3d.png` — 同一动作驱动 3D 侧栏"事件：处理中"（风扇运行）
- `e3-recovered-dashboard.png` — 新数据触发恢复后 Dashboard"已恢复"
- `e3-broadcast-messages.txt` — 捕获的 `dormmate/{nodeId}/event`（OPEN/HANDLING/RECOVERED）与 `dormmate/priority` 广播消息原文——三端同一状态源证据（同 eventId 贯穿完整生命周期）

### 待补拍（小程序端，由开发者工具人工截图）

补拍时机：**阶段 A 验收完成后的第一次开发者工具实测时**（即现在，代码已就绪）。补两张后放入 E3/ 并更新本说明：

1. 小程序三节点卡片与 Dashboard 同屏数值一致（证明"两端读取同一套实时数据"）
2. 小程序点"开启风扇"后 toast 提示与 Dashboard"处理中"同屏（证明"移动执行处理动作 → web 看到变化"联动）

## E1 3D 数字孪生增强（阶段 B，B1-B4）

- `e1-priority-halo-a.png` — 优先广播后对应楼底橙色呼吸光环（B1，E1⑤）
- `e1-priority-halo-b.png` — 点击选中后金色选中环与橙色优先光环并存
- `e1-event-badge-handling.png` — 标牌右上角橙色「处理中」徽标（B2，E1⑥）
- `e1-event-badge-recovered.png` — 恢复后徽标变绿色「已恢复」（处理中粒子同时变橙加速）
- `e1-focus-default.png` / `e1-focus-dorm-c-mid.png` / `e1-focus-dorm-c.png` — 镜头聚焦飞行：默认总览 → 飞行中 → 到达 dorm-c（B3，E1⑦）
- `e1-priority-focus-dorm-b.png` — 优先节点变化自动聚焦（用户交互闸门开启后）
- `e1-replay-playing.png` — 侧栏回放条「■ 停止回放」+「历史回放中」状态行（B4，E1⑦）
- `e1-replay-restored.png` — 停止回放后侧栏恢复跟随实时数据

## E2 Camera/ASR/TTS 交互增强（阶段 B，B5）

- `e2-voice-bar.png` — Dashboard 语音命令条（Win+H 等价 ASR 入口 + 摄像头控件）
- `e2-voice-view-dorm-b.png` — 语音「查看 dorm-b」后操作对象与 tab 同步切换
- `e2-tts-last-spoken.txt` — 「朗读状态」朗读文本原文（来自 dorm-b 真实 MQTT 记录）
- `e2-snapshot-dorm-b.png` — 语音「拍照」快照：顶部黑条叠加 nodeId/时间/状态，文件名含 eventId
- `e2-event-card-with-snapshot.png` — 恢复定稿后事件卡片含「现场快照」引用（完整交互链）
- `e2-interaction-chain.txt` — 语音命令 → 效果 全程记录

## 其余目录（阶段 C/D 填充）

- `D2/` 优先关注（≥3 组不同三节点情况，优先级随数据变化）— 阶段 D 归档
- `D3/` 事件生命周期三端一致 — 阶段 D 归档
- `D4/` 真实故障与修复 — 阶段 C/D 归档（D4 预演：Topic 写错/JSON 字段错/Broker 停/3D 映射错/移动端不同步）
- `D5/` Rule/ML 对照案例 — 阶段 C 归档（C4 案例：27.5℃/70% 规则正常、ML 明显不同）
- `Debug/` 现场 Modify/Debug 预演记录 — 阶段 D 归档
- `Reproduce/` 交叉复现（卡点→README 修订→复现成功）— 阶段 C 归档
