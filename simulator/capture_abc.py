"""DormMate A/B/C 运行截图（simulator/capture_abc.py）

复用 record_demo.py 的剧本编排（双 iframe 同屏、脚本发布、Broker 自启自停），
在 A/B/C 各关键节点对整页截图，输出到 docs/demo/screenshots/：

  A 组：a1-normal（三节点正常）/ a1-priority（A1 优先横幅）/ a2-fan（A2 开风扇+3D 联动）
        a3-recovered（A3 已恢复+自动关扇）/ a4-event（A4 事件面板）/ a4-report（报告事件复盘）
  B 组：b1-overview（B1 总览成句）/ b2-evidence（B2 依据卡片+优先标注）
        b4-tts（B4 朗读提醒）/ b3-summary（B3 今日摘要报告）
  C 组：c3-report（C3 报告 ML 异常分析区）/ c2-console（C2 控制台对照）
        c2-compare（C2 对照结果 JSON）/ c1-new + c1-history（C1 数据分离）
        c4-case（C4 不理想案例说明）

A4 导出事件后重生成 data/report.html，结束自动 git checkout 恢复三个程序产物；
不改任何产品代码。用法：python simulator/capture_abc.py
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

import record_demo as rd   # 复用：demo_page_html / pub_env / ensure_broker / start_server / switch_right / scroll_right_to / run

BASE = rd.BASE
NODES = rd.NODES
VIEWPORT = {"width": 1600, "height": 900}


def open_page(browser, left, right):
    context = browser.new_context(viewport=VIEWPORT)
    page = context.new_page()
    page.set_content(rd.demo_page_html(left, right))
    return context, page


def main():
    import paho.mqtt.client as mqtt
    from playwright.sync_api import sync_playwright

    broker = rd.ensure_broker()
    if broker is None and not rd.port_open(1883):
        print("[错误] Broker 未就绪", file=sys.stderr)
        return 1
    server = rd.start_server()
    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    pub.connect("127.0.0.1", 1883)
    pub.loop_start()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            now = datetime.now().replace(microsecond=0)

            # ================= A 组 =================
            print("== A 组截图 ==")
            context, page = open_page(browser, BASE + "/dashboard/index.html", BASE + "/three3d/index.html")
            left = page.frame_locator("iframe[name=left]")
            right = page.frame_locator("iframe[name=right]")
            left.locator("#connStatus.online").wait_for(timeout=20000)
            right.locator("#connStatus.online").wait_for(timeout=20000)
            for n in NODES:
                rd.pub_env(pub, n, 25, 60, now)
            page.wait_for_timeout(3500)
            page.screenshot(path=str(OUT / "a1-normal.png"))

            rd.pub_env(pub, "dorm-b", 32, 82, now - timedelta(minutes=10))
            rd.pub_env(pub, "dorm-b", 32.5, 81, now - timedelta(minutes=7))
            rd.pub_env(pub, "dorm-b", 33, 80, now - timedelta(minutes=5))
            page.wait_for_timeout(3500)
            page.screenshot(path=str(OUT / "a1-priority.png"))

            box = right.locator("#canvasContainer canvas").bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.wait_for_timeout(1000)
            left.locator("#tabs button").filter(has_text="dorm-b").first.click()
            page.wait_for_timeout(1200)
            left.locator("#fanOnBtn").click()
            page.wait_for_timeout(5000)
            page.screenshot(path=str(OUT / "a2-fan.png"))

            rd.pub_env(pub, "dorm-b", 30, 76, now + timedelta(minutes=1))
            page.wait_for_timeout(2500)
            rd.pub_env(pub, "dorm-b", 27, 65, now + timedelta(minutes=2))
            page.wait_for_timeout(1800)
            rd.pub_env(pub, "dorm-b", 26, 62, now + timedelta(minutes=3))
            page.wait_for_timeout(4000)
            page.screenshot(path=str(OUT / "a3-recovered.png"))

            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / "a4-event.png"))
            try:
                with page.expect_download(timeout=8000) as dl:
                    left.locator("#exportEventsBtn").click()
                dl.value.save_as(ROOT / "data" / "events.json")
            except Exception:
                pass
            rd.run(["analysis/analyze.py", str(ROOT / "data" / "final-dormmate.csv"), "--out", str(ROOT / "data")])
            rd.switch_right(page, BASE + "/data/report.html")
            rd.scroll_right_to(page, "事件复盘")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "a4-report.png"))
            context.close()

            # ================= B 组 =================
            print("== B 组截图 ==")
            rd.run(["analysis/make_day_data.py", "--out", str(ROOT / "docs" / "demo" / "sim-day-demo"), "--seed", "5"])
            rd.run(["analysis/daily_summary.py", "--day", str(ROOT / "docs" / "demo" / "sim-day-demo")])
            context, page = open_page(browser, BASE + "/dashboard/index.html",
                                      BASE + "/docs/demo/sim-day-demo/report.html")
            left = page.frame_locator("iframe[name=left]")
            left.locator("#connStatus.online").wait_for(timeout=20000)
            rd.scroll_right_to(page, "今日摘要")
            for n in NODES:
                rd.pub_env(pub, n, 25, 60, now)
            page.wait_for_timeout(3500)
            page.screenshot(path=str(OUT / "b1-overview.png"))

            rd.pub_env(pub, "dorm-c", 25, 80, now + timedelta(minutes=1))
            page.wait_for_timeout(4500)
            page.screenshot(path=str(OUT / "b2-evidence.png"))

            left.locator("#speakOverviewBtn").click()
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "b4-tts.png"))

            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "b3-summary.png"))
            context.close()

            # ================= C 组 =================
            print("== C 组截图 ==")
            r = rd.run(["analysis/c_ml.py"])
            console_html = ("<html><head><meta charset='UTF-8'><style>"
                            "body{background:#0d1117;color:#c9d1d9;font:14px/1.6 Consolas,monospace;padding:16px;white-space:pre-wrap;}"
                            "</style></head><body><pre>" +
                            (str(r.stdout).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                            + "</pre></body></html>")
            readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
            i = readme_text.find("C 组轻量 ML")
            j = readme_text.find("\n## ", i + 10)
            c_block = readme_text[i:j if j > 0 else None]
            k = readme_text.find("已知限制")
            limit_block = readme_text[k:readme_text.find("\n## ", k + 10) if readme_text.find("\n## ", k + 10) > 0 else None]
            readme_html = ("<html><head><meta charset='UTF-8'><style>"
                           "body{background:#f5f7fa;color:#2c3e50;font:15px/1.7 'Microsoft YaHei',sans-serif;padding:20px;white-space:pre-wrap;}"
                           "</style></head><body><pre style='white-space:pre-wrap;font-family:inherit'>" +
                           (c_block + "\n\n" + limit_block[:2500]).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                           + "</pre></body></html>")

            context, page = open_page(browser, BASE + "/data/report.html", "about:blank")
            page.frames[1].wait_for_load_state(timeout=20000)
            page.wait_for_timeout(3000)
            page.screenshot(path=str(OUT / "c3-report.png"))

            rd.switch_right_srcdoc(page, console_html)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "c2-console.png"))

            rd.switch_right(page, BASE + "/data/c_compare.json")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "c2-compare.png"))

            rd.switch_right(page, BASE + "/data/c_new.csv")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(OUT / "c1-new.png"))

            rd.switch_right(page, BASE + "/data/c_history.csv")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(OUT / "c1-history.png"))

            rd.switch_right_srcdoc(page, readme_html)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "c4-case.png"))
            context.close()

            browser.close()
    finally:
        pub.loop_stop()
        pub.disconnect()
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()
        if broker is not None:
            broker.terminate()

    # 恢复 A 段重生成的程序产物（仓库保持干净）
    import subprocess
    restored = subprocess.run(["git", "checkout", "--", "data/events.json", "data/report.html", "data/trend.png"],
                              cwd=str(ROOT), capture_output=True, text=True)
    if restored.returncode != 0:
        print("[提示] 产物恢复未执行（可能无改动）")
    shots = sorted(p.name for p in OUT.glob("*.png"))
    print(f"截图完成：{len(shots)} 张 → docs/demo/screenshots/")
    for s in shots:
        print("  ", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
