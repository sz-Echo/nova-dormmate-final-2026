// DormMate M5 Dashboard（dashboard/app.js）
// 数据链：模拟节点 -> MQTT Broker（ws://localhost:8083，WebSocket）-> mqtt.js 订阅 -> 三卡片 + Chart.js 趋势
// 规则复用：window.computeStatus / ADVICE / validateInputs 来自 ../web/script.js（M1 同一实现，零重写）；
// 本页以本地同一规则重算 status 展示，不信任消息里的 status（防手填/错误值）。
// 串线防线（SPEC §12）：topic dormmate/{nodeId}/env 的 nodeId 必须与消息 JSON 的 nodeId 一致，不一致丢弃并警告。
// 容错（评审加固）：JSON.parse try...catch + 解析结果对象类型守卫 + 六字段校验（time 含格式校验）+
// SPEC §3.1 范围校验（复用 window.validateInputs）；坏消息统一走 drop()：页面警告 + 计数，不抛异常、不白屏。
// 断线重连：mqtt.js reconnectPeriod 2000ms——冷启动演示（关闭 Broker 再重启）时浏览器自动恢复连接。
// 内存：每节点历史上限 60 条，超出 shift 裁剪最旧；图表数据增量追加、同策略同步裁剪。
// 记录结构：保持 SPEC §4 统一 JSON 六字段（含 action，A2 起写入动作值）；advice 渲染时查表，不入记录。

const WS_URL = "ws://localhost:8083";   // WebSocket 端口（mosquitto.conf listener 8083 + protocol websockets）
const TOPIC = "dormmate/+/env";         // 三节点订阅（SPEC §8：dormmate/{nodeId}/env）
const ACTION_TOPIC = "dormmate/+/action"; // A2 联动#1：动作通道订阅（自己发布后的回环去重；外部来源=移动端）
// A3 事件状态跨端广播：Dashboard 状态机是唯一持有者，在 OPEN/HANDLING/RECOVERED/CANCELLED
// 四个时机发布 dormmate/{nodeId}/event；优先节点变化时发布 dormmate/priority ——
// 3D 与移动端订阅展示，满足"三端对同一事件保持一致，不各自维护"（恢复仍仅由新数据触发）
const EVENT_STATES = ["OPEN", "HANDLING", "RECOVERED", "CANCELLED"];
const PRIORITY_TOPIC = "dormmate/priority";
const NODE_IDS = ["dorm-a", "dorm-b", "dorm-c"];
const HISTORY_LIMIT = 60;
const REQUIRED_FIELDS = ["nodeId", "temperature", "humidity", "status", "time", "action"];
const TIME_PATTERN = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/;   // SPEC §4 time 全格式
const utf8Decoder = new TextDecoder();   // 单例复用：热路径不再每消息新建（评审修复）

// 每节点状态：latest = 最新记录；history = 时间序列（统一 JSON 六字段，上限 HISTORY_LIMIT 条）；
// actionState = A2 用户动作（{nodeId, action, actionTime}，SPEC §9 A2 / MASTER_PLAN §6.1），
// 只记录"用户做了什么"，不直接改 status（恢复由 A3 新数据触发）；
// recovery = A3 恢复状态机（SPEC §9 A3 / MASTER_PLAN §6.3）：
//   null | {state:"processing", actionTime, normalStreak} | {state:"recovered", recoverTime}
const nodes = {};
NODE_IDS.forEach(function (id) {
  nodes[id] = { latest: null, history: [], actionState: null, recovery: null, event: null };
});

// A4 事件列表（已定稿的完整事件，可导出 events.json；事件、动作和结果均由程序真实产生）
const events = [];

let selectedNode = "dorm-a";
let receivedCount = 0;
let droppedCount = 0;   // 坏 JSON + 类型/格式/范围非法 + 串线 的总丢弃数
let lastPriorityPublished = null;   // A3：优先节点仅变化时广播，避免每条消息刷屏

const cardsEl = document.getElementById("cards");
const tabsEl = document.getElementById("tabs");
const connStatusEl = document.getElementById("connStatus");
const msgCountEl = document.getElementById("msgCount");
const dropCountEl = document.getElementById("dropCount");
const warnBannerEl = document.getElementById("warnBanner");
const overviewBarEl = document.getElementById("overviewBar");
const speakOverviewBtn = document.getElementById("speakOverviewBtn");
const priorityBannerEl = document.getElementById("priorityBanner");
const evidenceCardsEl = document.getElementById("evidenceCards");
const chartCanvas = document.getElementById("trendChart");
const actionNodeEl = document.getElementById("actionNode");
const fanOnBtn = document.getElementById("fanOnBtn");
const fanOffBtn = document.getElementById("fanOffBtn");
const actionStateTextEl = document.getElementById("actionStateText");
const eventListEl = document.getElementById("eventList");
const exportEventsBtn = document.getElementById("exportEventsBtn");
const dashVoiceCommandEl = document.getElementById("dashVoiceCommand");
const dashVoiceResultEl = document.getElementById("dashVoiceResult");
const dashCameraVideoEl = document.getElementById("dashCameraVideo");
const dashCameraStateEl = document.getElementById("dashCameraState");
const dashCameraStopBtnEl = document.getElementById("dashCameraStopBtn");

