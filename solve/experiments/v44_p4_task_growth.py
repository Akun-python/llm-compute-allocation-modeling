# -*- coding: utf-8 -*-
"""
v44 实验: 能力构成的演化 (分任务前沿增速)
C1 排行榜开放行的分任务列 (IFEval/BBH/MATH/GPQA/MUSR/MMLU-PRO):
1) 按月取各任务前沿 (月度最大值), 2024-06..2025-03 段;
2) 每任务年化增速 g_task = ln(max_end/max_start)/T*12 (月->年);
3) 结论: 推理类 (GPQA/MATH) 是否快于指令跟随 (IFEval) / 百科 (MMLU)?
输出: experiments/v44_p4_task_growth.csv/.json/.png
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


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb = lb[lb["date"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[(lb["#Params (B)"] > 0) & lic].copy()
    dfm["ym"] = dfm["date"].dt.to_period("M").astype(str)
    rows = []
    for t in TASKS:
        g = dfm.groupby("ym")[t].max()
        g = g[g.notna()]
        g = g.sort_index()
        t0, t1 = g.index[0], g.index[-1]
        T = (pd.Period(t1) - pd.Period(t0)).n
        rate = float(np.log(g.iloc[-1] / g.iloc[0]) / T * 12)
        rows.append({"task": t, "first": g.index[0], "last": g.index[-1],
                     "start": float(g.iloc[0]), "end": float(g.iloc[-1]),
                     "months": T, "annual_growth": rate})
        print(f"{t}: {g.iloc[0]:.1f}({g.index[0]}) -> {g.iloc[-1]:.1f}({g.index[-1]}) "
              f"| 年化 {rate:+.2f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v44_p4_task_growth.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for t in TASKS:
        g = dfm.groupby("ym")[t].max()
        g = g[g.notna()].sort_index()
        ax.plot(range(len(g)), g.values, "o-", lw=1.8, label=t)
    ax.set_xticks(range(len(g))); ax.set_xticklabels(g.index, rotation=45, fontsize=8)
    ax.set_ylabel("任务前沿 (月度最大值)"); ax.set_title("分任务能力前沿 (2024-06..2025-03)")
    ax.legend(fontsize=8, ncol=2); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v44_p4_task_growth.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v44_p4_task_growth.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("\ndone v44")


if __name__ == "__main__":
    main()