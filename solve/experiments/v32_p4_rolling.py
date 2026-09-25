# -*- coding: utf-8 -*-
"""
v32 实验: 前沿模型的滚动窗口稳定性 (bN/bT 随时间窗口漂移)
对开源前沿 (open, >=2024) 以截止时点窗口 (2024-06/09/12/2025-03) 滚动
拟合 QR90 (lnS = b0 + bN lnN + bT t):
1) bN: 规模弹性是否稳定 (预测关键假设);
2) bT: 时间斜率是否衰减 (放缓证据的参数层面核验).
输出: experiments/v32_p4_rolling.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, BASE
from scipy.optimize import linprog

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


def qr_fit(X, y, tau):
    n, m = X.shape
    cvec = np.concatenate([np.zeros(m), tau * np.ones(n), (1 - tau) * np.ones(n)])
    Aeq = np.hstack([X, np.eye(n), -np.eye(n)])
    r = linprog(cvec, A_eq=Aeq, b_eq=y,
                bounds=[(None, None)] * m + [(0, None)] * (2 * n), method="highs")
    return r.x[:m]


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[lic & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) &
             (lb["date"] >= "2024-01-01")].copy()
    dfm["t"] = (dfm["date"].dt.year - 2022.0) + (dfm["date"].dt.month - 1) / 12.0
    lnS = np.log(dfm["Average ⬆️"].to_numpy(dtype=float))
    lnN = np.log(dfm["#Params (B)"].to_numpy(dtype=float))
    t = dfm["t"].to_numpy(dtype=float)

    ends = ["2024-06-30", "2024-09-30", "2024-12-31", "2025-03-31"]
    rows = []
    for e in ends:
        mask = dfm["date"] <= pd.Timestamp(e)
        X = np.column_stack([np.ones(mask.sum()), lnN[mask], t[mask]])
        b0, bN, bT = qr_fit(X, lnS[mask], 0.9)
        rows.append({"window_end": e, "n": int(mask.sum()),
                     "b0": float(b0), "bN": float(bN), "bT": float(bT)})
        print(f"窗口 {e}: n={mask.sum()}  lnS={b0:.3f}+{bN:.3f}lnN+{bT:.3f}t")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v32_p4_rolling.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    x = np.arange(len(rdf))
    ax.plot(x, rdf["bN"], "o-", lw=2, color="#177cb0", label="规模弹性 bN")
    ax.plot(x, rdf["bT"], "s-", lw=2, color="#3eede7", label="时间斜率 bT")
    for i, (a, b) in enumerate(zip(rdf["bN"], rdf["bT"])):
        ax.text(i, a + 0.012, f"{a:.3f}", ha="center", fontsize=9, color="#177cb0")
        ax.text(i, b + 0.012, f"{b:.3f}", ha="center", fontsize=9, color="#3eede7")
    ax.set_xticks(x); ax.set_xticklabels([e[:7] for e in rdf["window_end"]])
    ax.set_ylabel("QR90 斜率"); ax.set_title("v32: 前沿模型滚动窗口参数稳定性")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v32_p4_rolling.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v32_p4_rolling.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("\ndone v32")


if __name__ == "__main__":
    main()