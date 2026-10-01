// DormMate V0.8R5 演示 PPT 生成器（pptxgenjs）
// 运行：node docs/V08R5_Plans/gen_ppt.js → docs/V08R5_Plans/DormMate_V08R5_PPT.pptx
// 任务书 p20-21 十二项内容 + 封面/收尾 = 14 页（10-15 页内）
const pptxgen = require("pptxgenjs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");
const IMG = (p) => path.join(ROOT, p);

// 配色：深蓝主色 + 项目状态四色点缀（偏冷蓝/偏热橙/偏湿青/正常绿）
const NAVY = "1E2761";
const INK = "2B3A48";
const MUTE = "6B7A8D";
const PAPER = "FFFFFF";
const CARD = "F4F6FA";
const COLD = "2E6BA8", HOT = "C97A1B", WET = "16808C", OK = "27905E";
const FONT = "Microsoft YaHei";

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";   // 13.33 x 7.5
p.defineLayout({ name: "W", width: 13.33, height: 7.5 });
p.layout = "W";

const W = 13.33, H = 7.5;

function header(s, title, kicker) {
  s.background = { color: PAPER };
  s.addText(kicker, { x: 0.7, y: 0.42, w: 6, h: 0.3, fontSize: 11, color: MUTE, fontFace: FONT, charSpacing: 2 });
  s.addText(title, { x: 0.7, y: 0.72, w: 11.9, h: 0.75, fontSize: 32, bold: true, color: NAVY, fontFace: FONT, margin: 0 });
}

function card(s, x, y, w, h, color) {
  s.addShape("roundRect", { x, y, w, h, rectRadius: 0.08, fill: { color: CARD }, line: { color: "E3E8F0", width: 1 } });
}

function stateDots(s, x, y) {
  const dots = [[OK, "正常"], [COLD, "偏冷"], [HOT, "偏热"], [WET, "偏湿"]];
  dots.forEach(([c, label], i) => {
    const dx = x + i * 1.35;
    s.addShape("ellipse", { x: dx, y, w: 0.32, h: 0.32, fill: { color: c }, line: { color: "FFFFFF", width: 1.5 } });
    s.addText(label, { x: dx - 0.3, y: y + 0.4, w: 1.0, h: 0.3, fontSize: 11, color: MUTE, fontFace: FONT, align: "center", margin: 0 });
  });
}

// ---------- 1 封面（深色） ----------
{
  const s = p.addSlide();
  s.background = { color: NAVY };
  stateDots(s, 1.05, 1.05);
  s.addText("DormMate", { x: 0.9, y: 2.1, w: 11.5, h: 1.3, fontSize: 66, bold: true, color: PAPER, fontFace: FONT, margin: 0 });
  s.addText("宿舍环境助手 —— 一个系统 · 两条数据链 · 多端协同 · 事件闭环", {
    x: 0.95, y: 3.55, w: 11.5, h: 0.6, fontSize: 21, color: "CADCFC", fontFace: FONT, margin: 0 });
  s.addText("V0.8R5 综合作品｜D1-D5 场景 + E1-E3 技术增强", {
    x: 0.95, y: 4.35, w: 11.5, h: 0.4, fontSize: 14, color: "8FA3C8", fontFace: FONT, margin: 0 });
  s.addNotes("开场：一句话讲清作品是什么——一个系统、两条数据链、多端协同、事件闭环。四个状态色点对应统一规则的四状态。");
}

