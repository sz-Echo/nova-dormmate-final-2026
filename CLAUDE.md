# CLAUDE.md — DormMate Final（nova-dommate-final-2026）

## 唯一事实源

- `docs/DORMMATE_SPEC.md`：项目规格（状态规则、统一 JSON、CSV 格式、回归测试数据、M1-M6 / A / B / C 要求、统一约定），稳定契约
- `docs/PLAN.md`：阶段计划与当前看板，活文档
- `docs/C01_Plans/MASTER_PLAN.md`：M1-M6 与 A/B/C 联系矩阵 + 剩余阶段（A/B/C/Final）详细执行步骤与契约，活文档
- 三者冲突以 SPEC 为准；SPEC 变更须用户确认

## 每次工作的步骤

1. 先读 `docs/DORMMATE_SPEC.md`、`docs/PLAN.md`、`docs/C01_Plans/MASTER_PLAN.md` 与当前阶段详细计划（C01 阶段见 `docs/C01_Plans/M1_PLAN.md`，后续阶段同名换号；A/B/C/Final 详细步骤在 MASTER_PLAN；V0.8R5 综合作品升级阶段见 `docs/V08R5_Plans/UPGRADE_PLAN.md`）
2. 只做 PLAN 看板里的当前阶段，不做未解锁阶段（依赖未完成/未过门禁）
3. 完成后按 PLAN 第 6 节模板输出交接摘要

## 关键规则速查（全文以 SPEC 为准）

- status 顺序（不可改）：① temperature < 18 → 偏冷 ② 否则 temperature >= 30 → 偏热 ③ 否则 humidity >= 75 → 偏湿 ④ 其余 → 正常
- JSON 字段统一：nodeId / temperature / humidity / status / time / action（action 预留，M1-M4 为空字符串）；status 必须由规则计算，禁止手填
- CSV 最小格式：`time,temperature,humidity,status`（UTF-8）
- 回归测试：25/60→正常、16/60→偏冷、31/60→偏热、25/80→偏湿
- M1-M4 单宿舍；M5 起 dorm-a / dorm-b / dorm-c 三节点、不能串线
- 技术边界：无数据库、真实传感器、LLM/RAG/Agent、正式 ML 训练；C 只做轻量 ML 应用闭环

## Git

- 本地沿用 F:\AIcoding 现有仓库（本目录为其中子目录），不新建仓库
- 提交风格：`type(scope): ...` 英文，如 `docs(nova-dommate-final-2026): ...`
- 不自动 commit / push；提交前先展示变更摘要
- Final 稳定版同步到用户 GitHub 账号的 `nova-dormmate-final-2026` 仓库（任务书 Page 3 & 11 原文拼写）
