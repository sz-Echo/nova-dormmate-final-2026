// DormMate A 组 priority.js —— A1 优先关注纯函数（零 DOM；dashboard/app.js 与 test-priority.html 共用）
// 规则（SPEC §9 A1 / MASTER_PLAN §6.4，顺序不可改，程序计算禁人工）：
//   ① 连续异常时长（按 time 分组：最新记录 time − 异常链起点 time，单位分钟）降序
//   ② 相同时比异常次数（该节点历史中 status != 正常的条数，demo 记录除外）降序
//   ③ 仍相同按 nodeId 固定顺序 dorm-a → dorm-b → dorm-c
// demo 标记（M6 遗留修复）：演示按钮产生的记录带 demo:true，不参与计算；
//   three3d 演示记录同样带 demo 标记，与真实 MQTT 数据隔离。

const PRIORITY_NODE_ORDER = ["dorm-a", "dorm-b", "dorm-c"];

function parseRecordTime(str) {
  // "YYYY-MM-DD HH:MM:SS" -> 毫秒时间戳（本地时区；与全项目 time 格式一致）
  return new Date(str.replace(" ", "T")).getTime();
}

function computeStreak(history) {
  // 从最新往回走连续 status != 正常的链（A1 连续异常时长）。
  // 返回 { statusType, startTime, endTime, durationMinutes, streakCount, abnormalCount }
  // 或 null（历史为空 / 最新一条为正常 / 全部为 demo 记录）。
  if (!Array.isArray(history)) return null;
  const rows = history.filter(function (r) { return r && !r.demo; });
  if (rows.length === 0) return null;
  const abnormalCount = rows.reduce(function (n, r) { return n + (r.status !== "正常" ? 1 : 0); }, 0);
  const last = rows[rows.length - 1];
  if (last.status === "正常") return null;
  const statusType = last.status;
  let start = last;
  for (let i = rows.length - 2; i >= 0; i--) {
    if (rows[i].status !== "正常") { start = rows[i]; } else { break; }
  }
  const endMs = parseRecordTime(last.time);
  const startMs = parseRecordTime(start.time);
  // 时间戳解析失败的防御：按 0 分钟处理，避免 NaN 污染排序（Dashboard 主路径有 TIME_PATTERN 校验，此处为纯函数自防御）
  const valid = !isNaN(endMs) && !isNaN(startMs) && endMs >= startMs;
  const durationMinutes = valid ? Math.max(0, Math.round((endMs - startMs) / 6000) / 10) : 0;   // 分钟，保留 1 位小数
  return {
    statusType: statusType,
    startTime: start.time,
    endTime: last.time,
    durationMinutes: durationMinutes,
    streakCount: rows.length - rows.indexOf(start),   // 当前异常链内的记录条数
    abnormalCount: abnormalCount                      // 该节点历史中异常总条数（② 次数的口径）
  };
}

function computePriority(nodes) {
  // nodes: { nodeId: { history: [...] } }
  // 返回 { nodeId|null, reason, details }；reason 为程序拼接的可解释原因（截图 A1 例句口径）。
  const details = PRIORITY_NODE_ORDER.map(function (id) {
    const node = nodes[id];
    const streak = node ? computeStreak(node.history) : null;
    return {
      nodeId: id,
      status: streak ? streak.statusType : "正常",
      durationMinutes: streak ? streak.durationMinutes : 0,
      abnormalCount: streak ? streak.abnormalCount : 0,
      source: streak ? (streak.startTime + " ~ " + streak.endTime + " 连续异常 " + streak.streakCount + " 条") : ""
    };
  });
  const abnormal = details.filter(function (d) { return d.status !== "正常"; });
  if (abnormal.length === 0) {
    return { nodeId: null, reason: "当前 3 个宿舍均正常，无需优先关注", details: details };
  }
  abnormal.sort(function (a, b) {
    if (b.durationMinutes !== a.durationMinutes) { return b.durationMinutes - a.durationMinutes; }   // ① 时长降序
    if (b.abnormalCount !== a.abnormalCount) { return b.abnormalCount - a.abnormalCount; }           // ② 次数降序
    return PRIORITY_NODE_ORDER.indexOf(a.nodeId) - PRIORITY_NODE_ORDER.indexOf(b.nodeId);             // ③ nodeId 顺序
  });
  const winner = abnormal[0];
  const parts = ["优先关注 " + winner.nodeId + "：已连续" + winner.status + " " + winner.durationMinutes + " 分钟"];
  abnormal.slice(1).forEach(function (d) {
    parts.push(d.nodeId + " 虽然" + d.status + "，但只持续 " + d.durationMinutes + " 分钟");
  });
  const normal = details.filter(function (d) { return d.status === "正常"; });
  if (normal.length > 0) {
    parts.push(normal.map(function (d) { return d.nodeId; }).join("、") + " 当前正常");
  }
  return { nodeId: winner.nodeId, reason: parts.join("；") + "。", details: details };
}

