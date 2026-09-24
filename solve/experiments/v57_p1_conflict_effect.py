# -*- coding: utf-8 -*-
"""
v57 实验: 冲突消解的有效性 (质量评分管道内部一致性)
用 p1_domain_quality.csv 的三阶段质量分:
1) 阶段秩相关: Q_weighted(加权均值) vs Q_topsis(消解后), 以及
   Q_weighted_plain vs Q_weighted (权重加入) 的域序变化;
2) 逐域冲突率 conflict_mean: 高冲突域(c4/commoncrawl) vs 低冲突域
   (github/wikipedia) 的消解位移幅度;
3) 结论: 冲突消解是微调(top/bottom 稳定) 而非颠覆, 高冲突域的
   消解位移更大.
输出: experiments/v57_p1_conflict_effect.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import BASE
from scipy.stats import spearmanr

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
    d = pd.read_csv(os.path.join("solve", "results", "p1_domain_quality.csv"))
    Qw = d["Q_weighted"].to_numpy()
    Qp = d["Q_weighted_plain"].to_numpy()
    Qt = d["Q_topsis"].to_numpy()
    cm = d["conflict_mean"].to_numpy()

    def rank(v):
        s = pd.Series(v).rank(method="min", ascending=False)
        return s.to_numpy()

    r_wt = rank(Qt) - rank(Qw)          # 消解造成的秩位移
    r_wp = rank(Qw) - rank(Qp)          # 权重造成的秩位移
    shift_resolve = np.abs(Qt - Qw)     # 分数位移
    shift_weight = np.abs(Qw - Qp)
    rho1 = spearmanr(Qw, Qt)[0]
    rho2 = spearmanr(Qp, Qw)[0]
    print(f"加权->消解 域序 Spearman = {rho1:.3f} (n=7)")
    print(f"平权->加权 域序 Spearman = {rho2:.3f}")
    rows = []
    for i in range(len(d)):
        rows.append({"domain": d.loc[i, "domain"], "Q_weighted": float(Qw[i]),
                     "Q_topsis": float(Qt[i]), "conflict_mean": float(cm[i]),
                     "rank_shift_resolve": int(r_wt[i]), "rank_shift_weight": int(r_wp[i]),
                     "score_shift_resolve": float(shift_resolve[i]),
                     "score_shift_weight": float(shift_weight[i])})
        print(f"{d.loc[i,'domain']:13s} 冲突率 {cm[i]:.2f} | 消解后秩位移 {int(r_wt[i]):+d} "
              f"| 分数位移 {shift_resolve[i]:.3f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v57_p1_conflict_effect.csv"), index=False, encoding="utf-8-sig")

    corr_cm = spearmanr(cm, shift_resolve)[0]
    print(f"\n冲突率 vs 消解位移 Spearman = {corr_cm:.3f}")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.scatter(cm, shift_resolve, color="#2563EB", s=60, alpha=0.85)
    for i in range(len(rdf)):
        ax.annotate(rdf.loc[i, "domain"], (cm[i], shift_resolve[i]),
                    textcoords="offset points", xytext=(5, 4), fontsize=8)
    ax.set_xlabel("域内冲突率 (conflict_mean)")
    ax.set_ylabel("消解造成的分数位移 |ΔQ|")
    ax.set_title(f"v57: 冲突消解的有效性 (冲突率-位移相关 {corr_cm:.3f})")
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v57_p1_conflict_effect.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v57_p1_conflict_effect.json"), "w", encoding="utf-8") as f:
        json.dump({"rho_weight_resolve": float(rho1), "rho_plain_weight": float(rho2),
                   "rho_conflict_shift": float(corr_cm), "rows": rows},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v57")


if __name__ == "__main__":
    main()