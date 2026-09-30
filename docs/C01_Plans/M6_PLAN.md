# M6 详细执行计划 — Three.js 3D 可视化（three3d/）

> 依据：docs/DORMMATE_SPEC.md、docs/PLAN.md、任务书 M6 原文（条目口径按用户截图确认）。本文件是 M6 期间的执行依据，随进度更新；与 SPEC/PLAN 冲突时以 SPEC 为准。

## 1. 决策记录（已与用户确认）

1. **Three.js 引入**：本地 vendor **r128（0.128.0）UMD** —— `build/three.min.js` + `examples/js/controls/OrbitControls.js` 放 three3d/vendor/；mqtt.min.js 从 dashboard/vendor/ 拷贝（已验证文件，免下载）。理由：r128 是最后"examples/js + UMD 双齐全"版本（examples/js 于 r148 删除、UMD build 于 r160 删除），纯 `<script>` 零构建，与 M5 vendor 模式一致、断网可跑；下载 URL 必须带 `@0.128.0` 精确版本号
2. **规则零重写**：three3d/index.html 直接 `<script src="../web/script.js">` 复用 `window.computeStatus / ADVICE / validateInputs`（与 dashboard 同款，SPEC §6 四组回归同一实现）
3. **校验链零重写**：handleMessage 逐行对齐 dashboard/app.js 98-181 行（JSON.parse try...catch → 对象类型守卫 → 六字段存在校验 → nodeId 字符串 → time 类型+格式正则 → validateInputs §3.1 范围校验 → **串线防线**（topic 第二段 nodeId == 消息 nodeId，否则丢弃+横幅+计数）→ 未知节点丢弃 → **status 用 window.computeStatus 重算，不信任消息里的值**），只把最后的"更新卡片"换成 `updateScene(nodeId, record)`
4. **唯一更新入口** `updateScene(nodeId, record)`：MQTT 消息与本地演示按钮一律经它进入 3D；requestAnimationFrame 渲染循环只做粒子/球动画，不做数据
5. **视觉映射：全套 4 类状态可见变化**（任务书要求 ≥3 类）：① 建筑主色 ② 发光指示球（颜色+高度）③ 楼顶粒子动画（偏冷飘雪/偏湿下雨/偏热热气/正常平静）④ CanvasTexture 中文标牌；色值与 dashboard 卡片色一致
6. **本地演示按钮**：侧栏 4 个按钮（SPEC §6 四组回归值 25/60、16/60、31/60、25/80）作用于当前选中楼——"四组回归逐一打出四状态"验收镜头 + Broker 未启动时的降级演示
7. **点击选中（A1 基础）**：Raycaster + pointer 位移阈值 <5px（区分 OrbitControls 拖拽）；`selectedNodeId` + 每节点 60 条历史（供 A1 程序计算连续异常时长）
8. **A2 预留**：每楼屋顶 fanGroup 风扇 mesh（hub + 3 叶片，M6 静止不转，注释标明 A2 挂点——A2 写 fan_on 后叶片绕 y 转动）；action 字段 M6 恒 ""，不做 actionState
9. **证据形式**：截图 + 录屏（任务书：3D 截图/录屏）
10. **场景规模**：地面 + GridHelper + 3 栋楼（每栋 body/roof/door/2 窗/标牌/指示球/粒子/风扇/选中环 ≈ 11 个对象）≈ **35+ 对象**（任务书 ≥2 对象达标，现场可数）

## 2. 范围红线（M6 不做）

- 不改 web/、dashboard/、simulator/、analysis/、mobile/ 已验收代码（dashboard/vendor/mqtt.min.js 只读拷贝，不改原文件）
- 不落盘 CSV、无数据库、无新数据源；status 一律由本地 window.computeStatus 重算，禁止信任消息里的 status（SPEC §4）
- 不做 A1 优先关注计算、A2 风扇动作（只预留 mesh 与注释挂点）、A3（依赖 A2）
- 不做游戏级渲染：无阴影贴图、无后处理；粒子总量 ≤900（3 楼 × 250 点）

## 3. 文件清单与职责

```
three3d/
├── index.html          页面骨架：状态栏（连接/收到/丢弃/警示横幅，dashboard 同款）+ canvas 容器 + 详情侧栏 + 演示按钮
├── style.css           全屏画布布局、覆盖层状态栏、警示横幅、侧栏面板、演示按钮（配色变量沿用 dashboard :root 色值）
├── app.js              全部逻辑（唯一 JS 入口）
└── vendor/
    ├── three.min.js        r128 UMD（≈600KB）
    ├── OrbitControls.js    r128 examples/js 版（挂 THREE.OrbitControls，≈30KB）
    └── mqtt.min.js         拷贝自 dashboard/vendor/mqtt.min.js（mqtt.js v5）
```

