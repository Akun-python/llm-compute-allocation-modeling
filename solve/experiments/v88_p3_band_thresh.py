# -*- coding: utf-8 -*-
"""
v88 实验: 质量通道转移带宽对 Q 阈值口径的敏感性
v53 以 Q* 跨 [Q0+0.2(1-Q0), Q0+0.8(1-Q0)] = [0.52, 0.88] 定义转移带,
给出带宽 exp 1.52 > power 0.97 > log 0.38 (decades). 本实验:
  1) 对同一 v31 解族轨迹 (只读) 在替代阈值口径 [0.45,0.95]/[0.50,0.90]/
     [0.55,0.85] 下重算每形式带宽与激活/饱和预算;
  2) 检查 exp>power>log 的带宽排序与 v53 是否不变 (排序稳健性);
  3) 检查激活序 (C_act 升序) 与饱和序 (C_sat 升序) 跨口径一致;
  4) 输出图: 各形式带宽随阈值口径的变化。
输出: experiments/v88_p3_band_thresh.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import BASE

EX = os.path.join(os.path.dirname(__file__))
for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"

Q0 = 0.4
THRESHOLDS = [(0.45, 0.95), (0.50, 0.90), (0.52, 0.88), (0.55, 0.85)]


def c_at(q, Cs, Qs):
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
    traj = {f: ([r["C"] for r in rows if r["form"] == f],
                [r["Q"] for r in rows if r["form"] == f]) for f in forms}

    # 复算 v53 主口径以校验
    Cs, Qs = traj["exp"]
    assert abs(np.log10(c_at(0.52, Cs, Qs)) - 18.2048) < 0.02  # 1.6028e18
    out = {"thresholds": [], "band_order_invariant": {}, "act_order_invariant": {},
           "sat_order_invariant": {}}
    for qa, qs in THRESHOLDS:
        bands, acts, sats = {}, {}, {}
        for f in forms:
            Cs, Qs = traj[f]
            Ca = c_at(qa, Cs, Qs)
            Cb = c_at(qs, Cs, Qs)
            bands[f] = float(np.log10(Cb) - np.log10(Ca))
            acts[f] = float(Ca)
            sats[f] = float(Cb)
        bsort = " > ".join(sorted(forms, key=lambda f: -bands[f]))
        asort = " > ".join(sorted(forms, key=lambda f: -acts[f]))  # 激活预算大=难激活
        ssort = " > ".join(sorted(forms, key=lambda f: -sats[f]))
        out["thresholds"].append({"qa": qa, "qs": qs,
                                  "band": {f: round(bands[f], 3) for f in forms},
                                  "C_act": {f: acts[f] for f in forms},
                                  "C_sat": {f: sats[f] for f in forms},
                                  "band_order": bsort, "act_order": asort,
                                  "sat_order": ssort})
        print(f"Q∈[{qa},{qs}]: band {bsort} | 激活 {asort} | 饱和 {ssort}")

    # 排序不变性: 与主口径 [0.52,0.88] 比较
    main_o = out["thresholds"][2]
    for key, lbl in [("band_order", "带宽"), ("act_order", "激活"), ("sat_order", "饱和")]:
        inv = all(t[key] == main_o[key] for t in out["thresholds"])
        out["band_order_invariant" if key == "band_order" else
            "act_order_invariant" if key == "act_order" else "sat_order_invariant"] = inv
        print(f"  {lbl}排序跨口径不变: {inv}")

    json.dump(out, open(os.path.join(EX, "v88_p3_band_thresh.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    cols = {"exp": "#177cb0", "power": "#1685a9", "log": "#3eede7"}
    x = np.arange(len(THRESHOLDS))
    for f in forms:
        vals = [t["band"][f] for t in out["thresholds"]]
        ax.plot(x, vals, "-o", color=cols[f], label=f, lw=1.8)
        for xi, v in zip(x, vals):
            ax.text(xi, v + 0.03, f"{v:.2f}", ha="center", fontsize=7.5, color="#1A1A1A")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Q∈[{qa},{qs}]" for qa, qs in THRESHOLDS], fontsize=8)
    ax.set_ylabel("转移带宽 (decades)"); ax.set_title("转移带宽对 Q 阈值口径的敏感性")
    ax.grid(alpha=0.3, axis="y"); ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v88_p3_band_thresh.png"), dpi=200)
    plt.close(fig)
    print("done v88")


if __name__ == "__main__":
    main()