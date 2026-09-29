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


def load_c_compare(data_dir, refresh=False):
    """C3：读取 data/c_compare.json（C2 对照结果，analysis/c_ml.py 程序生成）。

    refresh=True 时先保证结果与当前数据一致：data/c_history.csv 与 data/c_new.csv 都存在时，
    若 c_compare.json 缺失或早于任一数据文件，则复用 analysis/c_ml.compare_rows 重新对照
    （零重写）并写回——"换一份新 CSV 后重跑 analyze.py 即全量重新生成"（SPEC §9 C3）。
    数据文件缺失 / JSON 损坏时返回 []，不阻塞报告生成（ML 异常分析是可叠加区块）。
    """
    data_dir = Path(data_dir)
    cmp_path = data_dir / "c_compare.json"
    hist_path = data_dir / "c_history.csv"
    new_path = data_dir / "c_new.csv"

    if refresh and hist_path.exists() and new_path.exists():
        data_mtime = max(hist_path.stat().st_mtime, new_path.stat().st_mtime)
        if not cmp_path.exists() or cmp_path.stat().st_mtime < data_mtime:
            try:
                if str(ROOT) not in sys.path:
                    sys.path.insert(0, str(ROOT))  # 脚本直跑时包路径不在 sys.path（c_ml 反向 import 本模块）
                from analysis import c_ml  # 延迟导入：c_ml 依赖 numpy 且反向 import 本模块（无环）
                compare = c_ml.compare_rows(str(hist_path), str(new_path))
                cmp_path.write_text(
                    json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"[ML 对照] 已按当前 c_history.csv / c_new.csv 重新生成: {cmp_path}")
            except (ImportError, ValueError, OSError) as exc:
                print(f"[ML 对照] 重新生成失败（报告将显示旧结果或暂无）: {exc}", file=sys.stderr)

    if not cmp_path.exists():
        return []
    try:
        data = json.loads(cmp_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[ML 对照] c_compare.json 解析失败（忽略）：{exc}", file=sys.stderr)
        return []
    return data if isinstance(data, list) else []


def build_ml_block(compare):
    """C3 ML 异常分析区 HTML（全部由程序生成）：C2 对照结果并排（当前值 / 固定规则 / ML 判断，
    附异常分数）；"规则正常、ML 明显不同"的差异行高亮（截图 C3：ML 与固定规则并列，仅辅助判断）。"""
    if not compare:
        return ("<p>暂无 ML 对照结果（运行 <code>python analysis/c_ml.py</code> 生成 "
                "<code>data/c_compare.json</code> 后重新生成报告）</p>")
    rows = []
    for c in compare:
        is_diff = c.get("rule_status") == "正常" and c.get("ml_verdict") == -1
        row_class = " class='ml-diff'" if is_diff else ""
        ml_class = " class='ml-away'" if c.get("ml_verdict") == -1 else ""
        rows.append(
            f"<tr{row_class}><td>dorm-a</td>"
            f"<td>{html.escape(str(c.get('time') or ''))}</td>"
            f"<td>{c.get('temperature', 0):g}℃ / {c.get('humidity', 0):g}%</td>"
            f"<td class='status'>{html.escape(str(c.get('rule_status') or ''))}</td>"
            f"<td{ml_class}>{html.escape(str(c.get('ml_text') or ''))}</td>"
            f"<td>{c.get('ml_score', 0):.4f}</td></tr>"
        )
    diff_count = sum(1 for c in compare if c.get("rule_status") == "正常" and c.get("ml_verdict") == -1)
    note = (
        "<p class='meta'>模型：自实现 IsolationForest（n_estimators=100、random_state=42、阈值 0.5，"
        "替代原因见 README）；历史 = data/c_history.csv（dorm-a 40 条模拟数据，程序生成）；"
        "口径：1 = 接近历史常态，-1 = 与历史明显不同；ML 结果与固定规则并列，仅作辅助判断。"
        f"本次对照 {len(compare)} 组，'固定规则正常、ML 与历史明显不同' {diff_count} 组"
        + ("（高亮行）。" if diff_count else "。") + "</p>"
    )
    table = (
        "<table><tr><th>宿舍</th><th>时间</th><th>当前值</th><th>固定规则</th><th>ML 判断</th>"
        "<th>异常分数</th></tr>" + "".join(rows) + "</table>"
    )
    return note + table


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


def render_report(stats, csv_path, out_dir, events=None, c_compare=None):
    """生成 data/report.html：摘要、关注记录、事件复盘（A4）、ML 异常分析（C3）、趋势图
    （内容全部由程序生成；c_compare=None 时不渲染 ML 区——如 B3 模拟日报告）。"""
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
    # C3：ML 异常分析区（c_compare=None 时不渲染；空列表渲染"暂无"占位）
    ml_block = build_ml_block(c_compare) if c_compare is not None else None
    ml_section = ""
    if ml_block is not None:
        ml_section = "<section>\n<h2>ML 异常分析（C3）</h2>\n" + ml_block + "\n</section>\n"

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
.ml-diff td {{ background: #fdeee8; }}
.ml-away {{ color: #c0392b; font-weight: bold; }}
img {{ max-width: 100%; border: 1px solid #e3e8ee; border-radius: 4px; }}
</style>
</head>
<body>
<h1>DormMate 离线分析报告</h1>
<p class="meta">生成时间：{now} · 数据来源：{csv_path.name}（{stats['count']} 条记录）</p>
<!-- C3 扩展点：IsolationForest 结果接回此 section（勿删本注释） -->
{ml_section}<section>
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


def print_stats(stats, csv_path, trend_path, report_path, events=None, c_compare=None):
    """控制台统计输出（证据：与 CSV 人工核对一致；c_compare 为 C3 ML 对照行列表）。"""
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
    if c_compare:
        diff_n = sum(1 for c in c_compare if c.get("rule_status") == "正常" and c.get("ml_verdict") == -1)
        print(f"ML 异常分析（C3，data/c_compare.json）: {len(c_compare)} 组，差异行 {diff_n} 组")
    else:
        print("ML 异常分析（C3，data/c_compare.json）: 暂无")
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
    c_compare = load_c_compare(out_dir, refresh=True)   # C3：报告 ML 区与当前 c_history/c_new 一致
    plot_trend(df, trend_path)
    render_report(stats, Path(csv_path), out_dir, events, c_compare)
    print_stats(stats, csv_path, trend_path, report_path, events, c_compare)


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