index.html 脚本引入顺序（顺序即依赖，不可调换）：

```html
<script src="../web/script.js"></script>            <!-- 规则：computeStatus/ADVICE/validateInputs -->
<script src="vendor/three.min.js"></script>
<script src="vendor/OrbitControls.js"></script>      <!-- 依赖 THREE 全局 -->
<script src="vendor/mqtt.min.js"></script>
<script src="app.js"></script>
```

### app.js 函数骨架（函数名即验收指认点）

- 常量（与 dashboard 同款）：`WS_URL = "ws://localhost:8083"`、`TOPIC = "dormmate/+/env"`、`NODE_IDS`、`HISTORY_LIMIT = 60`、`REQUIRED_FIELDS` 六字段、`TIME_PATTERN`、单例 `utf8Decoder`
- `STATUS_STYLE` 映射表（见 §4）；`dormVisuals = { nodeId: { group, status, sphereTargetY, bodyMat, sphere, sphereMat, pointLight, sign, signCtx, signTexture, particles, fanBlades, ring } }`；`nodes = { nodeId: { latest, history[] } }`
- `initScene()`：WebGL 预检（测试 canvas `getContext("webgl")` + `new THREE.WebGLRenderer` 包 try...catch，失败显示降级横幅不白屏）→ **`scene = new THREE.Scene()`** → **`camera = new THREE.PerspectiveCamera(50, aspect, 0.1, 200)`** → **`renderer = new THREE.WebGLRenderer({ antialias: true })`**（`renderer.outputEncoding = THREE.sRGBEncoding`，r128 写法）→ `controls = new THREE.OrbitControls(camera, renderer.domElement)` → 环境光 0.55 + 方向光 0.8（10,20,10）→ 地面 PlaneGeometry(60,60) + GridHelper(60,20) → `NODE_IDS.forEach((id, i) => buildDorm(id, (i - 1) * 8))`（x = -8 / 0 / 8）→ resize 自适应
- `buildDorm(nodeId, x)`：group（body=Box(3,4,3)+MeshLambertMaterial、roof=Cone(2.3,1.5,4)、door、2 窗、signboard=Plane(2.2,1.1)+CanvasTexture、statusSphere=Sphere(0.35)+PointLight(状态色,0.8,8)、particles=Points、fanGroup、ring=Ring 贴地默认隐藏）；每个 mesh `userData.dormId = nodeId` 供 raycast 反查
- `createSign()` / `drawSign()`：canvas 512×256，`ctx.font = 'bold 42px "Microsoft YaHei", sans-serif'`（系统字体，中文免加载）；CanvasTexture `encoding = sRGBEncoding`、`minFilter = LinearFilter`、`generateMipmaps = false`（防糊）；**每次更新标牌必须 `texture.needsUpdate = true`**（最容易漏）
- `buildParticles()`：THREE.Points + BufferGeometry（r125 起 Geometry 已删，必须 BufferGeometry）+ PointsMaterial({size:0.15, transparent, opacity:0.9})；每楼 250 点；positions Float32Array **原地改值 + attribute.needsUpdate，绝不重建几何**
- `updateScene(nodeId, record)`：status 用 window.computeStatus 重算 → 落六字段记录 {nodeId, temperature, humidity, status, time, action} → nodes 更新（history 60 条裁剪）→ setDormStatus（`material.color.set()`，不重建 material/mesh）→ drawSign（标牌：节点名/状态/温湿度/建议查 window.ADVICE/时间）→ 选中节点则同步刷新侧栏
- `animate()` / `updateDormAnimation(nodeId, dt)`：粒子按 mode 下落/上升/漂浮（落地/出区域重置）；球 y 向 targetY lerp + 脉动缩放；`renderer.render(scene, camera)`
- `handleMessage(topic, text)` / `drop(reason)` / `setConnState(online, text)`：校验链同 dashboard/app.js 98-181；drop 带时间戳横幅 + 计数 + console.warn（成功路径不清横幅，dashboard 同款）；mqtt.js `reconnectPeriod: 2000`；payload 用单例 TextDecoder 解码
- 点击 vs 拖拽：pointerdown 记起点、pointerup 位移 <5px 才 `handleClick`（raycaster.setFromCamera → intersectObjects(楼群组, true) → userData.dormId → selectDorm；点地面取消选中）
- `selectDorm(nodeId)`：ring 显隐 + bodyMat.emissive 高亮 + 侧栏详情（状态/温湿度/建议/时间/最近 5 条历史）
- `applyDemoRecord(nodeId, temperature, humidity)`：time 本地格式化（复用 window.formatTime 存在性检查，兜底本地 pad2）→ 构造六字段 record（action ""）→ updateScene

