# -*- coding: utf-8 -*-
"""
v14 实验: 广义标度律 (interaction_N) 参数的可辨识性 —— 剖面似然
对关键参数 h (质量随参数量衰减指数), g (缺口幂), a (参数量指数) 做网格扫描,
固定其余参数在最优值, 计算残差平方和/剖面 R2, 判定参数是否被数据良好识别
(单峰且峰锐) 以及生成的 90% 区间.
回答: h=0.163 的估计是否"可信", 还是只被少数样本支撑?
输出: experiments/v14_p2_profile.csv + 图
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import B, RES, FIG, BASE

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


def load_b67():
    """B6+B7 数据: N,D,Q,Loss (与 p2 拟合相同口径)"""
    b6 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment.csv"))
    b7 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment_expanded.csv"))
    df = pd.concat([b6, b7], ignore_index=True)
    print("B6+B7:", df.shape)
    return df


def main():
    df = load_b67()
    # 找 Q 列
    qcols = [c for c in df.columns if c.lower().startswith("q") or "quality" in c.lower()]
    print("Q cols:", qcols, "loss cols ok")
    qcol = None
    for cand in ["Q_score", "Q", "quality", "data_quality"]:
        if cand in df.columns:
            qcol = cand
            break
    if qcol is None and qcols:
        qcol = qcols[0]
    assert qcol, "Q column not found"
    N, D, Q, L = (df[c].to_numpy(dtype=float) for c in ["N_params_B", "D_tokens_B", qcol, "val_loss"])
    # 参考参数 (interaction_N)
    p2 = json.load(open(os.path.join(RES, "p2_scaling_results.json"), encoding="utf-8"))
    pref = {k: float(v) for k, v in p2["generalized"]["forms"]["interaction_N"]["params"].items()}
    print("reference:", {k: round(v, 4) for k, v in pref.items()})

    def rss_for(params):
        E, A, a, B, b, C, g, h = params
        pred = (E + A * N ** (-a) + B * D ** (-b)
                + C * np.maximum(1 - Q, 0) ** g * N ** (-h))
        return float(np.sum((L - pred) ** 2))

    base_rss = rss_for([pref[k] for k in ["E", "A", "a", "B", "b", "C", "g", "h"]])
    n = len(N)
    sigma2 = base_rss / (n - 8)

    # 剖面扫描: 对每个关键参数做 41 点网格
    grids = {"h": np.linspace(0.02, 0.45, 41), "g": np.linspace(0.5, 1.6, 41),
             "a": np.linspace(0.1, 0.55, 41), "b": np.linspace(0.1, 0.5, 41)}
    rows = []
    for key, gv in grids.items():
        for v in gv:
            par = [pref[k] for k in ["E", "A", "a", "B", "b", "C", "g", "h"]]
            par[["E", "A", "a", "B", "b", "C", "g", "h"].index(key)] = v
            rss = rss_for(par)
            rows.append({"param": key, "value": v, "rss": rss, "r2": 1 - rss / np.sum((L - L.mean()) ** 2),
                         "lr_stat": (base_rss - rss) if rss < base_rss else -(rss - base_rss)})
    prof = pd.DataFrame(rows)
    prof.to_csv(os.path.join(EX, "v14_p2_profile.csv"), index=False, encoding="utf-8-sig")

    # 90% 剖面区间: LR 拒绝域 rss <= base_rss * exp(qchisq(0.90,1)/n)
    from scipy.stats import chi2
    thr = base_rss * np.exp(chi2.ppf(0.90, 1) / n)
    print("\n剖面似然 90%% 区间 (base rss=%.4f, thr=%.4f):" % (base_rss, thr))
    for key in grids:
        sub = prof[prof["param"] == key]
        inside = sub[sub["rss"] <= thr]
        if len(inside):
            print(f"  {key}: [{inside['value'].min():.3f}, {inside['value'].max():.3f}]  峰={sub.loc[sub['rss'].idxmin(),'value']:.3f}")
        else:
            print(f"  {key}: (none) 峰={sub.loc[sub['rss'].idxmin(),'value']:.3f}")

    # 图
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5))
    for ax, key in zip(axes.ravel(), ["h", "g", "a", "b"]):
        sub = prof[prof["param"] == key]
        ax.plot(sub["value"], sub["r2"], "-o", ms=2.5, color="#2563EB")
        ax.axhline(1 - thr / np.sum((L - L.mean()) ** 2), color="#EF4444", ls="--", lw=1)
        ax.set_xlabel(key); ax.set_ylabel("剖面 R2")
        ax.set_title(f"profile: {key} (ref={pref[key]:.3f})")
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v14_p2_profile.png"), dpi=200)
    plt.close(fig)
    print("\ndone v14")


if __name__ == "__main__":
    main()