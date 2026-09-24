# -*- coding: utf-8 -*-
"""
v18 实验: 前沿预测管道的历史回测 (out-of-sample)
用截止年份 y0 的数据拟合 0.9 分位数回归, 预测 2024/2025 前沿 S, 与
(1) 纯数据 90 分位口径 (2) 全样本 QR 口径 (3) 已发布模型实际规模 对照.
重点: 断点前 (y0<=2024) 外推是否会系统性高估? => 支撑"用含断点后信息
的全样本"的正文做法.
输出: experiments/v18_p4_backtest.csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, RES
from scipy.optimize import linprog
from scipy.stats import percentileofscore

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)


def load_frontier():
    """合并 C3 历史 (≤2023, 每年前沿行) + C1 排行榜开源行 (2024+), 同主链路口径"""
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb["year"] = lb["date"].dt.year
    lb = lb[lb["year"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[lic & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0)].copy()
    dfm = dfm[dfm["year"] >= 2022]
    dfm["lnS"] = np.log(dfm["Average ⬆️"])
    dfm["lnN"] = np.log(dfm["#Params (B)"])
    dfm["t"] = dfm["year"] - 2022.0
    # 历史年 (2022-2023) 从 C3 补前沿行
    ts = pd.read_csv(os.path.join(C, "leaderboard_extended_timeseries.csv"))
    hist = []
    for yy in [2022, 2023]:
        g = ts[(ts["Year"] == yy) & (ts["Average"] > 0)]
        if len(g):
            g = g.sort_values("Average", ascending=False).head(6)
            for _, r in g.iterrows():
                hist.append({"lnS": np.log(r["Average"]), "lnN": np.log(r["Params_B"]),
                             "t": yy - 2022.0, "year": yy})
    hdf = pd.DataFrame(hist)
    if len(hdf):
        dfm = pd.concat([dfm, hdf], ignore_index=True)
    return dfm


def qr_fit(X, y, tau=0.9):
    n, m = X.shape
    c = np.concatenate([np.zeros(m), tau * np.ones(n), (1 - tau) * np.ones(n)])
    Aeq = np.hstack([X, np.eye(n), -np.eye(n)])
    r = linprog(c, A_eq=Aeq, b_eq=y, bounds=[(None, None)] * m + [(0, None)] * (2 * n), method="highs")
    return r.x[:m]


def main():
    dfm = load_frontier()
    gN = 1.251125395176952
    rows = []
    # 目标年份实际值: 数据口径 (该年样本 90 分位) 与 QR 全样本模型值
    for y_target in [2024, 2025]:
        for y0 in [2022, 2023, 2024]:
            if y0 >= y_target:
                continue
            tr = dfm[dfm["year"] <= y0]
            if len(tr) < 12 or tr["year"].max() != y0:
                continue
            X = np.column_stack([np.ones(len(tr)), tr["lnN"], tr["t"]])
            b = qr_fit(X, tr["lnS"].to_numpy(), 0.9)
            # 锚定规模: y0 年 lnN 90 分位, 按 gN 增长到 y_target
            lnN_anchor = tr[tr["year"] == y0]["lnN"].quantile(0.9)
            lnN_f = lnN_anchor + gN * (y_target - y0)
            S_pred = float(np.exp(b[0] + b[1] * lnN_f + b[2] * (y_target - 2022)))
            # 实际: 目标年数据 90 分位 S (样本口径)
            tt = dfm[dfm["year"] == y_target]
            S_data = float(np.exp(tt["lnS"].quantile(0.9))) if len(tt) else np.nan
            # 全样本 QR 模型值 (y_target 处, lnN=目标年90分位)
            Xall = np.column_stack([np.ones(len(dfm)), dfm["lnN"], dfm["t"]])
            ball = qr_fit(Xall, dfm["lnS"].to_numpy(), 0.9)
            lnN_y = float(tt["lnN"].quantile(0.9)) if len(tt) else float(dfm["lnN"].quantile(0.9))
            S_qr = float(np.exp(ball[0] + ball[1] * lnN_y + ball[2] * (y_target - 2022)))
            # 实际"模型规模"对照: 目标年内最大开源模型参数量
            N_max = float(tt["#Params (B)"].max()) if len(tt) else np.nan
            rows.append({"y0": y0, "y_target": y_target, "n_train": len(tr),
                         "bN": round(float(b[1]), 3), "bT": round(float(b[2]), 3),
                         "S_pred": round(S_pred, 1),
                         "S_data90": round(S_data, 1) if np.isfinite(S_data) else np.nan,
                         "S_qr_full": round(S_qr, 1),
                         "err_vs_data": round((S_pred - S_data) / S_data, 3) if np.isfinite(S_data) else np.nan,
                         "err_vs_qr": round((S_pred - S_qr) / S_qr, 3),
                         "N_max_released_B": round(float(N_max), 1) if np.isfinite(N_max) else np.nan})
            print(f"y0={y0} -> {y_target}: pred S={S_pred:.1f} | 数据口径 {S_data:.1f} (err {(S_pred-S_data)/S_data*100:+.0f}%) | "
                  f"全样本QR {S_qr:.1f} (err {(S_pred-S_qr)/S_qr*100:+.0f}%) | 最大开源模型 {N_max:.0f}B")

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v18_p4_backtest.csv"), index=False, encoding="utf-8-sig")
    print("\ndone v18")


if __name__ == "__main__":
    main()