## 4. 四状态视觉映射表（色值与 dashboard 卡片色一致）

| 状态 | 建筑主色（body material） | 指示球（颜色+高度 sphereY） | 粒子动画（楼顶 y 5~9，250 点） | 标牌内容（CanvasTexture） |
|---|---|---|---|---|
| 正常 | `#27ae60` 绿 | `#2ecc71` 绿球，y=2.2（最低） | calm：少量浅绿尘埃缓慢漂浮（几乎平静） | `dorm-a · 正常` / `25.0℃ / 60%` / `环境舒适` / 时间 |
| 偏冷 | `#4a90d9` 蓝 | `#5dade2` 蓝球，y=3.7 | snow：白色雪点缓速下落 + 轻微横向漂移，落地重置 | `dorm-a · 偏冷` / `16.0℃ / 60%` / `注意保暖` / 时间 |
| 偏热 | `#e67e22` 橙 | `#f39c12` 橙球，y=4.4（最高） | heat：橙红点从屋顶向上升腾，出区域重置 | `dorm-a · 偏热` / `31.0℃ / 60%` / `注意通风` / 时间 |
| 偏湿 | `#16a085` 青 | `#1abc9c` 青球，y=3.0 | rain：青色雨点快速下落，落地重置 | `dorm-a · 偏湿` / `25.0℃ / 80%` / `注意除湿` / 时间 |

- 建议文案查 `window.ADVICE`（与 web/script.js 同一来源）
- 球高度是纯视觉区分（装饰性），与 A1 优先级规则无关（代码注释注明）
- 所有颜色切换用 `material.color.set()`，不重建 material/mesh；球 y 用 lerp 平滑过渡

## 5. 技术坑与对策（已按 r128 API 逐一核验）

1. **vendor 版本漂移（最高危）**：three.js r148 删除 examples/js、r160 删除 UMD build、r152 起 outputEncoding 改名。对策：下载 URL 钉死 `@0.128.0`，三备源依次尝试：
   - `https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js`
   - `https://unpkg.com/three@0.128.0/build/three.min.js`
   - `https://registry.npmmirror.com/three/0.128.0/files/build/three.min.js`（国内镜像）
   - OrbitControls 对应三源同路径换 `examples/js/controls/OrbitControls.js`；三源全失败 → 请用户浏览器手动打开 URL 另存为（给出精确地址）
   - S1 校验：文件大小（≈600KB / ≈30KB）+ 文件头 `three.js r128` 版本横幅
2. **OrbitControls 拖拽 vs click 冲突**：拖拽旋转松手会触发 pointerup，若直接 raycast 会把"旋转"误判为"选中"。对策：pointer 位移阈值 <5px（§3 骨架已内置）；OrbitControls 与 pointer 监听同绑 renderer.domElement，互不干扰
3. **CanvasTexture 中文**：canvas 2D fillText 用系统字体（Microsoft YaHei）渲染中文无网络依赖；两个坑：① 更新后必须 `needsUpdate = true` ② 默认 mipmap 发糊——设 LinearFilter + generateMipmaps=false + 512×256 高清倍率
4. **WebGL 不可用**（备用机/远程桌面）：initScene 首步预检 + try...catch，失败显示全屏中文降级横幅（原因+建议），页面其余功能（MQTT 状态栏）仍工作、不白屏
5. **Live Server 相对路径**：`../web/script.js` 要求"项目根为工作区 + Live Server 从项目根起服务"；路径错误 → 复用 dashboard 的 rulesMissing 防御（横幅提示，不白屏）；file:// 双击不在支持范围（README 写明）
6. **断线重连**：mqtt.js v5 重连后自动重新订阅；场景内存态断线期间保留，重连后下一条模拟消息自动刷新全部视觉；状态栏"已断开，重连中…"即可（冷启动演示关键点）
7. **两页面同订一个 Broker**：dashboard 与 three3d 同时订阅 `dormmate/+/env` 是 MQTT 正常多订阅者行为，互不冲突；演示可并排两个窗口对比
8. **演示时四状态凑不齐**：模拟器随机游走未必短期跑遍四状态 → MQTTX 手发 + 本地演示按钮双保险（§7 剧本第 3、4 步）

