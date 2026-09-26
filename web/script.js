// DormMate 统一状态规则（SPEC §3）——全项目唯一 JS 实现
// Python 侧（M2）按同一规则移植，须通过 SPEC §6 同一四组回归（见 docs/M1_PLAN.md）
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

// 单字段校验（S4）：空值 / 非数字（只接受十进制书写，拦截 0x/0b/1e 等） / 超出范围
// 返回错误文案，空字符串 = 合法
function validateField(rawValue, min, max, label) {
  const text = String(rawValue).trim();
  if (text === "") return `${label}不能为空`;
  if (!/^-?\d+(\.\d+)?$/.test(text)) return `${label}必须是数字`;
  const value = Number(text);
  if (value < min || value > max) return `${label}须在 ${min}~${max} 之间`;
  return "";
}

// 校验并解析两字段（S4）：返回 { messages, temperature, humidity }
// messages 为空 = 合法，此时 temperature/humidity 可直接使用（调用方无需二次 Number()）
function validateInputs(rawTemperature, rawHumidity) {
  const temperatureText = String(rawTemperature).trim();
  const humidityText = String(rawHumidity).trim();
  const messages = [];
  const temperatureError = validateField(temperatureText, TEMP_MIN, TEMP_MAX, "温度");
  if (temperatureError) messages.push(temperatureError);
  const humidityError = validateField(humidityText, HUMIDITY_MIN, HUMIDITY_MAX, "湿度");
  if (humidityError) messages.push(humidityError);
  return {
    messages: messages,
    temperature: Number(temperatureText),
    humidity: Number(humidityText)
  };
}

// 历史记录（S5）：仅存内存，刷新后可消失；内部结构 = SPEC §4 统一 JSON，action 预留空字符串
// 消费方（M2 导出 CSV 等）只读该数组、勿整体重赋值——analyze() 始终写入此模块级数组
const dormmateHistory = [];

function pad2(n) { return String(n).padStart(2, "0"); }

