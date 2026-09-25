# -*- coding: utf-8 -*-
"""
v73 实验: 跨框架拟合对比 —— 广义标度律参数稳定性核验 (P2)
同一数据 (B6+B7, n=810), 同一模型 (interaction_N, 8 参数), 6 个独立拟合框架:
  1) scipy least_squares TRF        (主链路引用)
  2) scipy least_squares dogbox     (信赖域狗腿变体)
  3) scipy curve_fit LM             (经典 Levenberg-Marquardt, 无边)
  4) scipy minimize L-BFGS-B        (拟牛顿, SSE)
  5) differential_evolution         (全局随机搜索, SSE)
  6) torch Adam                     (梯度下降, 投影边界, SSE)
比较: 参数估计跨框架一致性(相对极差), R2, 810 点上预测最大差异 =>
  拟合结果不依赖优化器/实现 => 参数与结论的数值稳定性.
输出: experiments/v73_p2_fit_frameworks.csv/.json/.png
"""
import os, sys, json, math
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import B, BASE

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

PNAMES = ["E", "A", "a", "B", "b", "C", "g", "h"]
NPAR = 8


def load_data():
    b6 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment.csv"))
    b7 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment_expanded.csv"))
    df = pd.concat([b6, b7]).dropna(subset=["N_params_B", "D_tokens_B", "Q_score", "val_loss"])
    return (df["N_params_B"].to_numpy(dtype=float),
            df["D_tokens_B"].to_numpy(dtype=float),
            df["Q_score"].to_numpy(dtype=float),
            df["val_loss"].to_numpy(dtype=float))


def model(p, N, D, Q):
    E, A, a, B, b, C, g, h = p
    return (E + A * N ** (-a) + B * D ** (-b)
            + C * np.maximum(1 - Q, 0) ** g * N ** (-h))


def resid(p, N, D, Q, L):
    return model(p, N, D, Q) - L


def sse(p, N, D, Q, L):
    r = resid(p, N, D, Q, L)
    return float(r @ r)


def r2(L, Lhat):
    denom = np.sum((L - L.mean()) ** 2)
    return 1 - np.sum((L - Lhat) ** 2) / denom


def bounds_for(L):
    lb = np.array([0.0, 1e-6, 1e-4, 1e-6, 1e-4, 1e-6, 1e-4, 1e-4])
    ub = np.array([L.min() * 1.2, 1e3, 5.0, 1e3, 5.0, 1e3, 10.0, 5.0])
    return lb, ub


def p0_for(L):
    return np.array([L.min() * 0.7, 3.0, 0.3, 3.0, 0.3, 1.0, 1.5, 0.3])