function setConnState(online, text) {
  connStatusEl.textContent = text;
  connStatusEl.className = "conn " + (online ? "online" : "offline");
}

// 规则模块缺失防御（如 ../web/script.js 因工作区根目录不对而 404）：
// 存标志供消息处理与连接事件共用，提示不被 connect 事件覆盖
const rulesMissing = typeof window.computeStatus !== "function" || !window.ADVICE || !window.validateInputs;
if (rulesMissing) {
  setConnState(false, "规则模块（web/script.js）加载失败——请以项目根目录为工作区用 Live Server 打开本页");
}

// ---- Chart.js：选中节点的温度 + 湿度双线（双 Y 轴）----
const chart = new Chart(chartCanvas, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { label: "温度（℃）", data: [], borderColor: "#e67e22", yAxisID: "y", tension: 0.3, pointRadius: 0 },
      { label: "湿度（%）", data: [], borderColor: "#16a085", yAxisID: "y1", tension: 0.3, pointRadius: 0 }
    ]
  },
  options: {
    responsive: true,
    animation: false,   // 实时高频更新关闭动画，避免曲线抖动
    scales: {
      y: { title: { display: true, text: "温度（℃）" }, min: 0, max: 50 },
      y1: {
        position: "right",
        title: { display: true, text: "湿度（%）" },
        min: 0, max: 100,
        grid: { drawOnChartArea: false }
      }
    }
  }
});

function rebuildChart() {
  // tab 切换 / 初始渲染：按 history 全量重建
  const history = nodes[selectedNode].history;
  chart.data.labels = history.map(function (r) { return r.time.slice(11); });  // HH:MM:SS
  chart.data.datasets[0].data = history.map(function (r) { return r.temperature; });
  chart.data.datasets[1].data = history.map(function (r) { return r.humidity; });
  chart.update();
}

function appendChartPoint(record) {
  // 消息到达：只追加一个点；超上限与 history 同策略裁剪（评审修复：不再全量重建）
  chart.data.labels.push(record.time.slice(11));
  chart.data.datasets[0].data.push(record.temperature);
  chart.data.datasets[1].data.push(record.humidity);
  if (chart.data.labels.length > HISTORY_LIMIT) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
    chart.data.datasets[1].data.shift();
  }
  chart.update();
}

// ---- 消息处理：JSON 容错 -> 对象守卫 -> 字段/类型/格式校验 -> 串线防线 -> 范围校验 -> 规则重算 ----
function handleMessage(topic, text) {
  receivedCount++;
  msgCountEl.textContent = "收到 " + receivedCount + " 条";

  // 兜底 try（评审硬化）：以下所有校验与处理之外，任何未预期异常也统一走 drop，
  // 保证"任何问题必有横幅 + 丢弃计数"，不白屏不静默（内部各 drop 分支正常 return）
  try {
  if (rulesMissing) {
    drop("规则模块（web/script.js）加载失败，无法处理消息");
    return;
  }
  let message;
  try {
    message = JSON.parse(text);
  } catch (err) {
    drop("消息不是合法 JSON：" + text.slice(0, 80));
    return;
  }
  // 对象类型守卫（评审修复）：null / 数字 / 字符串等合法 JSON 一律走 drop，不再抛 TypeError
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
  // time 类型 + 格式校验（评审修复）：非字符串或格式不符会令趋势图 X 轴标签乱码/图表冻结
  if (typeof message.time !== "string" || !TIME_PATTERN.test(message.time)) {
    drop("time 字段非法（SPEC §4 要求 YYYY-MM-DD HH:MM:SS）：" + text.slice(0, 80));
    return;
  }

  // SPEC §3.1 范围校验（评审修复）：复用 M1 的 window.validateInputs——
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

  // status 用本地同一规则重算；记录保持 SPEC §4 统一 JSON 六字段（action 保留，A2 起写入动作值）
  const node = nodes[message.nodeId];
  const status = window.computeStatus(validation.temperature, validation.humidity);
  const record = {
    nodeId: message.nodeId,
    temperature: validation.temperature,
    humidity: validation.humidity,
    status: status,
    time: message.time,
    action: node.actionState ? node.actionState.action : (message.action || "")   // A2：动作成为记录的一部分（SPEC §4）
  };

  node.latest = record;
  node.history.push(record);
  if (node.history.length > HISTORY_LIMIT) {
    node.history.shift();   // 裁剪最旧，防内存增长
  }

  // A3 恢复状态机（SPEC §9 A3 / MASTER_PLAN §6.3）：恢复必须由新数据触发，
  // 连续 ≥2 条 status==正常 才判"已恢复"；仍异常则清零计数、保持处理中（继续提示）；
  // 已恢复后再次出现异常 → 打破"已恢复"，回到仍需关注（截图 A3：后续数据仍异常就继续提示）
  if (node.recovery) {
    if (node.recovery.state === "processing") {
      if (record.status === "正常") {
        node.recovery.normalStreak += 1;
        if (node.recovery.normalStreak >= 2) {
          node.recovery = { state: "recovered", recoverTime: record.time };
          publishFanOffAuto(message.nodeId, record.time);   // 自动关扇：simulator 恢复随机游走、3D 风扇停止
          const finalized = finalizeEvent(message.nodeId, record.time);   // A4：事件定稿进"今日事件"面板
          publishEventState(message.nodeId, "RECOVERED", record.time,
            finalized ? finalized.summary : "已恢复", finalized ? finalized.eventId : null);
        }
      } else {
        node.recovery.normalStreak = 0;
      }
    } else if (record.status !== "正常") {
      node.recovery = null;
    }
  }

  // A4 事件草稿：异常出现时开草稿（开始时间/问题）；动作与优先原因由 A1/A2 路径回填
  if (record.status !== "正常" && !node.event) {
    node.event = {
      eventId: makeEventId(message.nodeId, record.time),
      nodeId: message.nodeId,
      startTime: record.time,
      problem: record.status,
      priorityReason: null,
      action: null,
      actionTime: null,
      recoverTime: null,
      result: null,
      summary: null
    };
    publishEventState(message.nodeId, "OPEN", record.time, "发现异常：" + record.status, node.event.eventId);
  }

  updateCard(message.nodeId);
  if (message.nodeId === selectedNode) appendChartPoint(record);
  refreshOverview();
  refreshPriority();
  refreshEvidence();
  if (message.nodeId === selectedNode) refreshActionBar();   // A3：新数据推进恢复状态机后同步动作条
  // 注意：成功路径不清空警告横幅——丢弃原因持续显示（点击横幅可关闭），
  // 避免"警告被下一条正常消息冲掉"导致验收时看不到拦截提示
  } catch (err) {
    drop("处理异常：" + err.message + "（" + text.slice(0, 60) + "）");
  }
}

