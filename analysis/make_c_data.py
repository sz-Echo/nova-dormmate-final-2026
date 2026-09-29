"""DormMate C S1 数据准备（analysis/make_c_data.py）

C1（SPEC §9 C1 / MASTER_PLAN §6.6）：单节点 dorm-a 的"平时"模拟历史与待判断新数据，
两份严格分离（截图 C1：历史数据与待判断新数据要分开，不能先混入再判断自己）：

  data/c_history.csv —— 40 条模拟历史（24~26℃ / 55~65% 附近，random_state=42 可复现，"模拟"标记）
  data/c_new.csv     —— 8 组待判断新数据（含"固定规则正常但与历史明显不同"候选，如 29℃/72%）

两份数据均由本脚本程序生成（C 组：数据与结果必须程序产生，禁止手改）；
换新历史 CSV 后重新运行本脚本与模型脚本即可（C1 完成线：换数据可重跑）。
数据来源（README 已记录）：历史数据 = 本脚本按 dorm-a"平时"画像生成的模拟值（非真实传感器）；
待判断新数据 = 本脚本生成的独立文件，与历史零混入。

用法：python analysis/make_c_data.py [--out data]
"""
import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.analyze import compute_status  # noqa: E402  # 统一规则零重写（SPEC §6）

# C 契约（MASTER_PLAN §6.6）：固定 random_state=42，同一份数据重复运行结果可复现
RANDOM_STATE = 42

# 待判断新数据（程序内置，非手改输出）：贴近平时 / 规则正常但偏离平时（候选）/ 规则异常 / 边界
NEW_ROWS = [
    (25.0, 58),    # 贴近平时 → 期望：规则正常、ML 接近常态
    (25.6, 60),    # 贴近平时
    (29.0, 72),    # 截图 C2 候选：规则正常（<30 且 <75），但明显偏离平时 24~26/55~65
    (27.5, 70),    # 略偏离平时（观察 ML 是否标记，不预设结论）
    (16.0, 60),    # 规则异常：偏冷
    (31.0, 60),    # 规则异常：偏热
    (25.0, 80),    # 规则异常：偏湿
    (18.0, 74),    # 规则边界附近：正常（湿度 74 < 75）
]


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "temperature", "humidity", "status"])   # SPEC §5 最小 4 列
        for r in rows:
            writer.writerow([r["time"], r["temperature"], r["humidity"], r["status"]])


def make_history():
    """dorm-a"平时"画像：2026-09-26/27 两天，每天 08:00 起每 30 分钟一条（共 40 条）。"""
    rng = random.Random(RANDOM_STATE)
    rows = []
    for day in ("2026-09-26", "2026-09-27"):
        for i in range(20):
            minutes = 8 * 60 + i * 30
            temp = round(rng.uniform(24.0, 26.0), 1)
            hum = round(rng.uniform(55.0, 65.0), 1)
            rows.append({
                "time": f"{day} {minutes // 60:02d}:{minutes % 60:02d}:00",
                "temperature": temp,
                "humidity": hum,
                "status": compute_status(temp, hum),
            })
    return rows


def make_new():
    """待判断新数据：时间独立（2026-09-28），与历史零混入。"""
    rows = []
    for i, (temp, hum) in enumerate(NEW_ROWS):
        rows.append({
            "time": f"2026-09-28 10:{i:02d}:00",
            "temperature": temp,
            "humidity": hum,
            "status": compute_status(temp, hum),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="C1 数据准备（程序生成，random_state=42）")
    parser.add_argument("--out", default=str(ROOT / "data"), help="输出目录（默认 data/）")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    history = make_history()
    new = make_new()
    write_csv(out_dir / "c_history.csv", history)
    write_csv(out_dir / "c_new.csv", new)

    print(f"已生成（模拟数据，random_state={RANDOM_STATE}，可复现）:")
    print(f"  {out_dir / 'c_history.csv'} —— 历史 {len(history)} 条（dorm-a 平时 24~26℃ / 55~65%）")
    print(f"  {out_dir / 'c_new.csv'} —— 待判断新数据 {len(new)} 条（与历史严格分离）")
    print("注：历史与新数据分开存放，模型须用历史 fit、再对新数据 predict（截图 C1 红线）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
