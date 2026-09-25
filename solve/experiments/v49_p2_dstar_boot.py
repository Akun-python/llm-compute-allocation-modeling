# -*- coding: utf-8 -*-
"""
v49 实验: 最优数据量曲线 D*(N) 参数的 Bootstrap 区间
D*(N) = k * N^expo, expo = a/b, k = (b*B/(a*A))^(1/b)  (加法律解析解).
1) 对 B6+B7 (n=810) 做 case bootstrap 300 次, 每次拟合加法律得 a/b;
2) 报告 expo 与 k 的 2.5/50/97.5 分位 + D*(1B)/1B 比值区间;
3) 对照 Chinchilla 经验规则 D=20N (expo=1.0).
输出: experiments/v49_p2_dstar_boot.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from v3_p2_forms import load_b67, fit_form
from common import BASE

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

B = 300


def main():
    df = load_b67()
    N = df["N_params_B"].to_numpy(dtype=float)
    D = df["D_tokens_B"].to_numpy(dtype=float)
    Q = df["Q_score"].to_numpy(dtype=float)
    L = df["val_loss"].to_numpy(dtype=float)
    rng = np.random.default_rng(19)

    def slope_k(p):
        # 加法律参数: E, A, a, B, b, C, g
        E, A, a, B_, b, C, g = p
        expo = a / b
        k = (b * B_ / (a * A)) ** (1 / b)
        return expo, k

    p0 = fit_form(N, D, Q, L, "additive")[0]
    e0, k0 = slope_k(p0)
    es, ks = [], []
    for _ in range(B):
        idx = rng.integers(0, len(N), size=len(N))
        p = fit_form(N[idx], D[idx], Q[idx], L[idx], "additive")[0]
        e, k = slope_k(p)
        es.append(e); ks.append(k)
    es = np.array(es); ks = np.array(ks)
    q = lambda a: np.percentile(a, [2.5, 50, 97.5])
    print(f"expo a/b: 点估计 {e0:.4f} | CI [{q(es)[0]:.4f}, {q(es)[2]:.4f}] (中位 {q(es)[1]:.4f})")
    print(f"k: 点估计 {k0:.3f} | CI [{q(ks)[0]:.3f}, {q(ks)[2]:.3f}]")
    ratio = ks * 1.0 ** es
    print(f"D*(1B)/1B: 点估计 {k0:.2f}x | CI [{q(ratio)[0]:.2f}, {q(ratio)[2]:.2f}] (Chinchilla 规则 20x)")

    pd.DataFrame({"draw": range(B), "expo": es, "k": ks}).to_csv(
        os.path.join(EX, "v49_p2_dstar_boot.csv"), index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    ax = axes[0]
    ax.hist(es, bins=30, color="#177cb0", alpha=0.8)
    ax.axvline(e0, color="#3eede7", lw=2, label=f"点估计 {e0:.3f}")
    ax.axvline(1.0, color="#44cef6", lw=1.5, ls="--", label="Chinchilla expo=1.0")
    ax.set_xlabel("a/b"); ax.set_title(f"expo 的 Bootstrap ({B} 次)")
    ax.legend(fontsize=8)
    ax = axes[1]
    ax.hist(ratio, bins=30, color="#70f3ff", alpha=0.8)
    ax.axvline(k0, color="#3eede7", lw=2, label=f"D*(1B)/1B ≈ {k0:.1f}")
    ax.axvline(20, color="#44cef6", lw=1.5, ls="--", label="D=20N 规则")
    ax.set_xlabel("D*(1B)/1B"); ax.set_title("数据/参数比 (1B 处)")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v49_p2_dstar_boot.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v49_p2_dstar_boot.json"), "w", encoding="utf-8") as f:
        json.dump({"expo_point": float(e0), "expo_ci": q(es).tolist(),
                   "k_point": float(k0), "k_ci": q(ks).tolist(),
                   "ratio_point": float(k0), "ratio_ci": q(ratio).tolist()},
                  f, ensure_ascii=False, indent=2)
    print("\ndone v49")


if __name__ == "__main__":
    main()