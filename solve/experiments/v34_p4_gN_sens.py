# -*- coding: utf-8 -*-
"""
v34 实验: 前沿预测对增速假设 gN 的敏感性 (tornado)
S_12(gN) = exp(c0 + bN(lnN90 + gN) + bT(t0+1))
S_24(gN) = exp(c0 + bN(lnN90 + 2 gN) + bT(t0+2))
扫 gN ∈ {0.4..1.6}, 报告 12/24 个月前沿对 gN 的跨度,
与分位数 tau/分解口径等其它不确定性来源对比.
输出: experiments/v34_p4_gN_sens.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import RES, BASE

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
    p4 = json.load(open(os.path.join(RES, "p4_results.json"), encoding="utf-8"))
    q = p4["frontier_qr"]
    c0, bN, bT, lnN90 = q["c0"], q["bN"], q["bT"], 2.700
    t0 = 3.0  # 2025-03
    gN_base = p4["gN"]
    print(f"QR: lnS={c0:.3f}+{bN:.3f}lnN+{bT:.3f}t, lnN90={lnN90}, gN={gN_base:.3f}")

    gs = [0.4, 0.6, 0.8, 1.0, gN_base, 1.4, 1.6]
    gs = sorted(set(gs))
    rows = []
    for g in gs:
        s12 = np.exp(c0 + bN * (lnN90 + g) + bT * (t0 + 1))
        s24 = np.exp(c0 + bN * (lnN90 + 2 * g) + bT * (t0 + 2))
        rows.append({"gN": g, "S_12": float(s12), "S_24": float(s24)})
        print(f"gN={g:.2f}: S_12={s12:.1f}  S_24={s24:.1f}")
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v34_p4_gN_sens.csv"), index=False, encoding="utf-8-sig")

    s12b = rdf[rdf["gN"] == gN_base]["S_12"].iloc[0]
    s24b = rdf[rdf["gN"] == gN_base]["S_24"].iloc[0]
    span12 = (rdf["S_12"].max() - rdf["S_12"].min()) / s12b
    span24 = (rdf["S_24"].max() - rdf["S_24"].min()) / s24b
    print(f"跨度: 12个月 ±{span12*100:.0f}% | 24个月 ±{span24*100:.0f}%")

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.plot(rdf["gN"], rdf["S_12"], "o-", lw=2, color="#177cb0", label="12 个月前沿 S")
    ax.plot(rdf["gN"], rdf["S_24"], "s-", lw=2, color="#3eede7", label="24 个月前沿 S")
    ax.axvline(gN_base, ls=":", color="#44cef6", label=f"基准 gN={gN_base:.2f}")
    for _, r in rdf.iterrows():
        ax.annotate(f"{r['S_24']:.0f}", (r["gN"], r["S_24"]), textcoords="offset points",
                    xytext=(0, 6), fontsize=8, color="#3eede7")
    ax.set_xlabel("参数量年均对数增速 gN"); ax.set_ylabel("预测前沿平均分 S")
    ax.set_title("前沿预测对增速假设的敏感性 (tornado)")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v34_p4_gN_sens.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v34_p4_gN_sens.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "span12_pct": float(span12 * 100),
                   "span24_pct": float(span24 * 100)}, f, ensure_ascii=False, indent=2)
    print("\ndone v34")


if __name__ == "__main__":
    main()