# -*- coding: utf-8 -*-
"""
v86 实验: P4 前沿预测的趋势形式集成 (回测加权 + 口径敏感性)
v82 给出四种趋势形式 (线性/二次/饱和/零增长) 的回测 MAPE 与全样本投影:
  12m: lin 71.7, quad 64.1, sat 64.1;  24m: lin 123.6, quad 102.7, sat 102.7
  MAPE: lin 177.7%, quad 70.9%, sat 56.9% (naive 9.8% 为零增长参照, 非趋势形式)
本实验:
  1) MAPE 反比加权集成 (lin/quad/sat);
  2) 口径敏感性: 等权平均 / 单形式极值 / 反比加权, 三者给出投影带;
  3) 检查集成投影是否落在论文双情景区间 [57.1,71.7] / [78.6,123.9] 内;
  4) 输出条形图: 各形式与集成投影 + 情景区间带。
输入: v82_p4_forecast_models.json (作为数据源, 只读)
输出: experiments/v86_p4_ensemble.json/.png
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from common import BASE

EX = os.path.join(os.path.dirname(__file__))
for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"

v82 = json.load(open(os.path.join(EX, "v82_p4_forecast_models.json"), encoding="utf-8"))
mape = {"lin": v82["agg"]["err_lin"]["mape"],
        "quad": v82["agg"]["err_quad"]["mape"],
        "sat": v82["agg"]["err_sat"]["mape"]}
proj12 = {k: v82["full_proj"]["12m"][k] for k in ("lin", "quad", "sat")}
proj24 = {k: v82["full_proj"]["24m"][k] for k in ("lin", "quad", "sat")}
SCEN = {"12m": (57.1, 71.7), "24m": (78.6, 123.9)}  # 双情景区间 [放缓, 基础]


def ensemble(horizon, weight_mode):
    p = proj12 if horizon == "12m" else proj24
    if weight_mode == "inv_mape":
        inv = {k: 1.0 / mape[k] for k in mape}
        s = sum(inv.values())
        w = {k: inv[k] / s for k in inv}
    elif weight_mode == "equal":
        w = {k: 1.0 / 3 for k in mape}
    elif weight_mode == "sat_only":
        return p["sat"]
    return sum(w[k] * p[k] for k in mape)


w_inv = {}
_inv = {k: 1.0 / mape[k] for k in mape}
_s = sum(_inv.values())
w_inv = {k: _inv[k] / _s for k in _inv}

res = {"inputs": {"mape": mape, "proj_12m": proj12, "proj_24m": proj24,
                  "scenario_intervals": SCEN,
                  "weights_inv_mape": {k: round(w_inv[k], 4) for k in w_inv}},
       "ensemble": {}, "landing": {}}
for h in ("12m", "24m"):
    lo, hi = SCEN[h]
    row = {}
    for mode in ("inv_mape", "equal", "sat_only"):
        v = ensemble(h, mode)
        row[mode] = round(float(v), 1)
        res["landing"].setdefault(h, {})[mode] = bool(lo <= v <= hi)
    # 极值带: 三种口径 min-max
    band = (min(row.values()), max(row.values()))
    row["band"] = [round(band[0], 1), round(band[1], 1)]
    row["in_scenario_band"] = bool(band[0] >= lo - 1e-9 and band[1] <= hi + 1e-9)
    res["ensemble"][h] = row
    print(f"{h}: inv_mape={row['inv_mape']}, equal={row['equal']}, "
          f"sat_only={row['sat_only']}, band={band}, in_interval={row['in_scenario_band']}")

json.dump(res, open(os.path.join(EX, "v86_p4_ensemble.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

# ---- 图: 12m/24m 各口径投影 + 情景区间带 ----
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.3))
labels12 = ["线性", "二次", "饱和", "集成\n(反比加权)", "集成\n(等权)", "饱和\n单形式"]
for ax, h in zip(axes, ("12m", "24m")):
    p = proj12 if h == "12m" else proj24
    lo, hi = SCEN[h]
    vals = [p["lin"], p["quad"], p["sat"], res["ensemble"][h]["inv_mape"],
            res["ensemble"][h]["equal"], res["ensemble"][h]["sat_only"]]
    colors = ["#70f3ff", "#3eede7", "#3eede7", "#177cb0", "#1685a9", "#44cef6"]
    bars = ax.bar(labels12, vals, color=colors, alpha=0.9, width=0.62)
    ax.axhspan(lo, hi, color="#88ada6", alpha=0.18)
    ax.text(0.02, hi, f"情景上限 {hi:.1f}", fontsize=8, va="bottom", color="#1685a9")
    ax.text(0.02, lo, f"情景下限 {lo:.1f}", fontsize=8, va="top", color="#1685a9")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}",
                ha="center", fontsize=8, color="#1A1A1A")
    ax.set_ylabel("前沿得分预测"); ax.set_title(f"{h} 各口径投影 vs 双情景区间")
    ax.grid(alpha=0.3, axis="y"); ax.set_ylim(0, max(hi * 1.15, max(vals) * 1.2))
fig.suptitle("P4 前沿预测: 趋势形式集成口径 (回测 MAPE 反比加权) 与情景区间", fontsize=12, y=1.02)
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(os.path.join(EX, "v86_p4_ensemble.png"), dpi=200)
plt.close(fig)
print("done v86")