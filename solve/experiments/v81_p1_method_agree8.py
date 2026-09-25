# -*- coding: utf-8 -*-
"""
v81 实验: 综合评分方法的域序一致性扩展 (Kendall W / 两两 Spearman)
在 v37 同一数据口径 (A1 51230 + A2/A3 各 15000 = 81230 样本) 上,
把方法族从 6 种扩展到 8 种: TOPSIS / SAW / GRA / RSR / 熵-CRITIC(0.5:0.5) /
CRITIC-only / PROMETHEE-II / VIKOR:
1) Kendall W: 8 方法是否一致同意"book 最优"类排序;
2) 两两 Spearman: 方法间成对一致性 (含新方法族);
3) 说明: SAW 与熵-CRITIC 使用同一组合权重 (0.5 熵 + 0.5 CRITIC), 域序重合,
   去重后 7 个独立方法; PROMETHEE-II 为 outranking 类, VIKOR 为折衷类.
输出: experiments/v81_p1_method_agree8.csv/.json/.png
"""
import os, json
import numpy as np
import pandas as pd
import sys
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


def promethee_ii(X, w):
    """PROMETHEE-II: 线性偏好函数 P(d)=d/d_max, 净流量 phi=phi+ - phi-"""
    d = X[:, None, :] - X[None, :, :]              # (n, n, m) 候选a优于b的分指标差
    wd = (d * w[None, None, :]).sum(axis=2)        # 加权差
    p = np.clip(wd, 0, None)                       # 偏好强度 (正部分)
    phi_plus = p.sum(axis=1) / (X.shape[0] - 1)
    phi_minus = p.sum(axis=0) / (X.shape[0] - 1)
    return phi_plus - phi_minus


def vikor(X, w, v=0.5):
    """VIKOR: 折衷解, Q = v*Snorm + (1-v)*Rnorm, 越小越好"""
    fstar = X.max(axis=0); fminus = X.min(axis=0)
    span = np.where(fstar - fminus > 1e-12, fstar - fminus, 1e-12)
    dnorm = (fstar[None, :] - X) / span            # (n, m) 越小越好(归一化距离)
    S = (dnorm * w).sum(axis=1)
    R = (dnorm * w).max(axis=1)
    Sstar, Sminus = S.min(), S.max()
    Rstar, Rminus = R.min(), R.max()
    Sn = (S - Sstar) / max(Sminus - Sstar, 1e-12)
    Rn = (R - Rstar) / max(Rminus - Rstar, 1e-12)
    Q = v * Sn + (1 - v) * Rn
    return Q, S, R


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
    wC = np.asarray(wc, float)

    # PROMETHEE-II / VIKOR 为"备选方案"类方法 (outranking/折衷), 直接在
    # 7 域 x 22 指标的域均矩阵上计算 (备选方案 = 7 个域), 与加权聚合类
    # 方法(样本级评分后取域均值)口径互补.
    doms0 = [d for d in np.unique(dom) if np.sum(dom == d) >= 50]
    Xd = np.vstack([np.nanmean(X[dom == d], axis=0) for d in doms0])
    phi = promethee_ii(Xd, w)
    Qv, _Sv, _Rv = vikor(Xd, w)

    scores = {"TOPSIS": topsis(X, w), "SAW": saw(X, w), "GRA": gra(X, X.max(axis=0)),
              "RSR": rsr(X), "熵-CRITIC": saw(X, w), "CRITIC-only": saw(X, wC),
              "PROMETHEE-II": pd.Series(phi, index=doms0), "VIKOR": pd.Series(-Qv, index=doms0)}
    doms = doms0
    print("域:", doms, "| n:", int(len(df)))
    table = {}
    for name, s in scores.items():
        if isinstance(s, pd.Series) and list(s.index) == doms:
            means = s
        else:
            means = pd.Series(s, index=dom).groupby(level=0).mean()
        table[name] = [means[d] for d in doms]
    df2 = pd.DataFrame(table, index=doms)
    df2.to_csv(os.path.join(EX, "v81_p1_method_agree8.csv"), encoding="utf-8-sig")

    ranks = df2.rank(axis=0, ascending=False)
    m, n = len(table), len(doms)
    T = ranks.sum(axis=1)
    S = np.sum((T - m * (n + 1) / 2) ** 2)
    W = 12 * S / (m ** 2 * n * (n ** 2 - 1))

    names = list(table.keys())
    pairs = []
    for i in range(m):
        for j in range(i + 1, m):
            rho = spearmanr(df2[names[i]], df2[names[j]]).statistic
            pairs.append({"a": names[i], "b": names[j], "spearman": float(rho)})
    pr = pd.DataFrame(pairs)
    pr.to_csv(os.path.join(EX, "v81_p1_method_pairwise8.csv"), index=False, encoding="utf-8-sig")
    print(f"Kendall W (8 方法) = {W:.4f}")
    print(f"两两 Spearman 均值 {pr['spearman'].mean():.3f} | 最小 {pr['spearman'].min():.3f}")
    print("各方法域序 (1=最优):")
    print(ranks.astype(int).to_string())

    # 加权/贴近度类子集 (TOPSIS/SAW/熵-CRITIC/PROMETHEE-II/VIKOR) 一致性
    wset = ["TOPSIS", "SAW", "熵-CRITIC", "PROMETHEE-II", "VIKOR"]
    wpairs = pr[pr["a"].isin(wset) & pr["b"].isin(wset)]
    print(f"加权/贴近度 5 方法两两 Spearman 均值: {wpairs['spearman'].mean():.3f} | 最小: {wpairs['spearman'].min():.3f}")

    with open(os.path.join(EX, "v81_p1_method_agree8.json"), "w", encoding="utf-8") as f:
        json.dump({"n_samples": int(len(df)), "kendall_W_8": float(W),
                   "pairwise": pr.to_dict("records"),
                   "ranks": ranks.astype(int).to_dict(),
                   "weighted5_mean_spearman": float(wpairs["spearman"].mean()),
                   "weighted5_min_spearman": float(wpairs["spearman"].min())},
                  f, ensure_ascii=False, indent=2)

    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    R = ranks.astype(int)
    im = ax.imshow(R.T, cmap="cyan_seq_r", vmin=1, vmax=n)
    ax.set_xticks(range(len(doms))); ax.set_xticklabels(doms, rotation=25, ha="right")
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
    for i in range(len(names)):
        for j in range(len(doms)):
            ax.text(j, i, str(R.iloc[j, i]), ha="center", va="center", fontsize=8.5)
    ax.set_title(f"8 种评分方法的域序 (Kendall W={W:.3f})")
    fig.colorbar(im, ax=ax, label="秩 (1=最优)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v81_p1_method_agree8.png"), dpi=200)
    plt.close(fig)
    print("\ndone v81")


if __name__ == "__main__":
    main()
