# -*- coding: utf-8 -*-
"""
问题三: 算力约束下的多维资源联合优化与结构性转移
决策变量: N(参数量,B), D(训练token数,B), Q(质量, 由领域配比加权决定, 含 p)
目标: min L(N,D,Q)  [广义标度律 interaction 形式, 问题二拟合参数]
约束: C_train + C_Q + C_attn <= C
  C_train = 6e18 * N * D
  C_Q     = D*1e9 * [g(Q)-g(Q0)]_+  (三种成本函数: 指数/幂/对数渐进)
  C_attn  = 2e14 * N * D * L_ctx    (eta=2e-4)
外生: L_ctx 取值依据 C7 (2048~131072), L_ctx^crit = 6/eta = 30000
分析:
  1) 低/中/高三档预算 C=1e19/1e22/1e24 的最优分配 (N*,D*,Q*) 与成本份额;
  2) 结构性转移的数学定义: 预算跨越量级时最优策略是否质变
     (定义: 份额排序/主导约束/内点-边界切换), 用连续预算扫描识别转移点;
  3) 成本函数选择对最优解的影响 (三种 g(Q) 对比);
  4) L_ctx 敏感性: 在 C7 可行值上扫描, 标出 L_ctx^crit.
输出: results/p3_*.csv/json, figures/p3_*.png
"""
import os, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from common import RES, FIG, BASE

for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

# ---- 广义标度律参数 (问题二 interaction 形式拟合值) ----
GL = {"E": 1.551497836760937, "A": 0.5340242690174833, "a": 0.2813537379269008,
      "B": 1.250801775247864, "b": 0.3101638726673506,
      "C": 0.44511211150804275, "g": 0.9905293045386531, "d": 0.044689829791678105}
ETA = 2e-4
LCTX_CRIT = 6.0 / ETA  # 30000

# ---- 质量成本函数 (附录B) ----
def g_cost(Q, form):
    if form == "exp":
        return 1e7 * np.exp(6.0 * Q)
    if form == "power":
        return 5e9 * Q ** 4.0
    return 2e9 * np.log1p(10.0 * Q)   # 对数渐进

G_FORMS = ["exp", "power", "log"]

# Q0: 基线质量 (问题一域级 Q 的语料加权均值约 0.39, 取 0.4)
Q0 = 0.4

def loss_generalized(N, D, Q):
    E, A, a, B, b, C, g, d = (GL[k] for k in ["E", "A", "a", "B", "b", "C", "g", "d"])
    return E + A * N ** (-a) + B * D ** (-b) + C * np.maximum(1 - Q, 0) ** g * D ** (-d)

def cost_terms(N, D, Q, form, L_ctx):
    """返回 (C_train, C_Q, C_attn) FLOPs"""
    C_train = 6e18 * N * D
    C_Q = D * 1e9 * max(g_cost(Q, form) - g_cost(Q0, form), 0.0)
    C_attn = ETA * (N * 1e9) * (D * 1e9) * L_ctx
    return C_train, C_Q, C_attn

def solve_opt(C, form, L_ctx, Q0v=Q0):
    """在预算 C 下求 (N*,D*,Q*); log 空间 SLSQP 多初值"""
    def obj(z):
        lnN, lnD, Q = z
        N, D = np.exp(lnN), np.exp(lnD)
        Q = np.clip(Q, Q0v, 1.0)
        return loss_generalized(N, D, Q)

    def cons(z):
        lnN, lnD, Q = z
        N, D = np.exp(lnN), np.exp(lnD)
        ct, cq, ca = cost_terms(N, D, Q, form, L_ctx)
        return C - (ct + cq + ca)

    best = None
    for seed in range(24):
        rng = np.random.default_rng(seed)
        lnN0 = rng.uniform(np.log(0.01), np.log(5000))
        lnD0 = rng.uniform(np.log(1), np.log(5000))
        Q0_ = rng.uniform(Q0v, 0.98)
        z0 = np.array([lnN0, lnD0, Q0_])
        sol = minimize(obj, z0, method="SLSQP", constraints={"type": "ineq", "fun": cons},
                       bounds=[(np.log(0.005), np.log(1e5)), (np.log(0.2), np.log(1e5)),
                               (Q0v, 1.0)],
                       options={"maxiter": 600, "ftol": 1e-12})
        if sol.success:
            val = obj(sol.x)
            if best is None or val < best[0]:
                best = (val, sol.x)
    if best is None:
        return None
    val, z = best
    lnN, lnD, Q = z
    N, D = np.exp(lnN), np.exp(lnD)
    Q = np.clip(Q, Q0v, 1.0)
    ct, cq, ca = cost_terms(N, D, Q, form, L_ctx)
    return {"N": N, "D": D, "Q": Q, "L": val,
            "C_train": ct, "C_Q": cq, "C_attn": ca,
            "C_total": ct + cq + ca, "C": C}

