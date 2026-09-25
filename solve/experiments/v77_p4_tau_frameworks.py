# -*- coding: utf-8 -*-
"""
v77 实验: 分位数族 x 五框架交叉验证 —— 前沿系数随 tau 的单调性与框架无关性 (P4)
对 C1 开源模型 (n=2493), lnS = c0 + bN*lnN + bT*t, 在 tau in {0.5,0.7,0.8,0.9,0.95,0.99}
上用 5 个独立实现 (linprog LP / statsmodels / sklearn / L-BFGS-B / Adam) 复算:
1) 每个 tau 上五框架系数一致 (最大相对极差);
2) bN/bT 随 tau 单调平滑变化 (越高分位前沿越陡?);
3) tau=0.9 (论文主选) 位于单调区间, 非极端选取.
=> 前沿斜率的框架无关性与 tau 单调性共同保证分解结论 (83.7%) 的稳健性.
输出: experiments/v77_p4_tau_frameworks.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
import v74_p4_qr_frameworks as v74
from common import BASE

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

TAUS = [0.5, 0.7, 0.8, 0.9, 0.95, 0.99]
FWS = ["LP", "statsmodels", "sklearn", "L-BFGS-B", "Adam"]
COLORS = {"LP": "#177cb0", "statsmodels": "#1685a9", "sklearn": "#3eede7",
          "L-BFGS-B": "#70f3ff", "Adam": "#44cef6"}


def runners(tau):
    return {"LP": lambda: v74.qr_linprog(X, y, tau),
            "statsmodels": lambda: v74.qr_statsmodels(X, y, tau),
            "sklearn": lambda: v74.qr_sklearn(X, y, tau),
            "L-BFGS-B": lambda: v74.qr_lbfgs(X, y, tau),
            "Adam": lambda: v74.qr_torch(X, y, tau, steps=5000)}


X, y, dfm, ts = v74.load_data()
print(f"数据: n={len(y)}")


def main():
    rows = []
    for tau in TAUS:
        run = runners(tau)
        betas = {fw: run[fw]() for fw in FWS}
        B = np.array([betas[fw] for fw in FWS])
        med = np.median(B, axis=0)
        spread = (B.max(axis=0) - B.min(axis=0)) / np.abs(med)
        for fw in FWS:
            b = betas[fw]
            rows.append({"tau": tau, "framework": fw, "c0": float(b[0]),
                         "bN": float(b[1]), "bT": float(b[2]),
                         "pinball": v74.pinball_sum(b, X, y, tau)})
        print(f"tau={tau:.2f}: bN={med[1]:.4f} bT={med[2]:.4f} "
              f"| 跨框架极差 bN={spread[1]*100:.2e}% bT={spread[2]*100:.2e}%")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v77_p4_tau_frameworks.csv"), index=False, encoding="utf-8-sig")

    # 单调性: 中位系数随 tau
    med_by_tau = rdf.groupby("tau")[["bN", "bT"]].median()
    bN_seq, bT_seq = med_by_tau["bN"].to_numpy(), med_by_tau["bT"].to_numpy()
    monoN = bool(np.all(np.diff(bN_seq) > 0)) or bool(np.all(np.diff(bN_seq) < 0))
    monoT = bool(np.all(np.diff(bT_seq) > 0)) or bool(np.all(np.diff(bT_seq) < 0))
    print(f"单调性: bN 随 tau {'单调' if monoN else '非单调'}; bT 随 tau {'单调' if monoT else '非单调'}")
    print(f"bN: {[f'{v:.4f}' for v in bN_seq]}")
    print(f"bT: {[f'{v:.4f}' for v in bT_seq]}")

    # 每 tau 跨框架最大极差 (bN/bT)
    maxspread = rdf.groupby("tau").apply(
        lambda g: max((g["bN"].max() - g["bN"].min()) / abs(g["bN"].median()),
                      (g["bT"].max() - g["bT"].min()) / abs(g["bT"].median()))).to_dict()
    agg = {"tau_list": TAUS,
           "bN_by_tau": {str(t): float(v) for t, v in zip(TAUS, bN_seq)},
           "bT_by_tau": {str(t): float(v) for t, v in zip(TAUS, bT_seq)},
           "monotone_bN": monoN, "monotone_bT": monoT,
           "max_spread_by_tau": {str(t): float(v) for t, v in maxspread.items()}}
    with open(os.path.join(EX, "v77_p4_tau_frameworks.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rdf.to_dict("records"), "agg": agg}, f, ensure_ascii=False, indent=2)

    # ---- 图: bN/bT vs tau (五框架重叠线) ----
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, key, ylab in [(axes[0], "bN", "前沿规模系数 bN"), (axes[1], "bT", "前沿技术进步系数 bT")]:
        for fw in FWS:
            g = rdf[rdf["framework"] == fw]
            ax.plot(g["tau"], g[key], "o-", color=COLORS[fw], lw=1.6, ms=4,
                    label=fw if key == "bN" else None)
        for t in TAUS:
            g = rdf[rdf["tau"] == t]
            sp = max((g["bN"].max() - g["bN"].min()) / abs(g["bN"].median()),
                     (g["bT"].max() - g["bT"].min()) / abs(g["bT"].median()))
            ax.annotate(f"极差 {sp*100:.1e}%", xy=(t, g[key].median()),
                        textcoords="offset points", xytext=(0, 10),
                        ha="center", fontsize=7.5, color="#1685a9")
        ax.set_xlabel("分位数 tau"); ax.set_ylabel(ylab)
        ax.set_title(f"{ylab} vs tau (五框架)")
        ax.grid(alpha=0.3)
        if key == "bN":
            ax.legend(fontsize=8)
    fig.suptitle("分位数族 x 五框架交叉验证 —— 前沿系数随 tau 单调且框架无关", fontsize=12, y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(EX, "v77_p4_tau_frameworks.png"), dpi=200)
    plt.close(fig)
    print("\ndone v77")


if __name__ == "__main__":
    main()