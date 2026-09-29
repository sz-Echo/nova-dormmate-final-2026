"""DormMate C S3 自动化验证（simulator/test_c3.py）

C3 结果接回 DormMate（SPEC §9 C3 / MASTER_PLAN §7.5 S3）：analyze.py 生成 report.html 时
新增"ML 异常分析（C3）"区（并排：当前值 / 固定规则 / ML 判断 + 异常分数，数据来自
data/c_compare.json）；换一份新数据（make_c_data.py --variant 2）后重跑 analyze.py →
report.html 全量重新生成 ML 结果并与固定规则并排（截图 C3）。

验证点：
  ① variant 1：报告含 ML 区，行数与 c_compare.json 一致，差异行高亮
  ② c_compare.json 缺失时 analyze.py 自动重生成（复用 c_ml.compare_rows，零重写，逐字段一致）
     —— 用项目内临时目录验证，不碰 data/ 中的基线文件
  ③ 换数据：--variant 2 → c_new.csv 变化 → 重跑 analyze.py → ML 区随新数据更新、旧候选消失
  ④ 收尾恢复 variant 1 基线并重跑 analyze.py（仓库数据回到基线，报告含 ML 区）
  ⑤ C2 回归：c_ml.py 独立运行仍通过原断言（发现差异 / 输出含"ML:与历史明显不同"）
证据：docs/evidence/c/（c3-report-variant1.html、c3-report-variant2.html、
     c3-console-v1.txt、c3-console-v2.txt、c3-report.png 截图）

前置：无（纯 Python；截图用本地静态服务 + Playwright，不需要 Broker）。
用法：python simulator/test_c3.py
"""
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EVIDENCE = ROOT / "docs" / "evidence" / "c"
EVIDENCE.mkdir(parents=True, exist_ok=True)
failures = []


def check(name, cond, actual=""):
    print(("PASS" if cond else "FAIL") + " | " + name + ((" | 实际: " + str(actual)) if not cond else ""))
    if not cond:
        failures.append(name)


def run(args):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True,
                          cwd=str(ROOT), encoding="utf-8", errors="replace")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_report():
    return (DATA / "report.html").read_text(encoding="utf-8")


