# -*- coding: utf-8 -*-
"""
v95 实验: 冲突消解 (k=6) 后八种评分方法的域序一致性
§5 核心声称: 加权/贴近度/折衷五方法域序高度一致 (两两 Spearman
min 0.93/mean 0.97, W=0.98 置换 p<0.001) -- 该结论基于消解前的
样本级分数。本实验回答: 若按主链路的对称截尾消解规则 (robust_resolve
k=6: 每样本按得分排序对称剔除 3 低+3 高指标后重归一化加权) 先消解,
再计算八方法, 域序一致性格局是否保持?
口径与 v81 完全一致: 81,230 样本 (A1 60k + arxiv 15k + github 15k),
熵-CRITIC 组合赋权; 样本级 6 方法 (TOPSIS/SAW/熵-CRITIC/CRITIC-only/
GRA/RSR) 在每样本 keep 子集上重算, 域级 2 方法 (PROMETHEE-II/VIKOR)
在 7x22 域均矩阵的对称裁剪版上重算 (备选方案=7 域, 与 v81 口径互补)。
输出: experiments/v95_p1_resolved_order.json/.csv/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax,
                        entropy_weight, critic_weight, topsis, ALL_IND,
                        DIRECTION)
from common import A, BASE
from scipy.stats import spearmanr, kendalltau
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

EX = os.path.join(os.path.dirname(__file__))
for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"

K = 6
K2 = K // 2


def keep_masks(X):
    """每样本 keep 掩码 (value-sort 对称剔除, 与 robust_resolve 相同)"""
    n, m = X.shape
    order = np.argsort(X, axis=1)          # 升序位置
    keep = np.ones_like(X, dtype=bool)
    rows = np.arange(n)[:, None]
    keep[rows, order[:, :K2]] = False
    keep[rows, order[:, m - K2:]] = False
    return keep


def resolved_scores(X, w, keep):
    """加权和类 (SAW/熵-CRITIC/CRITIC-only 共享): robust_resolve 语义"""
    n, m = X.shape
    Qr = np.empty(n)
    for i in range(n):
        kk = keep[i]
        ww = w[kk]
        Qr[i] = np.nansum(X[i, kk] * ww) / ww.sum()
    return Qr


def topsis_resolved(X, w, keep):
    """TOPSIS on keep 子集: 理想点=各列(keep 全局)最大值, 距离按 keep 加权"""
    n, m = X.shape
    ideal = X.max(axis=0)
    Q = np.empty(n)
    for i in range(n):
        kk = keep[i]
        d2 = ((X[i, kk] - ideal[kk]) ** 2 * w[kk] ** 2).sum()
        Q[i] = -np.sqrt(d2)                # 越小越远 -> 取负 (越高越好)
    return Q


def gra_resolved(X, keep):
    d = np.abs(X - X.max(axis=0)[None, :])
    dmin, dmax = d.min(), d.max()
    rho = (dmin + 0.5 * dmax) / (d + 0.5 * dmax)
    n = X.shape[0]
    out = np.empty(n)
    for i in range(n):
        out[i] = np.nanmean(rho[i, keep[i]])
    return out


def rsr_resolved(X, keep):
    n, m = X.shape
    R = np.zeros_like(X)
    for j in range(m):
        R[:, j] = X[:, j].argsort().argsort() + 1
    out = np.empty(n)
    for i in range(n):
        out[i] = R[i, keep[i]].sum() / keep[i].sum()
    return out


def promethee_ii(X, w):
    d = X[:, None, :] - X[None, :, :]
    wd = (d * w[None, None, :]).sum(axis=2)
    p = np.clip(wd, 0, None)
    n = X.shape[0]
    return p.sum(axis=1) / (n - 1) - p.sum(axis=0) / (n - 1)


def vikor(X, w, v=0.5):
    fstar = X.max(axis=0); fminus = X.min(axis=0)
    span = np.where(fstar - fminus > 1e-12, fstar - fminus, 1e-12)
    dnorm = (fstar[None, :] - X) / span
    S = (dnorm * w).sum(axis=1)
    R = (dnorm * w).max(axis=1)
    Sn = (S - S.min()) / max(S.max() - S.min(), 1e-12)
    Rn = (R - R.min()) / max(R.max() - R.min(), 1e-12)
    return v * Sn + (1 - v) * Rn


def main():
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"), limit=60000)
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"), limit=15000)
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"), limit=15000)
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    dom = df["_source_domain"].fillna("none").to_numpy()
    doms = [d for d in np.unique(dom) if np.sum(dom == d) >= 50]
    Xraw = df[ALL_IND].to_numpy(dtype=float)
    for j, k in enumerate(ALL_IND):
        if not DIRECTION[k]:
            Xraw[:, j] = -Xraw[:, j]
    X = winsorize_minmax(Xraw.copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    we, _e = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, float) + 0.5 * np.asarray(wc, float)
    keep = keep_masks(X)

    # --- 样本级 6 方法 (消解后) ---
    scores = {
        "TOPSIS(消解后)": topsis_resolved(X, w, keep),
        "SAW(消解后)": resolved_scores(X, w, keep),
        "熵-CRITIC(消解后)": resolved_scores(X, w, keep),
        "CRITIC-only(消解后)": resolved_scores(X, wc, keep),
        "GRA(消解后)": gra_resolved(X, keep),
        "RSR(消解后)": rsr_resolved(X, keep),
    }
    # --- 域级 2 方法 (域均矩阵对称裁剪后) ---
    Xd = np.vstack([np.nanmean(X[dom == d], axis=0) for d in doms])
    kd = keep_masks(Xd)
    Xd_masked = Xd.copy()
    Xd_masked[~kd] = np.nan
    phi = promethee_ii(np.where(kd, Xd, 0.0), w)      # 裁剪列置 0 (不影响权重的列对比)
    Qv = vikor(np.where(kd, Xd, 0.0), w)
    scores["PROMETHEE-II(消解后)"] = pd.Series(phi, index=doms)
    scores["VIKOR(消解后)"] = pd.Series(-Qv, index=doms)

    table = {}
    for name, s in scores.items():
        if isinstance(s, pd.Series):
            means = s
        else:
            means = pd.Series(s, index=dom).groupby(level=0).mean()
        table[name] = [float(means[d]) for d in doms]
    df2 = pd.DataFrame(table, index=doms)
    df2.to_csv(os.path.join(EX, "v95_p1_resolved_order.csv"), encoding="utf-8-sig")

    ranks = df2.rank(axis=0, ascending=False)
    n_methods, n_domains = len(table), len(doms)
    W = 12.0 * ((ranks.sum(axis=1) - (n_methods * (n_domains + 1) / 2)) ** 2).sum() / \
        (n_methods ** 2 * n_domains * (n_domains ** 2 - 1))
    cors = np.array([[spearmanr(ranks[a], ranks[b])[0] for b in ranks.columns]
                     for a in ranks.columns])
    cors_i = cors[np.tril_indices(n_methods, -1)]
    out = {"W_resolved": float(W), "n_methods": n_methods, "n_domains": n_domains,
           "pairwise_spearman_min": float(cors_i.min()), "pairwise_spearman_mean": float(cors_i.mean()),
           "orders": {d: {m: int(ranks.loc[d, m]) for m in ranks.columns} for d in doms}}
    with open(os.path.join(EX, "v95_p1_resolved_order.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"消解后八方法: Kendall W={W:.3f}, 两两 Spearman min={cors_i.min():.3f} mean={cors_i.mean():.3f}")
    print(df2.rank(axis=0, ascending=False).to_string())

    # --- 图: 秩矩阵 ---
    fig, ax = plt.subplots(figsize=(9, 3.6))
    grid = ranks.T.astype(float)
    im = ax.imshow(grid, cmap="Blues", aspect="auto")
    ax.set_xticks(range(n_domains)); ax.set_xticklabels(domains := list(doms), rotation=30, ha="right")
    ax.set_yticks(range(n_methods)); ax.set_yticklabels(list(ranks.columns), fontsize=7)
    for i in range(n_methods):
        for j in range(n_domains):
            ax.text(j, i, int(grid.iloc[i, j]), ha="center", va="center", fontsize=7)
    ax.set_title(f"冲突消解 (k=6) 后八方法七域秩 (W={W:.2f})")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v95_p1_resolved_order.png"), dpi=200)
    plt.close(fig)
    print("\nDONE v95")


if __name__ == "__main__":
    main()