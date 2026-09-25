# -*- coding: utf-8 -*-
"""
v83 实验: 跨框架求解器对比扩展 —— 9 框架全局最优一致性核验 (P3)
在 v72 基础上把一致性框架从 4 个扩到 9 个:
  1) SLSQP 24 初值 (主链路 solve_opt)
  2) COBYLA (无导数, 多初值)
  3) differential_evolution (全局随机搜索, 罚函数)
  4) shgo (单纯同调全局优化, 原生约束)
  5) L-BFGS-B (拟牛顿, 罚函数, 多初值)
  6) Powell (方向集无导数, 罚函数, 多初值)
  7) Nelder-Mead (单纯形无导数, 罚函数, 多初值)
  8) dual_annealing (模拟退火全局, 罚函数)
  9) grid-restart (对数网格粗搜 + Powell 精修, 独立全局参照)
trust-constr 继续保留作诊断 (边界角点失稳已知).
输出: experiments/v83_p3_solver9.csv/.json/.png
"""
import os, sys, json, math
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import loss_generalized, cost_terms, solve_opt, Q0
from common import BASE
from scipy.optimize import minimize, differential_evolution, shgo, dual_annealing

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
             "SHGO": "#44cef6", "trust-constr": "#1685a9", "L-BFGS-B": "#88ada6",
             "Powell": "#177cb0", "Nelder-Mead": "#3eede7", "dual-anneal": "#70f3ff",
             "grid": "#44cef6"}
AGREE_FW = ["SLSQP", "COBYLA", "DE", "SHGO", "L-BFGS-B", "Powell",
            "Nelder-Mead", "dual-anneal", "grid"]
REL_FTOL = 1e-8
PEN = 1e2


def _obj(z):
    lnN, lnD, Q = z
    return loss_generalized(np.exp(lnN), np.exp(lnD), float(np.clip(Q, Q0, 1.0)))


def _cons(z, C, form):
    lnN, lnD, Q = z
    ct, cq, ca = cost_terms(np.exp(lnN), np.exp(lnD), float(np.clip(Q, Q0, 1.0)), form, LCTX)
    return C - (ct + cq + ca)


def unpack(x):
    return float(_obj(x)), math.exp(x[0]), math.exp(x[1]), float(np.clip(x[2], Q0, 1.0))


def pen_obj(z, C, form):
    """相对罚函数: 罚项以预算归一, 避免 1e22 量级罚值导致的数值停滞"""
    viol = max(0.0, -_cons(z, C, form))
    return _obj(z) + PEN * (viol / C) ** 2


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


def polish_feasible(z0, C, form):
    """SLSQP 可行化精修 (<=30 步): 把罚函数收敛点投影回精确可行域"""
    try:
        sol = minimize(_obj, z0, method="SLSQP",
                       constraints={"type": "ineq", "fun": lambda z: _cons(z, C, form)},
                       bounds=BNDS, options={"maxiter": 30, "ftol": 1e-12})
        if sol.success and np.isfinite(sol.fun) and _cons(sol.x, C, form) >= -REL_FTOL * C:
            return sol.x
        return None
    except Exception:
        return None


def run_de(C, form):
    # 保持与 v72 完全一致 (绝对罚函数), 保证原框架数字可复现
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


def run_local(method, C, form, nstart=6, seed_base=3000):
    best = None
    opts = {"maxiter": 8000, "ftol": 1e-12}
    if method == "Nelder-Mead":
        opts = {"maxiter": 8000, "xatol": 1e-10, "fatol": 1e-12}
    elif method == "Powell":
        opts = {"maxiter": 8000, "xtol": 1e-10, "ftol": 1e-12}
    for s in range(nstart):
        rng = np.random.default_rng(seed_base + s)
        z0 = np.array([rng.uniform(*BNDS[0]), rng.uniform(*BNDS[1]), rng.uniform(*BNDS[2])])
        try:
            sol = minimize(lambda z: pen_obj(z, C, form), z0, method=method, bounds=BNDS,
                           options=opts)
            if not (np.isfinite(sol.fun) and np.all(np.isfinite(sol.x))):
                continue
            xf = polish_feasible(sol.x, C, form)
            if xf is None:
                continue
            v = _obj(xf)
            if best is None or v < best[0]:
                best = (v, xf)
        except Exception:
            continue
    return unpack(best[1]) if best else None


def run_da(C, form):
    try:
        res = dual_annealing(lambda z: pen_obj(z, C, form), BNDS, seed=11,
                             maxiter=300, initial_temp=5e3, restart_temp_ratio=2e-5,
                             visit=2.6, accept=-5.0, no_local_search=False)
        if not (np.isfinite(res.fun) and np.all(np.isfinite(res.x))):
            return None
        xf = polish_feasible(res.x, C, form)
        if xf is None:
            return None
        return unpack(xf)
    except Exception:
        return None


