# -*- coding: utf-8 -*-
"""
v84 实验: BIC/AIC 模型选择对拟合框架的鲁棒性 (P2)
v50 的 BIC 表基于单一拟合器 (scipy least_squares TRF)。本实验把六种广义
标度律形式用 4 个独立拟合框架各拟合一遍 (相同数据 B6+B7, n=810, 相同
边界/初值):
  1) TRF      (scipy least_squares, v50 同源 => 基线数字逐位复现)
  2) L-BFGS-B (拟牛顿, SSE)
  3) DE       (差分进化全局, SSE)
  4) Adam     (torch 梯度下降, 投影边界, SSE)
判定: 在每个框架下独立做 BIC 排序, 验证:
  a) interaction_N 是否总为 BIC 最优;
  b) 次优形式的 dBIC 是否总 >10 (Burnham & Anderson 决定性证据);
  c) 完整 BIC 排序是否跨框架一致.
注: 参数个数 k 用真实形式定义 (v3 N_FORM_PARAMS, saturating=8; v50 曾以
k=7 计 saturating, 仅使该形式 BIC 偏移 ln(n)≈6.7, 不改变其>200的拒绝结论)。
输出: experiments/v84_p2_bic_framework.csv/.json/.png
"""
import os, sys, json, math
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from v3_p2_forms import load_b67, loss_forms, N_FORM_PARAMS
from common import BASE
from scipy.optimize import minimize, differential_evolution, least_squares

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

FORMS = ["additive", "interaction_D", "interaction_N", "multiplicative",
         "saturating", "exponential_Q"]
FW = ["TRF", "L-BFGS-B", "DE", "Adam"]


def init_p(npar, L):
    p0 = np.zeros(npar)
    p0[0] = L.min() * 0.7
    p0[1], p0[3] = 3.0, 3.0
    p0[2], p0[4] = 0.3, 0.3
    p0[5] = 1.0
    p0[6] = 1.5
    if npar == 8:
        p0[7] = 0.3
    return p0


def bounds_for(npar, L):
    lb = np.array([0, 1e-6, 1e-4, 1e-6, 1e-4, 1e-6, 1e-4] + [1e-4] * (npar - 7))
    ub = np.array([L.min() * 1.2, 1e3, 5, 1e3, 5, 1e3, 10] + [5.0] * (npar - 7))
    return lb, ub


def fit_trf(N, D, Q, L, form):
    npar = N_FORM_PARAMS[form]
    p0 = init_p(npar, L); lb, ub = bounds_for(npar, L)
    sol = least_squares(lambda p: loss_forms(N, D, Q, p, form) - L, p0,
                        bounds=(lb, ub), max_nfev=120000)
    return sol.x


def fit_lbfgsb(N, D, Q, L, form):
    npar = N_FORM_PARAMS[form]
    p0 = init_p(npar, L); lb, ub = bounds_for(npar, L)
    res = minimize(lambda p: float(np.sum((loss_forms(N, D, Q, p, form) - L) ** 2)),
                   p0, method="L-BFGS-B", bounds=list(zip(lb, ub)),
                   options={"maxiter": 30000, "ftol": 1e-16, "gtol": 1e-12})
    return res.x


def fit_de(N, D, Q, L, form):
    npar = N_FORM_PARAMS[form]
    lb, ub = bounds_for(npar, L)
    res = differential_evolution(
        lambda p: float(np.sum((loss_forms(N, D, Q, p, form) - L) ** 2)),
        list(zip(lb, ub)), seed=11, maxiter=500, popsize=14, tol=1e-12, polish=True)
    return res.x


def fit_adam(N, D, Q, L, form, iters=12000):
    import torch
    npar = N_FORM_PARAMS[form]
    p0 = init_p(npar, L); lb, ub = bounds_for(npar, L)
    tp = torch.tensor(p0, dtype=torch.float64, requires_grad=True)
    tN = torch.tensor(N, dtype=torch.float64); tD = torch.tensor(D, dtype=torch.float64)
    tQ = torch.tensor(Q, dtype=torch.float64); tL = torch.tensor(L, dtype=torch.float64)
    tlb, tub = torch.tensor(lb, dtype=torch.float64), torch.tensor(ub, dtype=torch.float64)
    opt = torch.optim.Adam([tp], lr=3e-2)
    best_p, best_s = None, math.inf
    for _ in range(iters):
        opt.zero_grad()
        with torch.no_grad():
            tp.copy_(torch.clamp(tp, tlb, tub))
        p = tp
        if form == "additive":
            E, A, a, B, b, C, g = p
            yhat = E + A * tN ** (-a) + B * tD ** (-b) + C * torch.clamp(1 - tQ, min=0) ** g
        elif form == "interaction_D":
            E, A, a, B, b, C, g, d = p
            yhat = (E + A * tN ** (-a) + B * tD ** (-b)
                    + C * torch.clamp(1 - tQ, min=0) ** g * tD ** (-d))
        elif form == "interaction_N":
            E, A, a, B, b, C, g, h = p
            yhat = (E + A * tN ** (-a) + B * tD ** (-b)
                    + C * torch.clamp(1 - tQ, min=0) ** g * tN ** (-h))
        elif form == "multiplicative":
            E, A, a, B, b, C, g = p
            yhat = E + (A * tN ** (-a) + B * tD ** (-b)) * (1 + C * torch.clamp(1 - tQ, min=0) ** g)
        elif form == "saturating":
            E, A, a, B, b, C, g, s = p
            yhat = (E + A * tN ** (-a) + B * tD ** (-b)
                    + C * (torch.clamp(1 - tQ, min=0) / (s + torch.clamp(1 - tQ, min=0))) ** g)
        else:  # exponential_Q
            E, A, a, B, b, C, g = p
            yhat = E + A * tN ** (-a) + B * tD ** (-b) + C * torch.exp(-g * tQ)
        loss = torch.sum((yhat - tL) ** 2)
        loss.backward()
        opt.step()
        with torch.no_grad():
            if loss.item() < best_s:
                best_s = float(loss.item())
                best_p = tp.detach().numpy().copy()
    return best_p


