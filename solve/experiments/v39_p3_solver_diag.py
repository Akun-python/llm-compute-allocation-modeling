# -*- coding: utf-8 -*-
"""
v39 实验: 求解器多初值诊断 (SLSQP 24 初值解族散布)
对三档预算 (1e19/1e22/1e24, power) 显式跑 24 个随机初值 SLSQP,
记录每初值达到的目标 L:
1) 最优/中位/最差与散布 (max-min)/best;
2) 收敛成功率: 落在最优 L 的 1% 邻域内的初值比例;
3) 与 solve_opt (取最优) 的一致性.
结论: 多初值策略是否真正稳健 (高成功率 => 主链路结果不依赖初值).
输出: experiments/v39_p3_solver_diag.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import loss_generalized, cost_terms, solve_opt, Q0
from common import BASE
from scipy.optimize import minimize

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

SEEDS = 24


def run_one(C, form, seed):
    rng = np.random.default_rng(seed)

    def obj(z):
        lnN, lnD, lnQ = z
        return loss_generalized(np.exp(lnN), np.exp(lnD), np.exp(lnQ))

    def cons(z):
        lnN, lnD, lnQ = z
        ct, cq, ca = cost_terms(np.exp(lnN), np.exp(lnD), np.exp(lnQ), form, 4096)
        return C - (ct + cq + ca)
    z0 = np.array([rng.uniform(np.log(0.01), np.log(5000)),
                   rng.uniform(np.log(1), np.log(5000)),
                   rng.uniform(np.log(Q0 + 1e-6), np.log(1.0))])
    sol = minimize(obj, z0, method="SLSQP", constraints={"type": "ineq", "fun": cons},
                   bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)),
                           (np.log(Q0 + 1e-6), 0.0)],
                   options={"maxiter": 500, "ftol": 1e-12})
    if not sol.success:
        return np.inf
    return float(obj(sol.x))


def main():
    rows = []
    for C, form in [(1e19, "power"), (1e22, "power"), (1e24, "power")]:
        Ls = np.array([run_one(C, form, s) for s in range(SEEDS)])
        Ls = Ls[np.isfinite(Ls)]
        best = Ls.min()
        j = solve_opt(C, form, 4096)
        spread = (Ls.max() - Ls.min()) / best
        in1pct = (Ls <= best * 1.01).mean()
        rows.append({"C": C, "form": form, "n_success": int(len(Ls)),
                     "L_best": float(best), "L_median": float(np.median(Ls)),
                     "L_worst": float(Ls.max()), "spread_pct": float(spread * 100),
                     "in1pct_frac": float(in1pct),
                     "L_solve_opt": float(j["L"])})
        print(f"C={C:.0e} {form}: best {best:.4f} (solve_opt {j['L']:.4f}) | "
              f"中位 {np.median(Ls):.4f} 最差 {Ls.max():.4f} | "
              f"散布 {spread*100:.1f}% | 1%邻域成功率 {in1pct*100:.0f}%")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v39_p3_solver_diag.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    x = np.arange(len(rdf))
    w = 0.28
    ax.bar(x - w, rdf["L_best"], w, color="#177cb0", label="24 初值最优")
    ax.bar(x, rdf["L_median"], w, color="#70f3ff", label="中位")
    ax.bar(x + w, rdf["L_worst"], w, color="#88ada6", label="最差")
    ax.set_xticks(x); ax.set_xticklabels([f"{int(r['C']):.0e}" for _, r in rdf.iterrows()])
    ax.set_ylabel("目标 L"); ax.set_title("v39: SLSQP 24 初值解族散布 (power)")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v39_p3_solver_diag.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v39_p3_solver_diag.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("\ndone v39")


if __name__ == "__main__":
    main()