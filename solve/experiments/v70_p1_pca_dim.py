# -*- coding: utf-8 -*-
"""
v70 实验: 22 维质量指标体系的有效维度 (PCA)
90k 样本 22 个标准化指标:
1) PCA 特征值: 累积方差 50/80/90% 所需主成分数 (有效维度);
2) 前 3 主成分的载荷: 内容族(C) vs 格式族(F) 在各 PC 的贡献;
3) 结论: 指标虽 22 个但有效维度~4-6, 冗余度高; 但两族在 PC1/PC2
   载荷互补 => 多指标体系仍必要 (信息多元).
输出: experiments/v70_p1_pca_dim.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax, ALL_IND, FAMILY_C)
from common import A, BASE

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
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"), limit=60000)
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"), limit=15000)
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"), limit=15000)
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    X = winsorize_minmax(df[ALL_IND].to_numpy(dtype=float).copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    Xc = (X - X.mean(0)) / (X.std(0) + 1e-9)
    cov = np.cov(Xc.T)
    eig, V = np.linalg.eigh(cov)
    order = np.argsort(eig)[::-1]
    eig, V = eig[order], V[:, order]
    cum = np.cumsum(eig) / eig.sum()
    def ndim(thr):
        return int(np.searchsorted(cum, thr) + 1)
    d50, d80, d90 = ndim(0.5), ndim(0.8), ndim(0.9)
    print(f"有效维度: 50%={d50} 80%={d80} 90%={d90} (共 {len(ALL_IND)} 指标)")
    print("前6主成分方差占比:", [f"{v:.1%}" for v in cum[:6]])

    # 载荷: 前3 PC, 按族聚合
    jc = [ALL_IND.index(k) for k in FAMILY_C]
    fam = np.array([0 if i in jc else 1 for i in range(len(ALL_IND))])
    load3 = np.abs(V[:, :3])
    lc = load3[fam == 0].mean(0)
    lf = load3[fam == 1].mean(0)
    for k in range(3):
        print(f"PC{k+1}: 内容族平均|载荷| {lc[k]:.3f} vs 格式族 {lf[k]:.3f}")
    # 每族在主导PC的份额
    share_c_pc1 = float(load3[fam == 0, 0].sum() / load3[:, 0].sum())
    print(f"PC1 中内容族载荷份额 {share_c_pc1:.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1, 1.5]})
    axes[0].bar(range(len(eig)), cum, color="#2563EB", alpha=0.85)
    for thr, d in [(0.5, d50), (0.8, d80), (0.9, d90)]:
        axes[0].axhline(thr, color="#C2410C", lw=0.9, ls="--")
        axes[0].text(d - 0.4, thr + 0.02, f"{int(thr*100)}%: {d} 维", fontsize=8, color="#C2410C")
    axes[0].set_xlabel("主成分序"); axes[0].set_ylabel("累积方差占比")
    axes[0].set_title(f"v70: 有效维度 (80% = {d80} 维 / 22)")
    axes[0].grid(alpha=0.3, axis="y")
    axes[1].bar(np.arange(len(ALL_IND)) - 0.15, load3[:, 0], 0.3, label="PC1", color="#2563EB")
    axes[1].bar(np.arange(len(ALL_IND)) + 0.15, load3[:, 1], 0.3, label="PC2", color="#0EA5E9")
    axes[1].set_xticks(range(len(ALL_IND)))
    axes[1].set_xticklabels(ALL_IND, rotation=60, ha="right", fontsize=6)
    axes[1].set_ylabel("|载荷|"); axes[1].set_title("PC1/PC2 载荷 (内容族=前15)")
    axes[1].legend(fontsize=8); axes[1].grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v70_p1_pca_dim.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v70_p1_pca_dim.json"), "w", encoding="utf-8") as f:
        json.dump({"n_ind": len(ALL_IND), "dims": {"p50": d50, "p80": d80, "p90": d90},
                   "cum_var": cum[:6].tolist(), "share_c_pc1": share_c_pc1},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v70")


if __name__ == "__main__":
    main()