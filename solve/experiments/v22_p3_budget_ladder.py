# -*- coding: utf-8 -*-
"""
v22 实验: 预算-最优损失的规模经济 (budget ladder)
对 C ∈ {1e18..1e25} 用 exp/power/log 三种质量成本形式求最优 (N*,D*,Q*,L*),
拟合 ln(L*-E) vs ln C (对数线性), 给出"预算每翻倍最优损失下降比例"的弹性.
跨形式对比: 预算的规模经济是否与质量成本形式无关?
输出: experiments/v22_p3_budget_ladder.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import solve_opt, GL, G_FORMS
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

E = GL["E"]
Cs = np.geomspace(1e18, 1e25, 8)


def main():
    rows = []
    fits = {}
    for form in G_FORMS:
        for C in Cs:
            r = solve_opt(C, form, 4096)
            if r is None:
                continue
            rows.append({"form": form, "C": C, "L": r["L"], "N": r["N"],
                         "D": r["D"], "Q": r["Q"], "s_train": r["C_train"] / C,
                         "s_Q": r["C_Q"] / C, "s_attn": r["C_attn"] / C})
        df = pd.DataFrame([r for r in rows if r["form"] == form])
        lx, ly = np.log(df["C"]), np.log(df["L"] - E)
        k, b = np.polyfit(lx, ly, 1)
        r2 = 1 - np.sum((ly - (k * lx + b)) ** 2) / np.sum((ly - ly.mean()) ** 2)
        fits[form] = {"slope": float(k), "r2": float(r2),
                      "double_halving_pct": float((1 - 2 ** k) * 100)}
        print(f"{form}: ln(L*-E) vs lnC slope={k:.4f} R2={r2:.4f} "
              f"=> 预算翻倍损失下降 {(1-2**k)*100:.1f}%")

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v22_p3_budget_ladder.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8, 6))
    for form in G_FORMS:
        d = rdf[rdf["form"] == form]
        ax.plot(d["C"], d["L"] - E, "o-", lw=2, label=form)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("总预算 C (FLOPs)"); ax.set_ylabel("最优剩余损失 L* - E")
    ax.set_title("v22: 预算规模经济 (三种质量成本形式)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v22_p3_budget_ladder.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v22_p3_budget_ladder.json"), "w", encoding="utf-8") as f:
        json.dump({"fits": fits, "rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v22")


if __name__ == "__main__":
    main()