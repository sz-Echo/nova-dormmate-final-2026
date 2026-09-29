"""DormMate C S2 固定规则与轻量 ML 对照（analysis/c_ml.py）

C2（SPEC §9 C2 / MASTER_PLAN §6.6）：IsolationForest（n_estimators=100、random_state=42）
用历史 fit、对新数据 predict；固定规则列复用 compute_status（零重写）；
对照表输出控制台 + data/c_compare.json；寻找"固定规则正常、ML 明显不同"案例；
未出现则如实记录"本次测试未出现"（截图 C2：不伪造、不调参凑结果）。

predict 返回（截图 58 口径）：1 = 接近历史常态，-1 = 与历史明显不同。

模型实现：本项目自实现 IsolationForest（纯 numpy，确定性 random_state=42）。
替代原因（README 已记录）：scikit-learn 在本机 Python 3.14 + Windows 上安装成功但无法导入
（scipy 1.18.1 编译扩展 DLL 加载失败：cython_blas / _rank_filter_1d ImportError，PyPI 与
镜像重装均复现）；按 SPEC §13-3"等价替代"先例与 C 契约"sklearn 优先、自实现兜底"落地。
判定阈值：异常分数 s > 0.5 判 -1（s = 2^(-平均路径长度/c(n))，与历史平均路径等长或更短即为异常）。

用法：python analysis/c_ml.py [--history data/c_history.csv] [--new data/c_new.csv]
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.analyze import compute_status  # noqa: E402  # 统一规则零重写（SPEC §6）

N_ESTIMATORS = 100          # 截图 58 最小代码路线参数
RANDOM_STATE = 42           # C 契约：固定随机种子，可复现
ANOMALY_THRESHOLD = 0.5     # 自实现判定阈值（见模块说明）


def c_factor(n):
    """iForest 平均路径长度归一化常数（n=1→0；n=2→1；否则标准公式）。"""
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    return 2 * (math.log(n - 1) + 0.5772156649) - 2 * (n - 1) / n


def build_tree(X, depth, limit, rng):
    """单棵隔离树：随机特征 + 随机切点递归分裂，直到深度上限或单点。"""
    n = X.shape[0]
    if depth >= limit or n <= 1:
        return {"size": n}
    dim = rng.randrange(X.shape[1])
    lo = float(X[:, dim].min())
    hi = float(X[:, dim].max())
    if hi == lo:
        return {"size": n}
    cut = rng.uniform(lo, hi)
    left = X[X[:, dim] <= cut]
    right = X[X[:, dim] > cut]
    if left.shape[0] == 0 or right.shape[0] == 0:
        return {"size": n}
    return {
        "dim": dim,
        "cut": cut,
        "left": build_tree(left, depth + 1, limit, rng),
        "right": build_tree(right, depth + 1, limit, rng),
    }


def path_length(tree, x):
    """路径长度：每分裂 +1，到叶子加 c(叶子大小)（与 sklearn 同思路的近似）。"""
    if "dim" not in tree:
        return c_factor(tree["size"])
    if x[tree["dim"]] <= tree["cut"]:
        return 1 + path_length(tree["left"], x)
    return 1 + path_length(tree["right"], x)


def fit_isolation_forest(X):
    """fit：小数据（40 条）全量建 100 棵树；深度上限 ceil(log2(n))（iForest 标准做法，无调参）。"""
    n = X.shape[0]
    limit = int(math.ceil(math.log2(max(2, n))))
    rng = random.Random(RANDOM_STATE)
    trees = [build_tree(X, 0, limit, rng) for _ in range(N_ESTIMATORS)]
    return trees, c_factor(n)


def score_samples(trees, c_n, x):
    depths = [path_length(t, x) for t in trees]
    return float(2 ** (-(sum(depths) / len(depths)) / c_n))


def predict(trees, c_n, X):
    return np.array([-1 if score_samples(trees, c_n, row) > ANOMALY_THRESHOLD else 1 for row in X])


def load_csv_matrix(path):
    """读 4 列 CSV 的温度/湿度两列（时间列无逗号，np.loadtxt 可用）。"""
    return np.loadtxt(path, delimiter=",", skiprows=1, usecols=(1, 2), encoding="utf-8")


def load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        next(f)   # 表头
        for line in f:
            parts = line.strip().split(",")
            rows.append({
                "time": parts[0],
                "temperature": float(parts[1]),
                "humidity": float(parts[2]),
            })
    return rows


def compare_rows(history_csv, new_csv):
    """fit 历史 → predict 新数据 → 对照行列表（含固定规则列，复用 compute_status 零重写）。

    C3 复用：c_ml.main（控制台 + c_compare.json）与 analysis/analyze.py 报告刷新
    共用同一实现，保证报告 ML 区与 C2 输出永远一致。
    """
    X_hist = load_csv_matrix(history_csv)
    X_new = load_csv_matrix(new_csv)
    new_rows = load_rows(new_csv)
    if len(new_rows) != X_new.shape[0]:
        raise ValueError("新数据行列数不一致")
    trees, c_n = fit_isolation_forest(X_hist)
    compare = []
    for row, verdict in zip(new_rows, predict(trees, c_n, X_new)):
        rule = compute_status(row["temperature"], row["humidity"])
        score = score_samples(trees, c_n, np.array([row["temperature"], row["humidity"]]))
        ml_text = "接近历史常态" if verdict == 1 else "与历史明显不同"
        compare.append({
            "time": row["time"],
            "temperature": row["temperature"],
            "humidity": row["humidity"],
            "rule_status": rule,
            "ml_verdict": int(verdict),
            "ml_text": ml_text,
            "ml_score": round(score, 4),
        })
    return compare


def main():
    parser = argparse.ArgumentParser(description="C2 固定规则 / ML 对照（自实现 IsolationForest）")
    parser.add_argument("--history", default=str(ROOT / "data" / "c_history.csv"), help="历史 CSV（默认 data/c_history.csv）")
    parser.add_argument("--new", default=str(ROOT / "data" / "c_new.csv"), help="待判断新数据 CSV（默认 data/c_new.csv）")
    args = parser.parse_args()

    try:
        compare = compare_rows(args.history, args.new)
    except (ValueError, OSError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    X_hist = load_csv_matrix(args.history)
    print(f"=== C2 固定规则 / ML 对照 ===")
    print(f"历史: {args.history}（{X_hist.shape[0]} 条，n_estimators={N_ESTIMATORS}，random_state={RANDOM_STATE}）")
    print(f"新数据: {args.new}（{len(compare)} 条，与历史严格分离）")
    print(f"{'时间':22s} {'温度':>6s} {'湿度':>6s} {'固定规则':>6s} {'ML 判定':>12s} {'异常分数':>8s}")
    for c in compare:
        print(f"{c['time']:22s} {c['temperature']:>6.1f} {c['humidity']:>6.1f} {c['rule_status']:>6s} {c['ml_text']:>12s} {c['ml_score']:>8.4f}")

    # 截图 C2：优先寻找"固定规则仍为正常，但 ML 认为与该宿舍历史明显不同"的情况；
    # 不要求一定出现——未出现则如实记录，不伪造、不调参凑结果
    diff = [c for c in compare if c["rule_status"] == "正常" and c["ml_verdict"] == -1]
    print()
    if diff:
        print(f"发现 {len(diff)} 组'固定规则正常、ML 明显不同'（候选案例，用于 C4 说明）:")
        for c in diff:
            print(f"  {c['time']} {c['temperature']}℃/{c['humidity']}% —— 规则:{c['rule_status']} / ML:{c['ml_text']}（分数 {c['ml_score']}）")
    else:
        print("本次测试未出现'固定规则正常、ML 明显不同'的情况；观察：新数据全部被 ML 判为接近历史常态。")

    out = ROOT / "data" / "c_compare.json"
    out.write_text(json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n对照结果已写入: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
