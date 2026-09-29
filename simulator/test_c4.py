"""DormMate C S4 自动化验证（simulator/test_c4.py）

C4 不理想案例（SPEC §9 C4 / MASTER_PLAN §7.5 S4）：从实际对照结果中保留 1 个
"判断不太理想"的例子（数据 + 模型输出 + 可能原因），写入 README。
验证点：
  ① README 记录案例且数字与 data/c_compare.json 实际输出一致（27.5/70 → 0.6738，不虚构）
  ② README 引用的对照数字（29/72、16/60、31/60、25/80 分数）与 c_compare.json 一致
  ③ 案例数据在 data/c_new.csv 中真实存在（数据 + 模型输出已保留）
  ④ 可能原因引用的历史画像（40 条 / 24~26℃ / 55~65%）与 data/c_history.csv 一致
  ⑤ C4 红线口径：README 写明不做的项；c_ml.py 无 Label/Accuracy/F1/混淆矩阵/调参代码

用法：python simulator/test_c4.py（无需 Broker，纯 Python）
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures = []


def check(name, cond, actual=""):
    print(("PASS" if cond else "FAIL") + " | " + name + ((" | 实际: " + str(actual)) if not cond else ""))
    if not cond:
        failures.append(name)


readme = (ROOT / "README.md").read_text(encoding="utf-8")
compare = json.loads((ROOT / "data" / "c_compare.json").read_text(encoding="utf-8"))
by_key = {(c["temperature"], c["humidity"]): c for c in compare}

# ① 案例已记录且数字与 c_compare.json 实际输出一致（不虚构、不调参）
case = by_key.get((27.5, 70.0))
check("c_compare.json 中存在 27.5/70 行", case is not None)
if case:
    check("案例实际输出：规则正常 + ML 与历史明显不同",
          case["rule_status"] == "正常" and case["ml_verdict"] == -1 and case["ml_text"] == "与历史明显不同",
          str(case))
    check("案例实际分数 0.6738（README 引用值一致）", case["ml_score"] == 0.6738, case["ml_score"])
check("README 含 C4 不理想案例段", "不理想案例（C4）" in readme)
check("README 记录案例数据与输出", "27.5℃ / 70%" in readme and "与历史明显不同" in readme and "0.6738" in readme)

# ② README 引用的对照数字与 c_compare.json 一致
check("README 引用 29/72 分数与实际一致",
      "0.6738" in readme and by_key[(29.0, 72.0)]["ml_score"] == 0.6738)
for key, claimed in ([(16.0, 60.0), "0.5641"], [(31.0, 60.0), "0.5967"], [(25.0, 80.0), "0.6219"]):
    row = by_key.get(key)
    check(f"README 引用 {key[0]}/{key[1]} 分数 {claimed} 与实际一致",
          row is not None and row["ml_score"] == float(claimed) and claimed in readme,
          str(row)[:120] if row else "缺失行")
check("'并列最高分'表述成立（27.5/70 与 29/72 均为全表最高）",
      by_key[(27.5, 70.0)]["ml_score"] == by_key[(29.0, 72.0)]["ml_score"]
      == max(c["ml_score"] for c in compare))

# ③ 案例数据在新数据 CSV 中真实存在（数据已保留）
with (ROOT / "data" / "c_new.csv").open(encoding="utf-8") as f:
    new_rows = list(csv.reader(f))
cand = [r for r in new_rows[1:] if float(r[1]) == 27.5 and float(r[2]) == 70.0]
check("c_new.csv 保留 27.5/70 案例数据", len(cand) == 1 and cand[0][3] == "正常", cand)

# ④ 可能原因引用的历史画像与 c_history.csv 一致
with (ROOT / "data" / "c_history.csv").open(encoding="utf-8") as f:
    hist_rows = list(csv.reader(f))[1:]
temps = [float(r[1]) for r in hist_rows]
hums = [float(r[2]) for r in hist_rows]
check("README 引用'40 条'与实际一致", "40 条" in readme and len(hist_rows) == 40, len(hist_rows))
check("README 引用历史窄区间与实际一致（全部落在 24~26 / 55~65）",
      "24~26℃" in readme and "55~65%" in readme
      and min(temps) >= 24.0 and max(temps) <= 26.0 and min(hums) >= 55.0 and max(hums) <= 65.0,
      (min(temps), max(temps), min(hums), max(hums)))

# ⑤ C4 红线口径：不做的项写明；模型代码无 Label/Accuracy/F1/混淆矩阵/调参
check("README 写明 C4 不做的口径（Label/Accuracy/F1/混淆矩阵/调参/版本管理）",
      "不引入" in readme and "Label" in readme and "Accuracy" in readme and "F1" in readme
      and "混淆矩阵" in readme and "调参" in readme and "版本管理" in readme)
c_ml_src = (ROOT / "analysis" / "c_ml.py").read_text(encoding="utf-8").lower()
# 注：c_ml.py 文档字符串含 "scikit-learn"（替代原因说明，属文档而非代码），
# 故只查真正的 import / 评估 / 调参代码
check("c_ml.py 无 Label/Accuracy/F1/混淆矩阵/调参/评估代码",
      all(w not in c_ml_src for w in ("accuracy", "confusion", "f1", "label", "grid_search", "randomizedsearchcv"))
      and "import sklearn" not in c_ml_src and "from sklearn" not in c_ml_src,
      [w for w in ("accuracy", "confusion", "f1", "label") if w in c_ml_src])

print("C4 RESULT: %d failures" % len(failures))
sys.exit(1 if failures else 0)
