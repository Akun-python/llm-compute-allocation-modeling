# -*- coding: utf-8 -*-
"""
v64 实验: 前沿的分层演进 (90/75/50 分位增速对比)
C1 开放行 2024-06..2025-03:
1) 全域 + 1-3B + 10-30B 三个口径, 每月 90/75/50 分位分的年化增速;
2) 顶层(p90) vs 中位(p50) 增速比: 顶层独快(分化) 还是全层同步(普惠)?
3) 结论: 能力提升是否普惠整个分布.
输出: experiments/v64_p4_stratify.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, BASE

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

QS = [0.5, 0.75, 0.9]
QL = ["p50", "p75", "p90"]


def rate(gm):
    gm = gm[gm.notna()].sort_index()
    if len(gm) < 4:
        return np.nan
    ts = np.arange(len(gm))
    ys = np.log(gm.to_numpy())
    b = np.polyfit(ts, ys, 1)[0]
    months = (pd.Period(gm.index[-1]) - pd.Period(gm.index[0])).n
    return b * 12 if months > 0 else np.nan


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb = lb[lb["date"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[(lb["#Params (B)"] > 0) & lic & (lb["date"] >= "2024-06-01")].copy()
    dfm["ym"] = dfm["date"].dt.to_period("M").astype(str)

    rows = []
    for name, mask in [("全域", dfm.index), ("1-3B", dfm[(dfm["#Params (B)"] >= 1) & (dfm["#Params (B)"] < 3)].index),
                        ("10-30B", dfm[(dfm["#Params (B)"] >= 10) & (dfm["#Params (B)"] < 30)].index)]:
        g = dfm.loc[mask]
        vals = {}
        for q, ql in zip(QS, QL):
            gm = g.groupby("ym")["Average ⬆️"].quantile(q)
            r = rate(gm)
            vals[ql] = r
            print(f"{name:6s} {ql}: 年化 {r:+.2f}")
        ratio = vals["p90"] / vals["p50"] if vals["p50"] not in (0, np.nan) and not np.isnan(vals["p50"]) else np.nan
        vals["p90_p50_ratio"] = ratio
        print(f"{name:6s} p90/p50 比 = {ratio:.2f}\n")
        rows.append({"scope": name, **vals})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v64_p4_stratify.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    x = np.arange(len(rdf))
    w = 0.26
    for i, ql in enumerate(QL):
        ax.bar(x + (i - 1) * w, rdf[ql], w, label=ql, color=["#94A3B8", "#0EA5E9", "#2563EB"][i])
    ax.axhline(0, color="#C2410C", lw=1.0)
    ax.set_xticks(x); ax.set_xticklabels(rdf["scope"])
    ax.set_ylabel("年化对数增速")
    ax.set_title("v64: 前沿的分层演进 (p90/p75/p50)")
    ax.legend(fontsize=9); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v64_p4_stratify.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v64_p4_stratify.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)
    print("done v64")


if __name__ == "__main__":
    main()