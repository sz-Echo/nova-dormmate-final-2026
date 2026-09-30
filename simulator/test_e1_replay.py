#!/usr/bin/env python3
# DormMate V0.8R5 阶段 B（B4）：3D 事件回放 冒烟验证
# 流程：注入多条不同状态历史 -> 点击节点 -> 1× 回放（历史帧驱动，回放中实时数据仍进缓存）
#       -> 回放中发布 env（缓冲验证：#sideHistory 仍增长）+ 发布 HANDLING 事件（#sideEvent 实时、
#          #replayInfo 仍回放中，用户要求 2）-> 停止 -> 侧栏恢复跟随实时新数据
# 前置：Broker 与 5510 静态服务已运行（simulator 非必需）
# 运行：python simulator/test_e1_replay.py（exit code 0 = 通过）
# 证据：Evidence/E1/e1-replay-playing.png、e1-replay-restored.png
import json
import socket
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "Evidence"
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
NODE_IDS = ["dorm-a", "dorm-b", "dorm-c"]
CLICK_X = {"dorm-a": 0.33, "dorm-b": 0.5, "dorm-c": 0.66}

failures = []


def check(label, ok, extra=""):
    print(("PASS" if ok else "FAIL") + "  " + label + (("  [" + extra + "]") if extra else ""))
    if not ok:
        failures.append(label)


def pick_quiet_node():
    counts = {n: 0 for n in NODE_IDS}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    def on_msg(client, userdata, msg):
        try:
            p = json.loads(msg.payload.decode("utf-8"))
            if p.get("nodeId") in counts:
                counts[p["nodeId"]] += 1
        except Exception:
            pass
    c.on_message = on_msg
    c.connect(BROKER_HOST, BROKER_PORT)
    c.subscribe("dormmate/+/event")
    c.loop_start()
    time.sleep(5)
    c.loop_stop()
    c.disconnect()
    return min(NODE_IDS, key=lambda n: counts[n]), counts


def click_building(pg, node_id):
    for fx, fy in [(CLICK_X[node_id], 0.5), (CLICK_X[node_id], 0.55), (CLICK_X[node_id], 0.6), (CLICK_X[node_id], 0.45)]:
        pg.mouse.click(int(1280 * fx), int(800 * fy))
        pg.wait_for_timeout(300)
        if pg.evaluate("document.querySelector('#sideNodeId').textContent").startswith(node_id):
            return True
    return False


