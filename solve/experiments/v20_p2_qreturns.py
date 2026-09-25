# -*- coding: utf-8 -*-
"""
v20 实验: 质量投资回报随模型规模的衰减 (interaction_N 语义可视化)
固定 D=300B, 扫 Q∈[0.4,1], 对 N∈{0.1,1,10,100,1000}B 画 L(Q) 曲线;
量化:
1) 质量全幅收益 (Q 0.4->1.0 的 dL) 随 N 的衰减 — interaction_N 的
   N^-h 项使"模型越大对质量缺口越不敏感".
2) 质量弹性 dL/dQ at Q=0.6 随 N 变化 (log-log 斜率 ≈ h).
3) 等效参数: Q 0.4->0.6 相当于参数增加多少倍, 随 N 变化.
输出: experiments/v20_p2_qreturns.png/.json/.csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import loss_generalized, GL
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
    D = 300.0
    Ns = [0.1, 1.0, 10.0, 100.0, 1000.0]
    Qs = np.linspace(0.4, 1.0, 61)
    a = GL["a"]
    Lref = loss_generalized(1.0, D, 0.4)

    rows = []
    fig, ax = plt.subplots(figsize=(9, 6))
    for N in Ns:
        Ls = np.array([loss_generalized(N, D, Q) for Q in Qs])
        rows.append({"N": N, "L_q04": float(loss_generalized(N, D, 0.4)),
                     "L_q10": float(loss_generalized(N, D, 1.0)),
                     "gain_full": float(loss_generalized(N, D, 0.4) - loss_generalized(N, D, 1.0)),
                     "dLdQ_q06": float((loss_generalized(N, D, 0.62) - loss_generalized(N, D, 0.58)) / 0.04)})
        ax.plot(Qs, Ls - loss_generalized(N, D, 1.0), lw=2, label=f"N={N}B")
    ax.set_xlabel("质量 Q"); ax.set_ylabel("L(Q) - L(Q=1.0)")
    ax.set_title("质量投资回报曲线 (D=300B, interaction_N)")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v20_p2_qreturns.png"), dpi=200); plt.close(fig)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(EX, "v20_p2_qreturns.csv"), index=False, encoding="utf-8-sig")
    print(df.round(4).to_string(index=False))

    # 质量弹性 vs N (log-log 斜率近似 h)
    x = np.log(np.array(df["N"]))
    y = np.log(np.abs(np.array(df["dLdQ_q06"])))
    hhat = np.polyfit(x, y, 1)[0]
    print(f"\n质量弹性 dL/dQ 随 N 的 log-log 斜率 = {hhat:.3f} (理论 h={GL['h']:.3f})")

    # 等效参数节省 (Q 0.4->0.6 使 L 不变所需的模型更小): 找 N'<N 使
    # L(N',D,0.6) = L(N,D,0.4)
    eq = []
    for N in Ns:
        target = loss_generalized(N, D, 0.4)
        lo, hi = 0.001 * N, N
        for _ in range(80):
            mid = np.sqrt(lo * hi)
            if loss_generalized(mid, D, 0.6) > target:
                lo = mid
            else:
                hi = mid
        n_eq = np.sqrt(lo * hi)
        eq.append({"N": N, "N_equiv_smaller": float(n_eq),
                   "param_saving": float(N / n_eq)})
    edf = pd.DataFrame(eq)
    print("\n等效参数节省 (Q 0.4->0.6 的收益等价于可缩小模型倍数):")
    print(edf.round(3).to_string(index=False))

    out = {"dLdQ_loglog_slope": float(hhat), "h_ref": GL["h"], "curves": df.to_dict("records"),
           "equiv": edf.to_dict("records")}
    with open(os.path.join(EX, "v20_p2_qreturns.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\ndone v20")


if __name__ == "__main__":
    main()