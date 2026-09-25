# -*- coding: utf-8 -*-
"""
v5 实验: 问题四前沿预测方法家族对比 (不被单一框架局限)
对比:
  A) 前沿回归家族: 分位数0.9(基线) / 分位数0.95 / Huber稳健 / OLS / 分段线性(断点)
  B) 前沿函数族: 线性 log-log(基线) / 二次 / 对数饱和
  C) 预测区间家族: 自助(基线) / 共形预测(保距) / 正态近似
  D) Loss-Benchmark 桥接家族: logit-log(基线) / 线性 / 幂 / 分箱平均
输出: experiments/v5_p4_*.csv/json + 图
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, RES, FIG, BASE

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

from scipy.optimize import minimize


def quantile_fit(X, y, tau=0.9):
    """分位数回归: IRLS (WLS 加权用 sqrt(w) 缩放, 正确实现)"""
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    for _ in range(100):
        resid = y - X @ beta
        w = np.where(resid > 0, tau, 1 - tau)
        sw = np.sqrt(w)
        beta_new = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
        if np.max(np.abs(beta_new - beta)) < 1e-9:
            beta = beta_new
            break
        beta = beta_new
    return beta


def huber_fit(X, y, delta=1.345):
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    for _ in range(80):
        r = y - X @ beta
        w = np.where(np.abs(r) <= delta, 1.0, delta / np.maximum(np.abs(r), 1e-12))
        beta = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)[0]
    return beta


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    ep = pd.read_csv(os.path.join(C, "epoch_all_ai_models.csv"))
    bridge = pd.read_csv(os.path.join(C, "loss_benchmark_bridge_expanded.csv"))

    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb["year"] = lb["date"].dt.year
    lb["t"] = lb["date"].dt.year + (lb["date"].dt.dayofyear / 365.25)
    lb["is_open"] = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[lb["is_open"] & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) & lb["year"].notna()]
    dfm = dfm[dfm["year"] >= 2022]
    dfm = dfm.copy()
    dfm["lnS"] = np.log(dfm["Average ⬆️"])
    dfm["lnN"] = np.log(dfm["#Params (B)"])
    dfm["tt"] = dfm["t"] - 2022.0
    print("open frontier sample:", dfm.shape)

    # ========== A: 前沿回归家族 (双时间编码: 整数年 vs 小数年) ==========
    y = dfm["lnS"].to_numpy()
    X_i = np.column_stack([np.ones(len(dfm)), dfm["lnN"], dfm["year"] - 2022.0])   # 主编码(整数年)
    X_f = np.column_stack([np.ones(len(dfm)), dfm["lnN"], dfm["tt"]])              # 小数年
    rows = []
    for tname, X in [("int_year", X_i), ("frac_year", X_f)]:
        for name, fn, tau in [("qr90", quantile_fit, 0.9), ("qr95", quantile_fit, 0.95),
                              ("qr80", quantile_fit, 0.8), ("huber", huber_fit, None),
                              ("ols", lambda X, y: np.linalg.lstsq(X, y, rcond=None)[0], None)]:
            b = fn(X, y)
            resid = y - X @ b
            rows.append({"tcode": tname, "family": name, "bN": float(b[1]), "bT": float(b[2]),
                         "frontier_resid_p90": float(np.percentile(resid, 90)),
                         "rmse": float(np.sqrt(np.mean(resid ** 2)))})
    fam = pd.DataFrame(rows)
    fam.to_csv(os.path.join(EX, "v5_p4_reg_families.csv"), index=False, encoding="utf-8-sig")
    print("\n回归家族对比 (整数年 vs 小数年):")
    print(fam.to_string(index=False))
    # 主口径 qr90 (整数年) 与前版比较: 若 bT 显著不同 => 主报告数字需复核
    r_int = fam[(fam["tcode"] == "int_year") & (fam["family"] == "qr90")].iloc[0]
    print(f"\n[校验] 整数年 qr90: bN={r_int['bN']:.4f} bT={r_int['bT']:.4f} "
          f"(主报告: bN=0.319 bT=0.0914)")

    # ========== B: 前沿函数族 (对数时间+平方+饱和) ==========
    X = X_i
    fn_curves = {}
    X2 = np.column_stack([np.ones(len(dfm)), dfm["lnN"], dfm["tt"], dfm["tt"] ** 2])
    b2 = quantile_fit(X2, y, 0.9)
    def pred_quad(lnN, tt):
        return b2[0] + b2[1] * lnN + b2[2] * tt + b2[3] * tt ** 2
    # 对数饱和: lnS = c + bN lnN + bT ln(1+t)
    X3 = np.column_stack([np.ones(len(dfm)), dfm["lnN"], np.log1p(dfm["tt"])])
    b3 = quantile_fit(X3, y, 0.9)
    def pred_logt(lnN, tt):
        return b3[0] + b3[1] * lnN + b3[2] * np.log1p(tt)
    rows2 = []
    for name, pred, b in [("linear", lambda lnN, tt: b2[0] + b2[1]*lnN + b2[2]*tt, b2[:3]),
                          ("quad", pred_quad, b2), ("logt", pred_logt, b3)]:
        resid = y - pred(dfm["lnN"].to_numpy(), dfm["tt"].to_numpy())
        rows2.append({"curve": name, "frontier_resid_p90": float(np.percentile(resid, 90)),
                      "rmse": float(np.sqrt(np.mean(resid ** 2)))})
    fdf = pd.DataFrame(rows2)
    fdf.to_csv(os.path.join(EX, "v5_p4_curves.csv"), index=False, encoding="utf-8-sig")
    print("\n函数族对比:")
    print(fdf.to_string(index=False))

    # ========== C: 预测区间家族 ==========
    # 共形预测 (保距): 在训练残差上取 (1-alpha) 分位作为校准带宽
    b = quantile_fit(X, y, 0.9)
    resid = y - X @ b
    alpha = 0.1
    calib = np.abs(resid - np.median(resid))
    q_cal = np.quantile(calib, 1 - alpha)
    # 自助 (基线)
    rng = np.random.default_rng(42)
    nboot = 500
    t_h = 2025 + 24 / 12
    # 基准点: 2025 分位数前沿
    lnN_90 = float(dfm[dfm["year"] == 2025]["lnN"].quantile(0.9))
    S_now = float(np.exp(b[0] + b[1] * lnN_90 + b[2] * 3))
    gN = 1.251
    paths = []
    for _ in range(nboot):
        lnS = b[0] + b[1] * (lnN_90 + gN * 2) + b[2] * (t_h - 2022) + rng.normal(0, np.std(resid))
        paths.append(np.exp(lnS))
    paths = np.array(paths)
    boot_lo, boot_hi = np.percentile(paths, [10, 90])
    # 共形
    lnS_hat = b[0] + b[1] * (lnN_90 + gN * 2) + b[2] * (t_h - 2022)
    S_hat = np.exp(lnS_hat)
    conf_lo, conf_hi = np.exp(lnS_hat - q_cal), np.exp(lnS_hat + q_cal)
    # 正态近似
    sigma = np.std(resid) * (1 + 0.2 * 2)
    norm_lo, norm_hi = np.exp(lnS_hat - 1.645 * sigma), np.exp(lnS_hat + 1.645 * sigma)
    pred_rows = [{"method": "bootstrap", "lo": boot_lo, "hi": boot_hi, "mid": float(np.median(paths))},
                 {"method": "conformal", "lo": conf_lo, "hi": conf_hi, "mid": S_hat},
                 {"method": "normal", "lo": norm_lo, "hi": norm_hi, "mid": S_hat}]
    pdf = pd.DataFrame(pred_rows)
    pdf.to_csv(os.path.join(EX, "v5_p4_intervals.csv"), index=False, encoding="utf-8-sig")
    print("\n24 个月预测区间家族:")
    print(pdf.round(2).to_string(index=False))

    # ========== D: 桥接家族 ==========
    br = bridge[bridge["Val_Loss"] > 0].copy()
    br["A"] = br["LB_Average"].clip(1.0, 99.0) / 100.0
    br["logitA"] = np.log(br["A"] / (1 - br["A"]))
    br["lnLoss"] = np.log(br["Val_Loss"])
    rows3 = []
    # logit-log (基线)
    Xb = np.column_stack([np.ones(len(br)), br["lnLoss"]])
    bb = np.linalg.lstsq(Xb, br["logitA"], rcond=None)[0]
    r = br["logitA"] - Xb @ bb
    rows3.append({"bridge": "logit-log", "r2": 1 - r.var() / br["logitA"].var()})
    # 线性 Loss->A
    Xb2 = np.column_stack([np.ones(len(br)), br["Val_Loss"]])
    bb2 = np.linalg.lstsq(Xb2, br["LB_Average"], rcond=None)[0]
    r2 = br["LB_Average"] - Xb2 @ bb2
    rows3.append({"bridge": "linear", "r2": 1 - r2.var() / br["LB_Average"].var()})
    # 幂: A = a*L^b
    Xb3 = np.column_stack([np.ones(len(br)), br["lnLoss"]])
    bb3 = np.linalg.lstsq(Xb3, np.log(br["LB_Average"].clip(1e-9, None)), rcond=None)[0]
    r3 = np.log(br["LB_Average"].clip(1e-9, None)) - Xb3 @ bb3
    rows3.append({"bridge": "power", "r2": 1 - r3.var() / np.log(br["LB_Average"].clip(1e-9)).var()})
    bdf = pd.DataFrame(rows3)
    bdf.to_csv(os.path.join(EX, "v5_p4_bridges.csv"), index=False, encoding="utf-8-sig")
    print("\n桥接家族对比:")
    print(bdf.to_string(index=False))

    # 图: 区间对比
    fig, ax = plt.subplots(figsize=(8, 5))
    xs = np.arange(len(pdf))
    ax.errorbar(xs, pdf["mid"], yerr=[pdf["mid"] - pdf["lo"], pdf["hi"] - pdf["mid"]],
                fmt="o", capsize=4, ms=6)
    for i, r in pdf.iterrows():
        ax.text(i, r["hi"] + 3, f"{r['mid']:.0f} [{r['lo']:.0f},{r['hi']:.0f}]", ha="center", fontsize=8)
    ax.set_xticks(xs); ax.set_xticklabels(pdf["method"])
    ax.set_ylabel("24 个月前沿预测 (Average)")
    ax.set_title("v5: 预测区间家族对比")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v5_p4_intervals.png"), dpi=200); plt.close(fig)

    print("\ndone v5 p4")


if __name__ == "__main__":
    main()
