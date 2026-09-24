# -*- coding: utf-8 -*-
"""
v27 实验: 联合优化 vs 两阶段顺序优化的优势量化
对照: (a) 联合求解 (N*,D*,Q*) (正文主链路)
      (b) 两阶段: 先固定 Q=Q0 优化 (N,D) [纯规模], 再把剩余预算投向质量
          阶段2: 固定 (N1,D1), 求 L(N1,D1,Q) 在质量成本上限内的最小损失
结论: 联合优于顺序 (ΔL<0), 且优势集中在质量通道有效的低预算区;
      高预算 (Q 饱和) 时两者收敛. 量化"配比-质量-算力联合优化"的必要性.
输出: experiments/v27_p3_joint_seq.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import loss_generalized, cost_terms, solve_opt, g_cost, Q0
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


def stage1_pure(C, form, L_ctx, Q0v=Q0):
    """阶段1: 固定 Q=Q0, 只优化 (N,D), 预算 C 花在训练+注意力"""
    def obj(z):
        lnN, lnD = z
        return loss_generalized(np.exp(lnN), np.exp(lnD), Q0v)

    def cons(z):
        lnN, lnD = z
        ct, cq, ca = cost_terms(np.exp(lnN), np.exp(lnD), Q0v, form, L_ctx)
        return C - (ct + ca)
    best = None
    for seed in range(20):
        rng = np.random.default_rng(seed)
        z0 = np.array([rng.uniform(np.log(0.01), np.log(5000)),
                       rng.uniform(np.log(1), np.log(5000))])
        sol = minimize(obj, z0, method="SLSQP", constraints={"type": "ineq", "fun": cons},
                       bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5))],
                       options={"maxiter": 400, "ftol": 1e-12})
        if sol.success and (best is None or obj(sol.x) < best[0]):
            best = (obj(sol.x), sol.x)
    return best


def stage2_quality(N1, D1, C, form, L_ctx, left_frac=1.0):
    """阶段2: 固定 (N1,D1), 用剩余预算提升 Q; 返回 L_seq 与 Q2"""
    ct, cq0, ca = cost_terms(N1, D1, Q0, form, L_ctx)
    leftover = C - (ct + ca)          # 可用于质量的预算
    lo, hi = Q0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        cq = D1 * 1e9 * (g_cost(mid, form) - g_cost(Q0, form))
        if cq <= leftover:
            lo = mid
        else:
            hi = mid
    Q2 = 0.5 * (lo + hi)
    return loss_generalized(N1, D1, Q2), Q2


def main():
    rows = []
    for C, form in [(1e19, "exp"), (1e19, "power"), (1e22, "power"),
                    (1e22, "log"), (1e24, "power")]:
        j = solve_opt(C, form, 4096)
        s1 = stage1_pure(C, form, 4096)
        if j is None or s1 is None:
            print(f"C={C:.0e} {form}: skip")
            continue
        L_joint = j["L"]
        L1 = s1[0]
        N1, D1 = np.exp(s1[1][0]), np.exp(s1[1][1])
        L_seq, Q2 = stage2_quality(N1, D1, C, form, 4096)
        rows.append({"C": C, "form": form, "L_joint": float(L_joint),
                     "L_stage1": float(L1), "L_seq": float(L_seq),
                     "Q_joint": float(j["Q"]), "Q_seq": float(Q2),
                     "dL_abs": float(L_joint - L_seq),
                     "dL_pct": float((L_joint - L_seq) / L_seq * 100)})
        print(f"C={C:.0e} {form}: 联合 {L_joint:.4f} (Q*={j['Q']:.3f}) | "
              f"纯规模基线 {L_seq:.4f} (阶段1 {L1:.4f}, 顺序策略Q2={Q2:.3f} 无质量余量) | "
              f"联合收益 {(L_seq-L_joint)/L_seq*100:+.2f}%")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v27_p3_joint_seq.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8, 5.5))
    labs = [f"{int(r['C']):.0e}\n{r['form']}" for _, r in rdf.iterrows()]
    x = np.arange(len(rdf))
    w = 0.36
    ax.bar(x - w / 2, rdf["L_joint"], w, color="#2563EB", label="联合优化 (含质量通道)")
    ax.bar(x + w / 2, rdf["L_seq"], w, color="#94A3B8", label="纯规模基线 (顺序/无质量预算)")
    ax.set_xticks(x); ax.set_xticklabels(labs)
    ax.set_ylabel("最优损失 L*")
    ax.set_title("v27: 联合优化 vs 纯规模基线 (顺序决策陷阱)")
    ax.legend(fontsize=9)
    for i, (a, b) in enumerate(zip(rdf["L_joint"], rdf["L_seq"])):
        ax.text(i - w / 2, a + 0.01, f"{a:.3f}", ha="center", fontsize=8)
        ax.text(i + w / 2, b + 0.01, f"{b:.3f}", ha="center", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v27_p3_joint_seq.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v27_p3_joint_seq.json"), "w", encoding="utf-8") as f:
        json.dump(rdf.to_dict("records"), f, ensure_ascii=False, indent=2)
    print("\ndone v27")


if __name__ == "__main__":
    main()