// V0.8R5 阶段 A（A1）：微信小程序极简 MQTT 3.1.1 客户端（wx.connectSocket 承载）
// 背景：小程序环境没有现成 MQTT 库（mqtt.js 依赖浏览器 WebSocket 对象），故按 MQTT 3.1.1
// 规范手写最小子集，只实现本项目需要的报文：
//   CONNECT（Clean Session）/ SUBSCRIBE（QoS 0）/ PINGREQ（保活）/ PUBLISH（QoS 0，供 A2 动作按钮）
// 连接目标：本机 Mosquitto WebSocket（路径 /mqtt 与 dashboard 的 mqtt.js 默认一致）
// 设计原则（与 dashboard 同策略）：
//   消息 status 不信任——由页面用统一规则本地重算（rules.computeStatus）
//   断线自动重连（3 秒）——对应任务书 D4 加分项"自动重连"
// 说明：微信开发者工具需勾选"不校验合法域名"才能连 ws://127.0.0.1（任务书 V0.8R5 p15）

const DEFAULT_URL = "ws://127.0.0.1:8083/mqtt";
const DEFAULT_KEEPALIVE = 30; // 秒
const RECONNECT_DELAY_MS = 3000;

// ---------- MQTT 3.1.1 编解码 ----------

// UTF-8 编码（JS 字符串 → 字节数组；含代理对，中文按 3 字节）
function utf8Encode(str) {
  const bytes = [];
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i);
    if (c < 0x80) {
      bytes.push(c);
    } else if (c < 0x800) {
      bytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
    } else if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
      const c2 = str.charCodeAt(i + 1);
      if (c2 >= 0xdc00 && c2 <= 0xdfff) {
        const cp = 0x10000 + ((c - 0xd800) << 10) + (c2 - 0xdc00);
        bytes.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
        i++;
      } else {
        bytes.push(0xef, 0xbf, 0xbd); // 孤立高代理 → U+FFFD
      }
    } else {
      bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
    }
  }
  return new Uint8Array(bytes);
}

// UTF-8 解码（字节数组区间 → 字符串；异常字节输出替换符并跳过，防死循环）
function utf8Decode(bytes, start, end) {
  let out = "";
  let i = start;
  while (i < end) {
    const b0 = bytes[i];
    if (b0 < 0x80) {
      out += String.fromCharCode(b0);
      i += 1;
    } else if ((b0 & 0xe0) === 0xc0 && i + 1 < end) {
      out += String.fromCharCode(((b0 & 0x1f) << 6) | (bytes[i + 1] & 0x3f));
      i += 2;
    } else if ((b0 & 0xf0) === 0xe0 && i + 2 < end) {
      out += String.fromCharCode(((b0 & 0x0f) << 12) | ((bytes[i + 1] & 0x3f) << 6) | (bytes[i + 2] & 0x3f));
      i += 3;
    } else if ((b0 & 0xf8) === 0xf0 && i + 3 < end) {
      const cp = ((b0 & 0x07) << 18) | ((bytes[i + 1] & 0x3f) << 12) | ((bytes[i + 2] & 0x3f) << 6) | (bytes[i + 3] & 0x3f);
      out += String.fromCharCode(0xd800 + ((cp - 0x10000) >> 10), 0xdc00 + ((cp - 0x10000) & 0x3ff));
      i += 4;
    } else {
      out += "�";
      i += 1;
    }
  }
  return out;
}

// 剩余长度（Remaining Length）变长编码：≤4 字节，每字节低 7 位有效，最高位=还有后续
function encodeRemainingLength(value) {
  const out = [];
  do {
    let digit = value % 128;
    value = Math.floor(value / 128);
    if (value > 0) digit |= 0x80;
    out.push(digit);
  } while (value > 0);
  return out;
}

function decodeRemainingLength(bytes, offset) {
  let multiplier = 1;
  let value = 0;
  let count = 0;
  while (count < 4 && offset + count < bytes.length) {
    const digit = bytes[offset + count];
    value += (digit & 0x7f) * multiplier;
    count++;
    if ((digit & 0x80) === 0) break;
    multiplier *= 128;
  }
  return { value: value, count: count };
}

