# -*- coding: utf-8 -*-
"""
v89 实验: P1 冲突消解规则的替代构造交叉验证
主链路 (p1_quality/v57): 冲突指数 = |Q_C - Q_F| (双族均值差),
消解 = 对称截尾 k=6 (每样本去 3 低+3 高指标后加权), 域序 Spearman=1.000.
本实验:
  1) 截尾参数扫描: k ∈ {2,4,6,8} -> 域序 Spearman(Q_weighted, Q_resolved(k))
     是否全部 =1.000 (消解规则对 k 稳健);
  2) 替代冲突指数 (总体不一致度 std 22 维) 重做高冲突识别: 0.9 分位
     阈值下高冲突子集的域序与全量是否一致 (book 居首/低质垫底保持);
  3) 替代冲突率 vs 消解位移 Spearman (v57 为 0.0, 检验构造无关性)。
同一数据口径 (A1 51230 + A2/A3 15000 = 81230, 熵-CRITIC 组合赋权)。
输出: experiments/v89_p1_resolve_robust.json/.png
"""
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax,
                        entropy_weight, critic_weight, family_scores, ALL_IND)
from common import A, BASE
from scipy.stats import spearmanr
import json
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


def robust_resolve(X, w, k):
    n, m = X.shape
    k = min(k, m - 2)
    k2 = k // 2
    Qr = np.empty(n)
    for i in range(n):
        x = X[i]
        order = np.argsort(x)
        keep = order[k2: m - k2]
        ww = w[keep]
        Qr[i] = np.nansum(x[keep] * ww) / ww.sum()
    return Qr


def wmean(vals, w):
    m = np.isfinite(vals) & np.isfinite(w)
    if m.sum() == 0:
        return np.nan
    return np.average(vals[m], weights=w[m])


def domain_order(Q, dom, doms, conflict=None):
    """域级聚合: 与 p1_domain_quality.csv 一致, 权重=1/(冲突+0.05)"""
    if conflict is None:
        # 无冲突信息时用平权 (仅内部比较用)
        df = pd.DataFrame({"Q": Q, "d": dom})
        return {d: float(df[df.d == d].Q.mean()) for d in doms}
    df = pd.DataFrame({"Q": Q, "d": dom, "c": conflict})
    out = {}
    for d in doms:
        g = df[df.d == d]
        out[d] = float(wmean(g.Q.to_numpy(), (1.0 / (g.c.to_numpy() + 0.05))))
    return out


