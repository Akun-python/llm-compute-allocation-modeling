# -*- coding: utf-8 -*-
"""
v2 实验: 问题一算法家族对比 (不被单一框架局限)
对比:
  A) 赋权家族: 熵权 / CRITIC / 组合(基线) / PCA权重 / 等权
  B) 聚合家族: TOPSIS(基线) / 加权和 / 灰色关联度 GRA 贴近度
  C) 冲突度量家族: 双族均值差(基线) / 指标离散度(变异系数) / 信息熵分歧
  D) 配比模型家族: 岭回归(基线) / Lasso / ElasticNet / Huber / 梯度提升树
输出: experiments/v2_p1_*.csv + 图, 结论写 experiments/v2_conclusion.md
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import A, B, RES, FIG, BASE
import p1_quality as P1
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge, Lasso, ElasticNet, HuberRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

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


def load_X():
    """复用基线预处理得到归一化 X 与域名"""
    a1 = P1.load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"))
    a2 = P1.load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"))
    a3 = P1.load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"))
    df = pd.concat([P1.build_frame(a1), P1.build_frame(a2, "arxiv"), P1.build_frame(a3, "github")], ignore_index=True)
    Xraw = df[P1.ALL_IND].to_numpy(dtype=float)
    for j, k in enumerate(P1.ALL_IND):
        if not P1.DIRECTION[k]:
            Xraw[:, j] = -Xraw[:, j]
    X = P1.winsorize_minmax(Xraw)
    return X, df["_source_domain"].values


def pca_weight(X):
    """PCA 赋权: 各主成分贡献加权, 权重=各变量对前k个主成分载荷贡献"""
    Xs = StandardScaler().fit_transform(np.nan_to_num(X))
    pca = PCA(n_components=min(6, X.shape[1]))
    pca.fit(Xs)
    load = pca.components_ ** 2                      # (k, m)
    w = (load * pca.explained_variance_ratio_[:, None]).sum(axis=0)
    return w / w.sum()


def gra_close(X, w):
    """灰色关联度贴近度: 与正理想解的灰色关联度 (分辨系数 0.5)"""
    V = X * w
    V = np.nan_to_num(V, nan=0.0)          # 缺失列视为 0 (不贡献理想解)
    ideal = V.max(axis=0)
    diff = np.abs(V - ideal)
    dmin, dmax = diff.min(), diff.max()
    if dmax < 1e-12:
        return np.full(len(X), 1.0)
    zeta = (dmin + 0.5 * dmax) / (diff + 0.5 * dmax)
    return zeta.mean(axis=1)


def conflict_cv(X):
    """冲突度量B: 每样本指标变异系数 (方向统一后, 内部不一致度)"""
    return np.nanstd(X, axis=1) / np.maximum(np.nanmean(X, axis=1), 1e-9)


def conflict_entropy(X):
    """冲突度量C: 每样本指标概率化的信息熵分歧 (与均匀分布的 KL 距离上界)"""
    n, m = X.shape
    out = np.empty(n)
    for i in range(n):
        p = X[i] / np.maximum(X[i].sum(), 1e-12)
        p = np.clip(p, 1e-12, 1.0)
        ent = -(p * np.log(p)).sum() / np.log(m)
        out[i] = 1 - ent          # 越集中=>越不一致? 用 1-ent 表示"分歧度"
    return out


def main():
    X, doms = load_X()
    n = X.shape[0]
    print("X:", X.shape)

    # ========== A+B: 赋权家族 × 聚合家族 ==========
    w_ent, _ = P1.entropy_weight(X)
    w_cri, _, _ = P1.critic_weight(X)
    w_combo = 0.5 * w_ent + 0.5 * w_cri          # 基线
    w_pca = pca_weight(X)
    w_eq = np.full(22, 1 / 22)
    weights = {"entropy": w_ent, "critic": w_cri, "combo": w_combo, "pca": w_pca, "equal": w_eq}

    aggs = {}
    for wn, w in weights.items():
        aggs[f"topsis_{wn}"] = P1.topsis(X, w)
        aggs[f"wsum_{wn}"] = X @ w
        aggs[f"gra_{wn}"] = gra_close(X, w)
    agg_df = pd.DataFrame(aggs)

    # 域级质量: 每种方法
    rows = []
    for col in agg_df.columns:
        s = pd.Series(agg_df[col].values, index=np.arange(n))
        for d in ["book", "arxiv", "c4", "commoncrawl", "github", "wikipedia", "stackexchange"]:
            idx = doms == d
            rows.append({"method": col, "domain": d, "Q": float(s[idx].mean())})
    dom_long = pd.DataFrame(rows)
    dom_wide = dom_long.pivot(index="domain", columns="method", values="Q")
    dom_wide.to_csv(os.path.join(EX, "v2_p1_weights_agg_domains.csv"), encoding="utf-8-sig")
    print("\n域级质量分 (15 种方法):")
    print(dom_wide.round(3).to_string())

    # 方法间 Spearman 相关 (样本级)
    corr = agg_df.corr(method="spearman")
    corr.to_csv(os.path.join(EX, "v2_p1_method_corr.csv"), encoding="utf-8-sig")
    # 域排序一致性: 每种方法与基线 topsis_combo 的秩相关
    base_rank = dom_wide["topsis_combo"].rank()
    rank_rows = []
    for col in dom_wide.columns:
        rho = dom_wide[col].rank().corr(base_rank)
        rank_rows.append({"method": col, "domain_rank_rho_vs_base": rho})
    rank_df = pd.DataFrame(rank_rows).sort_values("domain_rank_rho_vs_base", ascending=False)
    rank_df.to_csv(os.path.join(EX, "v2_p1_rank_consistency.csv"), index=False, encoding="utf-8-sig")
    print("\n域排序与基线一致性:")
    print(rank_df.to_string(index=False))

    # ========== C: 冲突度量家族 ==========
    conf_base, qc, qf = P1.conflict_index(X)
    conf_cv = conflict_cv(X)
    conf_ent = conflict_entropy(X)
    cdf = pd.DataFrame({"base": conf_base, "cv": conf_cv, "entropy": conf_ent})
    cdf_corr = cdf.corr(method="spearman")
    cdf_corr.to_csv(os.path.join(EX, "v2_p1_conflict_corr.csv"), encoding="utf-8-sig")
    print("\n冲突度量相关 (Spearman):")
    print(cdf_corr.round(3).to_string())

    # 各度量 top-10% 样本与基线 top-10% 的 Jaccard 重合
    p90 = int(n * 0.1)
    s_base = set(np.argsort(conf_base)[-p90:])
    s_cv = set(np.argsort(conf_cv)[-p90:])
    s_ent = set(np.argsort(conf_ent)[-p90:])
    print("\n高冲突 top10% 重合率 (Jaccard):")
    print(" base-cv:", len(s_base & s_cv) / len(s_base | s_cv))
    print(" base-ent:", len(s_base & s_ent) / len(s_base | s_ent))

    # 对称截尾对三种度量的消解效果 (质量分前后变化, 域内单调性保持)
    w = w_combo
    Q_orig = P1.topsis(X, w)
    resolved = P1.robust_resolve(X, w, k=6)
    thr = np.nanpercentile(conf_base, 90)
    hi = conf_base > thr
    print(f"\n对称截尾消解 (基线冲突度量, 阈值 P90={thr:.3f}): 高冲突样本 {hi.sum()} 条, "
          f"Q均值 {Q_orig[hi].mean():.4f} -> {resolved[hi].mean():.4f}")

    # ========== D: 配比模型家族 ==========
    # 读 A4-A15 配比-损失 (1M_train 拟合) 复用 common.py 的列名
    from common import mixture_cols, loss_cols
    mres = []
    tm = pd.read_csv(os.path.join(A, "regmix_tables", "train_mixture_1m.csv"))
    tl = pd.read_csv(os.path.join(A, "regmix_tables", "train_pile_loss_1m.csv"))
    train1m = tm.merge(tl, on="index")
    Xtr = train1m[mixture_cols()].to_numpy(dtype=float)
    for j, loss in enumerate(loss_cols()):
        ytr = train1m[loss].to_numpy(dtype=float)
        short = loss.split("/")[-1]
        for model_name, mdl in [
            ("ridge", Ridge(alpha=1.0)), ("lasso", Lasso(alpha=0.01, max_iter=20000)),
            ("enet", ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=20000)),
            ("huber", HuberRegressor(alpha=1.0, max_iter=500)),
            ("gbt", GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=0)),
        ]:
            mdl.fit(Xtr, ytr)
            pred = mdl.predict(Xtr)
            resid = (ytr - pred) - (ytr - pred).mean()
            r2 = 1 - (resid ** 2).sum() / ((ytr - ytr.mean()) ** 2).sum()
            mres.append({"loss_domain": short, "model": model_name, "r2_fit_1m": r2})
    mdf = pd.DataFrame(mres)
    mdf.to_csv(os.path.join(EX, "v2_p1_mixture_families.csv"), index=False, encoding="utf-8-sig")
    pivot = mdf.pivot_table(index="model", values="r2_fit_1m", aggfunc="mean").sort_values("r2_fit_1m", ascending=False)
    print("\n配比模型家族 1M_train 拟合 R2 (13 损失域平均):")
    print(pivot.round(4).to_string())

    # 跨尺度: 用 60M/1B 测试集做尺度外推对比 (检验家族迁移稳健性)
    try:
        t60m = pd.read_csv(os.path.join(A, "regmix_tables", "test_mixture_60m.csv"))
        t60l = pd.read_csv(os.path.join(A, "regmix_tables", "test_pile_loss_60m.csv"))
        t1bm = pd.read_csv(os.path.join(A, "regmix_tables", "test_mixture_1B.csv"))
        t1bl = pd.read_csv(os.path.join(A, "regmix_tables", "test_pile_loss_1B.csv"))
        test60 = t60m.merge(t60l, on="index")
        test1b = t1bm.merge(t1bl, on="index")
        rows_x = []
        fams = [("ridge", Ridge(alpha=1.0)), ("lasso", Lasso(alpha=0.01, max_iter=20000)),
                ("enet", ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=20000)),
                ("huber", HuberRegressor(alpha=1.0, max_iter=500)),
                ("gbt", GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=0))]
        for scale, tdf in [("60M", test60), ("1B", test1b)]:
            Xte = tdf[mixture_cols()].to_numpy(dtype=float)
            for j, loss in enumerate(loss_cols()):
                ytr = train1m[loss].to_numpy(dtype=float)
                yte = tdf[loss].to_numpy(dtype=float)
                for model_name, mdl in fams:
                    mdl.fit(Xtr, ytr)
                    yhat = mdl.predict(Xte)
                    yhat_c = yhat - yhat.mean() + yte.mean()
                    r2 = 1 - ((yte - yhat_c) ** 2).sum() / ((yte - yte.mean()) ** 2).sum()
                    rows_x.append({"scale": scale, "loss_domain": loss.split("/")[-1],
                                   "model": model_name, "r2_xscale": r2})
        xdf = pd.DataFrame(rows_x)
        xdf.to_csv(os.path.join(EX, "v2_p1_mixture_xscale.csv"), index=False, encoding="utf-8-sig")
        pivot_x = xdf.pivot_table(index="model", values="r2_xscale", aggfunc="mean").sort_values("r2_xscale", ascending=False)
        print("\n跨尺度迁移 R2 (60M/1B 平均):")
        print(pivot_x.round(4).to_string())
    except Exception as e:
        print("60M/1B 测试集不可用:", e)

    # ========== 图 ==========
    fig, ax = plt.subplots(figsize=(9, 5))
    sel = ["topsis_combo", "topsis_entropy", "topsis_critic", "topsis_pca", "topsis_equal",
           "wsum_combo", "gra_combo"]
    sel = [c for c in sel if c in dom_wide.columns]
    dom_order = ["book", "arxiv", "c4", "commoncrawl", "github", "wikipedia", "stackexchange"]
    dd = dom_wide.loc[dom_order, sel]
    dd.plot(kind="bar", ax=ax, width=0.85)
    ax.set_ylabel("域级质量分 Q"); ax.set_title("v2: 赋权×聚合家族下的域级质量分")
    ax.legend(fontsize=7, ncol=3)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v2_p1_domains.png"), dpi=200); plt.close(fig)

    print("\ndone v2 p1")


if __name__ == "__main__":
    main()
