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

// analyze：读取输入 → 判断 → 展示（M3 语音指令直接调用此入口；S3 接入输入与建议，S4 加入校验）
function analyze() {
  // S3 实现
}

// 直接暴露到全局：test.html 回归测试与 M3 语音指令都依赖
if (typeof window !== "undefined") {
  window.computeStatus = computeStatus;
  window.ADVICE = ADVICE;
  window.analyze = analyze;
}

// DOM 操作一律包在 DOMContentLoaded 内，保证 test.html 引入本文件时不触碰 DOM
if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", function () {
    // S3 绑定"分析环境"按钮与输入
  });
}
