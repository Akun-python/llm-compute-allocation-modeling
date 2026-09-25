# -*- coding: utf-8 -*-
"""
v28 实验: 冲突消解的截尾深度敏感性 (k 扫描)
对对称截尾聚合 Q*_k (k=0,2,4,6,8,10) 检验:
1) 消解单调性: 高冲突样本 Q* 均值随 k 单调上升 (消解强度越大越明显);
2) 域序稳定性: 各 k 下域级 Q* 排序与 k=6 (正文默认) 的 Spearman 秩相关;
3) 主链路结论 (Q* 0.430->0.535, k=6) 的邻域鲁棒性.
输出: experiments/v28_p1_k_sens.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax,
                        entropy_weight, critic_weight, robust_resolve, ALL_IND)
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
    Xraw = df[ALL_IND].to_numpy(dtype=float)
    X = winsorize_minmax(Xraw.copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)   # 列均值填补 (同 v15)
    we, _e = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, dtype=float) + 0.5 * np.asarray(wc, dtype=float)

    # 冲突样本: |Q_C - Q_F| 高 (与主链路一致口径, 取 top 20%)
    from p1_quality import family_scores
    qc, qf = family_scores(X)
    conf = np.abs(qc - qf)
    thr = np.quantile(conf, 0.8)
    mask = conf >= thr
    print(f"n={len(X)} 冲突样本(top20%): {mask.sum()}")

    rows = []
    Qs = {}
    for k in [0, 2, 4, 6, 8, 10]:
        Qr = robust_resolve(X, w, k=k)
        Qs[k] = Qr
        rows.append({"k": k, "Qstar_high_conf": float(np.mean(Qr[mask])),
                     "Qstar_all": float(np.mean(Qr)),
                     "Qstar_base_conf": float(np.nanmean(w * X[mask]) / w.sum())})
        print(f"k={k}: 高冲突 Q*={rows[-1]['Qstar_high_conf']:.4f} | 全体 {rows[-1]['Qstar_all']:.4f}")

    # 域序稳定性: 按域对齐后比较 (k=6 为基准)
    dom = df["_source_domain"].fillna("none").to_numpy()
    order = {}
    for k in [0, 2, 4, 6, 8, 10]:
        dq = pd.DataFrame({"Q": Qs[k], "domain": dom}).groupby("domain")["Q"].mean()
        order[k] = dq.sort_values(ascending=False)
        print(f"k={k}: 域序 {[f'{d}:{v:.3f}' for d, v in order[k].items()][:7]}")

    base = order[6]
    sp = {}
    for k in [0, 2, 4, 8, 10]:
        aligned = pd.concat([base.rename("b"), order[k].rename("o")], axis=1).dropna()
        sp[k] = float(spearmanr(aligned["b"], aligned["o"]).statistic)
    print("\n域序与 k=6 的 Spearman (按域对齐):", sp)

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v28_p1_k_sens.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(rdf["k"], rdf["Qstar_high_conf"], "o-", lw=2, color="#177cb0", label="高冲突样本 Q*")
    ax.plot(rdf["k"], rdf["Qstar_all"], "s--", lw=2, color="#88ada6", label="全体样本 Q*")
    ax.axhline(rows[0]["Qstar_base_conf"], ls=":", color="#3eede7", label="高冲突基准(未消解)")
    ax.set_xlabel("对称截尾深度 k"); ax.set_ylabel("聚合质量分 Q*")
    ax.set_title("冲突消解深度敏感性")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v28_p1_k_sens.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v28_p1_k_sens.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "spearman_vs_k6": sp}, f, ensure_ascii=False, indent=2)
    print("\ndone v28")


if __name__ == "__main__":
    main()