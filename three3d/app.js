// DormMate M6 3D 场景（three3d/app.js）——S4 MQTT 实时驱动 3D
// 数据链：模拟节点 -> MQTT Broker（ws://localhost:8083，WebSocket）-> mqtt.js 订阅 -> handleMessage 校验 -> updateScene 驱动 3D
// 规则复用：window.computeStatus / ADVICE / validateInputs 来自 ../web/script.js（M1 同一实现，零重写）
// 任务书关键词落地点：scene / camera / renderer（initScene）、mesh / material（buildDorm）、
//   updateScene（本文件唯一更新入口）、JSON.parse（handleMessage）
// 串线防线（SPEC §12）：topic dormmate/{nodeId}/env 的 nodeId 必须与消息 nodeId 一致，不一致丢弃并警告
// 校验链（与 dashboard/app.js 同序同款）：JSON.parse 容错 -> 对象守卫 -> 六字段 -> time 格式 ->
//   validateInputs §3.1 范围 -> 串线防线 -> 未知节点 -> status 本地重算（不信任消息值）
// A1 预留：selectedNodeId = "3D 明确知道当前查看的是谁"；nodes[nodeId].history（上限 60 条，按 time 分组）供 A1 程序计算连续异常时长
// A2 预留：每楼屋顶 fanGroup 风扇 mesh（M6 静止；A2 写 fan_on 后让 fanBlades 绕 y 轴转动）
// WebGL 预检：不可用时显示降级横幅，页面其余部分不白屏

const NODE_IDS = ["dorm-a", "dorm-b", "dorm-c"];
const HISTORY_LIMIT = 60;   // 每节点历史上限（A1 复用），超出 shift 裁剪最旧

// 四状态视觉映射表（任务书 ≥3 类状态可见变化，本实现 4 类：建筑主色/指示球/粒子/标牌）
// 色值与 dashboard 卡片色一致（--green/--blue/--orange/--teal）；sphereY 是纯视觉区分（装饰性），与 A1 优先级规则无关
const STATUS_STYLE = {
  "正常": { body: 0x27ae60, light: 0x2ecc71, sphereY: 2.2, particles: "calm", particleColor: 0xd5f5e3 },
  "偏冷": { body: 0x4a90d9, light: 0x5dade2, sphereY: 3.7, particles: "snow", particleColor: 0xffffff },
  "偏热": { body: 0xe67e22, light: 0xf39c12, sphereY: 4.4, particles: "heat", particleColor: 0xe67e22 },
  "偏湿": { body: 0x16a085, light: 0x1abc9c, sphereY: 3.0, particles: "rain", particleColor: 0x5dade2 }
};

let scene, camera, renderer, controls;   // 任务书关键词：scene / camera / renderer
let selectedNodeId = null;               // A1 预留：当前查看的是谁
const dormVisuals = {};                  // { nodeId: { group, status, sphereTargetY, bodyMat, sphere, sphereMat, pointLight, sign, signCtx, signTexture, particles, fanBlades, ring } }
const nodes = {};                        // { nodeId: { latest, history[] } }，history 上限 HISTORY_LIMIT（统一 JSON 六字段）
NODE_IDS.forEach(function (id) { nodes[id] = { latest: null, history: [] }; });
// vendor 缺失防御：three.min.js 加载失败时顶层不抛 ReferenceError（降级横幅由启动调用处兜底）
const raycaster = (typeof THREE !== "undefined") ? new THREE.Raycaster() : null;
const clock = (typeof THREE !== "undefined") ? new THREE.Clock() : null;

