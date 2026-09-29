"""DormMate Final 关闭重启复验（simulator/test_final.py）

MASTER_PLAN §7.6：环境已按 README 冷启动（Broker 1883/8083 双端口就绪）后，
分五段复验两条链与 A/B/C 三个闭环：

  --realtime  F S3 实时链：真实 simulator 三节点 → Dashboard + 3D 并排（不串线）
  --offline   F S2 离线链：Web 录入 → 导出 CSV → analyze.py → report.html 四区齐全
              （含 SPEC §6 四组回归：analyze.py --selftest + web/test.html）
  --a-loop    F S4 A 闭环重演：dorm-b 偏热 → A1 优先横幅 → 开风扇 → 3D 风扇联动
              → 降温新数据 → 连续 2 条正常 → 已恢复 + 自动关扇 → 事件导出 → report 复盘
  --b-loop    F S5 B 信息闭环：总览成句 / 依据卡片 / 朗读提醒(TTS mock) /
              B3 换 seed 重新生成今日摘要（与 sim-day-2 不同）
  --c-repro   F S6 C 对照复现：random_state=42 → c_compare.json 与已提交版本逐字段一致

前置：Mosquitto Broker 已启动（127.0.0.1:1883 / 8083）。
      实时链（--realtime）需真实 simulator 运行中；
      剧本段（--a-loop / --b-loop）需 simulator 停止（脚本独占三节点数据流）。
证据：docs/evidence/final/。
用法：python simulator/test_final.py [--realtime] [--offline] [--a-loop] [--b-loop] [--c-repro]
      不带参数则全部执行（顺序：realtime → offline → a-loop → b-loop → c-repro）。
"""
import argparse
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EVIDENCE = ROOT / "docs" / "evidence" / "final"
EVIDENCE.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:5500"
NODES = ("dorm-a", "dorm-b", "dorm-c")
STATUSES = ("正常", "偏冷", "偏热", "偏湿")
failures = []


def check(name, cond, actual=""):
    print(("PASS" if cond else "FAIL") + " | " + name + ((" | 实际: " + str(actual)) if not cond else ""))
    if not cond:
        failures.append(name)


def run(args):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True,
                          cwd=str(ROOT), encoding="utf-8", errors="replace")


def run_raw(args):
    """非 Python 命令（如 git），不加解释器前缀。"""
    return subprocess.run(args, capture_output=True, text=True,
                          cwd=str(ROOT), encoding="utf-8", errors="replace")


