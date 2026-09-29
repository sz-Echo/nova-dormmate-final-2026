"""DormMate B S3 今日摘要生成器（analysis/daily_summary.py）

读模拟日数据（每节点 CSV + events.json，make_day_data.py 产出）→ 程序生成"今日摘要"
（SPEC §9 B3 例句口径：谁出了问题、做了什么、结果怎么样），输出：
控制台 + day_dir/summary.md + day_dir/report.html（当日报告页，全部程序生成）。
换一份数据必须重新运行生成（B3 完成线：禁止手工修改文字冒充程序结果）。

用法：python analysis/daily_summary.py --day data/sim-day-1
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.analyze import (  # noqa: E402  # 复用 M2/A4 已实现能力，零重写
    STATUS_ORDER, build_events_block, compute_stats, load_csv, load_events,
)

NODES = ["dorm-a", "dorm-b", "dorm-c"]
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def period_of(start_time):
    """时间段（程序推断）：<12 上午 / <18 下午 / 其余 晚间。"""
    try:
        hour = int(start_time[11:13])
    except (ValueError, IndexError):
        return ""
    if hour < 12:
        return "上午"
    if hour < 18:
        return "下午"
    return "晚间"


def minutes_between(start_time, end_time):
    return int((datetime.strptime(end_time, TIME_FMT) - datetime.strptime(start_time, TIME_FMT)).total_seconds() / 60)


def describe_node(node_id, csv_path, events):
    """单节点一句话（程序拼接）：有事件按事件讲；无事件按统计讲。"""
    stats = compute_stats(load_csv(csv_path))
    node_events = [e for e in events if e.get("nodeId") == node_id]
    if node_events:
        parts = []
        for e in node_events:
            period = period_of(str(e.get("startTime", "")))
            if e.get("result") == "已恢复" and e.get("recoverTime"):
                # 恢复时长 = 动作到恢复（"开启风扇后 N 分钟恢复"，截图 B3 例句口径）；无动作则从异常开始算
                base = str(e["actionTime"]) if e.get("action") == "fan_on" and e.get("actionTime") else str(e["startTime"])
                mins = minutes_between(base, str(e["recoverTime"]))
                action_part = "开启风扇后 " if e.get("action") == "fan_on" else ""
                parts.append(f"{node_id} {period}发生 1 次持续{e.get('problem', '异常')}，{action_part}{mins} 分钟恢复")
            else:
                parts.append(f"{node_id} {period}出现 1 次{e.get('problem', '异常')}，目前仍未恢复")
        return "；".join(parts)
    if stats["count"] == 0:
        return f"{node_id} 当日无记录"
    abnormal = sum(stats["status_counts"][s] for s in STATUS_ORDER[1:])
    if abnormal == 0:
        return f"{node_id} 全天整体正常"
    return f"{node_id} 出现 {abnormal} 条异常记录"


def build_summary(day_dir, events):
    sentences = []
    for node_id in NODES:
        csv_path = day_dir / f"{node_id}.csv"
        if csv_path.exists():
            sentences.append(describe_node(node_id, csv_path, events))
    total = len(events)
    tail = f"今日共发生 {total} 次需要关注的环境事件。" if total else "今日无需要关注的环境事件。"
    return "；".join(sentences) + "。" + tail


def main():
    parser = argparse.ArgumentParser(description="B3 今日摘要（程序生成，禁手改）")
    parser.add_argument("--day", required=True, help="模拟日数据目录（make_day_data.py 产出）")
    args = parser.parse_args()
    day_dir = Path(args.day)
    if not day_dir.exists():
        print(f"[错误] 目录不存在：{day_dir}", file=sys.stderr)
        return 1

    events = load_events(day_dir)
    summary = build_summary(day_dir, events)

    print("=== DormMate B3 今日摘要（程序生成） ===")
    print(f"数据目录: {day_dir}")
    print(f"事件数: {len(events)}")
    print(summary)

    (day_dir / "summary.md").write_text(
        "# 今日摘要（B3，程序生成）\n\n" + summary
        + "\n\n> 由 analysis/daily_summary.py 生成；换数据请重新运行，禁止手工修改文字。\n",
        encoding="utf-8",
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DormMate 今日摘要报告（B3）</title>
<style>
body {{ font-family: "Microsoft YaHei", system-ui, sans-serif; margin: 2rem auto; max-width: 860px; color: #2c3e50; background: #f5f7fa; }}
h1 {{ font-size: 1.6rem; }}
h2 {{ font-size: 1.15rem; border-left: 4px solid #3498db; padding-left: .5rem; }}
section {{ background: #fff; border: 1px solid #e3e8ee; border-radius: 8px; padding: 1rem 1.25rem; margin: 1rem 0; }}
table {{ border-collapse: collapse; width: 100%; margin: .5rem 0; }}
th, td {{ border: 1px solid #e3e8ee; padding: .4rem .6rem; text-align: left; }}
th {{ background: #f0f4f8; }}
.meta {{ color: #7f8c8d; }}
td.status {{ font-weight: bold; color: #c0392b; }}
</style>
</head>
<body>
<h1>DormMate 今日摘要报告（B3）</h1>
<p class="meta">生成时间：{now} · 数据目录：{day_dir.name} · 事件 {len(events)} 条</p>
<section>
<h2>今日摘要</h2>
<p>{summary}</p>
</section>
<section>
<h2>事件复盘</h2>
{build_events_block(events)}
</section>
</body>
</html>
"""
    (day_dir / "report.html").write_text(report, encoding="utf-8")
    print("产物已生成:")
    print(f"  {day_dir / 'summary.md'}")
    print(f"  {day_dir / 'report.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