def main():
    print("=== B4 事件回放冒烟验证 ===")
    (EVIDENCE / "E1").mkdir(parents=True, exist_ok=True)

    try:
        s = socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=3)
        s.close()
    except OSError:
        print("请先启动 Broker（D:\\Mosquitto\\mosquitto.exe -c D:\\Mosquitto\\mosquitto.conf -v）后重试")
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    target, counts = pick_quiet_node()
    print("目标节点：" + target + "（近 5 秒事件流量 " + json.dumps(counts, ensure_ascii=False) + "）")

    m = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    m.connect(BROKER_HOST, BROKER_PORT)

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        pg.goto("http://127.0.0.1:5510/three3d/index.html")
        pg.wait_for_timeout(3000)

        # ① 注入 12 条多状态历史（3 轮循环四状态，status 字段由页面本地重算）
        cycles = [(25, 60), (16, 60), (31, 60), (25, 80)] * 3
        for t, h in cycles:
            m.publish("dormmate/" + target + "/env", json.dumps({
                "nodeId": target, "temperature": t, "humidity": h, "status": "",
                "time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": ""}, ensure_ascii=False))
            time.sleep(0.15)

        ok = click_building(pg, target)
        check("点击 " + target + " 选中", ok)
        pg.wait_for_timeout(1000)

        # ② 回放按钮可用 + 选 1× 速度（慢速防快速播完，断言窗口充足）
        btn_enabled = pg.evaluate("!document.querySelector('#replayBtn').disabled")
        check("回放按钮可用（历史≥2）", btn_enabled)
        pg.select_option("#replaySpeed", "1")

        # ③ 开始回放
        pg.click("#replayBtn")
        playing = False
        for _ in range(15):
            info = pg.evaluate("document.querySelector('#replayInfo').textContent")
            if "历史回放中" in info:
                playing = True
                break
            pg.wait_for_timeout(200)
        check("回放启动（#replayInfo=历史回放中）", playing, info if playing else "")
        btn_text = pg.evaluate("document.querySelector('#replayBtn').textContent")
        check("回放中按钮=■ 停止回放（显眼停止）", "停止回放" in btn_text, btn_text)
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-replay-playing.png"))

        # ④ 回放帧在推进（1×=500ms/帧，800ms 后索引应前进）
        info1 = pg.evaluate("document.querySelector('#replayInfo').textContent")
        pg.wait_for_timeout(800)
        info2 = pg.evaluate("document.querySelector('#replayInfo').textContent")
        check("回放帧推进（" + info1.strip() + " -> " + info2.strip() + "）", info1 != info2)

        # ⑤ 回放中发布新 env：数据照进缓存（#sideHistory 出现新记录），视觉由回放帧驱动
        m.publish("dormmate/" + target + "/env", json.dumps({
            "nodeId": target, "temperature": 31.5, "humidity": 60, "status": "偏热",
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": ""}, ensure_ascii=False))
        hist_ok = False
        for _ in range(10):
            hist = pg.evaluate("document.querySelector('#sideHistory').textContent")
            if "偏热" in hist:
                hist_ok = True
                break
            pg.wait_for_timeout(300)
        check("回放中实时数据照进缓存（#sideHistory 出现偏热新记录）", hist_ok)

        # ⑥ 回放中发布 HANDLING 事件：#sideEvent 保持实时、#replayInfo 仍回放中（用户要求 2）
        for _ in range(20):
            m.publish("dormmate/" + target + "/event", json.dumps({
                "nodeId": target, "eventId": target + "-smoke-b4", "state": "HANDLING",
                "time": time.strftime("%Y-%m-%d %H:%M:%S"), "summary": "冒烟验证：回放中事件"}, ensure_ascii=False))
            pg.wait_for_timeout(200)
            if "处理中" in pg.evaluate("document.querySelector('#sideEvent').textContent"):
                break
            pg.wait_for_timeout(100)
        side_event = pg.evaluate("document.querySelector('#sideEvent').textContent")
        info = pg.evaluate("document.querySelector('#replayInfo').textContent")
        check("回放中 #sideEvent 仍实时显示处理中", "处理中" in side_event, side_event)
        check("回放中 #replayInfo 仍=历史回放中（事件态不回放）", "历史回放中" in info, info.strip())

        # ⑦ 停止回放：info 清空、按钮复位
        pg.click("#replayBtn")
        pg.wait_for_timeout(500)
        info = pg.evaluate("document.querySelector('#replayInfo').textContent")
        btn_text = pg.evaluate("document.querySelector('#replayBtn').textContent")
        check("停止后 #replayInfo 清空", info == "", repr(info))
        check("停止后按钮复位为回放", btn_text == "回放", btn_text)

        # ⑧ 停止后侧栏恢复跟随实时新数据（发布 偏湿 -> #sideStatus 偏湿）
        side_ok = False
        for _ in range(15):
            m.publish("dormmate/" + target + "/env", json.dumps({
                "nodeId": target, "temperature": 25, "humidity": 80, "status": "偏湿",
                "time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": ""}, ensure_ascii=False))
            pg.wait_for_timeout(300)
            if pg.evaluate("document.querySelector('#sideStatus').textContent") == "偏湿":
                side_ok = True
                break
        check("停止后侧栏恢复跟随实时新数据（偏湿）", side_ok)
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-replay-restored.png"))

        b.close()

    m.disconnect()
    print("=== " + ("B4 回放验证通过" if not failures else ("，".join(failures) + " 失败")) + " ===")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
