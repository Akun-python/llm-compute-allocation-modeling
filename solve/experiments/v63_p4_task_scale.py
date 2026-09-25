# -*- coding: utf-8 -*-
"""
v63 实验: 任务x规模二维增速热图
C1 开放行分任务列 + 参数分桶:
1) 每 (规模桶, 任务): 月度 90 分位的对数线性年化增速;
2) 热图: 行=任务, 列=规模桶;
3) 结论: 推理类任务在哪个规模段进步最快 (10-30B?), 指令/百科类的
   规模段分布.
输出: experiments/v63_p4_task_scale.csv/.json/.png
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

TASKS = ["IFEval", "BBH", "MATH Lvl 5", "GPQA", "MUSR", "MMLU-PRO"]
LABS = ["IFEval", "BBH", "MATH", "GPQA", "MUSR", "MMLU-PRO"]
BUCKETS = [(0.3, 1), (1, 3), (3, 10), (10, 30), (30, 100)]
BNAMES = ["0.3-1B", "1-3B", "3-10B", "10-30B", "30-100B"]


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb = lb[lb["date"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[(lb["#Params (B)"] > 0) & lic & (lb["date"] >= "2024-06-01")].copy()
    dfm["ym"] = dfm["date"].dt.to_period("M").astype(str)

    grid = np.zeros((len(TASKS), len(BUCKETS)))
    ncell = np.zeros((len(TASKS), len(BUCKETS)), int)
    for ti, t in enumerate(TASKS):
        for bi, (lo, hi) in enumerate(BUCKETS):
            g = dfm[(dfm["#Params (B)"] >= lo) & (dfm["#Params (B)"] < hi)].copy()
            gm = g.groupby("ym")[t].quantile(0.9)
            gm = gm[gm.notna()].sort_index()
            if len(gm) < 4:
                grid[ti, bi] = np.nan
                continue
            ts = np.arange(len(gm))
            ys = np.log(gm.to_numpy())
            b = np.polyfit(ts, ys, 1)[0]
            # 年化: 月份跨度
            months = (pd.Period(gm.index[-1]) - pd.Period(gm.index[0])).n
            grid[ti, bi] = b * 12 if months > 0 else np.nan
            ncell[ti, bi] = int(g[g[t].notna()].shape[0])
            print(f"{LABS[ti]:8s} {BNAMES[bi]:8s} 90分位年化 {grid[ti,bi]:+.2f} (n={ncell[ti,bi]})")

    rdf = pd.DataFrame(grid, index=LABS, columns=BNAMES)
    rdf.to_csv(os.path.join(EX, "v63_p4_task_scale.csv"), encoding="utf-8-sig")
    with open(os.path.join(EX, "v63_p4_task_scale.json"), "w", encoding="utf-8") as f:
        json.dump({"grid": rdf.round(3).to_dict(), "ncell": ncell.tolist(),
                   "tasks": LABS, "buckets": BNAMES}, f, ensure_ascii=False, indent=2)

    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    im = ax.imshow(grid, cmap="cyan_div", vmin=-1.5, vmax=1.5, aspect="auto")
    ax.set_xticks(range(len(BNAMES))); ax.set_xticklabels(BNAMES)
    ax.set_yticks(range(len(LABS))); ax.set_yticklabels(LABS)
    for ti in range(len(TASKS)):
        for bi in range(len(BUCKETS)):
            v = grid[ti, bi]
            if np.isnan(v):
                continue
            ax.text(bi, ti, f"{v:+.2f}", ha="center", va="center", fontsize=8,
                    color="white" if abs(v) > 0.7 else "black")
    ax.set_title("v63: 任务x规模二维前沿增速 (90分位年化)")
    fig.colorbar(im, ax=ax, label="年化对数增速")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v63_p4_task_scale.png"), dpi=200)
    plt.close(fig)
    print("\ndone v63")


if __name__ == "__main__":
    main()