// ---------- 2 问题与目标（浅色，2x2 四问卡片） ----------
{
  const s = p.addSlide();
  header(s, "问题与目标：四个连续的问题", "01 · 为什么做");
  const items = [
    ["现在该看谁？", "三间宿舍同时出现异常时，需要一个可解释、可重复、换数据就变的优先级判断（D2 优先关注）。"],
    ["怎么处理？", "发现异常后要能执行处理动作，并让动作成为系统状态的一部分（D3 开启风扇/通风）。"],
    ["处理完怎么验证？", "恢复不能由人点按钮决定，必须由后续新数据触发并自动判定（D3 恢复规则）。"],
    ["事后怎么复盘？", "完整事件记录 + 历史报告，回看谁出了问题、做了什么、结果如何（A4 事件复盘 + 报告）。"],
  ];
  const positions = [[0.7, 1.75], [6.9, 1.75], [0.7, 4.15], [6.9, 4.15]];
  items.forEach(([t, d], i) => {
    const [x, y] = positions[i];
    card(s, x, y, 5.7, 2.1, CARD);
    s.addText(String(i + 1), { x: x + 0.35, y: y + 0.3, w: 0.7, h: 0.65, fontSize: 34, bold: true, color: NAVY, fontFace: FONT, margin: 0 });
    s.addText(t, { x: x + 1.15, y: y + 0.38, w: 4.3, h: 0.45, fontSize: 19, bold: true, color: INK, fontFace: FONT, margin: 0 });
    s.addText(d, { x: x + 0.35, y: y + 1.0, w: 5.0, h: 0.95, fontSize: 13, color: MUTE, fontFace: FONT, margin: 0, valign: "top" });
  });
  s.addNotes("四个问题引出四个能力：优先关注 / 处理动作 / 恢复判断 / 事件复盘。强调'恢复必须由新数据触发'是任务书 D3 的硬约束。");
}

// ---------- 3 最终产品形态（三端截图） ----------
{
  const s = p.addSlide();
  header(s, "最终产品形态：三端围绕同一套实时状态", "02 · 产品");
  s.addImage({ path: IMG("Evidence/D1/d1-three-nodes-online.png"), x: 0.7, y: 1.7, w: 7.4, h: 4.16, rounding: true });
  s.addText("Dashboard 实时看板", { x: 0.7, y: 6.0, w: 7.4, h: 0.35, fontSize: 13, bold: true, color: INK, fontFace: FONT, align: "center", margin: 0 });
  s.addImage({ path: IMG("Evidence/E3/e3-mobile-dashboard-sync.png"), x: 8.4, y: 1.7, w: 2.1, h: 3.7, rounding: true });
  s.addText("移动端快查", { x: 8.4, y: 5.5, w: 2.1, h: 0.35, fontSize: 12, bold: true, color: INK, fontFace: FONT, align: "center", margin: 0 });
  s.addImage({ path: IMG("Evidence/E1/e1-priority-halo-b.png"), x: 10.75, y: 1.7, w: 1.85, h: 3.7, rounding: true });
  s.addText("3D 数字孪生", { x: 10.75, y: 5.5, w: 1.85, h: 0.35, fontSize: 12, bold: true, color: INK, fontFace: FONT, align: "center", margin: 0 });
  s.addText("三端订阅同一 MQTT 数据流：数值一致、状态一致、事件一致", {
    x: 8.4, y: 6.1, w: 4.2, h: 0.55, fontSize: 12.5, color: NAVY, fontFace: FONT, bold: true, align: "center", margin: 0 });
  s.addNotes("产品形态：Dashboard 盯屏总览、移动端随身快查快操作、3D 空间定位。强调三端一致性来自共享数据源（MQTT），不是各自维护。");
}

// ---------- 4 系统架构与两条数据链 ----------
{
  const s = p.addSlide();
  header(s, "系统架构：一个系统、两条数据链", "03 · 架构");
  s.addImage({ path: IMG("docs/V08R5_Plans/diagram-architecture.png"), x: 0.75, y: 1.65, w: 11.85, h: 5.3 });
  s.addNotes("架构图讲三条：离线链（CSV 即存储、无数据库）、实时链（MQTT 三端订阅）、统一防线（串线校验/本地重算/坏 JSON 拦截）。技术边界：无数据库、无真实传感器、无 LLM、无正式 ML 训练。");
}

