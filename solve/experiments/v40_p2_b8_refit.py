# -*- coding: utf-8 -*-
"""
v40 实验: B8 外推补充的参数级复核 (方向诊断形式化)
B8 (supplementary_NQ_experiment*) 与 B6/B7 同构但 Q 方向相反
(组内相关 +0.98 vs -0.93). 本实验:
1) 在 B8 (原样) 上拟合 6 种形式, 报告 interaction_N 参数与符号;
2) 与 B6+B7 全样本参数逐项对比: a/b/g/h 的漂移量;
3) 结论: B8 的 Q 系"逆向质量分", 直接拟合会产生符号翻转/退化参数
   (C<0 或 g 越界), 排除其进入主拟合的统计依据.
输出: experiments/v40_p2_b8_refit.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from v3_p2_forms import load_b67, loss_forms, fit_form
FORMS = ["additive", "interaction_D", "interaction_N", "multiplicative", "saturating", "exponential_Q"]
from common import B, BASE

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


def load_b8():
    cols = ["N_params_B", "D_tokens_B", "Q_score", "val_loss"]
    parts = []
    for f in ["supplementary_NQ_experiment.csv",
              "supplementary_NQ_experiment_expanded.csv",
              "supplementary_NQ_experiment_large.csv"]:
        d = pd.read_csv(os.path.join(B, f))
        parts.append(d[cols].dropna())
    df = pd.concat(parts, ignore_index=True)
    return (df["N_params_B"].to_numpy(dtype=float),
            df["D_tokens_B"].to_numpy(dtype=float),
            df["Q_score"].to_numpy(dtype=float),
            df["val_loss"].to_numpy(dtype=float))


def main():
    df67 = load_b67()
    N6 = df67["N_params_B"].to_numpy(dtype=float)
    D6 = df67["D_tokens_B"].to_numpy(dtype=float)
    Q6 = df67["Q_score"].to_numpy(dtype=float)
    L6 = df67["val_loss"].to_numpy(dtype=float)
    N8, D8, Q8, L8 = load_b8()
    forms = FORMS
    p_67 = fit_form(N6, D6, Q6, L6, "interaction_N")[0]
    p_8 = fit_form(N8, D8, Q8, L8, "interaction_N")[0]
    names = ["E", "A", "a", "B", "b", "C", "g", "h"]
    print("B6+B7 (n=%d):" % len(L6))
    for k, v in zip(names, p_67):
        print(f"  {k} = {v:.4f}")
    print("B8 原样 (n=%d):" % len(L8))
    for k, v in zip(names, p_8):
        print(f"  {k} = {v:.4f}")

    rows = [{"param": k, "b67": float(v67), "b8": float(v8),
             "delta": float(v8 - v67)} for k, v67, v8 in zip(names, p_67, p_8)]
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v40_p2_b8_refit.csv"), index=False, encoding="utf-8-sig")

    print("\n6 形式在 B8 上的 R2:")
    for fm in forms:
        r2 = fit_form(N8, D8, Q8, L8, fm)[1]
        print(f"  {fm}: {r2:.4f}")

    fig, ax = plt.subplots(figsize=(8, 4.6))
    x = np.arange(len(names))
    w = 0.36
    ax.bar(x - w/2, p_67, w, color="#177cb0", label="B6+B7")
    ax.bar(x + w/2, p_8, w, color="#3eede7", label="B8 (原样)")
    ax.axhline(0, color="#88ada6", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels(names)
    ax.set_ylabel("参数值"); ax.set_title("v40: interaction_N 在 B6+B7 vs B8 的参数复核")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v40_p2_b8_refit.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v40_p2_b8_refit.json"), "w", encoding="utf-8") as f:
        json.dump({"b67": dict(zip(names, p_67)), "b8": dict(zip(names, p_8)),
                   "r2_b8_forms": {fm: fit_form(N8, D8, Q8, L8, fm)[1] for fm in forms}},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v40")


if __name__ == "__main__":
    main()