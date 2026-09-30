#!/usr/bin/env python3
# DormMate V0.8R5 阶段 B（B2）：3D 事件徽标 + 处理中粒子 冒烟验证
# 流程：选安静节点 -> 发布 HANDLING 事件 -> 钩子 dataset.eventBadge 断言 + 标牌 canvas 徽标像素直读（橙）
#       -> 发布 RECOVERED -> 钩子 + 徽标像素（绿）
# 像素直读：createSign 把隐藏 canvas 挂在 DOM（#signCanvas-{nodeId}），getImageData 读徽标四角
# 前置：Broker 与 5510 静态服务已运行（simulator 非必需）
# 运行：python simulator/test_e1_badge.py（exit code 0 = 通过）
# 证据：Evidence/E1/e1-event-badge-handling.png、e1-event-badge-recovered.png
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

failures = []


def check(label, ok, extra=""):
    print(("PASS" if ok else "FAIL") + "  " + label + (("  [" + extra + "]") if extra else ""))
    if not ok:
        failures.append(label)


def pick_quiet_node():
    # 监听 5 秒事件流量，选最近无事件广播的节点（避开其他 Dashboard/用户正在操作的节点）
    counts = {n: 0 for n in NODE_IDS}
    got = []
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


def read_badge_pixels(pg, node_id):
    # 读徽标四角（fillRect 352,12,148,46 内、避开中央文字）像素，返回 [{r,g,b}, ...]
    return pg.evaluate("""(id) => {
      const cv = document.getElementById("signCanvas-" + id);
      if (!cv) return null;
      const ctx = cv.getContext("2d");
      const pts = [[358, 16], [358, 50], [470, 16], [470, 50]];
      return pts.map(p => {
        const d = ctx.getImageData(p[0], p[1], 1, 1).data;
        return [d[0], d[1], d[2]];
      });
    }""", node_id)


def near(c, target, tol=25):
    return abs(c[0] - target[0]) <= tol and abs(c[1] - target[1]) <= tol and abs(c[2] - target[2]) <= tol


def main():
    print("=== B2 事件徽标冒烟验证 ===")
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
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        pg.goto("http://127.0.0.1:5510/three3d/index.html")
        pg.wait_for_timeout(3000)

        # 初始：无事件时徽标区域应为白底。
        # 采样点避开标题文字：标题 42px bold 居中约 x130~380、y40~70，四角中 (358,50) 会压字，故只取
        # (358,16)、(470,16)、(470,50) 三个安全点
        init_px = read_badge_pixels(pg, target)
        safe = [init_px[0], init_px[2], init_px[3]] if init_px else None
        check("初始无事件时徽标区为白底（3 安全点）", safe is not None and all(near(c, (255, 255, 255), 15) for c in safe),
              str(init_px))

        # ① HANDLING -> 钩子 + 徽标橙 0xe67e22=(230,126,34)
        hook = ""
        for _ in range(40):
            m.publish("dormmate/" + target + "/event", json.dumps({
                "nodeId": target, "eventId": target + "-smoke-b2", "state": "HANDLING",
                "time": stamp, "summary": "冒烟验证：已开启风扇，处理中"}, ensure_ascii=False))
            pg.wait_for_timeout(200)
            hook = pg.evaluate("document.body.dataset.eventBadge || ''")
            if hook == target + "|HANDLING":
                break
            pg.wait_for_timeout(100)
        check("HANDLING 事件钩子=" + target + "|HANDLING", hook == target + "|HANDLING", hook)
        # 标牌重绘只在新 env 或事件变化时触发，稍等一帧再读像素
        pg.wait_for_timeout(300)
        px = read_badge_pixels(pg, target)
        ok_orange = px is not None and all(near(c, (230, 126, 34)) for c in px)
        check("标牌徽标四角=处理中橙色", ok_orange, str(px))
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-event-badge-handling.png"))

        # ② RECOVERED -> 钩子 + 徽标绿 0x27ae60=(39,174,96)
        hook = ""
        for _ in range(40):
            m.publish("dormmate/" + target + "/event", json.dumps({
                "nodeId": target, "eventId": target + "-smoke-b2", "state": "RECOVERED",
                "time": stamp, "summary": "冒烟验证：恢复正常"}, ensure_ascii=False))
            pg.wait_for_timeout(200)
            hook = pg.evaluate("document.body.dataset.eventBadge || ''")
            if hook == target + "|RECOVERED":
                break
            pg.wait_for_timeout(100)
        check("RECOVERED 事件钩子=" + target + "|RECOVERED", hook == target + "|RECOVERED", hook)
        pg.wait_for_timeout(300)
        px = read_badge_pixels(pg, target)
        ok_green = px is not None and all(near(c, (39, 174, 96)) for c in px)
        check("标牌徽标四角=已恢复绿色", ok_green, str(px))
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-event-badge-recovered.png"))

        b.close()

    m.disconnect()
    print("=== " + ("B2 徽标验证通过" if not failures else ("，".join(failures) + " 失败")) + " ===")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
