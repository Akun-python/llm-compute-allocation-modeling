# -*- coding: utf-8 -*-
"""
问题一(1): 数据质量评价 + 质量冲突消解
数据: A1 抽样集(51230条, 27字段, 22指标), A2 arxiv 扩展(17523条), A3 github 扩展(203752条)
流程:
  1) 列表型指标压缩为标量(均值) ; 方向统一为"越高越好" (负向指标做补转换 1-x)
  2) 分位数裁剪(1%/99%) + Min-Max 归一化
  3) 组合赋权: 熵权法 + CRITIC 法 (客观), 输出权重与对比
  4) 质量分: 加权和 + TOPSIS 贴近度
  5) 冲突消解: 定义"冲突样本"与冲突指数; 相关性分组聚合(两阶段鲁棒合成); 抽样集/扩展集对照
输出: results/p1_quality_*.csv, figures/p1_*.png
"""
import json, lzma, os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import A, RES, FIG, BASE

# 中文字体
import matplotlib.font_manager as fm
for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)

# ---------------- 常量 ----------------
SCALAR_IND = ["dsir_books", "dsir_wiki", "dsir_math",
              "rps_doc_word_count", "rps_doc_num_sentences", "rps_doc_unigram_entropy",
              "rps_doc_frac_unique_words", "rps_doc_frac_no_alph_words",
              "rps_doc_frac_chars_top_2gram", "rps_doc_frac_chars_top_3gram",
              "rps_lines_uppercase_letter_fraction", "rps_lines_ending_with_terminal_punctution_mark",
              "rps_lines_numerical_chars_fraction", "rps_doc_mean_word_length"]
LIST_IND = ["fineweb_edu", "fluency_en", "modernbert_cleanliness", "modernbert_readability",
            "modernbert_reasoning", "modernbert_professionalism", "qurater", "ad_en"]
ALL_IND = SCALAR_IND + LIST_IND

# 方向: True=越高越好, False=越低越好(负向)
DIRECTION = {
    "fineweb_edu": True, "fluency_en": True,
    "modernbert_cleanliness": True, "modernbert_readability": True,
    "modernbert_reasoning": True, "modernbert_professionalism": True,
    "dsir_books": True, "dsir_wiki": True, "dsir_math": True,
    "qurater": True,
    "ad_en": False,                       # 广告含量: 越低越好
    "rps_doc_word_count": True, "rps_doc_num_sentences": True,
    "rps_doc_unigram_entropy": True, "rps_doc_frac_unique_words": True,
    "rps_doc_frac_no_alph_words": False,  # 无字母词占比: 越低越好
    "rps_doc_frac_chars_top_2gram": False, "rps_doc_frac_chars_top_3gram": False,  # 重复性: 越低越好
    "rps_lines_uppercase_letter_fraction": False,  # 全大写噪音: 越低越好
    "rps_lines_ending_with_terminal_punctution_mark": True,
    "rps_lines_numerical_chars_fraction": False,   # 数字占比过高=表格/乱码
    "rps_doc_mean_word_length": True,     # 词长适中偏长为佳(信息密度)
}
assert set(DIRECTION) == set(ALL_IND)