def wait_port(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        s = socket.socket()
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except OSError:
            time.sleep(0.3)
    return False


def pub_env(client, node, t, h, dt):
    client.publish(f"dormmate/{node}/env", json.dumps({
        "nodeId": node, "temperature": t, "humidity": h, "status": "",
        "time": dt.strftime("%Y-%m-%d %H:%M:%S"), "action": ""
    }), qos=0)


def start_server():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "5500", "--bind", "127.0.0.1"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    ready = wait_port(5500)
    if not ready:
        server.terminate()
        check("5500 静态服务就绪", False, "端口未就绪")
        return None
    return server


def stop_server(server):
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()


def realtime():
    """F S3 实时链复跑：真实 simulator → Dashboard + 3D 并排。"""
    from playwright.sync_api import sync_playwright
    import paho.mqtt.client as mqtt

    seen = {n: set() for n in NODES}
    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_msg(client, userdata, msg):
        try:
            m = json.loads(msg.payload)
        except json.JSONDecodeError:
            return
        topic_node = msg.topic.split("/")[1] if msg.topic.count("/") >= 2 else ""
        if m.get("nodeId") == topic_node and topic_node in seen and m.get("status") in STATUSES:
            seen[topic_node].add(m["status"])

    sub.on_message = on_msg
    sub.connect("127.0.0.1", 1883)
    sub.subscribe("dormmate/+/env")
    sub.loop_start()

    server = start_server()
    if not server:
        sub.loop_stop(); sub.disconnect()
        return
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            # Dashboard：三卡片同屏 + 状态与订阅流一致（串线防线抽查）
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(BASE + "/dashboard/index.html")
            page.wait_for_selector("#connStatus.online", timeout=15000)
            page.wait_for_timeout(6000)
            cards_text = page.inner_text("#cards")
            for n in NODES:
                check(f"Dashboard 卡片含 {n}", n in cards_text, cards_text[:200])
            overview = page.inner_text("#overviewBar")
            check("总览条含三宿舍成句", "3 个宿舍" in overview, overview)
            # 每张卡片显示的状态必须来自该节点真实消息（订阅流中该节点出现过的状态）
            for n in NODES:
                card = page.locator("#cards .card").filter(has_text=n).first
                card_status = None
                for s in STATUSES:
                    if s in card.inner_text():
                        card_status = s
                        break
                check(f"{n} 卡片状态为四状态之一且订阅流中出现过",
                      card_status is not None and (card_status in seen[n] if seen[n] else True),
                      f"card={card_status} seen={sorted(seen[n])}")
            page.screenshot(path=str(EVIDENCE / "f-s3-dashboard.png"))

            # 3D：场景渲染 + 点击选中 dorm-b（building x=0 → 画布中心）
            page3d = browser.new_page(viewport={"width": 1400, "height": 1000})
            page3d.goto(BASE + "/three3d/index.html")
            page3d.wait_for_selector("#connStatus.online", timeout=15000)
            page3d.wait_for_timeout(3000)
            box = page3d.locator("#canvasContainer canvas").bounding_box()
            check("3D canvas 已渲染", box is not None)
            if box:
                page3d.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page3d.wait_for_timeout(600)
                check("3D 点击中心选中 dorm-b", page3d.inner_text("#sideNodeId") == "dorm-b",
                      page3d.inner_text("#sideNodeId"))
                check("3D 侧栏状态为四状态之一", page3d.inner_text("#sideStatus") in STATUSES,
                      page3d.inner_text("#sideStatus"))
            page3d.screenshot(path=str(EVIDENCE / "f-s3-3d.png"))
            browser.close()

        sub.loop_stop()
        sub.disconnect()
    finally:
        stop_server(server)


def offline():
    """F S2 离线链复跑：回归自测 → Web 录入 → 导出 CSV → analyze.py → report 四区。"""
    from playwright.sync_api import sync_playwright

    r = run(["analysis/analyze.py", "--selftest"])
    check("SPEC §6 四组回归（analyze.py --selftest）", "4/4 通过" in r.stdout, r.stdout[-200:])

    server = start_server()
    if not server:
        return
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(BASE + "/web/test.html")
            page.wait_for_selector("#summary", timeout=10000)
            summary = page.inner_text("#summary")
            check("web/test.html 四组回归全过", "失败" not in summary, summary)

            page.goto(BASE + "/web/index.html")
            rows = [(25, 60, "正常"), (16, 60, "偏冷"), (31, 60, "偏热"), (25, 80, "偏湿"),
                    (24, 58, "正常"), (29, 70, "正常"), (20, 65, "正常")]
            for t, h, expected in rows:
                page.fill("#temperature", str(t))
                page.fill("#humidity", str(h))
                page.click("#analyzeBtn")
                page.wait_for_timeout(150)
                check(f"Web 录入 {t}/{h} → {expected}", page.inner_text("#statusText") == expected,
                      page.inner_text("#statusText"))
            history_count = page.locator("#historyList li").count()
            check("历史 7 条", history_count == 7, history_count)
            page.screenshot(path=str(EVIDENCE / "f-s2-web.png"))

            with page.expect_download(timeout=10000) as dl_info:
                page.click("#exportBtn")
            dl = dl_info.value
            final_csv = DATA / "final-dormmate.csv"
            dl.save_as(final_csv)
            check("导出 CSV 落盘", final_csv.exists())
            lines = final_csv.read_text(encoding="utf-8-sig").strip().splitlines()
            check("CSV 表头 4 列 + 7 行", lines[0] == "time,temperature,humidity,status" and len(lines) == 8,
                  (lines[0], len(lines)))
            browser.close()

        r = run(["analysis/analyze.py", str(final_csv), "--out", str(DATA)])
        check("analyze.py 全量重生成", r.returncode == 0, r.stderr[-300:])
        report = (DATA / "report.html").read_text(encoding="utf-8")
        for section in ("摘要", "关注记录（status 非正常）", "事件复盘（A4）", "ML 异常分析（C3）", "趋势图"):
            check(f"report.html 含 {section} 区", section in report)
        check("ML 区含 29℃/72% 候选行", "29℃ / 72%" in report)
        (EVIDENCE / "f-s2-console.txt").write_text(r.stdout, encoding="utf-8")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1100, "height": 1500})
            page.goto(BASE + "/data/report.html")
            page.wait_for_selector("section", timeout=10000)
            page.screenshot(path=str(EVIDENCE / "f-s2-report.png"), full_page=True)
            browser.close()
    finally:
        stop_server(server)