def wait_port(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        s = socket.socket()
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except OSError:
            time.sleep(0.3)
    return False


def main():
    # 基线：variant 1 数据 + C2 对照（c_ml 独立运行，回归原 C2 断言）
    r = run(["analysis/make_c_data.py"])
    check("make_c_data 运行（variant 1）", r.returncode == 0, r.stderr[-200:])
    r = run(["analysis/c_ml.py"])
    check("c_ml 运行（C2 回归）", r.returncode == 0, r.stderr[-300:])
    compare1 = read_json(DATA / "c_compare.json")
    check("c_compare.json 8 组且字段齐全",
          len(compare1) == 8 and all(
              k in c for c in compare1 for k in
              ("time", "temperature", "humidity", "rule_status", "ml_verdict", "ml_text", "ml_score")
          ),
          str(compare1)[:200])
    diff1 = [c for c in compare1 if c["rule_status"] == "正常" and c["ml_verdict"] == -1]
    check("C2 回归：差异行存在且含 29/72 候选", any(c["temperature"] == 29.0 for c in diff1), str(diff1)[:200])
    check("C2 回归：控制台输出含差异说明", "发现" in r.stdout and "ML:与历史明显不同" in r.stdout, r.stdout[-200:])

    # ① 报告生成（stats 用 dormmate2.csv；ML 区数据来自 data/c_compare.json）
    r = run(["analysis/analyze.py", str(DATA / "dormmate2.csv"), "--out", str(DATA)])
    check("analyze.py 生成报告", r.returncode == 0, r.stderr[-300:])
    html1 = read_report()
    check("报告含 ML 异常分析（C3）区", "ML 异常分析（C3）" in html1)
    check("报告 ML 区行数与 c_compare.json 一致",
          html1.count("<td>dorm-a</td>") == len(compare1), html1.count("<td>dorm-a</td>"))
    check("三列并排：29℃/72% 候选行（固定规则 正常 + ML 与历史明显不同）",
          "29℃ / 72%" in html1 and "与历史明显不同" in html1,
          html1[html1.find("ML 异常分析"):html1.find("ML 异常分析") + 1200])
    check("差异行高亮类存在且数量一致",
          "class='ml-diff'" in html1 and html1.count("class='ml-diff'") == len(diff1),
          html1.count("class='ml-diff'"))
    check("控制台输出 ML 对照摘要", "ML 异常分析（C3" in r.stdout and "差异行" in r.stdout, r.stdout[-300:])
    shutil.copy(DATA / "report.html", EVIDENCE / "c3-report-variant1.html")
    (EVIDENCE / "c3-console-v1.txt").write_text(r.stdout, encoding="utf-8")

    # ② c_compare.json 缺失时自动重生成（项目内临时目录验证，不碰 data/ 基线文件）
    scratch = ROOT / "simulator" / ".c3-scratch"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    shutil.copy(DATA / "c_history.csv", scratch / "c_history.csv")
    shutil.copy(DATA / "c_new.csv", scratch / "c_new.csv")
    r = run(["analysis/analyze.py", str(DATA / "dormmate2.csv"), "--out", str(scratch)])
    check("scratch 目录无 c_compare.json 时 analyze.py 自动重生成",
          (scratch / "c_compare.json").exists() and r.returncode == 0,
          r.stderr[-300:] + str(list(scratch.iterdir())))
    compare_reg = read_json(scratch / "c_compare.json")
    check("自动重生成结果与 c_ml.py 输出逐字段一致（零重写）", compare_reg == compare1)
    check("scratch 报告含 ML 区", "ML 异常分析（C3）" in (scratch / "report.html").read_text(encoding="utf-8"))
    shutil.rmtree(scratch, ignore_errors=True)

    # ③ 换一份新数据（variant 2）→ 报告全量重新生成 ML 结果
    new_before = (DATA / "c_new.csv").read_text(encoding="utf-8")
    r = run(["analysis/make_c_data.py", "--variant", "2"])
    check("variant 2 数据生成", r.returncode == 0, r.stderr[-200:])
    new_after = (DATA / "c_new.csv").read_text(encoding="utf-8")
    check("c_new.csv 已变化（换数据）", new_after != new_before)
    r = run(["analysis/analyze.py", str(DATA / "dormmate2.csv"), "--out", str(DATA)])
    check("换数据后 analyze.py 重跑成功", r.returncode == 0, r.stderr[-300:])
    html2 = read_report()
    compare2 = read_json(DATA / "c_compare.json")
    check("报告 ML 区随新数据更新（variant 2 行出现、variant 1 候选消失）",
          "28.8℃ / 73%" in html2 and "29℃ / 72%" not in html2)
    check("c_compare.json 已按 variant 2 重生成",
          compare2 != compare1 and compare2[0]["temperature"] == 24.9, str(compare2[0])[:120])
    diff2 = [c for c in compare2 if c["rule_status"] == "正常" and c["ml_verdict"] == -1]
    check("variant 2 差异行数量与报告高亮一致",
          html2.count("class='ml-diff'") == len(diff2), (html2.count("class='ml-diff'"), len(diff2)))
    check("variant 2 报告与 variant 1 报告不同", html2 != html1)
    shutil.copy(DATA / "report.html", EVIDENCE / "c3-report-variant2.html")
    (EVIDENCE / "c3-console-v2.txt").write_text(r.stdout, encoding="utf-8")

    # ④ 收尾：恢复 variant 1 基线并重跑（仓库数据回到基线，报告仍含 ML 区）
    run(["analysis/make_c_data.py"])
    r = run(["analysis/c_ml.py"])
    check("收尾 c_ml 重跑（variant 1）", r.returncode == 0, r.stderr[-200:])
    r = run(["analysis/analyze.py", str(DATA / "dormmate2.csv"), "--out", str(DATA)])
    check("收尾 analyze.py 重跑", r.returncode == 0, r.stderr[-300:])
    html_final = read_report()
    check("收尾：报告回到 variant 1 基线（含 29/72 行）", "29℃ / 72%" in html_final)
    check("收尾：c_compare.json 与基线一致", read_json(DATA / "c_compare.json") == compare1)

    # ⑤ 证据截图（本地静态服务 + Playwright，无头浏览器渲染 report.html）
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "5500", "--bind", "127.0.0.1"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_port(5500):
            check("5500 静态服务就绪", False, "端口未就绪")
        else:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1100, "height": 1600})
                page.goto("http://127.0.0.1:5500/data/report.html")
                page.wait_for_selector("section", timeout=10000)
                page.screenshot(path=str(EVIDENCE / "c3-report.png"), full_page=True)
                browser.close()
            check("证据截图 c3-report.png 已生成", (EVIDENCE / "c3-report.png").exists())
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

    print("C3 RESULT: %d failures" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
