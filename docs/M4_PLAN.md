# M4 详细执行计划 — 移动端小程序（微信原生小程序）

> 依据：docs/DORMMATE_SPEC.md、docs/PLAN.md、任务书 M4 原文（第 16-19 条）。本文件是 M4 期间的执行依据，随进度更新；与 SPEC/PLAN 冲突时以 SPEC 为准。

## 1. 决策记录（已与用户确认）

- **平台**：微信原生小程序（任务书关键词 WXML / WXSS / Page data / setData / bindinput / bindtap 均为小程序技术栈；不选 H5 / uni-app）
- **AppID**：微信开发者工具"测试号"模式（touristappid），不注册小程序账号、不做真机（SPEC §13 约定 2）
- **规则移植口径**：小程序无法直接 require web/script.js（含 window/document DOM 代码、无 module.exports，且小程序项目根为 mobile/）→ 按 M2 Python 同模式"移植纯函数 + 过 SPEC §6 同一四组回归"，逐行同语义，**不复制 Web DOM 代码**；web/ 保持不动（M1 已收口，避免回归）
- **演示数据**："载入演示数据"按钮预置 4 条模拟历史 = SPEC §6 四组回归数据（25/60 正常、16/60 偏冷、31/60 偏热、25/80 偏湿），时间取当前往前推几分钟，同时演示规则与"查看数据"
- **验收口径**：验收清单严格按任务书第 16-19 条组织，S5 时逐条对照走查
- **提交风格豁免**：M4 提交 `feat: M4 微信小程序复用DormMate统一规则` 为中文且无 scope，系用户指定（现场答辩口径），豁免 CLAUDE.md 的英文 type(scope) 风格要求（同 M3 三次提交先例）

## 2. 范围红线（M4 不做）

- 不做 AppID 注册 / 真机预览 / 发布（测试号即可）
- 不做 MQTT 订阅（M5 起可选，仅注释预留）；不做 Camera / ASR / TTS（M3 是 web 侧，M3_PLAN §4 已定小程序不要求）
- 单宿舍 dorm-a；无数据库 / 传感器 / LLM
- 小程序内不做 CSV 导出（离线链在 M2 web 侧已覆盖）
- 不改 web/、analysis/、data/；不建 simulator/ dashboard/ three3d/（未解锁阶段）

## 3. 执行步骤（每步完成停下等用户确认）

### S0 文档对齐 ✅ 已完成（2026-09-27：本文件创建 + PLAN 看板更新；用户已批准计划并确认 4 项决策；微信开发者工具已安装——稳定版 2.02.2608070）

### S1 小程序骨架 ✅ 已完成（2026-09-27：mobile/ 全部文件已建；冷启动渲染用户已验证通过）

- 新建 mobile/（= 开发者工具项目根）：
  - `app.json`（pages 注册 + window：navigationBarTitleText "DormMate"）
  - `app.js`（App({}) 最小实现）、`app.wxss`（全局字体 / 卡片 / 配色）
  - `pages/index/index.wxml` + `index.wxss` + `index.js` + `index.json`
- WXML 区块：标题 DormMate → 环境输入（温度、湿度 input + 分析环境 / 载入演示数据按钮）→ 错误提示区 → 当前状态（status 大字 + advice）→ 历史记录列表（wx:for，空时"暂无记录"占位）
- 开发者工具"导入项目"选 mobile/，AppID 选"测试号"；project.config.json 由工具自动生成
- **检查点**：模拟器冷启动渲染页面，布局齐全

### S2 规则移植 + 四组回归 ✅ 已完成（2026-09-27：rules.js 移植 + onLoad 自动自测，Console 4 行 PASS 用户已确认）

- 新建 `mobile/utils/rules.js`，从 web/script.js 逐行移植（文件头注释注明来源与 SPEC §3/§3.1/§6）：
  - `computeStatus(temperature, humidity)`（顺序不可改：<18 偏冷 → ≥30 偏热 → ≥75 偏湿 → 正常）
  - `ADVICE`（偏冷→注意保暖 / 偏热→注意通风 / 偏湿→注意除湿 / 正常→环境舒适）
  - `TEMP_MIN/-50、TEMP_MAX/50、HUMIDITY_MIN/0、HUMIDITY_MAX/100`、`validateField`、`validateInputs`
  - `pad2`、`formatTime`（YYYY-MM-DD HH:MM:SS）、`runRulesSelfTest()`（跑四组比对，逐行打印 PASS/FAIL）
  - 全部 `module.exports` 导出
- **检查点**：页面 onLoad 自动执行 runRulesSelfTest()，Console 输出 4 行回归 PASS + ADVICE / 校验 / formatTime 附加校验行全 PASS；截图（对应 web/test.html 的角色）
- **备注（2026-09-27 实测修复）**：开发者工具 Console 直接敲 require 报 "require is not defined"，自测改为 onLoad 自动执行，无需手动命令