// ---------- 5 多端信息分工 ----------
{
  const s = p.addSlide();
  header(s, "多端协同：分工而不是复制", "04 · 协同方式");
  const rows = [
    [OK, "Dashboard", "当前重点（总览条 / 优先横幅 / 依据卡片 / 处理状态）", "实时数据在此汇聚，盯屏时一眼看到'现在最该看谁'"],
    [COLD, "移动端", "快查快操作（三节点状态 / 重点标识 / 事件徽标 / 开风扇）", "随身场景快速定位，不复制 Dashboard 图表"],
    [HOT, "3D", "空间状态（楼色 / 粒子 / 风扇 / 窗 / 光环 / 徽标 / 回放）", "空间位置用空间表达，哪个宿舍异常一眼定位"],
    [WET, "TTS 语音", "只读当前提醒（'朗读状态'读选中节点最新记录）", "语音适合短提醒，不适合长数据；听一句即可决策"],
    [NAVY, "report.html", "历史复盘（摘要 / 事件复盘 / ML 异常分析）", "复盘要完整记录，静态报告可回看、可归档"],
  ];
  rows.forEach(([c, name, task, why], i) => {
    const y = 1.7 + i * 1.08;
    card(s, 0.7, y, 11.9, 0.92, CARD);
    s.addShape("ellipse", { x: 1.0, y: y + 0.24, w: 0.44, h: 0.44, fill: { color: c } });
    s.addText(name, { x: 1.7, y: y + 0.2, w: 2.2, h: 0.5, fontSize: 16, bold: true, color: INK, fontFace: FONT, margin: 0, valign: "middle" });
    s.addText(task, { x: 3.9, y: y + 0.14, w: 5.6, h: 0.66, fontSize: 13, color: INK, fontFace: FONT, margin: 0, valign: "middle" });
    s.addText(why, { x: 9.6, y: y + 0.14, w: 2.85, h: 0.66, fontSize: 11.5, color: MUTE, fontFace: FONT, margin: 0, valign: "middle" });
  });
  s.addNotes("分工表（任务书 p16）：各入口承担不同信息任务——多端协同是多端互补，不是多端重复。");
}

// ---------- 6 D1-D2 ----------
{
  const s = p.addSlide();
  header(s, "D1 多节点稳定运行 · D2 优先关注", "05 · 场景");
  card(s, 0.7, 1.7, 5.7, 5.1, CARD);
  s.addText("D1 三节点稳定运行", { x: 1.0, y: 2.0, w: 5.1, h: 0.5, fontSize: 19, bold: true, color: INK, fontFace: FONT, margin: 0 });
  s.addText([
    { text: "dorm-a/b/c 三节点同时在线，topic↔nodeId 双校验防串线", options: { bullet: true, breakLine: true } },
    { text: "status 一律本地规则重算，不信任消息值", options: { bullet: true, breakLine: true } },
    { text: "坏 JSON / 缺字段 / 超范围拦截告警，Broker 重启自动重连", options: { bullet: true, breakLine: true } },
    { text: "新消息到达，Dashboard / 3D / 移动端同时更新", options: { bullet: true } },
  ], { x: 1.0, y: 2.65, w: 5.1, h: 2.1, fontSize: 13.5, color: INK, fontFace: FONT, paraSpaceAfter: 10 });
  s.addImage({ path: IMG("Evidence/D1/d1-three-nodes-online.png"), x: 1.15, y: 4.85, w: 4.9, h: 1.75, rounding: true });

  card(s, 6.9, 1.7, 5.7, 5.1, CARD);
  s.addText("D2 持续异常与优先关注", { x: 7.2, y: 2.0, w: 5.1, h: 0.5, fontSize: 19, bold: true, color: INK, fontFace: FONT, margin: 0 });
  s.addText([
    { text: "规则：连续异常时长 → 异常次数 → nodeId 顺序（三条兜底链）", options: { bullet: true, breakLine: true } },
    { text: "可解释：横幅直接给出理由（'已连续偏热 20 分钟'）", options: { bullet: true, breakLine: true } },
    { text: "换数据即变：三组不同数据验证优先级随数据变化，不写死节点", options: { bullet: true, breakLine: true } },
    { text: "经 dormmate/priority 广播，3D 光环与移动端标识跟随", options: { bullet: true } },
  ], { x: 7.2, y: 2.65, w: 5.1, h: 2.1, fontSize: 13.5, color: INK, fontFace: FONT, paraSpaceAfter: 10 });
  s.addImage({ path: IMG("Evidence/D2/d2-priority-group1.png"), x: 7.45, y: 4.85, w: 4.9, h: 1.75, rounding: true });
  s.addNotes("D1 讲稳定与防串线；D2 讲'现在先看谁'的程序化规则——时长回答'已经难受多久'，次数回答'反复异常'，nodeId 顺序是确定性兜底。");
}

