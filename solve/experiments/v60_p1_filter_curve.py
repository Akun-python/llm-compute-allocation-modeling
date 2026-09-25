# -*- coding: utf-8 -*-
"""
v60 实验: 文档级筛选的质量提升曲线 (第二层筛选收益量化)
90k 样本逐文档 Q_i: 对每域按 Q_i 截尾 y% 低质文档 (保留 top 100-y%),
1) 每域筛选曲线: 保留比例 p -> 域平均质量;
2) 关键数字: 删低质 20% 后的域平均质量提升 dQ20 (绝对/相对);
3) 低质域(commoncrawl/c4) 筛选收益是否最大 (长尾可挽救);
4) 与两级筛选叙事闭环: 域级粗筛 + 文档级细筛的收益数量级.
输出: experiments/v60_p1_filter_curve.csv/.json/.png
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
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"
import plotstyle

P_KEEP = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]


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

    rows = []
    for d in np.unique(dom):
        q = np.sort(Q[dom == d])[::-1]
        mean_full = q.mean()
        uplift20 = q[: int(0.8 * len(q))].mean() - mean_full
        row = {"domain": d, "n": int(len(q)), "mean_full": float(mean_full),
               "uplift_del20": float(uplift20),
               "rel_uplift_del20_pct": float(uplift20 / mean_full * 100)}
        for p in P_KEEP:
            row[f"keep_{int(p*100)}"] = float(q[: int(p * len(q))].mean())
        rows.append(row)
        print(f"{d:13s} 全量均值 {mean_full:.3f} | 删低质20%后均值 {row['keep_80']:.3f} "
              f"| 提升 {uplift20:+.3f} (相对 {uplift20/mean_full*100:+.1f}%)")
    rdf = pd.DataFrame(rows).sort_values("uplift_del20", ascending=False)
    rdf.to_csv(os.path.join(EX, "v60_p1_filter_curve.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    for r in rows:
        ax.plot([int(p * 100) for p in P_KEEP],
                [r[f"keep_{int(p*100)}"] for p in P_KEEP], marker="o", ms=3, lw=1.5,
                label=r["domain"])
    ax.set_xlabel("保留文档比例 (%)"); ax.set_ylabel("域平均质量 Q")
    ax.set_title("v60: 文档级筛选的质量提升曲线")
    ax.legend(fontsize=8, ncol=2); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v60_p1_filter_curve.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v60_p1_filter_curve.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "keep_levels": P_KEEP}, f, ensure_ascii=False, indent=2)
    print("\ndone v60")


if __name__ == "__main__":
    main()