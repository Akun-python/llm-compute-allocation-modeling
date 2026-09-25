# -*- coding: utf-8 -*-
"""
v74 实验: 分位数回归跨框架交叉验证 —— 前沿模型数值稳定性核验 (P4)
同一数据 (C1 开源模型, year>=2022), 同一模型 (lnS = c0 + bN*lnN + bT*t, tau=0.9),
5 个独立实现:
  1) scipy linprog HiGHS 精确LP (主链路, Koenker-Bassett)
  2) statsmodels QuantReg        (IRLS/外点法族)
  3) sklearn QuantileRegressor   (HiGHS LP, alpha=0)
  4) scipy minimize L-BFGS-B     (pinball 损失直接极小化)
  5) torch Adam                  (pinball 损失, 梯度下降)
比较: 系数 (c0,bN,bT), pinball 目标值, 预测差, 以及前沿增长分解的"规模占比" =>
  QR 结论不依赖统计实现/优化器 => 前沿斜率与规模贡献的数值稳定性.
输出: experiments/v74_p4_qr_frameworks.csv/.json/.png
"""
import os, sys, json, math
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, BASE

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"
import plotstyle

TAU = 0.9
PNAMES = ["c0", "bN", "bT"]
GN = 1.251  # C4 开源模型 lnN 年均增速 (主链路拟合值), 用于 eq.7 增长核算


def pinball_sum(beta, X, y, tau=TAU):
    r = y - X @ beta
    return float(np.sum(np.where(r >= 0, tau * r, (tau - 1) * r)))


