# -*- coding: utf-8 -*-
"""
v55 实验: 前沿的规模分桶增速梯度
开放行 (2024-06..2025-03) 按参数规模分 5 桶:
  [0.3-1, 1-3, 3-10, 10-30, 30-100]B
1) 每桶月度 90 分位分的对数线性拟合 => 年化增速;
2) 增速 vs 规模桶的关系 (大模型是否进步更快 / 小模型追赶);
3) 桶间前沿差距的演化 (头部桶-次头部桶差距收窄=追赶).
输出: experiments/v55_p4_scale_bucket.csv/.json/.png
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
    dfm = lb[(lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) & lic].copy()
    dfm = dfm[dfm["date"] >= "2024-06-01"].copy()
    dfm["t"] = (dfm["date"].dt.year - 2022) + (dfm["date"].dt.month - 1) / 12
    dfm["lnS"] = np.log(dfm["Average ⬆️"])

    rows = []
    for lo, hi in BUCKETS:
        g = dfm[(dfm["#Params (B)"] >= lo) & (dfm["#Params (B)"] < hi)]
        if len(g) < 30:
            continue
        gm = g.groupby("t")["lnS"].quantile(0.9)
        ts = gm.index.to_numpy()
        ys = gm.to_numpy()
        b = np.polyfit(ts, ys, 1)[0]
        ann = b * 12
        n = int(len(g))
        rows.append({"bucket": f"{lo}-{hi}B", "n": n, "b_month": float(b),
                     "annual_growth": float(ann),
                     "S90_start": float(np.exp(ys.min())), "S90_end": float(np.exp(ys.max()))})
        print(f"桶 {lo}-{hi}B (n={n}): 月度斜率 {b:.3f} => 年化 {ann:.2f} (90分位)")

    # 桶间差距: 最大桶 vs 次大桶 90 分位差距 (对数) 首末月
    top = max(rows, key=lambda r: r["bucket"])
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v55_p4_scale_bucket.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.bar(range(len(rdf)), rdf["annual_growth"], color="#177cb0", alpha=0.85)
    ax.set_xticks(range(len(rdf))); ax.set_xticklabels(rdf["bucket"], rotation=20)
    ax.set_ylabel("年化增速 (90 分位分)"); ax.set_title("前沿的规模分桶增速梯度")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v55_p4_scale_bucket.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v55_p4_scale_bucket.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v55")


if __name__ == "__main__":
    main()