function drop(reason) {
  droppedCount++;
  dropCountEl.hidden = false;
  dropCountEl.textContent = "丢弃 " + droppedCount + " 条";
  const stamp = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  showWarn("[" + stamp + "] " + reason);   // 带时间戳，可区分新旧证据
  console.warn("[DormMate] " + reason);
}

function showWarn(text) {
  warnBannerEl.textContent = text;
  warnBannerEl.hidden = text === "";
}

function formatNowLocal() {
  // 复用 M1 的 window.formatTime；缺失时本地兜底（YYYY-MM-DD HH:MM:SS，SPEC §4 全格式）
  if (typeof window.formatTime === "function") { return window.formatTime(new Date()); }
  function pad2(n) { return String(n).padStart(2, "0"); }
  const d = new Date();
  return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + " " +
    pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
}

// ---- A2 联动#1：外部（移动端）动作消息处理 ----
// 本页自己的 fan_on/fan_off 已在 publishAction / publishFanOffAuto 本地完成状态处理，
// 回环消息一律去重忽略；只有"外部来源（移动端）"的 fan_on 才进入状态机——
// 移动端开风扇 → Dashboard 显示"处理中"（恢复仍仅由后续新数据触发，本函数不判恢复）
function handleActionMessage(topic, text) {
  try {
    let message;
    try {
      message = JSON.parse(text);
    } catch (err) {
      drop("动作消息不是合法 JSON：" + text.slice(0, 80));
      return;
    }
    if (typeof message !== "object" || message === null || Array.isArray(message)) {
      drop("动作消息不是 JSON 对象：" + text.slice(0, 80));
      return;
    }
    const topicNodeId = topic.split("/")[1];
    if (message.nodeId !== topicNodeId) {
      drop("动作串线拦截：topic=" + topic + " 但消息 nodeId=" + message.nodeId);
      return;
    }
    if (NODE_IDS.indexOf(message.nodeId) < 0) {
      drop("动作消息未知节点 " + message.nodeId);
      return;
    }
    if (message.action !== "fan_on") {
      return; // fan_off 回环 / 未知动作：本页本地逻辑已处理，忽略
    }
    const node = nodes[message.nodeId];
    if (node.recovery && node.recovery.state === "processing") {
      return; // 已处理中：自己发布后的回环或重复动作，去重忽略
    }
    // 外部来源（移动端）触发的处理动作：与 publishAction 的 fan_on 本地分支同语义
    const actionTime = String(message.actionTime || formatNowLocal());
    node.actionState = { nodeId: message.nodeId, action: "fan_on", actionTime: actionTime };
    node.recovery = { state: "processing", actionTime: actionTime, normalStreak: 0 };
    if (node.event) {
      node.event.action = "fan_on";
      node.event.actionTime = actionTime;
    }
    const evId = (node.event && node.event.eventId) || makeEventId(message.nodeId, actionTime);
    publishEventState(message.nodeId, "HANDLING", actionTime, "已开启风扇，处理中（移动端触发）", evId);
    console.log("[联动] 收到移动端发来的 fan_on: " + message.nodeId + "（" + actionTime + "）");
    updateCard(message.nodeId);
    if (message.nodeId === selectedNode) refreshActionBar();
  } catch (err) {
    drop("动作处理异常：" + err.message + "（" + text.slice(0, 60) + "）");
  }
}

function makeEventId(nodeId, time) {
  return nodeId + "-" + String(time).replace(/[^0-9]/g, "");
}

