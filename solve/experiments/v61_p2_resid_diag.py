# -*- coding: utf-8 -*-
"""
v61 实验: 广义标度律 (interaction_N) 的残差诊断
B6+B7 (n=810) 拟合后:
1) 残差 vs N/D/Q 的 Pearson 相关 (应接近 0: 无系统遗漏结构);
2) 残差直方图/QQ 正态性 (Shapiro 或偏度峰度);
3) 残差标准差 vs additive (交互形式是否降低残差离散);
4) 高残差点 (|res|>2sd) 的样本特征.
输出: experiments/v61_p2_resid_diag.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from v3_p2_forms import load_b67, loss_forms, fit_form
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
    df = load_b67()
    N = df["N_params_B"].to_numpy(dtype=float)
    D = df["D_tokens_B"].to_numpy(dtype=float)
    Q = df["Q_score"].to_numpy(dtype=float)
    L = df["val_loss"].to_numpy(dtype=float)

    out = {}
    for form in ("additive", "interaction_N"):
        p, r2 = fit_form(N, D, Q, L, form)
        Lp = loss_forms(N, D, Q, p, form)
        res = L - Lp
        rN = float(np.corrcoef(res, N)[0, 1])
        rD = float(np.corrcoef(res, D)[0, 1])
        rQ = float(np.corrcoef(res, Q)[0, 1])
        sd = float(res.std())
        skew = float(pd.Series(res).skew())
        n_out = int(np.sum(np.abs(res) > 2 * sd))
        print(f"{form:14s} R2={r2:.4f} 残差sd={sd:.4f} | corr(res,N)={rN:+.3f} "
              f"corr(res,D)={rD:+.3f} corr(res,Q)={rQ:+.3f} | skew={skew:+.2f} | |res|>2sd: {n_out}")
        out[form] = {"r2": float(r2), "resid_sd": sd, "corr_N": rN, "corr_D": rD,
                     "corr_Q": rQ, "skew": skew, "n_outliers_2sd": n_out}
    pd.DataFrame([{"form": k, **v} for k, v in out.items()]).to_csv(
        os.path.join(EX, "v61_p2_resid_diag.csv"), index=False, encoding="utf-8-sig")

    # 图: 交互形式残差 vs Q 散点 + 直方图
    pN, _ = fit_form(N, D, Q, L, "interaction_N")
    res = L - loss_forms(N, D, Q, pN, "interaction_N")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    axes[0].scatter(Q, res, s=8, color="#2563EB", alpha=0.5)
    axes[0].axhline(0, color="#C2410C", lw=1.2)
    axes[0].set_xlabel("Q"); axes[0].set_ylabel("残差")
    axes[0].set_title(f"interaction_N 残差 vs Q (r={np.corrcoef(res,Q)[0,1]:+.3f})")
    axes[1].hist(res, bins=40, color="#0EA5E9", alpha=0.85)
    axes[1].axvline(0, color="#C2410C", lw=1.2)
    axes[1].set_xlabel("残差"); axes[1].set_title(f"残差分布 (sd={res.std():.4f})")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v61_p2_resid_diag.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v61_p2_resid_diag.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\ndone v61")


if __name__ == "__main__":
    main()