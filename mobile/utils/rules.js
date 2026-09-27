// DormMate 统一状态规则 —— 小程序侧实现（M4 S2）
// 移植自 web/script.js（M1 全项目唯一 JS 实现）的纯函数部分，逐行同语义，禁止改规则：
//   SPEC §3：status 顺序不可改（① <18 偏冷 ② >=30 偏热 ③ >=75 偏湿 ④ 其余 正常），命中即返回
//   SPEC §3.1：温度 −50~50、湿度 0~100（含边界）
//   SPEC §6：四组回归（25/60→正常、16/60→偏冷、31/60→偏热、25/80→偏湿）必须全部通过
// 说明：小程序无法直接 require web/script.js（含 window/document DOM 代码、无 module.exports），
// 故按 M2 Python 移植同模式，仅迁移纯函数、不复制 Web DOM 代码（M4_PLAN §1 决策记录）。
// 回归自测：由 pages/index/index.js 的 onLoad 自动执行（开发者工具 Console 不支持直接 require，实测报 require is not defined）

// SPEC §3：status 判断顺序不可改（① <18 偏冷 ② >=30 偏热 ③ >=75 偏湿 ④ 其余 正常），命中即返回
function computeStatus(temperature, humidity) {
  if (temperature < 18) return "偏冷";
  if (temperature >= 30) return "偏热";
  if (humidity >= 75) return "偏湿";
  return "正常";
}

// 建议映射表（与 web/script.js 的 ADVICE 一致）
const ADVICE = {
  "偏冷": "注意保暖",
  "偏热": "注意通风",
  "偏湿": "注意除湿",
  "正常": "环境舒适"
};

// SPEC §3.1 输入合法范围（含边界，与 web/script.js 一致）
const TEMP_MIN = -50, TEMP_MAX = 50;
const HUMIDITY_MIN = 0, HUMIDITY_MAX = 100;

// 单字段校验（与 web/script.js 的 validateField 同语义）：
// 空值 / 非数字（只接受十进制书写，拦截 0x/0b/1e 等） / 超出范围
// 返回错误文案，空字符串 = 合法
function validateField(rawValue, min, max, label) {
  const text = String(rawValue).trim();
  if (text === "") return `${label}不能为空`;
  if (!/^-?\d+(\.\d+)?$/.test(text)) return `${label}必须是数字`;
  const value = Number(text);
  if (value < min || value > max) return `${label}须在 ${min}~${max} 之间`;
  return "";
}

// 校验并解析两字段（与 web/script.js 的 validateInputs 同语义）
// 调用契约：必须先检查 messages 为空再使用 temperature/humidity——校验失败时返回值不可用
// （空串 Number 后为 0、非法文本为 NaN），直接使用会把错误值算成状态
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

function pad2(n) { return String(n).padStart(2, "0"); }

// time 格式：YYYY-MM-DD HH:MM:SS（SPEC §4）
function formatTime(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ` +
    `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

// SPEC §6 统一回归测试数据（runRulesSelfTest 与 index.js"载入演示数据"共用同一份，勿改动）
const REGRESSION_CASES = [
  { temperature: 25, humidity: 60, expected: "正常" },
  { temperature: 16, humidity: 60, expected: "偏冷" },
  { temperature: 31, humidity: 60, expected: "偏热" },
  { temperature: 25, humidity: 80, expected: "偏湿" }
];

// SPEC §4 统一 JSON 记录构造（onAnalyze / onLoadDemo 共用）：
// status 一律由 computeStatus 计算（禁止手填）；nodeId 单宿舍阶段固定 dorm-a；
// action 为预留字段，M1-M4 恒为空字符串
function buildRecord(temperature, humidity, time) {
  return {
    nodeId: "dorm-a",
    temperature: temperature,
    humidity: humidity,
    status: computeStatus(temperature, humidity),
    time: time,
    action: ""
  };
}

// SPEC §6 四组回归自测（对应 web/test.html 的角色）+ 移植一致性附加校验（M4 评审加固）：
// 先输出四组回归（顺序固定），再校验 ADVICE 映射 / validateField 范围与拦截 / formatTime 补零，
// 全部逐行打印 PASS/FAIL，返回是否全部通过
function runRulesSelfTest() {
  let allPassed = true;

  function check(label, passed) {
    if (!passed) allPassed = false;
    console.log(`${passed ? "PASS" : "FAIL"}  ${label}`);
  }

  // 四组回归（SPEC §6）
  REGRESSION_CASES.forEach(function (c) {
    const actual = computeStatus(c.temperature, c.humidity);
    check(`${c.temperature}/${c.humidity} -> ${actual}（期望 ${c.expected}）`, actual === c.expected);
  });

  // ADVICE 映射一致性（与 web/script.js 一致）
  [
    ["偏冷", "注意保暖"], ["偏热", "注意通风"], ["偏湿", "注意除湿"], ["正常", "环境舒适"]
  ].forEach(function (pair) {
    check(`ADVICE[${pair[0]}] = ${pair[1]}`, ADVICE[pair[0]] === pair[1]);
  });

  // validateField 合法边界（SPEC §3.1 含边界）
  [
    ["-50", TEMP_MIN, TEMP_MAX], ["50", TEMP_MIN, TEMP_MAX],
    ["0", HUMIDITY_MIN, HUMIDITY_MAX], ["100", HUMIDITY_MIN, HUMIDITY_MAX]
  ].forEach(function (c) {
    check(`validateField("${c[0]}") 边界合法`, validateField(c[0], c[1], c[2], "值") === "");
  });

  // validateField 拦截：空值 / 非数字 / 超范围（温度 −50~50、湿度 0~100）
  [
    ["", TEMP_MIN, TEMP_MAX, "不能为空"],
    ["abc", TEMP_MIN, TEMP_MAX, "必须是数字"],
    ["0x1A", TEMP_MIN, TEMP_MAX, "必须是数字"],
    ["-50.1", TEMP_MIN, TEMP_MAX, "之间"],
    ["50.1", TEMP_MIN, TEMP_MAX, "之间"],
    ["-1", HUMIDITY_MIN, HUMIDITY_MAX, "之间"],
    ["101", HUMIDITY_MIN, HUMIDITY_MAX, "之间"]
  ].forEach(function (c) {
    const msg = validateField(c[0], c[1], c[2], "值");
    check(`validateField("${c[0]}") 拦截`, msg !== "" && msg.indexOf(c[3]) >= 0);
  });

  // formatTime 补零与格式（SPEC §4：YYYY-MM-DD HH:MM:SS；2026 年 9 月 5 日 7:09:03）
  check("formatTime 补零", formatTime(new Date(2026, 8, 5, 7, 9, 3)) === "2026-09-05 07:09:03");

  return allPassed;
}

module.exports = {
  computeStatus: computeStatus,
  ADVICE: ADVICE,
  TEMP_MIN: TEMP_MIN,
  TEMP_MAX: TEMP_MAX,
  HUMIDITY_MIN: HUMIDITY_MIN,
  HUMIDITY_MAX: HUMIDITY_MAX,
  validateField: validateField,
  validateInputs: validateInputs,
  formatTime: formatTime,
  REGRESSION_CASES: REGRESSION_CASES,
  buildRecord: buildRecord,
  runRulesSelfTest: runRulesSelfTest
};
