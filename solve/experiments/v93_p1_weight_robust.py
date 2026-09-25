# -*- coding: utf-8 -*-
"""
v93 实验: P1 质量评分链的组合权重扰动鲁棒性
在官方全量口径 (A1 51230 + arxiv_ext 17523 + github_ext 203752 = 272505)
上, 对熵-CRITIC 组合权重 w = 0.5 w_ent + 0.5 w_cri 施加对数扰动
w_jit = w * exp(sigma * eps) (eps~N(0,1)), 考察七域质量分域序的稳定性:
  1) 每个 sigma 档做 200 次重抽 -> 域序与基线 Spearman 分布 / book 居首
     概率 / stackexchange 垫底概率;
  2) sigma 扫描 {0.05, 0.1, 0.2, 0.3, 0.5} 的鲁棒性曲线;
  3) 基线域序与官方 p1_domain_quality.csv 交叉核对 (域序一致即锚定)。
冲突权重固定为基线值 (只扰动指标权重, 隔离效应)。
输出: experiments/v93_p1_weight_robust.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax,
                        entropy_weight, critic_weight, family_scores, ALL_IND,
                        DIRECTION)
from common import A, BASE
from scipy.stats import spearmanr
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

rng = np.random.default_rng(42)


def main():
    # ---- 装载 (与 v89 相同的官方全量口径) ----
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"))
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"))
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"))
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    dom = df["_source_domain"].fillna("none").to_numpy()
    doms = [d for d in np.unique(dom) if np.sum(dom == d) >= 50]
    Xraw = df[ALL_IND].to_numpy(dtype=float)
    for j, k in enumerate(ALL_IND):
        if not DIRECTION[k]:
            Xraw[:, j] = -Xraw[:, j]
    X = winsorize_minmax(Xraw)
    we, _e = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, dtype=float) + 0.5 * np.asarray(wc, dtype=float)
    qc, qf = family_scores(X)
    conf_fam = np.abs(qc - qf)
    cw = 1.0 / (conf_fam + 0.05)          # 官方域聚合权重 (固定)

    def order(Q):
        ddf = pd.DataFrame({"Q": Q, "d": dom, "c": cw})
        rank = pd.Series(dtype=float)
        means = {}
        for d in doms:
            g = ddf[ddf.d == d]
            m = np.isfinite(g.Q.to_numpy()) & np.isfinite(g.c.to_numpy())
            means[d] = float(np.average(g.Q.to_numpy()[m], weights=g.c.to_numpy()[m]))
        return pd.Series(means).rank(ascending=False)

    base_order = order(np.nansum(X * w, axis=1))
    print("基线七域序 (1=最优):", dict(base_order.round(1)))

    # 官方 csv 锚定: 域序要求与官方 Q_weighted 一致
    off = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "results", "p1_domain_quality.csv"))
    offi = off.set_index("domain")
    ov = {d: float(offi.loc[d, "Q_weighted"]) for d in doms if d in offi.index}
    base_means = {}
    ddf = pd.DataFrame({"Q": np.nansum(X * w, axis=1), "d": dom, "c": cw})
    for d in doms:
        g = ddf[ddf.d == d]
        m = np.isfinite(g.Q.to_numpy()) & np.isfinite(g.c.to_numpy())
        base_means[d] = float(np.average(g.Q.to_numpy()[m], weights=g.c.to_numpy()[m]))
    ref_order = pd.Series(ov).rank(ascending=False)
    common = [d for d in doms if d in ov]
    rho_anchor = float(spearmanr(
        [pd.Series(base_means).rank(ascending=False).loc[d] for d in common],
        [ref_order.loc[d] for d in common])[0])
    print(f"官方锚定 Spearman(我的域序, 官方csv全量Q_weighted域序) = {rho_anchor:.4f}")

    # ---- 扰动扫描 ----
    sigmas = [0.05, 0.1, 0.2, 0.3, 0.5]
    N = 200
    rows = []
    all_rank_draws = {}   # domain -> list of ranks at sigma=0.2
    for s in sigmas:
        rhos, bk1, st7 = [], [], []
        for _ in range(N):
            wj = w * np.exp(s * rng.standard_normal(len(w)))
            Qj = np.nansum(X * wj, axis=1)
            o = order(Qj)
            rhos.append(spearmanr(o, base_order)[0])
            bk1.append(int(o["book"] == 1))
            st7.append(int(o["stackexchange"] == max(o)))
            if s == 0.2:
                for d in doms:
                    all_rank_draws.setdefault(d, []).append(int(o[d]))
        r = pd.Series(rhos)
        rows.append({"sigma": s, "spearman_min": float(r.min()), "spearman_mean": float(r.mean()),
                     "p_book_rank1": float(np.mean(bk1)), "p_stack_last": float(np.mean(st7))})
        print(f"sigma={s}: Spearman min={r.min():.4f} mean={r.mean():.4f} | "
              f"P(book#1)={np.mean(bk1):.3f} P(stack#7)={np.mean(st7):.3f}")

    out = {"baseline_order": {d: int(base_order[d]) for d in doms},
           "anchor_spearman_vs_official": float(rho_anchor),
           "n_draws": N, "n_samples": int(len(df)),
           "rows": rows,
           "sigma020_rank_counts": {d: {int(k): int(v) for k, v in
                                      pd.Series(all_rank_draws[d]).value_counts().items()} for d in doms}}
    with open(os.path.join(EX, "v93_p1_weight_robust.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # ---- 图: sigma=0.2 的域级秩分布热力 (水色系) ----
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    dom_ordered = list(base_order.sort_values().index)
    rankmat = np.array([[int(o["book"] if False else 0)]])
    rows20 = [d["sigma"] for d in rows]
    bar_dat = pd.Series(rows20)
    import collections
    counts = {d: collections.Counter(all_rank_draws[d]) for d in dom_ordered}
    grid = np.zeros((len(dom_ordered), 7))
    for i, d in enumerate(dom_ordered):
        for rk, c in counts[d].items():
            grid[i, rk - 1] = c / N
    im = ax.imshow(grid, cmap="Blues", aspect="auto")
    ax.set_yticks(range(len(dom_ordered))); ax.set_yticklabels(dom_ordered)
    ax.set_xticks(range(7)); ax.set_xticklabels([f"#{i+1}" for i in range(7)])
    ax.set_xlabel("域级质量序位 (1=最优)"); ax.set_ylabel("域")
    ax.set_title("组合权重 ±20% 对数扰动 (200 次) 的七域秩分布")
    for i in range(len(dom_ordered)):
        for j in range(7):
            v = grid[i, j]
            if v > 0.02:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if v > 0.55 else "#1685a9")
    fig.colorbar(im, ax=ax, label="重抽占比")
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v93_p1_weight_robust.png"), dpi=200)
    plt.close(fig)
    print("\nDONE v93")


if __name__ == "__main__":
    main()