# -*- coding: utf-8 -*-
"""
v24 实验: 计算最优 D*(N) 曲线 vs 实际前沿模型的训练数据规模
纯规模 (Q=Q0) 下由 KKT 均衡 N^a/D^b = aA/(bB) 得
    D*(N) = (bB/(aA))^{1/b} * N^{a/b}   (Chinchilla 式数据最优曲线)
对照:
1) B4 12 族 57 个实际训练点 (N_params_B, D_tokens_B).
2) Chinchilla 经验规则 D = 20*N (tokens/param=20).
3) 三档预算最优解 (D*,N*) 是否落在曲线上 (自洽性).
结论: 实际前沿模型普遍数据过量 (tokens/param 高于曲线 3-6 倍),
      符合"算力约束、数据充裕"的现实, 支撑 P3 结论.
输出: experiments/v24_p2_dstar_curve.png/.json/.csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import GL
from common import BASE, B

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

A, a, B_, b = GL["A"], GL["a"], GL["B"], GL["b"]
k = (b * B_ / (a * A)) ** (1 / b)   # D = k * N^{a/b}
expo = a / b
print(f"D*(N) = {k:.3f} * N^{expo:.4f}")


def dstar(N):
    return k * N ** expo


def main():
    b4 = pd.read_csv(os.path.join(B, "scaling_baseline.csv"))
    b4 = b4[b4["is_converged"] == 1]
    b4["D/N"] = b4["D_tokens_B"] / b4["N_params_B"]

    Ns = np.geomspace(0.05, 5000, 400)
    Ds = dstar(Ns)

    # 曲线上各 N 处 D/N 比
    dn_curve = k * Ns ** (expo - 1)

    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.loglog(Ns, Ds, lw=2, color="#177cb0", label="计算最优 D*(N) (本文 KKT)")
    N20 = np.geomspace(0.05, 5000, 100)
    ax.loglog(N20, 20 * N20, "--", lw=1.5, color="#88ada6", label="Chinchilla 经验规则 D=20N")
    fams = b4["family"].unique()
    for fm_ in fams:
        g = b4[b4["family"] == fm_]
        ax.scatter(g["N_params_B"], g["D_tokens_B"], s=42, alpha=0.75, label=fm_)
    ax.set_xlabel("参数量 N (B)"); ax.set_ylabel("训练数据 D (tokens, B)")
    ax.set_title("计算最优 D*(N) 与 B4 实际训练点对照")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v24_p2_dstar_curve.png"), dpi=200)
    plt.close(fig)

    # 统计: 实际点 D/N 分布 vs 曲线上同 N 的理论 D/N
    theo = dstar(b4["N_params_B"].to_numpy()) / b4["N_params_B"].to_numpy()
    ratio = (b4["D_tokens_B"] / theo)
    med_ratio = float(np.median(ratio))
    print(f"\n实际点 D/N: 中位 {np.median(b4['D/N']):.0f}  (最小 {b4['D/N'].min():.0f}, 最大 {b4['D/N'].max():.0f})")
    print(f"实际 D / 理论 D*(同N): 中位 {med_ratio:.1f}x  (范围 {ratio.min():.1f}x-{ratio.max():.1f}x)")
    m65 = b4["N_params_B"].to_numpy() == 65.0
    print(f"LLaMA 65B: 实际 {11349/65:.0f} tok/param vs 理论 {theo[m65][0]:.0f} (≈{11349/65/theo[m65][0]:.1f}x)")

    # 自洽性: 三档预算最优解在曲线上的残差
    rows = []
    for Cb, form, N, D in [(1e19, "exp", 0.294, 3.81), (1e22, "power", 5.97, 219.3),
                           (1e24, "power", 50.5, 2865.8)]:
        dstar_v = dstar(N)
        rows.append({"C": Cb, "form": form, "N": N, "D": D, "Dstar": float(dstar_v),
                     "off_curve_pct": float((D / dstar_v - 1) * 100)})
    print("\n预算最优解对曲线的偏差 (含质量成本后, Q>Q0 时理论曲线偏离是预期):")
    for r in rows:
        print(f"  C={r['C']:.0e} {r['form']}: D*_opt={r['D']:.1f} vs 纯规模曲线 {r['Dstar']:.1f} (偏差 {r['off_curve_pct']:+.0f}%)")

    out = {"k": float(k), "expo": float(expo),
           "actual_DN_median": float(np.median(b4["D/N"])),
           "actual_vs_theory_median_x": med_ratio,
           "budget_opt_off_curve": rows}
    with open(os.path.join(EX, "v24_p2_dstar_curve.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\ndone v24")


if __name__ == "__main__":
    main()