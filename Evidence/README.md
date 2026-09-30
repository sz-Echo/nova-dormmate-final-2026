# Evidence 索引（V0.8R5 综合作品阶段）

> 任务书 p19：不堆截图，每项保留最能证明结果的截图/短视频/消息记录，并配一句说明。
> C01 阶段证据仍冻结在 `docs/evidence/`，本目录为综合作品升级阶段证据（2026-09-30 起）。
> 多数截图由验收脚本 `python simulator/test_upgrade.py` 自动生成（exit code 0 = 阶段 A 全过）。

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

## 其余目录（阶段 B/C/D 填充）

- `D2/` 优先关注（≥3 组不同三节点情况，优先级随数据变化）— 阶段 D 归档
- `D3/` 事件生命周期三端一致 — 阶段 D 归档
- `D4/` 真实故障与修复 — 阶段 C/D 归档（D4 预演：Topic 写错/JSON 字段错/Broker 停/3D 映射错/移动端不同步）
- `D5/` Rule/ML 对照案例 — 阶段 C 归档（C4 案例：27.5℃/70% 规则正常、ML 明显不同）
- `E1/` 3D 增强（优先光环/聚焦/回放/事件徽标）— 阶段 B 归档
- `E2/` 语音/拍照交互增强 — 阶段 B 归档
- `Debug/` 现场 Modify/Debug 预演记录 — 阶段 D 归档
- `Reproduce/` 交叉复现（卡点→README 修订→复现成功）— 阶段 C 归档
