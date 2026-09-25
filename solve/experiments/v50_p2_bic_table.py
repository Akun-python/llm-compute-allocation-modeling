# -*- coding: utf-8 -*-
"""
v50 实验: 六种广义标度律形式的 BIC/AIC 模型选择
对 B6+B7 (n=810) 拟合六形式, 报告:
1) R2/RSS/参数个数 k/BIC/AIC 与相对最优的 deltaBIC;
2) 依据 (Burnham & Anderson): deltaBIC<2 等价, 2-6 弱证据, >6 强证据,
   >10 决定性 => interaction_N 的选择是否信息准则下成立.
输出: experiments/v50_p2_bic_table.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from v3_p2_forms import load_b67, loss_forms, fit_form
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

# 各形式参数个数: E, A, a, B, b, C, g (+h 仅 interaction_*)
K = {"additive": 7, "interaction_D": 8, "interaction_N": 8, "multiplicative": 7,
     "saturating": 7, "exponential_Q": 7}
FORMS = ["additive", "interaction_D", "interaction_N", "multiplicative",
         "saturating", "exponential_Q"]


def main():
    df = load_b67()
    N = df["N_params_B"].to_numpy(dtype=float)
    D = df["D_tokens_B"].to_numpy(dtype=float)
    Q = df["Q_score"].to_numpy(dtype=float)
    L = df["val_loss"].to_numpy(dtype=float)
    n = len(L)
    rows = []
    for form in FORMS:
        p, r2 = fit_form(N, D, Q, L, form)
        Lp = loss_forms(N, D, Q, p, form)
        rss = float(np.sum((L - Lp) ** 2))
        k = K[form]
        bic = n * np.log(rss / n) + k * np.log(n)
        aic = n * np.log(rss / n) + 2 * k
        rows.append({"form": form, "k": k, "r2": float(r2), "rss": rss,
                     "bic": bic, "aic": aic})
        print(f"{form:16s} k={k} R2={r2:.4f} BIC={bic:.2f} AIC={aic:.2f}")
    rdf = pd.DataFrame(rows).sort_values("bic")
    rdf["dBIC"] = rdf["bic"] - rdf["bic"].min()
    rdf["dAIC"] = rdf["aic"] - rdf["aic"].min()
    rdf.to_csv(os.path.join(EX, "v50_p2_bic_table.csv"), index=False, encoding="utf-8-sig")
    print("\n排序 (BIC):")
    print(rdf.round(2).to_string(index=False))
    best = rdf.iloc[0]
    print(f"\n最优: {best['form']} (dBIC=0); 次优 dBIC={rdf.iloc[1]['dBIC']:.2f} => "
          f"{'决定性证据' if rdf.iloc[1]['dBIC']>10 else '强证据' if rdf.iloc[1]['dBIC']>6 else '弱证据'}")

    fig, ax = plt.subplots(figsize=(9, 5))
    pos = np.arange(len(rdf))
    ax.barh(pos, rdf["dBIC"], color="#177cb0", alpha=0.85)
    ax.set_yticks(pos); ax.set_yticklabels(rdf["form"])
    ax.set_xlabel("dBIC (相对最优)"); ax.set_title("v50: 六形式信息准则选择")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v50_p2_bic_table.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v50_p2_bic_table.json"), "w", encoding="utf-8") as f:
        json.dump({"n": int(n), "rows": rows,
                   "best": best["form"], "second_dBIC": float(rdf.iloc[1]["dBIC"])},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v50")


if __name__ == "__main__":
    main()