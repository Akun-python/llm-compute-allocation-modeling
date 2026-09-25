# -*- coding: utf-8 -*-
"""
v69 实验: 开源家族的追赶时间预测
C1 开放行 2024-06..2025-03, 家族 90 分位分:
1) 各家族当前(2025-03) 90 分位与增速 g_f (对数线性月化);
2) 领跑者 = 当前 90 分位最高家族; 落后家族追赶时间
   T_catch = ln(领跑/当前) / (g_f - g_lead), 若 g_f <= g_lead 则永不收敛;
3) 结论: 哪些家族 12/24 个月内追平, 哪些永不 (增速不足).
输出: experiments/v69_p4_catchup.csv/.json/.png
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
    dfm = lb[(lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) & lic
             & (lb["date"] >= "2024-06-01")].copy()
    dfm["ym"] = dfm["date"].dt.to_period("M").astype(str)
    dfm["family"] = dfm["Model"].apply(fam_of)

    rows = []
    for f, g in dfm.groupby("family"):
        if len(g) < 30:
            continue
        gm = g.groupby("ym")["Average ⬆️"].quantile(0.9)
        gm = gm[gm.notna()].sort_index()
        if len(gm) < 4:
            continue
        ts = np.arange(len(gm)); ys = np.log(gm.to_numpy())
        b = np.polyfit(ts, ys, 1)[0]
        months = (pd.Period(gm.index[-1]) - pd.Period(gm.index[0])).n
        rows.append({"family": f, "n": int(len(g)), "S90_now": float(gm.iloc[-1]),
                     "g_month": float(b), "g_annual": float(b) * 12})
        print(f"{f:10s} n={len(g):>4} | 90分位 {gm.iloc[-1]:.1f} | 月增速 {b:+.3f} (年化 {b*12:+.2f})")
    rdf = pd.DataFrame(rows).sort_values("S90_now", ascending=False)
    lead = rdf.iloc[0]
    print(f"\n领跑者: {lead['family']} (90分位 {lead['S90_now']:.1f}, 月增速 {lead['g_month']:+.3f})")
    out = []
    for _, r in rdf.iterrows():
        gap = np.log(lead["S90_now"] / r["S90_now"])
        rel = r["g_month"] - lead["g_month"]
        if rel > 0:
            T = gap / rel
            out.append({"family": r["family"], "gap_log": float(gap),
                        "gap_pct": float((lead["S90_now"] / r["S90_now"] - 1) * 100),
                        "T_catch_months": float(T),
                        "T_catch_label": f"{T:.0f} 个月" if T < 60 else f"{T/12:.1f} 年"})
            print(f"  {r['family']:10s} 差距 {gap:.2f} log | 追赶 {T:.0f} 个月")
        else:
            out.append({"family": r["family"], "gap_log": float(gap),
                        "gap_pct": float((lead["S90_now"] / r["S90_now"] - 1) * 100),
                        "T_catch_months": None, "T_catch_label": "永不(增速不足)"})
            print(f"  {r['family']:10s} 差距 {gap:.2f} log | 永不 (g_f {r['g_month']:+.3f} <= 领跑 {lead['g_month']:+.3f})")
    odf = pd.DataFrame(out)
    odf.to_csv(os.path.join(EX, "v69_p4_catchup.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    for _, r in odf.iterrows():
        c = "#177cb0" if r["T_catch_months"] is not None and r["T_catch_months"] <= 12 else \
            ("#1685a9" if r["T_catch_months"] is not None else "#3eede7")
        ax.barh(r["family"], r["gap_pct"], color=c, alpha=0.85)
        lab = r["T_catch_label"]
        ax.text(r["gap_pct"], r["family"], f"  {lab}", va="center", fontsize=8)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("相对领跑者差距 (%)")
    ax.set_title("v69: 开源家族追赶时间 (蓝<=12个月, 青>12个月, 红=永不)")
    ax.grid(alpha=0.3, axis="x")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v69_p4_catchup.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v69_p4_catchup.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": out, "leader": {"family": lead["family"], "S90": float(lead["S90_now"]),
                    "g_month": float(lead["g_month"])}}, f, ensure_ascii=False, indent=2)
    print("\ndone v69")


if __name__ == "__main__":
    main()