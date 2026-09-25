# -*- coding: utf-8 -*-
"""
v19 实验: 配比 -> 损失域 迁移结构热图 (1M 尺度 Ridge 系数解读)
对 p1_mixture 的 13 源域 x 17 损失域系数矩阵做解释性分析:
1) 自域对齐: 源域 i 对损失域 i 的系数是否显著为负 (更多自己 -> 该域损失更低)?
2) 跨域迁移: 最强负迁移对 (哪一源域份额最能压低哪一损失域).
3) 小说域(book) 的跨域价值: gutenberg 系数分布.
4) 域聚合后的热图 + 每损失域的平均效果.
输出: experiments/v19_p1_transfer.png/.csv/.json
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import RES, BASE

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

ALIAS = {"wikipedia_en": "wikipedia", "gutenberg_pg_19": "book",
         "dm_mathematics": "arxiv", "pile_cc": "c4"}


def clean(s):
    s = s.replace("the_pile_", "").replace("_val_loss", "")
    return ALIAS.get(s, s)


def main():
    c = pd.read_csv(os.path.join(RES, "p1_mixture_coefs.csv"))
    raw_src = [x for x in c.columns[1:-2]]
    src_doms = [clean(x) for x in raw_src]
    loss_doms = [clean(x) for x in c["Unnamed: 0"].tolist()]
    M = c[raw_src].to_numpy(dtype=float)
    print("矩阵:", M.shape, "源域:", src_doms, "损失域:", loss_doms)

    # 自域对齐需用 raw 名匹配 (loss 行 raw 名)
    raw_loss = c["Unnamed: 0"].tolist()
    diag = []
    for i, ld_raw in enumerate(raw_loss):
        lc = clean(ld_raw)
        for j, sr in enumerate(raw_src):
            if lc == clean(sr):
                diag.append((lc, M[i, j]))
                break
    ddf = pd.DataFrame(diag, columns=["domain", "self_coef"])
    neg_frac = (ddf["self_coef"] < 0).mean()
    print("\n自域对齐系数 (负=自域越多该域损失越低):")
    print(ddf.round(3).to_string(index=False))
    print(f"自域系数为负的比例: {neg_frac*100:.0f}%")

    # 2) 最强负迁移对
    pairs = []
    for i, ld in enumerate(loss_doms):
        for j, sd in enumerate(src_doms):
            pairs.append((sd, ld, M[i, j]))
    pf = pd.DataFrame(pairs, columns=["source", "loss_domain", "coef"])
    top_neg = pf.nsmallest(8, "coef")
    print("\n最强负迁移对 (源域份额↑ -> 损失↓):")
    print(top_neg.round(3).to_string(index=False))

    # 3) book 域跨域价值
    book_col = src_doms.index("book") if "book" in src_doms else None
    if book_col is not None:
        bc = M[:, book_col]
        print("\nbook 域系数: mean=%.3f min=%.3f max=%.3f, 负(帮助)域数=%d/%d"
              % (bc.mean(), bc.min(), bc.max(), (bc < 0).sum(), len(bc)))

    # 4) 每损失域平均效果 (mean_effect 列)
    me = c["mean_effect"].to_numpy()
    print("\n每损失域 mean_effect 前3 (绝对值最大):")
    for i in np.argsort(-np.abs(me))[:3]:
        print(f"  {loss_doms[i]}: {me[i]:.3f}")

    # 热图
    fig, ax = plt.subplots(figsize=(10, 6.5))
    im = ax.imshow(M, cmap="cyan_div", vmin=-np.percentile(np.abs(M), 95), vmax=np.percentile(np.abs(M), 95), aspect="auto")
    ax.set_xticks(np.arange(len(src_doms))); ax.set_xticklabels(src_doms, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(np.arange(len(loss_doms))); ax.set_yticklabels(loss_doms, fontsize=9)
    ax.set_xlabel("混合源域 (配比系数)"); ax.set_ylabel("下游损失域")
    ax.set_title("v19: 配比-损失域 迁移系数热图 (1M)")
    fig.colorbar(im, ax=ax, label="Ridge 系数 (负=降低损失)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v19_p1_transfer.png"), dpi=200); plt.close(fig)

    out = {"self_alignment": ddf.to_dict("records"), "self_neg_frac": float(neg_frac),
           "top_neg_pairs": top_neg.to_dict("records"),
           "book_col_stats": None if book_col is None else
           {"mean": float(bc.mean()), "min": float(bc.min()), "max": float(bc.max()),
            "n_help": int((bc < 0).sum())}}
    with open(os.path.join(EX, "v19_p1_transfer.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\ndone v19")


if __name__ == "__main__":
    main()