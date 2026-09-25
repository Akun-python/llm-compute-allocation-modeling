# -*- coding: utf-8 -*-
"""
v68 实验: 能力目标->训练算力->工程规模的落地换算
P4 QR90 主链路 (lnS = 2.481 + 0.364 lnN + 0.089 t, 整数年 t=year-2022):
1) 给定 2025 年 (t=3) 的能力目标 S, 反解所需前沿参数量 N;
2) 用 v24 数据最优曲线 D*(N)=49.8 N^1.046 得 D, 训练算力 C_train=6e18 N D;
3) 换算为 H100 卡天数 (单卡 ~8.6e19 FLOP/天) 与万卡天数;
4) 对照: P3 最优解 C=1e22 对应的算力需求.
输出: experiments/v68_p4_compute_conversion.csv/.json/.png
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

B0 = 2.481
BN = 0.364
BT = 0.089
T = 3  # 2025
H100_DAY = 8.6e19  # FLOP/card/day
D_CURVE = (49.8, 1.046)  # D = k N^p (v24)
TARGETS = [60, 70, 80, 90, 100, 120, 150]


def main():
    rows = []
    for S in TARGETS:
        lnN = (np.log(S) - B0 - BT * T) / BN
        N = float(np.exp(lnN))
        D = D_CURVE[0] * N ** D_CURVE[1]
        C_train = 6e18 * N * D
        card_days = C_train / H100_DAY
        rows.append({"S": S, "N_B": N, "D_B": D, "C_train_FLOP": C_train,
                     "H100_card_days": card_days, "wan_card_days": card_days / 1e4})
        print(f"S={S:>3} -> N={N:8.1f}B D={D:8.0f}B | C_train={C_train:.2e} FLOP | "
              f"H100 卡天 {card_days:.0f} (万卡 {card_days/1e4:.1f} 天)")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v68_p4_compute_conversion.csv"), index=False, encoding="utf-8-sig")

    # P3 对照: C=1e22 最优解算力
    c22_N, c22_D = 6.13, 238.0  # v62 中位
    c22_flop = 6e18 * c22_N * c22_D
    print(f"\nP3 对照 C=1e22 最优解: N*={c22_N}B D*={c22_D}B -> C_train={c22_flop:.2e} FLOP "
          f"(H100 卡天 {c22_flop/H100_DAY:.0f})")

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.plot(rdf["S"], rdf["C_train_FLOP"], marker="o", color="#177cb0", lw=1.8)
    ax.set_yscale("log")
    ax.set_xlabel("能力目标 S (前沿平均分)"); ax.set_ylabel("训练算力 C_train (FLOP, log)")
    ax2 = ax.twinx()
    ax2.plot(rdf["S"], rdf["H100_card_days"], marker="s", color="#3eede7", lw=1.2, ls="--")
    ax2.set_ylabel("H100 卡天数 (log)", color="#3eede7")
    ax2.tick_params(axis="y", labelcolor="#3eede7")
    ax2.set_yscale("log")
    ax.set_title(f"能力目标->训练算力->工程规模 (2025, 整数年口径)")
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v68_p4_compute_conversion.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v68_p4_compute_conversion.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "p3_ref": {"C": 1e22, "N_B": c22_N, "D_B": c22_D,
                    "C_train_FLOP": c22_flop, "H100_card_days": c22_flop / H100_DAY}},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v68")


if __name__ == "__main__":
    main()