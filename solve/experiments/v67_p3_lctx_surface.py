# -*- coding: utf-8 -*-
"""
v67 实验: 上下文长度 x 预算的二维响应面
exp 成本形式, L_ctx in {0.5k, 1k, 2k, 4k, 8k} x 预算阶梯 1e18..1e24:
1) Q*(C) 曲线族: 更大 L_ctx 是否推迟质量通道激活/饱和 (注意力成本占比↑)?
2) 饱和预算随 L_ctx 的移动;
3) L*(C) 曲线族: 长上下文是否整体抬高损失下限路径.
输出: experiments/v67_p3_lctx_surface.csv/.json/.png
"""
import os, sys, json
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import BASE

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

ETA = 2e-4
Q0 = 0.4
BUDGETS = [1e18, 1e19, 1e20, 1e21, 1e22, 1e23, 1e24]
LCTXS = [512, 1000, 2000, 4000, 8000]


def g_cost(Q):
    return 1e7 * np.exp(6.0 * Q)


def loss_explicit(N, D, Q, p):
    E, A, a, B, b, C, g, h = p
    return E + A * N ** (-a) + B * D ** (-b) + C * (1 - Q) ** g * N ** (-h)


def total_cost(N, D, Q, lctx):
    return (6e18 * N * D
            + D * 1e9 * max(g_cost(Q) - g_cost(Q0), 0.0)
            + ETA * (N * 1e9) * (D * 1e9) * lctx)


def solve(p, Cb, lctx, n_starts=8, seed=7):
    rng = np.random.default_rng(seed)
    def obj(z):
        return loss_explicit(np.exp(z[0]), np.exp(z[1]), z[2], p)
    def cons(z):
        return Cb - total_cost(np.exp(z[0]), np.exp(z[1]), z[2], lctx)
    bounds = [(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)), (Q0, 1.0)]
    best = None
    for i in range(n_starts):
        z0 = np.array([rng.uniform(np.log(0.05), np.log(5000)),
                       rng.uniform(np.log(1), np.log(5000)),
                       rng.uniform(Q0, 0.98)])
        r = minimize(obj, z0, method="SLSQP", bounds=bounds,
                     constraints={"type": "ineq", "fun": cons},
                     options={"maxiter": 400, "ftol": 1e-12})
        if not r.success:
            continue
        N, D, Q = float(np.exp(r.x[0])), float(np.exp(r.x[1])), float(r.x[2])
        L = float(obj(r.x))
        if best is None or L < best[0]:
            best = (L, N, D, Q)
    return best


def main():
    d = json.load(open(os.path.join("solve", "results", "p2_scaling_results.json"), encoding="utf-8"))
    gl = d["generalized"]["forms"]["interaction_N"]["params"]
    p = [gl["E"], gl["A"], gl["a"], gl["B"], gl["b"], gl["C"], gl["g"], gl["h"]]
    rows = []
    for lctx in LCTXS:
        for Cb in BUDGETS:
            sol = solve(p, Cb, lctx)
            L, N, D, Q = sol
            rows.append({"lctx": lctx, "C": Cb, "L": L, "N": N, "D": D, "Q": Q})
    import pandas as pd
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v67_p3_lctx_surface.csv"), index=False, encoding="utf-8-sig")

    # 饱和预算: Q 首次 > Q0+0.005 的预算 (插值)
    sat = {}
    for lctx in LCTXS:
        g = rdf[rdf["lctx"] == lctx].sort_values("C")
        qs = g["Q"].to_numpy(); cs = g["C"].to_numpy()
        act = np.where(qs > Q0 + 0.005)[0]
        sat[lctx] = float(np.interp(np.log10(cs[act[0]]), np.log10(cs), cs)) if len(act) else float("nan")
        print(f"L_ctx={lctx}: 激活预算~{sat[lctx]:.1e} | Q(C=1e22)={g[g['C']==1e22]['Q'].iloc[0]:.3f}")
    # 轨迹首末
    for lctx in LCTXS:
        g = rdf[rdf["lctx"] == lctx].sort_values("C")
        print(f"  L_ctx={lctx}: L(1e18)={g.iloc[0]['L']:.3f} -> L(1e24)={g.iloc[-1]['L']:.3f}")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5))
    for lctx in LCTXS:
        g = rdf[rdf["lctx"] == lctx].sort_values("C")
        axes[0].plot(np.log10(g["C"]), g["Q"], marker="o", ms=3, lw=1.4, label=f"Lctx={lctx}")
        axes[1].plot(np.log10(g["C"]), g["L"], marker="o", ms=3, lw=1.4, label=f"Lctx={lctx}")
    axes[0].axhline(Q0, color="#C2410C", lw=1.0, ls="--")
    axes[0].set_xlabel("log10 预算"); axes[0].set_ylabel("Q*")
    axes[0].set_title("v67: Q*(C) 曲线族 (exp 形式)")
    axes[0].legend(fontsize=7, ncol=2); axes[0].grid(alpha=0.3)
    axes[1].set_xlabel("log10 预算"); axes[1].set_ylabel("L*")
    axes[1].set_title("v67: L*(C) 曲线族")
    axes[1].legend(fontsize=7, ncol=2); axes[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v67_p3_lctx_surface.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v67_p3_lctx_surface.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "sat_budget": sat}, f, ensure_ascii=False, indent=2)
    print("\ndone v67")


if __name__ == "__main__":
    main()