function publishEventState(nodeId, state, time, summary, eventId) {
  // A3：事件状态经共享状态流广播（dormmate/{nodeId}/event），三端同源；
  // eventId 由草稿开始时间派生，同一事件各状态共用，便于三端对齐
  const payload = {
    nodeId: nodeId,
    eventId: eventId || makeEventId(nodeId, time),
    state: state,
    time: time,
    summary: summary || ""
  };
  client.publish("dormmate/" + nodeId + "/event", JSON.stringify(payload), { qos: 0 }, function (err) {
    if (err) showWarn("事件状态发布失败：" + err.message);
  });
}

function publishAction(action) {
  // A2：动作经 MQTT 动作通道发布（dormmate/{nodeId}/action），simulator 与 three3d 同订阅响应；
  // 本地 actionState 只在发布成功后写入——与 A3 解耦：不因点击直接把状态改为"已恢复"
  const nodeId = selectedNode;
  if (!client.connected) {
    showWarn("MQTT 未连接，动作未发布——请先启动 Broker 并刷新页面连接");
    return;
  }
  const actionState = { nodeId: nodeId, action: action, actionTime: formatNowLocal() };
  client.publish("dormmate/" + nodeId + "/action", JSON.stringify(actionState), { qos: 0 }, function (err) {
    if (err) {
      showWarn("动作发布失败：" + err.message);
      return;
    }
    nodes[nodeId].actionState = actionState;
    if (action === "fan_on") {
      // A3 状态机进入 processing：恢复只能由后续新数据触发（连续 ≥2 条正常），点击不算恢复
      nodes[nodeId].recovery = { state: "processing", actionTime: actionState.actionTime, normalStreak: 0 };
      // A4 草稿回填动作（若异常草稿已存在；正常节点点风扇不产生事件）
      if (nodes[nodeId].event) {
        nodes[nodeId].event.action = actionState.action;
        nodes[nodeId].event.actionTime = actionState.actionTime;
      }
      const evId = (nodes[nodeId].event && nodes[nodeId].event.eventId) || makeEventId(nodeId, actionState.actionTime);
      publishEventState(nodeId, "HANDLING", actionState.actionTime, "已开启风扇，处理中", evId);
    } else {
      // 手动关闭风扇不视为恢复，重置状态机（恢复必须由新数据触发）；放弃处理 → 丢弃草稿
      const evId = (nodes[nodeId].event && nodes[nodeId].event.eventId) || makeEventId(nodeId, actionState.actionTime);
      nodes[nodeId].recovery = null;
      nodes[nodeId].event = null;
      publishEventState(nodeId, "CANCELLED", actionState.actionTime, "已取消处理", evId);
    }
    updateCard(nodeId);
    refreshActionBar();
  });
}

function publishFanOffAuto(nodeId, recoverTime) {
  // A3 恢复后的自动关扇：发布 fan_off 让 simulator 停止降温、3D 风扇停止；
  // 不重置 recovery（保持"已恢复"展示）
  const actionState = { nodeId: nodeId, action: "fan_off", actionTime: recoverTime };
  client.publish("dormmate/" + nodeId + "/action", JSON.stringify(actionState), { qos: 0 }, function (err) {
    if (!err) { nodes[nodeId].actionState = actionState; }
  });
}

function finalizeEvent(nodeId, recoverTime) {
  // A4 定稿：填恢复时间/结果，程序拼接复盘叙事（截图 A4 例句口径），进入事件列表（可导出 events.json）
  const ev = nodes[nodeId].event;
  if (!ev) return;
  // 字段规整：未成为过优先对象就恢复的边界（如三节点同异常、用户直接处理非首位节点）→ 空字符串而非 null
  if (!ev.priorityReason) { ev.priorityReason = ""; }
  if (!ev.action) { ev.action = ""; }
  if (!ev.actionTime) { ev.actionTime = ""; }
  ev.recoverTime = recoverTime;
  ev.result = "已恢复";
  ev.summary =
    ev.startTime.slice(11) + " " + ev.nodeId + " 连续" + ev.problem +
    (ev.priorityReason ? " → 优先关注 " + ev.nodeId + "（" + ev.priorityReason + "）" : "") +
    (ev.actionTime ? " → " + ev.actionTime.slice(11) + " 开启风扇并通风" : "") +
    " → " + recoverTime.slice(11) + " 恢复正常";
  events.push(ev);
  nodes[nodeId].event = null;
  renderEvents();
  return ev;   // A3：返回定稿事件（含 eventId 与 summary），供 RECOVERED 广播使用
}

function renderEvents() {
  // A4 事件面板：只列已定稿的完整事件（草稿不展示，避免"未恢复"事件冒充完整闭环）
  if (events.length === 0) {
    eventListEl.innerHTML = '<li class="event-empty">暂无事件</li>';
    return;
  }
  eventListEl.innerHTML = "";
  events.forEach(function (ev) {
    const li = document.createElement("li");
    li.textContent = ev.summary || (ev.nodeId + " " + ev.startTime + " " + ev.problem);
    if (ev.snapshot) {
      const span = document.createElement("span");   // E2：事件关联快照引用（文件名含 eventId）
      span.className = "event-snap";
      span.textContent = " · 现场快照：" + ev.snapshot;
      li.appendChild(span);
    }
    eventListEl.appendChild(li);
  });
}

