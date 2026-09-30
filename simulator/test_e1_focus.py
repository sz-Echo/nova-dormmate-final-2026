#!/usr/bin/env python3
# DormMate V0.8R5 阶段 B（B3）：3D 镜头聚焦动画 冒烟验证
# 流程：
#   ① 交互闸门：全新页面发布优先 dorm-b -> 1.5s 后 focusNode 仍空（首次交互前镜头不动）
#   ② 点击 dorm-c -> 聚焦动画进行（focusAnimating=1）-> 到达（focusNode=dorm-c）
#   ③ 拖拽中止：点击 dorm-a 启动动画 -> 立即 mouse.down 画布 -> 1s 后 focusAnimating 空且 focusNode 仍=dorm-c（动画被中止未完成）
#   ④ 优先自动聚焦：闸门已开，发布优先 dorm-a -> focusNode=dorm-a
# 前置：Broker 与 5510 静态服务已运行（simulator 非必需）
# 运行：python simulator/test_e1_focus.py（exit code 0 = 通过）
# 证据：Evidence/E1/e1-focus-default.png、e1-focus-dorm-c-mid.png、e1-focus-dorm-c.png、e1-priority-focus-dorm-a.png
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
CLICK_X = {"dorm-a": 0.33, "dorm-b": 0.5, "dorm-c": 0.66}

failures = []


def check(label, ok, extra=""):
    print(("PASS" if ok else "FAIL") + "  " + label + (("  [" + extra + "]") if extra else ""))
    if not ok:
        failures.append(label)


def hook(pg, key):
    return pg.evaluate("document.body.dataset['" + key + "'] || ''")


def click_building(pg, node_id):
    # 与 test_upgrade.py 同款：默认机位下分数坐标点击（选中是同步的，断言不受动画影响）
    for fx, fy in [(CLICK_X[node_id], 0.5), (CLICK_X[node_id], 0.55), (CLICK_X[node_id], 0.6), (CLICK_X[node_id], 0.45)]:
        pg.mouse.click(int(1280 * fx), int(800 * fy))
        pg.wait_for_timeout(300)
        if pg.evaluate("document.querySelector('#sideNodeId').textContent").startswith(node_id):
            return True
    return False


def poll(pg, key, want, tries, step_ms=300):
    for _ in range(tries):
        if hook(pg, key) == want:
            return True
        pg.wait_for_timeout(step_ms)
    return False


def changed_ratio(a_bytes, b_bytes, threshold=40, step=2):
    # 两帧差异像素占比（拖拽接管证明：镜头旋转 -> 大面积像素变化，远大于粒子动画噪声）
    if Image is None:
        return -1
    ia = Image.open(io.BytesIO(a_bytes)).convert("RGB")
    ib = Image.open(io.BytesIO(b_bytes)).convert("RGB")
    w, h = ia.size
    pa, pb = ia.load(), ib.load()
    changed = 0
    total = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            ra, ga, ba = pa[x, y]
            rb, gb, bb = pb[x, y]
            if abs(ra - rb) + abs(ga - gb) + abs(ba - bb) > threshold:
                changed += 1
            total += 1
    return changed / total


