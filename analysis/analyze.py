"""DormMate M2 离线分析（analysis/analyze.py）

数据链：Web 导出的 CSV（data/dormmate.csv，SPEC §5 最小 4 列，UTF-8）→ pandas 读取 →
对全部记录重跑统一规则（SPEC §3）→ 基础统计 → matplotlib trend.png → report.html

用法：
  python analysis/analyze.py [csv路径] [--out 输出目录]    # 不指定 CSV 时自动选择输出目录中最新的 CSV；产物输出 data/
  python analysis/analyze.py --watch [--out 输出目录]      # 监控目录：放入 / 更换 CSV 后自动重新生成
  python analysis/analyze.py --selftest                    # SPEC §6 四组回归自测
换一份新 CSV 后重跑即全量重新生成统计、trend.png、report.html（禁止手工修改结果）。
"""
import argparse
import html
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# 控制台输出统一 UTF-8：交互式终端天然支持 Unicode；管道/重定向场景避免 GBK 乱码（本机中文 Windows）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# 项目根（本文件向上两级）：nova-dormmate-final-2026/
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "dormmate.csv"
DEFAULT_OUT = ROOT / "data"

# 状态展示顺序（SPEC §3 四状态）
STATUS_ORDER = ["正常", "偏冷", "偏热", "偏湿"]
# 关注记录 = status 非正常（SPEC §8 注）
ATTENTION_STATUSES = ("偏冷", "偏热", "偏湿")


def compute_status(temperature, humidity):
    """SPEC §3：顺序不可改（①<18 偏冷 ②>=30 偏热 ③湿度>=75 偏湿 ④其余 正常），命中即返回。"""
    if temperature < 18:
        return "偏冷"
    if temperature >= 30:
        return "偏热"
    if humidity >= 75:
        return "偏湿"
    return "正常"


# SPEC §6 四组统一回归数据（与 web/test.html 同一组）
REGRESSION_CASES = [
    (25, 60, "正常"),
    (16, 60, "偏冷"),
    (31, 60, "偏热"),
    (25, 80, "偏湿"),
]


def selftest():
    """SPEC §6 四组回归自测，全过返回 True。"""
    passed = 0
    for temperature, humidity, expected in REGRESSION_CASES:
        actual = compute_status(temperature, humidity)
        ok = actual == expected
        passed += 1 if ok else 0
        print(f"{temperature}/{humidity} -> {actual}（期望 {expected}）{'通过' if ok else '失败'}")
    print(f"四组回归：{passed}/{len(REGRESSION_CASES)} 通过")
    return passed == len(REGRESSION_CASES)


