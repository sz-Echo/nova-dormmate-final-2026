"""DormMate C S1 自动化验证（simulator/test_c1.py）

C1 数据准备（SPEC §9 C1）：单节点模拟历史 + 待判断新数据严格分离；random_state=42 可复现；
"模拟"标记与数据来源写入 README；换新历史 CSV 可重跑（重跑脚本即重生成）。

用法：python simulator/test_c1.py（无需 Broker，纯 Python）
"""
import csv
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


def read_csv(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.reader(f))


r = run(["analysis/make_c_data.py"])
check("make_c_data 运行", r.returncode == 0, r.stderr[-200:])

history_path = ROOT / "data" / "c_history.csv"
new_path = ROOT / "data" / "c_new.csv"
check("c_history.csv 与 c_new.csv 均生成", history_path.exists() and new_path.exists())

hist = read_csv(history_path)
new = read_csv(new_path)
check("历史 4 列最小格式 + 40 条", len(hist) == 41 and hist[0] == ["time", "temperature", "humidity", "status"],
      (len(hist), hist[0]))
check("新数据 8 组 + 4 列", len(new) == 9 and new[0] == ["time", "temperature", "humidity", "status"],
      (len(new), new[0]))

# 历史画像：24~26℃ / 55~65%，全部正常（"平时"）
temps = [float(row[1]) for row in hist[1:]]
hums = [float(row[2]) for row in hist[1:]]
check("历史画像 24~26℃ / 55~65%", min(temps) >= 23.9 and max(temps) <= 26.1 and min(hums) >= 54.9 and max(hums) <= 65.1,
      (min(temps), max(temps), min(hums), max(hums)))
check("历史全部为正常", all(row[3] == "正常" for row in hist[1:]))

# 分离红线：两份数据时间不重叠、文件独立（不先混入再判断自己）
hist_times = {row[0] for row in hist[1:]}
new_times = {row[0] for row in new[1:]}
check("历史与新数据时间零重叠（严格分离）", not (hist_times & new_times))

# 候选行存在：29℃/72% 规则正常但与平时明显不同（截图 C2 例句）
cand = [row for row in new[1:] if float(row[1]) == 29.0 and float(row[2]) == 72.0]
check("候选 29℃/72% 存在且规则判定为正常", len(cand) == 1 and cand[0][3] == "正常", cand)

# 可复现：random_state=42，重复运行产出逐字节一致
r2 = run(["analysis/make_c_data.py"])
hist2 = read_csv(history_path)
check("重复运行历史数据逐行一致（random_state=42 可复现）", hist2 == hist, "不一致")

# README：模拟标记 + 两份数据来源写清（C1 完成线）
readme = (ROOT / "README.md").read_text(encoding="utf-8")
check("README 含模拟标记与数据来源说明",
      "c_history.csv" in readme and "c_new.csv" in readme and "模拟" in readme and "数据来源" in readme)
check("README 写清历史与新数据分离",
      "历史与新数据要分开" in readme and "make_c_data.py" in readme)

print("C1 RESULT: %d failures" % len(failures))
sys.exit(1 if failures else 0)
