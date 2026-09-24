# -*- coding: utf-8 -*-
"""
v6 实验: 全链路联合优化 —— 配比向量 p 作为决策变量
创新点: 把问题一的 17 域配比 p 与问题二的广义标度律、问题三的算力预算
打通成单一优化问题:
    min L(N, D, p) = E + A N^{-a} + B D^{-b} + C(1-Q(p))^g N^{-h}
    s.t.  6ND + D[g(Q)-g(Q0)]_+ + eta*N*D*L_ctx <= C,  sum(p)=1, p>=0
其中 Q(p) = p . Q_dom (域质量加权), 连接配比-质量-损失三个环节.
对比:
  A) 均匀配比 / 数据实际配比(比例不变缩放) / 联合优化配比 下的 L*
  B) 三档预算下的最优配比结构与质量成本份额
  C) 配比优化的边际价值 (相对均匀/基线配比的损失改善)
输出: experiments/v6_p3_joint.csv/json + 图
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import A, B, RES, FIG, BASE, MIX_DOMAINS
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

ETA = 2e-4
Q0 = 0.4
L_CTX = 4096

# 问题二选定的广义标度律 (interaction_N)
_p2 = os.path.join(RES, "p2_scaling_results.json")
_g = json.load(open(_p2, encoding="utf-8"))["generalized"]
pg = {k: float(v) for k, v in _g["forms"][_g["chosen"]]["params"].items()}
E_, A_, a_, B_, b_, C_, g_, h_ = (pg[k] for k in ["E", "A", "a", "B", "b", "C", "g", "h"])


def g_cost(Q, form="power"):
    return 5e9 * Q ** 4.0


def loss_gen(N, D, Q):
    return (E_ + A_ * N ** (-a_) + B_ * D ** (-b_)
            + C_ * np.maximum(1 - Q, 0) ** g_ * N ** (-h_))


def cost_total(N, D, Q):
    ct = 6e18 * N * D
    cq = D * 1e9 * max(g_cost(Q) - g_cost(Q0), 0.0)
    ca = ETA * (N * 1e9) * (D * 1e9) * L_CTX
    return ct + cq + ca


def solve_joint(C, qvec, p0):
    """Q 固定为配比导出值 Q(p0), 只优化 (N,D)"""
    Qp = float(np.clip(np.dot(p0, qvec), 0, 1))

    def obj(z):
        lnN, lnD = z
        return loss_gen(np.exp(lnN), np.exp(lnD), Qp)

    def cons(z):
        lnN, lnD = z
        return C - cost_total(np.exp(lnN), np.exp(lnD), Qp)

    best = None
    for seed in range(20):
        rng = np.random.default_rng(seed)
        z0 = [rng.uniform(np.log(0.01), np.log(5000)), rng.uniform(np.log(1), np.log(5000))]
        sol = minimize(obj, z0, method="SLSQP", constraints={"type": "ineq", "fun": cons},
                       bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5))],
                       options={"maxiter": 600, "ftol": 1e-12})
        if sol.success and (best is None or sol.fun < best[0]):
            best = (sol.fun, sol.x)
    L, z = best
    lnN, lnD = z
    N, D = np.exp(lnN), np.exp(lnD)
    return {"L": L, "L_p": L, "N": float(N), "D": float(D),
            "Q": Qp, "Q_p": Qp,
            "s_train": 6e18 * N * D / C,
            "s_Q": max(g_cost(Qp) - g_cost(Q0), 0.0) * D * 1e9 / C,
            "s_attn": ETA * N * D * L_CTX * 1e18 / C}


def main():
    # 17 域质量: 问题一域级 Q 映射 (直接映射域取 Q; 相近语料域归并; 其余 0.5)
    try:
        dq = pd.read_csv(os.path.join(RES, "p1_domain_quality.csv"))
        qmap = dict(zip(dq["domain"], dq["Q_weighted"]))
    except Exception:
        qmap = {}
    alias = {"wikipedia_en": "wikipedia", "gutenberg_pg_19": "book",
             "bookcorpus2": "book", "dm_mathematics": "arxiv", "pile_cc": "c4"}
    qvec = np.array([qmap.get(alias.get(d, d), 0.5) for d in MIX_DOMAINS], dtype=float)
    print("17 域质量 Q:", dict(zip(MIX_DOMAINS, np.round(qvec, 3))))

    # 基线配比: 从 1M 训练配比表的 17 域比例估计 (列名带 train_the_pile_ 前缀)
    try:
        tm = pd.read_csv(os.path.join(A, "regmix_tables", "train_mixture_1m.csv"))
        cols17 = ["train_the_pile_" + d for d in MIX_DOMAINS if "train_the_pile_" + d in tm.columns]
        p_data = tm[cols17].mean().to_numpy()
        p_data = np.clip(p_data, 0, None); p_data = p_data / p_data.sum()
    except Exception as e:
        print("数据配比不可用:", e)
        p_data = np.full(len(qvec), 1.0 / len(qvec))
    p_uniform = np.full(len(qvec), 1.0 / len(qvec))

    print("\n=== A: 三种配比下的最优损失 (C=1e22) ===")
    rows = []
    for name, p0 in [("uniform", p_uniform), ("data_mix", p_data)]:
        r = solve_joint(1e22, qvec, p0)
        rows.append({"scenario": name, **r})
        print(f"[{name}] L*={r['L']:.4f} N={r['N']:.3f} D={r['D']:.1f} Q*={r['Q']:.3f} Q(p)={r['Q_p']:.3f}")

    # === B: 三档预算下联合优化配比 (Q=Q(p) 直接耦合: 质量由配比内生决定) ===
    print("\n=== B: 三档预算下联合优化最优配比 ===")
    # 决策变量 = (lnN, lnD, p_1..p_16)  p_17 由归一化得出;  Q = clip(p . qvec)
    nd = len(qvec)
    budgets = [1e19, 1e22, 1e24]
    opt_rows = []
    for C in budgets:
        def _q_from_z(z):
            lnN, lnD = z[:2]
            p = np.clip(z[2:], 0, 1)
            pfull = np.concatenate([p, [max(1.0 - p.sum(), 0.0)]])
            s = pfull.sum()
            if s > 0:
                pfull = pfull / s
            return np.exp(lnN), np.exp(lnD), float(np.clip(np.dot(pfull, qvec), 0, 1))

        def obj(z):
            N, D, Qp = _q_from_z(z)
            return loss_gen(N, D, Qp)

        def cons(z):
            N, D, Qp = _q_from_z(z)
            return C - cost_total(N, D, Qp)

        best = None
        for seed in range(12):
            rng = np.random.default_rng(seed)
            p_init = rng.dirichlet(np.ones(nd))[: nd - 1] * (nd - 1)
            z0 = np.concatenate([[rng.uniform(np.log(0.01), np.log(5000)),
                                  rng.uniform(np.log(1), np.log(5000))],
                                 p_init])
            sol = minimize(obj, z0, method="SLSQP",
                           constraints={"type": "ineq", "fun": cons},
                           bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5))]
                                  + [(0.0, 1.0)] * (nd - 1),
                           options={"maxiter": 800, "ftol": 1e-11})
            if sol.success and (best is None or sol.fun < best[0]):
                best = (sol.fun, sol.x)
        L, z = best
        p = np.clip(z[2:], 0, 1)
        p = p / p.sum()
        pfull = np.concatenate([p, [1 - p.sum()]])
        pfull = np.clip(pfull, 0, None); pfull = pfull / pfull.sum()
        Qp = float(np.clip(np.dot(pfull, qvec), 0, 1))
        opt_rows.append({"C": C, "L": L, "N": float(np.exp(z[0])), "D": float(np.exp(z[1])),
                         "Q": Qp, "Qp": Qp, "Quse": Qp,
                         "p": pfull.tolist(), "top3": [MIX_DOMAINS[i] for i in np.argsort(pfull)[-3:][::-1]]})
        print(f"C={C:.0e}: L*={L:.4f} N={np.exp(z[0]):.3f} D={np.exp(z[1]):.1f} Q=Q(p)={Qp:.3f}")
        print(f"   最优配比 top3: {opt_rows[-1]['top3']}  权重 top5: {np.round(pfull[np.argsort(pfull)[-5:][::-1]], 3)}")

    # === C: 配比优化边际价值 ===
    print("\n=== C: 配比优化边际价值 (C=1e22) ===")
    r_base = solve_joint(1e22, qvec, p_uniform)
    r_data = solve_joint(1e22, qvec, p_data)
    r_opt = opt_rows[1]
    gain_uniform = (r_base["L_p"] - r_opt["L"]) / r_base["L_p"] * 100
    gain_data = (r_data["L_p"] - r_opt["L"]) / r_data["L_p"] * 100
    print(f"均匀配比 Q(p)={r_base['Q_p']:.3f} L={r_base['L_p']:.4f}; "
          f"数据配比 Q(p)={r_data['Q_p']:.3f} L={r_data['L_p']:.4f}; "
          f"联合优化 L={r_opt['L']:.4f} (改善 {gain_uniform:.2f}% vs 均匀, {gain_data:.2f}% vs 数据配比)")
    val = {"uniform_Q": r_base["Q_p"], "data_Q": r_data["Q_p"], "opt_L": r_opt["L"],
           "gain_vs_uniform_pct": gain_uniform, "gain_vs_data_pct": gain_data}

    with open(os.path.join(EX, "v6_p3_joint.json"), "w", encoding="utf-8") as f:
        json.dump({"qvec": {d: float(q) for d, q in zip(MIX_DOMAINS, qvec)},
                   "scenarios": rows, "opt_budgets": opt_rows, "value": val},
                  f, ensure_ascii=False, indent=2)
    pd.DataFrame(rows).to_csv(os.path.join(EX, "v6_p3_scenarios.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([{k: (v if k != "p" else json.dumps(v)) for k, v in r.items()} for r in opt_rows]
                 ).to_csv(os.path.join(EX, "v6_p3_opt_budgets.csv"), index=False, encoding="utf-8-sig")

    # 图: 最优配比 vs 质量
    fig, ax = plt.subplots(figsize=(11, 4.5))
    p_opt = np.array(opt_rows[1]["p"])
    order = np.argsort(qvec)
    ax.bar(np.arange(nd), qvec[order] * 100, color="#2563EB", alpha=0.55, label="域质量 Q×100")
    ax.bar(np.arange(nd) + 0.35, p_opt[order] * 100, color="#F59E0B", alpha=0.85, width=0.6, label="最优配比 p×100")
    ax.set_xticks(np.arange(nd)); ax.set_xticklabels([MIX_DOMAINS[i] for i in order], rotation=60, fontsize=7)
    ax.set_ylabel("%"); ax.set_title("v6: 联合优化最优配比 vs 域质量 (C=1e22)")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v6_p3_joint.png"), dpi=200); plt.close(fig)

    print("\ndone v6")


if __name__ == "__main__":
    main()
