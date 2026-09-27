// M4 S2/S3：Page data + setData + bindinput + bindtap（任务书第 17 条）
// 业务规则统一来自 utils/rules.js（移植 M1 web/script.js 纯函数，见该文件头注释）
const rules = require("../../utils/rules.js");

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

  // onLoad：页面加载即自动跑四组回归自测（SPEC §6），Console 直接输出 4 行 PASS
  // 说明：开发者工具 Console 不支持直接 require('utils/rules.js')（实测报 require is not defined），
  // 故自测入口放在这里，随页面加载自动执行，无需手动命令
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
      return null;
    }
    const status = rules.computeStatus(result.temperature, result.humidity);
    // 记录结构 = SPEC §4 统一 JSON（nodeId / temperature / humidity / status / time / action；
    // action 为预留字段，M1-M4 恒为空字符串）
    const record = {
      nodeId: "dorm-a",
      temperature: result.temperature,
      humidity: result.humidity,
      status: status,
      time: rules.formatTime(new Date()),
      action: ""
    };
    this.setData({
      status: status,
      advice: rules.ADVICE[status],
      errorMsg: "",
      history: this.data.history.concat(record)
    });
    return record;
  },

  // bindtap="onLoadDemo"：预置 4 条演示历史 = SPEC §6 四组回归数据（四个状态各一），
  // time 取当前往前推 1-4 分钟；不改变当前状态/建议区（只演示"查看数据"）
  onLoadDemo: function () {
    const now = Date.now();
    const demo = [
      { temperature: 25, humidity: 60 },
      { temperature: 16, humidity: 60 },
      { temperature: 31, humidity: 60 },
      { temperature: 25, humidity: 80 }
    ].map(function (item, index) {
      return {
        nodeId: "dorm-a",
        temperature: item.temperature,
        humidity: item.humidity,
        status: rules.computeStatus(item.temperature, item.humidity),
        time: rules.formatTime(new Date(now - (3 - index) * 60000)),
        action: ""
      };
    });
    this.setData({ history: demo });
  }
});
