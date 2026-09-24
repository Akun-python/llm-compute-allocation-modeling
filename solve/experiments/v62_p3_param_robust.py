# -*- coding: utf-8 -*-
"""
v62 实验: 参数不确定性下的最优解稳健性
用 v33 bootstrap CI 的端点, 在 C_budget=1e22 (exp 成本形式) 重解联合优化:
1) 关键参数 a/C/g/h 取 2.5%/中位/97.5% 的组合 (8 角点 + 中位);
2) 最优 (N*,D*,Q*,L*) 的散布 -> 最优解带;
3) 结论: 最优解对参数不确定性的敏感方向 (Q* 是否稳定, N* 带宽).
输出: experiments/v62_p3_param_robust.csv/.json/.png
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
LCTX = 1000


def g_cost(Q, form="exp"):
    if form == "exp":
        return 1e7 * np.exp(6.0 * Q)
    if form == "power":
        return 5e9 * Q ** 4
    return 2e9 * np.log1p(10.0 * Q)


def loss_explicit(N, D, Q, p):
    E, A, a, B, b, C, g, h = p
    return E + A * N ** (-a) + B * D ** (-b) + C * (1 - Q) ** g * N ** (-h)


def total_cost(N, D, Q, form):
    return (6e18 * N * D
            + D * 1e9 * max(g_cost(Q, form) - g_cost(Q0, form), 0.0)
            + ETA * (N * 1e9) * (D * 1e9) * LCTX)


def solve(p, Cb, form="exp", n_starts=12, seed=7):
    rng = np.random.default_rng(seed)

    def obj(z):
        lnN, lnD, q = z
        return loss_explicit(np.exp(lnN), np.exp(lnD), q, p)

    def cons(z):
        lnN, lnD, q = z
        return Cb - total_cost(np.exp(lnN), np.exp(lnD), q, form)

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
    ci = {r["param"]: (r["ci_lo"], r["boot_median"], r["ci_hi"])
          for r in json.load(open(os.path.join(EX, "v33_p2_boot_ci.json"), encoding="utf-8"))["rows"]}
    names = ["E", "A", "a", "B", "b", "C", "g", "h"]
    med = np.array([ci[k][1] for k in names])
    lo = np.array([ci[k][0] for k in names])
    hi = np.array([ci[k][2] for k in names])
    # 角点: 只扰动质量通道 4 参数 (a,C,g,h), 其余用中位
    keys = [0, 1, 3, 4]  # E,A,B,b 索引
    mid = med.copy()
    corners = []
    from itertools import product
    for bits in product([0, 1], repeat=4):
        p = med.copy()
        for j, b in enumerate(bits):
            idx = 2 + j  # a,C,g,h
            p[idx] = hi[idx] if b else lo[idx]
        corners.append(p)
    cases = [("lo_all", lo), ("median", med), ("hi_all", hi)] + \
            [(f"corner_{i:02d}", c) for i, c in enumerate(corners)]
    Cb = 1e22
    rows = []
    for name, p in cases:
        sol = solve(p, Cb)
        L, N, D, Q = sol
        rows.append({"case": name, "L": L, "N": N, "D": D, "Q": Q})
        print(f"{name:10s} Q*={Q:.3f} N*={N:.3f}B D*={D:.0f}B L*={L:.3f}")
    rdf = None
    import pandas as pd
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v62_p3_param_robust.csv"), index=False, encoding="utf-8-sig")
    qs = rdf["Q"].to_numpy(); ns = rdf["N"].to_numpy(); ls = rdf["L"].to_numpy()
    print(f"\nQ* 带宽 [{(qs.min()*100):.1f}, {(qs.max()*100):.1f}] (中位 {np.median(qs)*100:.1f}) | "
          f"N* 带宽 [{ns.min():.1f}, {ns.max():.1f}]B | L* 带宽 [{ls.min():.3f}, {ls.max():.3f}]")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    axes[0].scatter(qs, ns, s=40, color="#2563EB", alpha=0.8)
    axes[0].axvline(np.median(qs), color="#C2410C", lw=1.2, ls="--", label="Q* 中位")
    axes[0].set_xlabel("Q*"); axes[0].set_ylabel("N* (B)")
    axes[0].set_title("v62: 参数不确定性下的最优解 (C=1e22, exp)")
    axes[0].legend(fontsize=8); axes[0].grid(alpha=0.3)
    axes[1].bar(range(len(rdf)), ls, color="#0EA5E9", alpha=0.85)
    axes[1].set_xticks(range(len(rdf))); axes[1].set_xticklabels(rdf["case"], rotation=60, fontsize=7)
    axes[1].set_ylabel("L*"); axes[1].set_title("各参数组合的最优损失")
    axes[1].grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v62_p3_param_robust.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v62_p3_param_robust.json"), "w", encoding="utf-8") as f:
        json.dump({"C": Cb, "rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v62")


if __name__ == "__main__":
    main()