// ---------- 7 D3-D5 ----------
{
  const s = p.addSlide();
  header(s, "D3 事件闭环 · D4 故障修复 · D5 Rule/ML 对照", "05 · 场景");
  const cols = [
    ["D3 处理→验证→恢复", [
      "异常发现 → 建事件草稿（OPEN）",
      "开启风扇 → 处理中（HANDLING）",
      "连续 ≥2 条正常新数据 → 已恢复（RECOVERED）",
      "恢复仅由新数据触发，按钮不能改",
      "事件 ≥9 字段，三端共用同一 eventId",
    ], HOT],
    ["D4 实时链路故障与修复", [
      "坏 JSON → 拦截告警 + 丢弃计数，页面不受影响",
      "串线消息（topic 与 nodeId 不符）→ 丢弃",
      "Broker 停止 → 各端自动重连",
      "修复后重发 → 立即恢复更新",
      "视频 S7 幕保留完整故障修复过程",
    ], COLD],
    ["D5 固定规则与 ML 对照", [
      "IsolationForest 与固定规则双判断并排",
      "8 组新数据对照，差异行高亮",
      "诚实保留 1 个不理想案例（27.5℃/70%）",
      "模型只是辅助，与规则并列保留",
      "不做 Label/准确率/调参（任务边界）",
    ], WET],
  ];
  cols.forEach(([t, items, c], i) => {
    const x = 0.7 + i * 4.1;
    card(s, x, 1.7, 3.8, 5.1, CARD);
    s.addShape("ellipse", { x: x + 0.3, y: 2.0, w: 0.4, h: 0.4, fill: { color: c } });
    s.addText(t, { x: x + 0.85, y: 1.95, w: 2.9, h: 0.5, fontSize: 16.5, bold: true, color: INK, fontFace: FONT, margin: 0, valign: "middle" });
    s.addText(items.map((it) => ({ text: it, options: { bullet: true, breakLine: true } })),
      { x: x + 0.3, y: 2.7, w: 3.2, h: 3.9, fontSize: 12.5, color: INK, fontFace: FONT, paraSpaceAfter: 8, valign: "top" });
  });
  s.addNotes("D3 是核心场景：事件生命周期三态 + 恢复硬约束。D4 讲工程健壮性。D5 讲 Rule 与 ML 并列、诚实保留不理想案例。");
}

// ---------- 8 E1-E3 ----------
{
  const s = p.addSlide();
  header(s, "E1 3D 数字孪生 · E2 语音交互 · E3 移动端同步", "06 · 技术增强");
  const cols = [
    ["E1 3D 增强（7 条最低线全勾）", "优先光环 · 事件徽标 · 镜头聚焦 · 事件回放", "Evidence/E1/e1-priority-halo-b.png"],
    ["E2 Camera/ASR/TTS（6 条全勾）", "5 条语音指令 · 快照叠加节点/时间/状态并关联事件", "Evidence/E2/e2-snapshot-real.png"],
    ["E3 web-移动端同步（6 条全勾）", "同一 MQTT 数据流 · 共享事件状态 · 移动开风扇联动", "Evidence/E3/e3-mobile-dashboard-sync.png"],
  ];
  cols.forEach(([t, d, img], i) => {
    const x = 0.7 + i * 4.1;
    card(s, x, 1.7, 3.8, 5.1, CARD);
    s.addImage({ path: IMG(img), x: x + 0.35, y: 2.0, w: 3.1, h: 2.5, rounding: true });
    s.addText(t, { x: x + 0.3, y: 4.7, w: 3.2, h: 0.75, fontSize: 15.5, bold: true, color: INK, fontFace: FONT, margin: 0 });
    s.addText(d, { x: x + 0.3, y: 5.5, w: 3.2, h: 1.1, fontSize: 12, color: MUTE, fontFace: FONT, margin: 0, valign: "top" });
  });
  s.addNotes("三个共同技术增强：E1 用 3D 表达空间与事件、E2 用语音与快照增强交互、E3 让移动端与 web 实时同步（共享数据源驱动）。");
}

