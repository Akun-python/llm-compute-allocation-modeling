# -*- coding: utf-8 -*-
"""
v75 实验: 跨框架岭回归验证 —— 配比-Loss 模型与收缩指数数值稳定性核验 (P1)
同一数据 (A4+A5 训练 512 组, A6-A11 检验 1M/60M/1B), 同一模型
(Loss_j = b0 + Σ b_i p_i, 17 域配比 -> 13 目标域 Loss, L2 正则 alpha=1),
5 个独立拟合框架:
  1) sklearn Ridge solver=auto   (主链路, 闭式 Cholesky)
  2) sklearn Ridge solver=lsqr   (迭代最小二乘)
  3) numpy 闭式解  (Xc'Xc + aI)^{-1} Xc'yc, 显式复现 sklearn 去中心化)
  4) scipy least_squares TRF     (堆叠残差 [yc-Xc b; sqrt(a) b])
  5) torch Adam                  (罚目标梯度下降)
比较: 13 域系数跨框架最大相对偏差; 3 尺度系数范数幂律收缩指数 kappa =>
  配比-Loss 系数与 kappa=0.314 结论不依赖估计器实现.
输出: experiments/v75_p1_ridge_frameworks.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import A, BASE, MIX_DOMAINS, LOSS_DOMAINS, mixture_cols, loss_cols

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

ALPHA = 1.0
SCALES = ["1M_train", "60M", "1B"]
NS = np.array([0.001, 0.06, 1.0])


def load_pair(mix_name, loss_name):
    m = pd.read_csv(os.path.join(A, "regmix_tables", mix_name))
    l = pd.read_csv(os.path.join(A, "regmix_tables", loss_name))
    return m.merge(l, on="index")


def prepare(df):
    return (df[mixture_cols()].to_numpy(dtype=float),
            df[loss_cols()].to_numpy(dtype=float))


def fit_sklearn(X, y, solver):
    from sklearn.linear_model import Ridge
    kwargs = {"tol": 1e-12} if solver == "lsqr" else {}
    return Ridge(alpha=ALPHA, solver=solver, **kwargs).fit(X, y).coef_


def fit_numpy(X, y):
    """闭式岭解, 显式复现 sklearn 去中心化: coef 定义在去中心特征上"""
    Xm = X - X.mean(axis=0)
    ym = y - y.mean()
    A_ = Xm.T @ Xm + ALPHA * np.eye(X.shape[1])
    return np.linalg.solve(A_, Xm.T @ ym)


def fit_scipy(X, y):
    from scipy.optimize import least_squares
    Xm = X - X.mean(axis=0)
    ym = y - y.mean()

    def resid(b):
        return np.concatenate([ym - Xm @ b, np.sqrt(ALPHA) * b])
    sol = least_squares(resid, np.zeros(X.shape[1]), method="trf",
                        max_nfev=5000, xtol=1e-15, ftol=1e-15, gtol=1e-15)
    return sol.x


def fit_torch(X, y, steps=3000):
    import torch
    Xm = X - X.mean(axis=0)
    ym = y - y.mean()
    tX = torch.tensor(Xm, dtype=torch.float64)
    ty = torch.tensor(ym, dtype=torch.float64)
    b = torch.zeros(X.shape[1], dtype=torch.float64, requires_grad=True)
    opt = torch.optim.Adam([b], lr=0.05)
    best_v, best_b = np.inf, None
    for _ in range(steps):
        opt.zero_grad()
        r = ty - tX @ b
        loss = torch.sum(r ** 2) + ALPHA * torch.sum(b ** 2)
        loss.backward()
        opt.step()
        if float(loss) < best_v:
            best_v, best_b = float(loss), b.detach().numpy().copy()
    return best_b


RUNNERS = {"sklearn-auto": lambda X, y: fit_sklearn(X, y, "auto"),
           "sklearn-lsqr": lambda X, y: fit_sklearn(X, y, "lsqr"),
           "numpy-closed": fit_numpy,
           "scipy-TRF": fit_scipy,
           "torch-Adam": fit_torch}


def kappa_from(coefs_by_scale):
    """coefs_by_scale: dict scale -> (13x17) 系数矩阵; 返回 kappa (幂律拟合)"""
    norms = np.array([np.linalg.norm(coefs_by_scale[s]) for s in SCALES])
    mask = norms > 0
    A_, k = np.polyfit(np.log(NS[mask]), np.log(norms[mask]), 1)
    return -A_, norms


def main():
    train = load_pair("train_mixture_1m.csv", "train_pile_loss_1m.csv")
    Xtr, Ytr = prepare(train)
    tests = {"60M": load_pair("test_mixture_60m.csv", "test_pile_loss_60m.csv"),
             "1B": load_pair("test_mixture_1B.csv", "test_pile_loss_1B.csv")}
    sets = {"1M_train": (Xtr, Ytr),
            "60M": prepare(tests["60M"]),
            "1B": prepare(tests["1B"])}
    print(f"数据: train={Xtr.shape} 60M={sets['60M'][0].shape} 1B={sets['1B'][0].shape} "
          f"目标域={len(LOSS_DOMAINS)}")

    # 每个框架: scale -> 13x17 系数矩阵 (每域独立拟合)
    fitted = {}
    for fw, fn in RUNNERS.items():
        per_scale = {}
        for sname in SCALES:
            Xs, Ys = sets[sname]
            coefs = np.array([fn(Xs, Ys[:, j]) for j in range(len(LOSS_DOMAINS))])
            per_scale[sname] = coefs
        fitted[fw] = per_scale
        k, norms = kappa_from(per_scale)
        print(f"  {fw:14s} kappa={k:.6f}  ||β||@1M/60M/1B = "
              f"{norms[0]:.4f}/{norms[1]:.4f}/{norms[2]:.4f}")

    ref = fitted["sklearn-auto"]
    rows = []
    for fw in RUNNERS:
        maxdev = 0.0
        for sname in SCALES:
            # 相对偏差口径: 相对显著系数幅度 (|ref|<1e-3·max|ref| 视为近零, 不放大噪声)
            dev = np.abs(fitted[fw][sname] - ref[sname])
            denom = np.maximum(np.abs(ref[sname]), 1e-3 * np.abs(ref[sname]).max())
            maxdev = max(maxdev, float((dev / denom).max()))
        k, norms = kappa_from(fitted[fw])
        rows.append({"framework": fw, "max_coef_rel_dev": maxdev,
                     "kappa": float(k),
                     "norm_1M": float(norms[0]), "norm_60M": float(norms[1]),
                     "norm_1B": float(norms[2])})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v75_p1_ridge_frameworks.csv"), index=False, encoding="utf-8-sig")

    kappas = rdf["kappa"].to_numpy()
    devs = rdf["max_coef_rel_dev"].to_numpy()
    print(f"\nkappa 跨框架: 最小 {kappas.min():.6f} 最大 {kappas.max():.6f} "
          f"(极差 {kappas.max()-kappas.min():.3e})")
    print(f"系数最大相对偏差: 最小 {devs.min():.3e} 最大 {devs.max():.3e}")
    agg = {"n_train": int(len(Xtr)), "alpha": ALPHA, "domains": len(LOSS_DOMAINS),
           "kappa": {fw: float(r["kappa"]) for _, r in rdf.iterrows()},
           "kappa_range": float(kappas.max() - kappas.min()),
           "max_coef_rel_dev": {fw: float(r["max_coef_rel_dev"]) for _, r in rdf.iterrows()}}
    with open(os.path.join(EX, "v75_p1_ridge_frameworks.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rdf.to_dict("records"), "agg": agg}, f, ensure_ascii=False, indent=2)

    # ---- 图: (a) 系数最大相对偏差; (b) 收缩曲线 + kappa ----
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    ax = axes[0]
    fws = list(RUNNERS.keys())
    ax.bar(fws[1:], devs[1:], color=["#1685a9", "#3eede7", "#70f3ff", "#44cef6"])
    ax.set_yscale("log")
    ax.set_ylabel("系数最大相对偏差 (vs sklearn-auto, 对数轴)")
    ax.set_title("(a) 跨框架系数一致性 (13 域 × 3 尺度)")
    for i, v in enumerate(devs[1:]):
        ax.text(i, v * 1.6, f"{v:.1e}", ha="center", fontsize=8)
    ax.grid(alpha=0.3, axis="y")

    ax = axes[1]
    cols = ["#177cb0", "#1685a9", "#3eede7", "#70f3ff", "#44cef6"]
    for i, fw in enumerate(fws):
        norms = np.array([np.linalg.norm(fitted[fw][s]) for s in SCALES])
        ax.plot(NS, norms, "o-", color=cols[i], lw=1.6, label=f"{fw} (κ={kappas[i]:.3f})")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("参数量 N (B, 对数轴)"); ax.set_ylabel("||β|| (对数轴)")
    ax.set_title("(b) 系数范数收缩曲线与幂律指数")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=7.5)
    fig.suptitle("五框架岭回归交叉验证 —— 配比-Loss 系数与收缩指数 κ 数值稳定性", fontsize=12, y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(EX, "v75_p1_ridge_frameworks.png"), dpi=200)
    plt.close(fig)
    print("\ndone v75")


if __name__ == "__main__":
    main()