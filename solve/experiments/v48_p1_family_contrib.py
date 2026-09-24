# -*- coding: utf-8 -*-
"""
v48 实验: book 领先的指标族贡献分解
用加权标准化值 V_ij = w_j * X_ij 的域均值差做可加分解:
  Delta_j = w_j*(mean_j(book) - mean_j(all)), 总和 = book 的加权分优势.
1) 按指标族聚合 (内容主题 / 结构格式 / 语义模型分) 得到贡献;
2) 逐指标贡献 Top5 (哪些信号把 book 推到第 1);
3) 对照低质域 (commoncrawl) 的负贡献结构.
输出: experiments/v48_p1_family_contrib.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p1_quality import (load_jsonl_xz, build_frame, winsorize_minmax,
                        entropy_weight, critic_weight, ALL_IND)
from common import A, BASE

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

FAMILY = {
    "内容/主题": ["dsir_books", "dsir_wiki", "dsir_math", "fineweb_edu", "fluency_en",
                 "qurater", "modernbert_reasoning"],
    "结构/格式": ["rps_doc_word_count", "rps_doc_num_sentences", "rps_doc_unigram_entropy",
                 "rps_doc_frac_unique_words", "rps_doc_frac_no_alph_words",
                 "rps_doc_frac_chars_top_2gram", "rps_doc_frac_chars_top_3gram",
                 "rps_lines_uppercase_letter_fraction", "rps_lines_ending_with_terminal_punctution_mark",
                 "rps_lines_numerical_chars_fraction", "rps_doc_mean_word_length",
                 "modernbert_cleanliness"],
    "语义模型分": ["modernbert_readability", "modernbert_professionalism", "ad_en"],
}


def main():
    a1 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_signal_sample.jsonl.xz"), limit=60000)
    a2 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "arxiv_part-6777d8857c6e-000486.jsonl.xz"), limit=15000)
    a3 = load_jsonl_xz(os.path.join(A, "slimpajama_quality_extended", "github_part-6777d8857c6e-000275.jsonl.xz"), limit=15000)
    df = pd.concat([build_frame(a1), build_frame(a2, domain_hint="arxiv"),
                    build_frame(a3, domain_hint="github")], ignore_index=True)
    dom = df["_source_domain"].fillna("none").to_numpy()
    X = winsorize_minmax(df[ALL_IND].to_numpy(dtype=float).copy())
    X = np.where(np.isnan(X), np.nanmean(X, axis=0), X)
    we, _ = entropy_weight(X)
    wc = critic_weight(X)[0]
    w = 0.5 * np.asarray(we, float) + 0.5 * np.asarray(wc, float)
    V = X * w  # 加权标准化值
    allmean = V.mean(axis=0)

    def contrib(dom_name):
        m = V[dom == dom_name].mean(axis=0)
        return m - allmean

    book_d = contrib("book")
    cc_d = contrib("commoncrawl")
    arx_d = contrib("arxiv")

    rows = [{"indicator": ind, "family": next((f for f, inds in FAMILY.items() if ind in inds), "其他"),
             "book_delta": float(book_d[i]), "cc_delta": float(cc_d[i]), "arxiv_delta": float(arx_d[i])}
            for i, ind in enumerate(ALL_IND)]
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v48_p1_family_contrib.csv"), index=False, encoding="utf-8-sig")

    print("book 加权分相对全域优势 = %.4f (总和)" % book_d.sum())
    fam = rdf.groupby("family")["book_delta"].sum().sort_values(ascending=False)
    print(fam.to_string())
    print("\nbook 贡献 Top5 指标:")
    print(rdf.sort_values("book_delta", ascending=False).head(5)[["indicator", "book_delta"]].to_string(index=False))
    print("\ncommoncrawl 负贡献 Top3:")
    print(rdf.sort_values("cc_delta").head(3)[["indicator", "cc_delta"]].to_string(index=False))

    fig, ax = plt.subplots(figsize=(9, 5))
    fams = list(fam.index)
    pos = np.arange(len(fams))
    ax.barh(pos, fam.values, color="#2563EB", alpha=0.85)
    ax.axvline(0, color="#94A3B8", lw=0.8)
    ax.set_yticks(pos); ax.set_yticklabels(fams)
    ax.set_xlabel("book 相对全域的加权分贡献")
    ax.set_title(f"v48: book 领先的指标族贡献分解 (总优势 {book_d.sum():.4f})")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v48_p1_family_contrib.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v48_p1_family_contrib.json"), "w", encoding="utf-8") as f:
        json.dump({"book_total": float(book_d.sum()), "family_contrib": fam.to_dict(),
                   "top5": rdf.sort_values("book_delta", ascending=False).head(5)[["indicator", "book_delta"]].to_dict("records"),
                   "rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v48")


if __name__ == "__main__":
    main()