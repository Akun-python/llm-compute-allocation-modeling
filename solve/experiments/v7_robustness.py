# -*- coding: utf-8 -*-
"""
v7 实验: 稳健性与结构性检验
  A) 经典标度律: 留一族交叉验证 (B4 六族: Pythia/Qwen2/OPT/Cerebras-GPT/Phi/LLaMA)
     —— 用 5 族拟合、第 6 族验证(去族级偏移), 检验跨族泛化是否依赖特定族
  B) 前沿回归: 结构断点检验 (Chow 检验, 以 2023/2024 为断点) —— 检验技术进步率是否恒定
输出: experiments/v7_*.csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import B, C, RES, FIG, BASE
from scipy.optimize import least_squares

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)


def fit_classical(N, D, L):
    def resid(p):
        E, A, a, B, b = p
        return E + A * N ** (-a) + B * D ** (-b) - L
    return least_squares(resid, [L.min() * 0.7, 3, 0.3, 3, 0.3],
                         bounds=([0, 1e-6, 1e-4, 1e-6, 1e-4], [L.min() * 1.2, 1e3, 5, 1e3, 5]),
                         max_nfev=40000).x


def predict_classical(p, N, D):
    E, A, a, B, b = p
    return E + A * N ** (-a) + B * D ** (-b)


def r2_offset(y, yhat):
    off = np.mean(y - yhat)
    ss = np.sum((y - (yhat + off)) ** 2)
    return 1 - ss / np.sum((y - y.mean()) ** 2)


def main():
    # ===== A: 留一族交叉验证 =====
    bl = pd.read_csv(os.path.join(B, "scaling_baseline.csv"))
    bl = bl[bl["val_loss"].notna()]
    fams = sorted(bl["family"].unique())
    print("B4 六族:", fams, "n=", len(bl))
    rows = []
    for held in fams:
        tr = bl[bl["family"] != held]
        te = bl[bl["family"] == held]
        p = fit_classical(tr["N_params_B"].to_numpy(), tr["D_tokens_B"].to_numpy(), tr["val_loss"].to_numpy())
        lh = predict_classical(p, te["N_params_B"].to_numpy(), te["D_tokens_B"].to_numpy())
        rows.append({"held_out_family": held, "n_train": len(tr), "n_test": len(te),
                     "r2_offset": r2_offset(te["val_loss"].to_numpy(), lh),
                     "r2_raw": 1 - np.sum((te["val_loss"].to_numpy() - lh) ** 2)
                               / np.sum((te["val_loss"].to_numpy() - te["val_loss"].mean()) ** 2),
                     "alpha": float(p[2]), "beta": float(p[4])})
        print(f"留出 {held}: n={len(te)} 去偏移R2={rows[-1]['r2_offset']:.4f} alpha={p[2]:.3f} beta={p[4]:.3f}")
    cv = pd.DataFrame(rows)
    cv.to_csv(os.path.join(EX, "v7_p2_lofo.csv"), index=False, encoding="utf-8-sig")
    print("\n留一族验证汇总: 去偏移 R2 均值 =", cv["r2_offset"].mean().round(4),
          "alpha 均值 =", cv["alpha"].mean().round(4), "+-", cv["alpha"].std().round(4))

    # ===== B: 前沿结构断点 (Chow 检验) =====
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

    def ols_rss(X, y):
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        return np.sum((y - X @ b) ** 2), b

    X = np.column_stack([np.ones(len(dfm)), dfm["lnN"], dfm["t"]])
    y = dfm["lnS"].to_numpy()
    rss_full, b_full = ols_rss(X, y)
    n, k = X.shape
    chow_rows = []
    for break_t in [1.5, 2.5, 3.5]:   # 2023.5, 2024.5, 2025.5
        m1 = dfm["t"] < break_t
        n1, n2 = m1.sum(), (~m1).sum()
        if n1 < 20 or n2 < 20:
            continue
        rss1, _ = ols_rss(X[m1], y[m1])
        rss2, _ = ols_rss(X[~m1], y[~m1])
        rss_ur = rss1 + rss2
        F = ((rss_full - rss_ur) / k) / (rss_ur / (n - 2 * k))
        from scipy.stats import f as fdist
        pval = 1 - fdist.cdf(F, k, n - 2 * k)
        chow_rows.append({"break_t": break_t, "n1": n1, "n2": n2, "F": F, "p": pval,
                          "rss_full": rss_full, "rss_ur": rss_ur})
        print(f"\nChow 断点 t={break_t} (n1={n1}, n2={n2}): F={F:.1f}, p={pval:.4f}")
    chow = pd.DataFrame(chow_rows)
    chow.to_csv(os.path.join(EX, "v7_p4_chow.csv"), index=False, encoding="utf-8-sig")

    # 分段回归系数 (断点后技术进步率是否加速?)
    for break_t in [2.5]:
        m1 = dfm["t"] < break_t
        _, b1 = ols_rss(X[m1], y[m1])
        _, b2 = ols_rss(X[~m1], y[~m1])
        print(f"\n分段回归 (断点 {break_t}): 前段 bT={b1[2]:.3f} bN={b1[1]:.3f}; 后段 bT={b2[2]:.3f} bN={b2[1]:.3f}")

    print("\ndone v7")


if __name__ == "__main__":
    main()