// MQTT 连接与校验常量（与 dashboard/app.js 同款）
const WS_URL = "ws://localhost:8083";   // WebSocket 端口（mosquitto.conf listener 8083 + protocol websockets）
const TOPIC = "dormmate/+/env";         // 三节点订阅（SPEC §8：dormmate/{nodeId}/env）
const REQUIRED_FIELDS = ["nodeId", "temperature", "humidity", "status", "time", "action"];
const TIME_PATTERN = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/;   // SPEC §4 time 全格式
const utf8Decoder = new TextDecoder();   // 单例复用：热路径不再每消息新建
let receivedCount = 0;
let droppedCount = 0;   // 坏 JSON + 类型/格式/范围非法 + 串线 的总丢弃数

// ---- 顶层覆盖 UI 元素 ----
const connStatusEl = document.getElementById("connStatus");
const msgCountEl = document.getElementById("msgCount");
const dropCountEl = document.getElementById("dropCount");
const warnBannerEl = document.getElementById("warnBanner");
const sideNodeIdEl = document.getElementById("sideNodeId");
const sideStatusEl = document.getElementById("sideStatus");
const sideMetricsEl = document.getElementById("sideMetrics");
const sideAdviceEl = document.getElementById("sideAdvice");
const sideTimeEl = document.getElementById("sideTime");
const sideHistoryEl = document.getElementById("sideHistory");

// 规则模块缺失防御（如 ../web/script.js 因 Live Server 工作区根目录不对而 404）：
const rulesMissing = typeof window.computeStatus !== "function" || !window.ADVICE || !window.validateInputs;
if (rulesMissing) {
  showWarn("规则模块（web/script.js）加载失败——请以项目根目录为工作区用 Live Server 打开本页");
}

function showWarn(text) {
  warnBannerEl.textContent = text;
  warnBannerEl.hidden = text === "";
}
warnBannerEl.addEventListener("click", function () { showWarn(""); });

// ---- 本地演示按钮（SPEC §6 四组回归数据；作用于当前选中楼；Broker 未启动时的降级演示）----
document.querySelectorAll("#demoButtons button").forEach(function (btn) {
  btn.addEventListener("click", function () {
    if (!selectedNodeId) {
      showWarn("请先点击一栋楼，再点演示按钮");
      return;
    }
    applyDemoRecord(selectedNodeId, Number(btn.dataset.temp), Number(btn.dataset.hum));
  });
});

function applyDemoRecord(nodeId, temperature, humidity) {
  if (rulesMissing) {   // 与 MQTT 路径同款防御：规则模块缺失时提示而非抛 TypeError（评审修复）
    showWarn("规则模块（web/script.js）加载失败，演示按钮不可用——请以项目根目录为工作区用 Live Server 打开本页");
    return;
  }
  // 构造 SPEC §4 统一 JSON 六字段（action M6 恒 ""，A2 起写入动作值）→ 唯一入口 updateScene
  updateScene(nodeId, { nodeId: nodeId, temperature: temperature, humidity: humidity, status: "", time: formatNow(), action: "" });
}

function formatNow() {
  // 复用 M1 的 window.formatTime；缺失时本地兜底（YYYY-MM-DD HH:MM:SS，SPEC §4 全格式）
  if (typeof window.formatTime === "function") { return window.formatTime(new Date()); }
  function pad2(n) { return String(n).padStart(2, "0"); }
  const d = new Date();
  return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + " " +
    pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
}

