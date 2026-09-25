# -*- coding: utf-8 -*-
"""
v53 实验: 质量通道结构性转移的带宽
读 v31 解族轨迹 (C, Q*) 每 g-形式, 定义转移带 = Q* 在 [Q0+0.2(1-Q0),
Q0+0.8(1-Q0)] = [0.52, 0.88] 跨越的预算区间:
1) 每形式激活预算 C_act (Q*=0.52) 与饱和预算 C_sat (Q*=0.88);
2) 转移带宽 (decades) = log10(C_sat) - log10(C_act);
3) 带宽含义: log 形式转移最陡 (带宽窄), exp/power 平缓 (带宽宽);
4) 与 B 附录两阶段特征量 (g'(Q0) 激活序 / Delta_g 饱和序) 互证.
输出: experiments/v53_p3_transit_band.csv/.json/.png
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

Q0 = 0.4
Q20, Q80 = Q0 + 0.2 * (1 - Q0), Q0 + 0.8 * (1 - Q0)   # 0.52 / 0.88


def c_at(q, Cs, Qs):
    """在 log-C 空间对 Q 插值找预算 (单调递增段)"""
    idx = np.argsort(Cs)
    Cs, Qs = np.asarray(Cs)[idx], np.asarray(Qs)[idx]
    lc = np.log10(Cs)
    return 10 ** float(np.interp(q, Qs, lc))


def main():
    d = json.load(open(os.path.join(EX, "v31_p3_solution_family.json"), encoding="utf-8"))
    rows = d["rows"]
    forms = []
    for r in rows:
        if r["form"] not in forms:
            forms.append(r["form"])
    out = []
    for f in forms:
        fr = [r for r in rows if r["form"] == f]
        Cs = [r["C"] for r in fr]
        Qs = [r["Q"] for r in fr]
        C20 = c_at(Q20, Cs, Qs)
        C80 = c_at(Q80, Cs, Qs)
        band = np.log10(C80) - np.log10(C20)
        out.append({"form": f, "C_act_Q52": float(C20), "C_sat_Q88": float(C80),
                    "band_decades": float(band)})
        print(f"{f:10s} 激活Q=0.52 @ C={C20:.2e} | 饱和Q=0.88 @ C={C80:.2e} | "
              f"带宽 {band:.2f} 个数量级")
    rdf = pd.DataFrame(out)
    rdf.to_csv(os.path.join(EX, "v53_p3_transit_band.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    pos = np.arange(len(rdf))
    ax.barh(pos, rdf["band_decades"], color="#177cb0", alpha=0.85)
    ax.set_yticks(pos); ax.set_yticklabels(rdf["form"])
    ax.set_xlabel("转移带宽 (log10 预算跨度)")
    ax.set_title("v53: 质量通道结构性转移的预算带宽 (Q*=0.52->0.88)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v53_p3_transit_band.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v53_p3_transit_band.json"), "w", encoding="utf-8") as f:
        json.dump({"Q20": Q20, "Q80": Q80, "rows": out}, f, ensure_ascii=False, indent=2)
    print("\ndone v53")


if __name__ == "__main__":
    main()