def a_loop():
    """F S4 A 闭环重演（simulator 已停止，脚本独占三节点数据流）。"""
    from playwright.sync_api import sync_playwright
    import paho.mqtt.client as mqtt

    actions = []
    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_action(client, userdata, msg):
        try:
            actions.append(json.loads(msg.payload))
        except json.JSONDecodeError:
            pass

    sub.on_message = on_action
    sub.connect("127.0.0.1", 1883)
    sub.subscribe("dormmate/+/action")
    sub.loop_start()

    server = start_server()
    if not server:
        sub.loop_stop(); sub.disconnect()
        return
    try:
        now = datetime.now().replace(microsecond=0)
        with sync_playwright() as p:
            browser = p.chromium.launch()

            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(BASE + "/dashboard/index.html")
            page.wait_for_selector("#connStatus.online", timeout=15000)

            # A1：dorm-b 连续偏热（其他两节点正常）
            for node in NODES:
                pub_env(sub, node, 25, 60, now)
            pub_env(sub, "dorm-b", 32, 82, now - timedelta(minutes=10))
            pub_env(sub, "dorm-b", 32.5, 81, now - timedelta(minutes=7))
            pub_env(sub, "dorm-b", 33, 80, now - timedelta(minutes=5))
            page.wait_for_timeout(800)
            banner = page.inner_text("#priorityBanner")
            check("A1 优先横幅：dorm-b 偏热 + 连续时长", "dorm-b" in banner and "偏热" in banner and "连续" in banner, banner)
            check("B1 总览成句：1 个需要关注", "1 个需要关注" in page.inner_text("#overviewBar"),
                  page.inner_text("#overviewBar"))
            page.screenshot(path=str(EVIDENCE / "f-s4-banner.png"))

            # 3D 先选中 dorm-b（building x=0 → 画布中心），随后验证风扇联动
            page3d = browser.new_page(viewport={"width": 1400, "height": 1000})
            page3d.goto(BASE + "/three3d/index.html")
            page3d.wait_for_selector("#connStatus.online", timeout=15000)
            page3d.wait_for_timeout(2500)
            box = page3d.locator("#canvasContainer canvas").bounding_box()
            if box:
                page3d.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page3d.wait_for_timeout(600)
            check("3D 选中 dorm-b", page3d.inner_text("#sideNodeId") == "dorm-b", page3d.inner_text("#sideNodeId"))

            # A2：Dashboard 选 dorm-b（tab 按钮，app.js selectedNode）→ 开风扇 → 动作消息 + 处理中
            page.locator("#tabs button").filter(has_text="dorm-b").first.click()
            page.wait_for_timeout(300)
            check("动作区选中 dorm-b", page.inner_text("#actionNode") == "dorm-b", page.inner_text("#actionNode"))
            page.click("#fanOnBtn")
            page.wait_for_timeout(800)
            check("Dashboard 显示处理中", "处理中" in page.inner_text("#actionStateText"),
                  page.inner_text("#actionStateText"))
            fan_on = [a for a in actions if a.get("nodeId") == "dorm-b" and a.get("action") == "fan_on"]
            check("动作通道收到 fan_on(dorm-b)", len(fan_on) >= 1, str(actions)[:200])
            page.screenshot(path=str(EVIDENCE / "f-s4-processing.png"))

            # A2 联动：3D 风扇运行中
            page3d.wait_for_timeout(1200)
            check("3D 侧栏风扇运行中", "风扇运行中" in page3d.inner_text("#sideAction"),
                  page3d.inner_text("#sideAction"))
            page3d.screenshot(path=str(EVIDENCE / "f-s4-3d-fan.png"))

            # A3：降温新数据 → 连续 2 条正常 → 已恢复 + 自动 fan_off
            pub_env(sub, "dorm-b", 30, 76, now + timedelta(minutes=1))   # 仍偏热 → 保持处理中
            page.wait_for_timeout(600)
            check("降温中仍异常 → 保持处理中", "已恢复" not in page.inner_text("#actionStateText"),
                  page.inner_text("#actionStateText"))
            pub_env(sub, "dorm-b", 27, 65, now + timedelta(minutes=2))   # 正常 #1
            pub_env(sub, "dorm-b", 26, 62, now + timedelta(minutes=3))   # 正常 #2
            page.wait_for_timeout(1200)
            check("连续 2 条正常 → 已恢复", "已恢复" in page.inner_text("#actionStateText"),
                  page.inner_text("#actionStateText"))
            check("自动发布 fan_off", any(a.get("nodeId") == "dorm-b" and a.get("action") == "fan_off" for a in actions),
                  str(actions)[-200:])
            page.screenshot(path=str(EVIDENCE / "f-s4-recovered.png"))

            # A4：事件面板 + 导出 events.json
            events_text = page.inner_text("#eventList")
            check("今日事件面板含 dorm-b 事件", "dorm-b" in events_text, events_text[:200])
            with page.expect_download(timeout=10000) as dl_info:
                page.click("#exportEventsBtn")
            dl = dl_info.value
            dl.save_as(DATA / "events.json")
            check("events.json 已导出且含 dorm-b 事件",
                  any(e.get("nodeId") == "dorm-b" for e in json.loads((DATA / "events.json").read_text(encoding="utf-8"))))
            browser.close()

        # A4 复盘进报告
        r = run(["analysis/analyze.py", str(DATA / "final-dormmate.csv"), "--out", str(DATA)])
        check("A4 复盘重新生成报告", r.returncode == 0, r.stderr[-300:])
        report = (DATA / "report.html").read_text(encoding="utf-8")
        check("report 事件复盘区含 dorm-b 事件与复盘叙事", "dorm-b" in report and "复盘" in report)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1100, "height": 1500})
            page.goto(BASE + "/data/report.html")
            page.wait_for_selector("section", timeout=10000)
            page.screenshot(path=str(EVIDENCE / "f-s4-report-events.png"), full_page=True)
            browser.close()

        sub.loop_stop()
        sub.disconnect()
    finally:
        stop_server(server)


