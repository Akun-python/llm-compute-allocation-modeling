# -*- coding: utf-8 -*-
"""
v38 实验: 开源 vs 全量前沿的差距 (开源追赶视角)
C1 排行榜按 License 分开源/非开源, 按季度取各群组能力前沿 (Average 最大):
1) 各季度开源前沿 S_open vs 全量前沿 S_all 的比值 (追赶进度);
2) 差距是否随时间收窄 (开源策略有效性).
输出: experiments/v38_p4_open_gap.csv/.json/.png
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


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb = lb[lb["date"].notna()]
    dfm = lb[(lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0)].copy()
    lic = dfm["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False).to_numpy()
    dfm["qtr"] = dfm["date"].dt.year.astype(str) + "-Q" + \
        ((dfm["date"].dt.month - 1) // 3 + 1).astype(str)
    rows = []
    for q, g in dfm.groupby("qtr"):
        s_all = g["Average ⬆️"].max()
        idx = g.index.to_numpy()
        loc = dfm.index.get_indexer(idx)
        go = g[lic[loc]]
        if len(go) == 0:
            continue
        s_open = go["Average ⬆️"].max()
        rows.append({"qtr": q, "n": len(g), "n_open": int(lic[loc].sum()),
                     "S_all": float(s_all), "S_open": float(s_open),
                     "ratio": float(s_open / s_all)})
        print(f"{q}: 全量 {s_all:.1f} | 开源 {s_open:.1f} | 比值 {s_open/s_all:.2f} (n_open={int(lic[loc].sum())})")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v38_p4_open_gap.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(range(len(rdf)), rdf["S_all"], "o-", lw=2, color="#177cb0", label="全量前沿")
    ax.plot(range(len(rdf)), rdf["S_open"], "s--", lw=2, color="#3eede7", label="开源前沿")
    ax.set_xticks(range(len(rdf))); ax.set_xticklabels(rdf["qtr"], rotation=25)
    ax.set_ylabel("前沿平均分 S")
    ax2 = ax.twinx()
    ax2.plot(range(len(rdf)), rdf["ratio"], "d-", lw=1.6, color="#44cef6", label="开源/全量比值")
    ax2.set_ylabel("开源/全量比值", color="#44cef6"); ax2.set_ylim(0.5, 1.05)
    ax.set_title("开源 vs 全量能力前沿 (开源追赶)")
    ax.legend(loc="upper left", fontsize=9); ax2.legend(loc="lower left", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v38_p4_open_gap.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v38_p4_open_gap.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("\ndone v38")


if __name__ == "__main__":
    main()