// ---- Three 核心（任务书关键词：scene / camera / renderer）----
function initScene() {
  // WebGL 可用性预检：备用机/远程桌面可能无 WebGL，提前降级不白屏
  const probe = document.createElement("canvas");
  const gl = probe.getContext("webgl") || probe.getContext("experimental-webgl");
  if (!gl) {
    showWarn("当前浏览器/环境不支持 WebGL，3D 场景无法渲染——请使用 Chrome / Edge 并开启硬件加速");
    return false;
  }

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xdfe8f2);

  camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 200);
  camera.position.set(0, 14, 22);
  camera.lookAt(0, 3, 0);

  try {
    renderer = new THREE.WebGLRenderer({ antialias: true });
  } catch (err) {
    showWarn("WebGL 渲染器创建失败：" + err.message);
    return false;
  }
  renderer.outputEncoding = THREE.sRGBEncoding;   // r128 写法（r152+ 才改名 outputColorSpace）
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.getElementById("canvasContainer").appendChild(renderer.domElement);

  if (typeof THREE.OrbitControls !== "function") {
    showWarn("OrbitControls.js 加载失败——场景无法旋转（检查 three3d/vendor/OrbitControls.js）");   // 评审修复：vendor 缺失不抛异常
  } else {
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 3, 0);
    controls.enableDamping = true;                  // 惯性旋转更顺滑
    controls.maxPolarAngle = Math.PI / 2.1;         // 不钻到地面以下
  }

  // 灯光：环境光打底 + 方向光塑形
  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const sun = new THREE.DirectionalLight(0xffffff, 0.8);
  sun.position.set(10, 20, 10);
  scene.add(sun);

  // 地面 + 网格（帮助观察旋转/缩放）
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(60, 60),
    new THREE.MeshLambertMaterial({ color: 0x9ccc8e })
  );
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);
  scene.add(new THREE.GridHelper(60, 20, 0x8bb37d, 0xc8dcc0));

  // 三栋宿舍楼：x = -8 / 0 / 8（SPEC §12 三节点互不串线：每节点独立 group + nodeId 标记）
  NODE_IDS.forEach(function (id, i) { buildDorm(id, (i - 1) * 8); });

  window.addEventListener("resize", onResize);
  bindPointerSelect();
  return true;
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function tagDorm(mesh, nodeId) { mesh.userData.dormId = nodeId; }   // raycast 反查所属宿舍

