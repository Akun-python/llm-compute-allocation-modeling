# -*- coding: utf-8 -*-
"""
v31 实验: 最优解族随预算与质量成本形式的轨迹 (转移区间可视化)
对 g_cost 三种形式 (exp/power/log) 在 C=geomspace(1e18,1e25,12) 上求解:
1) Q*(C): 质量通道活跃区间与饱和点 (依成本形式而异);
2) N*(C), D*(C) 双对数: 规模通道幂律斜率与份额演变;
3) 转移定位: 质量主导 -> 混合 -> 纯规模 (Q 饱和) 的预算区间.
输出: experiments/v31_p3_solution_family.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import solve_opt
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


def main():
    Cs = np.geomspace(1e18, 1e25, 12)
    rows = []
    for form in ["exp", "power", "log"]:
        for C in Cs:
            r = solve_opt(C, form, 4096)
            if r is None:
                continue
            rows.append({"C": C, "form": form, "N": r["N"], "D": r["D"],
                         "Q": r["Q"], "L": r["L"],
                         "sN": r.get("share_N"), "sQ": r.get("share_Q")})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v31_p3_solution_family.csv"), index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    colors = {"exp": "#177cb0", "power": "#3eede7", "log": "#44cef6"}
    for form in ["exp", "power", "log"]:
        sub = rdf[rdf["form"] == form]
        axes[0].plot(sub["C"], sub["Q"], "o-", lw=1.8, color=colors[form], label=form)
        axes[1].loglog(sub["C"], sub["N"], "o-", lw=1.8, color=colors[form], label=form)
        axes[2].loglog(sub["C"], sub["D"], "s--", lw=1.5, color=colors[form], label=form)
    axes[0].set_xscale("log"); axes[0].set_ylim(0.3, 1.05)
    axes[0].set_xlabel("预算 C"); axes[0].set_ylabel("最优质量 Q*")
    axes[0].set_title("(a) 质量通道活跃区间")
    axes[1].set_xlabel("预算 C"); axes[1].set_ylabel("最优参数量 N* (B)")
    axes[1].set_title("(b) 规模通道")
    axes[2].set_xlabel("预算 C"); axes[2].set_ylabel("最优数据 D* (B)")
    axes[2].set_title("(c) 数据通道")
    for ax in axes:
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.suptitle("v31: 最优解族随预算轨迹 (成本形式决定转移区间)", y=1.03)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v31_p3_solution_family.png"), dpi=200)
    plt.close(fig)

    # 饱和预算 (Q*>=0.999 的最小 C)
    sat = rdf[rdf["Q"] >= 0.999].groupby("form")["C"].min().to_dict()
    print("Q 饱和预算(首档):", {k: f"{v:.1e}" for k, v in sat.items()})
    with open(os.path.join(EX, "v31_p3_solution_family.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rdf.to_dict("records"), "q_sat_budget": sat},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v31")


if __name__ == "__main__":
    main()