function exportEvents() {
  // A4 导出 events.json（UTF-8）：存入 data/ 后，python analysis/analyze.py 会生成 report.html"事件复盘"区
  if (events.length === 0) {
    showWarn("暂无完整事件可导出——请先完成一次 发现 → 判断 → 处理 → 恢复 流程");
    return;
  }
  const blob = new Blob([JSON.stringify(events, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "events.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
exportEventsBtn.addEventListener("click", exportEvents);

function refreshActionBar() {
  // 动作条随 tab 切换/动作发布/数据到达刷新（A2/A3 三态：仍需关注 / 处理中 / 已恢复）
  actionNodeEl.textContent = selectedNode;
  const node = nodes[selectedNode];
  const st = node.actionState;
  const rec = node.recovery;
  if (rec && rec.state === "recovered") {
    actionStateTextEl.textContent = "已恢复（" + rec.recoverTime.slice(11) + "）";
  } else if (rec && rec.state === "processing") {
    actionStateTextEl.textContent = "处理中 | 风扇已开启（连续正常 " + rec.normalStreak + "/2）";
  } else if (st && st.action === "fan_on") {
    actionStateTextEl.textContent = "处理中 | 风扇已开启（" + st.actionTime.slice(11) + "）";
  } else if (st && st.action === "fan_off") {
    const latest = node.latest;
    actionStateTextEl.textContent = (latest && latest.status !== "正常")
      ? "风扇已关闭，仍需关注"
      : "风扇已关闭（" + st.actionTime.slice(11) + "）";
  } else {
    actionStateTextEl.textContent = "尚未处理";
  }
}

fanOnBtn.addEventListener("click", function () { publishAction("fan_on"); });
fanOffBtn.addEventListener("click", function () { publishAction("fan_off"); });

function refreshOverview() {
  // B1 当前总览：每条成功消息后重算（priority.js buildOverview，程序拼接禁写死）
  if (typeof window.buildOverview !== "function") return;   // priority.js 缺失防御
  const hasData = NODE_IDS.some(function (id) { return nodes[id].history.length > 0; });
  if (!hasData) {
    overviewBarEl.hidden = true;
    speakOverviewBtn.hidden = true;   // B4：无提醒可读时隐藏朗读按钮
    return;
  }
  overviewBarEl.textContent = window.buildOverview(nodes);
  overviewBarEl.hidden = false;
  speakOverviewBtn.hidden = false;
}

function speakOverview() {
  // B4 信息分工：TTS 只读当前提醒（B1 总览文本），不长读数据；
  // 实现复用 M1 TTS 模式（web/script.js speechSynthesis 用法，lang zh-CN）
  if (!("speechSynthesis" in window) || !window.speechSynthesis) {
    showWarn("浏览器不支持语音合成（speechSynthesis）——请使用 Chrome / Edge");
    return;
  }
  const text = overviewBarEl.hidden ? "" : overviewBarEl.textContent;
  if (!text) {
    showWarn("暂无当前提醒可朗读——请先接收实时数据");
    return;
  }
  window.speechSynthesis.cancel();   // 重复点击从头朗读，不叠加（web/script.js 同款做法）
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  window.speechSynthesis.speak(utterance);
}
speakOverviewBtn.addEventListener("click", speakOverview);

// ---- E2 语音命令条：Win+H 等价 ASR（识别文字进输入框 -> Enter/失焦 -> 精确匹配指令），web/script.js 同款模式 ----
let dashCameraStream = null;
let lastVoiceAttemptText = "";

function showVoiceResult(text, isError) {
  dashVoiceResultEl.textContent = text;
  dashVoiceResultEl.classList.toggle("error", !!isError);
}

function speakSelectedNode() {
  // E2 朗读状态：TTS 读选中节点最新 MQTT 记录（真实节点数据，非单机表单）
  if (!("speechSynthesis" in window) || !window.speechSynthesis) {
    showWarn("浏览器不支持语音合成（speechSynthesis）——请使用 Chrome / Edge");
    return false;
  }
  const r = nodes[selectedNode].latest;
  if (!r) {
    showWarn("选中节点暂无实时数据，无法朗读");
    return false;
  }
  const text = selectedNode + "当前" + r.status + "：温度" + r.temperature + "摄氏度，湿度百分之" + r.humidity +
    "，建议" + window.ADVICE[r.status];
  window.speechSynthesis.cancel();   // 重复指令从头朗读，不叠加（同款做法）
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  document.body.dataset.lastSpoken = text;   // E2 验收钩子：headless 无音频设备，钩子证明朗读内容来自选中节点真实记录
  window.speechSynthesis.speak(utterance);
  return true;
}

async function ensureDashCamera() {
  // 入口先查 mediaDevices 可用性（用户要求 3）；不可用报错并附引导
  if (dashCameraStream) { return true; }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showVoiceResult("当前环境不支持摄像头——请在 localhost 或 https 下打开，并允许摄像头权限", true);
    return false;
  }
  try {
    dashCameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    dashCameraVideoEl.srcObject = dashCameraStream;
    dashCameraVideoEl.hidden = false;
    dashCameraStateEl.textContent = "摄像头已开启";
    dashCameraStopBtnEl.hidden = false;
    return true;
  } catch (err) {
    showVoiceResult("无法打开摄像头：" + (err.name || "未知错误") + "——请在 localhost 或 https 下打开，并允许摄像头权限", true);
    return false;
  }
}

function stopDashCamera() {
  if (dashCameraStream) {
    dashCameraStream.getTracks().forEach(function (track) { track.stop(); });
    dashCameraStream = null;
  }
  dashCameraVideoEl.srcObject = null;
  dashCameraVideoEl.hidden = true;
  dashCameraStateEl.textContent = "";
  dashCameraStopBtnEl.hidden = true;
}

function lastEventFor(nodeId) {
  // 快照关联对象：处理中草稿优先，否则该节点最近已定稿事件
  if (nodes[nodeId].event) { return nodes[nodeId].event; }
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].nodeId === nodeId) { return events[i]; }
  }
  return null;
}