// time 格式：YYYY-MM-DD HH:MM:SS（SPEC §4）
function formatTime(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ` +
    `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

// analyze：校验 → 判断 → 显示状态与建议 → 追加历史（M3 语音指令直接调用此入口）
// 参数可选：analyze("16", "60") 或 analyze(16, 60) 直接传值；不传则读取页面输入框
// 校验不通过：错误提示区显示具体原因，不分析、不追加历史，返回 null
// 成功：返回本次记录（统一 JSON），供 M3 语音播报等复用
function analyze(rawTemperature, rawHumidity) {
  const temperatureInput = document.getElementById("temperature");
  const humidityInput = document.getElementById("humidity");
  const errorMsg = document.getElementById("errorMsg");
  const statusText = document.getElementById("statusText");
  const adviceText = document.getElementById("adviceText");
  const historyList = document.getElementById("historyList");

  // 元素缺失（如 test.html 无表单）时显式报错，不静默失败
  if (!temperatureInput || !humidityInput || !errorMsg || !statusText || !adviceText || !historyList) {
    throw new Error("analyze() 需要 M1 表单元素（#temperature/#humidity/#errorMsg/#statusText/#adviceText/#historyList），当前页面缺少部分元素");
  }

  const rawTemperatureValue = rawTemperature === undefined ? temperatureInput.value : rawTemperature;
  const rawHumidityValue = rawHumidity === undefined ? humidityInput.value : rawHumidity;

  const result = validateInputs(rawTemperatureValue, rawHumidityValue);
  if (result.messages.length > 0) {
    errorMsg.textContent = result.messages.join("；");
    errorMsg.hidden = false;
    return null;
  }
  errorMsg.textContent = "";
  errorMsg.hidden = true;

  const status = computeStatus(result.temperature, result.humidity);
  statusText.textContent = status;
  adviceText.textContent = ADVICE[status];

  const record = {
    nodeId: "dorm-a",
    temperature: result.temperature,
    humidity: result.humidity,
    status: status,
    time: formatTime(new Date()),
    action: ""
  };
  dormmateHistory.push(record);

  const li = document.createElement("li");
  li.textContent = `${record.time} · ${record.nodeId} · ${record.temperature}℃ / ${record.humidity}% · ${record.status}`;
  historyList.appendChild(li);

  return record;
}

// M2 S1：CSV 导出（SPEC §5 最小格式：time,temperature,humidity,status 严格 4 列，UTF-8）
// buildCsv 纯函数：入参历史数组 → CSV 字符串；不含 nodeId/action；time 全格式原样输出；CRLF 换行
function buildCsv(history) {
  const header = "time,temperature,humidity,status";
  const rows = history.map(function (record) {
    return [record.time, record.temperature, record.humidity, record.status].join(",");
  });
  return [header].concat(rows).join("\r\n") + "\r\n";
}

// downloadCsv：把 dormmateHistory 导出为 dormmate.csv（Blob + 临时 <a download>）
// 加 UTF-8 BOM（﻿）保证 Excel/WPS 打开中文 status 不乱码；Python 端统一 utf-8-sig 读取
function downloadCsv() {
  if (dormmateHistory.length === 0) {
    alert("暂无历史记录，先分析几条数据再导出");
    return;
  }
  const csv = "﻿" + buildCsv(dormmateHistory);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "dormmate.csv";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// 直接暴露到全局：test.html 回归测试与 M3 语音指令都依赖
// 历史数组不叫 window.history（浏览器自带同名 API），用 dormmateHistory 避免覆盖
if (typeof window !== "undefined") {
  window.computeStatus = computeStatus;
  window.ADVICE = ADVICE;
  window.validateField = validateField;
  window.validateInputs = validateInputs;
  window.analyze = analyze;
  window.dormmateHistory = dormmateHistory;
  window.buildCsv = buildCsv;
  window.downloadCsv = downloadCsv;
}

// DOM 操作一律包在 DOMContentLoaded 内，保证 test.html 引入本文件时不触碰 DOM
if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", function () {
    const analyzeBtn = document.getElementById("analyzeBtn");
    if (analyzeBtn) analyzeBtn.addEventListener("click", function () { analyze(); });
    // M2 S1：导出 CSV 按钮（历史为空时 downloadCsv 内提示，不导出空文件）
    const exportBtn = document.getElementById("exportBtn");
    if (exportBtn) exportBtn.addEventListener("click", downloadCsv);

    // M3 S1：Camera（任务书第 11 条）——点击才请求权限，不连续采集、不自动开启
    // 注意：getUserMedia 要求 localhost 或 https，file:// 下不可用
    const cameraVideo = document.getElementById("cameraVideo");
    const startCameraBtn = document.getElementById("startCameraBtn");
    const snapshotBtn = document.getElementById("snapshotBtn");
    const stopCameraBtn = document.getElementById("stopCameraBtn");
    const cameraMsg = document.getElementById("cameraMsg");
    let cameraStream = null;

    function showCameraMsg(text) {
      if (!cameraMsg) return;
      cameraMsg.textContent = text;
      cameraMsg.hidden = text === "";
    }

    async function startCamera() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showCameraMsg("当前环境不支持摄像头（请通过 localhost / Live Server 打开页面）");
        return;
      }
      try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        cameraVideo.srcObject = cameraStream;
        startCameraBtn.disabled = true;
        snapshotBtn.disabled = false;
        stopCameraBtn.disabled = false;
        showCameraMsg("");
      } catch (err) {
        showCameraMsg("无法打开摄像头：" + (err.name || "未知错误") +
          "（请允许摄像头权限，并确认未被其他软件占用）");
      }
    }

    function stopCamera() {
      if (cameraStream) {
        cameraStream.getTracks().forEach(function (track) { track.stop(); });
        cameraStream = null;
      }
      cameraVideo.srcObject = null;
      startCameraBtn.disabled = false;
      snapshotBtn.disabled = true;
      stopCameraBtn.disabled = true;
    }

    function saveSnapshot() {
      if (!cameraStream || !cameraVideo.videoWidth) {
        showCameraMsg("请先打开摄像头");
        return;
      }
      const canvas = document.createElement("canvas");
      canvas.width = cameraVideo.videoWidth;
      canvas.height = cameraVideo.videoHeight;
      canvas.getContext("2d").drawImage(cameraVideo, 0, 0);
      canvas.toBlob(function (blob) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "dormmate-snapshot-" + formatTime(new Date()).replace(/[ :]/g, "-") + ".png";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        showCameraMsg("快照已保存（下载目录）");
      }, "image/png");
    }

    if (startCameraBtn) startCameraBtn.addEventListener("click", startCamera);
    if (snapshotBtn) snapshotBtn.addEventListener("click", saveSnapshot);
    if (stopCameraBtn) stopCameraBtn.addEventListener("click", stopCamera);
    // 输入框按 Enter 同样触发分析（页面无 form 提交路径）
    ["temperature", "humidity"].forEach(function (id) {
      const input = document.getElementById(id);
      if (input) input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") analyze();
      });
    });
  });
}
