// DormMate 统一状态规则（SPEC §3）——全项目唯一实现，其他模块（M4/M5/Python）禁止重写
// 本文件被 index.html 与 test.html 共用：顶层不得有任何 DOM 操作（test.html 无页面元素）

// SPEC §3：status 判断顺序不可改（① <18 偏冷 ② >=30 偏热 ③ >=75 偏湿 ④ 其余 正常），命中即返回
function computeStatus(temperature, humidity) {
  if (temperature < 18) return "偏冷";
  if (temperature >= 30) return "偏热";
  if (humidity >= 75) return "偏湿";
  return "正常";
}

// 建议映射表（文案见 M1_PLAN §1 决策记录）
const ADVICE = {
  "偏冷": "注意保暖",
  "偏热": "注意通风",
  "偏湿": "注意除湿",
  "正常": "环境舒适"
};

// SPEC §3.1 输入合法范围（含边界，各模块统一复用此范围）
const TEMP_MIN = -50, TEMP_MAX = 50;
const HUMIDITY_MIN = 0, HUMIDITY_MAX = 100;

// 校验输入（S4）：空值 / 非数字（Number() 后 isNaN）/ 明显异常值（超出 §3.1 范围）
// 返回错误文案数组，空数组 = 合法；逐字段给出具体原因
function validateInputs(rawTemperature, rawHumidity) {
  const messages = [];
  const temperature = Number(rawTemperature);
  const humidity = Number(rawHumidity);

  if (rawTemperature.trim() === "") messages.push("温度不能为空");
  else if (isNaN(temperature)) messages.push("温度必须是数字");
  else if (temperature < TEMP_MIN || temperature > TEMP_MAX) messages.push("温度须在 " + TEMP_MIN + "~" + TEMP_MAX + " 之间");

  if (rawHumidity.trim() === "") messages.push("湿度不能为空");
  else if (isNaN(humidity)) messages.push("湿度必须是数字");
  else if (humidity < HUMIDITY_MIN || humidity > HUMIDITY_MAX) messages.push("湿度须在 " + HUMIDITY_MIN + "~" + HUMIDITY_MAX + " 之间");

  return messages;
}

// 历史记录（S5）：仅存内存，刷新后可消失；内部结构 = SPEC §4 统一 JSON，action 预留空字符串
const dormmateHistory = [];

// time 格式：YYYY-MM-DD HH:MM:SS（SPEC §4）
function formatTime(d) {
  function pad(n) { return n < 10 ? "0" + n : "" + n; }
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
    " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
}

// analyze：校验 → 读取输入 → 判断 → 显示状态与建议 → 追加历史（M3 语音指令直接调用此入口）
// 校验不通过时：错误提示区显示具体原因，不分析、不追加历史
function analyze() {
  const temperatureInput = document.getElementById("temperature");
  const humidityInput = document.getElementById("humidity");
  const errorMsg = document.getElementById("errorMsg");

  const errors = validateInputs(temperatureInput.value, humidityInput.value);
  if (errors.length > 0) {
    errorMsg.textContent = errors.join("；");
    errorMsg.hidden = false;
    return;
  }
  errorMsg.textContent = "";
  errorMsg.hidden = true;

  const temperature = Number(temperatureInput.value);
  const humidity = Number(humidityInput.value);
  const status = computeStatus(temperature, humidity);

  document.getElementById("statusText").textContent = status;
  document.getElementById("adviceText").textContent = ADVICE[status];

  const record = {
    nodeId: "dorm-a",
    temperature: temperature,
    humidity: humidity,
    status: status,
    time: formatTime(new Date()),
    action: ""
  };
  dormmateHistory.push(record);

  const li = document.createElement("li");
  li.textContent = record.time + " · " + record.nodeId + " · " +
    record.temperature + "℃ / " + record.humidity + "% · " + record.status;
  document.getElementById("historyList").appendChild(li);
}

// 直接暴露到全局：test.html 回归测试与 M3 语音指令都依赖
// 历史数组不叫 window.history（浏览器自带同名 API），用 dormmateHistory 避免覆盖
if (typeof window !== "undefined") {
  window.computeStatus = computeStatus;
  window.ADVICE = ADVICE;
  window.validateInputs = validateInputs;
  window.analyze = analyze;
  window.dormmateHistory = dormmateHistory;
}

// DOM 操作一律包在 DOMContentLoaded 内，保证 test.html 引入本文件时不触碰 DOM
if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", function () {
    const analyzeBtn = document.getElementById("analyzeBtn");
    if (analyzeBtn) analyzeBtn.addEventListener("click", analyze);
  });
}
