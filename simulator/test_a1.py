"""DormMate A S2 现场演示脚本（simulator/test_a1.py）

按 SPEC §9 A1 三组三节点情况向 dormmate/{nodeId}/env 发布预设序列，供 Dashboard
"A1 优先关注"横幅现场验收（Dashboard 端由 priority.js computePriority 程序计算）。

用法：
  python simulator/test_a1.py --group 1     # 组① 只有 dorm-b 异常（偏热 20 分钟）
  python simulator/test_a1.py --group 2     # 组② dorm-b 偏热 20 分钟、dorm-c 偏湿 5 分钟
  python simulator/test_a1.py --group 3     # 组③ 三节点都异常：时长相同比次数（dorm-b 次数多）
  python simulator/test_a1.py --group 4     # 组③b 三节点都异常：全相同走 nodeId 顺序（dorm-a）
  python simulator/test_a1.py --group all   # 按顺序全部演示

每条消息 time 用固定时间戳（2026-09-28 20:xx），保证"连续异常时长"可精确核对
（组① 20 分钟 / 组② 20 与 5 分钟 / 组③ 各 5 分钟）。
"""
import argparse
import json
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

# 项目根（本文件向上两级），保证 import analysis 可用
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.analyze import compute_status  # noqa: E402  # 统一规则零重写（SPEC §6）

NODE_IDS = ["dorm-a", "dorm-b", "dorm-c"]
DATE = "2026-09-28"


def row(node_id, hhmmss, temperature, humidity):
    """统一 JSON 六字段；status 由规则计算（SPEC §4 禁手填）。"""
    return {
        "nodeId": node_id,
        "temperature": temperature,
        "humidity": humidity,
        "status": compute_status(temperature, humidity),
        "time": DATE + " " + hhmmss,
        "action": "",
    }


def norm(node_id, times):
    return [row(node_id, t, 25, 60) for t in times]


def hot(node_id, times):
    return [row(node_id, t, 31, 60) for t in times]


def wet(node_id, times):
    return [row(node_id, t, 25, 80) for t in times]


def cold(node_id, times):
    return [row(node_id, t, 16, 60) for t in times]


GROUPS = {
    1: {
        "name": "组① 只有 dorm-b 异常（偏热 20 分钟）→ 期望优先 dorm-b",
        "rows": (
            norm("dorm-a", ["20:20:00", "20:25:00", "20:30:00"])
            + hot("dorm-b", ["20:10:00", "20:15:00", "20:20:00", "20:25:00", "20:30:00"])
            + norm("dorm-c", ["20:20:00", "20:25:00", "20:30:00"])
        ),
    },
    2: {
        "name": "组② dorm-b 偏热 20 分钟、dorm-c 偏湿 5 分钟 → 期望优先 dorm-b",
        "rows": (
            norm("dorm-a", ["20:20:00", "20:25:00", "20:30:00"])
            + hot("dorm-b", ["20:10:00", "20:15:00", "20:20:00", "20:25:00", "20:30:00"])
            + wet("dorm-c", ["20:25:00", "20:30:00"])
        ),
    },
    3: {
        "name": "组③a 三节点都异常、时长相同（各 5 分钟）→ 期望次数兜底优先 dorm-b（异常 4 条）",
        "rows": (
            cold("dorm-a", ["20:00:00"]) + norm("dorm-a", ["20:05:00"]) + cold("dorm-a", ["20:25:00", "20:30:00"])
            + hot("dorm-b", ["19:58:00", "20:00:00"]) + norm("dorm-b", ["20:05:00"]) + hot("dorm-b", ["20:25:00", "20:30:00"])
            + wet("dorm-c", ["20:00:00"]) + norm("dorm-c", ["20:05:00"]) + wet("dorm-c", ["20:25:00", "20:30:00"])
        ),
    },
    4: {
        "name": "组③b 三节点都异常、时长/次数全相同 → 期望 nodeId 顺序兜底 dorm-a",
        "rows": (
            cold("dorm-a", ["20:00:00"]) + norm("dorm-a", ["20:05:00"]) + cold("dorm-a", ["20:25:00", "20:30:00"])
            + hot("dorm-b", ["20:00:00"]) + norm("dorm-b", ["20:05:00"]) + hot("dorm-b", ["20:25:00", "20:30:00"])
            + wet("dorm-c", ["20:00:00"]) + norm("dorm-c", ["20:05:00"]) + wet("dorm-c", ["20:25:00", "20:30:00"])
        ),
    },
}


def publish_group(client, group):
    info = GROUPS[group]
    print("=== " + info["name"] + " ===", flush=True)
    for message in info["rows"]:
        topic = f"dormmate/{message['nodeId']}/env"
        payload = json.dumps(message, ensure_ascii=False)
        client.publish(topic, payload, qos=0)
        print(f"{topic} -> {payload}", flush=True)
        time.sleep(0.3)


def main():
    parser = argparse.ArgumentParser(description="A1 优先关注现场演示（SPEC §9 A1 三组三节点数据）")
    parser.add_argument("--group", required=True, help="1|2|3|4|all")
    parser.add_argument("--host", default="127.0.0.1", help="Broker 地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=1883, help="Broker 端口（默认 1883）")
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()
    print(f"已连接 Broker {args.host}:{args.port}（Dashboard 需已打开并连接 8083）", flush=True)

    groups = list(range(1, 5)) if args.group == "all" else [int(args.group)]
    if any(g not in GROUPS for g in groups):
        parser.error("--group 取值：1|2|3|4|all")
    for g in groups:
        publish_group(client, g)
        time.sleep(1.0)
    print("演示完成。Dashboard 优先关注横幅应逐组显示对应结果。", flush=True)
    client.disconnect()


if __name__ == "__main__":
    main()
