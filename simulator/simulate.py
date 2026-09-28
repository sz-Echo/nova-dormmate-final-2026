"""DormMate M5 模拟节点发布器（simulator/simulate.py）

数据链：三个模拟节点 dorm-a / dorm-b / dorm-c 按统一 JSON（SPEC §4）定时发布到
本机 MQTT Broker（默认 127.0.0.1:1883），topic = dormmate/{nodeId}/env（SPEC §8）。
status 由 analysis/analyze.py 的 compute_status 计算（M2 已实现，零重写）；
四组回归自测复用 analysis.selftest（SPEC §6）。

A 组动作通道（SPEC §9 A2）：同时订阅 dormmate/+/action——收到 fan_on 后该节点温湿度
每步额外下降（模拟风扇/通风降温，期望 温度 −0.4 / 湿度 −0.5），fan_off 恢复随机游走；
温度降至 FAN_OFF_TEMP 自动 fan_off（模拟温控停机，避免过度降温产生"偏冷"假异常）。

用法：
  python simulator/simulate.py [--host 127.0.0.1] [--port 1883] [--interval 2.5]
  python simulator/simulate.py --selftest    # 四组回归自测后退出
Ctrl+C 停止。
"""
import argparse
import json
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

# 项目根（本文件向上两级）：nova-dormmate-final-2026/，保证 import analysis 可用
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.analyze import compute_status, selftest  # noqa: E402  # M2 同一规则实现，零重写

NODE_IDS = ["dorm-a", "dorm-b", "dorm-c"]

# 模拟数据取值范围（SPEC §3.1 合法范围 −50~50 / 0~100 的宿舍环境子集）
TEMP_RANGE = (15, 35)
HUMIDITY_RANGE = (40, 90)

# ---- A 组动作通道（SPEC §9 A2，MASTER_PLAN §7.3 S1）----
ACTION_TOPIC = "dormmate/+/action"
VALID_ACTIONS = ("fan_on", "fan_off")
# fan_on 降温参数：每步在随机游走基础上额外下降的区间（期望 温度 −0.4 / 湿度 −0.5）
FAN_TEMP_DROP = (-0.7, -0.1)
FAN_HUMIDITY_DROP = (-1.0, 0.0)
# 温度降到该值自动 fan_off（模拟温控停机，避免过度降温产生"偏冷"假异常）
FAN_OFF_TEMP = 26.0

# 注：paho-mqtt 2.x 已移除消息队列——断连时 publish 直接返回失败并丢弃，不排队；
# 故无需（也无法）设置队列上限，消息丢失情况由 publish_node 如实打印提示


