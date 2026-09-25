# -*- coding: utf-8 -*-
"""
v21 实验: 质量指标家族的经验聚类验证
对手工族划分 FAMILY_C(内容质量,15) / FAMILY_F(格式洁净,7) 做数据驱动核验:
1) 样本级 (同 p1 主链路 A 数据, winsorized+NaN填补) 指标间 Spearman 相关
   矩阵 -> 层次聚类 (1-rho, average) 切 2 簇 -> ARI/purity 对照手工族.
2) 域级聚合 (按 _source_domain 均值) 重复 -> 族结构在聚合层面更清晰.
3) 树状图输出 (染色手工族).
输出: experiments/v21_p1_family_cluster.png/.json
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import load_jsonl_xz, build_frame, winsorize_minmax, FAMILY_C, FAMILY_F, ALL_IND
from common import A, BASE

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)

from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.stats import rankdata
from sklearn.metrics import adjusted_rand_score
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


def load():
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"))
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"))
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"))
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    return df


def rank_corr(X):
    Xr = rankdata(X, axis=0)
    return np.corrcoef(Xr, rowvar=False)


def cluster_compare(R, y_true):
    d = 1 - np.clip(R, 0, 1)
    Z = linkage(d[np.triu_indices(len(d), 1)], method="average")
    lab2 = fcluster(Z, 2, criterion="maxclust")
    ari = adjusted_rand_score(y_true, lab2)
    pur = 0.0
    for cl in np.unique(lab2):
        members = y_true[lab2 == cl]
        pur += max(np.bincount(members, minlength=2)) / len(members) * len(members)
    pur /= len(lab2)
    return lab2, ari, pur, Z


def main():
    df = load()
    ind = [k for k in ALL_IND if k in df.columns]
    Xraw = df[ind].to_numpy(dtype=float)
    print("sample matrix:", Xraw.shape)
    X = winsorize_minmax(Xraw.copy())
    Xc = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    y_true = np.array([1 if k in FAMILY_C else 2 for k in ind])
    R = rank_corr(Xc)
    lab2, ari, pur, Z = cluster_compare(R, y_true)
    print(f"样本级 (n={len(Xc)}): ARI={ari:.3f} purity={pur:.3f}")
    for cl in np.unique(lab2):
        names = [ind[i] for i in np.where(lab2 == cl)[0]]
        print(f"  簇{cl} (n={len(names)}): {names}")

    # 域级聚合
    dom = df["_source_domain"].fillna("none").to_numpy()
    Xd = np.vstack([np.nanmean(Xc[dom == d_], axis=0) for d_ in sorted(set(dom))])
    Rd = rank_corr(Xd)
    lab2d, arid, purd, _ = cluster_compare(Rd, y_true)
    print(f"域级 (n={len(Xd)} 域): ARI={arid:.3f} purity={purd:.3f}")
    for cl in np.unique(lab2d):
        names = [ind[i] for i in np.where(lab2d == cl)[0]]
        print(f"  簇{cl} (n={len(names)}): {names}")

    # ---- 树状图
    fig, ax = plt.subplots(figsize=(11, 5.5))
    dendrogram(Z, labels=ind, orientation="left", ax=ax, leaf_font_size=8)
    for lb in ax.get_yticklabels():
        nm = lb.get_text()
        lb.set_color("#3eede7" if nm in FAMILY_C else "#177cb0")
    ax.set_title("质量指标层次聚类 (样本级 Spearman; 橙=内容族C / 蓝=格式族F; 无清晰族簇)")
    ax.set_xlabel("1 - Spearman 相关距离")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v21_p1_family_cluster.png"), dpi=200)
    plt.close(fig)

    # ---- 正交性统计 (构念效度旁证)
    jc = np.array([ind.index(k) for k in FAMILY_C]); jf = np.array([ind.index(k) for k in FAMILY_F])
    Mcc = R[np.ix_(jc, jc)]; Mff = R[np.ix_(jf, jf)]; Mcf = R[np.ix_(jc, jf)]
    stats = {"within_C_mean_rho": float(Mcc[~np.eye(len(jc), dtype=bool)].mean()),
             "within_F_mean_rho": float(Mff[~np.eye(len(jf), dtype=bool)].mean()),
             "cross_CF_mean_rho": float(Mcf.mean()),
             "cross_CF_range": [float(Mcf.min()), float(Mcf.max())],
             "PC1_explained": float(np.linalg.eigvalsh(R)[-1] / np.trace(R))}
    print(f"\n正交性: withinC={stats['within_C_mean_rho']:.3f} withinF="
          f"{stats['within_F_mean_rho']:.3f} cross={stats['cross_CF_mean_rho']:.3f} "
          f"PC1={stats['PC1_explained']:.3f}")

    out = {"sample": {"ARI": float(ari), "purity": float(pur), "n": int(Xc.shape[0])},
           "domain": {"ARI": float(arid), "purity": float(purd), "n": len(Xd)},
           "sample_cluster_assign": {ind[i]: int(lab2[i]) for i in range(len(ind))},
           "orthogonality": stats}
    with open(os.path.join(EX, "v21_p1_family_cluster.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\ndone v21")


if __name__ == "__main__":
    main()