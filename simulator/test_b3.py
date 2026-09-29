"""DormMate B S3 自动化验证（simulator/test_b3.py）

B3 今日摘要（SPEC §9 B3）：程序自动生成"今日摘要"；≥2 事件模拟日数据；
换一份事件数据后摘要必须重新生成（不手改）。
验证点：两份不同 seed 的模拟日数据 → 两次运行 → 摘要内容正确且不同；
summary.md / report.html 产物齐全（全部程序生成）。

用法：python simulator/test_b3.py（无需 Broker，纯 Python + Playwright 截图）
"""
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "docs" / "evidence" / "b"
EVIDENCE.mkdir(parents=True, exist_ok=True)
failures = []


def check(name, cond, actual=""):
    print(("PASS" if cond else "FAIL") + " | " + name + ((" | 实际: " + str(actual)) if not cond else ""))
    if not cond:
        failures.append(name)


def run(args):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True,
                          cwd=str(ROOT), encoding="utf-8", errors="replace")


def make_day(seed):
    out = ROOT / "data" / f"sim-day-{seed}"
    r = run(["analysis/make_day_data.py", "--out", str(out), "--seed", str(seed)])
    check(f"make_day_data seed={seed} 运行", r.returncode == 0, r.stderr[-200:])
    return out


def summarize(day):
    r = run(["analysis/daily_summary.py", "--day", str(day)])
    check(f"daily_summary {day.name} 运行", r.returncode == 0, r.stderr[-200:])
    return r.stdout


day1 = make_day(1)
day2 = make_day(2)
out1 = summarize(day1)
out2 = summarize(day2)

# 例句口径断言（程序生成，禁手改）
for name, out in (("day1", out1), ("day2", out2)):
    check(f"{name} 含 dorm-a 全天整体正常", "dorm-a 全天整体正常" in out, out[-200:])
    check(f"{name} 含 今日共发生 2 次需要关注的环境事件", "今日共发生 2 次需要关注的环境事件。" in out, out[-200:])
    check(f"{name} 含 dorm-b 下午发生 1 次持续偏热", "dorm-b 下午发生 1 次持续偏热" in out, out[-200:])

check("day1 含 dorm-c 晚间偏湿 未恢复", "dorm-c 晚间出现 1 次偏湿，目前仍未恢复" in out1, out1[-200:])
check("day1 含 开启风扇后 30 分钟恢复", "开启风扇后 30 分钟恢复" in out1, out1[-200:])
check("day2 含 dorm-c 晚间偏冷 未恢复", "dorm-c 晚间出现 1 次偏冷，目前仍未恢复" in out2, out2[-200:])
check("day2 含 开启风扇后 15 分钟恢复", "开启风扇后 15 分钟恢复" in out2, out2[-200:])

# 换数据必须重新生成且摘要不同（B3 完成线核心）
s1 = (day1 / "summary.md").read_text(encoding="utf-8")
s2 = (day2 / "summary.md").read_text(encoding="utf-8")
check("summary.md 两份产物齐全", (day1 / "summary.md").exists() and (day2 / "summary.md").exists())
check("换数据后摘要不同（重新生成，不手改）", s1 != s2, s1[-120:])

# events.json ≥2 事件 + report.html 产物
import json as _json
ev1 = _json.loads((day1 / "events.json").read_text(encoding="utf-8"))
ev2 = _json.loads((day2 / "events.json").read_text(encoding="utf-8"))
check("两份模拟日数据各 ≥2 事件", len(ev1) >= 2 and len(ev2) >= 2, (len(ev1), len(ev2)))
r1 = (day1 / "report.html").read_text(encoding="utf-8")
r2 = (day2 / "report.html").read_text(encoding="utf-8")
check("report.html 含今日摘要与事件复盘", "今日摘要" in r1 and "事件复盘" in r1 and "今日摘要" in r2 and "事件复盘" in r2)

# 截图两份报告
with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, day in (("b3-day1-report.png", day1), ("b3-day2-report.png", day2)):
        page = browser.new_page(viewport={"width": 1100, "height": 1200})
        page.goto((day / "report.html").as_uri())
        page.wait_for_timeout(500)
        page.screenshot(path=str(EVIDENCE / name), full_page=True)
        page.close()
    browser.close()

print("B3 RESULT: %d failures" % len(failures))
sys.exit(1 if failures else 0)
