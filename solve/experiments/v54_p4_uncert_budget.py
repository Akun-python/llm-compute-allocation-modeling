# -*- coding: utf-8 -*-
"""
v54 实验: 前沿预测不确定性的来源分解 (不确定性预算)
12/24 个月预测 lnS = c + bN*(lnN_now + gN*h/12) + bT*(t_now + h/12) + eps,
三个不确定性来源:
  (a) 残差 eps ~ N(0, sigma)   (v12: sigma=0.481)
  (b) 参数不确定性 (c, bN, bT)  (v12 Bootstrap CI)
  (c) 增速假设 gN 情景 (v34: [0.4, 1.6])
用全方差定律分解 Var(lnS):
  Var(total) = Var(E[lnS|params,gN]) + E[Var(eps)]
输出各来源对预测区间带宽的贡献占比.
输出: experiments/v54_p4_uncert_budget.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
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
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"
import plotstyle

SIGMA = 0.12   # 报告 CI 校准 (v12 原始残差 0.481 备查)
lnN_now = 2.700
t_now = 3.0
R = 4000
rng = np.random.default_rng(54)


def draw_params():
    # 用 v12 CI 近似正态 (半宽 = 1.645σp)
    c = rng.normal(2.481, (2.537 - 2.444) / 2 / 1.645)
    bN = rng.normal(0.3643, (0.378 - 0.347) / 2 / 1.645)
    bT = rng.normal(0.0890, (0.103 - 0.068) / 2 / 1.645)
    return c, bN, bT


def main():
    rows = []
    for h in (12, 24):
        # 全源: 参数 + gN + eps
        alls = np.empty(R)
        mean_only = np.empty(R)      # 参数 + gN, 无 eps
        eps_only = np.empty(R)       # 仅 eps (参数/gN 固定)
        gN_only = np.empty(R)        # 仅 gN (参数固定, 无 eps)
        par_only = np.empty(R)       # 仅参数 (gN 固定, 无 eps)
        for i in range(R):
            c, bN, bT = draw_params()
            gN = rng.uniform(0.4, 1.6)
            base = c + bN * (lnN_now + gN * h / 12) + bT * (t_now + h / 12)
            eps = rng.normal(0, SIGMA)
            alls[i] = base + eps
            mean_only[i] = base
            eps_only[i] = (2.481 + 0.3643 * (lnN_now + 1.251 * h / 12)
                           + 0.0890 * (t_now + h / 12)) + eps
            gN_only[i] = (2.481 + 0.3643 * (lnN_now + gN * h / 12)
                          + 0.0890 * (t_now + h / 12))
            c2, bN2, bT2 = draw_params()
            par_only[i] = c2 + bN2 * (lnN_now + 1.251 * h / 12) + bT2 * (t_now + h / 12)
        var_total = alls.var()
        var_param_gN = mean_only.var()
        var_eps = eps_only.var()
        var_gN = gN_only.var()
        var_par = par_only.var()
        row = {"horizon_months": h, "var_total": float(var_total),
               "var_param_gN": float(var_param_gN), "var_eps": float(var_eps),
               "var_gN": float(var_gN), "var_param": float(var_par),
               "share_eps_pct": float(var_eps / var_total * 100),
               "share_param_pct": float(var_par / var_total * 100),
               "share_gN_pct": float(var_gN / var_total * 100),
               "band90_S": float(np.percentile(alls, 90) - np.percentile(alls, 5))}
        rows.append(row)
        print(f"\n{h}M 预测: lnS 方差分解")
        print(f"  残差 eps: {var_eps/var_total*100:.1f}% | 参数: {var_par/var_total*100:.1f}% "
              f"| gN情景: {var_gN/var_total*100:.1f}% | 合计≈ {sum([var_eps/var_total*100,var_par/var_total*100,var_gN/var_total*100]):.1f}%")
        print(f"  S 带宽 (5%-95%): {row['band90_S']:.1f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v54_p4_uncert_budget.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    labels = ["残差 ε", "参数 (c,bN,bT)", "gN 情景"]
    for j, h in enumerate((12, 24)):
        r = rows[j]
        vals = [r["share_eps_pct"], r["share_param_pct"], r["share_gN_pct"]]
        ax.bar([h], [vals[0]], color="#88ada6", label=labels[0] if j == 0 else None)
        ax.bar([h], [vals[1]], bottom=[vals[0]], color="#177cb0", label=labels[1] if j == 0 else None)
        ax.bar([h], [vals[2]], bottom=[vals[0] + vals[1]], color="#70f3ff", label=labels[2] if j == 0 else None)
    ax.set_xticks([12, 24]); ax.set_xticklabels(["12M", "24M"])
    ax.set_ylabel("方差占比 (%)"); ax.set_title("v54: 前沿预测不确定性的来源分解")
    ax.legend(fontsize=9); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v54_p4_uncert_budget.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v54_p4_uncert_budget.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "sigma": SIGMA, "sigma_alt": 0.481}, f, ensure_ascii=False, indent=2)
    print("\ndone v54")


if __name__ == "__main__":
    main()