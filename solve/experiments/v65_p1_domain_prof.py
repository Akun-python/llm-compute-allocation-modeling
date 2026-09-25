# -*- coding: utf-8 -*-
"""
v65 实验: 域级质量画像的相似性结构
90k 样本逐文档 TOPSIS 前端的 22 维标准化指标:
1) 每域画像 = 域内指标均值向量 (7 x 22);
2) 域画像相关矩阵 + Ward 层次聚类 (树状图);
3) 结论: book 画像是否独树一帜, 低质域是否聚簇, arxiv 的位置.
输出: experiments/v65_p1_domain_prof.png/.json/.csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax, ALL_IND)
from common import A, BASE
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform

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
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"), limit=60000)
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"), limit=15000)
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"), limit=15000)
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    dom = df["_source_domain"].fillna("none").to_numpy()
    X = winsorize_minmax(df[ALL_IND].to_numpy(dtype=float).copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)

    doms = sorted(np.unique(dom))
    prof = np.stack([X[dom == d].mean(0) for d in doms])
    Cm = np.corrcoef(prof)
    rdf = pd.DataFrame(Cm, index=doms, columns=doms).round(3)
    rdf.to_csv(os.path.join(EX, "v65_p1_domain_prof.csv"), encoding="utf-8-sig")
    print("画像相关矩阵:\n", rdf.to_string())
    Dm = (1 - Cm + (1 - Cm).T) / 2
    np.fill_diagonal(Dm, 0.0)
    D = squareform(Dm)
    Z = linkage(D, method="ward")
    order = dendrogram(Z, labels=doms, no_plot=True)["leaves"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1, 1.6]})
    dendrogram(Z, labels=doms, ax=axes[0], orientation="left", leaf_font_size=9)
    axes[0].set_title("v65: 域画像 Ward 层次聚类")
    im = axes[1].imshow(Cm[np.ix_(order, order)], cmap="cyan_div", vmin=-1, vmax=1)
    axes[1].set_xticks(range(len(doms))); axes[1].set_xticklabels([doms[i] for i in order], rotation=45, fontsize=8)
    axes[1].set_yticks(range(len(doms))); axes[1].set_yticklabels([doms[i] for i in order], fontsize=8)
    axes[1].set_title("域画像相关矩阵")
    fig.colorbar(im, ax=axes[1])
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v65_p1_domain_prof.png"), dpi=200)
    plt.close(fig)

    # 关键数字: book 与各域的最小/最大画像相关
    bd = {d: float(Cm[doms.index("book"), i]) for i, d in enumerate(doms) if d != "book"}
    top = max(bd, key=bd.get)
    print(f"\nbook 画像相关: 最高 {top} {bd[top]:.2f} | 最低 {min(bd, key=bd.get)} {min(bd.values()):.2f}")
    with open(os.path.join(EX, "v65_p1_domain_prof.json"), "w", encoding="utf-8") as f:
        json.dump({"corr": Cm.round(3).tolist(), "domains": doms, "book_corr": bd},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v65")


if __name__ == "__main__":
    main()