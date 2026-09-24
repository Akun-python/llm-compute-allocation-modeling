# -*- coding: utf-8 -*-
"""
v47 实验: 配比模型的处方价值 (最优配比的预测收益)
1M 训练配比--损失数据上重拟合岭回归 (13 损失域 x 17 源域 + 截距),
把"平均预测损失"作为配比的处方目标:
1) LP 求单纯形上最小化平均损失的顶点最优配比 x* (线性规划);
2) 对照: 均匀配比 (1/17) 与训练表中实测最优混合行;
3) 报告 x* 的域结构与相对均匀配比的预测损失降幅;
4) 与域级质量排序对照 (高质域 book/gutenberg 权重是否偏高).
输出: experiments/v47_p1_mix_prescribe.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_mixture import load_pair, RIDGE_ALPHA
from common import A, BASE, MIX_DOMAINS, LOSS_DOMAINS
from scipy.optimize import linprog
from sklearn.linear_model import Ridge

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
    tr = load_pair("train_mixture_1m.csv", "train_pile_loss_1m.csv")
    X = tr[[f"train_the_pile_{d}" for d in MIX_DOMAINS]].to_numpy(dtype=float)
    Y = tr[[f"metric/the_pile_{d}_val_loss" for d in LOSS_DOMAINS]].to_numpy(dtype=float)
    nd = len(MIX_DOMAINS)
    models = [Ridge(alpha=RIDGE_ALPHA).fit(X, Y[:, j]) for j in range(len(LOSS_DOMAINS))]
    # 平均损失模型: a = 系数均值 (损失域平均), b = 截距均值
    B = np.stack([m.coef_ for m in models]).mean(axis=0)
    b0 = np.mean([m.intercept_ for m in models])

    # LP: min B@x, s.t. sum x = 1, x >= 0  (无约束顶点, 上界)
    res = linprog(B, A_eq=np.ones((1, nd)), b_eq=[1.0], bounds=[(0, 1)] * nd, method="highs")
    x_opt = res.x
    L_opt = B @ x_opt + b0
    L_unif = B @ (np.ones(nd) / nd) + b0
    L_best = min(B @ tr[[f"train_the_pile_{d}" for d in MIX_DOMAINS]].to_numpy(dtype=float).T
                 + b0)
    print(f"无约束LP: L* = {L_opt:.4f} vs 均匀 {L_unif:.4f} vs 训练实测最优 {L_best:.4f} "
          f"(降幅 {(L_unif - L_opt) / L_unif * 100:.1f}%)")

    # 二次正则 + 多样性上限: min B@x + lam*sum(x-1/17)^2, s.t. sum x=1, 0<=x<=cap
    from scipy.optimize import minimize
    cap = 0.30
    lam = 0.5 * np.abs(B).mean()

    def obj(x):
        return B @ x + lam * np.sum((x - 1 / nd) ** 2)

    def cons(x):
        return 1.0 - x.sum()
    x0 = np.ones(nd) / nd
    sol = minimize(obj, x0, method="SLSQP", constraints={"type": "eq", "fun": cons},
                   bounds=[(0, cap)] * nd, options={"maxiter": 400})
    x_reg = sol.x
    L_reg = B @ x_reg + b0
    print(f"上限{cap:.0%}+正则: L* = {L_reg:.4f} (降幅 {(L_unif - L_reg) / L_unif * 100:.1f}%)")
    print(f"正则最优配比 (权重>0.02):")
    for d, w in sorted(zip(MIX_DOMAINS, x_reg), key=lambda t: -t[1]):
        if w > 0.02:
            print(f"  {d}: {w:.3f}")

    rows = [{"domain": d, "x_lp": float(x_opt[i]), "x_reg": float(x_reg[i])}
            for i, d in enumerate(MIX_DOMAINS)]
    rdf = pd.DataFrame(rows).sort_values("x_reg", ascending=False)
    rdf.to_csv(os.path.join(EX, "v47_p1_mix_prescribe.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(9, 5))
    top = rdf.head(8)
    ax.barh(range(len(top)), top["x_reg"], color="#2563EB", alpha=0.85)
    ax.set_yticks(range(len(top))); ax.set_yticklabels(top["domain"])
    ax.set_xlabel("正则最优配比权重"); ax.set_title(f"v47: 处方最优配比 (上限30%+正则, 预测降幅 {(L_unif-L_reg)/L_unif*100:.1f}%)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v47_p1_mix_prescribe.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v47_p1_mix_prescribe.json"), "w", encoding="utf-8") as f:
        json.dump({"L_opt": float(L_opt), "L_uniform": float(L_unif), "L_train_best": float(L_best),
                   "gain_pct_lp": float((L_unif - L_opt) / L_unif * 100),
                   "gain_pct_reg": float((L_unif - L_reg) / L_unif * 100),
                   "L_reg": float(L_reg),
                   "x_opt": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v47")


if __name__ == "__main__":
    main()