def main():
    res = {}
    budgets = [1e19, 1e22, 1e24]
    lctx_vals = sorted(set([2048, 4096, 8192, 30000, 32768, 131072]))

    # ===== 1. 三档预算 × 三种成本函数 (L_ctx=4096 基准, C7 中位数附近) =====
    L_CTX_BASE = 4096
    rows = []
    for C in budgets:
        for form in G_FORMS:
            s = solve_opt(C, form, L_CTX_BASE)
            if s:
                s["budget"] = C; s["form"] = form; s["L_ctx"] = L_CTX_BASE
                s["s_train"] = s["C_train"] / s["C_total"]
                s["s_Q"] = s["C_Q"] / s["C_total"]
                s["s_attn"] = s["C_attn"] / s["C_total"]
                rows.append(s)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RES, "p3_opt_results.csv"), index=False, encoding="utf-8-sig")
    print("=== 三档预算最优配置 (L_ctx=4096) ===")
    print(df[["budget", "form", "N", "D", "Q", "L", "s_train", "s_Q", "s_attn"]].to_string(index=False))
    res["main"] = df.to_dict("records")

    # ===== 2. 结构性转移扫描: 连续预算 log 网格 =====
    Cgrid = np.logspace(17, 26, 181)
    scan = []
    for form in G_FORMS:
        for C in Cgrid:
            s = solve_opt(C, form, L_CTX_BASE)
            if s:
                s["form"] = form
                s["s_train"] = s["C_train"] / s["C_total"]
                s["s_Q"] = s["C_Q"] / s["C_total"]
                s["s_attn"] = s["C_attn"] / s["C_total"]
                scan.append(s)
    sdf = pd.DataFrame(scan)
    sdf.to_csv(os.path.join(RES, "p3_structural_scan.csv"), index=False, encoding="utf-8-sig")

    # 转移点识别: 份额主导成分切换 + Q 离开边界 (Q>Q0+0.005)
    print("\n=== 结构性转移点 (L_ctx=4096) ===")
    transitions = {}
    for form in G_FORMS:
        g = sdf[sdf["form"] == form].sort_values("C")
        dom = []
        q_active = []
        for _, r in g.iterrows():
            sh = [("train", r["s_train"]), ("Q", r["s_Q"]), ("attn", r["s_attn"])]
            dom.append(max(sh, key=lambda t: t[1])[0])
            q_active.append(r["Q"] > Q0 + 0.005)
        flips = []
        for i in range(1, len(g)):
            if dom[i] != dom[i - 1]:
                flips.append(("dominant", g.iloc[i]["C"], f"{dom[i-1]}->{dom[i]}"))
            if q_active[i] != q_active[i - 1]:
                flips.append(("Q_active", g.iloc[i]["C"], f"{q_active[i-1]}->{q_active[i]}"))
        transitions[form] = flips
        print(f"[{form}] 转移点:")
        for t in flips:
            print(f"   C={t[1]:.2e}: {t[0]} {t[2]}")
    res["transitions"] = {k: [[t[0], t[1], t[2]] for t in v] for k, v in transitions.items()}

    # ===== 3. L_ctx 敏感性: 三档预算 × C7 可行 L_ctx =====
    lrows = []
    for C in budgets:
        for lc in lctx_vals:
            for form in ["power"]:   # 幂函数成本为主案 (论文中另比较 exp/log)
                s = solve_opt(C, form, lc)
                if s:
                    s["L_ctx"] = lc; s["budget"] = C; s["form"] = form
                    s["s_train"] = s["C_train"] / s["C_total"]
                    s["s_attn"] = s["C_attn"] / s["C_total"]
                    lrows.append(s)
    ldf = pd.DataFrame(lrows)
    ldf.to_csv(os.path.join(RES, "p3_lctx_sensitivity.csv"), index=False, encoding="utf-8-sig")
    print("\n=== L_ctx 敏感性 (幂函数成本, 三档预算) ===")
    print(ldf[["budget", "L_ctx", "N", "D", "Q", "s_train", "s_attn"]].to_string(index=False))
    res["lctx"] = ldf.to_dict("records")

    with open(os.path.join(RES, "p3_results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    # ===== 4. 图 =====
    # (a) 三档预算最优配置对比 (成本份额堆叠)
    fig, ax = plt.subplots(figsize=(9, 5))
    forms_cn = {"exp": "指数型", "power": "幂函数型", "log": "对数渐进型"}
    xpos = np.arange(3)
    w = 0.27
    for i, form in enumerate(G_FORMS):
        g = df[df["form"] == form].sort_values("budget")
        st = g["s_train"].to_numpy()
        sq = g["s_Q"].to_numpy()
        sa = g["s_attn"].to_numpy()
        ax.bar(xpos + (i - 1) * w, st, w, label=f"{forms_cn[form]}·训练", color="#2563EB")
        ax.bar(xpos + (i - 1) * w, sq, w, bottom=st, label=f"{forms_cn[form]}·质量", color="#10B981")
        ax.bar(xpos + (i - 1) * w, sa, w, bottom=st + sq, label=f"{forms_cn[form]}·注意力", color="#F59E0B")
    ax.set_xticks(xpos)
    ax.set_xticklabels([f"C={c:.0e}" for c in budgets])
    ax.set_ylabel("预算份额"); ax.set_title("三档预算下三种成本函数的最优分配结构")
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p3_budget_shares.png"), dpi=200); plt.close(fig)

    # (b) 结构性转移: 份额随预算变化 (幂函数型)
    g = sdf[sdf["form"] == "power"].sort_values("C")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(g["C"], g["s_train"], label="训练份额", color="#2563EB", lw=2)
    ax.plot(g["C"], g["s_Q"], label="质量份额", color="#10B981", lw=2)
    ax.plot(g["C"], g["s_attn"], label="注意力份额", color="#F59E0B", lw=2)
    for C in budgets:
        ax.axvline(C, color="gray", ls="--", lw=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("算力预算 C (FLOPs, 对数)"); ax.set_ylabel("预算份额")
    ax.set_title("幂函数质量成本: 最优分配随预算的结构性演变")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p3_structural.png"), dpi=200); plt.close(fig)

    # (c) 最优参数量随预算
    fig, ax = plt.subplots(figsize=(8, 5))
    for form in G_FORMS:
        gg = sdf[sdf["form"] == form].sort_values("C")
        ax.plot(gg["C"], gg["N"], label=forms_cn[form], lw=2)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("预算 C (FLOPs)"); ax.set_ylabel("最优参数量 N* (B)")
    ax.set_title("最优参数量随预算的增长 (幂律拟合给出指数)")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p3_opt_N.png"), dpi=200); plt.close(fig)

    # (d) L_ctx 敏感性: 注意力份额 vs L_ctx
    fig, ax = plt.subplots(figsize=(8, 5))
    for C in budgets:
        g = ldf[ldf["budget"] == C].sort_values("L_ctx")
        ax.plot(g["L_ctx"], g["s_attn"], "o-", label=f"C={C:.0e}", lw=1.5)
    ax.axvline(LCTX_CRIT, color="red", ls="--", label=f"L_ctx^crit=30000")
    ax.set_xscale("log")
    ax.set_xlabel("上下文长度 L_ctx (对数)"); ax.set_ylabel("注意力开销份额")
    ax.set_title("上下文长度对注意力开销份额的影响")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p3_lctx_sens.png"), dpi=200); plt.close(fig)

    # (e) 损失下降 vs 预算
    fig, ax = plt.subplots(figsize=(8, 5))
    for form in G_FORMS:
        gg = sdf[sdf["form"] == form].sort_values("C")
        ax.plot(gg["C"], gg["L"], label=forms_cn[form], lw=2)
    ax.set_xscale("log")
    ax.set_xlabel("预算 C (FLOPs)"); ax.set_ylabel("最优可达 Loss L*")
    ax.set_title("最优 Loss 随预算的下降")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p3_opt_loss.png"), dpi=200); plt.close(fig)

    print("\ndone p3")

if __name__ == "__main__":
    main()
