# -*- coding: utf-8 -*-
"""
问题二: 跨维度数据融合与广义标度律
思路:
  1) 经典标度律 L(N,D)=E+A N^{-a}+B D^{-b} 以 B1(Pythia 全轨迹) 拟合;
     跨族验证 (B2/B4/B5) 时允许"族级截距偏移" (不同词表/分词器的不可约损失不同),
     报告 原始R2 与 去偏移R2 两种口径;
  2) 质量扩展: B6+B7 (域内) 拟合含 Q 的广义标度律, 两种形式对比:
     (a) additive:  L = E + A N^{-a} + B D^{-b} + C (1-Q)^g      (Q=1 退化经典)
     (b) interaction: L = E + A N^{-a} + B D^{-b} + C (1-Q)^g * D^{-d}
     用 B8 (含外推) 做外推验证;
  3) 弹性分析: eps_N, eps_D, eps_Q; 质量-规模等价条件 dN/dQ;
  4) 领域配比引入: 讨论 Q 的领域加权平均进入广义标度律的方式;
输出: results/p2_*.csv/json, figures/p2_*.png
"""
import os, json
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from common import B, RES, FIG, BASE

for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def fit_classical(N, D, L, p0=None):
    def resid(p):
        E, A, a, B, b = p
        return E + A * N ** (-a) + B * D ** (-b) - L
    if p0 is None:
        p0 = np.array([L.min() * 0.7, 3.0, 0.3, 3.0, 0.3])
    lb = np.array([0.0, 1e-6, 1e-4, 1e-6, 1e-4])
    ub = np.array([L.min() * 1.2, 1e3, 5.0, 1e3, 5.0])
    return least_squares(resid, p0, bounds=(lb, ub), max_nfev=40000)


def predict_classical(p, N, D):
    E, A, a, B, b = p
    return E + A * N ** (-a) + B * D ** (-b)


def fit_generalized(N, D, Q, L, form="additive", p0=None):
    """additive:  L = E + A N^{-a} + B D^{-b} + C (1-Q)^g
    interaction:  L = E + A N^{-a} + B D^{-b} + C (1-Q)^g * D^{-d} (质量收益随数据量衰减)
    interaction_N: L = E + A N^{-a} + B D^{-b} + C (1-Q)^g * N^{-h} (质量缺口随参数量衰减)"""
    def resid_add(p):
        E, A, a, B, b, C, g = p
        return E + A * N ** (-a) + B * D ** (-b) + C * np.maximum(1 - Q, 0) ** g - L

    def resid_int(p):
        E, A, a, B, b, C, g, d = p
        return (E + A * N ** (-a) + B * D ** (-b)
                + C * np.maximum(1 - Q, 0) ** g * D ** (-d) - L)

    def resid_intN(p):
        E, A, a, B, b, C, g, h = p
        return (E + A * N ** (-a) + B * D ** (-b)
                + C * np.maximum(1 - Q, 0) ** g * N ** (-h) - L)

    if form == "additive":
        resid, npar = resid_add, 7
    elif form == "interaction":
        resid, npar = resid_int, 8
    else:
        resid, npar = resid_intN, 8
    if p0 is None:
        p0 = np.array([L.min() * 0.7, 3.0, 0.3, 3.0, 0.3, 1.0, 1.5] + ([0.3] if npar == 8 else []))
    lb = np.array([0.0, 1e-6, 1e-4, 1e-6, 1e-4, 1e-6, 1e-4] + ([1e-4] if npar == 8 else []))
    ub = np.array([L.min() * 1.2, 1e3, 5.0, 1e3, 5.0, 1e3, 10.0] + ([5.0] if npar == 8 else []))
    return least_squares(resid, p0, bounds=(lb, ub), max_nfev=60000)


def predict_generalized(p, N, D, Q, form="additive"):
    if form == "additive":
        E, A, a, B, b, C, g = p
        return E + A * N ** (-a) + B * D ** (-b) + C * np.maximum(1 - Q, 0) ** g
    if form == "interaction":
        E, A, a, B, b, C, g, d = p
        return (E + A * N ** (-a) + B * D ** (-b)
                + C * np.maximum(1 - Q, 0) ** g * D ** (-d))
    E, A, a, B, b, C, g, h = p
    return (E + A * N ** (-a) + B * D ** (-b)
            + C * np.maximum(1 - Q, 0) ** g * N ** (-h))


def r2_metric(y, yhat):
    denom = np.sum((y - y.mean()) ** 2)
    return 1 - np.sum((y - yhat) ** 2) / denom if denom > 1e-12 else 0.0


