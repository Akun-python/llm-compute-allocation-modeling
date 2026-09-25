# -*- coding: utf-8 -*-
"""
v10 实验: 问题一质量评分指标消融 (指标族敏感性)
对 22 个质量指标做留一/留族消融, 重算组合赋权+TOPSIS 的域级质量排序:
  - 留一单个指标 (22 次)
  - 留整个"内容质量族" / "格式洁净族"
  - 留 modernbert_* / rps_* / dsir_* 分组
度量: 域排序 Spearman vs 基线, Q 相关, 冲突指数均值漂移, 消解效果变化
结论: 排序是否由某单一指标/指标族决定? 冲突与消解是否稳健?
输出: experiments/v10_p1_ablation.csv + 图
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
import p1_quality as P
from common import A, RES, FIG, BASE
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
plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"
import plotstyle


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
    dom = df["_source_domain"].to_numpy()
    return X, dom


def fast_critic_weight(X):
    """快速 CRITIC: Spearman 相关 = 秩的 Pearson 相关 (向量化 np.corrcoef)"""
    n, m = X.shape
    Rk = np.apply_along_axis(lambda v: pd.Series(v).rank(method="first").to_numpy(), 0, X)
    Rk = Rk / (n - 1) * 2 - 1
    Cmat = np.corrcoef(Rk, rowvar=False)
    Cmat = np.nan_to_num(Cmat)
    std = np.nanstd(X, axis=0, ddof=1)
    conflict = np.sum(1 - np.abs(Cmat), axis=1)
    C = std * conflict
    w = C / C.sum()
    return w


def domain_rank(X, dom):
    w_ent, _ = P.entropy_weight(X)
    w_cri = fast_critic_weight(X)
    w = 0.5 * w_ent + 0.5 * w_cri
    Q = P.topsis(X, w)
    dq = pd.DataFrame({"Q": Q, "domain": dom})
    grp = dq.groupby("domain")["Q"].mean().sort_values(ascending=False)
    return grp, w


def main():
    X, dom = load_data()
    n = len(X)
    print("data:", X.shape)

    # 基线
    grp0, w0 = domain_rank(X, dom)
    doms = grp0.index.tolist()
    print("基线域排序:", dict(zip(doms, np.round(grp0.values, 3))))
    ci0, qc0, qf0 = P.conflict_index(X)
    Qr0 = P.robust_resolve(X, w0, k=6)
    hi0 = ci0 > np.quantile(ci0[~np.isnan(ci0)], 0.9)
    resolv0 = float(np.nanmean(Qr0[hi0]) - np.nanmean(Qr0[~hi0]))

    rows = []
    groups = {"content_family": P.FAMILY_C, "format_family": P.FAMILY_F,
              "modernbert": [k for k in P.ALL_IND if k.startswith("modernbert")],
              "rps_doc": [k for k in P.ALL_IND if k.startswith("rps_doc")],
              "dsir": [k for k in P.ALL_IND if k.startswith("dsir")],
              "fineweb+fluency": ["fineweb_edu", "fluency_en"],
              "ad_en": ["ad_en"]}
    keep_set = {name: sorted(set(P.ALL_IND) - set(ks)) for name, ks in groups.items()}

    for name, keep in keep_set.items():
        jj = [P.ALL_IND.index(k) for k in keep]
        Xa = X[:, jj]
        grp, wa = domain_rank(Xa, dom)
        rk0 = pd.Series(np.arange(len(grp)), index=grp.index)
        rk_base = pd.Series(np.arange(len(grp0)), index=grp0.index)
        rho = rk0.reindex(doms).corr(rk_base.reindex(doms), method="spearman")
        # Q 相关 (对齐域均值)
        q0a = grp0.reindex(doms).to_numpy()
        q1a = grp.reindex(doms).to_numpy()
        qcorr = float(np.corrcoef(q0a, q1a)[0, 1])
        # 两族冲突: 在缩减列集上按族名重索引
        jc = [jj.index(P.ALL_IND.index(k)) for k in P.FAMILY_C if k in keep]
        jf = [jj.index(P.ALL_IND.index(k)) for k in P.FAMILY_F if k in keep]
        if jc and jf:
            qc = Xa[:, jc].mean(axis=1)
            qf = Xa[:, jf].mean(axis=1)
            ci = np.abs(qc - qf)
            Qr = P.robust_resolve(Xa, wa, k=6)
            hi = ci > np.nanquantile(ci, 0.9)
            resolv = float(np.nanmean(Qr[hi]) - np.nanmean(Qr[~hi]))
            cm = float(np.nanmean(ci))
        else:
            ci = np.full(len(X), np.nan)
            resolv, cm = np.nan, np.nan
        rows.append({"ablation": name, "n_ind": len(keep), "removed": len(P.ALL_IND) - len(keep),
                     "domain_rank_spearman": float(rho), "domain_Q_corr": qcorr,
                     "conflict_mean": cm, "resolution_gain": resolv,
                     "top_domain": grp.index[0]})
        print(f"[{name}] 保留{len(keep)}指标: 排序rho={rho:.3f} Q相关={qcorr:.3f} "
              f"冲突均值={cm:.3f} 消解增益={resolv:.3f} top={grp.index[0]}")

    # 留一单指标
    for k in P.ALL_IND:
        keep = [x for x in P.ALL_IND if x != k]
        jj = [P.ALL_IND.index(x) for x in keep]
        grp, wa = domain_rank(X[:, jj], dom)
        rk0 = pd.Series(np.arange(len(grp0)), index=grp0.index)
        rk1 = pd.Series(np.arange(len(grp)), index=grp.index)
        rho = rk0.reindex(doms).corr(rk1.reindex(doms), method="spearman")
        rows.append({"ablation": "leave1_" + k, "n_ind": len(keep), "removed": 1,
                     "domain_rank_spearman": float(rho), "domain_Q_corr": np.nan,
                     "conflict_mean": np.nan, "resolution_gain": np.nan, "top_domain": grp.index[0]})

    abl = pd.DataFrame(rows)
    abl.to_csv(os.path.join(EX, "v10_p1_ablation.csv"), index=False, encoding="utf-8-sig")
    lo = abl[abl["ablation"].str.startswith("leave1")]
    print("\n留一单指标: 排序rho 最小 =", lo["domain_rank_spearman"].min().round(4),
          "于", lo.loc[lo["domain_rank_spearman"].idxmin(), "ablation"])
    print("留一单指标: rho 中位数 =", lo["domain_rank_spearman"].median().round(4))

    # 图: 留族消融的排序相关性
    fig, ax = plt.subplots(figsize=(9, 4.5))
    gl = abl[~abl["ablation"].str.startswith("leave1")]
    gl = gl.sort_values("domain_rank_spearman")
    ax.barh(gl["ablation"], gl["domain_rank_spearman"], color="#177cb0")
    ax.axvline(1.0, color="#44cef6", ls="--", lw=1)
    ax.set_xlabel("域排序 Spearman (vs 基线)"); ax.set_xlim(0.6, 1.02)
    ax.set_title("v10: 指标族消融对域质量排序的影响")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v10_p1_ablation.png"), dpi=200); plt.close(fig)

    print("\ndone v10")


if __name__ == "__main__":
    main()