function buildDorm(nodeId, x) {
  const group = new THREE.Group();
  group.position.set(x, 0, 0);
  scene.add(group);

  // 建筑主体（状态主色挂在 bodyMat 上，随 status 变化）——任务书关键词：mesh + material
  const bodyMat = new THREE.MeshLambertMaterial({ color: STATUS_STYLE["正常"].body });
  const body = new THREE.Mesh(new THREE.BoxGeometry(3, 4, 3), bodyMat);
  body.position.y = 2;
  tagDorm(body, nodeId);
  group.add(body);

  // 屋顶（四棱锥）
  const roof = new THREE.Mesh(new THREE.ConeGeometry(2.3, 1.5, 4), new THREE.MeshLambertMaterial({ color: 0x8d6e63 }));
  roof.position.y = 4.75;
  roof.rotation.y = Math.PI / 4;
  tagDorm(roof, nodeId);
  group.add(roof);

  // 门 + 两扇窗（贴 +z 面，朝向相机初始视角）
  const door = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1.6, 0.1), new THREE.MeshLambertMaterial({ color: 0x5d4037 }));
  door.position.set(0, 0.8, 1.51);
  tagDorm(door, nodeId);
  group.add(door);
  [-0.9, 0.9].forEach(function (wx) {
    const win = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.1), new THREE.MeshBasicMaterial({ color: 0xaee1f9 }));
    win.position.set(wx, 2.2, 1.51);
    tagDorm(win, nodeId);
    group.add(win);
  });

  // 楼前标牌（CanvasTexture 中文：canvas 2D 系统字体，无网络依赖）
  const sign = createSign(nodeId);
  const signMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(2.2, 1.1),
    new THREE.MeshBasicMaterial({ map: sign.texture, side: THREE.DoubleSide })
  );
  signMesh.position.set(0, 2.4, 1.56);
  tagDorm(signMesh, nodeId);
  group.add(signMesh);

  // 状态指示球（颜色+高度随状态，见 setDormStatus / animate lerp）+ 同位置点光源（发光感）
  const sphereMat = new THREE.MeshBasicMaterial({ color: STATUS_STYLE["正常"].light });
  const sphere = new THREE.Mesh(new THREE.SphereGeometry(0.35, 24, 24), sphereMat);
  sphere.position.set(0, STATUS_STYLE["正常"].sphereY, 2.2);
  tagDorm(sphere, nodeId);
  group.add(sphere);
  const pointLight = new THREE.PointLight(STATUS_STYLE["正常"].light, 0.8, 8);
  pointLight.position.copy(sphere.position);
  group.add(pointLight);

  // 楼顶粒子（THREE.Points，每楼 250 点；按状态切换 雪/雨/热气/平静）
  const particles = buildParticles();
  tagDorm(particles.points, nodeId);   // 粒子同打标，防"点中楼顶粒子却取消选中"
  group.add(particles.points);

  // 屋顶风扇（A2 预留挂点：A2 写 fan_on 后让 fanBlades 绕 y 轴转动；M6 静止）
  const fanGroup = new THREE.Group();
  fanGroup.position.set(0, 5.6, 0);
  tagDorm(fanGroup, nodeId);
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.3, 12), new THREE.MeshLambertMaterial({ color: 0x666666 }));
  hub.rotation.x = Math.PI / 2;
  tagDorm(hub, nodeId);   // 全部 mesh 都打标：r128 raycaster 不跳过任何对象，未打标会导致点击落到该 mesh 时误判为"点空白→取消选中"
  fanGroup.add(hub);
  const fanBlades = new THREE.Group();
  for (let i = 0; i < 3; i++) {
    const holder = new THREE.Group();
    holder.rotation.y = (i * Math.PI * 2) / 3;
    const blade = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.06, 0.18), new THREE.MeshLambertMaterial({ color: 0x999999 }));
    blade.position.x = 0.7;
    tagDorm(blade, nodeId);
    holder.add(blade);
    fanBlades.add(holder);
  }
  fanGroup.add(fanBlades);
  group.add(fanGroup);

  // 选中环（RingGeometry 贴地，默认隐藏；点击选中时显示）
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(1.8, 2.1, 32),
    new THREE.MeshBasicMaterial({ color: 0xf1c40f, side: THREE.DoubleSide })
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.03;
  ring.visible = false;
  tagDorm(ring, nodeId);   // 选中环同打标：点击可见的选中环=点自己宿舍，不误取消选中
  group.add(ring);

  dormVisuals[nodeId] = {
    group: group,
    status: "正常",
    sphereTargetY: STATUS_STYLE["正常"].sphereY,
    bodyMat: bodyMat,
    sphere: sphere,
    sphereMat: sphereMat,
    pointLight: pointLight,
    sign: signMesh,
    signCtx: sign.ctx,
    signTexture: sign.texture,
    particles: particles,
    fanBlades: fanBlades,
    ring: ring
  };
}

function createSign(nodeId) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  const texture = new THREE.CanvasTexture(canvas);
  texture.encoding = THREE.sRGBEncoding;    // 与 renderer.outputEncoding 一致，避免 canvas sRGB 颜色被双重伽马发白（r128 纹理默认 LinearEncoding）
  texture.minFilter = THREE.LinearFilter;   // 防小字发糊（默认 mipmap 会让文字变糊）
  texture.generateMipmaps = false;
  drawSign(nodeId, null, ctx, texture);
  return { canvas: canvas, ctx: ctx, texture: texture };
}

function drawSign(nodeId, record, ctx, texture) {
  // 标牌四行：nodeId·状态 / 温湿度 / 建议（window.ADVICE 查表）/ 时间
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, 512, 256);
  ctx.fillStyle = "#2c3e50";
  ctx.font = 'bold 42px "Microsoft YaHei", sans-serif';
  ctx.textAlign = "center";
  if (record) {
    ctx.fillText(nodeId + " · " + record.status, 256, 68);
    ctx.font = '34px "Microsoft YaHei", sans-serif';
    ctx.fillText(record.temperature + "℃ / " + record.humidity + "%", 256, 120);
    ctx.fillStyle = "#e67e22";
    ctx.fillText(window.ADVICE[record.status], 256, 168);
    ctx.fillStyle = "#777777";
    ctx.font = '26px "Microsoft YaHei", sans-serif';
    ctx.fillText(record.time, 256, 214);
  } else {
    ctx.fillText(nodeId, 256, 68);
    ctx.font = '36px "Microsoft YaHei", sans-serif';
    ctx.fillStyle = "#555555";
    ctx.fillText("等待数据…", 256, 130);
  }
  texture.needsUpdate = true;   // CanvasTexture 更新后必须标记，否则画面不刷新（易漏点）
}

