# -*- coding: utf-8 -*-
"""
v9 实验: 上下文长度内生化的联合优化
创新点: C7 数据 (model_architecture_metadata.csv, 40 模型) 表明上下文长度与
能力显著正相关 (Spearman 0.51, p<0.001). 将 L_ctx 从外生参数提升为决策变量:
    min L(N,D,Q) - w * R(L_ctx)   (R 为上下文能力收益, 从数据拟合)
    s.t. 6ND + D[g(Q)-g(Q0)]_+ + eta*N*D*L_ctx <= C,  L_ctx ∈ [512, 131072]
回答: 算力约束下最优上下文长度是多少? 与固定 4096 相比的增益?
输出: experiments/v9_*.csv + 图
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, RES, FIG, BASE
from scipy.optimize import minimize
from scipy.stats import spearmanr

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

_p2 = os.path.join(RES, "p2_scaling_results.json")
_g = json.load(open(_p2, encoding="utf-8"))["generalized"]
pg = {k: float(v) for k, v in _g["forms"][_g["chosen"]]["params"].items()}
E_, A_, a_, B_, b_, C_, g_, h_ = (pg[k] for k in ["E", "A", "a", "B", "b", "C", "g", "h"])


def g_cost(Q, form="power"):
    return 5e9 * Q ** 4.0


def loss_gen(N, D, Q):
    return (E_ + A_ * N ** (-a_) + B_ * D ** (-b_)
            + C_ * np.maximum(1 - Q, 0) ** g_ * N ** (-h_))


def cost_total(N, D, Q, L_ctx):
    ct = 6e18 * N * D
    cq = D * 1e9 * max(g_cost(Q) - g_cost(Q0), 0.0)
    ca = ETA * (N * 1e9) * (D * 1e9) * L_ctx
    return ct + cq + ca


def fit_context_benefit():
    """从 C7 元数据拟合上下文收益 R(L): log(S) ~ bN ln(N) + bL ln(L)"""
    m = pd.read_csv(os.path.join(C, "model_architecture_metadata.csv"))
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    df = m.merge(lb, left_on="model_name", right_on="Model", how="inner")
    df = df[(df["max_position_embeddings"] > 0) & (df["Average ⬆️"] > 0)]
    X = np.column_stack([np.ones(len(df)), np.log(df["#Params (B)"]), np.log(df["max_position_embeddings"])])
    y = np.log(df["Average ⬆️"])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r2 = 1 - np.sum((y - X @ b) ** 2) / np.sum((y - y.mean()) ** 2)
    print("上下文收益拟合: lnS = %.3f + %.3f lnN + %.3f lnL  (n=%d, R2=%.3f)"
          % (b[0], b[1], b[2], len(df), r2))
    return {"bN": float(b[1]), "bL": float(b[2]), "n": len(df), "r2": float(r2),
            "spearman": float(spearmanr(df["max_position_embeddings"], df["Average ⬆️"]).statistic)}


def main():
    rb = fit_context_benefit()

    def R_ctx(L):
        return rb["bL"] * np.log(L)  # 相对收益项 (无常数不影响优化)

    print("\n=== A: 三档预算下联合优化 (w=1: 上下文收益权重) ===")
    budgets = [1e19, 1e22, 1e24]
    rows = []
    for C in budgets:
        best = None
        for seed in range(24):
            rng = np.random.default_rng(seed)
            z0 = [rng.uniform(np.log(0.01), np.log(5000)),
                  rng.uniform(np.log(1), np.log(5000)),
                  rng.uniform(Q0, 0.98),
                  rng.uniform(np.log(1024), np.log(65536))]

            def obj(z, C=C):
                lnN, lnD, Q, lnL = z
                N, D, Q, L = np.exp(lnN), np.exp(lnD), np.clip(Q, Q0, 1.0), np.clip(np.exp(lnL), 512, 131072)
                return loss_gen(N, D, Q) - R_ctx(L)

            def cons(z):
                lnN, lnD, Q, lnL = z
                N, D, Q, L = np.exp(lnN), np.exp(lnD), np.clip(Q, Q0, 1.0), np.clip(np.exp(lnL), 512, 131072)
                return C - loss_tot0(N, D, Q, L)

            sol = minimize(obj, z0, method="SLSQP", constraints={"type": "ineq", "fun": cons},
                           bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)),
                                   (Q0, 1.0), (np.log(512), np.log(131072))],
                           options={"maxiter": 800, "ftol": 1e-12})
            if sol.success and (best is None or sol.fun < best[0]):
                best = (sol.fun, sol.x)
        L, z = best
        N, D, Q, Lc = np.exp(z[0]), np.exp(z[1]), np.clip(z[2], Q0, 1.0), np.clip(np.exp(z[3]), 512, 131072)
        ct, cq, ca = (6e18 * N * D, D * 1e9 * max(g_cost(Q) - g_cost(Q0), 0.0),
                      ETA * N * 1e9 * D * 1e9 * Lc)
        rows.append({"C": C, "N": float(N), "D": float(D), "Q": float(Q),
                     "L_ctx_opt": float(Lc), "L_loss": float(loss_gen(N, D, Q)),
                     "s_train": ct / C, "s_Q": cq / C, "s_attn": ca / C})
        print(f"C={C:.0e}: N={N:.3f} D={D:.1f} Q={Q:.3f} L_ctx*={Lc:.0f} "
              f"L_loss={loss_gen(N, D, Q):.4f} s_attn={ca / C:.3f}")

    # === B: w 敏感性 (C=1e22): 上下文收益权重越大 -> 最长上下文越优? ===
    print("\n=== B: w 敏感性 (C=1e22) ===")
    w_rows = []
    for w in [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]:
        C = 1e22
        best = None
        for seed in range(24):
            rng = np.random.default_rng(seed)
            z0 = [rng.uniform(np.log(0.01), np.log(5000)),
                  rng.uniform(np.log(1), np.log(5000)),
                  rng.uniform(Q0, 0.98),
                  rng.uniform(np.log(1024), np.log(65536))]

            def obj(z, C=C, w=w):
                lnN, lnD, Q, lnL = z
                N, D, Q, L = np.exp(lnN), np.exp(lnD), np.clip(Q, Q0, 1.0), np.clip(np.exp(lnL), 512, 131072)
                return loss_gen(N, D, Q) - w * R_ctx(L)

            def cons(z):
                lnN, lnD, Q, lnL = z
                N, D, Q, L = np.exp(lnN), np.exp(lnD), np.clip(Q, Q0, 1.0), np.clip(np.exp(lnL), 512, 131072)
                return C - loss_tot0(N, D, Q, L)

            sol = minimize(obj, z0, method="SLSQP", constraints={"type": "ineq", "fun": cons},
                           bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)),
                                   (Q0, 1.0), (np.log(512), np.log(131072))],
                           options={"maxiter": 800, "ftol": 1e-12})
            if sol.success and (best is None or sol.fun < best[0]):
                best = (sol.fun, sol.x)
        L, z = best
        N, D, Q, Lc = np.exp(z[0]), np.exp(z[1]), np.clip(z[2], Q0, 1.0), np.clip(np.exp(z[3]), 512, 131072)
        w_rows.append({"w": w, "N": float(N), "D": float(D), "Q": float(Q), "L_ctx_opt": float(Lc),
                       "L_loss": float(loss_gen(N, D, Q))})
        print(f"w={w}: N={N:.3f} D={D:.1f} Q={Q:.3f} L_ctx*={Lc:.0f} L_loss={loss_gen(N, D, Q):.4f}")

    # === C: 对比固定 4096 (w=1 口径, C=1e22) ===
    print("\n=== C: 联合优化 vs 固定4096 (C=1e22, w=1) ===")
    r_joint = rows[1]
    # 固定 L_ctx=4096 的优化 (带上下文收益)
    C = 1e22
    best = None
    for seed in range(24):
        rng = np.random.default_rng(seed)
        z0 = [rng.uniform(np.log(0.01), np.log(5000)), rng.uniform(np.log(1), np.log(5000)), rng.uniform(Q0, 0.98)]

        def obj2(z):
            lnN, lnD, Q = z
            N, D, Q = np.exp(lnN), np.exp(lnD), np.clip(Q, Q0, 1.0)
            return loss_gen(N, D, Q) - R_ctx(4096.0)

        def cons2(z):
            lnN, lnD, Q = z
            N, D, Q = np.exp(lnN), np.exp(lnD), np.clip(Q, Q0, 1.0)
            return C - loss_tot0(N, D, Q, 4096.0)

        sol = minimize(obj2, z0, method="SLSQP", constraints={"type": "ineq", "fun": cons2},
                       bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)), (Q0, 1.0)],
                       options={"maxiter": 800, "ftol": 1e-12})
        if sol.success and (best is None or sol.fun < best[0]):
            best = (sol.fun, sol.x)
    L, z = best
    N0, D0, Q0_ = np.exp(z[0]), np.exp(z[1]), np.clip(z[2], Q0, 1.0)
    print(f"固定4096: N={N0:.3f} D={D0:.1f} Q={Q0_:.3f} L_loss={loss_gen(N0, D0, Q0_):.4f}")
    print(f"联合优化: N={r_joint['N']:.3f} D={r_joint['D']:.1f} Q={r_joint['Q']:.3f} "
          f"L_ctx={r_joint['L_ctx_opt']:.0f} L_loss={r_joint['L_loss']:.4f}")
    delta = loss_gen(N0, D0, Q0_) - loss_gen(r_joint["N"], r_joint["D"], r_joint["Q"])
    print(f"=> L_ctx 内生化损失增益: {delta:.4f} (相对损失降 {delta / loss_gen(N0, D0, Q0_) * 100:.2f}%)")

    with open(os.path.join(EX, "v9_p3_lctx_inner.json"), "w", encoding="utf-8") as f:
        json.dump({"benefit": rb, "budgets": rows, "w_sens": w_rows},
                  f, ensure_ascii=False, indent=2)
    pd.DataFrame(rows).to_csv(os.path.join(EX, "v9_p3_budgets.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(w_rows).to_csv(os.path.join(EX, "v9_p3_w_sens.csv"), index=False, encoding="utf-8-sig")

    # 图: w 敏感性
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax2 = ax.twinx()
    ax.plot([r["w"] for r in w_rows], [r["L_ctx_opt"] for r in w_rows], "o-", color="#2563EB", label="最优 L_ctx")
    ax2.plot([r["w"] for r in w_rows], [r["L_loss"] for r in w_rows], "s--", color="#F59E0B", label="损失")
    ax.set_xlabel("上下文收益权重 w"); ax.set_ylabel("最优上下文长度 L_ctx*", color="#2563EB")
    ax2.set_ylabel("训练损失 L", color="#F59E0B")
    ax.legend(loc="upper left"); ax2.legend(loc="lower right")
    ax.set_yscale("log")
    ax.set_title("v9: 最优上下文长度与收益权重的平衡 (C=1e22)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v9_p3_lctx_inner.png"), dpi=200); plt.close(fig)
    print("\ndone v9")


def loss_tot0(N, D, Q, L):
    return cost_total(N, D, Q, L)


if __name__ == "__main__":
    main()