function downloadBlobLocal(blob, filename) {
  // web/script.js downloadBlob 为模块私有，dashboard 自建同款副本（revoke 延迟 1s 防下载失败）
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
}

function takeSnapshot() {
  // E2 拍照：摄像头帧 + 顶部黑条叠加（nodeId/时间/状态）+ 事件关联（文件名含 eventId，UPGRADE_PLAN §5 决策）
  ensureDashCamera().then(function (ok) {
    if (!ok) { return; }
    const tryFrame = function (attempts) {
      if (!dashCameraVideoEl.videoWidth || dashCameraVideoEl.readyState < 2) {   // 首帧未渲染（web 同款判断）
        if (attempts < 30) { setTimeout(function () { tryFrame(attempts + 1); }, 100); }
        else { showVoiceResult("视频画面加载中，请稍后再试", true); }
        return;
      }
      const canvas = document.createElement("canvas");
      canvas.width = dashCameraVideoEl.videoWidth;
      canvas.height = dashCameraVideoEl.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) { showVoiceResult("快照生成失败，请重试", true); return; }
      ctx.drawImage(dashCameraVideoEl, 0, 0);
      const r = nodes[selectedNode].latest;
      const fs = Math.max(28, Math.round(canvas.width / 26));
      ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
      ctx.fillRect(0, 0, canvas.width, fs * 1.8);
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold " + fs + 'px "Microsoft YaHei", sans-serif';
      ctx.textAlign = "left";
      ctx.fillText(selectedNode + " · " + (r ? r.time : formatNowLocal()) + " · " + (r ? r.status : "无数据"),
        fs * 0.4, fs * 1.3);
      const ev = lastEventFor(selectedNode);
      const stamp = formatNowLocal().replace(/[ :]/g, "-");
      const filename = "dormmate-" + selectedNode + (ev ? "-" + ev.eventId : "") + "-" + stamp + ".png";
      canvas.toBlob(function (blob) {
        if (!blob) { showVoiceResult("快照生成失败，请重试", true); return; }
        downloadBlobLocal(blob, filename);
        if (ev) {
          ev.snapshot = filename;   // 草稿随 finalizeEvent 原对象入 events[]（字段自然保留）；已定稿则直接改 events[] 条目
          renderEvents();
        }
        showVoiceResult("快照已保存（下载目录）：" + filename, false);
      }, "image/png");
    };
    tryFrame(0);
  });
  return true;
}

// 指令表：正则指令先匹配（查看 dorm-x），再精确匹配关键词（web/script.js 同款标点修剪 + 未匹配保留全选）
const DASH_VOICE_COMMANDS = [
  {
    pattern: /^查看\s*(dorm-[abc])$/,
    run: function (m) { switchSelectedNode(m[1]); return { ok: true, msg: "切换到 " + m[1] }; }
  },
  {
    keyword: "朗读状态",
    run: function () { return { ok: speakSelectedNode(), msg: "朗读选中节点当前状态" }; }
  },
  {
    keyword: "拍照",
    run: function () { return { ok: takeSnapshot(), msg: "拍照并关联事件" }; }
  },
  {
    keyword: "开启风扇",
    run: function () { publishAction("fan_on"); return { ok: true, msg: "对 " + selectedNode + " 开启风扇" }; }
  },
  {
    keyword: "关闭风扇",
    run: function () { publishAction("fan_off"); return { ok: true, msg: "对 " + selectedNode + " 关闭风扇" }; }
  }
];

function handleDashVoiceCommand(rawText) {
  const text = rawText.replace(/^[\s。.，,！!？?、]+|[\s。.，,！!？?、]+$/g, "").trim();
  let result = null;
  for (let i = 0; i < DASH_VOICE_COMMANDS.length; i++) {
    const cmd = DASH_VOICE_COMMANDS[i];
    const m = cmd.pattern ? text.match(cmd.pattern) : null;
    if (m) { result = cmd.run(m); break; }
    if (!cmd.pattern && cmd.keyword === text) { result = cmd.run(null); break; }
  }
  if (!result) {
    dashVoiceCommandEl.select();   // 未匹配：保留文本并全选，供修正后重新提交（不清空销毁）
    lastVoiceAttemptText = text;
    showVoiceResult("识别结果：" + text + " → 未匹配任何指令（可用指令：查看 dorm-a/b/c / 朗读状态 / 拍照 / 开启风扇 / 关闭风扇）", true);
    return;
  }
  dashVoiceCommandEl.value = "";
  lastVoiceAttemptText = "";
  showVoiceResult("识别结果：" + text + " → " + (result.ok ? "已触发：" + result.msg : "未执行：" + result.msg), !result.ok);
}

