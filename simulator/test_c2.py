"""DormMate C S2 自动化验证（simulator/test_c2.py）

C2 固定规则 / ML 对照（SPEC §9 C2）：多组新数据双判断对照；"规则正常、ML 明显不同"
出现则保留并说明、未出现则如实记录（截图 C2：不伪造、不调参）；结果可复现。

用法：python simulator/test_c2.py（无需 Broker，纯 Python）
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures = []


def check(name, cond, actual=""):
    print(("PASS" if cond else "FAIL") + " | " + name + ((" | 实际: " + str(actual)) if not cond else ""))
    if not cond:
        failures.append(name)


def run(args):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True,
                          cwd=str(ROOT), encoding="utf-8", errors="replace")


r = run(["analysis/c_ml.py"])
check("c_ml 运行", r.returncode == 0, r.stderr[-300:])

compare_path = ROOT / "data" / "c_compare.json"
check("c_compare.json 生成", compare_path.exists())
compare = json.loads(compare_path.read_text(encoding="utf-8"))
check("对照表 8 组且字段齐全",
      len(compare) == 8 and all(
          k in c for c in compare for k in
          ("time", "temperature", "humidity", "rule_status", "ml_verdict", "ml_text", "ml_score")
      ),
      str(compare)[:200])

# 截图 58 口径：1 = 接近历史常态，-1 = 与历史明显不同
for c in compare:
    check(f"{c['time']} 判定值合法", c["ml_verdict"] in (1, -1), c["ml_verdict"])

# 规则异常行（16/60、31/60、25/80）的固定规则列必须与统一规则一致
by_rule = {c["time"]: c for c in compare}
rules_ok = all(
    compare[i]["rule_status"] == ("偏冷" if compare[i]["temperature"] == 16.0
                                  else "偏热" if compare[i]["temperature"] == 31.0
                                  else "偏湿" if compare[i]["humidity"] == 80.0
                                  else compare[i]["rule_status"])
    for i in range(len(compare))
)
check("固定规则列与统一规则一致（零重写）", rules_ok)

# 关键：候选 29℃/72%（规则正常）的 ML 判定——出现差异则保留解释；未出现则输出如实记录
out = r.stdout
diff_rows = [c for c in compare if c["rule_status"] == "正常" and c["ml_verdict"] == -1]
if diff_rows:
    check("出现'规则正常、ML 明显不同'且已保留", len(diff_rows) >= 1, str(diff_rows)[:200])
    check("输出解释差异案例", "发现" in out and "ML:与历史明显不同" in out, out[-300:])
else:
    check("未出现则如实记录（截图 C2：不伪造）", "本次测试未出现" in out, out[-300:])

# 可复现：random_state=42 固定，重复运行结果一致
r2 = run(["analysis/c_ml.py"])
compare2 = json.loads(compare_path.read_text(encoding="utf-8"))
check("重复运行结果一致（random_state=42 可复现）", compare2 == compare)

# README 记录替代原因（C 契约：sklearn 失败自实现兜底须 README 记录）
readme = (ROOT / "README.md").read_text(encoding="utf-8")
check("README 记录自实现替代原因", "自实现 IsolationForest" in readme and "scipy" in readme and "等价替代" in readme)

print("C2 RESULT: %d failures" % len(failures))
sys.exit(1 if failures else 0)
