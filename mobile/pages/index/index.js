// M4 S2/S3：Page data + setData + bindinput + bindtap（任务书第 17 条）
// 业务规则统一来自 utils/rules.js（移植 M1 web/script.js 纯函数，见该文件头注释）
const rules = require("../../utils/rules.js");

// M5 预留：本页可选订阅 MQTT（topic dormmate/{nodeId}/env），实时记录追加进 history；
// M4 不实现订阅，仅预留接入点（见 docs/M4_PLAN.md §4）
Page({
  // Page data：页面数据的唯一来源；界面渲染与更新全部走 setData
  data: {
    temperature: "",
    humidity: "",
    status: "—",
    advice: "—",
    errorMsg: "",
    history: []
  },

  // onLoad：页面加载即自动跑自测（SPEC §6 四组回归 + ADVICE / 校验 / formatTime 一致性校验），
  // Console 直接输出 PASS/FAIL。说明：开发者工具 Console 不支持直接 require('utils/rules.js')
  // （实测报 require is not defined），故自测入口放在这里，随页面加载自动执行，无需手动命令
  onLoad: function () {
    rules.runRulesSelfTest();
  },

  // bindinput：输入即写入 Page data（e.detail.value = 输入框当前值）
  onTempInput: function (e) {
    this.setData({ temperature: e.detail.value });
  },
  onHumidityInput: function (e) {
    this.setData({ humidity: e.detail.value });
  },

  // bindtap="onAnalyze"：校验 → 统一规则判断 → setData 更新状态/建议 → 追加历史
  // 校验失败：只显示错误提示，不分析、不追加历史（与 M1 行为一致）
  onAnalyze: function () {
    const result = rules.validateInputs(this.data.temperature, this.data.humidity);
    if (result.messages.length > 0) {
      this.setData({ errorMsg: result.messages.join("；") });
      return;
    }
    // 记录 = SPEC §4 统一 JSON（buildRecord 构造；status 由规则计算，action 预留空字符串）
    const record = rules.buildRecord(result.temperature, result.humidity, rules.formatTime(new Date()));
    this.setData({
      status: record.status,
      advice: rules.ADVICE[record.status],
      errorMsg: "",
      history: this.data.history.concat(record)
    });
  },

  // bindtap="onLoadDemo"：追加 4 条演示历史 = SPEC §6 四组回归数据（四个状态各一），
  // 与 onAnalyze 一致用 concat 追加，不清空已有记录；time 依次往前推 4/3/2/1 分钟
  onLoadDemo: function () {
    const now = Date.now();
    const demo = rules.REGRESSION_CASES.map(function (c, index) {
      return rules.buildRecord(c.temperature, c.humidity, rules.formatTime(new Date(now - (4 - index) * 60000)));
    });
    this.setData({ history: this.data.history.concat(demo) });
  }
});
