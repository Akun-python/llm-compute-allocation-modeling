# -*- coding: utf-8 -*-
"""
v90 实验: B4 缩放基准的留一族交叉验证 (复算 §6 声称)
方法论 (与 p2_scaling.fit_classical / §6 描述一致):
  1) 对每个留出家族, 用其余 11 个家族拟合经典标度律
     L = E + A N^{-a} + B D^{-b} (least_squares, 与主链路同边界);
  2) 偏移修正: 留出家族只允许常数偏移 E_ho = mean(L - 形状预测),
     偏移修正 R2 = 1 - SS_res/SS_tot;
  3) 输出逐家族 R2/n 与 alpha,beta 留出估计, 均值/范围/>=0.91 计数。
输出: experiments/v90_p2_family_loo.json/.csv/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p2_scaling import fit_classical, predict_classical, r2_metric
from common import BASE, B

EX = os.path.join(os.path.dirname(__file__))
B4 = os.path.join(B, "scaling_baseline.csv")

def r2_offset(y, shape):
    """只允许常数偏移的最优 R2"""
    e_ho = float(np.mean(y - shape))
    res = y - (shape + e_ho)
    ss_res = np.sum(res ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    return 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

def main():
    df = pd.read_csv(B4)
    families = df["family"].unique().tolist()
    rows = []
    loo_r2 = []
    loo_alpha = []
    for ho in families:
        tr = df[df["family"] != ho]
        te = df[df["family"] == ho]
        N, D, L = tr["N_params_B"].to_numpy(float), tr["D_tokens_B"].to_numpy(float), tr["val_loss"].to_numpy(float)
        sol = fit_classical(N, D, L)
        p = sol.x
        alpha, beta = p[2], p[4]
        shape = predict_classical(p, te["N_params_B"].to_numpy(float), te["D_tokens_B"].to_numpy(float))
        y = te["val_loss"].to_numpy(float)
        r2 = r2_offset(y, shape) if len(y) > 1 else float("nan")
        rows.append({"family": ho, "n": int(len(te)), "r2_loo": float(r2),
                     "alpha": float(alpha), "beta": float(beta),
                     "E_train": float(p[0]), "A": float(p[1]), "B": float(p[3])})
        loo_r2.append(r2)
        loo_alpha.append(alpha)
        print(f"{ho:12s} n={len(te):2d} r2_loo={r2:.4f} alpha={alpha:.4f} beta={beta:.4f}")
    r2_arr = np.array([r for r in loo_r2 if np.isfinite(r)])
    print(f"\nmean R2 = {r2_arr.mean():.4f}  range [{r2_arr.min():.4f}, {r2_arr.max():.4f}]")
    print(f"alpha range [{min(loo_alpha):.4f}, {max(loo_alpha):.4f}]")
    ge91 = [r for r in r2_arr if r >= 0.91]
    print(f"families with R2>=0.91: {len(ge91)}/{len(r2_arr)}")

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v90_p2_family_loo.csv"), index=False, encoding="utf-8-sig")
    out = {"n": int(len(df)), "n_families": len(families),
           "mean_r2_loo": float(r2_arr.mean()), "min_r2_loo": float(r2_arr.min()),
           "max_r2_loo": float(r2_arr.max()),
           "n_r2_ge91": int(len(ge91)), "n_r2_computable": int(len(r2_arr)),
           "alpha_range": [float(min(loo_alpha)), float(max(loo_alpha))],
           "rows": rows}
    with open(os.path.join(EX, "v90_p2_family_loo.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

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
    fig, ax = plt.subplots(figsize=(8, 5))
    rr = rdf[np.isfinite(rdf["r2_loo"])].sort_values("r2_loo", ascending=False)
    ax.bar(rr["family"], rr["r2_loo"], color="#177cb0")
    ax.axhline(0.91, color="#44cef6", ls="--", lw=1.2)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("偏移修正 R$^2$ (留一族)")
    ax.set_title("B4 经典标度律留一族交叉验证")
    for i, v in enumerate(rr["r2_loo"]):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v90_p2_family_loo.png"), dpi=200)
    plt.close(fig)
    print("\ndone v90")

if __name__ == "__main__":
    main()