def main():
    N, D, Q, L = load_data()
    lb, ub = bounds_for(L)
    px0 = p0_for(L)
    from scipy.optimize import least_squares, curve_fit, minimize, differential_evolution

    # 1) TRF (主链路)
    sol = least_squares(resid, px0, args=(N, D, Q, L), bounds=(lb, ub), max_nfev=60000)
    p_trf, sse_trf = sol.x, sse(sol.x, N, D, Q, L)
    print(f"[TRF]     SSE={sse_trf:.6e} nfev={sol.nfev}")

    # 2) dogbox
    sol = least_squares(resid, px0, args=(N, D, Q, L), bounds=(lb, ub), method="dogbox", max_nfev=60000)
    p_dog, sse_dog = sol.x, sse(sol.x, N, D, Q, L)
    print(f"[dogbox]  SSE={sse_dog:.6e} nfev={sol.nfev}")

    # 3) curve_fit LM (unbounded, 经典)
    popt, _pcov = curve_fit(lambda ndq, *p: model(np.array(p), ndq[0], ndq[1], ndq[2]),
                            (N, D, Q), L, p0=px0, maxfev=60000)
    p_lm, sse_lm = np.asarray(popt), sse(np.asarray(popt), N, D, Q, L)
    print(f"[LM]      SSE={sse_lm:.6e}")

    # 4) L-BFGS-B on SSE
    res = minimize(lambda p: sse(p, N, D, Q, L), px0, method="L-BFGS-B",
                   bounds=list(zip(lb, ub)),
                   options={"maxiter": 20000, "ftol": 1e-16, "gtol": 1e-12})
    p_lbfgs, sse_lbfgs = res.x, sse(res.x, N, D, Q, L)
    print(f"[L-BFGS-B] SSE={sse_lbfgs:.6e} iters={res.nit}")

    # 5) DE (global)
    res = differential_evolution(lambda p: sse(p, N, D, Q, L), list(zip(lb, ub)),
                                 seed=11, maxiter=400, popsize=12, tol=1e-12, polish=True)
    p_de, sse_de = res.x, sse(res.x, N, D, Q, L)
    print(f"[DE]      SSE={sse_de:.6e} nfev={res.nfev}")

    # 6) torch Adam (投影边界)
    import torch
    tp = torch.tensor(px0, dtype=torch.float64, requires_grad=True)
    tN = torch.tensor(N, dtype=torch.float64)
    tD = torch.tensor(D, dtype=torch.float64)
    tQ = torch.tensor(Q, dtype=torch.float64)
    tL = torch.tensor(L, dtype=torch.float64)
    tlb, tub = torch.tensor(lb, dtype=torch.float64), torch.tensor(ub, dtype=torch.float64)
    opt = torch.optim.Adam([tp], lr=3e-2)
    best_p, best_s = None, math.inf
    for it in range(15000):
        opt.zero_grad()
        with torch.no_grad():
            tp.copy_(torch.clamp(tp, tlb, tub))
        E, A, a, B, b, C, g, h = tp
        yhat = (E + A * tN ** (-a) + B * tD ** (-b)
                + C * torch.clamp(1 - tQ, min=0) ** g * tN ** (-h))
        loss = torch.sum((yhat - tL) ** 2)
        loss.backward()
        opt.step()
        with torch.no_grad():
            if loss.item() < best_s:
                best_s = float(loss.item())
                best_p = tp.detach().numpy().copy()
    p_adam, sse_adam = best_p, best_s
    print(f"[Adam]    SSE={sse_adam:.6e}")

    runs = {"TRF": (p_trf, sse_trf), "dogbox": (p_dog, sse_dog), "LM": (p_lm, sse_lm),
            "L-BFGS-B": (p_lbfgs, sse_lbfgs), "DE": (p_de, sse_de), "Adam": (p_adam, sse_adam)}
    ref = p_trf

    rows = []
    for fw, (p, ss) in runs.items():
        rows.append({"framework": fw, "SSE": ss, "R2": r2(L, model(p, N, D, Q))})
        for i, nm in enumerate(PNAMES):
            rows[-1][nm] = float(p[i])
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v73_p2_fit_frameworks.csv"), index=False, encoding="utf-8-sig")

    # 一致性指标
    P = np.array([runs[f][0] for f in runs])
    spread = (P.max(axis=0) - P.min(axis=0)) / np.median(P, axis=0)
    preds = np.array([model(runs[f][0], N, D, Q) for f in runs])
    max_pred_diff = float(np.abs(preds.max(axis=0) - preds.min(axis=0)).max())
    print("\n参数相对极差(6框架):")
    for nm, s in zip(PNAMES, spread):
        print(f"  {nm:2s} 极差={s*100:.3e}%")
    print(f"\n预测最大跨框架差异 (810点): {max_pred_diff:.2e}")
    all_r2 = {fw: float(r2(L, model(p, N, D, Q))) for fw, (p, ss) in runs.items()}
    print(f"R2 范围: {min(all_r2.values()):.6f} ~ {max(all_r2.values()):.6f}")
    for fw, (p, ss) in runs.items():
        print(f"  {fw:8s} R2={all_r2[fw]:.6f} SSE={ss:.6e}")

    agg = {"n": int(len(L)), "form": "interaction_N",
           "param_rel_spread_pct": {nm: float(s * 100) for nm, s in zip(PNAMES, spread)},
           "max_param_spread_pct": float(spread.max() * 100),
           "max_pred_diff": max_pred_diff,
           "sse_ref": float(sse_trf),
           "r2_ref": float(r2(L, model(p_trf, N, D, Q)))}
    with open(os.path.join(EX, "v73_p2_fit_frameworks.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rdf.to_dict("records"), "agg": agg}, f, ensure_ascii=False, indent=2)

    # ---- 图: (a) 参数相对偏差 vs TRF; (b) R2 + 预测最大差 ----
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    ax = axes[0]
    x = np.arange(NPAR)
    w = 0.13
    for i, fw in enumerate(["dogbox", "LM", "L-BFGS-B", "DE", "Adam"]):
        dev = np.abs((runs[fw][0] - ref)) / np.abs(ref)
        ax.bar(x + (i - 2) * w, dev, w, color=["#1685a9", "#3eede7", "#70f3ff", "#44cef6", "#88ada6"][i],
               label=fw if i == 0 else None)
    ax.set_yscale("log")
    ax.set_xticks(x); ax.set_xticklabels(PNAMES)
    ax.set_ylabel("参数相对偏差 (vs TRF, 对数轴)")
    ax.set_title("(a) 跨框架参数估计相对偏差")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8, loc="upper left")

    ax = axes[1]
    fws = list(runs.keys())
    r2v = [r2(L, model(runs[f][0], N, D, Q)) for f in fws]
    ax.bar(fws, r2v, color=["#177cb0", "#1685a9", "#3eede7", "#70f3ff", "#44cef6", "#88ada6"])
    ax.set_ylim(0.978, 0.981)
    ax.set_ylabel("拟合 R²"); ax.set_title("(b) 各框架拟合优度")
    for i, v in enumerate(r2v):
        ax.text(i, v + 2e-5, f"{v:.5f}", ha="center", fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    ax.annotate(f"810 点预测最大跨框架差异 {max_pred_diff:.1e}", xy=(0.5, 0.90),
                xycoords="axes fraction", ha="center", fontsize=9, color="#1685a9")
    fig.suptitle("v73: 六框架跨框架拟合对比 —— 广义标度律参数稳定性核验", fontsize=12, y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(EX, "v73_p2_fit_frameworks.png"), dpi=200)
    plt.close(fig)
    print("\ndone v73")


if __name__ == "__main__":
    main()