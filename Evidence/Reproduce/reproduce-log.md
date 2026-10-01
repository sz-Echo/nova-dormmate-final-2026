# 交叉复现日志（第一次冷执行）

- **复现日期**：2026-10-01（约 09:30-09:49）
- **复现方式**：Claude 以"从未接触项目的新同学"角色冷执行——唯一信息源 = 仓库 README.md 及 README 明确引用的仓库文件；明确禁区 = docs/V08R5_Plans/、docs/C01_Plans/、docs/PLAN.md、Evidence/、CLAUDE.md、git log（全程未打开）
- **环境准备**：项目外全新 venv（`%TEMP%\dormmate-repro\venv`，Python 3.14.4），依赖经清华镜像安装，Playwright chromium 就绪
- **完整过程截图**：`shots/`（22 张，文件名含步骤号）

## 复现时间线

| 时间 | 步骤 | 结果 |
|---|---|---|
| 09:30 | 环境盘点：Python 3.14.4 / Mosquitto 2.1.2 与 conf 四行配置 | 与 README 一致 |
| 09:31 | venv 创建 + 依赖安装 + chromium | 全部成功（约 2 分钟；pandas 装到 3.0.6，README 表写 3.0.5，属"最新"类差异） |
| 09:31 | 离线链：web 页回归四组 + 非法输入拦截四组 + CSV 导出 | 全部与 README 一致（BOM/4 列/表头正确） |
| 09:32 | CSV → `python analysis/analyze.py` → report.html | 自动选中最新 CSV；摘要/趋势/事件复盘/ML 异常分析区数值与 CSV 逐一核对一致；不理想案例（27.5℃/70%、0.6738）准确存在 |
| 09:32 | `web/test.html` 回归页 | 4/4 通过 |
| 09:35-09:44 | 实时链：Broker → simulator → 5510 静态服务 → Dashboard / 3D | 三节点同批刷新、多端同一条消息一致更新、互不串线、优先横幅动态切换 |
| 09:43 | D4 故障：发布坏 JSON `{bad` | Dashboard 横幅告警、丢弃计数 0→1、页面不受影响；重发合法消息立即恢复 |
| 09:44 | D5：c_ml.py 对照 + analyze.py 重跑 | 输出与 README 完全一致 |
| 09:44 | `python simulator/test_upgrade.py` | **exit 0 全部通过**（前置检查 + 协议帧 30 项 + 事件/优先广播断言 + 三端一致性 + D3 完整生命周期） |
| 09:44 | `dashboard/test-priority.html` / web 语音命令条 | 15 项 PASS / 指令匹配与未匹配提示正确 |
| 09:45-09:47 | 移动端（微信开发者工具） | 工具与 CLI 存在、project.config.json 有效；CLI 编译需 GUI 手动开启"服务端口"+ 人工授权，无法无人工干预验证（见卡点 ②） |
| 09:48-09:49 | 收尾 | 杀掉全部自启进程（1883/8083/5510 无残留）；删除临时脚本 |

## 卡点清单（7 条）

| # | 卡点 | 卡在哪一步 | 处理与 README 修订 |
|---|---|---|---|
| ① | MQTTX 未安装（README 标"可选"但未给替代路径） | 第六节"产生一条测试数据"方式 1 | README 补 paho-mqtt 一行等价发布命令（同 Broker/topic/payload） |
| ② | 微信开发者工具 CLI 需 GUI 手动开"服务端口"+人工授权，无法无人干预编译 | 移动端编译运行 | 非 README 缺陷；README 注明"移动端编译与同步核验需人工 GUI 操作"；协议帧 30 项与移动端联动已由 test_upgrade.py 自动化验证 |
| ③ | simulator 实测发布间隔 2.5 秒，README 写"每 3 秒" | 冷启动清单第 2/4 步预期核对 | README 改"约每 2.5 秒" |
| ④ | 离线链缺"把导出 CSV 放入 data/"衔接说明 | web 导出 CSV → analyze.py 之间 | README 离线分析处补一句 |
| ⑤ | report.html 实际区块名"摘要"，README 开头写"今日摘要" | 报告区块核对 | README 统一为"摘要 / 趋势 / 事件复盘 / ML 异常分析" |
| ⑥ | mobile/project.config.json 自带固定 appid，README 说选"测试号" | 移动端导入步骤 | README 注明"项目已带测试 appid wxd7c27e7d8b4c53e1，导入时保持默认" |
| ⑦ | 工具侧环境事实（非卡点，备查）：paho-mqtt 2.x 短生命周期 connect()+publish 无 loop 不发消息（用 connect_async+loop_start）；test_upgrade.py 运行会自写 Evidence/D1、E3 截图 | — | 不改 README；本条留档 |

## 复现结论（第一次）

- **离线分析链：完全跑通**——web 输入 → 统一规则 → 非法拦截 → CSV 导出 → analyze.py → report.html 五区数值逐一核对一致，回归四组全对
- **实时系统链：完全跑通**——Broker → simulator → Dashboard/3D 三节点实时更新、多端一致、不串线、坏 JSON 拦截、D3 事件完整生命周期；test_upgrade.py exit 0
- **移动端：部分验证**——工具与配置确认、协议帧 30 项单测通过、移动端联动自动化通过；GUI 编译无法无人干预
- **无卡点步骤**：venv+依赖安装、Mosquitto 配置、web 页全流程、analyze.py 全流程、组件启动、test_upgrade.py、D4/D5、test-priority、语音命令

## 产物清单

- 截图 22 张：`shots/`
- 复现数据：`repro-web-20261001.csv`（web 页导出、放入 data/ 跑通离线链后移入此处留证）
- venv：`%TEMP%\dormmate-repro\venv`（保留，第二次复现复用）
- README 修订 diff：`readme-revision.diff`
