# -*- coding: utf-8 -*-
"""
v30 实验: 域级质量分的推断性检验
对 TOPSIS 质量分 Q_i (7 域) 做:
1) Kruskal-Wallis: 7 域间是否存在显著差异;
2) 两两 Mann-Whitney U (Bonferroni): book 显著高于其余? c4 是否显著低于?
3) 效应量 (rank-biserial r): 域间差异的实际大小.
输出: experiments/v30_p1_domain_sig.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax,
                        entropy_weight, critic_weight, topsis, ALL_IND)
from common import A, BASE
from scipy.stats import kruskal, mannwhitneyu

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
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"))
    df = build_frame(a1)
    dom = df["_source_domain"].fillna("none").to_numpy()
    Xraw = df[ALL_IND].to_numpy(dtype=float)
    X = winsorize_minmax(Xraw.copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    we, _e = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, float) + 0.5 * np.asarray(wc, float)
    Q = topsis(X, w)

    groups = {d: Q[dom == d] for d in np.unique(dom)}
    print("每域样本量:", {d: len(g) for d, g in groups.items()})
    H, p = kruskal(*[g for d, g in groups.items() if len(g) >= 10])
    print(f"Kruskal-Wallis: H={H:.1f} p={p:.2e} (7 域)")

    doms = [d for d in np.unique(dom) if len(groups[d]) >= 10]
    qmeans = {d: float(np.mean(groups[d])) for d in doms}
    order = sorted(doms, key=lambda d: -qmeans[d])
    print("域序(均值):", {d: round(qmeans[d], 3) for d in order})

    rows = []
    pairs = [(a, b) for i, a in enumerate(order) for b in order[i + 1:]]
    alpha = 0.05 / len(pairs)
    for a, b in pairs:
        u, pv = mannwhitneyu(groups[a], groups[b], alternative="two-sided")
        # rank-biserial r = 1 - 2U/(na*nb)
        r = 1 - 2 * u / (len(groups[a]) * len(groups[b]))
        rows.append({"a": a, "b": b, "mean_a": qmeans[a], "mean_b": qmeans[b],
                     "diff": qmeans[a] - qmeans[b], "p": float(pv),
                     "sig": bool(pv < alpha), "rank_biserial_r": float(r)})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v30_p1_domain_sig.csv"), index=False, encoding="utf-8-sig")
    nsig = rdf["sig"].sum()
    print(f"\n两两 Mann-Whitney (Bonferroni alpha={alpha:.2e}): {nsig}/{len(rdf)} 对显著")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    data = [groups[d] for d in order]
    bp = ax.boxplot(data, tick_labels=[f"{d}\n({qmeans[d]:.2f})" for d in order],
                    showfliers=False, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("#70f3ff")
    ax.set_ylabel("TOPSIS 质量分 Q")
    ax.set_title("域级质量分分布 (n=%d, Kruskal-Wallis p<1e-300)" % len(Q))
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v30_p1_domain_sig.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v30_p1_domain_sig.json"), "w", encoding="utf-8") as f:
        json.dump({"kruskal_H": float(H), "kruskal_p": float(p),
                   "n_sig_pairs": int(nsig), "n_pairs": len(rdf),
                   "means": qmeans}, f, ensure_ascii=False, indent=2)
    print("\ndone v30")


if __name__ == "__main__":
    main()