### S3 页面交互（Page data / setData / bindinput / bindtap） ✅ 已完成（2026-09-27 用户实测：输入 / 拦截 / 历史 / 演示数据全部通过）

- `index.js`：
  - `data: { temperature:"", humidity:"", status:"—", advice:"—", errorMsg:"", history:[] }`
  - `bindinput="onTempInput"/"onHumidityInput"` → `e.detail.value` → `setData`
  - `bindtap="onAnalyze"`：`validateInputs` → 有错 setData errorMsg（不分析、不追加历史）；合法 → `computeStatus` + `ADVICE` → setData 状态/建议/清错误 → 记录 `{nodeId:"dorm-a",temperature,humidity,status,time:formatTime(new Date()),action:""}`（SPEC §4 统一 JSON）→ `setData({history: this.data.history.concat(record)})`
  - `bindtap="onLoadDemo"`：预置 4 条演示历史（四个状态各一，time 依次往前推）
  - 输入框 `bindconfirm="onAnalyze"`（对应 M1 的 Enter 体验）；温度 input 用 `type="text"`（小程序数字键盘无负号，温度范围 −50~50 含负数，与 M1 README 已知限制一致；text 也便于演示非数字校验拦截）
- `index.wxss`：状态大字高亮、卡片式三区块、错误红色提示（对应 M1 自定义样式，能指出位置）
- **检查点**：模拟器输入 31/60 → 偏热+注意通风；25/80 → 偏湿+注意除湿；非法输入（空 / 非数字 / 60℃ / 120%）被拦截且提示原因
- **提交（用户确认后）**：实际提交 `feat: M4 微信小程序复用DormMate统一规则`（用户指定消息，cb947ff；替代本行原计划的英文消息）

### S4 冷启动 + 新数据验收（任务书第 18-19 条） ✅ 已完成（2026-09-27 用户实测：冷启动正常 / 31-60 偏热+注意通风 / 演示数据 4 条 / 拦截提示 / Console 4 行 PASS；证据 = docs/evidence/m4/ review 归档 + 用户实测记录，截图非 M4 完成线要求、无需补拍）

- 完全退出微信开发者工具 → 重新打开 → 打开 mobile/ 项目 → 页面正常渲染
- 现场输入 3 组新数据（如 31/60、16/60、25/80）→ 状态 / 建议正确变化、历史逐条追加
- 截图留存 docs/evidence/m4/（冷启动截图、新数据结果截图、四组回归 Console 截图、页面布局截图）

### S5 验收 + 交接 ✅ 已完成（2026-09-27：验收清单第 16-19 条走查通过、README 补小程序运行方式、PLAN 看板收口、提交 feat: M4 微信小程序复用DormMate统一规则）

- 对照验收清单逐条走查；README 补 M4 运行方式（开发者工具导入 mobile/、测试号、Console 回归自测命令）与已知限制（数字键盘无负号）
- 更新 PLAN.md §4 看板（M4 完成）与 §2 状态列；按 PLAN §6 模板输出交接摘要
- **提交（用户确认后）**：实际随 cb947ff 一次提交（用户指定消息）

### S6 评审修复（code-review 10 finder） ✅ 代码完成（用户开发者工具复测通过）

- 配置（用户确认）：appid 按开发者工具"测试号"自动写入的值提交（wxd7c27e7d8b4c53e1），文档口径统一为"测试号（工具自动填入测试 AppID）"；project.private.config.json 入 .gitignore 并取消跟踪（本地文件保留）
- 行为：载入演示数据改 concat 追加（不再覆盖真实记录）；demo 时间改 4/3/2/1 分钟前（不再等于点击时刻）
- 复用：rules.js 导出 REGRESSION_CASES / buildRecord，自测与演示数据共用同一份回归数据与同一记录构造；onAnalyze 删除 bindtap 用不到的返回值；validateInputs 补"失败返回值不可用"调用契约注释
- 自测加固（用户确认）：四组回归 4 行 PASS 保持在前，其后追加 ADVICE 映射 / validateField 边界与拦截 / formatTime 补零校验行
- 文档：§8 工具风险行改已解决；S3/S5 提交信息更正为实际消息；§1 补提交风格豁免；README 已知限制补小程序 type="text" 与 wx:key 条目；PLAN 看板去重 + GitHub 同步跟踪；index.js 补 MQTT 预留注释
- 接受不改：wx:key 同秒重复（SPEC §4 禁止额外字段，无干净修复）→ README 记为已知限制；其余不采纳项与理由见评审修复计划
- **检查点（用户）**：清缓存编译 → 冷启动（touristappid）→ Console 四组回归 + 附加校验全 PASS → 演示数据追加不覆盖真实记录
- **提交**：已提交（6b0e91b fix(nova-dormmate-final-2026): M4 code review fixes）