function computeWinnerPhrase(nodes) {
  // B2 依据短语（SPEC §9 B2 / MASTER_PLAN §6.5）：返回 { nodeId, phrase } 或 null（无异常）。
  // 短语按实际命中规则程序选择：持续异常时间更长 / 异常次数更多 / 按节点顺序优先 / 是唯一异常节点。
  // buildOverview（B1）与 Dashboard 依据卡片（B2）共用本函数，避免两处口径漂移。
  const result = computePriority(nodes);
  if (!result.nodeId) return null;
  const winner = result.details.filter(function (d) { return d.nodeId === result.nodeId; })[0];
  const others = result.details.filter(function (d) {
    return d.nodeId !== result.nodeId && d.status !== "正常";
  });
  if (others.length === 0) { return { nodeId: result.nodeId, phrase: "是唯一异常节点" }; }
  let maxOtherDur = -1;
  let maxOtherCount = -1;
  others.forEach(function (d) {
    if (d.durationMinutes > maxOtherDur) { maxOtherDur = d.durationMinutes; }
    if (d.abnormalCount > maxOtherCount) { maxOtherCount = d.abnormalCount; }
  });
  if (winner.durationMinutes > maxOtherDur) { return { nodeId: result.nodeId, phrase: "持续异常时间更长" }; }
  if (winner.abnormalCount > maxOtherCount) { return { nodeId: result.nodeId, phrase: "异常次数更多" }; }
  return { nodeId: result.nodeId, phrase: "按节点顺序优先" };
}

function buildOverview(nodes) {
  // B1 当前总览（SPEC §9 B1 / MASTER_PLAN §6.5）：程序模板拼接，禁写死；
  // 输出如"当前 3 个宿舍中，1 个正常，2 个需要关注；dorm-b 持续异常时间更长，是当前重点，dorm-c 出现偏湿。"
  // 节点/状态/重点全部来自真实数据；重点依据短语复用 computeWinnerPhrase（与 B2 同源）。
  const details = PRIORITY_NODE_ORDER.map(function (id) {
    const node = nodes[id];
    const streak = node ? computeStreak(node.history) : null;
    return {
      nodeId: id,
      status: streak ? streak.statusType : "正常",
      durationMinutes: streak ? streak.durationMinutes : 0,
      abnormalCount: streak ? streak.abnormalCount : 0
    };
  });
  const abnormal = details.filter(function (d) { return d.status !== "正常"; });
  const normalCount = details.length - abnormal.length;
  let text = "当前 3 个宿舍中，" + normalCount + " 个正常，" + abnormal.length + " 个需要关注";
  if (abnormal.length > 0) {
    const winnerPhrase = computeWinnerPhrase(nodes);   // 复用 A1 排序与依据判定，零重写
    const winner = abnormal.filter(function (d) { return d.nodeId === winnerPhrase.nodeId; })[0];
    if (abnormal.length > 1) {
      text += "；" + winner.nodeId + " " + winnerPhrase.phrase + "，是当前重点";
      abnormal.forEach(function (d) {
        if (d.nodeId !== winner.nodeId) { text += "，" + d.nodeId + " 出现" + d.status; }
      });
    } else {
      text += "；" + winner.nodeId + " 出现" + winner.status + "，是当前重点";
    }
  }
  return text + "。";
}

window.computeStreak = computeStreak;
window.computePriority = computePriority;
window.computeWinnerPhrase = computeWinnerPhrase;
window.buildOverview = buildOverview;
