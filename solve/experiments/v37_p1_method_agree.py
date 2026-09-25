# -*- coding: utf-8 -*-
"""
v37 实验: 综合评分方法的域序一致性 (Kendall W / 两两 Spearman)
在抽样+扩展数据上, 用 6 种评分方法 (TOPSIS / SAW / GRA / RSR /
熵-CRITIC(0.5:0.5) / CRITIC-only) 各自得到七域域级质量分排序:
1) Kendall 协同系数 W: 6 方法是否一致同意"book 最优"类排序?
2) 两两 Spearman: 方法间成对一致性.
结论: 域级质量排序方法不变 (W 接近 1), 为评分方法选择提供统计依据.
输出: experiments/v37_p1_method_agree.csv/.json/.png
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


def gra(X, ref):
    """灰色关联度: 参考序列为各列最优(越大越好)"""
    d = np.abs(X - ref)
    dmin, dmax = d.min(), d.max()
    rho = (dmin + 0.5 * dmax) / (d + 0.5 * dmax)
    return rho.mean(axis=1)


def saw(X, w):
    return X @ w


def rsr(X):
    """秩和比: 各指标内 rank 求和后归一"""
    R = np.zeros_like(X)
    for j in range(X.shape[1]):
        R[:, j] = X[:, j].argsort().argsort() + 1
    return R.sum(axis=1) / (X.shape[1] * X.shape[0])


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
    wE = np.asarray(we, float); wC = np.asarray(wc, float)

    scores = {"TOPSIS": topsis(X, w), "SAW": saw(X, w), "GRA": gra(X, X.max(axis=0)),
              "RSR": rsr(X), "熵-CRITIC": saw(X, w), "CRITIC-only": saw(X, wC)}
    doms = np.unique(dom)
    doms = [d for d in doms if np.sum(dom == d) >= 50]
    print("域:", doms)
    table = {}
    for name, s in scores.items():
        means = pd.Series(s, index=dom).groupby(level=0).mean()
        table[name] = [means[d] for d in doms]
    df2 = pd.DataFrame(table, index=doms)
    df2.to_csv(os.path.join(EX, "v37_p1_method_agree.csv"), encoding="utf-8-sig")

    # Kendall W
    ranks = df2.rank(axis=0, ascending=False)
    T = ranks.sum(axis=1)
    m, n = len(table), len(doms)
    S = np.sum((T - m * (n + 1) / 2) ** 2)
    W = 12 * S / (m ** 2 * n * (n ** 2 - 1))
    print(f"Kendall W = {W:.4f} (m={m}, n={n})")

    # 两两 Spearman (按域对齐)
    pairs = []
    names = list(table.keys())
    for i in range(m):
        for j in range(i + 1, m):
            rho = spearmanr(df2[names[i]], df2[names[j]]).statistic
            pairs.append({"a": names[i], "b": names[j], "spearman": float(rho)})
    pr = pd.DataFrame(pairs)
    pr.to_csv(os.path.join(EX, "v37_p1_method_pairwise.csv"), index=False, encoding="utf-8-sig")
    print("两两 Spearman 均值: %.3f | 最小: %.3f" % (pr["spearman"].mean(), pr["spearman"].min()))
    print("排序(各方法):")
    print(df2.rank(axis=0, ascending=False).astype(int).to_string())

    with open(os.path.join(EX, "v37_p1_method_agree.json"), "w", encoding="utf-8") as f:
        json.dump({"kendall_W": float(W), "pairwise": pr.to_dict("records"),
                   "ranks": df2.rank(axis=0, ascending=False).astype(int).to_dict()},
                  f, ensure_ascii=False, indent=2)

    fig, ax = plt.subplots(figsize=(8, 5))
    R = df2.rank(axis=0, ascending=False).astype(int)
    im = ax.imshow(R.T, cmap="cyan_seq_r", vmin=1, vmax=7)
    ax.set_xticks(range(len(doms))); ax.set_xticklabels(doms, rotation=25, ha="right")
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
    for i in range(len(names)):
        for j in range(len(doms)):
            ax.text(j, i, str(R.iloc[j, i]), ha="center", va="center", fontsize=9)
    ax.set_title(f"6 种评分方法的域序 (Kendall W={W:.3f})")
    fig.colorbar(im, ax=ax, label="秩 (1=最优)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v37_p1_method_agree.png"), dpi=200)
    plt.close(fig)
    print("\ndone v37")


if __name__ == "__main__":
    main()