function processDashVoiceInput() {
  const text = dashVoiceCommandEl.value.trim();
  if (!text || text === lastVoiceAttemptText) { return; }   // 空文本 / 未匹配保留的文本不重复处理
  handleDashVoiceCommand(text);
}

dashVoiceCommandEl.addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.isComposing) { processDashVoiceInput(); }   // IME 选字回车不触发
});
dashVoiceCommandEl.addEventListener("blur", processDashVoiceInput);
dashCameraStopBtnEl.addEventListener("click", stopDashCamera);

// ---- B2 判断依据：三节点依据卡片（每项指标附数据来源；优先节点 ★ + 原因）----
const evidenceEls = {};

function buildEvidenceCards() {
  NODE_IDS.forEach(function (id) {
    const card = document.createElement("div");
    card.className = "evidence-card";
    card.innerHTML =
      '<div class="ev-node">' + id + "</div>" +
      '<div class="ev-winner" hidden></div>' +
      "<ul></ul>";
    evidenceCardsEl.appendChild(card);
    evidenceEls[id] = {
      card: card,
      node: card.querySelector(".ev-node"),
      winner: card.querySelector(".ev-winner"),
      list: card.querySelector("ul")
    };
  });
}

function refreshEvidence() {
  // 每条成功消息后重算：指标与来源全部来自程序计算（priority.js），无手写结论
  if (typeof window.computePriority !== "function") return;   // priority.js 缺失防御
  const hasData = NODE_IDS.some(function (id) { return nodes[id].history.length > 0; });
  if (!hasData) { evidenceCardsEl.parentElement.hidden = true; return; }
  evidenceCardsEl.parentElement.hidden = false;

  const result = window.computePriority(nodes);
  const winnerPhrase = typeof window.computeWinnerPhrase === "function"
    ? window.computeWinnerPhrase(nodes) : null;

  result.details.forEach(function (d) {
    const refs = evidenceEls[d.nodeId];
    const latest = nodes[d.nodeId].latest;
    const lines = [];
    // 当前状态（来源：最新记录）
    lines.push("<li>当前状态：<b>" + d.status + "</b>" +
      (latest ? "（" + latest.time.slice(11) + " " + latest.temperature + "℃/" + latest.humidity + "%）" : "（暂无数据）") + "</li>");
    // 连续异常时长（来源：连续异常链的时间范围与条数）
    if (d.status !== "正常") {
      lines.push("<li>连续异常时长：<b>" + d.durationMinutes + " 分钟</b></li>");
      lines.push('<li class="ev-source">依据：' + d.source + "</li>");
    } else {
      lines.push("<li>连续异常时长：无（当前正常）</li>");
    }
    // 异常次数（来源：该节点历史中 status != 正常的记录）
    lines.push("<li>异常次数：<b>" + d.abnormalCount + " 条</b></li>");
    lines.push('<li class="ev-source">依据：该节点历史中 status != 正常的记录条数（demo 记录除外）</li>');
    refs.list.innerHTML = lines.join("");
    // 优先节点标注（原因与优先横幅同源）
    const isWinner = d.nodeId === result.nodeId;
    refs.card.className = "evidence-card" + (isWinner ? " winner" : "");
    refs.winner.hidden = !isWinner;
    if (isWinner && winnerPhrase) {
      refs.winner.textContent = "★ 当前优先：依据（" + winnerPhrase.phrase + "）";
    }
  });
}

function refreshPriority() {
  // A1 优先关注：每条成功消息后重算横幅（priority.js computePriority，程序计算禁人工）
  if (typeof window.computePriority !== "function") return;   // priority.js 缺失防御
  const hasData = NODE_IDS.some(function (id) { return nodes[id].history.length > 0; });
  if (!hasData) { priorityBannerEl.hidden = true; return; }   // 尚无真实数据时不显示
  const result = window.computePriority(nodes);
  priorityBannerEl.textContent = result.reason;
  priorityBannerEl.className = "priority " + (result.nodeId ? "has" : "none");
  priorityBannerEl.hidden = false;
  // A3 跨端广播：优先节点变化时发布 dormmate/priority（与横幅同源、程序计算；空串=无重点）
  const winner = result.nodeId || "";
  if (winner !== lastPriorityPublished) {
    lastPriorityPublished = winner;
    client.publish(PRIORITY_TOPIC, JSON.stringify({ nodeId: winner, reason: result.reason, time: formatNowLocal() }), { qos: 0 }, function (err) {
      if (err) showWarn("优先状态发布失败：" + err.message);
    });
  }
  // A4：优先原因回填到当前优先节点的事件草稿（随横幅每次刷新更新，保持"当下判断"的原因；
  // 短语取横幅"优先关注 X：已连续…分钟"中的依据部分，与截图 A1 例句口径一致）
  if (result.nodeId && nodes[result.nodeId].event) {
    const prefix = "优先关注 " + result.nodeId + "：";
    if (result.reason.indexOf(prefix) === 0) {
      nodes[result.nodeId].event.priorityReason = result.reason.slice(prefix.length).split("；")[0];
    }
  }
}