def b_loop():
    """F S5 B 信息闭环：总览 / 依据 / 朗读提醒（TTS mock）/ B3 换 seed 重生成今日摘要。"""
    from playwright.sync_api import sync_playwright
    import paho.mqtt.client as mqtt

    server = start_server()
    if not server:
        return
    try:
        now = datetime.now().replace(microsecond=0)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(BASE + "/dashboard/index.html")
            page.wait_for_selector("#connStatus.online", timeout=15000)

            # B1：总览成句 + 状态变化自动更新
            pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            pub.connect("127.0.0.1", 1883)
            pub.loop_start()
            for node in NODES:
                pub_env(pub, node, 25, 60, now)
            page.wait_for_timeout(800)
            overview = page.inner_text("#overviewBar")
            check("B1 全正常总览", overview == "当前 3 个宿舍中，3 个正常，0 个需要关注。", overview)
            pub_env(pub, "dorm-c", 25, 80, now + timedelta(minutes=1))
            page.wait_for_timeout(800)
            overview = page.inner_text("#overviewBar")
            check("B1 状态变化总览自动更新（dorm-c 是当前重点）",
                  "2 个需要关注" not in overview and "1 个需要关注" in overview
                  and "dorm-c 出现偏湿，是当前重点" in overview, overview)

            # B2：依据卡片（3 张 + 优先标注 + 来源可指）
            card_count = page.locator("#evidenceCards .evidence-card").count()
            check("B2 依据卡片 3 张", card_count == 3, card_count)
            check("B2 依据来源可指（'依据：'）", "依据：" in page.inner_text("#evidenceCards"))
            check("B2 优先标注 dorm-c", "winner" in page.locator("#evidenceCards .evidence-card").filter(has_text="dorm-c").first.get_attribute("class"))
            page.screenshot(path=str(EVIDENCE / "f-s5-overview.png"))

            # B4：朗读提醒（TTS mock 按 test_b4 模式：构造器截获 + speechSynthesis 替换，全部放 init_script）
            page.add_init_script("""
                window.__spoken = [];
                const OrigU = window.SpeechSynthesisUtterance;
                window.SpeechSynthesisUtterance = function (text) {
                    window.__spoken.push("[ctor] " + String(text));
                    return new OrigU(text);
                };
                window.SpeechSynthesisUtterance.prototype = OrigU.prototype;
                window.speechSynthesis = {
                    cancel: function () {},
                    speak: function (u) { window.__spoken.push("[speak] " + String(u && u.text)); },
                    getVoices: function () { return []; },
                    addEventListener: function () {},
                    removeEventListener: function () {}
                };
            """)
            page.reload()
            page.wait_for_selector("#connStatus.online", timeout=15000)
            page.wait_for_timeout(500)
            # 刷新后内存态清空 → 重新发布三节点数据，总览与朗读按钮才会出现
            for node in NODES:
                pub_env(pub, node, 25, 60, now + timedelta(minutes=2))
            pub_env(pub, "dorm-c", 25, 80, now + timedelta(minutes=3))
            page.wait_for_timeout(800)
            page.click("#speakOverviewBtn")
            page.wait_for_timeout(500)
            spoken = page.evaluate("window.__spoken.join(' | ')")
            check("B4 朗读提醒只读当前总览（含 3 个宿舍成句）", "3 个宿舍" in spoken, spoken)
            browser.close()
            pub.disconnect()

        # B3：换 seed 重新生成今日摘要（与 sim-day-2 必须不同）
        r = run(["analysis/make_day_data.py", "--out", str(DATA / "sim-day-final"), "--seed", "3"])
        check("B3 模拟日数据生成（seed 3）", r.returncode == 0, r.stderr[-300:])
        r = run(["analysis/daily_summary.py", "--day", str(DATA / "sim-day-final")])
        check("B3 今日摘要生成", r.returncode == 0, r.stderr[-300:])
        summary = (DATA / "sim-day-final" / "summary.md").read_text(encoding="utf-8")
        summary2 = (DATA / "sim-day-2" / "summary.md").read_text(encoding="utf-8")
        check("B3 换数据摘要重新生成（与 sim-day-2 不同）", summary != summary2 and len(summary) > 50)
        day_events = json.loads((DATA / "sim-day-final" / "events.json").read_text(encoding="utf-8"))
        check("B3 模拟日 ≥2 事件", len(day_events) >= 2, len(day_events))
        check("B3 摘要为程序成句（含节点与事件描述）",
              all(n in summary for n in NODES) and ("发生" in summary or "正常" in summary), summary[:200])
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1100, "height": 1500})
            page.goto(BASE + "/data/sim-day-final/report.html")
            page.wait_for_selector("section", timeout=10000)
            page.screenshot(path=str(EVIDENCE / "f-s5-summary-report.png"), full_page=True)
            browser.close()
    finally:
        stop_server(server)


