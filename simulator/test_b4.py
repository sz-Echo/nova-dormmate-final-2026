"""DormMate B S4 自动化验证（simulator/test_b4.py）

B4 信息分工（SPEC §9 B4）：TTS 只读当前提醒（Dashboard"朗读提醒"按钮读 B1 总览）；
分工说明表在 README。验证点：无数据时按钮隐藏；有数据后按钮出现；点击后 speechSynthesis
收到与总览条一致的文本；README 分工表齐全。

前置：本机 Mosquitto Broker 已启动（127.0.0.1:1883 / WebSocket 8083）。
用法：python simulator/test_b4.py（脚本自带 5500 静态服务启停）
"""
import json
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:5500"
EVIDENCE = ROOT / "docs" / "evidence" / "b"
EVIDENCE.mkdir(parents=True, exist_ok=True)
failures = []


def check(name, cond, actual=""):
    print(("PASS" if cond else "FAIL") + " | " + name + ((" | 实际: " + str(actual)) if not cond else ""))
    if not cond:
        failures.append(name)


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


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "5500", "--bind", "127.0.0.1"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_port(5500):
            check("5500 静态服务就绪", False, "端口未就绪")
            return 1

        pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        pub.connect("127.0.0.1", 1883)
        pub.loop_start()

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 1100})
            # 记录 speechSynthesis 调用（B4：TTS 只读当前提醒）
            # 同时截获构造器与 speak（宿主对象替换可能被静默忽略，构造器截获更可靠）
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
            page.goto(BASE + "/dashboard/index.html")
            page.wait_for_selector("#connStatus.online", timeout=15000)
            page.wait_for_timeout(500)

            # 无数据：朗读按钮隐藏
            check("无数据时朗读按钮隐藏", page.is_hidden("#speakOverviewBtn"))

            # 有数据：按钮出现，点击后 TTS 收到与总览一致的提醒
            now = datetime.now().replace(microsecond=0)
            for node in ("dorm-a", "dorm-b", "dorm-c"):
                pub.publish(f"dormmate/{node}/env", json.dumps({
                    "nodeId": node, "temperature": 25, "humidity": 60, "status": "",
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"), "action": ""
                }), qos=0)
            page.wait_for_timeout(1000)
            check("有数据后朗读按钮出现", page.is_visible("#speakOverviewBtn"))
            overview_text = page.inner_text("#overviewBar")
            page.click("#speakOverviewBtn")
            page.wait_for_timeout(500)
            spoken = page.evaluate("window.__spoken")
            check("TTS 收到提醒且与总览条文本一致（只读当前提醒）",
                  len(spoken) >= 1 and overview_text in str(spoken), (spoken, overview_text))

            page.screenshot(path=str(EVIDENCE / "b4-dashboard-division.png"))

            browser.close()

        pub.disconnect()

        # README 分工说明表（B4 完成线：能说明"为什么这条信息适合放在这里"）
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        check("README 分工表含四入口", all(k in readme for k in ("Dashboard", "3D", "TTS", "report.html")))
        check("README 分工表含放置理由", "为什么放在这里" in readme and "一眼定位" in readme)

        print("B4 RESULT: %d failures" % len(failures))
        return 1 if failures else 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
