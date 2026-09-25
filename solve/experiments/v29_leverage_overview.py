# -*- coding: utf-8 -*-
"""
v29 实验: 四问题能力杠杆总览 (端到端弹性对照)
从各结果文件汇总"损失/能力对投入的对数弹性", 统一为可比口径:
  P2: |eps_N| |eps_D| |eps_Q|  (损失对 N/D/Q 的对数弹性, 交互(N)形式)
  P3: 预算弹性 (ln(L*-E)~lnC 斜率, v22) 与上下文弹性 (v9 bL)
  P4: 时间斜率 bT (能力前沿的年度对数增速)
产出总览表 + 横向条形图: 各通道杠杆排序 => 结论"质量与上下文是最高杠杆
通道, 规模次之, 时间外生演进 0.089".
输出: experiments/v29_leverage_overview.csv/.json/.png
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
    p2 = json.load(open(os.path.join(RES, "p2_scaling_results.json"), encoding="utf-8"))
    p4 = json.load(open(os.path.join(RES, "p4_results.json"), encoding="utf-8"))
    v22 = json.load(open(os.path.join(EX, "v22_p3_budget_ladder.json"), encoding="utf-8"))
    v9 = json.load(open(os.path.join(EX, "v9_p3_lctx_inner.json"), encoding="utf-8"))

    eps = p2["elasticity"]
    budget = v22["fits"]["power"]["slope"]
    bL = v9["benefit"]["bL"]
    bT = p4["frontier_qr"]["bT"]
    share = p4["annual_decomp"]["scale_share"]

    rows = [
        {"channel": "质量 Q (P2)", "type": "损失弹性 |eps_Q|", "value": abs(eps["eps_Q"]),
         "unit": "d lnL / dQ (Q+0.1 -> L降1.5%)"},
        {"channel": "上下文长度 (P3)", "type": "能力弹性 b_Lctx", "value": abs(bL),
         "unit": "lnS / ln L_ctx (约参数量弹性一半)"},
        {"channel": "预算 C (P3)", "type": "预算弹性", "value": abs(budget),
         "unit": "d ln(L*-E)/d lnC (翻倍预算损失降10.5%)"},
        {"channel": "参数量 N (P2)", "type": "损失弹性 |eps_N|", "value": abs(eps["eps_N"]),
         "unit": "d lnL / d lnN"},
        {"channel": "时间 t (P4)", "type": "前沿斜率 b_T", "value": float(bT),
         "unit": "d lnS / 年 (2024H2后放缓)"},
        {"channel": "数据量 D (P2)", "type": "损失弹性 |eps_D|", "value": abs(eps["eps_D"]),
         "unit": "d lnL / d lnD"},
    ]
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v29_leverage_overview.csv"), index=False, encoding="utf-8-sig")
    print(rdf.round(3).to_string(index=False))

    fig, ax = plt.subplots(figsize=(9, 5.5))
    order = rdf.sort_values("value", ascending=True)
    bars = ax.barh(order["channel"], order["value"], color=["#177cb0", "#1685a9", "#70f3ff",
                                                             "#44cef6", "#88ada6", "#3eede7"])
    for b, v in zip(bars, order["value"]):
        ax.text(v + 0.002, b.get_y() + b.get_height() / 2, f"{v:.3f}", va="center", fontsize=9)
    ax.set_xlabel("对数弹性 (绝对值)")
    ax.set_title("能力杠杆总览 (上下文/预算/质量 > 时间/参数 > 数据)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v29_leverage_overview.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v29_leverage_overview.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "scale_share_p4": float(share)}, f, ensure_ascii=False, indent=2)
    print("scale_share:", share)
    print("\ndone v29")


if __name__ == "__main__":
    main()