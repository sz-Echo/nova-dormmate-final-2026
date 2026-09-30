#!/usr/bin/env python3
# DormMate V0.8R5 阶段 B（B1）：3D 优先光环冒烟验证
# 流程：发布 dormmate/priority(dorm-b) -> 3D 页面 dataset.priorityHalo == "dorm-b"
#       -> 点击 dorm-b 楼（光环+选中环并存截图）-> 发布空 nodeId -> 光环清除
# 前置：Broker（127.0.0.1:1883）与 5510 静态服务已运行（simulator 非必需）
# 运行：python simulator/test_e1_halo.py（exit code 0 = 通过）
# 证据：Evidence/E1/e1-priority-halo-a.png、e1-priority-halo-b.png
import io
import json
import socket
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

try:
    from PIL import Image
except Exception:
    Image = None

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "Evidence"
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883

failures = []


def check(label, ok, extra=""):
    print(("PASS" if ok else "FAIL") + "  " + label + (("  [" + extra + "]") if extra else ""))
    if not ok:
        failures.append(label)


def count_orange_tint(off_bytes, on_bytes, x0, y0, x1, y1):
    # 差分着色签名：光环橙叠加在浅色背景上会被稀释成淡色，直接比色不可靠；
    # 改为统计「G、B 明显下降且 R 基本不降」的像素（橙色混入的专属特征），抗背景与脉冲相位
    if Image is None:
        return -1
    img_off = Image.open(io.BytesIO(off_bytes)).convert("RGB")
    img_on = Image.open(io.BytesIO(on_bytes)).convert("RGB")
    w, h = img_on.size
    box = (int(w * x0), int(h * y0), int(w * x1), int(h * y1))
    po = img_off.crop(box).load()
    pn = img_on.crop(box).load()
    bw, bh = img_on.crop(box).size
    count = 0
    for y in range(0, bh, 2):
        for x in range(0, bw, 2):
            ro, go, bo = po[x, y]
            rn, gn, bn = pn[x, y]
            if rn - ro > -30 and gn - go < -30 and bn - bo < -30:
                count += 1
    return count


def main():
    print("=== B1 优先光环冒烟验证 ===")
    (EVIDENCE / "E1").mkdir(parents=True, exist_ok=True)

    # 前置：Broker
    try:
        s = socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=3)
        s.close()
    except OSError:
        print("请先启动 Broker（D:\\Mosquitto\\mosquitto.exe -c D:\\Mosquitto\\mosquitto.conf -v）后重试")
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    m = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    m.connect(BROKER_HOST, BROKER_PORT)

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        pg.goto("http://127.0.0.1:5510/three3d/index.html")
        pg.wait_for_timeout(3000)

        # ① 发布优先 dorm-b -> 光环钩子
        m.publish("dormmate/priority", json.dumps(
            {"nodeId": "dorm-b", "reason": "冒烟验证：优先关注 dorm-b", "time": time.strftime("%Y-%m-%d %H:%M:%S")},
            ensure_ascii=False))
        halo = ""
        for _ in range(10):
            halo = pg.evaluate("document.body.dataset.priorityHalo || ''")
            if halo == "dorm-b":
                break
            pg.wait_for_timeout(500)
        check("发布优先 dorm-b 后 3D 光环钩子=dorm-b", halo == "dorm-b", halo)
        pg.wait_for_timeout(1500)   # 等脉冲跑几拍，截图里有光环
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-priority-halo-a.png"))

        # ② 点击 dorm-b 楼 -> 选中环与光环并存
        for fx, fy in [(0.5, 0.5), (0.5, 0.55), (0.5, 0.6), (0.5, 0.45)]:
            pg.mouse.click(int(1280 * fx), int(800 * fy))
            pg.wait_for_timeout(400)
            if pg.evaluate("document.querySelector('#sideNodeId').textContent").startswith("dorm-b"):
                break
        check("点击 dorm-b 楼后侧栏选中（光环+选中环并存）",
              pg.evaluate("document.querySelector('#sideNodeId').textContent").startswith("dorm-b"))
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-priority-halo-b.png"))

        # ③ 发布空 nodeId -> 光环清除
        m.publish("dormmate/priority", json.dumps(
            {"nodeId": "", "reason": "冒烟验证：全部正常，无需优先关注", "time": time.strftime("%Y-%m-%d %H:%M:%S")},
            ensure_ascii=False))
        cleared = ""
        for _ in range(10):
            cleared = pg.evaluate("document.body.dataset.priorityHalo || ''")
            if cleared == "":
                break
            pg.wait_for_timeout(500)
        check("发布空 nodeId 后光环清除", cleared == "", repr(cleared))

        # ④ 像素级验证：其他 Dashboard 可能持续广播优先消息覆盖本脚本发布（演示只开一个的已知干扰），
        #    故截取瞬间持续重发、hook 吻合才截图；再以差分着色签名证明光环真实渲染
        def capture_with(payload, want):
            for _ in range(40):
                m.publish("dormmate/priority", json.dumps(payload, ensure_ascii=False))
                pg.wait_for_timeout(200)
                if pg.evaluate("document.body.dataset.priorityHalo || ''") == want:
                    return pg.screenshot()
                pg.wait_for_timeout(100)
            return None

        off_bytes = capture_with(
            {"nodeId": "", "reason": "像素验证：清空", "time": time.strftime("%Y-%m-%d %H:%M:%S")}, "")
        on_bytes = capture_with(
            {"nodeId": "dorm-b", "reason": "像素验证：优先 dorm-b", "time": time.strftime("%Y-%m-%d %H:%M:%S")}, "dorm-b")
        if off_bytes is None or on_bytes is None:
            check("像素级：光环开/关截图均成功捕获", False, "off=" + str(off_bytes is not None) + " on=" + str(on_bytes is not None))
        elif Image is None:
            print("INFO  PIL 不可用，跳过像素级验证（钩子断言已覆盖）")
        else:
            tint_n = count_orange_tint(off_bytes, on_bytes, 0.25, 0.40, 0.75, 0.85)
            check("像素级：光环开启后楼底地面带出现橙色着色（差分签名=" + str(tint_n) + "）", tint_n > 300)

        b.close()

    m.disconnect()
    print("=== " + ("B1 光环验证通过" if not failures else ("，".join(failures) + " 失败")) + " ===")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
