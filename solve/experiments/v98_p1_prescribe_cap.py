# -*- coding: utf-8 -*-
"""
v98 实验: 配比处方收益对多样性上限 c 的敏感性 (锚定 §5 "配比调节是有限杠杆")
v47 显示: 无约束 LP 顶点解 16.9% (上界) -> cap=0.30+二次正则 11.9%.
本实验扫描单域上限 c in {0.10,0.20,0.30,0.50,0.70,1.00} (含 v47 基准
c=0.30 与无约束上界 c=1.00), 回答: 若给配比更多自由度, 实测训练最优
混合行收益仍仅 ~3%, 说明"有限杠杆"结论稳健, 还是收益随 c 迅速放大?
口径与 v47 完全一致: 经由 p1_mixture.load_pair 读 train_mixture_1m.csv +
train_pile_loss_1m.csv, Ridge(alpha), 13 损失域系数均值 B, 正则
lam=0.5*mean|B|.
输出: experiments/v98_p1_prescribe_cap.json/.csv/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from sklearn.linear_model import Ridge
from scipy.optimize import linprog, minimize
from p1_mixture import load_pair, RIDGE_ALPHA, MIX_DOMAINS, LOSS_DOMAINS
from common import A, BASE

EX = os.path.join(os.path.dirname(__file__))


def main():
    tr = load_pair("train_mixture_1m.csv", "train_pile_loss_1m.csv")
    X = tr[[f"train_the_pile_{d}" for d in MIX_DOMAINS]].to_numpy(dtype=float)
    Y = tr[[f"metric/the_pile_{d}_val_loss" for d in LOSS_DOMAINS]].to_numpy(dtype=float)
    nd = len(MIX_DOMAINS)
    models = [Ridge(alpha=RIDGE_ALPHA).fit(X, Y[:, j]) for j in range(len(LOSS_DOMAINS))]
    B = np.stack([m.coef_ for m in models]).mean(axis=0)
    b0 = np.mean([m.intercept_ for m in models])

    # 无约束 LP 上界 (标定)
    res = linprog(B, A_eq=np.ones((1, nd)), b_eq=[1.0], bounds=[(0, 1)] * nd, method="highs")
    L_unif = float(B @ (np.ones(nd) / nd) + b0)
    L_lp = float(B @ res.x + b0)
    L_train_best = float(min(B @ tr[[f"train_the_pile_{d}" for d in MIX_DOMAINS]].to_numpy(dtype=float).T + b0))

    caps = [0.10, 0.20, 0.30, 0.50, 0.70, 1.00]
    lam = 0.5 * np.abs(B).mean()
    rows = []

    def obj(x):
        return B @ x + lam * np.sum((x - 1 / nd) ** 2)

    def cons(x):
        return 1.0 - x.sum()

    for cap in caps:
        if abs(cap - 1.0) < 1e-12:
            # cap=1.0 即无约束 (仅正则项促多样); linprog 为纯线性上界
            L_reg = L_lp
            xs = res.x
        else:
            sol = minimize(obj, np.ones(nd) / nd, method="SLSQP",
                           constraints={"type": "eq", "fun": cons},
                           bounds=[(0, cap)] * nd, options={"maxiter": 500})
            xs = sol.x
            L_reg = float(B @ xs + b0)
        gain_pct = (L_unif - L_reg) / L_unif * 100
        active = sorted([(d, float(w)) for w, d in zip(xs, MIX_DOMAINS) if w > 0.02],
                        key=lambda t: -t[1])
        rows.append({"cap": cap, "L_reg": L_reg, "gain_pct": gain_pct,
                     "active": active})
        print(f"cap={cap:.2f}: 降幅 {gain_pct:.2f}% | 活跃域(>2%): "
              f"{[(d, round(w,2)) for d, w in active]}")

    train_gain_pct = (L_unif - L_train_best) / L_unif * 100
    rows.append({"cap": "train_best", "L_reg": L_train_best,
                 "gain_pct": train_gain_pct, "active": "实测最优混合行"})
    print(f"\n实测训练最优混合行: 降幅 {train_gain_pct:.2f}%")

    out = {"L_unif": L_unif, "L_lp": L_lp, "L_train_best": L_train_best,
           "rows": rows, "ridge_alpha": RIDGE_ALPHA}
    with open(os.path.join(EX, "v98_p1_prescribe_cap.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    pd.DataFrame([{k: v for k, v in r.items() if k != "active"} for r in rows]).to_csv(
        os.path.join(EX, "v98_p1_prescribe_cap.csv"), index=False, encoding="utf-8-sig")

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
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    cs = np.array([r["cap"] for r in rows if isinstance(r["cap"], float)])
    gs = np.array([r["gain_pct"] for r in rows if isinstance(r["cap"], float)])
    ax.plot(cs, gs, "o-", color="#177cb0", lw=1.8, ms=5, label="处方收益 (上限+正则)")
    ax.axhline(train_gain_pct, color="#3eede7", ls="--", lw=1.3,
               label=f"实测训练最优混合行 {train_gain_pct:.1f}%")
    ax.axhline(0, color="k", lw=0.7)
    for c, g in zip(cs, gs):
        ax.annotate(f"{g:.1f}%", (c, g), textcoords="offset points",
                    xytext=(0, 6), ha="center", fontsize=8)
    ax.set_xlabel("单域配比上限 c")
    ax.set_ylabel("平均验证损失相对均匀配比降幅 (%)")
    ax.set_title("配比处方收益 vs 多样性上限")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v98_p1_prescribe_cap.png"), dpi=200)
    plt.close(fig)
    print("\nDONE v98")


if __name__ == "__main__":
    main()