FITTERS = {"TRF": fit_trf, "L-BFGS-B": fit_lbfgsb, "DE": fit_de, "Adam": fit_adam}


def main():
    df = load_b67().dropna(subset=["N_params_B", "D_tokens_B", "Q_score", "val_loss"])
    N = df["N_params_B"].to_numpy(dtype=float)
    D = df["D_tokens_B"].to_numpy(dtype=float)
    Q = df["Q_score"].to_numpy(dtype=float)
    L = df["val_loss"].to_numpy(dtype=float)
    n = len(L)
    print("n =", n)

    rows = []
    for fw in FW:
        for form in FORMS:
            p = FITTERS[fw](N, D, Q, L, form)
            Lp = loss_forms(N, D, Q, p, form)
            rss = float(np.sum((L - Lp) ** 2))
            k = N_FORM_PARAMS[form]
            bic = n * np.log(rss / n) + k * np.log(n)
            aic = n * np.log(rss / n) + 2 * k
            r2 = 1 - rss / float(np.sum((L - L.mean()) ** 2))
            rows.append({"framework": fw, "form": form, "k": k, "r2": r2, "rss": rss,
                         "bic": bic, "aic": aic})
            print(f"{fw:9s} {form:16s} k={k} R2={r2:.5f} BIC={bic:.2f}")

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v84_p2_bic_framework.csv"), index=False, encoding="utf-8-sig")

    # 每框架内排序与 dBIC
    summary = []
    for fw in FW:
        sub = rdf[rdf["framework"] == fw].sort_values("bic").reset_index(drop=True)
        sub["dBIC"] = sub["bic"] - sub["bic"].min()
        sub["dBIC_thresh"] = sub["dBIC"] > 10  # 决定性证据阈值
        best = sub.iloc[0]["form"]
        second = sub.iloc[1]["form"]; second_d = float(sub.iloc[1]["dBIC"])
        rank_str = " > ".join(sub["form"].tolist())
        summary.append({"framework": fw, "best": best, "second": second,
                        "second_dBIC": round(second_d, 2),
                        "best_bic": float(sub.iloc[0]["bic"]),
                        "ranking": rank_str})
        print(f"\n[{fw}] BIC 最优: {best}; 次优 {second} dBIC={second_d:.2f} "
              f"({'决定性' if second_d > 10 else '不足'})")
        print("  排序:", rank_str)

    sdf = pd.DataFrame(summary)
    sdf.to_csv(os.path.join(EX, "v84_p2_bic_framework_summary.csv"), index=False, encoding="utf-8-sig")
    all_best = set(sdf["best"])
    all_dec = bool((sdf["second_dBIC"] > 10).all())
    print(f"\n跨框架最优完全一致: {all_best == {'interaction_N'}} "
          f"({all_best}); 所有框架次优 dBIC>10: {all_dec}; "
          f"次优 dBIC 范围: {sdf['second_dBIC'].min():.2f} ~ {sdf['second_dBIC'].max():.2f}")

    json.dump({"n": int(n), "summary": summary,
               "all_best_interaction_N": all_best == {"interaction_N"},
               "all_second_dec": bool(all_dec),
               "second_dBIC_range": [float(sdf["second_dBIC"].min()), float(sdf["second_dBIC"].max())]},
              open(os.path.join(EX, "v84_p2_bic_framework.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 图: 每框架 dBIC 条形 (按 interaction_N 为基准)
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.4), sharey=True)
    for ax, fw in zip(axes, FW):
        sub = rdf[rdf["framework"] == fw]
        bic = sub.set_index("form")["bic"]
        d = bic - bic.min()
        order = sub.sort_values("bic")["form"].tolist()
        vals = [d[f] for f in order]
        colors = ["#177cb0" if f == "interaction_N" else "#88ada6" for f in order]
        ax.barh(range(len(order))[::-1], vals, color=colors)
        ax.set_yticks(range(len(order))[::-1]); ax.set_yticklabels(order, fontsize=8)
        ax.set_title(fw, fontsize=10)
        ax.set_xlabel("dBIC")
        for i, v in enumerate(vals):
            ax.text(v + 2, i, f"{v:.1f}", fontsize=7, va="center")
        ax.axvline(10, color="#1685a9", lw=1, ls="--")
        ax.set_xlim(0, max(vals) * 1.15)
    ax.text(0.0, -1.6, "虚线=ΔBIC 10 (决定性证据阈值)", transform=axes[0].transAxes, fontsize=8, color="#1685a9")
    fig.suptitle("BIC 模型选择对拟合框架的鲁棒性 (六形式 × 四框架)", fontsize=12, y=1.02)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(os.path.join(EX, "v84_p2_bic_framework.png"), dpi=200)
    plt.close(fig)
    print("\ndone v84")


if __name__ == "__main__":
    main()