def main():
    print("=== B3 镜头聚焦冒烟验证 ===")
    (EVIDENCE / "E1").mkdir(parents=True, exist_ok=True)

    try:
        s = socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=3)
        s.close()
    except OSError:
        print("请先启动 Broker（D:\\Mosquitto\\mosquitto.exe -c D:\\Mosquitto\\mosquitto.conf -v）后重试")
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    m = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    m.connect(BROKER_HOST, BROKER_PORT)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        pg.goto("http://127.0.0.1:5510/three3d/index.html")
        pg.wait_for_timeout(3000)

        # ① 交互闸门：首次交互前优先变化只出光环，镜头不动
        m.publish("dormmate/priority", json.dumps(
            {"nodeId": "dorm-b", "reason": "聚焦验证：闸门测试", "time": stamp}, ensure_ascii=False))
        pg.wait_for_timeout(1500)
        check("闸门：首次交互前优先变化不移动镜头（focusNode 空）", hook(pg, "focusNode") == "",
              "focusNode=" + repr(hook(pg, "focusNode")))
        m.publish("dormmate/priority", json.dumps(
            {"nodeId": "", "reason": "聚焦验证：清空", "time": stamp}, ensure_ascii=False))

        # ② 点击 dorm-c -> 动画 -> 到达
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-focus-default.png"))
        ok = click_building(pg, "dorm-c")
        check("点击 dorm-c 选中", ok)
        in_flight = poll(pg, "focusAnimating", "1", 10, 100)
        if in_flight:
            pg.screenshot(path=str(EVIDENCE / "E1" / "e1-focus-dorm-c-mid.png"))   # 飞行中途证据
        check("点击后聚焦动画进行（focusAnimating=1）", in_flight)
        arrived = poll(pg, "focusNode", "dorm-c", 20, 300)
        check("镜头到达 dorm-c（focusNode=dorm-c）", arrived, hook(pg, "focusNode"))
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-focus-dorm-c.png"))

        # ③ 拖拽中止：点击空白地面回总览触发飞行（本地触发，无外部优先广播竞态）-> 飞行中拖拽 -> 中止、未到达；
        #    像素级证明 OrbitControls 接管：拖拽前后两帧差异占比远大于粒子噪声。
        #    注：优先变化触发的飞行用同一 focusAnim 通路，中止语义一致（④ 验证优先自动聚焦本体）
        pg.mouse.click(150, 700)   # 聚焦 dorm-c 时左下角为地面/空白（若命中某楼则选中该楼，同样启动飞行，断言不依赖目标）
        in_flight = poll(pg, "focusAnimating", "1", 10, 100)
        check("点击空白触发聚焦动画（focusAnimating=1）", in_flight)
        pre_drag = pg.screenshot()
        pg.mouse.move(640, 400)
        pg.mouse.down()
        pg.mouse.move(700, 450)   # 拖拽 >5px：既是 OrbitControls 旋转（接管验证），又不构成点击（不会重选楼）
        pg.wait_for_timeout(200)
        pg.mouse.up()
        pg.wait_for_timeout(300)
        check("拖拽中止：动画已停（focusAnimating 空）", hook(pg, "focusAnimating") == "",
              "focusAnimating=" + repr(hook(pg, "focusAnimating")))
        pg.wait_for_timeout(700)
        post_drag = pg.screenshot()
        check("拖拽中止：镜头未到达新目标（focusNode 仍=dorm-c）", hook(pg, "focusNode") == "dorm-c",
              "focusNode=" + hook(pg, "focusNode") + " focusTarget=" + hook(pg, "focusTarget"))
        ratio = changed_ratio(pre_drag, post_drag)
        check("拖拽接管：OrbitControls 旋转了镜头（拖拽前后帧差异=" + str(ratio) + "）",
              ratio > 0.03)

        # ④ 优先自动聚焦（闸门已开）：发布优先 dorm-b -> 镜头自动飞过去（持续重发防其他 Dashboard 覆盖）
        arrived = False
        for _ in range(20):
            m.publish("dormmate/priority", json.dumps(
                {"nodeId": "dorm-b", "reason": "聚焦验证：优先变化自动聚焦", "time": stamp}, ensure_ascii=False))
            pg.wait_for_timeout(300)
            if hook(pg, "focusNode") == "dorm-b":
                arrived = True
                break
        check("优先变化自动聚焦到 dorm-b（闸门已开）", arrived, hook(pg, "focusNode"))
        pg.screenshot(path=str(EVIDENCE / "E1" / "e1-priority-focus-dorm-b.png"))
        m.publish("dormmate/priority", json.dumps(
            {"nodeId": "", "reason": "聚焦验证：清空", "time": stamp}, ensure_ascii=False))

        b.close()

    m.disconnect()
    print("=== " + ("B3 聚焦验证通过" if not failures else ("，".join(failures) + " 失败")) + " ===")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