## 6. 执行步骤（每步完成停下等用户确认）

### S0 文档对齐 ✅ 已完成（2026-09-28：本文件创建 + PLAN 看板更新；3 项选择 + 10 项决策经用户批准执行；M5 GitHub 同步当日完成——subtree push 首次因网络失败、重试成功，GitHub 更新至 0283170）

### S1 vendor 文件落地 ✅ 已完成（2026-09-28：jsdelivr 第 1 源即成功；three.min.js 603KB + OrbitControls.js 26KB + mqtt.min.js 342KB 拷贝；REVISION="128" 版本核验通过；用户确认）

### S2 静态场景（Three 骨架）

- 建 three3d/index.html + style.css + app.js：initScene / buildDorm / createSignTexture / buildParticles / OrbitControls / resize 自适应 / WebGL 预检 / 点击选中 + 侧栏（先静态占位数据）
- 验证点：Live Server（项目根为工作区）打开 three3d/index.html——三栋楼 + 地面 + 标牌（中文正常）+ 球可见；拖拽旋转/缩放流畅；拖拽不误选、点击楼高亮 + 侧栏；Console 无报错
- 检查点：用户看到场景并可旋转（**vendor 文件的真实验收**）
- 状态（2026-09-28）：three3d/index.html + style.css + app.js 已建（场景/灯光/地面/三栋楼/标牌/指示球/粒子/风扇/选中环/OrbitControls/点击选中/WebGL 预检），node --check 语法通过；用户实测确认后进入 S3

### S3 updateScene 状态映射（离数据驱动）

- 实现 STATUS_STYLE、setDormStatus、updateScene、drawSign、animate 循环（粒子/球动画）、本地演示按钮（四组回归）
- 验证点：点侧栏 4 个按钮（25/60、16/60、31/60、25/80）→ 对应楼逐一打出四状态：建筑变色、球变色变高、粒子切换（雪/雨/热气/平静）、标牌文字与建议更新；过渡平滑
- 检查点：用户逐一打出四状态并截图（docs/evidence/m6/）
- 状态（2026-09-28）：STATUS_STYLE 四状态映射 / setDormStatus / updateScene（唯一入口）/ drawSign 四行标牌 / 粒子四模式动画 / 球 lerp+脉动 / 演示按钮已实现，node --check 语法通过，用户实测确认（四状态逐一打出）✅

### S4 MQTT 实时驱动

- 加 mqtt.js 连接/订阅/handleMessage（校验链逐行对齐 dashboard/app.js 98-181 行）/状态栏/警示横幅/丢弃计数
- 验证点：① Mosquitto + simulator 启动 → 三栋楼每 2-3 秒随数据变化、互不串线 ② MQTTX 手发一条消息 → 对应楼 3D 即时变化（必演镜头）③ MQTTX 发坏 JSON/缺字段/串线消息 → 横幅 + 丢弃计数、场景不动不崩 ④ 关 Broker 再开 → "重连中…"→ 自动恢复实时刷新
- 检查点：用户实测 ①-④ 全过
- 状态（2026-09-28）：mqtt.js 连接/订阅 + handleMessage 校验链（与 dashboard/app.js 同序同款：JSON.parse 容错 → 对象守卫 → 六字段 → time 格式 → validateInputs → 串线防线 → 未知节点 → status 重算）+ 状态栏/丢弃横幅计数 + reconnectPeriod 2000 已实现，用户实测 ①-④ 确认 ✅

### S5 验收交接

- 按 §8 验收清单走查 + §7 演示剧本完整走一遍并截图/录屏 → docs/evidence/m6/
- README.md 补 M6 运行方式（vendor 来源、Broker → simulator → Live Server 启动顺序）；PLAN 看板收口
- 提交（先展示变更摘要，用户确认）；GitHub 同步（先展示命令，用户确认）
- 检查点：用户确认证据与提交
- 状态（2026-09-28）：README 已补 M6 运行方式/主要功能/文档索引；PLAN 看板收口；**证据自动化验证完成**（Playwright + paho-mqtt，用户委托）——10 张自动化截图 + 1 录屏 + 3 张用户手拍（shot-1/2/3）落 docs/evidence/m6/，逐项程序化断言全过：① simulator 实时驱动（已连接+收到 12 条）② 物理点击选中/取消 + 四状态演示（bodyMat 颜色逐一 == 期望 hex，截后复核）③ MQTT 单条 16/60（status 故意写错）→ dorm-c 变蓝 4a90d9 + 侧栏"偏冷"（规则重算）④ 坏 JSON/缺字段/串线逐条丢弃计数递增 + 横幅 ⑤ 停 Broker →"已断开，重连中…"→ 重启 →"已连接"+收到 40 条；console 唯一报错为 Broker 停机窗口的 WebSocket ERR_CONNECTION_REFUSED（重连测试预期行为，非应用缺陷）；提交完成 415c9db（23 文件）；GitHub 已同步至 aef28b5（2026-09-28 subtree push 一次成功）

