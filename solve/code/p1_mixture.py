# -*- coding: utf-8 -*-
"""
问题一(2): 17 域配比 - Loss 定量关系建模 (RegMix 数据 A4-A15)
思路:
  1) 每个目标域 j 的 Loss 对 17 维配比 p 做带正则的线性回归 (Loss_j = b0 + Σ b_i p_i + eps)
     配比满足单纯形约束 => 采用"去一基"参数化或直接 L2 正则 (岭回归) 处理共线性;
  2) 训练: A4(配比)+A5(Loss) 512 组; 检验: A6/A7(1M), A8/A9(60M), A10/A11(1B) 各 256/256/64 组;
  3) 外推: A12-A15 (10B/70B 预估 Loss) 检验模型尺度外推稳健性;
  4) 跨域分析: 各训练域对目标域 Loss 的边际效应排序; 负向/正向显著性;
  5) 质量引入: 用问题一域级 Q 对领域做先验加权 (质量高领域权重向 0 收缩), 对比有无质量先验的预测误差.
输出: results/p1_mixture_*.csv, figures/p1_mixture_*.png
"""
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.metrics import r2_score
from sklearn.model_selection import KFold
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from common import A, RES, FIG, BASE, MIX_DOMAINS, LOSS_DOMAINS, mixture_cols, loss_cols

for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

RIDGE_ALPHA = 1.0

def load_pair(mix_name, loss_name):
    m = pd.read_csv(os.path.join(A, "regmix_tables", mix_name))
    l = pd.read_csv(os.path.join(A, "regmix_tables", loss_name))
    df = m.merge(l, on="index")
    return df

def prepare(df):
    X = df[mixture_cols()].to_numpy(dtype=float)
    Y = df[loss_cols()].to_numpy(dtype=float)
    return X, Y