function buildParticles() {
  // 每楼 250 点：楼顶 y 5~9 区域；positions 原地改值，绝不重建几何（性能）
  const count = 250;
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 3;       // x：楼宽范围
    positions[i * 3 + 1] = 5 + Math.random() * 4;       // y：楼顶 5~9
    positions[i * 3 + 2] = (Math.random() - 0.5) * 3;   // z
  }
  const geometry = new THREE.BufferGeometry();          // r125 起 Geometry 已删除，必须 BufferGeometry
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({ size: 0.15, color: STATUS_STYLE["正常"].particleColor, transparent: true, opacity: 0.9 });
  return { points: new THREE.Points(geometry, material), positions: positions, material: material, mode: "calm" };
}

// ---- 状态映射：四状态 -> 建筑主色/指示球/粒子/标牌（唯一更新入口，任务书关键词：updateScene）----
function setDormStatus(nodeId, status) {
  const v = dormVisuals[nodeId];
  const style = STATUS_STYLE[status];
  if (!v || !style) { return; }
  v.status = status;
  v.bodyMat.color.setHex(style.body);                // material.color.set，不重建 material/mesh
  v.sphereMat.color.setHex(style.light);
  v.pointLight.color.setHex(style.light);
  v.sphereTargetY = style.sphereY;                   // animate 里 lerp 平滑过渡
  v.particles.mode = style.particles;
  v.particles.material.color.setHex(style.particleColor);
}

let sceneUnavailableWarned = false;   // 场景未初始化（无 WebGL）时只提示+计数一次，防每条消息刷屏（评审修复）

function updateScene(nodeId, record) {
  const v = dormVisuals[nodeId];
  if (!v) {
    if (!sceneUnavailableWarned) {   // initScene 失败（如 WebGL 不可用）时消息无处可去，按"必有横幅+计数"口径处理一次
      sceneUnavailableWarned = true;
      drop("场景未初始化（WebGL 不可用），实时消息无法驱动 3D");
    }
    return;
  }
  // status 由本地同一规则重算，不信任传入值（SPEC §4 禁止手填/直接带入）
  const status = window.computeStatus(record.temperature, record.humidity);
  const rec = {
    nodeId: nodeId,
    temperature: record.temperature,
    humidity: record.humidity,
    status: status,
    time: record.time,
    action: ""   // M6 恒 ""（SPEC §4 预留字段；A2 起改为按节点写入动作值，评审修复：不透传消息里的任意值）
  };
  const node = nodes[nodeId];
  node.latest = rec;
  node.history.push(rec);
  if (node.history.length > HISTORY_LIMIT) { node.history.shift(); }   // 裁剪最旧，防内存增长（A1 复用口径）
  setDormStatus(nodeId, status);
  // 标牌内容未变时跳过重绘（CanvasTexture 更新会整张重传 GPU，热路径省一次是一次，评审修复）
  const signKey = status + "|" + record.temperature + "|" + record.humidity + "|" + record.time;
  if (v.lastSignKey !== signKey) {
    v.lastSignKey = signKey;
    drawSign(nodeId, rec, v.signCtx, v.signTexture);
  }
  if (selectedNodeId === nodeId) { renderSidebar(); }
}

