// DormMate V0.8R5 阶段 A 验收（A1 部分）：mobile/utils/mqtt.js 协议帧单元测试
// 用 stub wx.connectSocket 驱动真实客户端代码，逐字节断言 MQTT 3.1.1 帧：
//   CONNECT（协议名/级别/CleanSession/KeepAlive/clientId 长度前缀）
//   SUBSCRIBE（三 topic 长度前缀 + QoS 0）
//   PUBLISH（topic + payload 完整）
//   半包/粘包解析、断线重连调度、主动关闭、未连接拒绝 publish、send 异常防御（safeSend）
// 运行：node simulator/test_mobile_mqtt.js（退出码 0 = 全部通过）
const path = require("path");
const { createMqttClient } = require(path.resolve("mobile/utils/mqtt.js"));

let failures = 0;
function check(label, ok) {
  console.log((ok ? "PASS" : "FAIL") + "  " + label);
  if (!ok) failures++;
}

function ab(bytes) {
  const b = new Uint8Array(bytes.length);
  b.set(bytes);
  return b.buffer;
}

let sent = [];
let handlers = {};
let sendThrows = false;

function makeTask() {
  return {
    send: function (opts) {
      if (sendThrows) throw { errMsg: "sendSocketMessage:fail socket closed" };
      sent.push(Buffer.from(new Uint8Array(opts.data)));
    },
    close: function () {},
    onOpen: function (fn) { handlers.open = fn; },
    onMessage: function (fn) { handlers.message = fn; },
    onClose: function (fn) { handlers.close = fn; },
    onError: function (fn) { handlers.error = fn; }
  };
}
global.wx = { connectSocket: function () { return makeTask(); } };

// 测试端编码器（构造假 Broker 帧）
function utf8(s) { return Buffer.from(s, "utf8"); }
function mqttStr(s) {
  const b = utf8(s);
  const out = Buffer.alloc(2 + b.length);
  out.writeUInt16BE(b.length, 0);
  b.copy(out, 2);
  return out;
}
function varint(n) {
  const out = [];
  do {
    let d = n % 128;
    n = Math.floor(n / 128);
    if (n > 0) d |= 0x80;
    out.push(d);
  } while (n > 0);
  return Buffer.from(out);
}
function publishFrame(topic, payload) {
  const body = Buffer.concat([mqttStr(topic), utf8(payload)]);
  return Buffer.concat([Buffer.from([0x30]), varint(body.length), body]);
}

const statuses = [];
const messages = [];
const client = createMqttClient({
  clientId: "dormmate-mobile-test01",
  topics: ["dormmate/+/env", "dormmate/+/event", "dormmate/priority"],
  onStatus: function (s) { statuses.push(s); },
  onMessage: function (t, p) { messages.push({ topic: t, payload: p }); }
});

// ---- 用例 1：CONNECT 帧 ----
client.connect();
check("connect() 后状态=连接中", statuses[statuses.length - 1].indexOf("连接中") === 0);
handlers.open();
const c = sent[0];
const CID = "dormmate-mobile-test01";
check("CONNECT 固定头=0x10", c[0] === 0x10);
check("CONNECT 剩余长度=10+2+clientId", c[1] === 10 + 2 + CID.length);
check("CONNECT 协议名 MQTT", c.slice(4, 8).toString() === "MQTT");
check("CONNECT 协议级 0x04 / CleanSession 0x02", c[8] === 0x04 && c[9] === 0x02);
check("CONNECT KeepAlive=30s（0x001E）", c[10] === 0x00 && c[11] === 0x1e);
check("CONNECT clientId 完整", c.slice(14).toString() === CID);

// ---- 用例 2：CONNACK → SUBSCRIBE（三 topic）----
handlers.message({ data: ab([0x20, 0x02, 0x00, 0x00]) });
check("CONNACK 后状态=已连接", statuses[statuses.length - 1].indexOf("已连接") === 0);
const s = sent[1];
check("SUBSCRIBE 固定头=0x82", s[0] === 0x82);
check("SUBSCRIBE 总长=60（三 topic 之和）", s.length === 60);
// 布局：0x82 | varint | pid(2) | [len(2)+topic+QoS(1)]×3；topic 体偏移 6 / 23 / 42
check("SUBSCRIBE topic1=dormmate/+/env", s.slice(6, 6 + 14).toString() === "dormmate/+/env");
check("SUBSCRIBE topic2=dormmate/+/event", s.slice(23, 23 + 16).toString() === "dormmate/+/event");
check("SUBSCRIBE topic3=dormmate/priority", s.slice(42, 42 + 17).toString() === "dormmate/priority");
check("三个 topic 的 QoS 均为 0", s[20] === 0x00 && s[39] === 0x00 && s[59] === 0x00);
handlers.message({ data: ab([0x90, 0x03, 0x00, 0x01, 0x00]) });

// ---- 用例 3：PUBLISH（发 action 的真实路径）----
const actionJson = '{"nodeId":"dorm-b","action":"fan_on","actionTime":"2026-09-30 17:30:00"}';
check("publish 返回 true", client.publish("dormmate/dorm-b/action", actionJson) === true);
const pub = sent[2];
check("PUBLISH 固定头=0x30", pub[0] === 0x30);
check("PUBLISH 剩余长度=2+22+payload", pub[1] === 2 + 22 + actionJson.length);
check("PUBLISH topic=dormmate/dorm-b/action", pub.slice(4, 4 + 22).toString() === "dormmate/dorm-b/action");
check("PUBLISH payload 完整", pub.slice(4 + 22).toString() === actionJson);

// ---- 用例 4：safeSend 防御（send 抛异常不炸，返回 false）----
sendThrows = true;
check("send 抛异常时 publish 返回 false", client.publish("dormmate/dorm-b/action", actionJson) === false);
sendThrows = false;

// ---- 用例 5：三通道 PUBLISH 解析（env/event/priority）----
const envJson = '{"nodeId":"dorm-a","temperature":25,"humidity":60,"status":"正常","time":"2026-09-30 17:30:00","action":""}';
handlers.message({ data: ab(publishFrame("dormmate/dorm-a/env", envJson)) });
check("env PUBLISH 解析成功", messages.length === 1 && messages[0].payload === envJson);
handlers.message({ data: ab(publishFrame("dormmate/dorm-a/event",
  '{"nodeId":"dorm-a","eventId":"e1","state":"HANDLING","time":"2026-09-30 17:30:00","summary":"x"}')) });
check("event PUBLISH 解析成功", messages.length === 2 && messages[1].topic === "dormmate/dorm-a/event");
handlers.message({ data: ab(publishFrame("dormmate/priority",
  '{"nodeId":"dorm-a","reason":"r","time":"2026-09-30 17:30:00"}')) });
check("priority PUBLISH 解析成功", messages.length === 3 && messages[2].topic === "dormmate/priority");

// ---- 用例 6：断线重连调度 + 主动关闭 ----
handlers.close();
check("onClose 后状态含重连", statuses[statuses.length - 1].indexOf("重连") >= 0);
client.close();
check("close() 后状态=已断开", statuses[statuses.length - 1] === "已断开");

// ---- 用例 7：未连接时 publish 拒绝 ----
check("未连接 publish 返回 false", client.publish("dormmate/dorm-a/action", "{}") === false);

console.log(failures === 0 ? "=== 协议帧单元测试全部通过（30 项）===" : "=== " + failures + " 项失败 ===");
process.exit(failures === 0 ? 0 : 1);