def c_repro():
    """F S6 C 对照复现：random_state=42 → c_compare.json 与已提交版本逐字段一致。"""
    r = run(["analysis/make_c_data.py"])
    check("C 数据重生成（random_state=42）", r.returncode == 0, r.stderr[-200:])
    r = run(["analysis/c_ml.py"])
    check("C 对照重跑", r.returncode == 0, r.stderr[-300:])
    fresh = json.loads((DATA / "c_compare.json").read_text(encoding="utf-8"))
    r = run_raw(["git", "show", "HEAD:nova-dormmate-final-2026/data/c_compare.json"])
    check("读取已提交版本 c_compare.json", r.returncode == 0 and r.stdout.strip(), r.stderr[-200:])
    if r.returncode == 0 and r.stdout.strip():
        committed = json.loads(r.stdout)
        check("复现结果与已提交版本逐字段一致（random_state=42 可复现）", fresh == committed)
    else:
        check("复现结果与已提交版本逐字段一致（random_state=42 可复现）", False, "无法读取已提交版本")
    check("对照表 8 组", len(fresh) == 8, len(fresh))
    diff = [c for c in fresh if c["rule_status"] == "正常" and c["ml_verdict"] == -1]
    check("差异行 3 组且含 29/72（0.6738）", len(diff) == 3 and any(c["temperature"] == 29.0 for c in diff),
          str(diff)[:200])

    # 报告最终态：ML 区与对照一致
    r = run(["analysis/analyze.py", str(DATA / "final-dormmate.csv"), "--out", str(DATA)])
    check("报告重生成", r.returncode == 0, r.stderr[-300:])
    report = (DATA / "report.html").read_text(encoding="utf-8")
    check("报告 ML 区含复现结果（29℃/72% + 0.6738）", "29℃ / 72%" in report and "0.6738" in report)
    (EVIDENCE / "f-s6-console.txt").write_text(r.stdout, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="DormMate Final 复验（分段执行）")
    for flag in ("realtime", "offline", "a-loop", "b-loop", "c-repro"):
        parser.add_argument("--" + flag.replace("_", "-"), dest=flag.replace("-", "_"),
                            action="store_true", help=f"执行 {flag} 段")
    args = parser.parse_args()
    selected = [k for k in ("realtime", "offline", "a_loop", "b_loop", "c_repro")
                if getattr(args, k, False)]
    if not selected:
        selected = ["realtime", "offline", "a_loop", "b_loop", "c_repro"]
    for section in selected:
        print(f"===== Final {section} =====")
        globals()[section]()
    print("FINAL RESULT: %d failures" % len(failures))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