// ---------- 9 事件生命周期 ----------
{
  const s = p.addSlide();
  header(s, "事件生命周期：OPEN → HANDLING → RECOVERED", "07 · 核心机制");
  s.addImage({ path: IMG("docs/V08R5_Plans/diagram-event-state.png"), x: 0.75, y: 1.7, w: 11.85, h: 5.35 });
  s.addNotes("状态机唯一持有者是 Dashboard；恢复仅由新数据触发；同一 eventId 贯穿三态，3D 与移动端订阅广播渲染，不各自维护。");
}

// ---------- 10 真实故障与修复 ----------
{
  const s = p.addSlide();
  header(s, "一次真实故障与修复：坏 JSON 拦截", "08 · 故障");
  card(s, 0.7, 1.75, 5.6, 4.9, CARD);
  s.addText("故障注入与修复过程", { x: 1.0, y: 2.05, w: 5.0, h: 0.5, fontSize: 18, bold: true, color: INK, fontFace: FONT, margin: 0 });
  s.addText([
    { text: "向 dormmate/dorm-b/env 发布故意破坏的 JSON：{bad json", options: { bullet: true, breakLine: true } },
    { text: "Dashboard 校验链 JSON.parse 失败 → 告警横幅 + 丢弃计数 +1", options: { bullet: true, breakLine: true } },
    { text: "页面不受影响，其他节点继续正常更新", options: { bullet: true, breakLine: true } },
    { text: "修复：重发合法消息 → 立即恢复更新", options: { bullet: true, breakLine: true } },
    { text: "同类防线：串线拦截 / 缺字段 / 超范围 / Broker 停自动重连", options: { bullet: true } },
  ], { x: 1.0, y: 2.65, w: 5.0, h: 3.6, fontSize: 13.5, color: INK, fontFace: FONT, paraSpaceAfter: 11 });
  s.addImage({ path: IMG("Evidence/D4/d4-badjson-warning.png"), x: 6.75, y: 2.1, w: 5.85, h: 0.55 });
  s.addText("告警横幅：消息不是合法 JSON：{bad json", { x: 6.75, y: 2.85, w: 5.85, h: 0.35, fontSize: 11.5, color: MUTE, fontFace: FONT, align: "center", margin: 0 });
  s.addImage({ path: IMG("Evidence/D4/d4-drop-count.png"), x: 7.6, y: 3.4, w: 2.2, h: 0.5 });
  s.addImage({ path: IMG("Evidence/D4/d4-coldstart-console.png"), x: 6.75, y: 4.15, w: 5.85, h: 2.4, rounding: true });
  s.addText("冷启动：真实按序启动 Broker 与模拟节点（终端输出直播）", { x: 6.75, y: 6.6, w: 5.85, h: 0.35, fontSize: 11.5, color: MUTE, fontFace: FONT, align: "center", margin: 0 });
  s.addNotes("任务书要求至少保留 1 次真实故障与修复。校验链天然覆盖错误 JSON / 错误 Topic / 超范围；视频 S7 幕展示完整过程。");
}