// 点击横幅关闭（下次丢弃消息时重新显示）
warnBannerEl.addEventListener("click", function () {
  showWarn("");
});

// ---- MQTT 连接（mqtt.js，WebSocket；reconnectPeriod 断线自动重连）----
const client = mqtt.connect(WS_URL, { reconnectPeriod: 2000 });

client.on("connect", function () {
  if (rulesMissing) {
    setConnState(false, "规则模块（web/script.js）加载失败——请以项目根目录为工作区打开本页");
    client.subscribe(TOPIC, function (err) {
      if (err) showWarn("订阅失败：" + err.message);
    });
    client.subscribe(ACTION_TOPIC, function (err) {
      if (err) showWarn("动作订阅失败：" + err.message);
    });
    return;
  }
  setConnState(true, "已连接 " + WS_URL);
  client.subscribe(TOPIC, function (err) {
    if (err) showWarn("订阅失败：" + err.message);
  });
  client.subscribe(ACTION_TOPIC, function (err) {
    if (err) showWarn("动作订阅失败：" + err.message);
  });
});
client.on("reconnect", function () { setConnState(false, "已断开，重连中…"); });
client.on("close", function () { setConnState(false, "已断开，重连中…"); });
client.on("error", function (err) { setConnState(false, "连接错误：" + err.message); });
client.on("message", function (topic, payload) {
  // mqtt.js v5 浏览器端 payload 恒为 Uint8Array，单例 TextDecoder 解码
  const text = utf8Decoder.decode(payload);
  if (/^dormmate\/[^/]+\/action$/.test(topic)) {
    handleActionMessage(topic, text);   // A2 联动#1：动作通道（外部 fan_on 进入状态机）
  } else {
    handleMessage(topic, text);
  }
});

// ---- 渲染：三卡片与 tab 均建一次、增量更新（评审修复：不再每条消息全量重建 DOM）----
const cardEls = {};

function buildCards() {
  NODE_IDS.forEach(function (id) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML =
      '<div class="node">' + id + "</div>" +
      '<div class="status">—</div>' +
      '<div class="metrics">等待数据…</div>' +
      '<div class="advice"></div>' +
      '<div class="action"></div>' +
      '<div class="time"></div>';
    cardsEl.appendChild(card);
    cardEls[id] = {
      status: card.querySelector(".status"),
      metrics: card.querySelector(".metrics"),
      advice: card.querySelector(".advice"),
      action: card.querySelector(".action"),
      time: card.querySelector(".time")
    };
  });
}

function updateCard(nodeId) {
  const refs = cardEls[nodeId];
  const r = nodes[nodeId].latest;
  if (!r) return;
  refs.status.textContent = r.status;
  refs.status.className = "status " + r.status;   // 颜色类随状态切换
  refs.metrics.textContent = r.temperature + "℃ / " + r.humidity + "%";
  refs.advice.textContent = window.ADVICE[r.status];   // 建议查表渲染，不入记录（保持统一 JSON 六字段）
  // A2/A3 三态显示：仍需关注 / 处理中 / 已恢复（恢复必须由新数据触发，按钮只发动作）
  const st = nodes[nodeId].actionState;
  const rec = nodes[nodeId].recovery;
  if (rec && rec.state === "recovered") {
    refs.action.textContent = "已恢复（" + rec.recoverTime.slice(11) + "）";
  } else if (rec && rec.state === "processing") {
    refs.action.textContent = "处理中 | 风扇已开启（连续正常 " + rec.normalStreak + "/2）";
  } else if (st && st.action === "fan_on") {
    refs.action.textContent = "处理中 | 风扇已开启";
  } else if (st && st.action === "fan_off") {
    refs.action.textContent = (r.status !== "正常") ? "风扇已关闭，仍需关注" : "风扇已关闭";
  } else {
    refs.action.textContent = "";
  }
  refs.time.textContent = r.time;   // textContent 注入安全（与 web/script.js 同款惯例）
}

const tabEls = {};

function switchSelectedNode(nodeId) {
  // E2：tab 点击与语音指令共用同一选中切换入口
  selectedNode = nodeId;
  Object.keys(tabEls).forEach(function (key) {
    tabEls[key].className = key === nodeId ? "active" : "";
  });
  rebuildChart();
  refreshActionBar();   // A2 动作条随 tab 切换刷新到当前节点
}

function buildTabs() {
  NODE_IDS.forEach(function (id) {
    const btn = document.createElement("button");
    btn.textContent = id;
    btn.addEventListener("click", function () { switchSelectedNode(id); });
    tabsEl.appendChild(btn);
    tabEls[id] = btn;
  });
  tabEls[selectedNode].className = "active";
}

// 初始渲染
buildCards();
buildTabs();
buildEvidenceCards();
rebuildChart();
refreshActionBar();
