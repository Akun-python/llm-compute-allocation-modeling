# -*- coding: utf-8 -*-
"""
v41 实验: 弹性结论对参考点的稳健性
在 (N0,D0,Q0) 网格上 (N0 0.7-1.3 x D0 200-400 x Q0 0.5-0.7, 共 175 点)
用与主链路相同的有限差分口径重算 eps_N/eps_D/eps_Q:
1) 质量弹性是否在全部参考点上保持最高 (|eps_Q| > |eps_N|, > |eps_D|)?
2) 比值 |eps_Q/eps_N| 的最小/中位/最大 (弹性排序的量化区间).
输出: experiments/v41_p2_eps_ref_grid.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import BASE, RES

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


def main():
    p2 = json.load(open(os.path.join(RES, "p2_scaling_results.json"), encoding="utf-8"))
    prm = p2["generalized"]["forms"]["interaction_N"]["params"]
    p = [prm["E"], prm["A"], prm["a"], prm["B"], prm["b"], prm["C"], prm["g"], prm.get("h", 0.1627)]

    def L(N, D, Q):
        E, A, a, B_, b, C, gg, h = p
        return E + A * N ** (-a) + B_ * D ** (-b) + C * (1 - Q) ** gg * N ** (-h)

    hh = 1e-4
    rows = []
    for N0 in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]:
        for D0 in [200, 250, 300, 350, 400]:
            for Q0 in [0.5, 0.55, 0.6, 0.65, 0.7]:
                L0 = L(N0, D0, Q0)
                eN = (L(N0 * (1 + hh), D0, Q0) - L0) / (hh * L0)
                eD = (L(N0, D0 * (1 + hh), Q0) - L0) / (hh * L0)
                eQ = (L(N0, D0, Q0 + hh) - L0) / (hh * L0)
                rows.append({"N0": N0, "D0": D0, "Q0": Q0,
                             "eps_N": float(eN), "eps_D": float(eD), "eps_Q": float(eQ),
                             "r_QN": float(abs(eQ) / abs(eN)), "r_QD": float(abs(eQ) / abs(eD))})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v41_p2_eps_ref_grid.csv"), index=False, encoding="utf-8-sig")

    rQN = rdf["r_QN"]; rQD = rdf["r_QD"]
    print(f"网格点数: {len(rdf)}")
    print(f"|eps_Q|>|eps_N| 占比: {(rdf['eps_Q'].abs() > rdf['eps_N'].abs()).mean():.3f}")
    print(f"|eps_Q|>|eps_D| 占比: {(rdf['eps_Q'].abs() > rdf['eps_D'].abs()).mean():.3f}")
    print(f"比值 |eQ/eN|: min {rQN.min():.2f} / 中位 {rQN.median():.2f} / max {rQN.max():.2f}")
    print(f"比值 |eQ/eD|: min {rQD.min():.2f} / 中位 {rQD.median():.2f} / max {rQD.max():.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    ax = axes[0]
    ax.violinplot([rdf["eps_N"], rdf["eps_D"], rdf["eps_Q"]], showmedians=True)
    ax.set_xticks([1, 2, 3]); ax.set_xticklabels(["$\\varepsilon_N$", "$\\varepsilon_D$", "$\\varepsilon_Q$"])
    ax.set_ylabel("弹性"); ax.set_title("175 参考点上的弹性分布")
    ax.axhline(0, color="#88ada6", lw=0.8)
    ax = axes[1]
    ax.hist(rQN, bins=20, color="#177cb0", alpha=0.75, label="$|\\varepsilon_Q/\\varepsilon_N|$")
    ax.hist(rQD, bins=20, color="#3eede7", alpha=0.6, label="$|\\varepsilon_Q/\\varepsilon_D|$")
    ax.set_xlabel("比值"); ax.set_title("质量弹性相对优势分布")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v41_p2_eps_ref_grid.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v41_p2_eps_ref_grid.json"), "w", encoding="utf-8") as f:
        json.dump({"n": len(rdf),
                   "q_gt_N": float((rdf["eps_Q"].abs() > rdf["eps_N"].abs()).mean()),
                   "q_gt_D": float((rdf["eps_Q"].abs() > rdf["eps_D"].abs()).mean()),
                   "rQN": [float(rQN.min()), float(rQN.median()), float(rQN.max())],
                   "rQD": [float(rQD.min()), float(rQD.median()), float(rQD.max())]},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v41")


if __name__ == "__main__":
    main()