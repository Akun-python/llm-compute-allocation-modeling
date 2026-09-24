# -*- coding: utf-8 -*-
"""
v12 实验: 精确分位数回归的参数与预测不确定性 (bootstrap on LP-QR)
对 (c, bN, bT) 做 300 次样本自助重抽, 报告 90% 参数区间;
并将参数不确定性叠加残差噪声, 给出 12/24 个月前沿预测的合并区间.
输出: experiments/v12_p4_ci.json/csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, RES, FIG, BASE
from scipy.optimize import linprog

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)


def qr_fit(X, y, tau=0.9):
    n, m = X.shape
    cvec = np.concatenate([np.zeros(m), tau * np.ones(n), (1 - tau) * np.ones(n)])
    Aeq = np.hstack([X, np.eye(n), -np.eye(n)])
    res = linprog(cvec, A_eq=Aeq, b_eq=y, bounds=[(None, None)] * m + [(0, None)] * (2 * n),
                  method="highs")
    if not res.success:
        raise RuntimeError("LP QR failed")
    return res.x[:m]


def load_frontier():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb["year"] = lb["date"].dt.year
    lb = lb[lb["year"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[lic & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0)].copy()
    dfm = dfm[dfm["year"] >= 2022]
    dfm["lnS"] = np.log(dfm["Average ⬆️"])
    dfm["lnN"] = np.log(dfm["#Params (B)"])
    dfm["t"] = dfm["year"] - 2022.0
    return dfm


def main():
    dfm = load_frontier()
    X = np.column_stack([np.ones(len(dfm)), dfm["lnN"], dfm["t"]])
    y = dfm["lnS"].to_numpy()
    n = len(dfm)
    b0 = qr_fit(X, y, 0.9)
    resid = y - X @ b0
    print("全样本 QR90: c=%.3f bN=%.3f bT=%.4f  (n=%d)" % (b0[0], b0[1], b0[2], n))

    rng = np.random.default_rng(7)
    B = 300
    draws = np.empty((B, 3))
    for k in range(B):
        idx = rng.choice(n, n, replace=True)
        try:
            draws[k] = qr_fit(X[idx], y[idx], 0.9)
        except RuntimeError:
            draws[k] = b0
    lo, hi = np.percentile(draws, [5, 95], axis=0)
    for name, k in [("c", 0), ("bN", 1), ("bT", 2)]:
        print(f"{name}: {b0[k]:.4f}  90%%CI=[{lo[k]:.4f}, {hi[k]:.4f}]")

    # 预测合并区间: 参数不确定性 + 残差噪声
    sigma = np.std(resid)
    gN = 1.251125395176952
    lnN0, t0 = 2.69, 3.0
    results = {}
    for months in [12, 24]:
        t_h = t0 + months / 12.0
        paths = []
        for k in range(2000):
            b = draws[rng.integers(B)]
            eps = rng.normal(0, sigma)
            lnS = b[0] + b[1] * (lnN0 + gN * months / 12.0) + b[2] * t_h + eps
            paths.append(np.exp(lnS))
        p = np.array(paths)
        results[months] = {"median": float(np.median(p)),
                           "p10": float(np.percentile(p, 10)),
                           "p90": float(np.percentile(p, 90))}
        print(f"{months}个月: median={np.median(p):.1f} [p10={np.percentile(p,10):.1f}, p90={np.percentile(p,90):.1f}]")

    with open(os.path.join(EX, "v12_p4_ci.json"), "w", encoding="utf-8") as f:
        json.dump({"b0": {k: float(v) for k, v in zip(["c", "bN", "bT"], b0)},
                   "ci90": {"c": [float(lo[0]), float(hi[0])],
                            "bN": [float(lo[1]), float(hi[1])],
                            "bT": [float(lo[2]), float(hi[2])]},
                   "sigma": float(sigma), "forecast": results},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v12")


if __name__ == "__main__":
    main()