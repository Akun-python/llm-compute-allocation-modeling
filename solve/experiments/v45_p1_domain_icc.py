# -*- coding: utf-8 -*-
"""
v45 实验: 质量分的域间一致性 (ICC / 方差分解)
在 90k 样本的 TOPSIS 质量分上做单向方差分解:
1) 域间方差 sigma_b^2 vs 域内方差 sigma_w^2;
2) ICC = sigma_b^2 / (sigma_b^2 + sigma_w^2): 质量分的可解释方差占比;
3) 同域内部 vs 跨域差异的 F 检验 (域主效应显著性).
结论: 域是质量分的主效应载体 (ICC 高 => 域级质量排序有统计根基).
输出: experiments/v45_p1_domain_icc.csv/.json/.png
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


def icc_anova(Q, dom):
    doms = np.unique(dom)
    k = len(doms)
    grand = Q.mean()
    n = len(Q)
    ss_b = sum(len(Q[dom == d]) * (Q[dom == d].mean() - grand) ** 2 for d in doms)
    ss_w = sum(((Q[dom == d] - Q[dom == d].mean()) ** 2).sum() for d in doms)
    df_b, df_w = k - 1, n - k
    ms_b, ms_w = ss_b / df_b, ss_w / df_w
    F = ms_b / ms_w
    sigma_b = max((ms_b - ms_w) / n * n / (n - df_b / k), 0.0)  # 组间方差分量
    sigma_w = ms_w
    icc = sigma_b / (sigma_b + sigma_w) if (sigma_b + sigma_w) > 0 else 0.0
    return icc, F, df_b, df_w, sigma_b, sigma_w


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

    icc, F, df_b, df_w, sb, sw = icc_anova(Q, dom)
    print(f"ICC = {icc:.3f} | F({df_b},{df_w}) = {F:.1f} | sigma_b = {sb:.5f} | sigma_w = {sw:.5f}")

    # 域内一致性: 每域 25/75 分位带宽 vs 全域
    rows = []
    for d in np.unique(dom):
        q = Q[dom == d]
        rows.append({"domain": d, "n": len(q), "mean": float(q.mean()),
                     "sd": float(q.std()), "p25": float(np.percentile(q, 25)),
                     "p75": float(np.percentile(q, 75))})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v45_p1_domain_icc.csv"), index=False, encoding="utf-8-sig")
    print(rdf.round(3).to_string(index=False))

    fig, ax = plt.subplots(figsize=(8.5, 5))
    pos = np.arange(len(rdf))
    ax.barh(pos, rdf["sd"], color="#2563EB", alpha=0.85)
    ax.set_yticks(pos); ax.set_yticklabels(rdf["domain"])
    ax.set_xlabel("域内质量分标准差"); ax.set_title(f"v45: 域内离散度 (ICC={icc:.3f})")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v45_p1_domain_icc.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v45_p1_domain_icc.json"), "w", encoding="utf-8") as f:
        json.dump({"icc": float(icc), "F": float(F), "df_b": int(df_b), "df_w": int(df_w),
                   "sigma_b": float(sb), "sigma_w": float(sw),
                   "domains": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v45")


if __name__ == "__main__":
    main()