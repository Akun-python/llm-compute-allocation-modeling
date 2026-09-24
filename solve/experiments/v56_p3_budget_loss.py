# -*- coding: utf-8 -*-
"""
v56 实验: 预算-损失弹性的通道差异
读 v31 解族轨迹 (C, L*), 对每 g-形式拟合 ln L* ~ ln C 的对数斜率:
1) 各形式 L*(C) 斜率 (预算翻倍损失降幅);
2) 与纯规模理论对照 (无质量通道时 a*alpha ≈ -0.14);
3) 质量通道是否使"预算->损失"收益更陡 (exp/pow/log 差异);
4) 三档预算处 (1e19/1e22/1e24) 的 L* 横截面.
输出: experiments/v56_p3_budget_loss.csv/.json/.png
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


def main():
    d = json.load(open(os.path.join(EX, "v31_p3_solution_family.json"), encoding="utf-8"))
    rows = d["rows"]
    forms = []
    for r in rows:
        if r["form"] not in forms:
            forms.append(r["form"])
    out = []
    for f in forms:
        fr = sorted([r for r in rows if r["form"] == f], key=lambda r: r["C"])
        Cs = np.array([r["C"] for r in fr], float)
        Ls = np.array([r["L"] for r in fr], float)
        # 对数斜率 (预算高区, 排除极低预算的噪声)
        mask = Cs >= 1e17
        lc = np.log(Cs[mask]); ll = np.log(Ls[mask])
        k, *_ = np.polyfit(lc, ll, 1)
        L19 = float(np.interp(np.log10(1e19), np.log10(Cs), Ls))
        L22 = float(np.interp(np.log10(1e22), np.log10(Cs), Ls))
        L24 = float(np.interp(np.log10(1e24), np.log10(Cs), Ls))
        out.append({"form": f, "slope_lnL_lnC": float(k),
                    "L_at_1e19": L19, "L_at_1e22": L22, "L_at_1e24": L24})
        print(f"{f:10s} lnL~lnC 斜率 {k:.3f} | L(1e19)={L19:.2f} L(1e22)={L22:.2f} "
              f"L(1e24)={L24:.2f} | 1e19->1e22 降幅 {(1-L22/L19)*100:.0f}%")
    rdf = pd.DataFrame(out)
    rdf.to_csv(os.path.join(EX, "v56_p3_budget_loss.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    pos = np.arange(len(rdf))
    ax.barh(pos, rdf["slope_lnL_lnC"], color="#2563EB", alpha=0.85)
    ax.axvline(-0.14, color="#C2410C", lw=1.4, ls="--", label="纯规模理论 ~ -0.14")
    ax.set_yticks(pos); ax.set_yticklabels(rdf["form"])
    ax.set_xlabel("ln L* / ln C (预算翻倍损失降幅)")
    ax.set_title("v56: 预算-损失弹性的通道差异")
    ax.legend(fontsize=9); ax.grid(alpha=0.3, axis="x")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v56_p3_budget_loss.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v56_p3_budget_loss.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": out, "pure_scaling_ref": -0.14}, f, ensure_ascii=False, indent=2)
    print("\ndone v56")


if __name__ == "__main__":
    main()