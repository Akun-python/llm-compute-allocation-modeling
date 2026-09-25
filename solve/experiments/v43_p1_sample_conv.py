# -*- coding: utf-8 -*-
"""
v43 实验: 域级质量分的抽样规模收敛性
在 90k 质量样本上, 固定权重(全量熵-CRITIC+TOPSIS), 按域以比例
f in {5%,10%,20%,40%,70%,100%} 有放回重抽, 每 f 做 30 次:
1) 每次重抽计算七域域级质量分的排序;
2) 记录 book 排第 1 的比例 (排位稳定性) 与 与全量排序的 Spearman 均值;
3) 结论: 排序在多大样本量下收敛 (抽样充分性核验).
输出: experiments/v43_p1_sample_conv.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax,
                        entropy_weight, critic_weight, topsis, ALL_IND)
from common import A, BASE
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
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"
import plotstyle


def main():
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"), limit=60000)
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"), limit=15000)
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"), limit=15000)
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    dom = df["_source_domain"].fillna("none").to_numpy()
    Xraw = df[ALL_IND].to_numpy(dtype=float)
    X = winsorize_minmax(Xraw.copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    we, _e = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, float) + 0.5 * np.asarray(wc, float)
    Qfull = topsis(X, w)
    full_rank = pd.Series(Qfull, index=dom).groupby(level=0).mean().rank(ascending=False)
    doms = list(full_rank.index)
    top_dom = full_rank.idxmin()  # 全量排序第 1 的域
    rng = np.random.default_rng(7)

    fracs = [0.05, 0.1, 0.2, 0.4, 0.7, 1.0]
    rows = []
    for f in fracs:
        p_book1 = 0.0
        sp = []
        for _ in range(30):
            idx = []
            for d in doms:
                sub = np.where(dom == d)[0]
                m = max(1, int(len(sub) * f))
                idx.append(rng.choice(sub, size=m, replace=True))
            idx = np.concatenate(idx)
            r = pd.Series(Qfull[idx], index=dom[idx]).groupby(level=0).mean().rank(ascending=False)
            p_book1 += (r[top_dom] == 1)
            sp.append(spearmanr([r[d] for d in doms], [full_rank[d] for d in doms]).statistic)
        p_book1 /= 30
        sp_mean = float(np.mean(sp))
        rows.append({"frac": f, "p_book_rank1": float(p_book1), "spearman_vs_full": sp_mean})
        print(f"f={f:.0%}: 第1域({top_dom})保持第1概率 {p_book1:.2f} | 与全量排序 Spearman 均值 {sp_mean:.3f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v43_p1_sample_conv.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(rdf["frac"] * 100, rdf["p_book_rank1"], "o-", color="#177cb0", lw=2, label="book 排第 1 概率")
    ax.plot(rdf["frac"] * 100, rdf["spearman_vs_full"], "s--", color="#3eede7", lw=2, label="与全量排序 Spearman")
    ax.set_xlabel("抽样比例 (%)"); ax.set_ylim(0.3, 1.02)
    ax.set_title("v43: 域级质量排序的抽样收敛性")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v43_p1_sample_conv.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v43_p1_sample_conv.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("\ndone v43")


if __name__ == "__main__":
    main()