def r2_offset(y, yhat):
    """去族级偏移 R2: 允许预测整体平移 (不同模型族不可约损失不同)"""
    off = np.mean(y - yhat)
    return r2_metric(y, yhat + off)


def main():
    res = {}

    # ===== 1. 经典标度律: B1 拟合 =====
    pythia = pd.read_csv(os.path.join(B, "pythia_training_log_existing.csv"))
    pythia = pythia[pythia["val_loss"].notna()]
    N, D, L = (pythia[k].to_numpy() for k in ["N_params_B", "D_tokens_B", "val_loss"])
    sol_c = fit_classical(N, D, L)
    p_c = sol_c.x
    Lhat_c = predict_classical(p_c, N, D)
    r2_c = r2_metric(L, Lhat_c)
    print("经典标度律参数:", dict(zip(["E", "A", "a", "B", "b"], p_c)), "R2=", round(r2_c, 6))
    res["classical"] = {"params": {k: float(v) for k, v in zip(["E", "A", "a", "B", "b"], p_c)},
                        "r2_pythia": r2_c, "n": len(N)}

    # 各模型轨迹内 R2
    per_model = []
    for gid, g in pythia.groupby("run_id"):
        lh = predict_classical(p_c, g["N_params_B"].to_numpy(), g["D_tokens_B"].to_numpy())
        per_model.append({"run_id": gid, "N": g["N_params_B"].iloc[0],
                          "r2": r2_metric(g["val_loss"].to_numpy(), lh)})
    res["classical"]["per_model"] = per_model

    # ===== 2. 族外验证: B2 Cerebras (半合成) =====
    cer = pd.read_csv(os.path.join(B, "cerebras_training_log.csv"))
    N2, D2, L2 = cer["N_params_B"].to_numpy(), cer["D_tokens_B"].to_numpy(), cer["val_loss"].to_numpy()
    L2h = predict_classical(p_c, N2, D2)
    r2_cer_raw = r2_metric(L2, L2h)
    r2_cer_off = r2_offset(L2, L2h)
    print(f"Cerebras 族外: 原始R2={r2_cer_raw:.4f}, 去偏移R2={r2_cer_off:.4f}")
    res["validation"] = {"cerebras_r2_raw": r2_cer_raw, "cerebras_r2_offset": r2_cer_off}

    # ===== 3. 跨族验证: B4 =====
    bl = pd.read_csv(os.path.join(B, "scaling_baseline.csv"))
    bl = bl[bl["val_loss"].notna()]
    N4, D4, L4 = bl["N_params_B"].to_numpy(), bl["D_tokens_B"].to_numpy(), bl["val_loss"].to_numpy()
    L4h = predict_classical(p_c, N4, D4)
    res["validation"]["baseline_r2_raw"] = r2_metric(L4, L4h)
    res["validation"]["baseline_r2_offset"] = r2_offset(L4, L4h)
    print(f"跨族收敛点: 原始R2={res['validation']['baseline_r2_raw']:.4f}, 去偏移R2={res['validation']['baseline_r2_offset']:.4f}")

    # ===== 4. 文献验证: B5 =====
    pub = pd.read_csv(os.path.join(B, "published_scaling_data.csv"))
    pub = pub[pub["val_loss"].notna()]
    N5, D5, L5 = pub["N_params_B"].to_numpy(), pub["D_tokens_B"].to_numpy(), pub["val_loss"].to_numpy()
    L5h = predict_classical(p_c, N5, D5)
    res["validation"]["published_r2_raw"] = r2_metric(L5, L5h)
    res["validation"]["published_r2_offset"] = r2_offset(L5, L5h)
    print(f"文献数据: 原始R2={res['validation']['published_r2_raw']:.4f}, 去偏移R2={res['validation']['published_r2_offset']:.4f}")

    # ===== 5. 广义标度律: B6+B7 拟合, B8 单独诊断 =====
    b6 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment.csv"))
    b7 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment_expanded.csv"))
    b8 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment_large.csv"))
    fit_df = pd.concat([b6, b7])
    NN, DD, QQ, LL = (fit_df[k].to_numpy() for k in ["N_params_B", "D_tokens_B", "Q_score", "val_loss"])
    results = {}
    for form in ("additive", "interaction", "interaction_N"):
        sol = fit_generalized(NN, DD, QQ, LL, form=form)
        lh = predict_generalized(sol.x, NN, DD, QQ, form=form)
        r2 = r2_metric(LL, lh)
        pnames = ["E", "A", "a", "B", "b", "C", "g"] + (["d"] if form == "interaction" else []) + (["h"] if form == "interaction_N" else [])
        results[form] = {"params": {kk: float(v) for kk, v in zip(pnames, sol.x)},
                         "r2_fit": r2}
        print(f"[广义 {form}] 拟合R2={r2:.5f}")
    # B8 数据一致性诊断: 同一 N,D 下 Q 与 Loss 的方向
    corr_b6 = []
    for (nn, dd), g in b6.groupby(["N_params_B", "D_tokens_B"]):
        if len(g) > 2:
            corr_b6.append(np.corrcoef(g["Q_score"], g["val_loss"])[0, 1])
    corr_b8 = []
    for (nn, dd), g in b8.groupby(["N_params_B", "D_tokens_B"]):
        if len(g) > 2:
            corr_b8.append(np.corrcoef(g["Q_score"], g["val_loss"])[0, 1])
    diag = {"B6_within_corr_mean": float(np.mean(corr_b6)), "B8_within_corr_mean": float(np.mean(corr_b8))}
    print("B6 组内 corr(Q,Loss) 均值 =", round(diag["B6_within_corr_mean"], 3),
          "| B8 组内 corr(Q,Loss) 均值 =", round(diag["B8_within_corr_mean"], 3))
    # B8 单独拟合 (说明: B8 为半合成外推补充, 其 Loss 尺度与 Q 方向与 B6/B7 不同,
    #  仅用于结构稳健性对照, 不作直接实验观测)
    b8_fit = {}
    for form in ("additive", "interaction", "interaction_N"):
        sol8 = fit_generalized(b8["N_params_B"].to_numpy(), b8["D_tokens_B"].to_numpy(),
                               1.0 - b8["Q_score"].to_numpy(), b8["val_loss"].to_numpy(), form=form)
        lh8 = predict_generalized(sol8.x, b8["N_params_B"].to_numpy(), b8["D_tokens_B"].to_numpy(),
                                  1.0 - b8["Q_score"].to_numpy(), form=form)
        b8_fit[form] = {"r2_fit_B8": r2_metric(b8["val_loss"].to_numpy(), lh8)}
        print(f"[B8 单独 {form}] 拟合R2={b8_fit[form]['r2_fit_B8']:.5f}")
    # 选拟合优度更高者 (基于 B6+B7; 同参数个数 7/8/8, 直接比 R2)
    formg = max(results, key=lambda f: results[f]["r2_fit"])
    pg = results[formg]["params"]
    print("选用形式:", formg, pg)
    res["generalized"] = {"chosen": formg, "forms": results, "B8_diagnosis": diag, "B8_fit": b8_fit}

    # ===== 6. 弹性与等价条件 (基准点 N=1B, D=300B, Q=0.6) =====
    E2, A2, a2, B2, b2, C2, g2 = (pg[k] for k in ["E", "A", "a", "B", "b", "C", "g"])
    d2 = pg.get("d", 0.0)
    h2 = pg.get("h", 0.0)

    def Lfun(NNv, DDv, QQv):
        base_val = E2 + A2 * NNv ** (-a2) + B2 * DDv ** (-b2)
        qterm = C2 * np.maximum(1 - QQv, 0) ** g2
        if formg == "interaction":
            qterm *= DDv ** (-d2)
        if formg == "interaction_N":
            qterm *= NNv ** (-h2)
        return base_val + qterm

    N0, D0, Q0 = 1.0, 300.0, 0.6
    hh = 1e-3
    L0 = Lfun(N0, D0, Q0)
    eps_N = (Lfun(N0 * (1 + hh), D0, Q0) - L0) / (hh * L0)
    eps_D = (Lfun(N0, D0 * (1 + hh), Q0) - L0) / (hh * L0)
    eps_Q = (Lfun(N0, D0, Q0 + hh) - L0) / (hh * L0)
    print(f"基准(N={N0}B,D={D0}B,Q={Q0}): eps_N={eps_N:.4f} eps_D={eps_D:.4f} eps_Q={eps_Q:.4f}")
    res["elasticity"] = {"N0": N0, "D0": D0, "Q0": Q0, "L0": L0,
                         "eps_N": eps_N, "eps_D": eps_D, "eps_Q": eps_Q}

    # 等价条件: Q 提升 dQ=0.1 的等效参数增量
    dLdN = A2 * a2 * N0 ** (-a2 - 1)
    dLdQ = -C2 * g2 * (1 - Q0) ** (g2 - 1)
    if formg == "interaction":
        dLdQ *= D0 ** (-d2)
    if formg == "interaction_N":
        dLdQ *= N0 ** (-h2)
    eq_dN = -(dLdQ / dLdN) * 0.1
    res["equivalence"] = {"dLdN": dLdN, "dLdQ": dLdQ, "dN_per_dQ0.1": eq_dN}
    print(f"质量提升0.1等价于参数增加 dN = {eq_dN:.4f} B (基准点)")

    # 不同 Q0 下等价曲线
    qs = np.linspace(0.1, 0.95, 50)
    dns = []
    for q in qs:
        dLdQq = -C2 * g2 * (1 - q) ** (g2 - 1)
        if formg == "interaction":
            dLdQq *= D0 ** (-d2)
        if formg == "interaction_N":
            dLdQq *= N0 ** (-h2)
        dns.append(-(dLdQq / dLdN) * 0.1)
    res["equivalence"]["curve"] = {"q": qs.tolist(), "dN": dns}

    # ===== 7. 外推验证: B10 大模型 Loss =====
    lg = pd.read_csv(os.path.join(B, "supplementary_large_baseline.csv"))
    lg = lg[lg["val_loss"].notna()]
    Nl, Dl, Ll = lg["N_params_B"].to_numpy(), lg["D_tokens_B"].to_numpy(), lg["val_loss"].to_numpy()
    Llh = predict_classical(p_c, Nl, Dl)
    r2_large_raw = r2_metric(Ll, Llh)
    r2_large_off = r2_offset(Ll, Llh)
    res["extrapolation"] = {"r2_large_raw": r2_large_raw, "r2_large_offset": r2_large_off}
    print(f"100B-10000B 外推: 原始R2={r2_large_raw:.4f} 去偏移R2={r2_large_off:.4f}")

    with open(os.path.join(RES, "p2_scaling_results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    # ===== 8. 图 =====
    # (a) 经典标度律拟合
    fig, ax = plt.subplots(figsize=(6.2, 6))
    ax.scatter(L, Lhat_c, s=8, alpha=0.5, color="#2563EB")
    lims = [L.min() - 0.1, L.max() + 0.1]
    ax.plot(lims, lims, "r--", lw=1)
    ax.set_xlabel("实际验证 Loss (B1 Pythia)"); ax.set_ylabel("标度律预测 Loss")
    ax.set_title(f"经典标度律拟合 (R2={r2_c:.4f})")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p2_classical_fit.png"), dpi=200); plt.close(fig)

    # (b) 广义标度律拟合 (B6+B7)
    lh_all = predict_generalized(np.array([pg[k] for k in pg]), NN, DD, QQ, form=formg)
    fig, ax = plt.subplots(figsize=(6.2, 6))
    s = ax.scatter(LL, lh_all, c=QQ, s=10, alpha=0.6, cmap="viridis")
    cb = fig.colorbar(s, ax=ax); cb.set_label("Q")
    lims = [LL.min() - 0.1, LL.max() + 0.1]
    ax.plot(lims, lims, "r--", lw=1)
    ax.set_xlabel("实际 Loss (B6+B7)"); ax.set_ylabel("广义标度律预测 Loss")
    ax.set_title(f"广义标度律拟合 (R2={results[formg]['r2_fit']:.4f})")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p2_generalized_fit.png"), dpi=200); plt.close(fig)

    # (c) 弹性条形图
    fig, ax = plt.subplots(figsize=(6, 4.5))
    names = ["参数弹性 eps_N", "数据弹性 eps_D", "质量弹性 eps_Q"]
    vals = [eps_N, eps_D, eps_Q]
    bars = ax.bar(names, vals, color=["#2563EB", "#0EA5E9", "#10B981"])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.005, f"{v:.3f}", ha="center")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title(f"基准点 (N={N0}B, D={D0}B, Q={Q0}) 的边际弹性")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p2_elasticity.png"), dpi=200); plt.close(fig)

    # (d) 质量-参数等价
    fig, ax = plt.subplots(figsize=(6.2, 4.5))
    ax.plot(qs, dns, color="#7C3AED", lw=2)
    ax.set_xlabel("当前质量 Q"); ax.set_ylabel("Q 提升 0.1 的等效参数增量 dN (B)")
    ax.set_title(f"质量-规模等价关系 (N={N0}B, D={D0}B)")
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p2_equivalence.png"), dpi=200); plt.close(fig)

    # (e) 外推验证 (B8 + B10)
    fig, ax = plt.subplots(figsize=(6.2, 6))
    ax.scatter(Nl, Ll, s=30, color="#2563EB", label="大模型 Loss (B10)")
    ax.scatter(Nl, Llh, s=18, marker="x", color="#EF4444", label="经典标度律预测")
    ax.set_xscale("log")
    ax.set_xlabel("参数量 N (B)"); ax.set_ylabel("Loss")
    ax.set_title(f"100B-10000B 外推验证 (去偏移R2={r2_large_off:.4f})")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p2_extrapolation.png"), dpi=200); plt.close(fig)

    print("done p2")


if __name__ == "__main__":
    main()
