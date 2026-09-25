# -*- coding: utf-8 -*-
"""
v3 实验: 问题二标度律家族对比 (不被单一形式局限)
对比:
  A) 质量项形式: 加性(基线A) / 交互D(基线B) / 乘性因子 / N交互 / 饱和形式
  B) 拟合家族: 最小二乘(基线) / log空间拟合 / Huber鲁棒 / 分位数拟合
  C) 参数不确定性: 自助法置信区间 (经典形式)
  D) 留一族交叉验证: 跨家族泛化稳健性
输出: experiments/v3_p2_*.csv/json + 图, 结论写 experiments/v3_conclusion.md
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import B, RES, FIG, BASE
from scipy.optimize import least_squares

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


# ---------- 数据 ----------
def load_b67():
    b6 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment.csv"))
    b7 = pd.read_csv(os.path.join(B, "supplementary_NQ_experiment_expanded.csv"))
    return pd.concat([b6, b7])


# ---------- 质量项形式库 ----------
def loss_forms(N, D, Q, p, form):
    """p = [E, A, a, B, b, C, g, (d|h|s)] 长度随形式而定"""
    if form == "additive":
        E, A, a, B, b, C, g = p
        return E + A * N ** (-a) + B * D ** (-b) + C * np.maximum(1 - Q, 0) ** g
    if form == "interaction_D":                    # 基线
        E, A, a, B, b, C, g, d = p
        return E + A * N ** (-a) + B * D ** (-b) + C * np.maximum(1 - Q, 0) ** g * D ** (-d)
    if form == "interaction_N":
        E, A, a, B, b, C, g, h = p
        return E + A * N ** (-a) + B * D ** (-b) + C * np.maximum(1 - Q, 0) ** g * N ** (-h)
    if form == "multiplicative":
        E, A, a, B, b, C, g = p
        base = A * N ** (-a) + B * D ** (-b)
        return E + base * (1 + C * np.maximum(1 - Q, 0) ** g)
    if form == "saturating":
        E, A, a, B, b, C, g, s = p
        return E + A * N ** (-a) + B * D ** (-b) + C * (np.maximum(1 - Q, 0) / (s + np.maximum(1 - Q, 0))) ** g
    if form == "exponential_Q":
        E, A, a, B, b, C, g = p
        return E + A * N ** (-a) + B * D ** (-b) + C * np.exp(-g * Q)
    raise ValueError(form)


N_FORM_PARAMS = {"additive": 7, "interaction_D": 8, "interaction_N": 8,
                 "multiplicative": 7, "saturating": 8, "exponential_Q": 7}
PARAM_NAMES = {"additive": ["E", "A", "a", "B", "b", "C", "g"],
               "interaction_D": ["E", "A", "a", "B", "b", "C", "g", "d"],
               "interaction_N": ["E", "A", "a", "B", "b", "C", "g", "h"],
               "multiplicative": ["E", "A", "a", "B", "b", "C", "g"],
               "saturating": ["E", "A", "a", "B", "b", "C", "g", "s"],
               "exponential_Q": ["E", "A", "a", "B", "b", "C", "g"]}


def fit_form(N, D, Q, L, form, loss_type="l2"):
    npar = N_FORM_PARAMS[form]
    p0 = np.zeros(npar)
    p0[0] = L.min() * 0.7     # E
    p0[1], p0[3] = 3.0, 3.0   # A, B
    p0[2], p0[4] = 0.3, 0.3   # a, b
    p0[5] = 1.0               # C
    p0[6] = 1.5               # g
    if form in ("interaction_D", "interaction_N", "saturating"):
        p0[7] = 0.3
    lb = np.array([0, 1e-6, 1e-4, 1e-6, 1e-4, 1e-6, 1e-4] + [1e-4] * (npar - 7))
    ub = np.array([L.min() * 1.2, 1e3, 5, 1e3, 5, 1e3, 10] + [5.0] * (npar - 7))

    def resid(p):
        return loss_forms(N, D, Q, p, form) - L

    if loss_type == "l2":
        sol = least_squares(resid, p0, bounds=(lb, ub), max_nfev=120000)
    elif loss_type == "huber":
        def hres(p):
            r = resid(p)
            return np.where(np.abs(r) <= 1.35, r, np.sign(r) * (1.35 * (2 * np.abs(r) - 1.35)) ** 0.5)
        sol = least_squares(hres, p0, bounds=(lb, ub), max_nfev=120000)
    elif loss_type == "log":
        def lres(p):
            pred = loss_forms(N, D, Q, p, form)
            return np.log(np.maximum(pred, 1e-9)) - np.log(np.maximum(L, 1e-9))
        sol = least_squares(lres, p0, bounds=(lb, ub), max_nfev=120000)
    pred = loss_forms(N, D, Q, sol.x, form)
    r2 = 1 - np.sum((L - pred) ** 2) / np.sum((L - L.mean()) ** 2)
    return sol.x, r2


def main():
    df = load_b67()
    N, D, Q, L = (df[k].to_numpy() for k in ["N_params_B", "D_tokens_B", "Q_score", "val_loss"])
    print("B6+B7:", len(df))

    # ========== A: 质量项形式对比 (L2 拟合) ==========
    forms = ["additive", "interaction_D", "interaction_N", "multiplicative", "saturating", "exponential_Q"]
    rows = []
    for f in forms:
        p, r2 = fit_form(N, D, Q, L, f)
        rows.append({"form": f, "r2": r2,
                     "params": {k: float(v) for k, v in zip(PARAM_NAMES[f], p)}})
        print(f"[{f}] R2={r2:.5f} params={dict(zip(PARAM_NAMES[f], np.round(p, 4)))}")
    form_df = pd.DataFrame([{"form": r["form"], "r2": r["r2"]} for r in rows])
    form_df.to_csv(os.path.join(EX, "v3_p2_forms.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(EX, "v3_p2_forms_full.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    # 加性 vs 交互D vs 乘性 残差图
    fig, ax = plt.subplots(figsize=(8, 5))
    for f in ["additive", "interaction_D", "multiplicative"]:
        p, _ = fit_form(N, D, Q, L, f)
        pred = loss_forms(N, D, Q, p, f)
        ax.scatter(pred, L - pred, s=6, alpha=0.4, label=f)
    ax.axhline(0, color="#88ada6", lw=0.8)
    ax.set_xlabel("预测 Loss"); ax.set_ylabel("残差")
    ax.set_title("v3: 不同质量项形式的残差分布")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v3_p2_forms_resid.png"), dpi=200); plt.close(fig)

    # ========== B: 拟合家族对比 (交互D形式) ==========
    print("\n拟合家族对比 (interaction_D):")
    fit_rows = []
    for lt in ["l2", "huber", "log"]:
        p, r2 = fit_form(N, D, Q, L, "interaction_D", loss_type=lt)
        fit_rows.append({"loss_type": lt, "r2": r2})
        print(f"  [{lt}] R2={r2:.5f}")
    fit_df = pd.DataFrame(fit_rows)
    fit_df.to_csv(os.path.join(EX, "v3_p2_fit_families.csv"), index=False, encoding="utf-8-sig")

    # ========== C: 经典形式自助置信区间 ==========
    b1 = pd.read_csv(os.path.join(B, "pythia_training_log_existing.csv"))
    print("\nB1:", b1.shape)
    N1, D1, L1 = (b1[k].to_numpy() for k in ["N_params_B", "D_tokens_B", "val_loss"])
    rng = np.random.default_rng(7)
    nb = 300
    boots = []
    idx = np.arange(len(b1))
    for _ in range(nb):
        s = rng.choice(idx, size=len(idx), replace=True)
        def resid(p):
            E, A, a, B, b = p
            return E + A * N1[s] ** (-a) + B * D1[s] ** (-b) - L1[s]
        try:
            sol = least_squares(resid, [L1.min() * 0.8, 3, 0.3, 3, 0.3],
                                bounds=([0, 1e-6, 1e-4, 1e-6, 1e-4], [L1.min(), 1e3, 5, 1e3, 5]),
                                max_nfev=20000)
            boots.append(sol.x)
        except Exception:
            pass
    boots = np.array(boots)
    ci = np.percentile(boots, [5, 50, 95], axis=0)
    boot_df = pd.DataFrame(ci, columns=["E", "A", "a", "B", "b"], index=["p5", "p50", "p95"])
    boot_df.to_csv(os.path.join(EX, "v3_p2_bootstrap_ci.csv", ), encoding="utf-8-sig")
    print("\n经典参数自助 90% 区间:")
    print(boot_df.round(4).to_string())

    # ========== D: 留一族交叉验证 (B4 缩放基准, B5 文献) ==========
    from sklearn.model_selection import LeaveOneGroupOut
    b4 = pd.read_csv(os.path.join(B, "scaling_baseline.csv"))
    b5 = pd.read_csv(os.path.join(B, "published_scaling_data.csv"))
    print("\nB4:", b4.shape, "B5:", b5.shape)
    print("B4 cols:", list(b4.columns)[:12])
    print("B5 cols:", list(b5.columns)[:12])

    print("\ndone v3 p2")


if __name__ == "__main__":
    main()
