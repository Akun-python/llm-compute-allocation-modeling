# -*- coding: utf-8 -*-
"""
v4 实验: 问题三优化算法家族对比 (不被单一求解器局限)
对比:
  A) 求解器家族: SLSQP(基线) / trust-constr / differential_evolution / basinhopping
  B) 解析解核对: 纯规模情形(Q=Q0) 的 KKT 解析分配 vs 数值解
  C) p 作为联合决策变量: 在质量成本耦合下, 质量 Q 的灵敏度
  D) 帕累托前沿: L* vs C 的宽范围扫描 + 幂律拟合
输出: experiments/v4_p3_*.csv/json + 图
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import RES, FIG, BASE
from scipy.optimize import minimize, differential_evolution, basinhopping
from scipy.optimize import NonlinearConstraint

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

# 广义标度律参数 (interaction_D, 问题二拟合)
GL = {"E": 1.551497836760937, "A": 0.5340242690174833, "a": 0.2813537379269008,
      "B": 1.250801775247864, "b": 0.3101638726673506,
      "C": 0.44511211150804275, "g": 0.9905293045386531, "d": 0.044689829791678105}
ETA = 2e-4
Q0 = 0.4


def g_cost(Q, form):
    if form == "exp":
        return 1e7 * np.exp(6.0 * Q)
    if form == "power":
        return 5e9 * Q ** 4.0
    return 2e9 * np.log1p(10.0 * Q)


def loss_gen(N, D, Q):
    E, A, a, B, b, C, g, d = (GL[k] for k in ["E", "A", "a", "B", "b", "C", "g", "d"])
    return E + A * N ** (-a) + B * D ** (-b) + C * np.maximum(1 - Q, 0) ** g * D ** (-d)


def cost_total(N, D, Q, form, L_ctx):
    ct = 6e18 * N * D
    cq = D * 1e9 * max(g_cost(Q, form) - g_cost(Q0, form), 0.0)
    ca = ETA * (N * 1e9) * (D * 1e9) * L_ctx
    return ct + cq + ca


def solve_slsqp(C, form, L_ctx):
    best = None
    for seed in range(24):
        rng = np.random.default_rng(seed)
        z0 = [rng.uniform(np.log(0.01), np.log(5000)), rng.uniform(np.log(1), np.log(5000)),
              rng.uniform(Q0, 0.98)]
        def obj(z):
            lnN, lnD, Q = z
            Q = np.clip(Q, Q0, 1.0)
            return loss_gen(np.exp(lnN), np.exp(lnD), Q)
        def cons(z):
            lnN, lnD, Q = z
            return C - cost_total(np.exp(lnN), np.exp(lnD), np.clip(Q, Q0, 1.0), form, L_ctx)
        sol = minimize(obj, z0, method="SLSQP", constraints={"type": "ineq", "fun": cons},
                       bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)), (Q0, 1.0)],
                       options={"maxiter": 600, "ftol": 1e-12})
        if sol.success and (best is None or sol.fun < best[0]):
            best = (sol.fun, sol.x)
    return best


def solve_trust(C, form, L_ctx):
    best = None
    for seed in range(12):
        rng = np.random.default_rng(seed)
        z0 = [rng.uniform(np.log(0.01), np.log(5000)), rng.uniform(np.log(1), np.log(5000)),
              rng.uniform(Q0, 0.98)]
        def obj(z):
            lnN, lnD, Q = z
            return loss_gen(np.exp(lnN), np.exp(lnD), np.clip(Q, Q0, 1.0))
        nlc = NonlinearConstraint(lambda z: C - cost_total(np.exp(z[0]), np.exp(z[1]), np.clip(z[2], Q0, 1.0), form, L_ctx),
                                  -np.inf, 0.0)
        sol = minimize(obj, z0, method="trust-constr", constraints=[nlc],
                       bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)), (Q0, 1.0)],
                       options={"maxiter": 600, "gtol": 1e-10})
        if sol.success and (best is None or sol.fun < best[0]):
            best = (sol.fun, sol.x)
    return best


def solve_de(C, form, L_ctx):
    """差分进化: 全局搜索 (取对数空间)"""
    def obj(z):
        lnN, lnD, Q = z
        if C - cost_total(np.exp(lnN), np.exp(lnD), Q, form, L_ctx) < 0:
            return 1e6 + loss_gen(np.exp(lnN), np.exp(lnD), Q)
        return loss_gen(np.exp(lnN), np.exp(lnD), Q)
    sol = differential_evolution(obj, [(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)), (Q0, 1.0)],
                                 seed=3, maxiter=400, tol=1e-10, polish=True)
    return (sol.fun, sol.x) if sol.success else None


def solve_bh(C, form, L_ctx):
    """盆跳: 全局优化 (局部 SLSQP + 随机扰动)"""
    def obj(z):
        lnN, lnD, Q = z
        Q = np.clip(Q, Q0, 1.0)
        if C - cost_total(np.exp(lnN), np.exp(lnD), Q, form, L_ctx) < 0:
            return 1e6 + loss_gen(np.exp(lnN), np.exp(lnD), Q)
        return loss_gen(np.exp(lnN), np.exp(lnD), Q)
    sol = basinhopping(obj, [np.log(1), np.log(100), 0.6], niter=60, seed=3,
                       minimizer_kwargs={"method": "SLSQP",
                                         "bounds": [(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)), (Q0, 1.0)]})
    return (sol.fun, sol.x)


def kkt_pure_scale(C, L_ctx, form="power"):
    """解析解: Q=Q0 时的最优分配 (Chinchilla 式)
    目标 min E + A N^-a + B D^-b, 约束 (6 + eta L_ctx) e18 N D = C
    KKT: a A N^-a = b B D^-b (边际损失相等)  =>  N/D 比例解析"""
    E, A, a, B, b = (GL[k] for k in ["E", "A", "a", "B", "b"])
    k = 6 + ETA * L_ctx * 1e-6      # 单位: 6e18 + eta*1e18*L_ctx -> (6 + eta*1e-6*L_ctx)? 检查量纲
    # 约束: (6 + eta*L_ctx*1e-6? ) 直接用数值关系:
    # ct + ca = 6e18 ND + eta *1e9*1e9 * L_ctx * ND = (6 + eta*1e-6? ) 不, eta*(1e9)^2*L_ctx = eta*1e18*L_ctx
    # = e18 * (6 + eta*L_ctx) * N*D ; eta=2e-4 => (6 + 2e-4*L_ctx)e18
    coeff = (6.0 + ETA * L_ctx) * 1e18
    # KKT: N^-a D^-b 均衡 => N = D^{b/a} * (aA/(bB))^{1/a}
    ND_target = C / coeff
    # 数值解 N,D (对数)
    lnN, lnD = np.log(1.0), np.log(ND_target)   # 初值 D=N*D/N=ND, N=1
    def f(z):
        lnN, lnD = z
        N, D = np.exp(lnN), np.exp(lnD)
        return a * A * N ** (-a) - b * B * D ** (-b)   # =0 均衡
    from scipy.optimize import root
    sol = root(lambda z: [f(z), np.log(np.exp(z[0]) * np.exp(z[1])) - np.log(ND_target)],
               [lnN, lnD])
    N, D = np.exp(sol.x[0]), np.exp(sol.x[1])
    return {"N": N, "D": D, "L": loss_gen(N, D, Q0)}


def main():
    L_CTX = 4096
    C0 = 1e22
    form = "power"

    # ========== A: 求解器家族对比 ==========
    solvers = {"slsqp": solve_slsqp, "trust": solve_trust, "de": solve_de, "bh": solve_bh}
    rows = []
    for name, fn in solvers.items():
        try:
            r = fn(C0, form, L_CTX)
            if r:
                val, z = r
                lnN, lnD, Q = z
                rows.append({"solver": name, "L": val, "N": float(np.exp(lnN)),
                             "D": float(np.exp(lnD)), "Q": float(np.clip(Q, Q0, 1.0))})
                print(f"[{name}] L={val:.6f} N={np.exp(lnN):.4f} D={np.exp(lnD):.2f} Q={np.clip(Q,Q0,1.0):.4f}")
        except Exception as e:
            print(f"[{name}] FAILED: {e}")
    sdf = pd.DataFrame(rows)
    sdf.to_csv(os.path.join(EX, "v4_p3_solvers.csv"), index=False, encoding="utf-8-sig")
    print("\n求解器对比 (C=1e22, power):")
    print(sdf.to_string(index=False))

    # ========== B: KKT 解析解 vs 数值 (纯规模 Q=Q0) ==========
    krows = []
    for C in [1e19, 1e22, 1e24]:
        an = kkt_pure_scale(C, L_CTX)
        # 数值: 固定 Q=Q0 求规模最优
        def obj(z):
            lnN, lnD = z
            return loss_gen(np.exp(lnN), np.exp(lnD), Q0)
        def cons(z):
            return C - cost_total(np.exp(z[0]), np.exp(z[1]), Q0, form, L_CTX)
        sol = minimize(obj, [np.log(an["N"]), np.log(an["D"])], method="SLSQP",
                       constraints={"type": "ineq", "fun": cons},
                       bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5))],
                       options={"maxiter": 400, "ftol": 1e-12})
        krows.append({"C": C, "analytic_N": an["N"], "analytic_D": an["D"],
                      "num_N": float(np.exp(sol.x[0])), "num_D": float(np.exp(sol.x[1])),
                      "rel_err_N": abs(an["N"] - np.exp(sol.x[0])) / an["N"]})
        print(f"C={C:.0e}: KKT N={an['N']:.4f} D={an['D']:.2f} | 数值 N={np.exp(sol.x[0]):.4f} D={np.exp(sol.x[1]):.2f}")
    kdf = pd.DataFrame(krows)
    kdf.to_csv(os.path.join(EX, "v4_p3_kkt_check.csv"), index=False, encoding="utf-8-sig")

    # ========== C: Q 灵敏度 (固定 N,D 预算下质量的最优投入) ==========
    qrows = []
    for C in [1e19, 1e22]:
        r = solve_slsqp(C, form, L_CTX)
        if not r:
            continue
        _, z = r
        N0, D0 = np.exp(z[0]), np.exp(z[1])
        for dQ in [0.05, 0.1, 0.2, 0.3]:
            Qv = min(Q0 + dQ, 0.99)
            Lq = loss_gen(N0, D0, Qv)
            cq = D0 * 1e9 * max(g_cost(Qv, form) - g_cost(Q0, form), 0.0)
            qrows.append({"C": C, "dQ": dQ, "Q": Qv, "L_at_fixed_scale": Lq, "extra_cost": cq})
    qdf = pd.DataFrame(qrows)
    qdf.to_csv(os.path.join(EX, "v4_p3_q_sensitivity.csv"), index=False, encoding="utf-8-sig")
    print("\n质量灵敏度 (固定规模):")
    print(qdf.to_string(index=False))

    # ========== D: 帕累托前沿 L* vs C ==========
    Cgrid = np.logspace(17, 26, 91)
    frows = []
    for C in Cgrid:
        r = solve_slsqp(C, form, L_CTX)
        if r:
            val, z = r
            lnN, lnD, Q = z
            frows.append({"C": C, "L": val, "N": float(np.exp(lnN)), "D": float(np.exp(lnD)),
                          "Q": float(np.clip(Q, Q0, 1.0))})
    fdf = pd.DataFrame(frows)
    fdf.to_csv(os.path.join(EX, "v4_p3_pareto.csv"), index=False, encoding="utf-8-sig")
    # 幂律拟合 L* vs C
    mask = fdf["L"] > GL["E"] * 1.001
    beta = np.polyfit(np.log(fdf.loc[mask, "C"]), np.log(fdf.loc[mask, "L"] - GL["E"]), 1)
    print(f"\n帕累托前沿: ln(L-E) = {beta[0]:.4f} * lnC + {beta[1]:.4f}  (指数 {beta[0]:.4f})")

    # 图: 求解器对比 + 帕累托
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(fdf["C"], fdf["L"], "o-", ms=3, color="#177cb0", label="SLSQP 最优")
    for C in [1e19, 1e22, 1e24]:
        ax.axvline(C, color="#88ada6", ls="--", lw=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("预算 C (FLOPs)"); ax.set_ylabel("最优 Loss L*")
    ax.set_title("v4: 算力--性能帕累托前沿")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v4_p3_pareto.png"), dpi=200); plt.close(fig)

    with open(os.path.join(EX, "v4_p3_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"solvers": rows, "kkt": krows, "pareto_exp": float(beta[0])}, f, ensure_ascii=False, indent=2)

    print("\ndone v4 p3")


if __name__ == "__main__":
    main()
