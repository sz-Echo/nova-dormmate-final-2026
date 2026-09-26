# M2 详细执行计划 — 离线数据分析与报告

> 依据：docs/DORMMATE_SPEC.md、docs/PLAN.md、任务书 M2 原文。本文件是 M2 期间的执行依据，随进度更新；与 SPEC/PLAN 冲突时以 SPEC 为准。

## 1. 决策记录（已与用户确认）

- **CSV 读取库**：pandas（本机已装 3.0.5；任务书原文"csv /pandas"二选一；C 模块轻量 ML 也复用 pandas，全项目技术栈统一）
- **CSV 加 UTF-8 BOM**：验收要求 CSV 用 Excel / WPS 打开核对，中文 status 需 BOM 才不乱码；Python 端统一 `encoding="utf-8-sig"` 读取（有无 BOM 均正确）
- **关注记录口径**：任务书未明确定义，按 SPEC §8 注：status 非正常（偏冷 / 偏热 / 偏湿）即关注记录
- **M5 起 CSV 方案提前锁定**：三节点阶段每节点一个 CSV 文件（data/dorm-a.csv 等），保持 4 列不变（SPEC §5 推荐方案，全项目统一）；analyze.py 路径参数化天然支持每节点文件
- **数据来源红线（用户提醒）**：CSV 必须是 M1 Web 页面实际运行导出的文件，禁止手工在 Excel 改数据；time 必须全格式 YYYY-MM-DD HH:MM:SS（导出时原样输出，不用 toLocaleString）
- **"更换 CSV"语义（用户要求）**：analyze.py 不指定文件时自动选择 data/ 目录中最新的 CSV（旧文件保留、新文件生效）；提供 `--watch` 监控模式，放入 / 更换 CSV 后自动重新生成，无需手动指定路径

## 2. 范围红线（M2 不做）

- 不做 M3 Camera / ASR / TTS；不做多节点；无数据库 / 传感器 / LLM
- 不手工改 CSV 数据；不手工改 trend.png / report.html——验收要求换新 CSV 后产物全部由程序重新生成
- 不做 ML（那是 C 组）；不引入 pandas 之外的复杂分析
- M1-M4 单宿舍：data/dormmate.csv 严格 4 列（不含 nodeId / action）

## 3. 执行步骤（每步完成停下等用户确认）

### S0 文档对齐 ✅ 已完成（本文档 + PLAN 看板更新）

- 新建本文件；docs/PLAN.md §2 状态列 M2 → 进行中、§4 看板更新、§3 M2 行补"详细步骤见 docs/M2_PLAN.md"
- **检查点**：本文档存在、与 SPEC 一致、§4 衔接表覆盖 M1-M6 与 A/B/C

### S1 Web 导出 CSV（任务书：Blob / download）✅ 已完成（用户浏览器实测通过：4 列、中文正常、time 全格式、空历史提示、BOM）

- web/script.js 新增（顶层无 DOM，沿用 M1 约定）：
  - `buildCsv(history)` 纯函数：入参历史数组 → 返回 CSV 字符串；表头 `time,temperature,humidity,status`；严格 4 列（SPEC §5，不含 nodeId/action）；time 全格式原样输出；CRLF 换行
  - `downloadCsv()`：历史为空时提示不导出；`new Blob(["﻿" + csv], {type: "text/csv;charset=utf-8"})` + `URL.createObjectURL` + 临时 `<a download="dormmate.csv">` 点击后 `revokeObjectURL`
- web/index.html：历史区加"导出 CSV"按钮 `#exportBtn`，点击绑定放 DOMContentLoaded
- **检查点**：浏览器输入 ≥5 条（含四组回归）→ 导出 → WPS / 记事本打开：4 列表头、中文正常、time 全格式

### S2 Python 规则移植 + 四组回归自测 ✅ 已完成（--selftest 4/4 通过）

- 新建 analysis/analyze.py（单文件）；`compute_status(t, h)` 严格按 SPEC §3 顺序移植
- `python analysis/analyze.py --selftest` 跑 SPEC §6 四组断言（25/60→正常、16/60→偏冷、31/60→偏热、25/80→偏湿），全部打印通过 / 失败（沿用 web/test.html 证据思路）
- **检查点**：--selftest 四组全过

### S3 pandas 读 CSV + 统计（执行前先经用户确认安装 matplotlib）✅ 代码完成（临时 CSV 桩测通过，待用户真实 CSV 验收）

- `pip install matplotlib`（pandas 3.0.5 已装，无需重复安装）
- `pd.read_csv(path, encoding="utf-8-sig")`；CLI：`python analysis/analyze.py [csv路径]`，默认 `data/dormmate.csv`，不存在时明确报错
- 对全部记录**重跑统一规则**（status_calc）并与 CSV status 列比对，输出自查计数（数据来自 Web 导出应一致）
- 统计：记录数；温度 / 湿度最高最低（含对应 time）；各状态数量；**关注记录**（status 非正常）列表（time、温度、湿度、status）
- **检查点**：控制台统计与 CSV 人工核对一致（如 10 条记录、2 条关注）

### S4 matplotlib → data/trend.png ✅ 代码完成（Microsoft YaHei / SimHei 已注册，桩测无缺字警告，待用户打开验收）

- 中文字体：`plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]`；`axes.unicode_minus = False`
- 上 subplot：温度 / 湿度随时间折线（x=time，标签稀疏 / 旋转防重叠）；下 subplot：四状态数量柱状图；输出 data/trend.png
- **检查点**：打开 trend.png 中文正常、曲线与 CSV 数据吻合