def format_time(dt):
    """time 格式 YYYY-MM-DD HH:MM:SS（SPEC §4，与 analysis/analyze.py 使用的时间格式一致）。"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def build_message(node_id, temperature, humidity):
    """统一 JSON（SPEC §4）：先四舍五入到 1 位小数，status 必须用舍入后的值按规则计算，
    保证消息内数值与 status 自洽（评审修复：此前用未舍入值算 status，边界处如 29.96→发布
    30.0 但 status=正常，与 Dashboard 按发布值重算的结果矛盾）。"""
    t = round(temperature, 1)
    h = round(humidity, 1)
    return {
        "nodeId": node_id,
        "temperature": t,
        "humidity": h,
        "status": compute_status(t, h),
        "time": format_time(datetime.now()),
        "action": "",
    }


def next_value(current, low, high, step_max):
    """随机游走一步并夹回 [low, high]，保证取值始终在合法范围内。"""
    return min(max(current + random.uniform(-step_max, step_max), low), high)


# fan_state 由 on_message 网络线程写入、发布线程读取；用锁保证一致
FAN_LOCK = threading.Lock()
fan_state = {node_id: False for node_id in NODE_IDS}


def handle_action_message(client, userdata, msg):
    """动作消息校验（与 Dashboard 校验链同款思路的 Python 版）：topic 格式 → JSON 容错 →
    nodeId 与 topic 第二段一致（串线防线）→ 节点/动作值合法；非法消息丢弃并打印原因。"""
    topic = msg.topic
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != "dormmate" or parts[2] != "action":
        print(f"[动作] 非法 topic 丢弃：{topic}", flush=True)
        return
    topic_node = parts[1]
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[动作] 非法 JSON 丢弃：{msg.payload[:80]!r}（{exc}）", flush=True)
        return
    if not isinstance(payload, dict) or payload.get("nodeId") != topic_node:
        print(f"[动作] nodeId 与 topic 不符或缺失，丢弃：{topic} {payload}", flush=True)
        return
    action = payload.get("action")
    if topic_node not in NODE_IDS or action not in VALID_ACTIONS:
        print(f"[动作] 节点/动作值非法，丢弃：{payload}", flush=True)
        return
    with FAN_LOCK:
        fan_state[topic_node] = action == "fan_on"
    if action == "fan_on":
        print(f"[{format_time(datetime.now())}] 动作生效：{topic_node} 开启风扇/通风（降温趋势）", flush=True)
    else:
        print(f"[{format_time(datetime.now())}] 动作生效：{topic_node} 关闭风扇（恢复随机游走）", flush=True)


def publish_node(client, node_id, interval):
    """单节点发布循环（独立线程）：随机游走 -> 风扇降温偏置（fan_on 时）-> 统一 JSON -> 发布。"""
    topic = f"dormmate/{node_id}/env"
    temperature = random.uniform(*TEMP_RANGE)
    humidity = random.uniform(*HUMIDITY_RANGE)
    while True:
        temperature = next_value(temperature, *TEMP_RANGE, 1.5)
        humidity = next_value(humidity, *HUMIDITY_RANGE, 4.0)
        with FAN_LOCK:
            is_fan_on = fan_state[node_id]
        if is_fan_on:
            # 模拟风扇/通风降温：随机游走后额外下降（夹回合法范围）
            temperature = max(temperature + random.uniform(*FAN_TEMP_DROP), TEMP_RANGE[0])
            humidity = max(humidity + random.uniform(*FAN_HUMIDITY_DROP), HUMIDITY_RANGE[0])
            if temperature <= FAN_OFF_TEMP:
                # 模拟温控停机：避免过度降温产生"偏冷"假异常（MASTER_PLAN §7.3 S1）
                with FAN_LOCK:
                    fan_state[node_id] = False
                print(f"[{format_time(datetime.now())}] {node_id} 温度降至 {temperature:.1f}℃，自动关闭风扇", flush=True)
        message = build_message(node_id, temperature, humidity)
        payload = json.dumps(message, ensure_ascii=False)
        result = client.publish(topic, payload, qos=0)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            # Broker 未连接：paho 2.x 无离线队列，本条被丢弃，如实提示不假装已发布
            # 注意不能用 is_published()：它在失败时会抛 RuntimeError 而非返回 False（paho 2.x 实测）
            print(f"[{message['time']}] Broker 未连接，本条丢弃：{topic}", flush=True)
        else:
            print(f"[{message['time']}] {topic} -> {payload}", flush=True)
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="DormMate M5 模拟节点发布器")
    parser.add_argument("--host", default="127.0.0.1", help="Broker 地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=1883, help="Broker 端口（默认 1883）")
    parser.add_argument("--interval", type=float, default=2.5, help="每节点发布间隔秒数（默认 2.5）")
    parser.add_argument("--selftest", action="store_true", help="SPEC §6 四组回归自测后退出")
    args = parser.parse_args()

    # 参数校验（评审修复）：负数会在发布线程里抛 ValueError 静默死亡；0 会变成发布死循环
    if args.interval <= 0:
        parser.error("--interval 必须大于 0")

    if args.selftest:
        ok = selftest()  # 复用 analysis/analyze.py 的 M2 自测（同一实现）
        sys.exit(0 if ok else 1)

    # connect_async + loop_start：首次连接也由后台线程持续重试（评审修复：此前同步 connect
    # 在 Broker 未启动时直接抛 ConnectionRefusedError 崩溃退出，与"自动重连"注释不符）
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = handle_action_message  # A 组：动作通道订阅回调
    client.connect_async(args.host, args.port, keepalive=60)
    client.loop_start()
    print(f"连接 Broker {args.host}:{args.port}（未启动时自动重试，Ctrl+C 停止）…", flush=True)

    # 等待首次连接成功后再开始发布：connect_async 在后台重试，此处不阻塞进程退出路径；
    # 若直接启动发布线程，首批消息会赶在连接建立前被丢弃（评审修复实测发现）
    try:
        while not client.is_connected():
            time.sleep(0.2)
    except KeyboardInterrupt:
        client.disconnect()
        client.loop_stop()
        print("\n已停止。", flush=True)
        sys.exit(0)
    print(f"已连接，三节点开始发布（间隔 {args.interval}s）", flush=True)

    # A 组：订阅动作通道（订阅失败只提示，不阻塞发布）
    result, _ = client.subscribe(ACTION_TOPIC, qos=0)
    if result != mqtt.MQTT_ERR_SUCCESS:
        print(f"[动作] 订阅失败 {ACTION_TOPIC}（rc={result}），风扇动作将不生效", flush=True)
    else:
        print(f"已订阅动作通道 {ACTION_TOPIC}（fan_on 降温 / fan_off 恢复）", flush=True)

    threads = [
        threading.Thread(target=publish_node, args=(client, node_id, args.interval), daemon=True)
        for node_id in NODE_IDS
    ]
    for thread in threads:
        thread.start()

    try:
        # join 等待发布线程：某线程异常退出时主进程随之退出，不假装还活着（评审修复）
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        # 优雅关闭：发送 MQTT DISCONNECT 并停止网络线程（评审修复）
        client.disconnect()
        client.loop_stop()
        print("\n已停止。", flush=True)


if __name__ == "__main__":
    main()
