// M4 S2/S3：Page data + setData + bindinput + bindtap（任务书第 17 条）
// 业务规则统一来自 utils/rules.js（移植 M1 web/script.js 纯函数，见该文件头注释）
const rules = require("../../utils/rules.js");
// V0.8R5 阶段 A（A1）：极简 MQTT 客户端（wx.connectSocket 承载，见 utils/mqtt.js 头注释）
const mqtt = require("../../utils/mqtt.js");

// A1/A2 实时订阅：dormmate/{nodeId}/env → 与 dashboard 同策略（topic↔nodeId 防串线 +
// 范围校验 + 本地重算 status，不信任消息 status）；三节点卡片恒显示（无数据时"等待数据"），
// "开启风扇"发布 dormmate/{nodeId}/action（联动#1：simulator 降温 → Dashboard 处理中 → 3D 风扇转）
// A3：订阅 dormmate/{nodeId}/event（处理中/已恢复徽标）与 dormmate/priority（★当前重点），
// 事件与重点状态来自 Dashboard 广播（同一套系统状态源），本页只展示、不自行判断
const NODE_ORDER = ["dorm-a", "dorm-b", "dorm-c"];
const STATUS_CLASS = { "正常": "normal", "偏冷": "cold", "偏热": "hot", "偏湿": "wet" };

function nodePlaceholder(id) {
  return { nodeId: id, temperature: "—", humidity: "—", status: "等待数据", statusClass: "waiting", time: "" };
}