### S5 report.html 生成 ✅ 代码完成（桩测报告三要素齐全、C3 扩展点注释就位，待用户打开验收）

- analyze.py 拼 HTML 字符串写 data/report.html：标题 + 生成时间、**摘要**表（记录数、温湿度最高 / 最低、各状态数量）、**关注记录**表、`<img src="trend.png">`；内嵌简单 CSS
- 结构分 section（summary / attention / trend），预留 ml section 注释（C3 IsolationForest 结果接回点）
- **检查点**：浏览器打开 report.html 三要素齐全、数据与 CSV 一致

### S6 换 CSV 全量重生成验收（任务书核心）✅ 已完成（用户用 dormmate2.csv（9 条）重跑：统计 / trend.png / report.html 全量重新生成、自查 0 条不一致；run1/run2 产物快照在 docs/evidence/m2/）

- 用 Web 页面再导出一份**不同数据**的 CSV（第二次实际运行导出，非手工改），分别跑 `python analysis/analyze.py data/xxx.csv`
- 核对两轮：统计、trend.png、report.html 均随数据变化且为程序覆盖重生成
- **检查点**：两份 CSV → 两轮产物各自一致；换 CSV 重跑即更新

### S7 验收 + 交接 + 提交 ✅ 已完成（README 补 M2 运行方式；PLAN 看板更新；控制台输出留档 docs/evidence/m2/；交接摘要按 PLAN §6；提交 feat(nova-dormmate-final-2026): M2 offline analysis CSV export and python report）

- 对照 §5 验收清单逐条走查；证据截图 docs/evidence/m2/（CSV 在 WPS/Excel 打开、控制台统计、trend.png、report.html 渲染、换 CSV 前后对比）
- README.md 补 M2 运行方式；PLAN.md §4 看板 M2 完成、§2 状态列；按 PLAN §6 模板输出交接摘要
- 提交（先展示变更摘要）：`feat(nova-dormmate-final-2026): M2 offline analysis CSV export and python report`

### S8 "更换后自动生成"增强 ✅ 已完成（测试1：不指定 CSV 自动选最新 new.csv（9 条）；测试2：--watch 放入两份 CSV 管线自动跑 2 次、最终报告为最新文件数据）

- analyze.py：不指定 CSV 时 `pick_csv()` 自动选输出目录中最新的 .csv；`--watch` 每 2 秒轮询，检测到新 / 更换的 CSV 自动重跑管线（单文件错误跳过不退出）；watch 输出 flush 防日志丢失
- 检查点：见 §1 决策记录"更换 CSV 语义"；README 运行方式已同步
- 提交：待用户确认后提交

## 4. 关键设计 — 与后续阶段衔接

按阶段维度（M1-M6 / A / B / C / Final）：

| 阶段 | 联系 |
|---|---|
| M1 | 复用 computeStatus()（Python 移植过同一四组回归）；导出源 = dormmateHistory 统一 JSON；4 列 CSV = JSON 去掉 nodeId/action |
| M3 | web/ 导出按钮与脚本保持可用；M3 复用 analyze() 不受影响；README 由 M3 补全 |
| M4 | 同一状态规则不重写；小程序可参考分析统计口径 |
| M5 | M2 决策记录**提前锁定**：三节点阶段每节点一个 CSV 保持 4 列（SPEC §5 推荐方案）；analyze.py 路径参数化天然支持每节点文件 |
| M6 | 3D 由 MQTT 驱动不读 CSV，无直接接口；状态口径一致 |
| A1 | 关注记录口径（status 非正常）与 A 组一致；analyze.py 按 time 处理记录的逻辑可作 A1 连续异常时长计算参考 |
| A2/A3 | action 字段 M2 仍为空、CSV 不含 action，不影响 A2 预留；A3"恢复由新数据触发"与 M2"重跑规则"同一思想 |
| B | report.html / 控制台统计全部程序生成不手写——B 组程序化说明的雏形，B 依赖此模式 |
| C1/C3 | data/*.csv 即 C1 数据源（特征 temperature/humidity 正是 CSV 列）；C3 IsolationForest 结果接回 report.html（S5 预留 ml section），扩展同一 analyze.py |
| Final | 离线链（Web→CSV→Python→trend.png/report.html）是 Final 重启复验两条链之一 |

## 5. 验收清单（完成线）

1. Web 页实际运行导出的 CSV：4 列表头、UTF-8、中文正常、time 全格式 YYYY-MM-DD HH:MM:SS（Blob + download）
2. pandas 重新读取 CSV + 基础统计（记录数、温湿度最高 / 最低）
3. 对全部记录重跑统一规则：各状态数量 + 关注记录（status 非正常）
4. matplotlib 生成 data/trend.png（中文正常、与数据吻合）
5. 自动生成 data/report.html（摘要、关注记录、趋势图三要素）
6. 换一份新 CSV 后统计、trend.png、report.html 全部由程序重新生成，禁止手工修改
7. 质量门禁：Python 四组回归全过；web/test.html 四组不回归；CSV 用 WPS / Excel 打开核对
8. 能解释数据流：Web 哪段代码导出、Python 哪段读 / 算 / 画 / 写

## 6. 验证方式

- `python analysis/analyze.py --selftest` 四组全过
- 浏览器导出 CSV 放 data/dormmate.csv → `python analysis/analyze.py` → 控制台统计 + 打开 trend.png / report.html 核对
- 换第二份 Web 导出的 CSV 重跑 → 三产物全部变化且一致
- web/test.html 四组仍全过；证据截图 → docs/evidence/m2/