def main():
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"), limit=60000)
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"), limit=15000)
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"), limit=15000)
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    dom = df["_source_domain"].fillna("none").to_numpy()
    doms = [d for d in np.unique(dom) if np.sum(dom == d) >= 50]
    X = winsorize_minmax(df[ALL_IND].to_numpy(dtype=float).copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    we, _ = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, float) + 0.5 * np.asarray(wc, float)

    Qw = X @ w
    qc, qf = family_scores(X)
    conflict_fam = np.abs(qc - qf)   # 官方冲突指数
    do_w = domain_order(Qw, dom, doms, conflict_fam)
    # 0) 官方口径复核: p1_domain_quality.csv 的 Q_weighted/Q_topsis 域序
    off = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "results", "p1_domain_quality.csv"))
    rho_off = float(spearmanr(off["Q_weighted"], off["Q_topsis"])[0])
    print(f"官方csv 复核: Spearman(Q_weighted, Q_topsis) = {rho_off}")
    # 1) 截尾 k 扫描
    ks = [2, 4, 6, 8]
    k_rows = []
    for k in ks:
        Qr = robust_resolve(X, w, k)
        do_r = domain_order(Qr, dom, doms, conflict_fam)
        rho = float(spearmanr([do_w[d] for d in doms], [do_r[d] for d in doms])[0])
        k_rows.append({"k": k, "rho_weight_resolve": rho,
                       "order_resolve": [d for d in sorted(doms, key=lambda x: -do_r[x])]})
        print(f"k={k}: 域序 Spearman(加权, 消解) = {rho}")
    k_rho = [r["rho_weight_resolve"] for r in k_rows]
    all_one = all(abs(v - 1.0) < 1e-9 for v in k_rho)
    print(f"全部 k 下 rho=1.000: {all_one}")

    # 2) 替代冲突指数: 总体不一致度 std(22 维)
    conflict_std = X.std(axis=1)
    thresh = float(np.quantile(conflict_std, 0.9))
    hi = conflict_std >= thresh
    lo = conflict_std < thresh
    print(f"替代冲突指数: 90 分位阈值 {thresh:.4f}, 高冲突 n={hi.sum()}")
    # 高冲突子集内域序 vs 全量 (同一加权聚合口径)
    def subset_order(mask, conflict):
        mask = np.asarray(mask)
        out = {}
        for d in doms:
            sel = (dom == d) & mask
            if sel.sum() == 0:
                continue
            out[d] = float(wmean(Qw[sel], 1.0 / (conflict[sel] + 0.05)))
        return out
    so_hi = subset_order(hi, conflict_std)
    rho_hi = float(spearmanr([do_w[d] for d in doms], [so_hi[d] for d in doms])[0])
    print(f"高冲突子集域序 Spearman vs 全量 = {rho_hi}")

    # 3) 替代冲突率 vs 消解位移 (v57 为 0.0)
    Qr6 = robust_resolve(X, w, 6)
    shift = Qr6 - Qw
    rho_shift = float(spearmanr(conflict_std, shift)[0])
    rho_shift_fam = float(spearmanr(conflict_fam, shift)[0])
    print(f"冲突率(std) vs 消解位移 Spearman = {rho_shift:.3f}; "
          f"双族差口径 = {rho_shift_fam:.3f}")

    out = {"n": int(len(df)), "k_sweep": k_rows, "k_all_rho_one": all_one,
           "alt_conflict_std_p90": thresh, "n_high": int(hi.sum()),
           "rho_high_vs_all": rho_hi, "rho_std_vs_shift": rho_shift,
           "rho_family_vs_shift": rho_shift_fam,
           "domain_order_weighted": {d: do_w[d] for d in doms}}
    json.dump(out, open(os.path.join(EX, "v89_p1_resolve_robust.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2))
    ax = axes[0]
    ax.bar([str(k) for k in ks], k_rho, color="#177cb0", alpha=0.9, width=0.55)
    ax.axhline(1.0, color="#1685a9", ls="--", lw=1)
    ax.set_ylim(0.96, 1.004); ax.set_ylabel("域序 Spearman(加权, 消解)")
    ax.set_xlabel("对称截尾 k (去 k/2 低 + k/2 高指标)")
    ax.set_title("消解规则对截尾参数 k 的稳健性"); ax.grid(alpha=0.3, axis="y")
    ax = axes[1]
    order = sorted(doms, key=lambda d: -do_w[d])
    ax.bar(np.arange(len(order)), [do_w[d] for d in order], width=0.62,
           color="#3eede7", label="全量")
    ax.bar(np.arange(len(order)) + 0.32, [so_hi[d] for d in order], width=0.62,
           color="#44cef6", label="高冲突子集")
    ax.set_xticks(np.arange(len(order)) + 0.16)
    ax.set_xticklabels(order, rotation=30, fontsize=8)
    ax.set_ylabel("域均质量分"); ax.set_title("高冲突子集域序 vs 全量 (替代冲突指数)")
    ax.grid(alpha=0.3, axis="y"); ax.legend(fontsize=8)
    fig.suptitle("P1 冲突消解规则的替代构造交叉验证 (k 扫描 + 冲突指数构造)", fontsize=12, y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(EX, "v89_p1_resolve_robust.png"), dpi=200)
    plt.close(fig)
    print("done v89")


if __name__ == "__main__":
    main()