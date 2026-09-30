#!/usr/bin/env python3
# DormMate V0.8R5 阶段 B 一键验收（E1 3D 增强 + E2 语音/拍照交互）
# 编排运行 5 个 B 冒烟套件（各自断言+截图归档到 Evidence/E1、Evidence/E2），全部通过才 exit 0：
#   ① test_e1_halo.py    E1⑤ 优先光环（钩子+像素差分）
#   ② test_e1_badge.py   E1⑥ 事件徽标+处理中粒子（标牌 canvas 像素直读）
#   ③ test_e1_focus.py   E1⑦ 镜头聚焦（飞行/到达/拖拽中止/优先自动聚焦，交互闸门）
#   ④ test_e1_replay.py  E1⑦ 事件回放（历史帧驱动+实时隔离+停止恢复）
#   ⑤ test_e2_voice.py   E2 语音命令条（查看/朗读/拍照/开风扇/未匹配，完整交互链）
# 前置：Broker（127.0.0.1:1883）已运行；5510 端口静态服务已运行（python -m http.server 5510，项目根）
# 注意：不要用 VS Code Live Server 的 5500 跑本脚本——Live Server 会因证据文件写入而重载页面，打断测试
# 运行：python simulator/test_stage_b.py（exit code 0 = 阶段 B 全过）
import json
import socket
import subprocess
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
STATIC_URL = "http://127.0.0.1:5510/dashboard/index.html"

SUITES = [
    "test_e1_halo.py",
    "test_e1_badge.py",
    "test_e1_focus.py",
    "test_e1_replay.py",
    "test_e2_voice.py"
]

failures = []


def check(label, ok, extra=""):
    print(("PASS" if ok else "FAIL") + "  " + label + (("  [" + extra + "]") if extra else ""))
    if not ok:
        failures.append(label)


def check_broker():
    try:
        s = socket.create_connection((BROKER_HOST, BROKER_PORT), timeout=3)
        s.close()
        return True
    except OSError:
        return False


def check_static():
    import urllib.request
    try:
        with urllib.request.urlopen(STATIC_URL, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def check_other_dashboards():
    got = []
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    def on_msg(client, userdata, msg):
        got.append(msg.topic)
    c.on_message = on_msg
    c.connect(BROKER_HOST, BROKER_PORT)
    c.subscribe("dormmate/+/event")
    c.subscribe("dormmate/priority")
    c.loop_start()
    time.sleep(3)
    c.loop_stop()
    c.disconnect()
    return len(got)


def run_suite(name):
    proc = subprocess.run(
        ["python", str(ROOT / "simulator" / name)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    return proc.returncode == 0


def print_checklist():
    # 阶段 B 验收标准逐条对照（UPGRADE_PLAN §5 line 189）：E1 最低线 7 条、E2 最低线 6 条
    print("--- 阶段 B 验收标准逐条对照 ---")
    e1 = [
        ("E1① ≥3 宿舍区域与 nodeId 明确映射", "C01 已有：三栋楼 x=-8/0/8 与 dorm-a/b/c 一一对应（three3d/app.js buildDorm）"),
        ("E1② 3D 中区分并选择不同节点", "C01 已有：raycaster 点击选中环+高亮（selectDorm）"),
        ("E1③ ≥2 类对象随状态动态变化", "C01 已有：楼体色/指示球/粒子/标牌/风扇/窗 6 类（updateScene/setDormStatus）"),
        ("E1④ 新消息到达 3D 无需刷新即更新", "C01 已有：MQTT 订阅实时驱动（handleMessage→updateScene）"),
        ("E1⑤ 优先关注节点在 3D 中明显表达", "B1 光环：setPriorityHalo 橙色呼吸光环（test_e1_halo.py 钩子+像素差分）"),
        ("E1⑥ 处理中/已恢复至少一种状态在 3D 中体现", "B2 徽标：标牌右上角事件徽标 处理中橙/已恢复绿 + 处理中粒子加速（test_e1_badge.py canvas 像素直读）"),
        ("E1⑦ ≥1 项明显展示效果的交互", "B3 镜头聚焦飞行+拖拽中止（test_e1_focus.py）；B4 事件回放 1×/4×/8×（test_e1_replay.py）"),
    ]
    e2 = [
        ("E2① ASR ≥2 条有意义指令", "B5 五条：查看 dorm-x / 朗读状态 / 拍照 / 开启风扇 / 关闭风扇（test_e2_voice.py）"),
        ("E2② ≥1 条语音指令真实改变操作对象或触发已有功能", "「查看 dorm-b」切换选中+tab；「开启风扇」paho 实测收到 fan_on 动作"),
        ("E2③ 朗读内容来自当前真实节点或事件状态", "speakSelectedNode 读选中节点最新 MQTT 记录；dataset.lastSpoken 断言含 dorm-b/温度/偏热/31.5"),
        ("E2④ ≥1 张与当前节点/事件关联的快照", "拍照快照文件名含 nodeId+eventId，关联事件草稿/定稿记录"),
        ("E2⑤ 快照能说明节点/时间/状态", "快照顶部黑条叠加「nodeId · time · status」白字"),
        ("E2⑥ ≥1 条完整交互链（语音选择→朗读→记录现场）", "test_e2_voice.py ⑥：查看 dorm-b→朗读→拍照→恢复定稿→事件卡片含快照引用"),
    ]
    for t, ev in e1:
        print("  [E1] " + t + " — " + ev)
    for t, ev in e2:
        print("  [E2] " + t + " — " + ev)


def main():
    print("=== DormMate V0.8R5 阶段 B 验收（E1 3D 增强 + E2 语音/拍照）===")
    # 用户要求 4：先建证据目录，避免截图保存报错
    (EVIDENCE / "E1").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "E2").mkdir(parents=True, exist_ok=True)

    check("前置：Broker 已运行（127.0.0.1:1883）", check_broker())
    check("前置：5510 静态服务已运行（" + STATIC_URL + "）", check_static())
    if not failures:
        other = check_other_dashboards()
        if other > 0:
            print("提示：检测到其他 Dashboard 实例在广播事件/优先消息（3 秒内 " + str(other) +
                  " 条）——多实例共享 Broker 会互相覆盖广播；正式演示只开一个 Dashboard。断言已做抗干扰处理，继续执行。")
        for name in SUITES:
            print("--- 套件 " + name + " ---")
            check("套件 " + name, run_suite(name))
    print_checklist()
    print("=== " + ("阶段 B 验收全部通过" if not failures else ("，".join(failures) + " 失败")) + " ===")
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
