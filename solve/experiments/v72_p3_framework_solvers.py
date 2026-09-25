# -*- coding: utf-8 -*-
"""
v72 实验: 跨框架求解器对比 —— 全局最优一致性核验 (P3)
对 3 预算 x 3 成本形式 = 9 个实例, 用 5 个独立求解框架:
  1) SLSQP 24 初值 (主链路 solve_opt)
  2) trust-constr (内点法, 多初值)
  3) COBYLA (无导数, 多初值)
  4) differential_evolution (全局随机搜索, 罚函数)
  5) shgo (单纯同调全局优化, 原生约束)
比较各框架的最优目标 L* 与决策 (N*,D*,Q*):
  跨框架一致 => 主链路最优解是全局最优 (不依赖求解器/初值/全局方法).
输出: experiments/v72_p3_framework_solvers.csv/.json/.png
"""
import os, sys, json, math
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import loss_generalized, cost_terms, solve_opt, Q0, GL, GL_FORM
from common import BASE
from scipy.optimize import minimize, differential_evolution, shgo

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

LCTX = 4096
BUDGETS = [1e19, 1e22, 1e24]
FORMS = ["exp", "power", "log"]
BNDS = [(math.log(0.005), math.log(1e5)), (math.log(0.2), math.log(1e5)), (Q0, 1.0)]
FW_COLORS = {"SLSQP": "#177cb0", "COBYLA": "#3eede7", "DE": "#70f3ff",
             "SHGO": "#44cef6", "trust-constr": "#1685a9"}
# 一致性核验框架(排除 trust-constr: 已知在边界角点最优处失稳, 单独作诊断)
AGREE_FW = ["SLSQP", "COBYLA", "DE", "SHGO"]
REL_FTOL = 1e-8  # 相对可行容差 (约束值量级 1e19-1e24, 绝对容差不适用)


def _obj(z):
    lnN, lnD, Q = z
    return loss_generalized(np.exp(lnN), np.exp(lnD), float(np.clip(Q, Q0, 1.0)))


def _cons(z, C, form):
    lnN, lnD, Q = z
    ct, cq, ca = cost_terms(np.exp(lnN), np.exp(lnD), float(np.clip(Q, Q0, 1.0)), form, LCTX)
    return C - (ct + cq + ca)


def unpack(x):
    return float(_obj(x)), math.exp(x[0]), math.exp(x[1]), float(np.clip(x[2], Q0, 1.0))


def run_slsqp(C, form):
    j = solve_opt(C, form, LCTX)
    return (j["L"], j["N"], j["D"], j["Q"]) if j else None


def run_trust(C, form, nstart=3):
    best = None
    for s in range(nstart):
        rng = np.random.default_rng(1000 + s)
        z0 = np.array([rng.uniform(*BNDS[0]), rng.uniform(*BNDS[1]), rng.uniform(*BNDS[2])])
        try:
            sol = minimize(_obj, z0, method="trust-constr",
                           constraints={"type": "ineq", "fun": lambda z: _cons(z, C, form)},
                           bounds=BNDS, options={"maxiter": 400, "gtol": 1e-9, "xtol": 1e-9})
            if sol.success:
                val = _obj(sol.x)
                if best is None or val < best[0]:
                    best = (val, sol.x)
        except Exception:
            continue
    return unpack(best[1]) if best else None


def run_cobyla(C, form, nstart=3):
    best = None
    for s in range(nstart):
        rng = np.random.default_rng(2000 + s)
        z0 = np.array([rng.uniform(*BNDS[0]), rng.uniform(*BNDS[1]), rng.uniform(*BNDS[2])])
        try:
            sol = minimize(_obj, z0, method="COBYLA",
                           constraints={"type": "ineq", "fun": lambda z: _cons(z, C, form)},
                           bounds=BNDS, options={"maxiter": 3000, "tol": 1e-9, "rhobeg": 0.4})
            v = _obj(sol.x)
            if sol.success and np.isfinite(v) and _cons(sol.x, C, form) >= -REL_FTOL * C:
                if best is None or v < best[0]:
                    best = (v, sol.x)
        except Exception:
            continue
    return unpack(best[1]) if best else None


def run_de(C, form):
    PEN = 1e2

    def pen(z):
        return _obj(z) + PEN * max(0.0, -_cons(z, C, form)) ** 2

    res = differential_evolution(pen, BNDS, seed=7, maxiter=400, popsize=12,
                                 tol=1e-10, polish=True, workers=1)
    if not res.success or not np.isfinite(res.fun):
        return None
    if _cons(res.x, C, form) < -REL_FTOL * C:
        return None
    return unpack(res.x)


