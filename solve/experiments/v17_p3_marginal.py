# -*- coding: utf-8 -*-
"""
v17 实验: 三通道预算分配的边际价值分析 (问题三收官验证)
1) 在全局最优分配 (C=1e22, power, L_ctx=4096) 处, 把预算从通道 i 移 δ 到
   通道 j 后重优化, 得两两边际流失值矩阵——若最优在 simplex 内部, 对角线
   外全部为正 (任何单向转移 L 都增大).
2) "最后一美元": 总预算 +5% 且只能投给单一通道时, 各通道可回收的损失
   改善 vs 整体最优投放 — 给出追加预算投放优先级.
3) 12x12 分配 simplex 响应面 (s_train x s_Q) 等高线 + 最优分配点.
输出: experiments/v17_p3_marginal.csv/.json + 响应面图
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import (loss_generalized, cost_terms, solve_opt, G_FORMS,
                             Q0, ETA)
from scipy.optimize import minimize

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from common import BASE
for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def solve_alloc(C, s_train, s_Q, form, L_ctx, Q0v=Q0):
    """给定三通道预算份额, 求最小 L; s_attn = 1 - s_train - s_Q"""
    s_attn = 1.0 - s_train - s_Q
    if min(s_train, s_Q, s_attn) <= 0:
        return None
    cap_t, cap_q, cap_a = s_train * C, s_Q * C, s_attn * C

    def obj(z):
        lnN, lnD, Q = z
        return loss_generalized(np.exp(lnN), np.exp(lnD), np.clip(Q, Q0v, 1.0))

    def cons(z):
        lnN, lnD, Q = z
        ct, cq, ca = cost_terms(np.exp(lnN), np.exp(lnD), np.clip(Q, Q0v, 1.0), form, L_ctx)
        return np.array([cap_t - ct, cap_q - cq, cap_a - ca])

    best = None
    for seed in range(20):
        rng = np.random.default_rng(seed)
        z0 = np.array([rng.uniform(np.log(0.02), np.log(500)),
                       rng.uniform(np.log(0.5), np.log(2000)),
                       rng.uniform(Q0v, 0.98)])
        sol = minimize(obj, z0, method="SLSQP",
                       constraints={"type": "ineq", "fun": cons},
                       bounds=[(np.log(0.005), np.log(1e5)),
                               (np.log(0.2), np.log(1e5)), (Q0v, 1.0)],
                       options={"maxiter": 500, "ftol": 1e-12})
        if sol.success:
            val = obj(sol.x)
            if best is None or val < best[0]:
                best = (val, sol.x)
    if best is None:
        return None
    val, z = best
    N, D, Q = np.exp(z[0]), np.exp(z[1]), np.clip(z[2], Q0v, 1.0)
    ct, cq, ca = cost_terms(N, D, Q, form, L_ctx)
    return {"L": val, "N": N, "D": D, "Q": Q,
            "ct": ct, "cq": cq, "ca": ca, "s": (ct / C, cq / C, ca / C)}


def main():
    results = {}
    for C, form in [(1e19, "exp"), (1e22, "power"), (1e24, "power")]:
        L_ctx = 4096
        opt = solve_opt(C, form, L_ctx)
        if opt is None:
            print(f"C={C:.0e} {form}: baseline failed, skip")
            continue
        L0 = opt["L"]
        s = (opt["C_train"] / C, opt["C_Q"] / C, opt["C_attn"] / C)
        print(f"\n== C={C:.0e} {form} == 全局最优 L0={L0:.5f} "
              f"份额 s=(train={s[0]:.3f}, Q={s[1]:.3f}, attn={s[2]:.3f})")
        names = ["train", "Q", "attn"]

        # 1) 两两转移边际矩阵 (移 0.5% 总预算)
        delta = 0.005
        M = np.zeros((3, 3))
        for i in range(3):
            for j in range(3):
                if i == j:
                    continue
                ss = list(s)
                ss[i] -= delta
                ss[j] += delta
                r = solve_alloc(C, ss[0], ss[1], form, L_ctx)
                M[i, j] = (r["L"] - L0) / delta if r else np.nan
        offdiag = M[(~np.eye(3, dtype=bool)) & ~np.isnan(M)]
        diag_note = "OK" if (offdiag > 0).all() else "WARN"
        print(f"转移边际矩阵 (每移1%%): {np.round(M, 4).tolist()}  [{diag_note}]")

        # 2) 追加 +5% 预算单通道投放 vs 整体最优
        C5 = 1.05 * C
        opt5 = solve_opt(C5, form, L_ctx)
        dL_best = (L0 - opt5["L"]) if opt5 else np.nan
        rows = []
        for i, name in enumerate(names):
            ss = list(s)
            ss[i] = (ss[i] * C + 0.05 * C) / C5
            for k in range(3):
                if k != i:
                    ss[k] = ss[k] * C / C5
            r = solve_alloc(C5, ss[0], ss[1], form, L_ctx)
            if r:
                rows.append({"channel": name, "L_reopt": r["L"],
                             "dL_improve": L0 - r["L"],
                             "share_of_best": (L0 - r["L"]) / dL_best if dL_best > 0 else np.nan})
        print(f"+5%%单通道 (整体最优可改善 {dL_best:.4f}): "
              f"{[(r['channel'], round(r['dL_improve'],5), None if np.isnan(r['share_of_best']) else round(r['share_of_best'],3)) for r in rows]}")

        results[f"{C:.0e}_{form}"] = {"L0": L0, "shares": {"train": s[0], "Q": s[1], "attn": s[2]},
                                      "marginal_matrix": M.tolist(), "note": diag_note,
                                      "plus5": rows, "dL_best_overall": float(dL_best)}

        # 3) 响应面只画一次 (C=1e22 power)
        if C == 1e22 and form == "power":
            grid = np.linspace(0.35, 0.95, 13)
            gq = np.linspace(0.02, 0.30, 13)
            Z = np.full((len(grid), len(gq)), np.nan)
            for a, st in enumerate(grid):
                for b, sq in enumerate(gq):
                    if sq + st > 0.97:
                        continue
                    r = solve_alloc(C, st, sq, form, L_ctx)
                    if r:
                        Z[a, b] = r["L"]
            fig, ax = plt.subplots(figsize=(8, 6))
            c = ax.contourf(gq, grid, Z, levels=18, cmap="YlOrRd")
            ax.contour(gq, grid, Z, levels=10, colors="k", linewidths=0.4, alpha=0.5)
            ax.set_xlabel("质量通道份额 s_Q"); ax.set_ylabel("训练通道份额 s_train")
            ax.plot(s[1], s[0], "o", ms=12, color="#2563EB", mec="white", mew=2, label="全局最优分配")
            cb = fig.colorbar(c, ax=ax); cb.set_label("最小损失 L*")
            ax.set_title("v17: 三通道分配响应面 (C=1e22, power)")
            ax.legend(fontsize=9)
            fig.tight_layout(); fig.savefig(os.path.join(EX, "v17_p3_simplex.png"), dpi=200)
            plt.close(fig)

    with open(os.path.join(EX, "v17_p3_marginal.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\ndone v17")


if __name__ == "__main__":
    main()