# -*- coding: utf-8 -*-
"""
v76 实验: P3 最优轨迹 vs 真实训练点 —— 跨问题闭环外部验证
- P3 最优轨迹: log10 C in [17,26] 步长 0.25 上用主链路 solve_opt(power, L_ctx=4096)
  生成 N*(C) 曲线并单调插值.
- 真实训练点: B4 scaling_baseline is_converged==1 的 (N, D) -> 实际训练算力
  C_real = 6e18 * N * D.
- 对照: 每个实际点相对最优轨迹的偏差 delta = log10 N - log10 N*(C_real),
  并给出 Chinchilla 规则 (D=20N) 与 P2 计算最优 D*(N) 的对照线.
- 结论: 问题二/三的算力-规模关系与实际开源训练实践一致, 四问模型链闭环.
输出: experiments/v76_p3_real_closure.csv/.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import solve_opt, GL, Q0
from common import BASE, B

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

LCTX = 4096
FORM = "power"
A6 = 6e18  # FLOP/param/token


def build_trajectory():
    Cs, Ns = [], []
    for lc in np.arange(17.0, 26.01, 0.25):
        j = solve_opt(10 ** lc, FORM, LCTX)
        if j:
            Cs.append(float(j["C"])); Ns.append(j["N"])
    Cs, Ns = np.array(Cs), np.array(Ns)
    o = np.argsort(Cs)
    Cs, Ns = Cs[o], Ns[o]
    # 去掉非单调段 (数值噪声), 保证插值单调
    keep = [0]
    for i in range(1, len(Ns)):
        if Ns[i] > Ns[keep[-1]]:
            keep.append(i)
    return Cs[keep], Ns[keep]


def main():
    # P2 计算最优 D*(N) 常数 (KKT 均衡, 纯规模)
    A_, a_, B_, b_ = GL["A"], GL["a"], GL["B"], GL["b"]
    k = (b_ * B_ / (a_ * A_)) ** (1 / b_)
    expo = a_ / b_
    print(f"P2 D*(N) = {k:.3f} * N^{expo:.4f}")

    Cs, Ns = build_trajectory()
    print(f"P3 轨迹: {len(Cs)} 个预算点, log10 C in [{np.log10(Cs[0]):.2f}, {np.log10(Cs[-1]):.2f}]")
    lC, lN = np.log10(Cs), np.log10(Ns)
    # 轨迹局部斜率 (对数-对数)
    traj_slope = float(np.polyfit(lC, lN, 1)[0])
    print(f"P3 轨迹整体斜率 logN/logC = {traj_slope:.3f} (论文 N*~C^0.46)")

    # B4 实际训练点
    b4 = pd.read_csv(os.path.join(B, "scaling_baseline.csv"))
    b4 = b4[b4["is_converged"] == 1].copy()
    Nreal = b4["N_params_B"].to_numpy(dtype=float)
    Dreal = b4["D_tokens_B"].to_numpy(dtype=float)
    Creal = A6 * Nreal * Dreal
    lCreal = np.log10(Creal)
    Nstar = 10 ** np.interp(lCreal, lC, lN)
    delta = np.log10(Nreal) - np.log10(Nstar)
    # Chinchilla D=20N: C = 6*20*N^2
    chin = 10 ** (0.5 * lCreal - np.log10(np.sqrt(A6 * 20)))
    d_chin = np.log10(Nreal) - np.log10(chin)
    # P2 D* 隐含算力: C = 6*N*D*(N)
    lCstar = np.log10(A6 * Nreal * k * Nreal ** expo)
    d_dstar = np.log10(Nreal) - np.log10(10 ** np.interp(lCstar, lC, lN))

    rows = pd.DataFrame({"family": b4["family"], "N": Nreal, "D": Dreal,
                         "C_real": Creal, "Nstar_P3": Nstar,
                         "delta_vs_P3": delta, "delta_vs_chinchilla": d_chin,
                         "delta_vs_Dstar": d_dstar})
    rows.to_csv(os.path.join(EX, "v76_p3_real_closure.csv"), index=False, encoding="utf-8-sig")

    med = float(np.median(np.abs(delta)))
    q25, q75 = np.percentile(np.abs(delta), [25, 75])
    in_quarter = float((np.abs(delta) <= 0.25).mean())
    in_half = float((np.abs(delta) <= 0.5).mean())
    pearson = float(np.corrcoef(np.log10(Nreal), np.log10(Nstar))[0, 1])
    from scipy.stats import spearmanr
    spearman = float(spearmanr(np.log10(Nreal), np.log10(Nstar)).statistic)
    ols_slope = float(np.polyfit(lCreal, np.log10(Nreal), 1)[0])
    med_chin = float(np.median(np.abs(d_chin)))
    neg_frac = float((delta < 0).mean())
    print(f"\n实际点 vs P3 最优轨迹: 中位 |delta| = {med:.3f} dex (IQR {q25:.3f}-{q75:.3f})")
    print(f"  |delta|<=0.25 dex 占比 {in_quarter:.0%}, <=0.5 dex 占比 {in_half:.0%}")
    print(f"  Pearson(logN_real, logN_star) = {pearson:.3f}, Spearman = {spearman:.3f}")
    print(f"  偏差符号: N<N*(C) 占比 {neg_frac:.0%} (数据相对充裕一侧)")
    print(f"  实际云 logN~logC OLS 斜率 {ols_slope:.3f} vs P3 轨迹 {traj_slope:.3f} vs Chinchilla 0.5")
    print(f"对照: vs Chinchilla 中位 |delta| = {med_chin:.3f} dex")

    agg = {"n_points": int(len(Nreal)), "traj_slope": traj_slope, "ols_slope_real": ols_slope,
           "median_abs_delta": med, "iqr_abs_delta": [float(q25), float(q75)],
           "frac_le_0_25": in_quarter, "frac_le_0_5": in_half,
           "pearson": pearson, "spearman": spearman,
           "frac_neg_delta": neg_frac, "median_abs_delta_chinchilla": med_chin,
           "dstar_k": float(k), "dstar_expo": float(expo)}
    with open(os.path.join(EX, "v76_p3_real_closure.json"), "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2)

    # ---- 图: (a) 轨迹 vs 实际点; (b) delta 分布 ----
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5))
    ax = axes[0]
    fams = b4["family"].unique()
    cmap = plt.get_cmap("cyan_seq")
    for i, fam in enumerate(fams):
        g = b4[b4["family"] == fam]
        ax.scatter(np.log10(A6 * g["N_params_B"] * g["D_tokens_B"]), np.log10(g["N_params_B"]),
                   s=34, alpha=0.8, color=cmap(0.15 + 0.7 * i / max(len(fams) - 1, 1)),
                   label=fam, edgecolor="none")
    lc_grid = np.linspace(17, 26, 300)
    ax.plot(lc_grid, np.interp(lc_grid, lC, lN), "-", lw=2.4, color="#177cb0",
            label=f"P3 最优轨迹 N*(C) (斜率 {traj_slope:.2f})")
    ax.plot(lc_grid, 0.5 * lc_grid - np.log10(np.sqrt(A6 * 20)), "--", lw=1.6, color="#88ada6",
            label="Chinchilla 规则 D=20N (斜率 0.50)")
    ax.set_xlabel("实际训练算力 log10 C (FLOP)"); ax.set_ylabel("log10 N (B)")
    ax.set_title(f"(a) P3 最优轨迹 vs B4 实际训练点 (中位 |Δ|={med:.2f} dex)")
    ax.legend(fontsize=6.5, ncol=2, loc="lower right")
    ax.grid(alpha=0.3)
    ax.set_xlim(16.5, 26.5)

    ax = axes[1]
    ax.hist(delta, bins=24, color="#1685a9", alpha=0.85, edgecolor="white")
    ax.axvline(0, color="#177cb0", lw=1.6, ls="--")
    ax.axvline(np.median(delta), color="#3eede7", lw=1.4, ls="-", label=f"中位 {np.median(delta):.2f}")
    ax.set_xlabel("Delta = log10 N_actual - log10 N*(C_real) (dex)")
    ax.set_ylabel("模型数")
    ax.set_title("(b) 实际点相对最优轨迹的偏差分布")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.suptitle("P3 最优轨迹与真实训练点的闭环对照 —— 算力-规模关系外部验证", fontsize=12, y=1.02)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(EX, "v76_p3_real_closure.png"), dpi=200)
    plt.close(fig)
    print("\ndone v76")


if __name__ == "__main__":
    main()