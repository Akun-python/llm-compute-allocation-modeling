# -*- coding: utf-8 -*-
"""
v36 实验: 质量-规模替代等值面 (P2 弹性可视化的直观版)
固定 D=300B, 画 L(N,Q) 等高线 (N in [0.1,10]B, Q in [0.4,1.0]):
1) 等损失曲线的切向斜率 = dQ/dN|_L = -eps_N*N/(eps_Q) 揭示替代率;
2) 标出基准点 (N=1B,Q=0.6) 与"质量+0.1 等价参数节省"轨迹.
输出: experiments/v36_p2_subst_contour.png/.json
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import BASE, RES

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
    p2 = json.load(open(os.path.join(RES, "p2_scaling_results.json"), encoding="utf-8"))
    prm = p2["generalized"]["forms"]["interaction_N"]["params"]
    p = [prm["E"], prm["A"], prm["a"], prm["B"], prm["b"], prm["C"], prm["g"], prm.get("h", 0.1627)]

    def L(N, Q, D=300.0):
        E, A, a, B_, b, C, gg, h = p
        return E + A * N ** (-a) + B_ * D ** (-b) + C * (1 - Q) ** gg * N ** (-h)

    Ns = np.linspace(0.1, 10, 200)
    Qs = np.linspace(0.4, 1.0, 120)
    Z = np.array([[L(n, q) for q in Qs] for n in Ns])

    fig, ax = plt.subplots(figsize=(9, 6.2))
    cf = ax.contourf(Ns, Qs, Z.T, levels=24, cmap="cyan_seq")
    cs = ax.contour(Ns, Qs, Z.T, levels=[2.2, 2.3, 2.4, 2.5, 2.6, 2.7],
                    colors="#3eede7", linewidths=1.3)
    ax.clabel(cs, inline=True, fontsize=9)
    ax.plot([1.0], [0.6], "o", ms=9, color="#1685a9", label="基准 (N=1B, Q=0.6)")
    # 等价轨迹: Q+0.1 -> N' (保持 L 不变)
    N0, Q0 = 1.0, 0.6
    L0 = L(N0, Q0)
    qs = np.linspace(Q0, 1.0, 20)
    nq = []
    for q in qs:
        lo, hi = 1e-3, N0
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            if L(mid, q) < L0:
                hi = mid
            else:
                lo = mid
        nq.append(0.5 * (lo + hi))
    ax.plot(nq, qs, "--", color="#44cef6", lw=2, label="等损失等价轨迹 (质量→规模替代)")
    ax.set_xlabel("参数量 N (B)"); ax.set_ylabel("数据质量 Q")
    ax.set_title("v36: 质量-规模替代等值面 (D=300B)")
    ax.legend(fontsize=9, loc="lower left")
    fig.colorbar(cf, ax=ax, label="L")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v36_p2_subst_contour.png"), dpi=200)
    plt.close(fig)

    # 替代率: dN/dQ at 基准
    h = 1e-4
    dN = (L(N0 * (1 + h), Q0) - L(N0, Q0)) / (h * N0)
    dQ = (L(N0, Q0 + h) - L(N0, Q0)) / h
    subst = -dQ / dN   # dN per dQ (保持 L)
    print(f"基准替代率 dN/dQ = {subst:.3f} B/单位Q (≈{subst*0.1:.3f}B 每+0.1Q)")
    with open(os.path.join(EX, "v36_p2_subst_contour.json"), "w", encoding="utf-8") as f:
        json.dump({"subst_dN_dQ": float(subst), "per_0p1Q": float(subst * 0.1)},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v36")


if __name__ == "__main__":
    main()