// ---------- 11 Rule/ML 对照 ----------
{
  const s = p.addSlide();
  header(s, "Rule / ML 对照：并列保留，模型只是辅助", "09 · 对照案例");
  card(s, 0.7, 1.75, 5.4, 4.9, CARD);
  s.addText("值得分析的案例：27.5℃ / 70%", { x: 1.0, y: 2.05, w: 4.8, h: 0.5, fontSize: 18, bold: true, color: INK, fontFace: FONT, margin: 0 });
  s.addText([
    { text: "固定规则：正常（27.5 < 30 且 70 < 75）", options: { bullet: true, breakLine: true } },
    { text: "ML（IsolationForest）：与历史明显不同，分数 0.6738", options: { bullet: true, breakLine: true } },
    { text: "分数高于三组规则异常组（0.5641 / 0.5967 / 0.6219）", options: { bullet: true, breakLine: true } },
    { text: "可能原因：历史仅 40 条且全在 24~26℃ / 55~65% 窄区间，模型'常态'边界过窄", options: { bullet: true, breakLine: true } },
    { text: "结论：ML 的语义是'与历史不同'而非'规则异常'，直接当异常提醒会误报——所以并列保留、辅助判断", options: { bullet: true } },
  ], { x: 1.0, y: 2.7, w: 4.8, h: 3.7, fontSize: 13, color: INK, fontFace: FONT, paraSpaceAfter: 11 });
  s.addImage({ path: IMG("Evidence/D5/d5-report-ml-section.png"), x: 6.5, y: 1.75, w: 6.1, h: 4.9, rounding: true });
  s.addNotes("任务书 D5：不一致不判'错误'，分析判断依据差异；允许主动设计测试输入但不改模型输出。边界：无 Label / 准确率 / 调参 / 模型服务。");
}

// ---------- 12 自主设计与亮点 ----------
{
  const s = p.addSlide();
  header(s, "自主设计与亮点", "10 · 设计决策");
  const items = [
    ["优先级三条兜底链", "时长 → 次数 → nodeId 顺序：任何数据下都有唯一、可解释的答案"],
    ["事件状态唯一源", "Dashboard 状态机唯一持有 + event topic 广播，三端不各自维护"],
    ["手写极简 MQTT 客户端", "移动端零依赖手写 MQTT 3.1.1 协议帧（30 项单测），不引入 npm 构建"],
    ["快照与事件关联", "语音拍照自动叠加节点/时间/状态，文件名含 eventId，事件卡片引用现场快照"],
    ["3D 事件回放", "每节点内存缓存最近记录，按时间轴重放状态颜色与粒子变化"],
    ["诚实的不理想案例", "ML 对照保留 27.5℃/70% 误判案例与原因分析，不粉饰模型"],
  ];
  items.forEach(([t, d], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.7 + col * 6.15, y = 1.75 + row * 1.75;
    card(s, x, y, 5.8, 1.55, CARD);
    s.addShape("ellipse", { x: x + 0.3, y: y + 0.32, w: 0.4, h: 0.4, fill: { color: NAVY } });
    s.addText(String(i + 1), { x: x + 0.3, y: y + 0.36, w: 0.4, h: 0.32, fontSize: 13, bold: true, color: PAPER, fontFace: FONT, align: "center", margin: 0 });
    s.addText(t, { x: x + 0.9, y: y + 0.22, w: 4.7, h: 0.4, fontSize: 15.5, bold: true, color: INK, fontFace: FONT, margin: 0 });
    s.addText(d, { x: x + 0.9, y: y + 0.66, w: 4.7, h: 0.75, fontSize: 11.5, color: MUTE, fontFace: FONT, margin: 0, valign: "top" });
  });
  s.addNotes("自主设计 10 条决策的 6 条代表性亮点。强调：全部是 C01 已学能力（Web/Python/MQTT/小程序/3D/ML）的重组，未引入超纲技术栈。");
}

