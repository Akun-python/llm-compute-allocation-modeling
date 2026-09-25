# -*- coding: utf-8 -*-
"""
v87 实验: P2 留出交叉验证的配对被检验 (交互(N) vs 经典/乘性 的显著性)
v26 只报告各形式 CV RMSE 均值/标准差; 本实验复现其协议 (K=5, REP=3,
seed 42, forms=classical/additive/interaction_N/multiplicative) 并记录
逐折 RMSE, 做配对显著性检验:
  1) 复算均值与 v26 一致 (确定性验证);
  2) 配对 Wilcoxon 符号秩检验 + 配对 t 检验:
     interaction_N vs classical (主声明: 相对经典降 59.5%),
     interaction_N vs multiplicative (最接近对手, 0.0511 vs 0.0519),
     additive vs classical (53% 声明);
  3) 输出逐折误差图。
输入: 同一数据源 load_b67 (v3 协议), 只读
输出: experiments/v87_p2_cv_paired.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from scipy.stats import wilcoxon, ttest_rel
sys.path.insert(0, os.path.dirname(__file__))
from v3_p2_forms import load_b67, loss_forms
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


def fit_classical(N, D, L):
    """与 v26 逐位一致: L = E + A N^-a + B D^-b (5p, 无质量项)"""
    from scipy.optimize import least_squares
    def resid(p):
        E, A, a, B_, b = p
        return E + A * N ** (-a) + B_ * D ** (-b) - L
    p0 = [L.min() * 0.7, 3.0, 0.3, 3.0, 0.3]
    lb = [0, 1e-6, 1e-4, 1e-6, 1e-4]
    ub = [L.min() * 1.2, 1e3, 5, 1e3, 5]
    sol = least_squares(resid, p0, bounds=(lb, ub), max_nfev=120000)
    return sol.x


def pred_classical(N, D, p):
    E, A, a, B_, b = p
    return E + A * N ** (-a) + B_ * D ** (-b)


def fit_form(N, D, Q, L, name):
    """委托 v3 协议 (与 v26 一致)"""
    from v3_p2_forms import fit_form as _ff
    return _ff(N, D, Q, L, name)


def rmse(y, p):
    return float(np.sqrt(np.mean((p - y) ** 2)))


def main():
    df = load_b67()
    N, D, Q, L = (df[k].to_numpy(dtype=float) for k in
                  ["N_params_B", "D_tokens_B", "Q_score", "val_loss"])
    rng = np.random.default_rng(42)
    forms = ["classical", "additive", "interaction_N", "multiplicative"]
    K, REP = 5, 3
    results = {f: [] for f in forms}
    for rep in range(REP):
        idx = rng.permutation(len(L))
        folds = np.array_split(idx, K)
        for k in range(K):
            te = np.concatenate([folds[j] for j in range(K) if j != k])
            tr = folds[k]
            for f in forms:
                if f == "classical":
                    p = fit_classical(N[tr], D[tr], L[tr])
                    phat = pred_classical(N[te], D[te], p)
                else:
                    p, _ = fit_form(N[tr], D[tr], Q[tr], L[tr], f)
                    phat = loss_forms(N[te], D[te], Q[te], p, f)
                results[f].append(rmse(L[te], phat))
    arr = {f: np.array(results[f]) for f in forms}
    means = {f: float(arr[f].mean()) for f in forms}
    print("CV 均值复核:", {f: round(means[f], 4) for f in forms})
    # 与 v26 交叉验证
    v26 = {"classical": 0.12620821468662152, "additive": 0.05960987608715003,
           "interaction_N": 0.051127292572458446, "multiplicative": 0.05187031604068446}
    for f in forms:
        assert abs(means[f] - v26[f]) < 1e-6, f"{f} 均值与 v26 不一致: {means[f]}"
    print("与 v26 逐位一致 [OK]")

    pairs = [("interaction_N", "classical"), ("interaction_N", "multiplicative"),
             ("additive", "classical")]
    out = {"n_paired": int(len(arr["classical"])), "means": means, "pairs": {}}
    for a, b in pairs:
        d = arr[a] - arr[b]
        red = 1 - arr[a] / arr[b]
        w = wilcoxon(arr[a], arr[b])
        t = ttest_rel(arr[a], arr[b])
        row = {"form_a": a, "form_b": b,
               "mean_a": float(arr[a].mean()), "mean_b": float(arr[b].mean()),
               "mean_reduction_pct": float(np.mean(red) * 100),
               "wilcoxon_stat": float(w.statistic), "wilcoxon_p": float(w.pvalue),
               "ttest_stat": float(t.statistic), "ttest_p": float(t.pvalue)}
        out["pairs"][f"{a}|{b}"] = row
        print(f"{a} vs {b}: 降 {np.mean(red)*100:.1f}%  "
              f"Wilcoxon p={w.pvalue:.4g}  t 检验 p={t.pvalue:.4g}")

    json.dump(out, open(os.path.join(EX, "v87_p2_cv_paired.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    xs = np.arange(len(forms))
    colors = {"classical": "#70f3ff", "additive": "#3eede7",
              "interaction_N": "#177cb0", "multiplicative": "#44cef6"}
    for i, f in enumerate(forms):
        pts = arr[f]
        ax.plot(xs[i] + np.random.default_rng(7).uniform(-0.12, 0.12, len(pts)),
                pts, "o", ms=4, alpha=0.55, color=colors[f], label=f)
    for i, f in enumerate(forms):
        ax.plot([i], [arr[f].mean()], "D", ms=7, color=colors[f], mec="white")
        ax.text(i, arr[f].mean() + 0.004, f"{arr[f].mean():.4f}",
                ha="center", fontsize=8, color="#1A1A1A")
    ax.set_xticks(xs); ax.set_xticklabels(["经典", "加性", "交互($N$)", "乘性"])
    ax.set_ylabel("留出折 RMSE"); ax.set_title("P2 留出交叉验证逐折误差 (K=5×REP=3, 15 折配对)")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v87_p2_cv_paired.png"), dpi=200)
    plt.close(fig)
    print("done v87")


if __name__ == "__main__":
    main()