// ---- 动画循环：只做粒子/球动画与渲染，不做数据（数据统一走 updateScene）----
function animate() {
  requestAnimationFrame(animate);
  if (document.hidden) { return; }   // 标签页隐藏时不渲染，省 GPU（dt 有 0.1 上限，恢复无跳变，评审修复）
  const dt = Math.min(clock.getDelta(), 0.1);
  NODE_IDS.forEach(function (id) { updateDormAnimation(id, dt); });
  if (controls) { controls.update(); }   // OrbitControls 缺失（vendor 加载失败）时跳过，页面仍可渲染
  renderer.render(scene, camera);
}

function updateDormAnimation(nodeId, dt) {
  const v = dormVisuals[nodeId];
  const p = v.particles;
  const yMin = 5;
  const yMax = 9;
  // 粒子按状态模式运动：偏冷飘雪/偏湿下雨（下落）、偏热热气（上升）、正常平静（缓浮）
  let dir, speed;
  if (p.mode === "snow") { dir = -1; speed = 0.6; }
  else if (p.mode === "rain") { dir = -1; speed = 2.4; }
  else if (p.mode === "heat") { dir = 1; speed = 1.4; }
  else { dir = 1; speed = 0.25; }   // calm
  for (let i = 0; i < p.positions.length; i += 3) {
    let y = p.positions[i + 1] + dir * speed * dt;
    if (y > yMax) { y = yMin; }
    if (y < yMin) { y = yMax; }
    p.positions[i + 1] = y;
  }
  p.points.geometry.attributes.position.needsUpdate = true;   // 原地改值后标记，不重建几何
  if (p.mode === "snow") { p.points.rotation.y += 0.3 * dt; }  // 飘雪轻微横向漂移

  // 指示球：y 向目标高度 lerp 平滑过渡 + 轻微脉动（球高度纯视觉区分，与 A1 优先级规则无关）
  if (v.sphereTargetY !== undefined) {
    v.sphere.position.y += (v.sphereTargetY - v.sphere.position.y) * Math.min(1, dt * 4);
    v.pointLight.position.copy(v.sphere.position);
    v.sphere.scale.setScalar(1 + Math.sin(clock.elapsedTime * 4) * 0.08);
  }
}

// ---- 点击选中 vs OrbitControls 拖拽（pointer 位移阈值 <5px，仅左键）----
let pointerDownPos = null;
let pointerDownButton = -1;

function bindPointerSelect() {
  const el = renderer.domElement;
  el.addEventListener("pointerdown", function (e) {
    if (e.pointerType === "touch" || e.pointerType === "pen") { e.preventDefault(); }   // 触摸手势不交给浏览器默认行为（防边缘滑动=返回，S6 修复）
    pointerDownPos = { x: e.clientX, y: e.clientY };
    pointerDownButton = e.button;
  });
  el.addEventListener("pointerup", function (e) {
    if (!pointerDownPos) { return; }
    const dx = e.clientX - pointerDownPos.x;
    const dy = e.clientY - pointerDownPos.y;
    const button = pointerDownButton;
    pointerDownPos = null;
    pointerDownButton = -1;
    // 仅左键且位移 <5px 才是点击；右键平移/中键缩放（OrbitControls 绑定）不触发选中（评审修复）
    if (button === 0 && dx * dx + dy * dy < 25) { handleClick(e); }
  });
  el.addEventListener("pointercancel", function () {
    pointerDownPos = null;   // 触摸手势被系统打断：清状态，防下一次点击被误判（评审修复）
    pointerDownButton = -1;
  });
}

function handleClick(e) {
  const rect = renderer.domElement.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((e.clientX - rect.left) / rect.width) * 2 - 1,
    -((e.clientY - rect.top) / rect.height) * 2 + 1
  );
  raycaster.setFromCamera(ndc, camera);
  const hits = raycaster.intersectObjects(scene.children, true);
  for (let i = 0; i < hits.length; i++) {
    const dormId = hits[i].object.userData && hits[i].object.userData.dormId;
    if (dormId) { selectDorm(dormId); return; }
  }
  if (selectedNodeId) { selectDorm(null); }   // 点中地面/空白 → 取消选中
}

