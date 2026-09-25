# -*- coding: utf-8 -*-
"""
v51 实验: 质量-参数替代率随规模的演化
在 interaction_N 律下, 等损失面上的局部替代率 (隐函数定理):
  dN/dQ = -L_Q/L_N
  L_N = -a A N^{-a-1} - h C (1-Q)^g N^{-h-1}
  L_Q = -C g (1-Q)^{g-1} N^{-h}
沿 N in [0.3, 3]B (固定 Q=0.6) 与沿最优曲线 D=D*(N) 两条路径评估:
1) 每 0.1Q 等价参数 (B): 0.1*(-dN/dQ);
2) 替代率随规模的演化方向 (质量购买力随规模升/降);
3) 与 v36 参考点 (-0.243B/+0.1Q) 对照.
输出: experiments/v51_p2_subst_scale.csv/.json/.png
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

# interaction_N 参数 (B6+B7 全样本, 与 p2_scaling_results.json 一致)
E, A, a, B_, b, C, g, h = (1.6397, 0.4039, 0.3055, 1.3228, 0.2921,
                           0.3563, 0.9912, 0.1627)
Q0 = 0.6


def dN_dQ(N, Q=Q0):
    L_N = -a * A * N ** (-a - 1) - h * C * (1 - Q) ** g * N ** (-h - 1)
    L_Q = -C * g * (1 - Q) ** (g - 1) * N ** (-h)
    return -L_Q / L_N


def dstar(N):
    k = (b * B_ / (a * A)) ** (1 / b)
    return k * N ** (a / b)


def main():
    Ns = np.linspace(0.3, 3.0, 28)
    rows = []
    for N in Ns:
        eq_fix = 0.1 * (-dN_dQ(N))          # 每 +0.1Q 可减少的参数 (B)
        D = dstar(N)
        eq_opt = 0.1 * (-dN_dQ(N))          # 沿 D*(N) 同 N 处 (替代率与 D 无关)
        rows.append({"N": float(N), "Dstar": float(D), "eq_0.1Q_B_fixD": float(eq_fix),
                     "eq_0.1Q_B_optD": float(eq_opt)})
        print(f"N={N:.2f}B D*={D:6.1f} | 每+0.1Q 等价减少 {eq_fix:+.3f}B 参数")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v51_p2_subst_scale.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(Ns, rdf["eq_0.1Q_B_fixD"], color="#177cb0", lw=2, marker="o", ms=4,
            label="每 +0.1Q 等价减少参数 (B)")
    ax.axhline(0.243, color="#3eede7", lw=1.4, ls="--", label="v36 参考点 0.243B/0.1Q")
    ax.set_xlabel("N (B)"); ax.set_ylabel("等价参数 (B) / +0.1Q")
    ax.set_title("v51: 质量-参数替代率随规模的演化 (Q=0.6, interaction_N)")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v51_p2_subst_scale.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v51_p2_subst_scale.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "N_ref": 1.0, "eq_ref": float(0.1 * (-dN_dQ(1.0))),
                   "trend": "上升" if rows[-1]["eq_0.1Q_B_fixD"] > rows[0]["eq_0.1Q_B_fixD"] else "下降"},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v51")


if __name__ == "__main__":
    main()