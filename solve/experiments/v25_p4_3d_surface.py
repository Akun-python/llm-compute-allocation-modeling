# -*- coding: utf-8 -*-
"""
v25 实验: 前沿的 (lnN, t, lnS) 3D 表面 + QR90 拟合平面
把开源前沿散点画成 3D 视图: 两个驱动 (规模 lnN、时间 t) -> 能力 lnS,
叠加 0.9 分位数回归平面, 标注 2025 前沿点与 2026/2027 预测点.
输出: experiments/v25_p4_3d_surface.png
"""
import os, sys
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


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb["year"] = lb["date"].dt.year
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[lic & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0)].copy()
    dfm = dfm[dfm["year"] >= 2024]
    lnS = np.log(dfm["Average ⬆️"].to_numpy(dtype=float))
    lnN = np.log(dfm["#Params (B)"].to_numpy(dtype=float))
    t = (dfm["year"].to_numpy(dtype=float) - 2022.0)

    X = np.column_stack([np.ones(len(dfm)), lnN, t])
    n, m = X.shape
    cvec = np.concatenate([np.zeros(m), 0.9 * np.ones(n), 0.1 * np.ones(n)])
    Aeq = np.hstack([X, np.eye(n), -np.eye(n)])
    r = linprog(cvec, A_eq=Aeq, b_eq=lnS,
                bounds=[(None, None)] * m + [(0, None)] * (2 * n), method="highs")
    b0, bN, bT = r.x[:3]
    print(f"QR90: lnS = {b0:.3f} + {bN:.3f} lnN + {bT:.3f} t  (n={n})")

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(lnN, t, lnS, s=6, alpha=0.35, color="#2563EB", label="开源前沿样本")
    # 拟合平面
    nn = np.linspace(lnN.min(), lnN.max(), 30)
    tt = np.linspace(t.min(), 4.0, 30)
    NN, TT = np.meshgrid(nn, tt)
    SS = b0 + bN * NN + bT * TT
    ax.plot_surface(NN, TT, SS, alpha=0.25, color="#C2410C")
    # 2025 前沿点与预测点
    gN = 1.251125395176952
    lnN25 = dfm[dfm["year"] == 2025]["#Params (B)"].to_numpy(dtype=float)
    lnN25 = np.log(np.quantile(lnN25, 0.9))
    s25 = b0 + bN * lnN25 + bT * (3.0)
    s26 = b0 + bN * (lnN25 + gN) + bT * 4.0
    s27 = b0 + bN * (lnN25 + 2 * gN) + bT * 5.0
    ax.scatter([lnN25], [3.0], [s25], s=90, marker="*", color="#16A34A", label=f"2025 前沿 (S={np.exp(s25):.0f})")
    ax.scatter([lnN25 + gN], [4.0], [s26], s=90, marker="^", color="#DC2626", label=f"2026 预测 (S={np.exp(s26):.0f})")
    ax.scatter([lnN25 + 2 * gN], [5.0], [s27], s=90, marker="^", color="#DC2626", label=f"2027 预测 (S={np.exp(s27):.0f})")
    ax.set_xlabel("lnN (参数量)"); ax.set_ylabel("t (年, 2022=0)"); ax.set_zlabel("lnS (能力)")
    ax.set_title("v25: 前沿表面与 0.9 分位数回归平面")
    ax.view_init(elev=18, azim=-58)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v25_p4_3d_surface.png"), dpi=200)
    plt.close(fig)
    print("done v25")


if __name__ == "__main__":
    main()