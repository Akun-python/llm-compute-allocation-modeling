# -*- coding: utf-8 -*-
"""
v23 实验: 年度前沿增速表 (能力得分通胀减速的逐年证据)
合并 C3 历史 + C1 排行榜开源行, 逐年前沿 (该年 top1 S), 计算年度
对数增速 bT_yy = lnS(y+1)-lnS(y), 对照 2024 与 2025 的减速幅度,
并给出与全样本 QR 时间斜率 bT=0.089 的比较.
输出: experiments/v23_p4_annual_slowdown.csv/.json
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C
from scipy.stats import linregress

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb["year"] = lb["date"].dt.year
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[lic & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) & (lb["year"] >= 2024)]
    ts = pd.read_csv(os.path.join(C, "leaderboard_extended_timeseries.csv"))
    hist = [(yy, float(g["Average"].max())) for yy in [2022, 2023]
            for g in [ts[(ts["Year"] == yy) & (ts["Average"] > 0)]] if len(g)]
    hist = pd.DataFrame(hist, columns=["year", "S"])

    fy = pd.DataFrame({"year": dfm.groupby("year")["Average ⬆️"].max().index,
                       "S": dfm.groupby("year")["Average ⬆️"].max().values})
    fy = pd.concat([hist, fy], ignore_index=True).sort_values("year")
    fy["lnS"] = np.log(fy["S"])
    fy["dlnS"] = fy["lnS"].diff()
    fy["g_pct"] = fy["S"].pct_change() * 100
    print(fy.round(3).to_string(index=False))

    # 分段时间斜率: 2022-2024 vs 2024-2025
    pre = fy[fy["year"] <= 2024]
    bT_pre = float(linregress(pre["year"], pre["lnS"]).slope)
    bT_last = float(fy["dlnS"].iloc[-1])
    bT_full = float(linregress(fy["year"], fy["lnS"]).slope)
    print(f"\nbT: 2022-2024 全段 {bT_pre:.3f} | 最后一年 {bT_last:.3f} | 全样本 2022-2025 {bT_full:.3f}")
    ratio = bT_last / bT_pre
    print(f"2025 年度增速 / 2022-2024 平均 = {ratio:.2f} (减速 {(1-ratio)*100:.0f}%)")

    fy.to_csv(os.path.join(EX, "v23_p4_annual_slowdown.csv"), index=False, encoding="utf-8-sig")
    out = {"annual": fy.to_dict("records"),
           "bT_2022to2024": float(bT_pre), "bT_last_year": float(bT_last),
           "bT_full": float(bT_full), "slowdown_ratio": float(ratio)}
    with open(os.path.join(EX, "v23_p4_annual_slowdown.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\ndone v23")


if __name__ == "__main__":
    main()