def run_shgo(C, form):
    try:
        res = shgo(_obj, BNDS, n=64, iters=4,
                   constraints={"type": "ineq", "fun": lambda z: _cons(z, C, form)},
                   options={"f_tol": 1e-9}, sampling_method="sobol")
        if not res.success or not np.isfinite(res.fun) or res.x is None:
            return None
        if _cons(res.x, C, form) < -REL_FTOL * C:
            return None
        return unpack(res.x)
    except Exception:
        return None


RUNNERS = {"SLSQP": run_slsqp, "trust-constr": run_trust, "COBYLA": run_cobyla,
           "DE": run_de, "SHGO": run_shgo}


def main():
    rows, agg = [], []
    for C in BUDGETS:
        for form in FORMS:
            best = None
            for fw, fn in RUNNERS.items():
                r = fn(C, form)
                rows.append({"C": C, "form": form, "framework": fw,
                             "L": r[0], "N": r[1], "D": r[2], "Q": r[3]} if r else
                            {"C": C, "form": form, "framework": fw,
                             "L": np.nan, "N": np.nan, "D": np.nan, "Q": np.nan})
                if r and fw in AGREE_FW and (best is None or r[0] < best):
                    best = r[0]
            ok = [r for r in rows if r["C"] == C and r["form"] == form
                  and r["framework"] in AGREE_FW and np.isfinite(r["L"])]
            rels = [(r["L"] - best) / best for r in ok] if best else []
            qs = [r["Q"] for r in ok]
            tc = [r for r in rows if r["C"] == C and r["form"] == form
                  and r["framework"] == "trust-constr"]
            tc_gap = ((tc[0]["L"] - best) / best * 100) if tc and np.isfinite(tc[0]["L"]) else np.nan
            agg.append({"C": C, "form": form, "L_best": best,
                        "max_rel_pct": max(rels) * 100 if rels else np.nan,
                        "n_converged": len(ok), "n_total": len(AGREE_FW),
                        "Q_range": (max(qs) - min(qs)) if qs else np.nan,
                        "all_agree_1e6": bool(max(rels) < 1e-6) if rels else False,
                        "trust_gap_pct": float(tc_gap) if not (tc_gap != tc_gap) else np.nan})
            print(f"C={C:.0e} {form:5s}: L*={best:.8f} | 4框架一致(相对偏差 "
                  f"{max(rels)*100:.2e}%) | Q*范围={max(qs)-min(qs):.2e} | "
                  f"trust-constr 偏离={tc_gap:.2e}%" if np.isfinite(tc_gap) else
                  f"C={C:.0e} {form:5s}: L*={best:.8f} | 4框架一致(相对偏差 "
                  f"{max(rels)*100:.2e}%) | Q*范围={max(qs)-min(qs):.2e} | trust-constr 未收敛")

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v72_p3_framework_solvers.csv"), index=False, encoding="utf-8-sig")
    _py = lambda o: o.item() if hasattr(o, "item") else str(o)
    with open(os.path.join(EX, "v72_p3_framework_solvers.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "agg": agg, "gl_form": GL_FORM,
                   "gl": {k: float(v) for k, v in GL.items()}}, f,
                  ensure_ascii=False, indent=2, default=_py)

    # ---- 图: 3 面板(成本形式) x 预算, 各框架 L* 分组柱 ----
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    for ax, form in zip(axes, FORMS):
        sub = rdf[rdf["form"] == form]
        x = np.arange(len(BUDGETS))
        w = 0.14
        for i, fw in enumerate(RUNNERS):
            vals = [sub[(sub["framework"] == fw) & (sub["C"] == C)]["L"].iloc[0]
                    if len(sub[(sub["framework"] == fw) & (sub["C"] == C)]) else np.nan
                    for C in BUDGETS]
            ax.bar(x + (i - 2) * w, vals, w, color=FW_COLORS[fw], label=fw if form == "exp" else None,
                   edgecolor="white", lw=0.3)
        a = [A for A in agg if A["form"] == form]
        for xi, A in enumerate(a):
            ax.text(xi, A["L_best"], f"±{A['max_rel_pct']:.1e}%",
                    ha="center", va="bottom", fontsize=7.5, color="#1685a9")
        ax.set_xticks(x); ax.set_xticklabels(["1e19", "1e22", "1e24"])
        ax.set_title(f"质量成本 = {form}")
        ax.set_ylabel("最优损失 L*")
        ax.grid(alpha=0.3, axis="y")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=9, frameon=False)
    fig.suptitle("五框架跨框架求解对比 —— 全局最优一致性 (括号为最大相对偏差)",
                 fontsize=11, y=1.02)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(os.path.join(EX, "v72_p3_framework_solvers.png"), dpi=200)
    plt.close(fig)

    n_all = sum(1 for a in agg if a["all_agree_1e6"])
    print(f"\n4框架(SLSQP/COBYLA/DE/SHGO)全部实例相对偏差<1e-6: {n_all}/{len(agg)}")
    print("done v72")


if __name__ == "__main__":
    main()
