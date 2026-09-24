# -*- coding: utf-8 -*-
"""
v52 实验: 前沿模型的规模/时间弹性的分位数族
对开放行 (2024-06..2025-03) 做分位数回归 lnS = c0 + bN lnN + bT t,
tau in [0.5, 0.7, 0.8, 0.9, 0.95]:
1) 各分位的 bN/bT/截距表 (LP 线性规划);
2) 前沿定义稳健性: QR90 主链路的 0.364 在分位族中的位置;
3) 规模弹性随分位的演化 (领先者是否更规模弹性).
输出: experiments/v52_p4_quantile_ladder.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, BASE
from scipy.optimize import linprog

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


def qreg(X, y, tau):
    n, k = X.shape
    # min tau*sum(u) + (1-tau)*sum(v), s.t. Xb - y = u - v
    c = np.concatenate([np.zeros(k), tau * np.ones(n), (1 - tau) * np.ones(n)])
    A_eq = np.hstack([X, np.eye(n), -np.eye(n)])
    res = linprog(c, A_eq=A_eq, b_eq=y, bounds=[(None, None)] * k + [(0, None)] * (2 * n),
                  method="highs")
    return res.x[:k]


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb = lb[lb["date"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[(lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) & lic].copy()
    dfm = dfm[dfm["date"] >= "2024-06-01"].copy()
    dfm["lnN"] = np.log(dfm["#Params (B)"])
    dfm["lnS"] = np.log(dfm["Average ⬆️"])
    dfm["t"] = (dfm["date"].dt.year - 2022) + (dfm["date"].dt.month - 1) / 12
    X = np.column_stack([dfm["lnN"], dfm["t"], np.ones(len(dfm))])
    y = dfm["lnS"].to_numpy()

    rows = []
    for tau in [0.5, 0.7, 0.8, 0.9, 0.95]:
        b = qreg(X, y, tau)
        rows.append({"tau": tau, "bN": float(b[0]), "bT": float(b[1]), "c0": float(b[2])})
        print(f"tau={tau:.2f}: bN={b[0]:.3f} bT={b[1]:.3f} c0={b[2]:.3f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v52_p4_quantile_ladder.csv"), index=False, encoding="utf-8-sig")

    # 时间离散化敏感性: 整数年 t vs 月度 t 的 QR90 对比 (同一样本 2493)
    t_int = (dfm["date"].dt.year - 2022).to_numpy(dtype=float)
    X_int = np.column_stack([dfm["lnN"], t_int, np.ones(len(dfm))])
    b_int = qreg(X_int, y, 0.9)
    disc = {"bN_month": float(rows[3]["bN"]), "bT_month": float(rows[3]["bT"]),
            "bN_int": float(b_int[0]), "bT_int": float(b_int[1])}
    print(f"\n离散化敏感性 QR90: t=整数年 bN={b_int[0]:.3f} bT={b_int[1]:.3f} | "
          f"t=月度 bN={rows[3]['bN']:.3f} bT={rows[3]['bT']:.3f}")
    print(f"bT 比值: {disc['bT_month']/disc['bT_int']:.1f}x")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(rdf["tau"], rdf["bN"], marker="o", color="#2563EB", lw=2, label="规模弹性 bN (月度 t)")
    ax.plot(rdf["tau"], rdf["bT"], marker="s", color="#0EA5E9", lw=2, label="时间弹性 bT (月度 t)")
    ax.axhline(0.364, color="#C2410C", lw=1.2, ls="--", label="QR90 主链路 bN=0.364 (整数年 t)")
    ax.axhline(0.089, color="#94A3B8", lw=1.2, ls=":", label="QR90 主链路 bT=0.089 (整数年 t)")
    ax.set_xlabel("分位 tau"); ax.set_ylabel("弹性")
    ax.set_title("v52: 前沿模型弹性的分位数族 (含时间口径对比)")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v52_p4_quantile_ladder.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v52_p4_quantile_ladder.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "n": int(len(dfm)), "discretization": disc},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v52")


if __name__ == "__main__":
    main()