def run_grid(C, form, ngr=21, nq=11):
    """对数网格粗搜 (21x21x11) + 前 5 个可行点 Powell 精修 + SLSQP 可行化"""
    lnNg = np.linspace(BNDS[0][0], BNDS[0][1], ngr)
    lnDg = np.linspace(BNDS[1][0], BNDS[1][1], ngr)
    Qg = np.linspace(Q0, 1.0, nq)
    cands = []
    for lnN in lnNg:
        for lnD in lnDg:
            for q in Qg:
                z = np.array([lnN, lnD, q])
                c = _cons(z, C, form)
                if c < 0:
                    continue
                cands.append((_obj(z), z))
    if not cands:
        return None
    cands.sort(key=lambda t: t[0])
    best = (cands[0][0], cands[0][1])
    for _, z0 in cands[:5]:
        try:
            sol = minimize(lambda z: pen_obj(z, C, form), z0, method="Powell",
                           bounds=BNDS, options={"maxiter": 5000, "xtol": 1e-10, "ftol": 1e-12})
            if not (np.isfinite(sol.fun) and np.all(np.isfinite(sol.x))):
                continue
            xf = polish_feasible(sol.x, C, form)
            if xf is None:
                continue
            v = _obj(xf)
            if v < best[0]:
                best = (v, xf)
        except Exception:
            continue
    return unpack(best[1])


RUNNERS = {"SLSQP": run_slsqp, "trust-constr": run_trust, "COBYLA": run_cobyla,
           "DE": run_de, "SHGO": run_shgo, "L-BFGS-B": lambda C, f: run_local("L-BFGS-B", C, f),
           "Powell": lambda C, f: run_local("Powell", C, f),
           "Nelder-Mead": lambda C, f: run_local("Nelder-Mead", C, f),
           "dual-anneal": run_da, "grid": run_grid}


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
            print(f"C={C:.0e} {form:5s}: L*={best:.8f} | {len(AGREE_FW)}框架一致(相对偏差 "
                  f"{max(rels)*100:.2e}%) | Q*范围={max(qs)-min(qs):.2e} | "
                  f"trust 偏离={tc_gap:.2e}%" if np.isfinite(tc_gap) else
                  f"C={C:.0e} {form:5s}: L*={best:.8f} | {len(AGREE_FW)}框架一致(相对偏差 "
                  f"{max(rels)*100:.2e}%) | Q*范围={max(qs)-min(qs):.2e} | trust 未收敛")

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v83_p3_solver9.csv"), index=False, encoding="utf-8-sig")
    _py = lambda o: o.item() if hasattr(o, "item") else str(o)
    json.dump({"rows": rows, "agg": agg,
               "agree_frameworks": AGREE_FW}, open(os.path.join(EX, "v83_p3_solver9.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=_py)

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.6))
    order = list(RUNNERS.keys())
    for ax, form in zip(axes, FORMS):
        sub = rdf[rdf["form"] == form]
        x = np.arange(len(BUDGETS))
        w = 0.09
        for i, fw in enumerate(order):
            vals = [sub[(sub["framework"] == fw) & (sub["C"] == C)]["L"].iloc[0]
                    if len(sub[(sub["framework"] == fw) & (sub["C"] == C)]) else np.nan
                    for C in BUDGETS]
            ax.bar(x + (i - 4) * w, vals, w, color=FW_COLORS[fw], label=fw if form == "exp" else None,
                   edgecolor="white", lw=0.3)
        for xi, A in enumerate(agg):
            if A["form"] == form:
                ax.text(xi, A["L_best"], f"±{A['max_rel_pct']:.1e}%",
                        ha="center", va="bottom", fontsize=7, color="#1685a9")
        ax.set_xticks(x); ax.set_xticklabels(["1e19", "1e22", "1e24"])
        ax.set_title(f"质量成本 = {form}")
        ax.set_ylabel("最优损失 L*")
        ax.grid(alpha=0.3, axis="y")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle("v83: 九框架跨框架求解对比 —— 全局最优一致性 (括号为最大相对偏差)",
                 fontsize=11, y=1.02)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(os.path.join(EX, "v83_p3_solver9.png"), dpi=200)
    plt.close(fig)

    n_all = sum(1 for a in agg if a["all_agree_1e6"])
    print(f"\n{len(AGREE_FW)}框架全部实例相对偏差<1e-6: {n_all}/{len(agg)}")
    print("done v83")


if __name__ == "__main__":
    main()