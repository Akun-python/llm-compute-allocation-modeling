# -*- coding: utf-8 -*-
"""
v15 实验: 无监督自编码器质量评分 (与 TOPSIS 组合赋权对照)
思路: 高质量文本在 22 维质量指标上"像典型好样本", 自编码器重构误差小的样本
视为高质量; 低质/异常样本重构误差大. 实现两档:
  - PCA 线性重构 (线性自编码闭式解)
  - MLP 自编码 (非线性)
把每个样本按重构误差升序映射为质量分 (误差小=质量高), 聚合成 7 域质量,
与基线 TOPSIS 域排序对照; 并检查与冲突指数的关系.
输出: experiments/v15_p1_ae.csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
import p1_quality as P
from common import A, RES, FIG, BASE
from sklearn.decomposition import PCA
from sklearn.neural_network import MLPRegressor
from scipy.stats import spearmanr

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


def load_data():
    a1 = P.load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"))
    a2 = P.load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"))
    a3 = P.load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"))
    df = pd.concat([P.build_frame(a1), P.build_frame(a2, domain_hint="arxiv"),
                    P.build_frame(a3, domain_hint="github")], ignore_index=True)
    Xraw = df[P.ALL_IND].to_numpy(dtype=float)
    for j, k in enumerate(P.ALL_IND):
        if not P.DIRECTION[k]:
            Xraw[:, j] = -Xraw[:, j]
    X = P.winsorize_minmax(Xraw)
    return X, df["_source_domain"].to_numpy()


def main():
    X, dom = load_data()
    n = X.shape[0]
    print("data:", X.shape, "NaN:", np.isnan(X).sum())
    # 用于自编码的矩阵: 列均值填补 (主流程的赋权/聚合均为 NaN 容忍口径)
    Ximp = np.nan_to_num(X, nan=0.0)
    # 0 可能是"缺失"而非真实低值, 用列均值填充更中性
    for j in range(X.shape[1]):
        col = X[:, j]
        if np.isnan(col).any():
            Ximp[:, j] = np.where(np.isnan(col), np.nanmean(col), col)
    X = Ximp

    # 基线 TOPSIS 组合赋权
    w_ent, _ = P.entropy_weight(X)
    w_cri_fast = None
    # 用 p1 的 critic (可能与主代码一致)
    w_cri, _, _ = P.critic_weight(X)
    w = 0.5 * w_ent + 0.5 * w_cri
    Q_base = P.topsis(X, w)
    dq_base = pd.DataFrame({"Q": Q_base, "domain": dom}).groupby("domain")["Q"].mean().sort_values(ascending=False)
    print("基线 TOPSIS 域排序:", dict(zip(dq_base.index, np.round(dq_base.values, 3))))

    # PCA 线性自编码 (重构误差)
    pca = PCA(n_components=8, random_state=0).fit(X)
    Xhat_pca = pca.inverse_transform(pca.transform(X))
    err_pca = np.mean((X - Xhat_pca) ** 2, axis=1)
    # 误差小 = 质量高 -> 质量分 = 1 - 归一化误差
    e = np.clip(err_pca, np.percentile(err_pca, 1), np.percentile(err_pca, 99))
    Q_pca = 1 - (e - e.min()) / (e.max() - e.min())

    # MLP 自编码 (16->8->16, 快速训练, 抽样子集以控时间)
    rng = np.random.default_rng(0)
    idx = rng.choice(n, min(n, 60000), replace=False)
    Xs = X[idx]
    mlp = MLPRegressor(hidden_layer_sizes=(12, 12), activation="relu", solver="adam",
                       max_iter=30, random_state=0, learning_rate_init=1e-3, batch_size=2048, verbose=False)
    mlp.fit(Xs, Xs)
    Xhat_mlp = mlp.predict(X)
    err_mlp = np.mean((X - Xhat_mlp) ** 2, axis=1)
    e2 = np.clip(err_mlp, np.percentile(err_mlp, 1), np.percentile(err_mlp, 99))
    Q_mlp = 1 - (e2 - e2.min()) / (e2.max() - e2.min())

    # 域聚合
    def domq(q):
        return pd.DataFrame({"Q": q, "domain": dom}).groupby("domain")["Q"].mean().sort_values(ascending=False)
    dq_pca = domq(Q_pca)
    dq_mlp = domq(Q_mlp)
    print("PCA 重构误差 域排序:", dict(zip(dq_pca.index, np.round(dq_pca.values, 3))))
    print("MLP 重构误差 域排序:", dict(zip(dq_mlp.index, np.round(dq_mlp.values, 3))))

    doms = dq_base.index.tolist()
    rk = lambda dq: pd.Series(np.arange(len(dq)), index=dq.index)
    for name, dq in [("pca", dq_pca), ("mlp", dq_mlp)]:
        rho = rk(dq).reindex(doms).corr(rk(dq_base).reindex(doms), method="spearman")
        top = dq.index[0]
        print(f"[{name}] 域排序 Spearman vs TOPSIS = {rho:.3f}, top 域 = {top}")

    # 冲突关系: 重构误差高 (=质量低) 的样本是否也是高冲突样本?
    ci, qc, qf = P.conflict_index(X)
    m = np.isfinite(ci) & np.isfinite(err_pca)
    rho_ei = spearmanr(err_pca[m], ci[m]).statistic
    print("PCA 重构误差 vs 冲突指数: rho = %.3f" % rho_ei)
    hi_conf = ci > np.nanquantile(ci, 0.9)
    hi_e = err_pca > np.percentile(err_pca, 90)
    overlap = np.mean(hi_conf & hi_e) / np.mean(hi_conf)
    print("高冲突∩高重构误差 覆盖率: %.3f" % overlap)

    pd.DataFrame({"Q_topsis": Q_base, "Q_pca_ae": Q_pca, "Q_mlp_ae": Q_mlp,
                  "conflict": ci}).to_csv(
        os.path.join(EX, "v15_p1_ae_scores.csv"), index=False, encoding="utf-8-sig")

    # 图: 域级三方法对比
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(doms))
    ax.bar(x - 0.25, dq_base.reindex(doms).values, 0.22, color="#2563EB", label="TOPSIS 组合赋权")
    ax.bar(x, dq_pca.reindex(doms).values, 0.22, color="#10B981", label="PCA 自编码")
    ax.bar(x + 0.25, dq_mlp.reindex(doms).values, 0.22, color="#F59E0B", label="MLP 自编码")
    ax.set_xticks(x); ax.set_xticklabels(doms, rotation=20); ax.set_ylabel("域平均质量分")
    ax.set_title("v15: 监督/无监督质量评分家族对比")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v15_p1_ae.png"), dpi=200); plt.close(fig)

    print("\ndone v15")


if __name__ == "__main__":
    main()