def load_csv(csv_path):
    """读取 CSV（utf-8-sig 兼容 Web 导出的 BOM 头），校验 4 列与 time 全格式，重跑统一规则。"""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"未找到 CSV 文件：{csv_path}\n"
            "请把 Web 页面导出的 dormmate.csv 放到 data/ 目录，或运行时传入文件路径"
        )
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    missing = {"time", "temperature", "humidity", "status"} - set(df.columns)
    if missing:
        raise ValueError(
            f"CSV 缺少列：{sorted(missing)}（SPEC §5 最小格式为 time,temperature,humidity,status）"
        )
    if len(df) == 0:
        raise ValueError("CSV 无数据行（只有表头），请先在 Web 页面分析几条数据再导出")
    # time 必须为全格式 YYYY-MM-DD HH:MM:SS（M2_PLAN §1 数据来源红线）
    try:
        df["time"] = pd.to_datetime(df["time"], format="%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        raise ValueError(f"time 列格式应为 YYYY-MM-DD HH:MM:SS（全格式）：{e}") from e
    df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
    df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce")
    if df["temperature"].isna().any() or df["humidity"].isna().any():
        raise ValueError("temperature / humidity 列含非数字值，请检查 CSV")
    # 对全部记录重跑统一规则（不直接信任 CSV 里的 status 列）
    df["status_calc"] = df.apply(
        lambda row: compute_status(row["temperature"], row["humidity"]), axis=1
    )
    return df


def compute_stats(df):
    """基础统计：记录数、温湿度最高/最低（含对应 time）、各状态数量、关注记录。"""
    def time_str(row):
        return row["time"].strftime("%Y-%m-%d %H:%M:%S")

    def peak(column):
        row = df.loc[df[column].idxmax()]
        return row[column], time_str(row)

    def trough(column):
        row = df.loc[df[column].idxmin()]
        return row[column], time_str(row)

    attention = df[df["status_calc"].isin(ATTENTION_STATUSES)].sort_values("time")
    return {
        "count": len(df),
        "temp_max": peak("temperature"),
        "temp_min": trough("temperature"),
        "hum_max": peak("humidity"),
        "hum_min": trough("humidity"),
        "status_counts": {s: int((df["status_calc"] == s).sum()) for s in STATUS_ORDER},
        "mismatch": int((df["status_calc"] != df["status"]).sum()),
        "attention": [
            (time_str(r), r["temperature"], r["humidity"], r["status_calc"])
            for _, r in attention.iterrows()
        ],
    }


def plot_trend(df, out_path):
    """matplotlib 生成 trend.png：上=温度/湿度随时间折线，下=四状态数量柱状。"""
    import matplotlib

    matplotlib.use("Agg")  # 不弹窗口，直接写文件
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # Windows 中文字体，避免图中中文显示为方框
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7))

    ax1.plot(df["time"], df["temperature"], marker="o", color="#e74c3c", label="温度（℃）")
    ax1.set_ylabel("温度（℃）", color="#e74c3c")
    ax1.tick_params(axis="y", labelcolor="#e74c3c")
    ax1.set_title("温度 / 湿度随时间变化")
    ax1b = ax1.twinx()
    ax1b.plot(df["time"], df["humidity"], marker="s", color="#3498db", label="湿度（%）")
    ax1b.set_ylabel("湿度（%）", color="#3498db")
    ax1b.tick_params(axis="y", labelcolor="#3498db")
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax1b.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="best")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    fig.autofmt_xdate()

    counts = [int((df["status_calc"] == s).sum()) for s in STATUS_ORDER]
    colors = ["#2ecc71", "#74b9ff", "#e17055", "#fdcb6e"]
    bars = ax2.bar(STATUS_ORDER, counts, color=colors)
    ax2.set_ylabel("记录数")
    ax2.set_title("各状态数量（按统一规则重算）")
    for bar in bars:
        ax2.annotate(
            str(int(bar.get_height())),
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            ha="center",
            va="bottom",
        )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def load_events(data_dir):
    """读取 data/events.json（A4 事件记录，Dashboard"今日事件"导出）。
    文件缺失/损坏时返回空列表并提示，不阻塞报告生成（事件复盘是可叠加区块）。"""
    data_dir = Path(data_dir)
    events_path = data_dir / "events.json"
    if not events_path.exists():
        return []
    try:
        data = json.loads(events_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[事件] events.json 解析失败（忽略）：{exc}", file=sys.stderr)
        return []
    if not isinstance(data, list):
        print("[事件] events.json 不是数组（忽略）", file=sys.stderr)
        return []
    return [e for e in data if isinstance(e, dict)]


def build_events_block(events):
    """A4 事件复盘区 HTML（全部由程序生成）：事件表格 + 程序拼接的复盘叙事。"""
    if not events:
        return "<p>暂无事件记录（在 Dashboard 完成一次 A 组处理流程并导出 data/events.json 后重新生成）</p>"
    rows = "".join(
        f"<tr><td>{html.escape(str(e.get('nodeId') or ''))}</td>"
        f"<td>{html.escape(str(e.get('startTime') or ''))}</td>"
        f"<td class='status'>{html.escape(str(e.get('problem') or ''))}</td>"
        f"<td>{html.escape(str(e.get('priorityReason') or ''))}</td>"
        f"<td>{html.escape(str(e.get('action') or ''))}（{html.escape(str(e.get('actionTime') or ''))}）</td>"
        f"<td>{html.escape(str(e.get('recoverTime') or ''))}</td>"
        f"<td class='status'>{html.escape(str(e.get('result') or ''))}</td></tr>"
        for e in events
    )
    table = (
        "<table><tr><th>宿舍</th><th>开始时间</th><th>问题</th><th>优先原因</th>"
        "<th>处理动作</th><th>恢复时间</th><th>结果</th></tr>" + rows + "</table>"
    )
    stories = "".join(
        f"<li>{html.escape(str(e.get('summary', '')))}</li>" for e in events if e.get("summary")
    )
    stories_block = "<h3>复盘</h3><ul>" + stories + "</ul>" if stories else ""
    return table + stories_block


def render_report(stats, csv_path, out_dir, events=None):
    """生成 data/report.html：摘要、关注记录、事件复盘（A4）、趋势图（内容全部由程序生成）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def fmt_num(v):
        return f"{v:g}"

    summary_rows = (
        f"<tr><th>记录数</th><td>{stats['count']}</td></tr>"
        f"<tr><th>温度最高</th><td>{fmt_num(stats['temp_max'][0])}℃（{stats['temp_max'][1]}）</td></tr>"
        f"<tr><th>温度最低</th><td>{fmt_num(stats['temp_min'][0])}℃（{stats['temp_min'][1]}）</td></tr>"
        f"<tr><th>湿度最高</th><td>{fmt_num(stats['hum_max'][0])}%（{stats['hum_max'][1]}）</td></tr>"
        f"<tr><th>湿度最低</th><td>{fmt_num(stats['hum_min'][0])}%（{stats['hum_min'][1]}）</td></tr>"
        f"<tr><th>状态自查</th><td>CSV status 列与重算不一致 {stats['mismatch']} 条</td></tr>"
    )
    status_rows = "".join(
        f"<tr><th>{s}</th><td>{stats['status_counts'][s]}</td></tr>" for s in STATUS_ORDER
    )
    if stats["attention"]:
        attention_rows = "".join(
            f"<tr><td>{html.escape(t)}</td><td>{fmt_num(temp)}℃</td>"
            f"<td>{fmt_num(hum)}%</td><td class='status'>{html.escape(status)}</td></tr>"
            for t, temp, hum, status in stats["attention"]
        )
        attention_block = (
            "<table><tr><th>时间</th><th>温度</th><th>湿度</th><th>状态</th></tr>"
            + attention_rows
            + "</table>"
        )
    else:
        attention_block = "<p>无关注记录（全部正常）</p>"

    events_block = build_events_block(events if events is not None else [])

    html_text = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DormMate 离线分析报告</title>
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
img {{ max-width: 100%; border: 1px solid #e3e8ee; border-radius: 4px; }}
</style>
</head>
<body>
<h1>DormMate 离线分析报告</h1>
<p class="meta">生成时间：{now} · 数据来源：{csv_path.name}（{stats['count']} 条记录）</p>
<!-- C3 扩展点：IsolationForest 结果接回此 section（勿删本注释） -->
<section>
<h2>摘要</h2>
<table>{summary_rows}</table>
<h3>各状态数量（按统一规则重算）</h3>
<table>{status_rows}</table>
</section>
<section>
<h2>关注记录（status 非正常）</h2>
{attention_block}
</section>
<section>
<h2>事件复盘（A4）</h2>
{events_block}
</section>
<section>
<h2>趋势图</h2>
<img src="trend.png" alt="温度 / 湿度随时间趋势图">
</section>
</body>
</html>
"""
    (out_dir / "report.html").write_text(html_text, encoding="utf-8")


def print_stats(stats, csv_path, trend_path, report_path, events=None):
    """控制台统计输出（证据：与 CSV 人工核对一致）。"""
    def fmt_num(v):
        return f"{v:g}"

    print("=== DormMate M2 离线分析 ===")
    print(f"数据文件: {csv_path}")
    print(f"记录数: {stats['count']}")
    print(
        f"温度: 最高 {fmt_num(stats['temp_max'][0])}℃（{stats['temp_max'][1]}）"
        f"/ 最低 {fmt_num(stats['temp_min'][0])}℃（{stats['temp_min'][1]}）"
    )
    print(
        f"湿度: 最高 {fmt_num(stats['hum_max'][0])}%（{stats['hum_max'][1]}）"
        f"/ 最低 {fmt_num(stats['hum_min'][0])}%（{stats['hum_min'][1]}）"
    )
    counts_str = " / ".join(f"{s} {stats['status_counts'][s]}" for s in STATUS_ORDER)
    print(f"各状态数量（按统一规则重算）: {counts_str}")
    print(f"自查: CSV status 列与重算不一致 {stats['mismatch']} 条")
    if stats["attention"]:
        print("关注记录（status 非正常）:")
        for t, temp, hum, status in stats["attention"]:
            print(f"  {t} · {fmt_num(temp)}℃ / {fmt_num(hum)}% · {status}")
    else:
        print("关注记录（status 非正常）: 无")
    print(f"事件复盘（A4，data/events.json）: {len(events or [])} 条")
    for ev in (events or []):
        if ev.get("summary"):
            print(f"  {ev['summary']}")
    print("产物已重新生成:")
    print(f"  {trend_path}")
    print(f"  {report_path}")


def pick_csv(data_dir):
    """不指定 CSV 时自动选择目录中最新的 .csv（"更换 CSV"语义：新文件即当前数据源，旧文件保留）。"""
    data_dir = Path(data_dir)
    csv_files = list(data_dir.glob("*.csv")) if data_dir.exists() else []
    if not csv_files:
        raise FileNotFoundError(
            f"目录 {data_dir} 中没有 CSV 文件，请把 Web 导出的 CSV 放进 data/ 目录"
        )
    return max(csv_files, key=lambda p: p.stat().st_mtime)


def watch(out_dir):
    """监控输出目录：放入或更换 CSV 后自动重新生成统计、trend.png、report.html（Ctrl+C 停止）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"监控目录: {out_dir}")
    print("放入或更换 CSV 文件后自动重新生成统计、trend.png、report.html（Ctrl+C 停止）")
    last_signature = None
    while True:
        try:
            csv_files = list(out_dir.glob("*.csv"))
            if csv_files:
                newest = max(csv_files, key=lambda p: p.stat().st_mtime)
                signature = (str(newest), newest.stat().st_mtime, newest.stat().st_size)
                if signature != last_signature:
                    last_signature = signature
                    print(f"[检测到 CSV] {newest.name}")
                    try:
                        run_pipeline(newest, out_dir)
                    except (FileNotFoundError, ValueError) as e:
                        print(f"[跳过] {newest.name}: {e}", file=sys.stderr)
                    sys.stdout.flush()  # 输出重定向到文件时不丢日志
            time.sleep(2)
        except KeyboardInterrupt:
            print("停止监控")
            break


def run_pipeline(csv_path, out_dir):
    """完整管线：读 CSV → 统计 → trend.png → report.html（含 A4 事件复盘）→ 控制台输出。"""
    df = load_csv(csv_path)
    stats = compute_stats(df)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trend_path = out_dir / "trend.png"
    report_path = out_dir / "report.html"
    events = load_events(out_dir)   # A4：data/events.json 缺失时不阻塞（区块显示"暂无事件记录"）
    plot_trend(df, trend_path)
    render_report(stats, Path(csv_path), out_dir, events)
    print_stats(stats, csv_path, trend_path, report_path, events)


def main():
    parser = argparse.ArgumentParser(
        description="DormMate M2 离线分析：CSV -> 统计 / trend.png / report.html"
    )
    parser.add_argument(
        "csv",
        nargs="?",
        default=None,
        help="CSV 文件路径（不指定则自动选择输出目录中最新的 CSV）",
    )
    parser.add_argument(
        "--out", default=str(DEFAULT_OUT), help=f"产物输出目录（默认 {DEFAULT_OUT}）"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="监控输出目录：放入 / 更换 CSV 后自动重新生成",
    )
    parser.add_argument("--selftest", action="store_true", help="SPEC §6 四组回归自测")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    try:
        if args.watch:
            watch(args.out)
        else:
            csv_path = args.csv
            if csv_path is None:
                csv_path = pick_csv(args.out)
                print(f"[自动选择最新 CSV] {csv_path}")
            run_pipeline(csv_path, args.out)
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
