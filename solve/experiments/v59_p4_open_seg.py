# -*- coding: utf-8 -*-
"""
v59 实验: 开源-闭源差距的规模段分解
C1 2024-06..2025-03, 按参数规模分桶 + 开源/闭源:
1) 每桶每季度: 开源 90 分位 vs 闭源 90 分位 (前沿口径) 与中位数;
2) 差距比 open/closed 的演化 (追赶是否分段);
3) 结论: 开源追赶在哪些规模段完成/未完成.
输出: experiments/v59_p4_open_seg.csv/.json/.png
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
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"
import plotstyle

BUCKETS = [(0.3, 1), (1, 3), (3, 10), (10, 30), (30, 100)]


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb = lb[lb["date"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    closed = lb["Hub License"].notna() & ~lic
    dfm = lb[(lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) & (lb["date"] >= "2024-06-01")].copy()
    dfm["q"] = dfm["date"].dt.year * 4 + dfm["date"].dt.month // 3
    dfm["open"] = lic[dfm.index] if hasattr(lic, "index") else lic.to_numpy()[dfm.index.to_numpy()]
    dfm["bucket"] = pd.cut(dfm["#Params (B)"], bins=[b[0] for b in BUCKETS] + [100],
                           labels=[f"{lo}-{hi}B" for lo, hi in BUCKETS])
    qs = sorted(dfm["q"].unique())
    rows = []
    for b in BUCKETS:
        g = dfm[(dfm["#Params (B)"] >= b[0]) & (dfm["#Params (B)"] < b[1])]
        for q in qs:
            gq = g[g["q"] == q]
            op = gq[gq["open"]]["Average ⬆️"]
            cl = gq[~gq["open"]]["Average ⬆️"]
            if len(op) < 5 or len(cl) < 5:
                continue
            med_ratio = float(np.median(op) / np.median(cl))
            rows.append({"bucket": f"{b[0]}-{b[1]}B", "quarter": int(q),
                         "n_open": int(len(op)), "n_closed": int(len(cl)),
                         "median_open": float(np.median(op)), "median_closed": float(np.median(cl)),
                         "med_ratio": med_ratio})
            print(f"{b[0]:>4}-{b[1]:<4}B Q{int(q%4) or 4} 开/闭中位比 {med_ratio:.2f} "
                  f"(n={len(op)}/{len(cl)})")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v59_p4_open_seg.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9, 5))
    for b in BUCKETS:
        g = rdf[rdf["bucket"] == f"{b[0]}-{b[1]}B"]
        if len(g):
            ax.plot(g["quarter"], g["med_ratio"], marker="o", lw=1.6,
                    label=f"{b[0]}-{b[1]}B")
    ax.axhline(1.0, color="#3eede7", lw=1.3, ls="--", label="open = closed")
    ax.set_xticks(qs); ax.set_xticklabels([f"Q{int(q%4) or 4}" for q in qs])
    ax.set_ylabel("开源/闭源中位分比"); ax.set_xlabel("季度")
    ax.set_title("v59: 开源-闭源差距的规模段分解")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v59_p4_open_seg.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v59_p4_open_seg.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v59")


if __name__ == "__main__":
    main()