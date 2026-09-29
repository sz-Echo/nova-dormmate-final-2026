"""DormMate B S3 模拟日数据生成器（analysis/make_day_data.py）

程序生成"一天"的三节点模拟数据：每节点一个 CSV（SPEC §5 最小 4 列，UTF-8）+ events.json
（≥2 条完整事件，A4 九字段口径）。数据与事件全部由本脚本程序产出（B 组：内容程序生成，禁止手改）；
换 seed 产出不同数据 → 今日摘要必须不同（B3 完成线：换数据重新生成）。

用法：
  python analysis/make_day_data.py --out data/sim-day-1 --seed 1
  python analysis/make_day_data.py --out data/sim-day-2 --seed 2
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.analyze import compute_status  # noqa: E402  # 统一规则零重写（SPEC §6）

NODES = ["dorm-a", "dorm-b", "dorm-c"]
DAY = "2026-09-28"


def row(node_id, hhmmss, temperature, humidity):
    """SPEC §5 最小 4 列；status 必须由规则计算（禁手填）。"""
    t = round(temperature, 1)
    h = round(humidity, 1)
    return {
        "nodeId": node_id,
        "time": DAY + " " + hhmmss,
        "temperature": t,
        "humidity": h,
        "status": compute_status(t, h),
    }


def normal_stretch(node_id, start_min, end_min, step_min, rng):
    """正常时段（24~26℃ / 50~60%）。"""
    rows = []
    t = start_min
    while t <= end_min:
        rows.append(row(node_id, f"{t // 60:02d}:{t % 60:02d}:00", rng.uniform(24.2, 25.8), rng.uniform(50, 60)))
        t += step_min
    return rows


def write_node_csv(day_dir, node_id, rows):
    path = day_dir / f"{node_id}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "temperature", "humidity", "status"])
        for r in rows:
            writer.writerow([r["time"], r["temperature"], r["humidity"], r["status"]])
    return path


def make_event(node_id, start, problem, duration_min, action_time, recover_time, result, action="fan_on"):
    """A4 九字段事件（MASTER_PLAN §6.2）；summary 由程序拼接。"""
    summary = (
        f"{start[11:]} {node_id} 连续{problem} → 优先关注 {node_id}"
        + (f" → {action_time[11:]} 开启风扇并通风" if action == "fan_on" else "")
        + (f" → {recover_time[11:]} 恢复正常" if result == "已恢复" else " → 至当日结束仍未恢复")
    )
    return {
        "nodeId": node_id,
        "startTime": start,
        "problem": problem,
        "priorityReason": f"已连续{problem} {duration_min} 分钟" if duration_min else "",
        "action": action if result == "已恢复" else "",
        "actionTime": action_time if result == "已恢复" else "",
        "recoverTime": recover_time if result == "已恢复" else "",
        "result": result,
        "summary": summary,
    }


def generate(day_dir, seed):
    rng = random.Random(seed)
    day_dir = Path(day_dir)
    day_dir.mkdir(parents=True, exist_ok=True)
    events = []

    # dorm-a：全天正常
    write_node_csv(day_dir, "dorm-a", normal_stretch("dorm-a", 8 * 60, 21 * 60, 60, rng))

    # dorm-b：下午一次"偏热"事件（seed 变化时长与恢复节奏），处理后恢复
    hot_duration = 40 if seed == 1 else 30
    recover_after = 30 if seed == 1 else 15   # 开启风扇后 N 分钟恢复（截图 B3 例句口径）
    hot_start_min = 13 * 60 + 20
    action_min = hot_start_min + hot_duration + 5
    recover_min = action_min + recover_after
    rows_b = normal_stretch("dorm-b", 8 * 60, 13 * 60, 60, rng)
    t = hot_start_min
    while t < hot_start_min + hot_duration:
        rows_b.append(row("dorm-b", f"{t // 60:02d}:{t % 60:02d}:00", rng.uniform(31, 32.5), rng.uniform(58, 62)))
        t += 10
    for dt, temp, hum in ((10, 30, 76), (20, 27, 65), (30, 26, 62)):
        m = action_min + dt
        rows_b.append(row("dorm-b", f"{m // 60:02d}:{m % 60:02d}:00", temp, hum))
    rows_b.extend(normal_stretch("dorm-b", recover_min + 30, 21 * 60, 60, rng))
    rows_b.sort(key=lambda r: r["time"])
    write_node_csv(day_dir, "dorm-b", rows_b)
    events.append(make_event(
        "dorm-b",
        DAY + f" {hot_start_min // 60:02d}:{hot_start_min % 60:02d}:00",
        "偏热", hot_duration,
        DAY + f" {action_min // 60:02d}:{action_min % 60:02d}:00",
        DAY + f" {recover_min // 60:02d}:{recover_min % 60:02d}:00",
        "已恢复",
    ))

    # dorm-c：晚间一次异常事件（seed 变化问题类型与开始时间；未处理 → 仍未恢复）
    wet_start_min = 19 * 60 + 30 if seed == 1 else 20 * 60
    c_problem = "偏湿" if seed == 1 else "偏冷"
    rows_c = normal_stretch("dorm-c", 8 * 60, 18 * 60, 60, rng)
    t = wet_start_min
    while t <= 21 * 60:
        if c_problem == "偏湿":
            rows_c.append(row("dorm-c", f"{t // 60:02d}:{t % 60:02d}:00", rng.uniform(24.5, 26), rng.uniform(80, 86)))
        else:
            rows_c.append(row("dorm-c", f"{t // 60:02d}:{t % 60:02d}:00", rng.uniform(16, 17.5), rng.uniform(55, 65)))
        t += 15
    rows_c.sort(key=lambda r: r["time"])
    write_node_csv(day_dir, "dorm-c", rows_c)
    events.append(make_event(
        "dorm-c",
        DAY + f" {wet_start_min // 60:02d}:{wet_start_min % 60:02d}:00",
        c_problem, 0, "", "", "仍需关注", action="",
    ))

    (day_dir / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成模拟日数据：{day_dir}（seed={seed}，事件 {len(events)} 条）")
    return day_dir


def main():
    parser = argparse.ArgumentParser(description="B3 模拟日数据生成器（程序生成，禁手改）")
    parser.add_argument("--out", required=True, help="输出目录（如 data/sim-day-1）")
    parser.add_argument("--seed", type=int, default=1, help="随机种子（默认 1；换 seed 产出不同数据）")
    args = parser.parse_args()
    generate(args.out, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
