"""D2/D3/D5 证据采集器（V0.8R5 阶段 C6a）

按任务书 Evidence 要求，为 D2（优先关注随数据变化）/ D3（事件生命周期三端一致）/
D5（Rule/ML 对照案例）生成截图证据到 Evidence/D2、Evidence/D3、Evidence/D5。

用法：
  python simulator/capture_d.py            # 全部三组
  python simulator/capture_d.py --d2       # 只采 D2
  python simulator/capture_d.py --d3       # 只采 D3
  python simulator/capture_d.py --d5       # 只采 D5

前置：Broker + simulator + 5510 静态服务（python -m http.server 5510，项目根）已运行；
正式采集时只开一个 Dashboard（多实例会互相覆盖事件广播，UPGRADE_PLAN §8）。
复用：test_a1.GROUPS/publish_group（D2 序列）、test_upgrade 的 check_broker/check_simulator/
dorm_card/click_building/now_str（D3 流程工具），不重写既有逻辑。
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_a1 import GROUPS, publish_group  # noqa: E402  # D2 序列与发布（零重写）
from test_upgrade import (  # noqa: E402  # D3 流程工具（零重写）
    BROKER_HOST, BROKER_PORT, EVIDENCE, check_broker, check_simulator,
    click_building, dorm_card, now_str,
)

BASE = "http://127.0.0.1:5510"
TARGET = "dorm-b"   # D3 事件主角固定 dorm-b（与演示视频故事线一致）


def find_sim_pids():
    """PowerShell 查 simulate.py 进程（Win32_Process CommandLine 匹配）。"""
    ps = ('Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" | '
          "Where-Object { $_.CommandLine -like '*simulate.py*' } | "
          "Select-Object -ExpandProperty ProcessId")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, errors="replace")
    return [int(x) for x in out.stdout.split() if x.strip().isdigit()]


def kill_sim(pids):
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, text=True, errors="replace")


def start_sim():
    """后台重启 simulator（D2 采集后恢复原状态）。"""
    return subprocess.Popen([sys.executable, "simulator/simulate.py"], cwd=str(ROOT),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_d2():
    """D2：三组三节点情况 → Dashboard 优先横幅截图（优先级随数据变化）。

    simulator 实时数据（真实时间戳）会打断 test_a1 固定时间戳序列的 streak，
    故采集前暂停 simulator、采集后按原状态恢复（D2 横幅仅由序列数据驱动）。
    """
    from playwright.sync_api import sync_playwright
    print("=== D2 优先关注证据（3 组） ===", flush=True)
    sim_pids = find_sim_pids()
    if sim_pids:
        print(f"  暂停 simulator（PID {sim_pids}）以隔离序列数据…", flush=True)
        kill_sim(sim_pids)
        time.sleep(1.0)
    (EVIDENCE / "D2").mkdir(parents=True, exist_ok=True)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()
    time.sleep(0.5)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page()
        pg.goto(BASE + "/dashboard/index.html")
        for _ in range(30):
            try:
                if "已连接" in pg.locator("#connStatus").inner_text():
                    break
            except Exception:
                pass
            pg.wait_for_timeout(500)
        time.sleep(2.0)
        for g in (1, 2, 3):
            print("-- " + GROUPS[g]["name"] + " --", flush=True)
            publish_group(client, g)
            time.sleep(1.5)   # 等 priority.js 计算并渲染横幅
            path = EVIDENCE / "D2" / f"d2-priority-group{g}.png"
            pg.screenshot(path=str(path))
            print("  已保存 " + str(path), flush=True)
        b.close()
    client.disconnect()
    if sim_pids:
        print("  重启 simulator（恢复原状态）…", flush=True)
        start_sim()
        time.sleep(2.0)
    print("D2 完成", flush=True)


def run_d3():
    """D3：注入 dorm-b 偏热 → OPEN → fan_on（移动端同构）→ HANDLING → 2 条正常 → RECOVERED；
    截 Dashboard 处理中/已恢复 + 3D 徽标，广播原文归档（同一事件三端同源）。"""
    from playwright.sync_api import sync_playwright
    print("=== D3 事件生命周期证据（dorm-b） ===", flush=True)
    (EVIDENCE / "D3").mkdir(parents=True, exist_ok=True)
    events, prios = [], []
    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    def on_msg(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            return
        if msg.topic == "dormmate/priority":
            prios.append(payload)
        elif msg.topic.endswith("/event"):
            events.append(payload)
    sub.on_message = on_msg
    sub.connect(BROKER_HOST, BROKER_PORT)
    sub.subscribe("dormmate/+/event")
    sub.subscribe("dormmate/priority")
    sub.loop_start()

    m = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    m.connect(BROKER_HOST, BROKER_PORT)

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page()
        pg.goto(BASE + "/dashboard/index.html")
        for _ in range(30):
            try:
                if "已连接" in pg.locator("#connStatus").inner_text():
                    break
            except Exception:
                pass
            pg.wait_for_timeout(500)
        time.sleep(2.0)

        pg3 = b.new_page(viewport={"width": 1280, "height": 800})
        pg3.goto(BASE + "/three3d/index.html")
        pg3.wait_for_timeout(3500)
        click_building(pg3, TARGET)

        # ① 注入偏热 → OPEN
        env = {"nodeId": TARGET, "temperature": 31.5, "humidity": 60, "status": "偏热", "time": now_str(), "action": ""}
        m.publish("dormmate/" + TARGET + "/env", json.dumps(env, ensure_ascii=False))
        time.sleep(2.0)

        # ② fan_on（移动端同构 payload，E3 联动）→ HANDLING
        action_state = {"nodeId": TARGET, "action": "fan_on", "actionTime": now_str()}
        m.publish("dormmate/" + TARGET + "/action", json.dumps(action_state, ensure_ascii=False))
        for _ in range(10):
            card = dorm_card(pg, TARGET)
            if card and "处理中" in card["status"]:
                break
            pg.wait_for_timeout(300)
        pg.screenshot(path=str(EVIDENCE / "D3" / "d3-handling-dashboard.png"))
        pg3.wait_for_timeout(1200)   # 等 3D 收到 HANDLING 广播渲染徽标/风扇
        pg3.screenshot(path=str(EVIDENCE / "D3" / "d3-handling-3d.png"))
        print("  handling 截图完成", flush=True)

        # ③ 2 条正常新数据 → RECOVERED（恢复仅由新数据触发）
        for i in range(2):
            env = {"nodeId": TARGET, "temperature": 25.0, "humidity": 60, "status": "正常", "time": now_str(), "action": ""}
            m.publish("dormmate/" + TARGET + "/env", json.dumps(env, ensure_ascii=False))
            time.sleep(1.0)
        pg.screenshot(path=str(EVIDENCE / "D3" / "d3-recovered-dashboard.png"))   # 瞬态：恢复后立即截
        pg3.wait_for_timeout(800)
        pg3.screenshot(path=str(EVIDENCE / "D3" / "d3-recovered-3d.png"))

        # ④ 广播原文归档（与 E3 同一口径：event + priority）
        lines = []
        for e in events:
            if e.get("nodeId") == TARGET:
                lines.append("event " + json.dumps(e, ensure_ascii=False))
        for pr in prios:
            lines.append("priority " + json.dumps(pr, ensure_ascii=False))
        (EVIDENCE / "D3" / "d3-broadcast-messages.txt").write_text("\n".join(lines), encoding="utf-8")
        print("  广播原文 " + str(len(lines)) + " 条已归档", flush=True)
        b.close()
    m.disconnect()
    sub.loop_stop()
    print("D3 完成", flush=True)


def run_d5():
    """D5：重跑 c_ml 对照 + analyze.py → report.html ML 区截图 + c_compare.json 副本。"""
    from playwright.sync_api import sync_playwright
    print("=== D5 Rule/ML 对照证据 ===", flush=True)
    (EVIDENCE / "D5").mkdir(parents=True, exist_ok=True)
    r1 = subprocess.run([sys.executable, "analysis/c_ml.py"], cwd=str(ROOT),
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r1.stdout[-500:] if r1.stdout else "", flush=True)
    r2 = subprocess.run([sys.executable, "analysis/analyze.py"], cwd=str(ROOT),
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r2.stdout[-300:] if r2.stdout else "") + (r2.stderr[-200:] if r2.stderr else ""), flush=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1280, "height": 1600})
        pg.goto("file:///" + str(ROOT / "data" / "report.html").replace("\\", "/"))
        try:
            ml_heading = pg.locator("text=ML 异常分析").first
            ml_heading.scroll_into_view_if_needed()
            pg.wait_for_timeout(500)
        except Exception as e:
            print("  INFO 未定位到 ML 区标题，截整页：" + str(e), flush=True)
        pg.screenshot(path=str(EVIDENCE / "D5" / "d5-report-ml-section.png"), full_page=True)
        b.close()
    shutil.copyfile(str(ROOT / "data" / "c_compare.json"),
                    str(EVIDENCE / "D5" / "d5-c-compare.json"))
    print("D5 完成", flush=True)


def main():
    parser = argparse.ArgumentParser(description="D2/D3/D5 证据采集器（阶段 C6a）")
    parser.add_argument("--d2", action="store_true")
    parser.add_argument("--d3", action="store_true")
    parser.add_argument("--d5", action="store_true")
    args = parser.parse_args()
    only = [k for k in ("d2", "d3", "d5") if getattr(args, k)]
    if not only:
        only = ["d2", "d3", "d5"]

    print("=== DormMate V0.8R5 阶段 C6a 证据采集 ===", flush=True)
    if not check_broker():
        print("请先启动 Broker（D:\\Mosquitto\\mosquitto.exe -c D:\\Mosquitto\\mosquitto.conf -v）后重试")
        sys.exit(1)
    for k in only:
        {"d2": run_d2, "d3": run_d3, "d5": run_d5}[k]()
    print("=== 证据采集完成 ===", flush=True)


if __name__ == "__main__":
    main()
