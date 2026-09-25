# -*- coding: utf-8 -*-
"""
v71 实验: 前沿的规模-时间等能力线
QR90 主链路 lnS = 2.481 + 0.364 lnN + 0.089 t:
1) S 目标 {60,70,80,90} 的 (lnN, t) 等值线 (t 整数年 2..5);
2) 边际替代率 d lnN/dt = -bT/bN: 每等一年可少用多少参数;
3) 结论: 算力约束下时间与规模可互换 (时间折现的量化).
输出: experiments/v71_p4_isoquant.csv/.json/.png
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

B0, BN, BT = 2.481, 0.364, 0.089
TARGETS = [60, 70, 80, 90, 100]
TS = np.linspace(2, 5, 121)


def main():
    mrs = -BT / BN
    print(f"边际替代率 d lnN/dt = {mrs:.3f} => 每等1年可少用 {np.exp(mrs)-1:.0%} 参数 "
          f"(或提前1年需 {np.exp(-mrs)-1:.0%} 更多参数)")
    rows = []
    for S in TARGETS:
        lnN = np.log(S) - B0 - BT * TS
        for t, ln in zip(TS[::30], lnN[::30]):
            rows.append({"S": S, "t": float(t), "lnN": float(ln), "N_B": float(np.exp(ln))})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v71_p4_isoquant.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for S in TARGETS:
        lnN = np.log(S) - B0 - BT * TS
        ax.plot(TS, lnN, lw=1.8, marker="o", ms=3, label=f"S={S}")
    ax.set_xlabel("年份 t (2022=0, 整数年口径)"); ax.set_ylabel("ln N (对数参数量)")
    ax.set_title(f"v71: 规模-时间等能力线 (斜率 {mrs:.3f}: 等1年少22%参数)")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v71_p4_isoquant.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v71_p4_isoquant.json"), "w", encoding="utf-8") as f:
        json.dump({"mrs_lnN_t": mrs, "one_year_param_saving_pct": float(np.exp(mrs) - 1), "one_year_early_premium_pct": float(np.exp(-mrs) - 1),
                   "rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v71")


if __name__ == "__main__":
    main()