def fit_eval(Xtr, Ytr, Xte, Yte, alpha=RIDGE_ALPHA, scale_correct=True):
    """对每个目标域拟合岭回归, 返回 (模型列表, 指标字典)
    scale_correct=True: 跨尺度检验时, 绝对 Loss 基线随参数量平移,
    用"尺度内去均值"的判定系数 R²_adj (等价 corr(ŷ,y)²) 衡量配比排序效应的迁移."""
    models, metrics = [], {}
    per_domain_te = []
    for j, dom in enumerate(LOSS_DOMAINS):
        mdl = Ridge(alpha=alpha)
        mdl.fit(Xtr, Ytr[:, j])
        yhat = mdl.predict(Xte)
        y = Yte[:, j]
        rmse = np.sqrt(np.mean((y - yhat) ** 2))
        if scale_correct:
            yhat_c = yhat - yhat.mean() + y.mean()
            ss_res = np.sum((y - yhat_c) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
            r = np.corrcoef(y, yhat)[0, 1] if np.std(y) > 1e-12 else 0.0
        else:
            r2 = r2_score(y, yhat)
            r = np.corrcoef(y, yhat)[0, 1] if np.std(y) > 1e-12 else 0.0
        models.append(mdl)
        metrics[dom] = {"r2_test": r2, "rmse_test": rmse, "corr_test": r,
                        "coef": mdl.coef_, "intercept": mdl.intercept_}
        per_domain_te.append(r2)
    metrics["_mean_r2"] = np.mean(per_domain_te)
    return models, metrics

def main():
    # ---------- 训练/检验 ----------
    train = load_pair("train_mixture_1m.csv", "train_pile_loss_1m.csv")
    Xtr, Ytr = prepare(train)
    tests = {
        "1M": load_pair("test_mixture_1m.csv", "test_pile_loss_1m.csv"),
        "60M": load_pair("test_mixture_60m.csv", "test_pile_loss_60m.csv"),
        "1B": load_pair("test_mixture_1B.csv", "test_pile_loss_1B.csv"),
    }
    print("train:", train.shape, "tests:", {k: v.shape for k, v in tests.items()})

    # 基准: 岭回归 (用 1M 训练集)
    models_1m, met_1m = fit_eval(Xtr, Ytr, Xtr, Ytr)
    print("in-sample mean R2:", met_1m["_mean_r2"])

    # 逐检验集评估
    rows = []
    for name, tdf in tests.items():
        Xte, Yte = prepare(tdf)
        _, met = fit_eval(Xtr, Ytr, Xte, Yte)
        rows.append({"scale": name, "n": len(tdf), "mean_r2": met["_mean_r2"],
                     "mean_rmse": np.mean([met[d]["rmse_test"] for d in LOSS_DOMAINS])})
    perf = pd.DataFrame(rows)
    perf.to_csv(os.path.join(RES, "p1_mixture_test_perf.csv"), index=False, encoding="utf-8-sig")
    print(perf.to_string())

    # 外推表评估 (用 10B/70B 的 est Loss 对照)
    est_rows = []
    for scale in ("10b", "70b"):
        m = pd.read_csv(os.path.join(A, "regmix_tables", f"est_mixture_{scale}.csv"))
        l = pd.read_csv(os.path.join(A, "regmix_tables", f"est_pile_loss_{scale}.csv"))
        tdf = m.merge(l, on="index")
        Xte, Yte = prepare(tdf)
        _, met = fit_eval(Xtr, Ytr, Xte, Yte)
        est_rows.append({"scale": scale, "n": len(tdf), "mean_r2": met["_mean_r2"],
                         "mean_rmse": np.mean([met[d]["rmse_test"] for d in LOSS_DOMAINS])})
    est_perf = pd.DataFrame(est_rows)
    est_perf.to_csv(os.path.join(RES, "p1_mixture_extrap_perf.csv"), index=False, encoding="utf-8-sig")
    print(est_perf.to_string())

    # ---------- 领域边际效应 ----------
    coef_df = pd.DataFrame({dom: met_1m[dom]["coef"] for dom in LOSS_DOMAINS}, index=MIX_DOMAINS)
    coef_df["mean_effect"] = coef_df.mean(axis=1)
    coef_df["abs_mean_effect"] = coef_df["mean_effect"].abs()
    coef_df = coef_df.sort_values("abs_mean_effect", ascending=False)
    coef_df.to_csv(os.path.join(RES, "p1_mixture_coefs.csv"), encoding="utf-8-sig")

    # 交叉验证稳定性 (5-fold on train)
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_r2 = []
    for tr_idx, va_idx in kf.split(Xtr):
        _, met = fit_eval(Xtr[tr_idx], Ytr[tr_idx], Xtr[va_idx], Ytr[va_idx])
        cv_r2.append(met["_mean_r2"])
    print("5-fold CV mean R2:", np.mean(cv_r2), "+-", np.std(cv_r2))

    # ---------- 质量引入 (先验加权岭回归) ----------
    # 用问题一域级 Q 映射到 17 域: 直接映射域取 Q, 其余取 0.5
    try:
        dq = pd.read_csv(os.path.join(RES, "p1_domain_quality.csv"))
        qmap = dict(zip(dq["domain"], dq["Q_weighted"]))
    except FileNotFoundError:
        qmap = {}
    dom_q = pd.Series([qmap.get(d, 0.5) for d in MIX_DOMAINS], index=MIX_DOMAINS)

    # 质量加权: 高 Q 域配比系数向 0 收缩更多 (高质量数据"自带"低损失), 通过样本加权实现:
    #   每行样本按 其领域质量加权 — 但配比是全局的, 采用岭惩罚按域质量缩放
    q_ridge = Ridge(alpha=RIDGE_ALPHA)
    q_ridge.fit(Xtr, Ytr)
    q_pen = np.abs(dom_q.to_numpy())  # 作为额外特征乘子: 直接使用 Q 作为回归特征
    Xq = np.hstack([Xtr, np.outer(np.ones(Xtr.shape[0]), dom_q.to_numpy())])
    # 增加"整体质量"特征: 配比与域质量的点积 (单一标量)
    qmix = Xtr @ dom_q.to_numpy()
    Xq2 = np.hstack([Xtr, qmix.reshape(-1, 1)])
    models_q, met_q = fit_eval(Xq2, Ytr, Xq2, Ytr)
    print("with quality feature: in-sample mean R2 =", met_q["_mean_r2"])

    # 检验质量增强是否提升检验误差
    comp_rows = []
    for name, tdf in tests.items():
        Xte, Yte = prepare(tdf)
        qmix_te = Xte @ dom_q.to_numpy()
        Xq2te = np.hstack([Xte, qmix_te.reshape(-1, 1)])
        _, met_plain = fit_eval(Xtr, Ytr, Xte, Yte)
        _, met_q = fit_eval(Xq2, Ytr, Xq2te, Yte)
        comp_rows.append({"scale": name,
                          "plain_r2": met_plain["_mean_r2"], "quality_r2": met_q["_mean_r2"],
                          "plain_rmse": np.mean([met_plain[d]["rmse_test"] for d in LOSS_DOMAINS]),
                          "quality_rmse": np.mean([met_q[d]["rmse_test"] for d in LOSS_DOMAINS])})
    comp = pd.DataFrame(comp_rows)
    comp.to_csv(os.path.join(RES, "p1_mixture_quality_compare.csv"), index=False, encoding="utf-8-sig")
    print(comp.to_string())

    # ---------- 跨尺度收缩分析: 各尺度独立拟合, 比较系数 ----------
    scale_fits = {}
    all_sets = {"1M_train": train, "1M_test": tests["1M"], "60M": tests["60M"], "1B": tests["1B"],
                "10b": pd.read_csv(os.path.join(A, "regmix_tables", "est_mixture_10b.csv")).merge(
                    pd.read_csv(os.path.join(A, "regmix_tables", "est_pile_loss_10b.csv")), on="index"),
                "70b": pd.read_csv(os.path.join(A, "regmix_tables", "est_mixture_70b.csv")).merge(
                    pd.read_csv(os.path.join(A, "regmix_tables", "est_pile_loss_70b.csv")), on="index")}
    for name, tdf in all_sets.items():
        Xte, Yte = prepare(tdf)
        # 每域独立岭回归, 记录系数与残差均方
        coefs = []
        for j, dom in enumerate(LOSS_DOMAINS):
            m = Ridge(alpha=RIDGE_ALPHA).fit(Xtr if name == "1M_train" else Xte, Ytr[:, j] if name == "1M_train" else Yte[:, j])
            coefs.append(m.coef_)
        scale_fits[name] = np.array(coefs)
    # 系数范数与余弦相似度 (相对 1M_train)
    ref = scale_fits["1M_train"]
    rows = []
    for name, cf in scale_fits.items():
        norm = np.linalg.norm(cf)
        cos = np.sum(ref * cf) / (np.linalg.norm(ref) * norm + 1e-12)
        rows.append({"scale": name, "coef_norm": norm, "cos_sim_vs_1M": cos})
    shrink = pd.DataFrame(rows)
    shrink.to_csv(os.path.join(RES, "p1_mixture_scale_shrink.csv"), index=False, encoding="utf-8-sig")
    print("\n跨尺度系数收缩:")
    print(shrink.to_string())

    # 幂律收缩拟合: ||β(N)|| = c * N^{-κ} (用 1M/60M/1B 三尺度, 对数回归)
    Ns = np.array([0.001, 0.06, 1.0])   # B 单位
    norms = np.array([shrink[shrink["scale"] == s]["coef_norm"].values[0] for s in ["1M_train", "60M", "1B"]])
    mask = norms > 0
    A_, kappa = np.polyfit(np.log(Ns[mask]), np.log(norms[mask]), 1)
    kappa = -A_
    print(f"系数范数收缩幂律: ||β|| = {np.exp(A_):.4f} * N^{{-{kappa:.3f}}}")
    with open(os.path.join(RES, "p1_shrink_kappa.txt"), "w", encoding="utf-8") as f:
        f.write(f"kappa={kappa:.4f}\nbase={np.exp(A_):.6f}\n")

    # ---------- 图 ----------
    # 1) 检验集 R2 条形
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = perf["scale"]; y = perf["mean_r2"]
    bars = ax.bar(x, y, color="#2563EB", alpha=0.85)
    for b, v in zip(bars, y):
        ax.text(b.get_x() + b.get_width()/2, v + 0.005, f"{v:.3f}", ha="center")
    ax.set_ylabel("13 域平均 R2 (尺度内去均值)")
    ax.set_title("配比-Loss 岭回归在三个参数尺度检验集上的表现")
    ax.set_ylim(0, 1.0)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_mixture_test.png"), dpi=200); plt.close(fig)

    # 2) 跨尺度收缩曲线
    fig, ax = plt.subplots(figsize=(7, 4.8))
    ax.plot(Ns, norms, "o-", color="#7C3AED", lw=2)
    Nfit = np.linspace(0.0005, 1.2, 100)
    ax.plot(Nfit, np.exp(A_) * Nfit ** (-kappa), "--", color="#EF4444", lw=1.5,
            label=f"幂律拟合: ||β|| = {np.exp(A_):.3f}·N^(−{kappa:.3f})")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("参数量 N (B, 对数轴)"); ax.set_ylabel("配比系数范数 ||β|| (对数轴)")
    ax.set_title("配比边际效应的跨尺度收缩")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_mixture_shrink.png"), dpi=200); plt.close(fig)

    # 2) 域边际效应排序
    fig, ax = plt.subplots(figsize=(10, 5))
    top = coef_df.head(17)
    ax.barh(top.index[::-1], top["mean_effect"], color=["#EF4444" if v < 0 else "#10B981" for v in top["mean_effect"][::-1]])
    ax.axvline(0, color="gray", lw=0.8)
    ax.set_xlabel("对 13 域 Loss 的平均边际效应 (增加 1% 配比)")
    ax.set_title("17 个训练域对验证损失的边际效应排序")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_mixture_effects.png"), dpi=200); plt.close(fig)

    # 3) 预测 vs 实际 (1B 检验集, 平均 Loss)
    Xte, Yte = prepare(tests["1B"])
    avg_yhat = np.mean([models_1m[j].predict(Xte) for j in range(len(LOSS_DOMAINS))], axis=0)
    avg_y = Yte.mean(axis=1)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(avg_y, avg_yhat, s=18, alpha=0.7, color="#2563EB")
    lims = [min(avg_y.min(), avg_yhat.min()), max(avg_y.max(), avg_yhat.max())]
    ax.plot(lims, lims, "r--", lw=1)
    ax.set_xlabel("实际平均验证 Loss"); ax.set_ylabel("预测平均验证 Loss")
    ax.set_title("1B 检验集: 平均 Loss 预测 vs 实际")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_mixture_scatter.png"), dpi=200); plt.close(fig)

    print("done p1_mixture")

if __name__ == "__main__":
    main()
