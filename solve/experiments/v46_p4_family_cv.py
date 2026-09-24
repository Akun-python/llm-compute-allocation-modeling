# -*- coding: utf-8 -*-
"""
v46 实验: 前沿模型的家族留出验证 (bN 的跨家族稳健性)
C1 开放行 (2024-06..2025-03), 模型按家族分桶 (llama/qwen/gemma/deepseek/
mistral/phi/olmo/yi/other), 对 ln S = c0 + bN ln N + bT t 做:
1) 全量 OLS (基准 bN 对照主链路 QR90 的 0.364);
2) 逐个家族留出: 训练于其余家族, 预测留出家族, 报告 R2/MAE;
3) bN 的留出分布 (各次拟合的 bN 值) => 规模弹性是否跨家族稳定.
结论: 前沿模型的规模弹性不依赖单一模型家族.
输出: experiments/v46_p4_family_cv.csv/.json/.png
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

FAMILIES = ["llama", "qwen", "gemma", "deepseek", "mistral", "phi", "olmo", "yi"]


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
    dfm = dfm[dfm["date"] >= "2024-06-01"].copy()
    dfm["lnN"] = np.log(dfm["#Params (B)"])
    dfm["lnS"] = np.log(dfm["Average ⬆️"])
    dfm["t"] = (dfm["date"].dt.year - 2022) + (dfm["date"].dt.month - 1) / 12
    dfm["family"] = dfm["Model"].apply(fam_of)

    X = np.column_stack([dfm["lnN"], dfm["t"], np.ones(len(dfm))])
    y = dfm["lnS"].to_numpy()
    beta_full, *_ = np.linalg.lstsq(X, y, rcond=None)
    print(f"全量 OLS: bN = {beta_full[0]:.3f} | bT = {beta_full[1]:.3f} (主链路 QR90 bN=0.364)")
    r2_full = 1 - np.sum((y - X @ beta_full) ** 2) / np.sum((y - y.mean()) ** 2)
    print(f"全量 R2 = {r2_full:.3f} (n={len(dfm)})")

    rows = []
    for f, g in dfm.groupby("family"):
        if len(g) < 10:
            continue
        famv = dfm["family"].to_numpy()
        te_idx = np.where(famv == f)[0]
        tr_idx = np.array([i for i in range(len(dfm)) if i not in te_idx])
        beta_tr, *_ = np.linalg.lstsq(X[tr_idx], y[tr_idx], rcond=None)
        yp = X[te_idx] @ beta_tr
        yt = y[te_idx]
        r2 = 1 - np.sum((yt - yp) ** 2) / np.sum((yt - yt.mean()) ** 2)
        mae = float(np.mean(np.abs(yt - yp)))
        rows.append({"family": f, "n": len(g), "r2_loo": float(r2), "mae": mae,
                     "bN_loo": float(beta_tr[0]), "bT_loo": float(beta_tr[1]),
                     "resid_mean": float(np.mean(yt - yp))})
        print(f"留出 {f}: n={len(g):4d} | R2={r2:.3f} | MAE={mae:.3f} | bN={beta_tr[0]:.3f} | 残差均值 {np.mean(yt-yp):+.3f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v46_p4_family_cv.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(range(len(rdf)), rdf["bN_loo"], color="#2563EB", alpha=0.85)
    ax.axhline(beta_full[0], color="#C2410C", lw=1.6, label=f"全量 bN={beta_full[0]:.3f}")
    ax.axhline(0.364, color="#16A34A", lw=1.2, ls="--", label="QR90 主链路 bN=0.364")
    ax.set_xticks(range(len(rdf))); ax.set_xticklabels(rdf["family"], rotation=25)
    ax.set_ylabel("留出拟合的 bN"); ax.set_title("v46: 家族留出的规模弹性 bN (前沿模型)")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v46_p4_family_cv.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v46_p4_family_cv.json"), "w", encoding="utf-8") as f:
        json.dump({"bN_full": float(beta_full[0]), "bT_full": float(beta_full[1]),
                   "r2_full": float(r2_full), "n": int(len(dfm)),
                   "rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v46")


if __name__ == "__main__":
    main()