## 4. 关键设计 — 与 M1-M6 / A / B / C 联系

| 阶段 | 联系 |
|---|---|
| M1 | computeStatus / ADVICE / 校验范围移植（同语义 + 同一四组回归）；记录结构 = SPEC §4 统一 JSON（nodeId dorm-a、action ""）；**不复制 Web DOM 代码**；web/ 不改动 |
| M2 | 离线链（web→CSV→Python→trend/report）不受影响；小程序历史字段与 CSV 4 列同源（time/temperature/humidity/status）；小程序不做 CSV 导出（红线） |
| M3 | 小程序不要求 Camera/ASR/TTS（M3_PLAN §4 已定）；M3 产物不迁移 |
| M4 自身 | 任务书第 16-19 条逐条对应验收清单（见 §5） |
| M5 | 单宿舍占位 dorm-a；记录 JSON 已含 nodeId，M5 三节点只需换 nodeId；MQTT 订阅 M5 起可选（代码注释预留，不实现） |
| M6 | 无直接接口（3D 由 MQTT 驱动，与小程序平行） |
| A | action 字段 M1-M4 恒 ""（SPEC §4），A2 动作状态 M5+ 实现；小程序记录结构已预留兼容，无需后期改结构 |
| B | M4 证据截图是 B 组程序化说明的素材来源；说明由 B 阶段程序生成，M4 不手写 |
| C | 无直接接口（C 复用离线链 CSV + report.html 扩展点） |
| Final | mobile/ 在最终提交清单（SPEC §11）；Final 重启复验时顺带打开小程序确认可运行 |

## 5. 验收清单（任务书第 16-19 条 + 项目门禁）

1. **第 16 条（规则迁移）**：同一套 DormMate 核心业务规则迁移到小程序——computeStatus 纯函数移植、顺序不可改；不复制 Web DOM 代码；四组回归全过（25/60→正常、16/60→偏冷、31/60→偏热、25/80→偏湿）
2. **第 17 条（技术关键词）**：WXML（页面结构）/ WXSS（样式）/ Page data（页面数据）/ setData（数据更新）/ bindinput（输入绑定）/ bindtap（按钮绑定）全部落地，现场能指出每个关键词对应哪段代码
3. **第 18 条（冷启动）**：微信开发者工具从关闭状态打开，小程序正常运行（测试号，无 AppID/真机）
4. **第 19 条（新数据）**：输入新数据得到正确状态 / 建议（现场 3 组新数据，状态+建议正确变化；非法输入拦截）
5. **项目门禁（非任务书）**：开发者工具稳定运行核心页面；证据截图 docs/evidence/m4/；README 补 M4 运行方式

## 6. 现场演示剧本（S5 照着走）

**准备**：微信开发者工具登录（测试号）→ 导入 mobile/ → 模拟器运行。

1. **冷启动（第 18 条）**：关闭开发者工具 → 重新打开 → 打开项目 → 页面正常
2. **输入新数据（第 19 条）**：输入 31/60 → 偏热、注意通风；25/80 → 偏湿、注意除湿；16/60 → 偏冷、注意保暖；再试一组非法输入（如 60℃ / 120%）→ 拦截提示
3. **技术关键词（第 17 条）**：打开 index.wxml 指出 bindinput/bindtap 位置、index.js 指出 Page data 与 setData、WXSS 指出样式
4. **规则迁移（第 16 条）**：打开项目时 Console 自动输出四组回归 PASS 与 ADVICE / 校验 / formatTime 附加校验行（onLoad 自动执行 runRulesSelfTest）；对照 web/script.js 的 computeStatus 说明同一套规则（顺序不可改）
5. **查看数据**：点"载入演示数据" → 4 条历史（四个状态各一）→ 再手动分析几条，历史逐条追加、带时间与 nodeId

## 7. 验证方式

- Console：页面 onLoad 自动执行 runRulesSelfTest()，输出四组回归 PASS + 附加校验行全 PASS
- 冷启动（关闭重开）+ 现场 3 组新数据，按演示剧本走查
- 证据截图 → docs/evidence/m4/，随 M4 提交

## 8. 风险

- ~~工具未安装~~ ✅ 已解决（2026-09-27 安装稳定版 2.02.2608070）；后续工具问题按 SPEC §13 约定 5 检索排查
- 基础库版本差异 → 用开发者工具默认基础库，不用新特性
- 测试号无法真机预览 → 完成线不要求真机（SPEC §13 约定 2）
- 小程序数字键盘无负号 → 温度输入框 type="text"（与 M1 已知限制一致）
