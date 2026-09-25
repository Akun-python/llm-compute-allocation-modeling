# -*- coding: utf-8 -*-
"""
v66 实验: 六种形式的参数一致性
B6+B7 上分别拟合六形式, 抽取共享参数 (E/A/a/B/b/C/g) 跨形式对比:
1) 规模弹性 a (N指数) 与 b (D指数) 是否跨形式稳定;
2) g (质量弹性) 在两族 ((1-Q)^g vs exp(-gQ)) 的语义差异;
3) 结论: 弹性是数据性质而非形式产物.
输出: experiments/v66_p2_form_params.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from v3_p2_forms import load_b67, fit_form, PARAM_NAMES
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

FORMS = ["additive", "interaction_D", "interaction_N", "multiplicative",
         "saturating", "exponential_Q"]


def main():
    df = load_b67()
    N = df["N_params_B"].to_numpy(dtype=float)
    D = df["D_tokens_B"].to_numpy(dtype=float)
    Q = df["Q_score"].to_numpy(dtype=float)
    L = df["val_loss"].to_numpy(dtype=float)

    rows = []
    for form in FORMS:
        p, r2 = fit_form(N, D, Q, L, form)
        names = PARAM_NAMES[form]
        row = {"form": form, "r2": float(r2)}
        for k, v in zip(names, p):
            row[k] = float(v)
        rows.append(row)
        print(f"{form:15s} R2={r2:.4f} a={row.get('a', float('nan')):.3f} "
              f"b={row.get('b', float('nan')):.3f} E={row['E']:.3f} g={row.get('g', float('nan')):.3f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v66_p2_form_params.csv"), index=False, encoding="utf-8-sig")

    a = rdf["a"].to_numpy(); b = rdf["b"].to_numpy()
    print(f"\na 跨形式: 均值 {a.mean():.3f} 范围 [{a.min():.3f}, {a.max():.3f}] CV {a.std()/a.mean()*100:.1f}%")
    print(f"b 跨形式: 均值 {b.mean():.3f} 范围 [{b.min():.3f}, {b.max():.3f}] CV {b.std()/b.mean()*100:.1f}%")
    gp = rdf[rdf["form"] != "exponential_Q"]["g"]
    print(f"(1-Q)^g 族 g: 均值 {gp.mean():.3f} 范围 [{gp.min():.3f}, {gp.max():.3f}]")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for i, (name, vals) in enumerate([("a (N 弹性)", a), ("b (D 弹性)", b)]):
        axes[i].bar(range(len(FORMS)), vals, color="#177cb0", alpha=0.85)
        axes[i].axhline(vals.mean(), color="#3eede7", lw=1.2, ls="--", label=f"均值 {vals.mean():.3f}")
        axes[i].set_xticks(range(len(FORMS))); axes[i].set_xticklabels(FORMS, rotation=25, fontsize=7)
        axes[i].set_ylabel(name); axes[i].set_title(f"{name} 跨形式稳定性 (CV {vals.std()/vals.mean()*100:.1f}%)")
        axes[i].legend(fontsize=8); axes[i].grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v66_p2_form_params.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v66_p2_form_params.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows,
                   "a_mean": float(a.mean()), "a_cv_pct": float(a.std()/a.mean()*100),
                   "b_mean": float(b.mean()), "b_cv_pct": float(b.std()/b.mean()*100)},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v66")


if __name__ == "__main__":
    main()