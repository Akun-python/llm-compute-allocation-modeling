# -*- coding: utf-8 -*-
"""
v35 实验: 配比模型的留出验证与跨尺度迁移损失
对 1M 配比--损失数据 (512 行, 13 损失域) 做:
1) 逐损失域 5 折留出 CV (同尺度泛化能力, 严格检验非过拟合);
2) 全量训练后外推 test 1M/60M/1B 的跨尺度 R2 (迁移损失量化);
3) 对比: 同尺度留出 R2 vs 跨尺度 R2 的差距 = "迁移代价".
输出: experiments/v35_p1_mix_cv.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from sklearn.linear_model import Ridge
from p1_mixture import prepare, fit_eval, load_pair, RIDGE_ALPHA
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


def main():
    tr = load_pair("train_mixture_1m.csv", "train_pile_loss_1m.csv")
    Xtr = tr[mixture_cols("train_the_pile")].to_numpy(dtype=float)
    Ytr = tr[loss_cols()].to_numpy(dtype=float)
    rng = np.random.default_rng(11)
    K = 5
    idx = rng.permutation(len(Xtr))
    folds = np.array_split(idx, K)
    cv_r2 = np.zeros((len(loss_cols()), K))
    for k in range(K):
        te = np.concatenate([folds[j] for j in range(K) if j != k])
        tr_ = folds[k]
        for j, lc in enumerate(loss_cols()):
            r = Ridge(alpha=RIDGE_ALPHA).fit(Xtr[tr_], Ytr[tr_, j])
            yp = r.predict(Xtr[te])
            yt = Ytr[te, j]
            cv_r2[j, k] = 1 - np.sum((yt - yp) ** 2) / np.sum((yt - yt.mean()) ** 2)
    cv_mean = cv_r2.mean(axis=1)

    # 跨尺度外推 (全量 1M 训练)
    yhat_tr = np.column_stack([Ridge(alpha=RIDGE_ALPHA).fit(Xtr, Ytr[:, j]).predict(Xtr)
                               for j in range(len(loss_cols()))])
    ref = {"1M_train": (Xtr, Ytr)}
    for name in ["1M", "60M", "1B"]:
        te = load_pair(f"test_mixture_{name}.csv", f"test_pile_loss_{name}.csv")
        ref[name] = (te[mixture_cols("train_the_pile")].to_numpy(dtype=float),
                     te[loss_cols()].to_numpy(dtype=float))

    rows = []
    for j, lc in enumerate(loss_cols()):
        row = {"loss_domain": lc, "cv_r2": float(cv_mean[j])}
        for name, (X, Y) in ref.items():
            if name == "1M_train":
                yp = yhat_tr[:, j]
            else:
                yp = Ridge(alpha=RIDGE_ALPHA).fit(Xtr, Ytr[:, j]).predict(X)
                # 尺度基线校正 (主链路 scale_correct 口径): 平移训练/目标尺度均值差
                yp = yp + (Y[:, j].mean() - Ytr[:, j].mean())
            yt = Y[:, j]
            row[f"r2_{name}"] = float(1 - np.sum((yt - yp) ** 2) / np.sum((yt - yt.mean()) ** 2))
        # 同时记录未校正的跨尺度 R2 (诚实对照)
        for name in ["60M", "1B"]:
            X, Y = ref[name]
            yp = Ridge(alpha=RIDGE_ALPHA).fit(Xtr, Ytr[:, j]).predict(X)
            yt = Y[:, j]
            row[f"r2_{name}_raw"] = float(1 - np.sum((yt - yp) ** 2) / np.sum((yt - yt.mean()) ** 2))
        rows.append(row)
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v35_p1_mix_cv.csv"), index=False, encoding="utf-8-sig")
    print("CV R2 (同尺度留出) 均值: %.3f | 域范围: %.3f-%.3f" %
          (rdf["cv_r2"].mean(), rdf["cv_r2"].min(), rdf["cv_r2"].max()))
    for name in ["1M_train", "1M", "60M", "1B"]:
        print(f"R2_{name} 均值: {rdf['r2_' + name].mean():.3f}")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    means = [rdf["cv_r2"].mean(), rdf["r2_1M"].mean(), rdf["r2_60M"].mean(), rdf["r2_1B"].mean()]
    labs = ["同尺度留出 CV", "外推 1M", "外推 60M\n(基线校正)", "外推 1B\n(基线校正)"]
    bars = ax.bar(labs, means, color=["#177cb0", "#1685a9", "#70f3ff", "#3eede7"])
    for b, v in zip(bars, means):
        ax.text(b.get_x() + b.get_width() / 2, v + (0.08 if v >= 0 else -0.35),
                f"{v:.3f}", ha="center", fontsize=9)
    ax.axhline(0, color="#88ada6", lw=0.8)
    ax.set_ylim(-4.2, 1.05); ax.set_ylabel("平均 R²")
    ax.set_title("v35: 配比模型留出验证与跨尺度迁移 (13 损失域, 60M/1B 含基线校正)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v35_p1_mix_cv.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v35_p1_mix_cv.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v35")


if __name__ == "__main__":
    main()