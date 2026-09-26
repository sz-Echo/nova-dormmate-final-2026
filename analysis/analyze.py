"""DormMate M2 离线分析（analysis/analyze.py）

数据链：Web 导出的 CSV（data/dormmate.csv，SPEC §5 最小 4 列，UTF-8）→ pandas 读取 →
对全部记录重跑统一规则（SPEC §3）→ 基础统计 → matplotlib trend.png → report.html

用法：
  python analysis/analyze.py [csv路径] [--out 输出目录]    # 默认 data/dormmate.csv，产物输出 data/
  python analysis/analyze.py --selftest                    # SPEC §6 四组回归自测
换一份新 CSV 后重跑即全量重新生成统计、trend.png、report.html（禁止手工修改结果）。
"""
import argparse
import html
import sys
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


def render_report(stats, csv_path, out_dir):
    """生成 data/report.html：摘要、关注记录、趋势图三要素（内容全部由程序生成）。"""
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
<h2>趋势图</h2>
<img src="trend.png" alt="温度 / 湿度随时间趋势图">
</section>
</body>
</html>
"""
    (out_dir / "report.html").write_text(html_text, encoding="utf-8")


def print_stats(stats, csv_path, trend_path, report_path):
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
    print("产物已重新生成:")
    print(f"  {trend_path}")
    print(f"  {report_path}")


def run_pipeline(csv_path, out_dir):
    """完整管线：读 CSV → 统计 → trend.png → report.html → 控制台输出。"""
    df = load_csv(csv_path)
    stats = compute_stats(df)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trend_path = out_dir / "trend.png"
    report_path = out_dir / "report.html"
    plot_trend(df, trend_path)
    render_report(stats, Path(csv_path), out_dir)
    print_stats(stats, csv_path, trend_path, report_path)


def main():
    parser = argparse.ArgumentParser(
        description="DormMate M2 离线分析：CSV -> 统计 / trend.png / report.html"
    )
    parser.add_argument(
        "csv", nargs="?", default=str(DEFAULT_CSV), help=f"CSV 文件路径（默认 {DEFAULT_CSV}）"
    )
    parser.add_argument(
        "--out", default=str(DEFAULT_OUT), help=f"产物输出目录（默认 {DEFAULT_OUT}）"
    )
    parser.add_argument("--selftest", action="store_true", help="SPEC §6 四组回归自测")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)

    try:
        run_pipeline(args.csv, args.out)
    except (FileNotFoundError, ValueError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
