# -*- coding: utf-8 -*-
"""
v85 实验: 八方法 Kendall W 的置换检验 (P1 评分方法一致性显著性)
v81 报告八方法 Kendall W=0.6908 但未给显著性。本实验:
  1) 在同一数据口径 (A1 51230 + A2/A3 各 15000 = 81230) 上复算观测 W8;
  2) 置换检验: 随机置换样本的域标签 (每置换要求各域>=50 样本), 重算八方法
     域均矩阵 -> 域序 -> Kendall W, B=2000 次, 得到零分布;
  3) 报告置换 p 值 + 零分布 95% 分位, 判定"八方法域序一致性"是否显著
     (同样对加权/贴近度/折衷 5 方法子集做 W5 置换检验);
  4) 输出零分布直方图: 观测 W 是否远在零分布右尾。
输出: experiments/v85_p1_w_permutation.csv/.json/.png
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
    d = np.abs(X - ref)
    dmin, dmax = d.min(), d.max()
    rho = (dmin + 0.5 * dmax) / (d + 0.5 * dmax)
    return rho.mean(axis=1)


def saw(X, w):
    return X @ w


def rsr(X):
    R = np.zeros_like(X)
    for j in range(X.shape[1]):
        R[:, j] = X[:, j].argsort().argsort() + 1
    return R.sum(axis=1) / (X.shape[1] * X.shape[0])


def promethee_ii(X, w):
    d = X[:, None, :] - X[None, :, :]
    wd = (d * w[None, None, :]).sum(axis=2)
    phi = np.clip(wd, 0, None).sum(axis=1) / (X.shape[0] - 1) \
        - np.clip(wd, 0, None).sum(axis=0) / (X.shape[0] - 1)
    return phi


def vikor(X, w, v=0.5):
    fstar = X.max(axis=0); fminus = X.min(axis=0)
    span = np.where(fstar - fminus > 1e-12, fstar - fminus, 1e-12)
    dnorm = (fstar[None, :] - X) / span
    S = (dnorm * w).sum(axis=1)
    R = (dnorm * w).max(axis=1)
    Q = v * (S - S.min()) / max(S.max() - S.min(), 1e-12) \
        + (1 - v) * (R - R.min()) / max(R.max() - R.min(), 1e-12)
    return -Q


def kendall_w(rank_frame):
    """rank_frame: DataFrame(域 x 方法), 值=该方法下该域的秩(1最优)
    m=评分方法数(列), n=域数(行): W=12S/(m^2 n (n^2-1))"""
    m, n = rank_frame.shape[1], rank_frame.shape[0]
    T = rank_frame.sum(axis=1)
    S = np.sum((T - m * (n + 1) / 2) ** 2)
    return 12 * S / (m ** 2 * n * (n ** 2 - 1))


def domain_rank_frame(scores, dom, doms):
    """对每方法: 域均 -> 秩(1=最优); 返回 DataFrame"""
    tab = {}
    for name, s in scores.items():
        df = pd.DataFrame({"s": np.asarray(s), "d": dom})
        means = df.groupby("d")["s"].mean()
        tab[name] = [means[d] for d in doms]
    return pd.DataFrame(tab, index=doms).rank(axis=0, ascending=False)


def main():
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"), limit=60000)
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"), limit=15000)
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"), limit=15000)
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    dom0 = df["_source_domain"].fillna("none").to_numpy()
    doms = [d for d in np.unique(dom0) if np.sum(dom0 == d) >= 50]
    Xraw = df[ALL_IND].to_numpy(dtype=float)
    X = winsorize_minmax(Xraw.copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    we, _e = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, float) + 0.5 * np.asarray(wc, float)
    wC = np.asarray(wc, float)

    Xd = np.vstack([np.nanmean(X[dom0 == d], axis=0) for d in doms])
    scores = {"TOPSIS": topsis(X, w), "SAW": saw(X, w), "GRA": gra(X, X.max(axis=0)),
              "RSR": rsr(X), "entropy-CRITIC": saw(X, w), "CRITIC-only": saw(X, wC),
              "PROMETHEE-II": pd.Series(promethee_ii(Xd, w), index=doms),
              "VIKOR": pd.Series(vikor(Xd, w), index=doms)}
    # 统一: 样本级方法 -> 域均; 域级方法 -> Series 直接用
    dom = dom0.copy()
    rfr = None
    def ranks_for(domlab):
        tab = {}
        for name, s in scores.items():
            if isinstance(s, pd.Series) and list(s.index) == doms:
                tab[name] = [s[d] for d in doms]
            else:
                dfm = pd.DataFrame({"s": np.asarray(s), "d": domlab})
                means = dfm.groupby("d")["s"].mean()
                tab[name] = [means[d] for d in doms]
        return pd.DataFrame(tab, index=doms).rank(axis=0, ascending=False)

    rf = ranks_for(dom)
    W8_obs = float(kendall_w(rf))
    W5_cols = ["TOPSIS", "SAW", "entropy-CRITIC", "PROMETHEE-II", "VIKOR"]
    W5_obs = float(kendall_w(rf[W5_cols]))
    print(f"n={len(df)} 观测: W8={W8_obs:.4f}  W5(加权/折衷)={W5_obs:.4f}")
    assert abs(W8_obs - 0.6908) < 1e-3, f"W8 与 v81 不一致: {W8_obs}"

    rng = np.random.default_rng(42)
    B = 2000
    null8, null5 = [], []
    while len(null8) < B:
        perm = rng.permutation(dom)
        # 过滤: 每置换域>=50
        if min(np.bincount(pd.factorize(perm)[0])) < 50:
            continue
        pk = {d: np.sum(perm == d) for d in doms}
        if min(pk.values()) < 50:
            continue
        rf1 = ranks_for(perm)
        null8.append(float(kendall_w(rf1)))
        null5.append(float(kendall_w(rf1[W5_cols])))
    null8 = np.array(null8); null5 = np.array(null5)
    p8 = float((null8 >= W8_obs).mean())
    p5 = float((null5 >= W5_obs).mean())
    print(f"置换 B={B}: 零分布 W8 均值 {null8.mean():.4f} "
          f"(95%分位 {np.percentile(null8,95):.4f}) -> p8={p8:.4f}")
    print(f"                零分布 W5 均值 {null5.mean():.4f} "
          f"(95%分位 {np.percentile(null5,95):.4f}) -> p5={p5:.4f}")

    json.dump({"n": int(len(df)), "W8_obs": W8_obs, "W5_obs": W5_obs,
               "B": B, "p8": p8, "p5": p5,
               "null8_mean": float(null8.mean()), "null8_p95": float(np.percentile(null8, 95)),
               "null5_mean": float(null5.mean()), "null5_p95": float(np.percentile(null5, 95))},
              open(os.path.join(EX, "v85_p1_w_permutation.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    pd.DataFrame({"null8": null8, "null5": null5}).to_csv(
        os.path.join(EX, "v85_p1_w_permutation_null.csv"), index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.3))
    for ax, null, Wobs, lab in [(axes[0], null8, W8_obs, "八方法 W"),
                                (axes[1], null5, W5_obs, "加权/折衷五方法 W")]:
        ax.hist(null, bins=30, color="#3eede7", alpha=0.75, edgecolor="white")
        ax.axvline(Wobs, color="#1685a9", lw=2)
        ax.text(Wobs, ax.get_ylim()[1] * 0.9, f"观测 {Wobs:.3f}", color="#1685a9", fontsize=9)
        ax.set_xlabel("置换零分布 Kendall W"); ax.set_title(lab)
        ax.grid(alpha=0.3, axis="y")
    fig.suptitle("八/五方法域序一致性的置换检验 (B=2000)", fontsize=12, y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(EX, "v85_p1_w_permutation.png"), dpi=200)
    plt.close(fig)
    print("done v85")


if __name__ == "__main__":
    main()