// ---------- 13 开放拓展（如实标注未纳入） ----------
{
  const s = p.addSlide();
  header(s, "Open Enhancement：如实说明", "11 · 开放拓展");
  card(s, 0.7, 1.75, 5.4, 4.9, "FFF7E6");
  s.addText("基础线声明", { x: 1.0, y: 2.05, w: 4.8, h: 0.5, fontSize: 18, bold: true, color: INK, fontFace: FONT, margin: 0 });
  s.addText("本项目基础线未引入任何超纲技术：无数据库、无真实传感器、无 LLM/RAG/Agent、无正式 ML 训练流程、不新建后端服务。开放拓展属任务书允许但非完成线前提，本作品如实标注'未纳入基础线'。",
    { x: 1.0, y: 2.7, w: 4.8, h: 1.9, fontSize: 13.5, color: INK, fontFace: FONT, margin: 0, valign: "top" });
  s.addText("已完成的自主设计均属共同完成线内：手写 MQTT 客户端（零依赖）、3D 事件回放、快照事件关联等",
    { x: 1.0, y: 4.7, w: 4.8, h: 1.2, fontSize: 12, color: MUTE, fontFace: FONT, margin: 0, valign: "top" });

  card(s, 6.5, 1.75, 6.1, 4.9, CARD);
  s.addText("可作为后续方向的候选", { x: 6.8, y: 2.05, w: 5.5, h: 0.5, fontSize: 18, bold: true, color: INK, fontFace: FONT, margin: 0 });
  s.addText([
    { text: "事件数据接云端存储与多机部署", options: { bullet: true, breakLine: true } },
    { text: "真机同步（任务书 p15 明确不要求，属拓展）", options: { bullet: true, breakLine: true } },
    { text: "真实传感器接入，替换模拟节点", options: { bullet: true, breakLine: true } },
    { text: "更多 ASR 指令与多轮语音对话", options: { bullet: true, breakLine: true } },
    { text: "更丰富的 3D 场景与事件动画", options: { bullet: true } },
  ], { x: 6.8, y: 2.7, w: 5.5, h: 3.5, fontSize: 14, color: INK, fontFace: FONT, paraSpaceAfter: 14 });
  s.addNotes("任务书允许开放拓展但不得替代共同完成线；本作品按红线如实声明，不虚标。");
}

// ---------- 14 已知限制与后续（深色收尾） ----------
{
  const s = p.addSlide();
  s.background = { color: NAVY };
  s.addText("已知限制与后续", { x: 0.9, y: 0.65, w: 11.5, h: 0.8, fontSize: 32, bold: true, color: PAPER, fontFace: FONT, margin: 0 });
  const items = [
    "sklearn 在本机 Python 3.14 无法导入 → 纯 numpy 等价自实现 IsolationForest（README 记录替代原因）",
    "ASR 等价方案：Win+H 系统语音输入（webkitSpeechRecognition 依赖 Google 服务国内不可用）",
    "'已恢复'展示是瞬态：恢复后新异常立即重新 OPEN，属规则正确行为",
    "演示只开一个 Dashboard：多实例会互相覆盖事件广播（状态机唯一持有者设计）",
  ];
  items.forEach((it, i) => {
    const y = 1.85 + i * 1.15;
    s.addShape("ellipse", { x: 1.0, y: y + 0.16, w: 0.3, h: 0.3, fill: { color: "CADCFC" } });
    s.addText(it, { x: 1.6, y: y, w: 10.8, h: 0.85, fontSize: 14, color: "DCE4F2", fontFace: FONT, margin: 0, valign: "middle" });
  });
  s.addText("感谢观看 —— 欢迎现场核验：Run / Explain / Modify / Debug / Verify", {
    x: 0.9, y: 6.4, w: 11.5, h: 0.55, fontSize: 16, bold: true, color: PAPER, fontFace: FONT, align: "center", margin: 0 });
  s.addNotes("收尾：已知限制如实说明（等价替代先例），并邀请现场核验五项（任务书 p22-23 现场验收）。");
}

p.writeFile({ fileName: path.join(__dirname, "DormMate_V08R5_PPT.pptx") }).then(() => {
  console.log("PPT generated:", path.join(__dirname, "DormMate_V08R5_PPT.pptx"));
});
