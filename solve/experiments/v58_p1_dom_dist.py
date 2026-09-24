# -*- coding: utf-8 -*-
"""
v58 实验: 域内文档级质量分布的形状
90k 样本上逐文档 TOPSIS 质量分 Q_i, 按域刻画分布形状:
1) 均值/std/偏度/峰度 + 高质尾占比 (Q_i > 全域75分位);
2) 重叠密度曲线: book 宽而高, commoncrawl 低而聚;
3) 与 v45 ICC (域间仅5%方差) 呼应: 域内分布形状 = 第二层筛选的依据;
4) 过滤头寸: 低质域内的高质长尾 = 可筛选挽救的文档占比.
输出: experiments/v58_p1_dom_dist.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax,
                        entropy_weight, critic_weight, topsis, ALL_IND)
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
    dom = df["_source_domain"].fillna("none").to_numpy()
    X = winsorize_minmax(df[ALL_IND].to_numpy(dtype=float).copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    we, _ = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, float) + 0.5 * np.asarray(wc, float)
    Q = topsis(X, w)
    thr = np.percentile(Q, 75)

    rows = []
    for d in np.unique(dom):
        q = Q[dom == d]
        rows.append({"domain": d, "n": int(len(q)), "mean": float(q.mean()),
                     "std": float(q.std()), "skew": float(pd.Series(q).skew()),
                     "kurt": float(pd.Series(q).kurt()),
                     "high_tail_share": float(np.mean(q > thr)),
                     "p90": float(np.percentile(q, 90))})
        r = rows[-1]
        print(f"{d:13s} mean={r['mean']:.3f} sd={r['std']:.3f} skew={r['skew']:+.2f} "
              f"kurt={r['kurt']:+.2f} | 高质尾占比 {r['high_tail_share']:.2f} | p90={r['p90']:.3f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v58_p1_dom_dist.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    for d in np.unique(dom):
        q = Q[dom == d]
        ax.hist(q, bins=40, density=True, alpha=0.55, label=d)
    ax.axvline(thr, color="#C2410C", lw=1.2, ls="--", label=f"全域 75 分位 {thr:.2f}")
    ax.set_xlabel("文档级质量分 Q_i"); ax.set_ylabel("密度")
    ax.set_title("v58: 域内文档质量分布 (重叠直方图)")
    ax.legend(fontsize=8, ncol=2); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v58_p1_dom_dist.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v58_p1_dom_dist.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "q75": float(thr)}, f, ensure_ascii=False, indent=2)
    print("\ndone v58")


if __name__ == "__main__":
    main()