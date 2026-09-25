# -*- coding: utf-8 -*-
"""
v42 实验: 开源前沿的家族竞争动态
按季度识别开源前沿的领跑家族 (按 Model 关键词匹配 Llama/Qwen/Gemma/
DeepSeek/Mistral/Phi 等) 与竞争广度:
1) 每季度领跑家族 (开源行 S 最大者的家族) 与紧随其后的家族;
2) 竞争集中度: 前 5 高分模型家族的 HHI (越分散竞争越激烈).
输出: experiments/v42_p4_family_dyn.csv/.json/.png
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

FAMILIES = ["llama", "qwen", "gemma", "deepseek", "mistral", "phi", "olmo",
            "gpt", "claude", "baichuan", "yi", "falcon"]


def fam_of(name):
    n = str(name).lower()
    for f in FAMILIES:
        if f in n:
            return f
    return "other"


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb = lb[lb["date"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[(lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) & lic].copy()
    dfm["qtr"] = dfm["date"].dt.year.astype(str) + "-Q" + \
        ((dfm["date"].dt.month - 1) // 3 + 1).astype(str)
    dfm["family"] = dfm["Model"].apply(fam_of)
    rows = []
    for q, g in dfm.groupby("qtr"):
        top = g.sort_values("Average ⬆️", ascending=False).head(5)
        top5 = top["family"].value_counts().to_dict()
        shares = np.array(list(top5.values()), dtype=float) / 5.0
        hhi = float((shares ** 2).sum())
        leader = g.loc[g["Average ⬆️"].idxmax()]
        runner = g[g["family"] != leader["family"]].sort_values("Average ⬆️", ascending=False)
        runner_fam = fam_of(runner.iloc[0]["Model"]) if len(runner) else "none"
        rows.append({"qtr": q, "leader": fam_of(leader["Model"]), "S_leader": float(leader["Average ⬆️"]),
                     "runner": runner_fam, "hhi_top5": hhi,
                     "n": len(g), "families": sorted(g["family"].unique())})
        print(f"{q}: 领跑={fam_of(leader['Model'])} ({leader['Average ⬆️']:.1f}) "
              f"| 第二={runner_fam} | top5 HHI={hhi:.2f} | 家族数={len(g['family'].unique())}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v42_p4_family_dyn.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(range(len(rdf)), rdf["hhi_top5"], "o-", color="#177cb0", lw=2, label="top5 家族 HHI")
    ax.set_xticks(range(len(rdf))); ax.set_xticklabels(rdf["qtr"], rotation=25)
    ax.set_ylabel("HHI (前 5 高分模型)"); ax.set_ylim(0.2, 1.0)
    for i, r in rdf.iterrows():
        ax.annotate(r["leader"], (i, r["hhi_top5"]),
                    textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8, color="#3eede7")
    ax.set_title("v42: 开源前沿家族竞争 (领跑家族 + top5 集中度)")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v42_p4_family_dyn.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v42_p4_family_dyn.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("\ndone v42")


if __name__ == "__main__":
    main()