function selectDorm(nodeId) {
  NODE_IDS.forEach(function (id) {
    const v = dormVisuals[id];
    v.ring.visible = id === nodeId;
    v.bodyMat.emissive.setHex(id === nodeId ? 0x222222 : 0x000000);   // 选中楼整体提亮
  });
  selectedNodeId = nodeId;
  renderSidebar();
}

function renderSidebar() {
  if (!selectedNodeId) {
    sideNodeIdEl.textContent = "未选中";
    sideStatusEl.textContent = "—";
    sideStatusEl.className = "side-status";
    sideMetricsEl.textContent = "点击一栋楼查看详情";
    sideAdviceEl.textContent = "";
    sideTimeEl.textContent = "";
    sideHistoryEl.innerHTML = "";
    return;
  }
  const node = nodes[selectedNodeId];
  const r = node && node.latest;
  sideNodeIdEl.textContent = selectedNodeId;
  if (r) {
    sideStatusEl.textContent = r.status;
    sideStatusEl.className = "side-status " + r.status;   // 颜色类随状态切换（与 dashboard 卡片同款）
    sideMetricsEl.textContent = r.temperature + "℃ / " + r.humidity + "%";
    sideAdviceEl.textContent = window.ADVICE[r.status];   // 建议查表渲染（与 web/script.js 同一来源）
    sideTimeEl.textContent = r.time;
    sideHistoryEl.innerHTML = "";
    node.history.slice(-5).reverse().forEach(function (h) {
      const li = document.createElement("li");
      li.textContent = h.time.slice(11) + " " + h.status + " " + h.temperature + "℃/" + h.humidity + "%";
      sideHistoryEl.appendChild(li);
    });
  } else {
    sideStatusEl.textContent = "—";
    sideStatusEl.className = "side-status";
    sideMetricsEl.textContent = "等待数据…（点下方演示按钮，或等 S4 MQTT 数据）";
    sideAdviceEl.textContent = "";
    sideTimeEl.textContent = "";
    sideHistoryEl.innerHTML = "";
  }
}

// ---- MQTT 实时驱动（校验链与 dashboard/app.js 同序同款：容错 -> 守卫 -> 字段 -> 范围 -> 串线 -> 重算）----
function setConnState(online, text) {
  connStatusEl.textContent = text;
  connStatusEl.className = "conn " + (online ? "online" : "offline");
}

function drop(reason) {
  droppedCount++;
  dropCountEl.hidden = false;
  dropCountEl.textContent = "丢弃 " + droppedCount + " 条";
  const stamp = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  showWarn("[" + stamp + "] " + reason);   // 带时间戳，可区分新旧证据
  console.warn("[DormMate 3D] " + reason);
}