### S6 评审修复

- code-review 走查（对齐 M5 S6 的 10 角度经验），重点：校验链与 dashboard 一致性、updateScene 唯一入口、粒子不重建几何、needsUpdate 无遗漏、error 路径不白屏；修复后用户复测
- 检查点：用户复测通过；提交修复
- 状态（2026-09-28）：code-review 完成（14 项确认发现）——修复 9 项：演示路径 rulesMissing 防御 / 选中环·风扇·粒子打标（点击环不再误取消选中）/ pointer 仅左键+pointercancel / CanvasTexture sRGBEncoding / action 强制 ""（M6 恒空）/ vendor 缺失多层防御（顶层常量·OrbitControls·mqtt·启动 try）/ 无 WebGL 时消息一次性 drop 提示 / 标牌内容不变跳过重绘 / document.hidden 暂停渲染；遗留 3 项（共享校验模块抽取需改 dashboard 违反 M6 红线暂缓、色值三处定义已注释说明、演示记录混入 history 留 A 阶段处理）；全量自动化回归复测通过，用户复测确认；提交 7e72183（GitHub 已同步至 44b391c）；**追加修复（用户复测发现）**：Edge「鼠标手势」导致右键左划=浏览器返回退出页面——浏览器级手势网页无法拦截，用户侧关闭（Edge 设置→外观→鼠标手势，README 已记录）+ 代码侧防御加固（style.css `touch-action: none`/`overscroll-behavior: none` + pointerdown touch/pen preventDefault，触摸屏同样受益）

## 7. 现场演示剧本（S5 照着走）

**准备**：关闭所有进程 → `mosquitto -c "<实际路径>\mosquitto.conf" -v` → `python simulator/simulate.py` → Live Server（项目根为工作区）→ 打开 three3d/index.html（可并排再开 dashboard 作对照）。

1. **场景初览 + 关键词现场指认**：旋转/缩放一圈；打开 app.js 现场指出 `scene`（`scene = new THREE.Scene()`）、`camera`（PerspectiveCamera）、`renderer`（WebGLRenderer）、`mesh`（buildDorm 里的 `new THREE.Mesh(...)`）、`material`（MeshLambertMaterial / MeshBasicMaterial / PointsMaterial）、`updateScene`（唯一更新入口函数）、`JSON.parse`（handleMessage 里）
2. **实时驱动**：simulator 三节点持续发布 → 三栋楼建筑色/球高/粒子/标牌时间随数据跳动，互不串线
3. **MQTTX 必演镜头（≥1 条实时消息驱动 3D）**：MQTTX 向 `dormmate/dorm-c/env` 手发：
   ```json
   {"nodeId":"dorm-c","temperature":16,"humidity":60,"status":"偏热","time":"2026-09-28 10:30:00","action":""}
   ```
   status 故意写错（16℃ 应判偏冷）→ dorm-c 楼 3D 立即变蓝 + 雪粒子 + 标牌"偏冷 · 注意保暖"——一条消息同时证明"实时消息驱动 3D"与"status 由规则重算、不信任消息值"（SPEC §4）
4. **四组回归逐一打出四状态**：选中 dorm-a，依次点演示按钮（或 MQTTX 依次发 25/60、16/60、31/60、25/80）→ 绿正常 → 蓝偏冷 → 橙偏热 → 青偏湿，四状态视觉逐一呈现，截图四张
5. **串线与坏消息防线**：MQTTX 发 topic=dormmate/dorm-a/env 但 nodeId=dorm-b → 红色横幅 + 丢弃计数 +1、场景不变；再发一条坏 JSON → 同样拦截不白屏
6. **点击选中（A1 预留）**：点 dorm-b → 高亮 + 侧栏详情；先拖拽旋转再松手 → 不误选中
7. **冷启动复验**：关 Broker → 状态栏"已断开，重连中…"→ 重启 Broker → 自动恢复实时刷新（dashboard 同款）