// MQTT 字符串 = 2 字节大端长度前缀 + UTF-8 字节
function encodeMqttString(str) {
  const body = utf8Encode(str);
  const out = new Uint8Array(2 + body.length);
  out[0] = (body.length >> 8) & 0xff;
  out[1] = body.length & 0xff;
  out.set(body, 2);
  return out;
}

function concatBytes(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

// 报文 = 固定头（类型字节 + 剩余长度变长编码）+ 报文体
function buildPacket(type, body) {
  const header = encodeRemainingLength(body.length);
  const out = new Uint8Array(1 + header.length + body.length);
  out[0] = type;
  out.set(header, 1);
  out.set(body, 1 + header.length);
  return out;
}

// CONNECT（MQTT 3.1.1）：协议名 "MQTT" + 协议级 0x04 + Clean Session + KeepAlive + ClientId
function buildConnectPacket(clientId, keepaliveSeconds) {
  const variable = new Uint8Array(10);
  variable[0] = 0x00; variable[1] = 0x04;              // Protocol Name Length
  variable[2] = 0x4d; variable[3] = 0x51; variable[4] = 0x54; variable[5] = 0x54; // "MQTT"
  variable[6] = 0x04;                                  // Protocol Level = 3.1.1
  variable[7] = 0x02;                                  // Connect Flags: Clean Session
  variable[8] = (keepaliveSeconds >> 8) & 0xff;        // Keep Alive（秒，2 字节大端）
  variable[9] = keepaliveSeconds & 0xff;
  return buildPacket(0x10, concatBytes(variable, encodeMqttString(clientId)));
}

// SUBSCRIBE：PacketId + 每个 topic（长度前缀 + QoS 0）
function buildSubscribePacket(packetId, topics) {
  const parts = [];
  topics.forEach(function (t) {
    parts.push(encodeMqttString(t));
    parts.push(new Uint8Array([0x00]));
  });
  let bodyLength = 2;
  parts.forEach(function (p) { bodyLength += p.length; });
  const body = new Uint8Array(bodyLength);
  body[0] = (packetId >> 8) & 0xff;
  body[1] = packetId & 0xff;
  let offset = 2;
  parts.forEach(function (p) { body.set(p, offset); offset += p.length; });
  return buildPacket(0x82, body);
}

// PUBLISH（QoS 0，无 PacketId）：topic（长度前缀）+ payload 原文
function buildPublishPacket(topic, payload) {
  return buildPacket(0x30, concatBytes(encodeMqttString(topic), utf8Encode(payload)));
}

const PINGREQ_PACKET = new Uint8Array([0xc0, 0x00]);

// ---------- 客户端 ----------

function createMqttClient(options) {
  options = options || {};
  const url = options.url || DEFAULT_URL;
  const keepaliveSeconds = options.keepaliveSeconds || DEFAULT_KEEPALIVE;
  const topics = options.topics || ["dormmate/+/env"];
  const clientId = options.clientId || ("dormmate-mobile-" + Math.random().toString(16).slice(2, 10));
  const onStatus = options.onStatus || function () {};
  const onMessage = options.onMessage || function () {};

  let socketTask = null;
  let status = "未连接";
  let packetId = 0;
  let pingTimer = null;
  let reconnectTimer = null;
  let closedByUser = false;
  let buffer = new Uint8Array(0); // 跨 WebSocket 消息的字节缓存（一个消息可能含多个/半个报文）

  function setStatus(text) {
    status = text;
    onStatus(text);
  }

  function nextPacketId() {
    packetId = (packetId % 65535) + 1;
    return packetId;
  }

  // 防御：socket 半关闭/重连窗口内 wx send 可能同步抛错，统一转成受控日志，不产生红色报错
  function safeSend(task, data) {
    try {
      task.send({ data: data });
      return true;
    } catch (err) {
      console.log("[MQTT] send 失败（socket 可能已关闭）: " + (err && err.errMsg ? err.errMsg : String(err)));
      return false;
    }
  }

  function startPing() {
    stopPing();
    pingTimer = setInterval(function () {
      if (socketTask) safeSend(socketTask, PINGREQ_PACKET.buffer);
    }, keepaliveSeconds * 1000);
  }

  function stopPing() {
    if (pingTimer) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  function scheduleReconnect(reason) {
    if (closedByUser) return;
    stopPing();
    setStatus(reason + "，3 秒后重连…");
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(function () { connect(); }, RECONNECT_DELAY_MS);
  }

  function handlePublish(packet) {
    const qos = (packet[0] >> 1) & 0x03;
    let offset = 1;
    const rl = decodeRemainingLength(packet, offset);
    offset += rl.count;
    const topicLength = (packet[offset] << 8) | packet[offset + 1];
    offset += 2;
    const topic = utf8Decode(packet, offset, offset + topicLength);
    offset += topicLength;
    if (qos > 0) offset += 2; // Packet Identifier（QoS 0 无此字段）
    onMessage(topic, utf8Decode(packet, offset, packet.length));
  }

  function handlePacket(packet) {
    const type = packet[0] >> 4;
    if (type === 0x02) { // CONNACK（0x20）
      if (packet[3] !== 0) {
        console.log("[MQTT] CONNACK 拒绝，返回码 " + packet[3]);
        return;
      }
      console.log("[MQTT] CONNACK ok → 发送 SUBSCRIBE " + topics.join(", "));
      setStatus("已连接（MQTT）");
      socketTask.send({ data: buildSubscribePacket(nextPacketId(), topics).buffer });
      startPing();
    } else if (type === 0x09) { // SUBACK（0x90）
      console.log("[MQTT] SUBACK 已确认");
    } else if (type === 0x03) { // PUBLISH（0x30）
      handlePublish(packet);
    } else if (type === 0x0d) { // PINGRESP（0xD0）保活应答，无需处理
      // noop
    } else {
      console.log("[MQTT] 忽略未知报文类型 0x" + type.toString(16));
    }
  }

  function feedBytes(bytes) {
    buffer = concatBytes(buffer, bytes);
    let offset = 0;
    while (buffer.length - offset >= 2) {
      const rl = decodeRemainingLength(buffer, offset + 1);
      const total = 1 + rl.count + rl.value;
      if (buffer.length - offset < total) break; // 报文不完整，等下一段
      handlePacket(buffer.slice(offset, offset + total));
      offset += total;
    }
    buffer = buffer.slice(offset);
  }

  function connect() {
    if (closedByUser) return;
    setStatus("连接中…");
    console.log("[MQTT] 连接 " + url);
    socketTask = wx.connectSocket({
      url: url,
      protocols: ["mqtt"],
      fail: function (err) {
        console.log("[MQTT] connectSocket 失败", err);
        scheduleReconnect("连接失败");
      }
    });
    socketTask.onOpen(function () {
      console.log("[MQTT] WebSocket 已打开 → 发送 CONNECT（clientId=" + clientId + ", keepalive=" + keepaliveSeconds + "s）");
      socketTask.send({ data: buildConnectPacket(clientId, keepaliveSeconds).buffer });
    });
    socketTask.onMessage(function (res) {
      feedBytes(new Uint8Array(res.data));
    });
    socketTask.onClose(function () {
      console.log("[MQTT] WebSocket 关闭");
      scheduleReconnect("连接断开");
    });
    socketTask.onError(function (err) {
      console.log("[MQTT] WebSocket 错误", err);
      scheduleReconnect("连接异常");
    });
  }

  function close() {
    closedByUser = true;
    stopPing();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (socketTask) {
      try { socketTask.close({}); } catch (e) { /* 已关闭则忽略 */ }
      socketTask = null;
    }
    setStatus("已断开");
  }

  function publish(topic, payload) {
    if (!socketTask || status !== "已连接（MQTT）") {
      console.log("[MQTT] 未连接，忽略 publish " + topic);
      return false;
    }
    return safeSend(socketTask, buildPublishPacket(topic, payload).buffer);
  }

  return {
    connect: connect,
    close: close,
    publish: publish,
    getStatus: function () { return status; }
  };
}

module.exports = {
  createMqttClient: createMqttClient,
  DEFAULT_URL: DEFAULT_URL
};