def load_data():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    ts = pd.read_csv(os.path.join(C, "leaderboard_extended_timeseries.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb["year"] = lb["date"].dt.year
    lb = lb[lb["year"].notna()]
    lic_open = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    lb["is_open"] = lic_open
    dfm = lb[lb["is_open"] & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0)].copy()
    dfm = dfm[dfm["year"] >= 2022]
    dfm["lnS"] = np.log(dfm["Average ⬆️"])
    dfm["lnN"] = np.log(dfm["#Params (B)"])
    dfm["t"] = dfm["year"] - 2022
    X = np.column_stack([np.ones(len(dfm)), dfm["lnN"], dfm["t"]])
    y = dfm["lnS"].to_numpy()
    return X, y, dfm, ts


def qr_linprog(X, y, tau=TAU):
    """主链路: 精确分位数回归 (线性规划, Koenker-Bassett)"""
    from scipy.optimize import linprog
    n, m = X.shape
    c = np.concatenate([np.zeros(m), tau * np.ones(n), (1 - tau) * np.ones(n)])
    Aeq = np.hstack([X, np.eye(n), -np.eye(n)])
    res = linprog(c, A_eq=Aeq, b_eq=y,
                  bounds=[(None, None)] * m + [(0, None)] * (2 * n), method="highs")
    return res.x[:m]


def qr_statsmodels(X, y, tau=TAU):
    from statsmodels.regression.quantile_regression import QuantReg
    fit = QuantReg(y, X).fit(q=tau)
    return np.asarray(fit.params)


def qr_sklearn(X, y, tau=TAU):
    from sklearn.linear_model import QuantileRegressor
    mdl = QuantileRegressor(quantile=tau, alpha=0.0, solver="highs", fit_intercept=False)
    mdl.fit(X, y)
    return mdl.coef_


def qr_lbfgs(X, y, tau=TAU):
    from scipy.optimize import minimize
    rng = np.random.default_rng(3)

    def obj(b):
        r = y - X @ b
        return np.sum(np.where(r >= 0, tau * r, (tau - 1) * r))
    best = None
    for s in range(5):
        b0 = rng.normal(0, 1, X.shape[1])
        res = minimize(obj, b0, method="L-BFGS-B",
                       options={"maxiter": 5000, "ftol": 1e-16, "gtol": 1e-12})
        if res.success and (best is None or res.fun < best[0]):
            best = (res.fun, res.x)
    return best[1]


def qr_torch(X, y, tau=TAU, steps=6000):
    import torch
    tX = torch.tensor(X, dtype=torch.float64)
    ty = torch.tensor(y, dtype=torch.float64)
    beta = torch.tensor(np.array([2.0, 0.3, 0.05]), dtype=torch.float64, requires_grad=True)
    opt = torch.optim.Adam([beta], lr=0.05)
    best_v, best_b = math.inf, None
    for _ in range(steps):
        opt.zero_grad()
        r = ty - tX @ beta
        loss = torch.sum(torch.where(r >= 0, tau * r, (tau - 1) * r))
        loss.backward()
        opt.step()
        if float(loss) < best_v:
            best_v, best_b = float(loss), beta.detach().numpy().copy()
    return best_b


def scale_share(bN, dfm, ts):
    """前沿增长分解的规模占比: scale = bN*ΔlnN, total = ΔlnS (与主链路一致)"""
    fy = []
    for yy in sorted(dfm["year"].unique()):
        g = dfm[dfm["year"] == yy]
        best = g.loc[g["lnS"].idxmax()]
        fy.append({"year": int(yy), "S": float(np.exp(best["lnS"])), "lnN": float(best["lnN"])})
    hist = ts[ts["Year"] <= 2021]
    hist_f = {}
    cmax = -1.0
    for yy in sorted(hist["Year"].unique()):
        cmax = max(cmax, float(hist[hist["Year"] == yy]["Average"].max()))
        hist_f[int(yy)] = cmax
    years_all = sorted(set(list(hist_f.keys()) + [f["year"] for f in fy]))
    shares, scales, totals = [], [], []
    S_prev = lnN_prev = None
    for yy in years_all:
        if yy in hist_f:
            S_cur = float(hist_f[yy])
            lnN_cur = np.log(max(ts[ts["Year"] == yy]["Params_B"].max(), 0.1))
        else:
            r = [f for f in fy if f["year"] == yy]
            if not r:
                continue
            S_cur, lnN_cur = r[0]["S"], r[0]["lnN"]
        if S_prev is not None and S_prev > 0 and S_cur > 0:
            total = np.log(S_cur) - np.log(S_prev)
            scale = bN * (lnN_cur - lnN_prev)
            if abs(total) > 1e-12:
                shares.append(scale / total)
                scales.append(scale)
                totals.append(total)
        S_prev, lnN_prev = S_cur, lnN_cur
    return float(np.mean(shares)), float(np.sum(scales) / np.sum(totals)), shares


def main():
    X, y, dfm, ts = load_data()
    runs = {"LP": qr_linprog(X, y), "statsmodels": qr_statsmodels(X, y),
            "sklearn": qr_sklearn(X, y), "L-BFGS-B": qr_lbfgs(X, y), "Adam": qr_torch(X, y)}
    ref = runs["LP"]
    print(f"数据: n={len(y)}, 特征列=3, tau={TAU}")
    rows = []
    for fw, b in runs.items():
        row = {"framework": fw, "pinball": pinball_sum(b, X, y)}
        for i, nm in enumerate(PNAMES):
            row[nm] = float(b[i])
        ss_m, ss_a, _ = scale_share(b[1], dfm, ts)
        row["scale_share_mean"], row["scale_share_agg"] = ss_m, ss_a
        sga = b[1] * GN / (b[1] * GN + b[2])
        row["share_growthacc"] = float(sga)
        rows.append(row)
        print(f"  {fw:12s} c0={b[0]:.4f} bN={b[1]:.4f} bT={b[2]:.4f} "
              f"pinball={row['pinball']:.6f} | 增长核算规模占比={sga:.5f} "
              f"(逐年均值/聚合={ss_m:.4f}/{ss_a:.4f})")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v74_p4_qr_frameworks.csv"), index=False, encoding="utf-8-sig")

    B = np.array([runs[f] for f in runs])
    spread = (B.max(axis=0) - B.min(axis=0)) / np.abs(np.median(B, axis=0))
    preds = np.array([X @ runs[f] for f in runs])
    max_pred_diff = float(np.abs(preds.max(axis=0) - preds.min(axis=0)).max())
    ss_mean = np.array([r["scale_share_mean"] for r in rows])
    ss_agg = np.array([r["scale_share_agg"] for r in rows])
    sga = np.array([r["share_growthacc"] for r in rows])
    print(f"\n系数相对极差: c0={spread[0]*100:.3e}% bN={spread[1]*100:.3e}% bT={spread[2]*100:.3e}%")
    print(f"预测最大跨框架差异 (n={len(y)}): {max_pred_diff:.2e}")
    print(f"增长核算规模占比 极差: {(sga.max()-sga.min()):.3e} (LP 参考 {sga[0]:.4f})")
    print(f"逐年分解规模占比 极差: 均值{(ss_mean.max()-ss_mean.min()):.3e} 聚合{(ss_agg.max()-ss_agg.min()):.3e}")

    agg = {"n": int(len(y)), "tau": TAU, "gN": GN,
           "coef_rel_spread_pct": {nm: float(s * 100) for nm, s in zip(PNAMES, spread)},
           "max_pred_diff": max_pred_diff,
           "share_growthacc": {fw: float(r["share_growthacc"]) for fw, r in zip(runs, rows)},
           "scale_share_mean": {fw: float(r["scale_share_mean"]) for fw, r in zip(runs, rows)},
           "scale_share_agg": {fw: float(r["scale_share_agg"]) for fw, r in zip(runs, rows)}}
    with open(os.path.join(EX, "v74_p4_qr_frameworks.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rdf.to_dict("records"), "agg": agg}, f, ensure_ascii=False, indent=2)

    # ---- 图: (a) 系数相对偏差 vs LP; (b) 规模占比 + pinball ----
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    ax = axes[0]
    x = np.arange(3)
    w = 0.15
    cols = ["#1685a9", "#3eede7", "#70f3ff", "#44cef6", "#88ada6"]
    for i, fw in enumerate(["statsmodels", "sklearn", "L-BFGS-B", "Adam"]):
        dev = np.abs(B[i + 1] - ref) / np.abs(ref)
        ax.bar(x + (i - 1.5) * w, dev, w, color=cols[i], label=fw)
    ax.set_yscale("log")
    ax.set_xticks(x); ax.set_xticklabels(PNAMES)
    ax.set_ylabel("系数相对偏差 (vs LP, 对数轴)")
    ax.set_title("(a) 跨框架前沿系数相对偏差")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8)

    ax = axes[1]
    x = np.arange(len(runs))
    ax.bar(x, sga, 0.55, color="#177cb0", label="增长核算规模占比 bN·gN/(bN·gN+bT)")
    ax.set_xticks(x); ax.set_xticklabels(list(runs.keys()))
    ax.set_ylim(0.83, 0.85)
    ax.set_ylabel("规模贡献占比")
    ax.set_title("(b) 规模占比跨框架一致")
    for i, v in enumerate(sga):
        ax.text(i, v + 2e-5, f"{v:.5f}", ha="center", fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8, loc="lower right")
    ax.annotate(f"n={len(y)} 点预测最大跨框架差异 {max_pred_diff:.1e}",
                xy=(0.02, 0.92), xycoords="axes fraction", fontsize=8.5, color="#1685a9")
    fig.suptitle("五框架分位数回归交叉验证 —— 前沿系数与规模占比数值稳定性", fontsize=12, y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(EX, "v74_p4_qr_frameworks.png"), dpi=200)
    plt.close(fig)
    print("\ndone v74")


if __name__ == "__main__":
    main()