def load_jsonl_xz(path, limit=None):
    """流式读取 jsonl.xz"""
    recs = []
    with lzma.open(path, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            recs.append(json.loads(line))
    return recs

def compress_list(v):
    """列表型指标压缩为标量: 均值; 空列表->nan"""
    if isinstance(v, list) and len(v) > 0:
        arr = np.asarray(v, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size > 0:
            return float(np.mean(arr))
    return np.nan

def build_frame(recs, domain_hint=None):
    rows = []
    for r in recs:
        row = {}
        row["id"] = r.get("id")
        row["_source_domain"] = r.get("_source_domain", domain_hint)
        if "content" in r:
            row["content_len"] = len(r["content"])
        for k in SCALAR_IND:
            v = r.get(k)
            row[k] = v if isinstance(v, (int, float)) else np.nan
        for k in LIST_IND:
            row[k] = compress_list(r.get(k))
        rows.append(row)
    return pd.DataFrame(rows)

def winsorize_minmax(X, lo=0.01, hi=0.99):
    """分位数裁剪 + Min-Max 归一化, 返回 0-1 矩阵(越高越好)"""
    Xn = np.empty_like(X, dtype=float)
    for j in range(X.shape[1]):
        col = X[:, j]
        q_lo, q_hi = np.nanpercentile(col, [lo * 100, hi * 100])
        c = np.clip(col, q_lo, q_hi)
        span = q_hi - q_lo
        Xn[:, j] = (c - q_lo) / span if span > 1e-12 else 0.5
    return Xn

def entropy_weight(X):
    """熵权法: 输入已归一化(0-1, 非负)"""
    n, m = X.shape
    P = X / np.nansum(X, axis=0, keepdims=True)
    P = np.where(P > 0, P, 1e-12)
    e = -np.nansum(P * np.log(P), axis=0) / np.log(n)
    d = 1 - e
    w = d / d.sum()
    return w, e

def critic_weight(X):
    """CRITIC 赋权: 对比强度(标准差) x 冲突性(1-|r|)"""
    n, m = X.shape
    std = np.nanstd(X, axis=0, ddof=1)
    # 用 Spearman 秩相关减小异常值影响
    R = np.ones((m, m))
    cols = [X[:, j] for j in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            with np.errstate(invalid="ignore"):
                rho = spearmanr(cols[i], cols[j]).statistic
            R[i, j] = R[j, i] = rho if np.isfinite(rho) else 0.0
    conflict = np.sum(1 - np.abs(R), axis=1)
    C = std * conflict
    w = C / C.sum()
    return w, std, conflict

def topsis(X, w):
    """TOPSIS 贴近度(越高越好), 输入归一化矩阵与权重"""
    V = X * w
    ideal = np.max(V, axis=0)
    nadir = np.min(V, axis=0)
    d_pos = np.sqrt(np.nansum((V - ideal) ** 2, axis=1))
    d_neg = np.sqrt(np.nansum((V - nadir) ** 2, axis=1))
    return d_neg / (d_pos + d_neg)

# 质量指标分族: "内容质量族" C 与 "格式洁净族" F (方向统一后均越高越好)
FAMILY_C = ["fineweb_edu", "fluency_en", "modernbert_cleanliness", "modernbert_readability",
            "modernbert_reasoning", "modernbert_professionalism", "dsir_books", "dsir_wiki",
            "dsir_math", "qurater", "rps_doc_word_count", "rps_doc_num_sentences",
            "rps_doc_unigram_entropy", "rps_doc_frac_unique_words", "rps_doc_mean_word_length"]
FAMILY_F = ["ad_en", "rps_doc_frac_no_alph_words", "rps_doc_frac_chars_top_2gram",
            "rps_doc_frac_chars_top_3gram", "rps_lines_uppercase_letter_fraction",
            "rps_lines_numerical_chars_fraction", "rps_lines_ending_with_terminal_punctution_mark"]
assert set(FAMILY_C + FAMILY_F) == set(ALL_IND)

def family_scores(X):
    """两族分数: Q_C=内容质量族均值, Q_F=格式洁净族均值 (方向统一后均越高越好, 0-1)"""
    jc = [ALL_IND.index(k) for k in FAMILY_C]
    jf = [ALL_IND.index(k) for k in FAMILY_F]
    return X[:, jc].mean(axis=1), X[:, jf].mean(axis=1)


def conflict_index(X):
    """冲突指数 (样本级): |Q_C - Q_F| ∈ [0,1]
    Q_C=内容质量族均值, Q_F=格式洁净族均值.
    冲突高 = "内容好而格式脏" (如高教育价值+高广告) 或 "格式净而内容贫"."""
    qc, qf = family_scores(X)
    return np.abs(qc - qf), qc, qf


def robust_resolve(X, w, k=6):
    """冲突消解: 对称 trimmed 聚合 (每个样本剔除 k/2 个最低与 k/2 个最高分指标后加权)
    消解规则: 冲突样本中, 极端高/低分指标视为该样本"内部不一致"的来源,
    对称剔除后按剩余指标重归一化权重合成, 得到消解后的打分 Q*."""
    n, m = X.shape
    k = min(k, m - 2)
    k2 = k // 2
    Qr = np.empty(n)
    for i in range(n):
        x = X[i]
        order = np.argsort(x)
        keep = order[k2: m - k2]        # 对称去极值
        ww = w[keep]
        Qr[i] = np.nansum(x[keep] * ww) / ww.sum()
    return Qr

def main():
    # ---------- 1. 读取 ----------
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"))
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"))
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"))
    print(f"A1={len(a1)} A2={len(a2)} A3={len(a3)}")

    df1 = build_frame(a1)
    df2 = build_frame(a2, domain_hint="arxiv")
    df3 = build_frame(a3, domain_hint="github")
    df = pd.concat([df1, df2, df3], ignore_index=True)
    df["set"] = np.where(df.index < len(a1), "sample",
                         np.where(df.index < len(a1) + len(a2), "arxiv_ext", "github_ext"))
    print("total:", df.shape, "missing per indicator:")
    print(df[ALL_IND].isna().sum())

    # ---------- 2. 方向统一: 负向指标补转换 ----------
    Xraw = df[ALL_IND].to_numpy(dtype=float)
    for j, k in enumerate(ALL_IND):
        if not DIRECTION[k]:
            Xraw[:, j] = -Xraw[:, j]
    # 统一再归一化 (负向取反后 min-max)
    X = winsorize_minmax(Xraw)
    df_q = pd.DataFrame(X, columns=ALL_IND, index=df.index)
    df_q["domain"] = df["_source_domain"].values
    df_q["set"] = df["set"].values
    df_q["id"] = df["id"].values

    # ---------- 3. 组合赋权 ----------
    w_ent, e_ent = entropy_weight(X)
    w_cri, std_c, conf_c = critic_weight(X)
    w_combo = 0.5 * w_ent + 0.5 * w_cri
    wdf = pd.DataFrame({"indicator": ALL_IND, "direction": [DIRECTION[k] for k in ALL_IND],
                        "entropy_w": w_ent, "critic_w": w_cri, "combo_w": w_combo})
    wdf.to_csv(os.path.join(RES, "p1_quality_weights.csv"), index=False, encoding="utf-8-sig")

    # ---------- 4. 质量分: 加权和 + TOPSIS ----------
    Q_weighted = np.nansum(X * w_combo, axis=1)
    Q_topsis = topsis(X, w_combo)
    df_q["Q_weighted"] = Q_weighted
    df_q["Q_topsis"] = Q_topsis

    # ---------- 5. 冲突指数 与 冲突消解 ----------
    ci, qc, qf = conflict_index(X)
    df_q["conflict"] = ci
    df_q["Q_content"] = qc
    df_q["Q_format"] = qf
    # 消解后质量分 Q*: trimmed 聚合
    df_q["Q_resolved"] = robust_resolve(X, w_combo, k=6)
    # 冲突成因: 冲突与内容长度、域的关系
    if "content_len" in df.columns:
        clen = df["content_len"].to_numpy()
        mask = np.isfinite(clen) & np.isfinite(ci)
        rho, p = spearmanr(clen[mask], ci[mask])
        print(f"conflict vs content_len: rho={rho:.3f} p={p:.2e}")
        df_q["content_len"] = clen

    # 域级聚合 (加权均值, 权重=样本冲突倒数: 冲突越高越不可信)
    def wmean(vals, w):
        m = np.isfinite(vals) & np.isfinite(w)
        if m.sum() == 0:
            return np.nan
        return np.average(vals[m], weights=w[m])

    agg = []
    for dom, g in df_q.groupby("domain"):
        wgt = 1.0 / (g["conflict"] + 0.05)
        agg.append({
            "domain": dom, "n": len(g),
            "Q_weighted": wmean(g["Q_weighted"].to_numpy(), wgt.to_numpy()),
            "Q_resolved": wmean(g["Q_resolved"].to_numpy(), wgt.to_numpy()),
            "Q_topsis": wmean(g["Q_topsis"].to_numpy(), wgt.to_numpy()),
            "Q_weighted_plain": np.nanmean(g["Q_weighted"].to_numpy()),
            "conflict_mean": np.nanmean(g["conflict"].to_numpy()),
        })
    dom_q = pd.DataFrame(agg).sort_values("Q_weighted", ascending=False)
    dom_q.to_csv(os.path.join(RES, "p1_domain_quality.csv"), index=False, encoding="utf-8-sig")
    print("\n域级质量分:")
    print(dom_q.to_string())

    # 抽样集 vs 全量对照 (域级)
    sub = df_q[df_q["set"] == "sample"]
    full = df_q
    def dom_agg(d):
        return d.groupby("domain").apply(
            lambda g: wmean(g["Q_weighted"].to_numpy(),
                             (1.0 / (g["conflict"].to_numpy() + 0.05))),
            include_groups=False).to_dict()
    comp = pd.DataFrame({"sample_only": pd.Series(dom_agg(sub)), "all_records": pd.Series(dom_agg(full))})
    comp = comp.reindex(sorted(comp.index))
    comp.to_csv(os.path.join(RES, "p1_sample_vs_full_Q.csv"), encoding="utf-8-sig")
    print("\n抽样集/全量对照:\n", comp.to_string())

    # 冲突消解效果: 高冲突样本 Q_resolved 与 Q_weighted 对比
    ci_arr = df_q["conflict"].to_numpy()
    ci_arr = ci_arr[np.isfinite(ci_arr)]
    thresh = np.percentile(ci_arr, 90)
    high_conf = df_q[df_q["conflict"] >= thresh]
    print(f"\n高冲突样本数: {len(high_conf)} (阈值 P90={thresh:.4f}), "
          f"原始Q均值={high_conf['Q_weighted'].mean():.4f}, "
          f"消解后Q均值={high_conf['Q_resolved'].mean():.4f}")

    # ---------- 6. 冲突分析 ----------
    print("\n冲突指数描述统计:")
    print(df_q["conflict"].describe())
    dom_conf = df_q.groupby("domain")["conflict"].agg(["mean", "median", "max", "count"])
    dom_conf.to_csv(os.path.join(RES, "p1_conflict_by_domain.csv"), encoding="utf-8-sig")
    print(dom_conf.to_string())

    # 冲突样本示例: 冲突最高的样本
    top_conf = df_q.nlargest(5, "conflict")
    print("\nTop-5 冲突样本指标值(部分):")
    print(top_conf[["domain", "Q_content", "Q_format", "conflict"] + ALL_IND[:6]].to_string())

    # 扩展集 vs 抽样集 冲突结论对照 (arxiv / github)
    set_comp = {}
    for sname in ["sample", "arxiv_ext", "github_ext"]:
        g = df_q[df_q["set"] == sname]
        set_comp[sname] = {"n": len(g), "conflict_mean": g["conflict"].mean(),
                           "conflict_p90": g["conflict"].quantile(0.9),
                           "Q_mean": g["Q_weighted"].mean()}
    set_comp_df = pd.DataFrame(set_comp).T
    set_comp_df.to_csv(os.path.join(RES, "p1_conflict_by_set.csv"), encoding="utf-8-sig")
    print("\n按数据集(抽样/扩展)的冲突统计:")
    print(set_comp_df.to_string())

    df_q.to_csv(os.path.join(RES, "p1_quality_all.csv"), index=False, encoding="utf-8-sig")

    # ---------- 7. 图 ----------
    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    # 权重对比条形图
    fig, ax = plt.subplots(figsize=(11, 5))
    idx = np.arange(len(ALL_IND))
    w = 0.28
    ax.bar(idx - w, w_ent, w, label="熵权法", color="#2563EB")
    ax.bar(idx, w_cri, w, label="CRITIC", color="#0EA5E9")
    ax.bar(idx + w, w_combo, w, label="组合权重", color="#10B981")
    ax.set_xticks(idx); ax.set_xticklabels(ALL_IND, rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("权重"); ax.legend(); ax.set_title("22 项质量指标的三种权重对比 (R2 表示判定系数)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_weights.png"), dpi=200); plt.close(fig)

    # 域级质量分布
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(dom_q["domain"], dom_q["Q_weighted"], color="#2563EB", alpha=0.85)
    for b, v in zip(bars, dom_q["Q_weighted"]):
        ax.text(b.get_x() + b.get_width()/2, v + 0.002, f"{v:.3f}", ha="center", fontsize=8)
    ax.set_ylabel("域级质量分 Q (加权)")
    ax.set_title("7 个质量域的域级质量评分 Q")
    ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_domain_q.png"), dpi=200); plt.close(fig)

    # 冲突指数直方图 (去掉 NaN 行)
    ci_valid = df_q["conflict"].dropna()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(ci_valid, bins=60, color="#F59E0B", alpha=0.85, edgecolor="white")
    ax.axvline(np.nanpercentile(ci_valid, 90), color="red", ls="--", label="P90 分位")
    ax.set_xlabel("冲突指数 |Q_C − Q_F|"); ax.set_ylabel("频数"); ax.legend()
    ax.set_title("样本级质量冲突指数分布")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_conflict_hist.png"), dpi=200); plt.close(fig)

    # Q_C vs Q_F 散点 (冲突可视化)
    fig, ax = plt.subplots(figsize=(7, 6))
    s = ax.scatter(df_q["Q_content"], df_q["Q_format"], c=df_q["conflict"],
                   s=4, alpha=0.35, cmap="YlOrRd")
    cb = fig.colorbar(s, ax=ax)
    cb.set_label("冲突指数")
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("内容质量族 Q_C"); ax.set_ylabel("格式洁净族 Q_F")
    ax.set_title("内容质量 vs 格式洁净: 冲突可视化")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_conflict_scatter.png"), dpi=200); plt.close(fig)

    # 域内冲突箱线图
    fig, ax = plt.subplots(figsize=(9, 4.5))
    order = dom_q["domain"].tolist()
    data = [df_q[df_q["domain"] == d]["conflict"].values for d in order]
    ax.boxplot(data, labels=order, showfliers=False)
    ax.set_ylabel("冲突指数"); ax.set_xlabel("质量域")
    ax.set_title("各质量域内部冲突指数分布")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_conflict_box.png"), dpi=200); plt.close(fig)

    # 冲突消解效果: Q_weighted vs Q_resolved 散点(按冲突着色)
    fig, ax = plt.subplots(figsize=(7, 6))
    s = ax.scatter(df_q["Q_weighted"], df_q["Q_resolved"], c=df_q["conflict"],
                   s=5, alpha=0.4, cmap="YlOrRd")
    cb = fig.colorbar(s, ax=ax); cb.set_label("冲突指数")
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("原始组合质量分 Q"); ax.set_ylabel("冲突消解后质量分 Q*")
    ax.set_title("冲突消解前后质量分对比")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p1_resolve_scatter.png"), dpi=200); plt.close(fig)

    print("done p1_quality")

if __name__ == "__main__":
    main()
