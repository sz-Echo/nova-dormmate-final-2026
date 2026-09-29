"""DormMate B S1 自动化验证（simulator/test_b1.py）

B1 当前总览（SPEC §9 B1 / MASTER_PLAN §6.5）：程序成句、状态变化自动更新、不写死。
验证点：① 全正常 ② 单异常（dorm-b 偏热）③ 双异常（截图例句逐字一致）
       ④ dorm-c 恢复后总览自动变化 ⑤ test-priority.html（含组⑦ B1 断言）0 失败。

前置：本机 Mosquitto Broker 已启动（127.0.0.1:1883 / WebSocket 8083）。
用法：python simulator/test_b1.py
脚本自动：临时启动 127.0.0.1:5500 静态服务（项目根）→ Playwright 打开 dashboard →
paho 按剧本发布 → 断言总览条文本 + 截图到 docs/evidence/b/ → 关闭服务。
"""
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
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


def pub_env(client, node, t, h, dt):
    client.publish(f"dormmate/{node}/env", json.dumps({
        "nodeId": node, "temperature": t, "humidity": h, "status": "",
        "time": dt.strftime("%Y-%m-%d %H:%M:%S"), "action": ""
    }), qos=0)


def main():
    # 静态服务（项目根，相对路径 ../web/script.js 可用）
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

        now = datetime.now().replace(microsecond=0)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(BASE + "/dashboard/index.html")
            page.wait_for_selector("#connStatus.online", timeout=15000)
            page.wait_for_timeout(800)

            # ① 全正常
            for node in ("dorm-a", "dorm-b", "dorm-c"):
                pub_env(pub, node, 25, 60, now)
            page.wait_for_timeout(800)
            t = page.inner_text("#overviewBar")
            check("全正常 → 3 个正常 0 个需要关注", t == "当前 3 个宿舍中，3 个正常，0 个需要关注。", t)
            page.screenshot(path=str(EVIDENCE / "b1-1-all-normal.png"))

            # ② dorm-b 偏热 10 分钟（单异常）
            for i in range(3):
                pub_env(pub, "dorm-b", 31, 60, now - timedelta(minutes=10 - 5 * i))
            page.wait_for_timeout(800)
            t = page.inner_text("#overviewBar")
            check("单异常 → 2 正常 1 关注；dorm-b 是当前重点",
                  "2 个正常，1 个需要关注" in t and "dorm-b 出现偏热，是当前重点" in t, t)
            page.screenshot(path=str(EVIDENCE / "b1-2-b-hot.png"))

            # ③ dorm-c 偏湿 → 双异常（截图例句逐字一致）
            pub_env(pub, "dorm-c", 25, 80, now)
            page.wait_for_timeout(800)
            t = page.inner_text("#overviewBar")
            check("双异常 → 截图例句逐字一致",
                  t == "当前 3 个宿舍中，1 个正常，2 个需要关注；dorm-b 持续异常时间更长，是当前重点，dorm-c 出现偏湿。", t)
            page.screenshot(path=str(EVIDENCE / "b1-3-b-hot-c-wet.png"))

            # ④ dorm-c 恢复 → 总览自动变回（不写死）
            pub_env(pub, "dorm-c", 25, 60, now + timedelta(minutes=1))
            page.wait_for_timeout(800)
            t = page.inner_text("#overviewBar")
            check("dorm-c 恢复 → 总览自动更新为 2 正常 1 关注",
                  "2 个正常，1 个需要关注" in t and "dorm-b 出现偏热，是当前重点" in t, t)
            page.screenshot(path=str(EVIDENCE / "b1-4-c-recovered.png"))

            # ⑤ 测试页（含组⑦ B1 断言）仍全过
            page.goto(BASE + "/dashboard/test-priority.html")
            page.wait_for_selector("#summary", timeout=10000)
            summary = page.inner_text("#summary")
            check("test-priority.html 汇总 0 失败（含组⑦ B1 断言）", "0 失败" in summary, summary)
            page.screenshot(path=str(EVIDENCE / "b1-5-test-page.png"), full_page=True)

            browser.close()

        pub.disconnect()
        print("B1 RESULT: %d failures" % len(failures))
        return 1 if failures else 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