Page({
  // Page data：页面数据的唯一来源；界面渲染与更新全部走 setData
  data: {
    temperature: "",
    humidity: "",
    status: "—",
    advice: "—",
    errorMsg: "",
    history: [],
    mqttState: "未连接",
    mqttNodes: NODE_ORDER.map(nodePlaceholder),
    fanPending: false
  },

  // onLoad：页面加载即自动跑自测（SPEC §6 四组回归 + ADVICE / 校验 / formatTime 一致性校验），
  // Console 直接输出 PASS/FAIL。说明：开发者工具 Console 不支持直接 require('utils/rules.js')
  // （实测报 require is not defined），故自测入口放在这里，随页面加载自动执行，无需手动命令
  onLoad: function () {
    rules.runRulesSelfTest();
    this.initMqtt();
  },

  // onUnload：离开页面关闭 MQTT（停止重连与保活定时器）并清理防抖定时器
  onUnload: function () {
    if (this.mqttClient) {
      this.mqttClient.close();
      this.mqttClient = null;
    }
    if (this.fanResetTimer) {
      clearTimeout(this.fanResetTimer);
      this.fanResetTimer = null;
    }
  },

  // A1：建立 MQTT 连接并订阅 dormmate/+/env；收到 env 消息 → 校验 → 本地重算状态 → 展示
  initMqtt: function () {
    const that = this;
    const latest = {};       // nodeId → 最新 env 记录
    const eventByNode = {};  // nodeId → 最新事件状态（A3，来自 Dashboard 广播）
    let priorityNode = "";   // A3：当前重点节点（来自 Dashboard 广播）
    const EVENT_LABEL = { OPEN: "待处理", HANDLING: "处理中", RECOVERED: "已恢复", CANCELLED: "已取消" };
    const EVENT_CLASS = { OPEN: "open", HANDLING: "handling", RECOVERED: "recovered", CANCELLED: "cancelled" };
    const EVENT_STATES = ["OPEN", "HANDLING", "RECOVERED", "CANCELLED"];

    function renderNodes() {
      that.setData({
        mqttNodes: NODE_ORDER.map(function (id) {
          const rec = latest[id] || nodePlaceholder(id);
          const evt = eventByNode[id];
          return {
            nodeId: id,
            temperature: rec.temperature,
            humidity: rec.humidity,
            status: rec.status,
            statusClass: rec.statusClass,
            time: rec.time,
            isPriority: priorityNode === id,
            eventBadge: evt ? (EVENT_LABEL[evt.state] || evt.state) : "",
            eventBadgeClass: evt ? (EVENT_CLASS[evt.state] || "") : ""
          };
        })
      });
    }

    // A3：事件状态（Dashboard 状态机广播，本页只订阅展示，不自行判断）
    function handleEventMessage(topic, payload) {
      const nodeIdFromTopic = topic.split("/")[1];
      let msg;
      try {
        msg = JSON.parse(payload);
      } catch (e) {
        console.log("[MQTT] 事件非法 JSON 忽略: " + topic + " " + payload);
        return;
      }
      if (msg.nodeId !== nodeIdFromTopic) {
        console.log("[MQTT] 事件串线忽略: topic=" + nodeIdFromTopic + " payload.nodeId=" + msg.nodeId);
        return;
      }
      if (NODE_ORDER.indexOf(msg.nodeId) < 0 || EVENT_STATES.indexOf(msg.state) < 0) {
        console.log("[MQTT] 事件状态非法忽略: " + topic + " " + payload);
        return;
      }
      eventByNode[msg.nodeId] = { state: msg.state, time: String(msg.time || "") };
      renderNodes();
      console.log("[MQTT] 事件状态: " + msg.nodeId + " → " + msg.state);
    }

    // A3：当前重点节点（Dashboard 广播，程序计算，本页只展示）
    function handlePriorityMessage(payload) {
      let msg;
      try {
        msg = JSON.parse(payload);
      } catch (e) {
        console.log("[MQTT] 优先消息非法 JSON 忽略");
        return;
      }
      if (typeof msg.nodeId !== "string") return;
      priorityNode = NODE_ORDER.indexOf(msg.nodeId) >= 0 ? msg.nodeId : "";
      renderNodes();
      console.log("[MQTT] 当前重点: " + (priorityNode || "无"));
    }

    this.mqttClient = mqtt.createMqttClient({
      topics: ["dormmate/+/env", "dormmate/+/event", "dormmate/priority"],
      onStatus: function (state) {
        that.setData({ mqttState: state });
      },
      onMessage: function (topic, payload) {
        // 按 topic 分流：priority（全局单 topic）→ event → env
        if (topic === "dormmate/priority") {
          handlePriorityMessage(payload);
          return;
        }
        if (topic.split("/")[2] === "event") {
          handleEventMessage(topic, payload);
          return;
        }
        const nodeIdFromTopic = topic.split("/")[1]; // dormmate/{nodeId}/env
        let msg;
        try {
          msg = JSON.parse(payload);
        } catch (e) {
          console.log("[MQTT] 非法 JSON 忽略: " + topic + " " + payload);
          return;
        }
        // 防串线：消息 nodeId 必须与 topic 第二段一致（与 dashboard 校验链同策略）
        if (msg.nodeId !== nodeIdFromTopic) {
          console.log("[MQTT] 串线消息忽略: topic=" + nodeIdFromTopic + " payload.nodeId=" + msg.nodeId);
          return;
        }
        // 范围校验（SPEC §3.1），非法字段整条忽略
        const check = rules.validateInputs(msg.temperature, msg.humidity);
        if (check.messages.length > 0) {
          console.log("[MQTT] 字段非法忽略: " + topic + " " + payload);
          return;
        }
        const statusText = rules.computeStatus(check.temperature, check.humidity);
        latest[nodeIdFromTopic] = {
          nodeId: nodeIdFromTopic,
          temperature: check.temperature,
          humidity: check.humidity,
          status: statusText,
          statusClass: STATUS_CLASS[statusText] || "",
          time: String(msg.time || "")
        };
        renderNodes();
        console.log("[MQTT] " + nodeIdFromTopic + " " + check.temperature + "℃/" + check.humidity +
          "% → " + statusText + " (" + (msg.time || "") + ")");
      }
    });
    this.mqttClient.connect();
  },

  // A2：开启风扇（联动#1）——发布 actionState 到 dormmate/{nodeId}/action（MASTER_PLAN §6.1 契约），
  // simulator 收到后降温、Dashboard 进入"处理中"、3D 风扇转动；2 秒防抖避免连点重复发送
  onFanOn: function (e) {
    if (this.data.fanPending) return;
    const nodeId = e.currentTarget.dataset.node;
    const actionState = { nodeId: nodeId, action: "fan_on", actionTime: rules.formatTime(new Date()) };
    const ok = !!(this.mqttClient && this.mqttClient.publish("dormmate/" + nodeId + "/action", JSON.stringify(actionState)));
    this.setData({ fanPending: true });
    if (this.fanResetTimer) clearTimeout(this.fanResetTimer);
    this.fanResetTimer = setTimeout(function () {
      this.setData({ fanPending: false });
    }.bind(this), 2000);
    console.log("[MQTT] 已发布动作: " + JSON.stringify(actionState) + (ok ? "" : "（未连接，发送失败）"));
    wx.showToast({
      title: ok ? (nodeId + " 风扇指令已发送") : "MQTT 未连接，指令未发送",
      icon: "none"
    });
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