function handleMessage(topic, text) {
  receivedCount++;
  msgCountEl.textContent = "收到 " + receivedCount + " 条";

  // 兜底 try：以下所有校验与处理之外，任何未预期异常也统一走 drop，
  // 保证"任何问题必有横幅 + 丢弃计数"，不白屏不静默（内部各 drop 分支正常 return）
  try {
    if (rulesMissing) {
      drop("规则模块（web/script.js）加载失败，无法处理消息");
      return;
    }
    let message;
    try {
      message = JSON.parse(text);   // 任务书关键词：JSON.parse
    } catch (err) {
      drop("消息不是合法 JSON：" + text.slice(0, 80));
      return;
    }
    // 对象类型守卫：null / 数字 / 字符串等合法 JSON 一律走 drop，不抛 TypeError
    if (typeof message !== "object" || message === null || Array.isArray(message)) {
      drop("消息不是 JSON 对象：" + text.slice(0, 80));
      return;
    }
    for (let i = 0; i < REQUIRED_FIELDS.length; i++) {
      if (!(REQUIRED_FIELDS[i] in message)) {
        drop("消息缺少字段 " + REQUIRED_FIELDS[i] + "：" + text.slice(0, 80));
        return;
      }
    }
    if (typeof message.nodeId !== "string") {
      drop("nodeId 字段不是字符串：" + text.slice(0, 80));
      return;
    }
    // time 类型 + 格式校验：非字符串或格式不符会令标牌/侧栏时间乱码
    if (typeof message.time !== "string" || !TIME_PATTERN.test(message.time)) {
      drop("time 字段非法（SPEC §4 要求 YYYY-MM-DD HH:MM:SS）：" + text.slice(0, 80));
      return;
    }
    // SPEC §3.1 范围校验：复用 M1 的 window.validateInputs——
    // 覆盖范围（温度 −50~50、湿度 0~100）、非数字、NaN / Infinity，与全项目口径统一
    const validation = window.validateInputs(message.temperature, message.humidity);
    if (validation.messages.length > 0) {
      drop("数据非法（" + validation.messages.join("；") + "）：" + text.slice(0, 80));
      return;
    }
    // 串线防线（SPEC §12）：topic 里的 nodeId 必须等于消息 JSON 里的 nodeId
    const topicNodeId = topic.split("/")[1];
    if (message.nodeId !== topicNodeId) {
      drop("串线拦截：topic=" + topic + " 但消息 nodeId=" + message.nodeId + "，已丢弃");
      return;
    }
    if (NODE_IDS.indexOf(message.nodeId) < 0) {
      drop("未知节点 " + message.nodeId);
      return;
    }
    // status 不信任消息值，updateScene 内用本地同一规则重算（SPEC §4 禁止手填/直接带入）
    updateScene(message.nodeId, {
      nodeId: message.nodeId,
      temperature: validation.temperature,
      humidity: validation.humidity,
      time: message.time,
      action: message.action
    });
    // 注意：成功路径不清空警告横幅——丢弃原因持续显示（点击横幅可关闭），
    // 避免"警告被下一条正常消息冲掉"导致验收时看不到拦截提示
  } catch (err) {
    drop("处理异常：" + err.message + "（" + text.slice(0, 60) + "）");
  }
}

// ---- MQTT 连接（mqtt.js，WebSocket；reconnectPeriod 断线自动重连，重连后自动重新订阅）----
if (typeof mqtt === "undefined") {
  setConnState(false, "MQTT 客户端（mqtt.min.js）加载失败——检查 three3d/vendor/mqtt.min.js");   // 评审修复：vendor 缺失不抛异常
} else {
const client = mqtt.connect(WS_URL, { reconnectPeriod: 2000 });

client.on("connect", function () {
  if (rulesMissing) {
    setConnState(false, "规则模块（web/script.js）加载失败——请以项目根目录为工作区打开本页");
    client.subscribe(TOPIC, function (err) {
      if (err) { showWarn("订阅失败：" + err.message); }
    });
    return;
  }
  setConnState(true, "已连接 " + WS_URL);
  client.subscribe(TOPIC, function (err) {
    if (err) { showWarn("订阅失败：" + err.message); }
  });
});
client.on("reconnect", function () { setConnState(false, "已断开，重连中…"); });
client.on("close", function () { setConnState(false, "已断开，重连中…"); });
client.on("error", function (err) { setConnState(false, "连接错误：" + err.message); });
client.on("message", function (topic, payload) {
  // mqtt.js v5 浏览器端 payload 恒为 Uint8Array，单例 TextDecoder 解码
  handleMessage(topic, utf8Decoder.decode(payload));
});
}   // typeof mqtt 守卫结束

// ---- 启动 ----
try {
  if (initScene()) { animate(); }
} catch (err) {
  // vendor（three.min.js）缺失/损坏等加载期异常：降级横幅，不白屏（评审修复）
  showWarn("Three.js（three.min.js）加载失败：" + err.message);
}
