# -*- coding: utf-8 -*-
"""
v26 实验: 标度律形式的留出交叉验证 (模型选择的严格检验)
对 classical (无质量项,5p) / additive (7p) / interaction_N (8p) /
multiplicative (7p) 在 B6+B7 (810 点) 上做 5 折 x3 重复 CV:
- 每折: 训练 4/5, 留出 1/5 预测 val_loss -> RMSE / R^2 (留出).
- 结论: 加入质量项 (additive) 是否真正提升留出精度? 交互(N) 形式是否
  比加性更优? => 支撑正文"选 interaction_N 不靠过拟合"的论断.
输出: experiments/v26_p2_cv.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from v3_p2_forms import load_b67, fit_form, loss_forms
from common import BASE
from scipy.optimize import least_squares

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


def fit_classical(N, D, L):
    """L = E + A N^-a + B D^-b (5p, 无质量项); 返回参数"""
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


def rmse_r2(y, p):
    r = p - y
    return float(np.sqrt(np.mean(r ** 2))), float(1 - np.sum(r ** 2) / np.sum((y - y.mean()) ** 2))


def main():
    df = load_b67()
    N, D, Q, L = (df[k].to_numpy(dtype=float) for k in
                  ["N_params_B", "D_tokens_B", "Q_score", "val_loss"])
    print("data:", len(L))
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
                results[f].append(rmse_r2(L[te], phat))
    rows = []
    for f in forms:
        rmses = [r[0] for r in results[f]]
        r2s = [r[1] for r in results[f]]
        rows.append({"form": f, "cv_rmse_mean": float(np.mean(rmses)),
                     "cv_rmse_std": float(np.std(rmses)),
                     "cv_r2_mean": float(np.mean(r2s)), "cv_r2_std": float(np.std(r2s))})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v26_p2_cv.csv"), index=False, encoding="utf-8-sig")
    print(rdf.round(4).to_string(index=False))

    fig, ax = plt.subplots(figsize=(7.5, 5))
    x = np.arange(len(forms))
    ax.bar(x, rdf["cv_rmse_mean"], yerr=rdf["cv_rmse_std"], capsize=4,
           color=["#88ada6", "#70f3ff", "#177cb0", "#44cef6"])
    ax.set_xticks(x); ax.set_xticklabels(forms, rotation=15)
    ax.set_ylabel("留出折 RMSE")
    ax.set_title("v26: 标度律形式 5 折 x3 交叉验证 (B6+B7, n=810)")
    for i, v in enumerate(rdf["cv_rmse_mean"]):
        ax.text(i, v + 0.003, f"{v:.3f}", ha="center", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v26_p2_cv.png"), dpi=200); plt.close(fig)

    with open(os.path.join(EX, "v26_p2_cv.json"), "w", encoding="utf-8") as f:
        json.dump(rdf.to_dict("records"), f, ensure_ascii=False, indent=2)
    print("\ndone v26")


if __name__ == "__main__":
    main()