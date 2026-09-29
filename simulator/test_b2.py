"""DormMate B S2 自动化验证（simulator/test_b2.py）

B2 判断依据（SPEC §9 B2 / MASTER_PLAN §6.5）：Dashboard 依据卡片——每节点三项指标
（连续异常时长 / 异常次数 / 当前状态）各附数据来源；优先节点 ★ + 原因。
验证点：4 组三节点情况（test_a1.py 预设序列）→ 优先对象与依据短语合理变化 + 来源可指认。

前置：本机 Mosquitto Broker 已启动（127.0.0.1:1883 / WebSocket 8083）。
用法：python simulator/test_b2.py
脚本自动：临时启动 127.0.0.1:5500 静态服务 → Playwright 开 dashboard（每组前 reload 清空历史）
→ 调用 simulator/test_a1.py --group N 发布 → 断言依据卡片 → 截图 docs/evidence/b/ → 关闭服务。
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:5500"
EVIDENCE = ROOT / "docs" / "evidence" / "b"
EVIDENCE.mkdir(parents=True, exist_ok=True)
failures = []

# 四组情况 → 期望（优先节点, 依据短语）
EXPECTED = {
    1: ("dorm-b", "是唯一异常节点"),
    2: ("dorm-b", "持续异常时间更长"),
    3: ("dorm-b", "异常次数更多"),
    4: ("dorm-a", "按节点顺序优先"),
}


def check(name, cond, actual=""):
    print(("PASS" if cond else "FAIL") + " | " + name + ((" | 实际: " + str(actual)) if not cond else ""))
    if not cond:
        failures.append(name)


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
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "5500", "--bind", "127.0.0.1"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_port(5500):
            check("5500 静态服务就绪", False, "端口未就绪")
            return 1

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 1100})

            for group, (node, phrase) in EXPECTED.items():
                page.goto(BASE + "/dashboard/index.html")
                page.wait_for_selector("#connStatus.online", timeout=15000)
                page.wait_for_timeout(500)
                r = subprocess.run(
                    [sys.executable, str(ROOT / "simulator" / "test_a1.py"), "--group", str(group)],
                    capture_output=True, text=True, timeout=60, cwd=str(ROOT),
                    encoding="utf-8", errors="replace",
                )
                if r.returncode != 0:
                    check(f"组{group} 发布脚本运行", False, r.stderr[-200:])
                    continue
                page.wait_for_timeout(1200)

                winner_node = page.evaluate(
                    "() => { const c = document.querySelector('#evidenceCards .evidence-card.winner');"
                    " return c ? c.querySelector('.ev-node').textContent : null; }"
                )
                winner_line = page.evaluate(
                    "() => { const c = document.querySelector('#evidenceCards .evidence-card.winner');"
                    " return c ? c.querySelector('.ev-winner').textContent : ''; }"
                )
                cards_text = page.inner_text("#evidenceCards")
                check(f"组{group} 优先卡片 = {node}", winner_node == node, winner_node)
                check(f"组{group} 依据短语 = {phrase}", phrase in winner_line, winner_line)
                check(f"组{group} 卡片含指标与来源", "连续异常时长" in cards_text and "异常次数" in cards_text
                      and "依据：" in cards_text, cards_text[:150])
                page.screenshot(path=str(EVIDENCE / f"b2-group{group}.png"))

            # 来源可指认（组 2：dorm-b 异常链时间范围 20:10:00 ~ 20:30:00）
            page.goto(BASE + "/dashboard/index.html")
            page.wait_for_selector("#connStatus.online", timeout=15000)
            page.wait_for_timeout(500)
            subprocess.run(
                [sys.executable, str(ROOT / "simulator" / "test_a1.py"), "--group", "2"],
                capture_output=True, text=True, timeout=60, cwd=str(ROOT),
                encoding="utf-8", errors="replace",
            )
            page.wait_for_timeout(1200)
            cards_text = page.inner_text("#evidenceCards")
            check("来源可指认（完整时间范围 + 连续异常条数）",
                  "2026-09-28 20:10:00 ~ 2026-09-28 20:30:00 连续异常 5 条" in cards_text,
                  cards_text[:400])

            # 测试页（含组⑧ B2 断言）仍全过
            page.goto(BASE + "/dashboard/test-priority.html")
            page.wait_for_selector("#summary", timeout=10000)
            summary = page.inner_text("#summary")
            check("test-priority.html 汇总 0 失败（含组⑧ B2 断言）", "0 失败" in summary, summary)
            page.screenshot(path=str(EVIDENCE / "b2-test-page.png"), full_page=True)

            browser.close()

        print("B2 RESULT: %d failures" % len(failures))
        return 1 if failures else 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