## 8. 验收清单（任务书条目 + SPEC §8 完成线 + 项目门禁）

1. **≥2 个对象**：3 栋 × ≈11 个 mesh/Points + 地面 + GridHelper ≈ 35+ 对象，现场可数
2. **≥3 类状态可见变化**：4 类（建筑主色 / 指示球 / 粒子动画 / 标牌文字）全部由 updateScene 统一驱动
3. **≥1 条实时消息驱动 3D**：MQTTX 手发一条 → 对应楼 3D 即时变化（剧本第 3 步，录屏留证）
4. **关键词落地**：Three.js / scene / camera / renderer / mesh / material / updateScene / JSON.parse 在 app.js 中均为真实命名，现场能指出每处对应哪段代码
5. **三节点互不串线**：独立 topic（dormmate/{nodeId}/env）+ topic↔nodeId 双防线（SPEC §12）；串线消息被丢弃且有证据
6. **项目门禁**：SPEC §6 四组回归数据逐一打出四状态（复用 web/script.js 同一实现，规则零重写）；证据截图/录屏 docs/evidence/m6/；README 补 M6；提交 + GitHub 同步（先展示摘要/命令，用户确认）

（条目口径按用户截图组织；如截图编号有出入，以截图为准修正。）

## 9. 关键设计 — 与 M1-M6 / A / B / C 联系

| 阶段 | 联系 |
|---|---|
| M1 | three3d/index.html 直接引入 web/script.js 复用 computeStatus / ADVICE / validateInputs（规则零重写，SPEC §6 同一实现）；四状态色值与 M1 / Dashboard 卡片色一致 |
| M2 | 无直接接口；离线链（CSV → trend.png / report.html）不受影响 |
| M3 | README 运行方式更新；GitHub 同步沿用 M3 建立的 nova remote + subtree push 机制 |
| M4 | 无直接接口（小程序预留点不变） |
| M5 | 订阅同一 MQTT 数据流（dormmate/+/env、ws://localhost:8083）；mqtt.min.js 拷贝复用；校验链与 dashboard/app.js 98-181 行同序同款；simulator 零改动 |
| M6 | three3d/ 本体（SPEC §7 新目录） |
| A1 | selectedNodeId + 点击选中高亮 + 详情侧栏 = "3D 明确知道当前查看的是谁"的基础；每节点 60 条历史（按 time 分组）供 A1 程序计算连续异常时长；优先规则本身 A 阶段做。⚠ 遗留（评审记录）：S3 演示按钮数据也会写入 history，A1 计算连续异常时长前需排除演示记录或清空重采 |
| A2 | action 字段 M6 恒 ""；fanGroup 风扇 mesh 预留挂点（A2 写 fan_on 后风扇转动，操作后 Dashboard/3D 状态一致）；M6 不做 actionState、不因点击直接改状态 |
| A3 | 无（依赖 A2；恢复必须由新数据触发） |
| B | M6 证据（截图/录屏/丢弃日志）为 B 组程序化说明素材 |
| C | 无直接接口（C 复用离线链 CSV + report.html） |
| Final | 实时链 = 模拟节点 → MQTT → Dashboard → **3D**，M6 是终点；冷启动复验含 3D（SPEC §2） |

## 10. 风险

- **vendor 下载失败/被墙**（高×中）→ 三备源链 + 用户手动下载兜底；mqtt.min.js 本地拷贝免下载
- **误下新版 three.js**（中×高）→ URL 钉死 `@0.128.0`；S1 校验文件头版本横幅
- **OrbitControls 拖拽误触发选中**（高×低）→ pointer 位移阈值 <5px
- **CanvasTexture 不刷新/发糊**（中×中）→ needsUpdate=true + LinearFilter + 512×256 canvas
- **WebGL 不可用**（低×高）→ S2 首步预检 + 降级横幅不白屏
- **校验链与 dashboard 顺序漂移**（中×中）→ S4 逐行对照 dashboard/app.js 98-181 行；复跑 M5 同款坏消息矩阵
- **Live Server 工作区根不对 → script.js 404**（中×低）→ rulesMissing 防御横幅（dashboard 同款）
- **演示时四状态凑不齐**（中×低）→ MQTTX 手发 + 本地演示按钮双保险
- **中文标牌乱码**（低×中）→ 文件 UTF-8 保存 + meta charset（VS Code 默认即 UTF-8）
- **粒子/动画卡顿**（低×低）→ ≤900 点、原地改 BufferAttribute、不重建几何/material
