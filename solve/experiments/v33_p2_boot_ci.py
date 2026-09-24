# -*- coding: utf-8 -*-
"""
v33 实验: 广义标度律参数的 Bootstrap 置信区间
对 B6+B7 (810 点) 上的 interaction_N 形式做 case bootstrap (300 次重抽):
1) 参数 CI (E,A,a,B,b,C,g,h) 2.5/97.5 分位;
2) 弹性 eps_N/eps_D/eps_Q 的 CI (重抽后逐参数重算弹性);
3) 等价结论 (Q+0.1 ~= 多少 B 参数) 的 CI.
输出: experiments/v33_p2_boot_ci.csv/.json/.png
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

PARAMS = ["E", "A", "a", "B", "b", "C", "g", "h"]
N0, D0, Q0 = 1.0, 300.0, 0.6


def elasticities(p):
    E, A, a, B_, b, C, g, h = p
    L = E + A * N0 ** (-a) + B_ * D0 ** (-b) + C * (1 - Q0) ** g * N0 ** (-h)
    # 数值差分口径(同主链路 p2_scaling): d lnL/d lnN 含 h 交互通道
    hh = 1e-4
    LpN = loss_fn(N0 * (1 + hh), D0, Q0, p)
    LpD = loss_fn(N0, D0 * (1 + hh), Q0, p)
    LpQ = loss_fn(N0, D0, Q0 + hh, p)
    eps_N = (LpN - L) / (hh * L)
    eps_D = (LpD - L) / (hh * L)
    eps_Q = (LpQ - L) / (hh * L)
    return eps_N, eps_D, eps_Q


def loss_fn(N, D, Q, p):
    E, A, a, B_, b, C, g, h = p
    return E + A * N ** (-a) + B_ * D ** (-b) + C * (1 - Q) ** g * N ** (-h)


def equiv_params(p):
    """质量 +0.1 等价参数节省: 求 N' 使 L(N',D0,Q0+0.1)=L(N0,D0,Q0)"""
    L0 = loss_fn(N0, D0, Q0, p)
    lo, hi = 1e-4, N0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if loss_fn(mid, D0, Q0 + 0.1, p) < L0:
            hi = mid
        else:
            lo = mid
    return N0 - 0.5 * (lo + hi)


def main():
    df = load_b67()
    N, D, Q, L = (df[k].to_numpy(dtype=float) for k in
                  ["N_params_B", "D_tokens_B", "Q_score", "val_loss"])
    rng = np.random.default_rng(7)
    B = 300
    boots = []
    for i in range(B):
        idx = rng.integers(0, len(L), len(L))
        try:
            p, _ = fit_form(N[idx], D[idx], Q[idx], L[idx], "interaction_N")
            boots.append(p)
        except Exception:
            pass
    M = np.array(boots)
    print(f"bootstrap 成功 {len(M)}/{B}")

    lo, hi = np.percentile(M, [2.5, 97.5], axis=0)
    med = np.median(M, axis=0)
    rows = []
    for j, name in enumerate(PARAMS):
        rows.append({"param": name, "boot_median": float(med[j]),
                     "ci_lo": float(lo[j]), "ci_hi": float(hi[j])})
        print(f"{name}: {med[j]:.4f} [{lo[j]:.4f}, {hi[j]:.4f}]")

    epsM = np.array([elasticities(p) for p in M])
    for j, nm in enumerate(["eps_N", "eps_D", "eps_Q"]):
        e_lo, e_hi = np.percentile(epsM[:, j], [2.5, 97.5])
        print(f"{nm}: {np.median(epsM[:, j]):.4f} [{e_lo:.4f}, {e_hi:.4f}]")
        rows.append({"param": nm, "boot_median": float(np.median(epsM[:, j])),
                     "ci_lo": float(e_lo), "ci_hi": float(e_hi)})

    eqM = np.array([equiv_params(M[i]) for i in range(len(M))])
    e_lo, e_hi = np.percentile(eqM, [2.5, 97.5])
    print(f"equivalence(Q+0.1): {np.median(eqM):.3f}B [{e_lo:.3f}, {e_hi:.3f}]")
    rows.append({"param": "equiv_B", "boot_median": float(np.median(eqM)),
                 "ci_lo": float(e_lo), "ci_hi": float(e_hi)})

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v33_p2_boot_ci.csv"), index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    show = ["a", "b", "h", "g", "eps_N", "eps_D", "eps_Q", "equiv_B"]
    sub = rdf[rdf["param"].isin(show)]
    y = np.arange(len(sub))
    ax.errorbar(sub["boot_median"], y, xerr=[sub["boot_median"] - sub["ci_lo"],
                                             sub["ci_hi"] - sub["boot_median"]],
                fmt="o", color="#2563EB", capsize=4, lw=1.5)
    ax.set_yticks(y); ax.set_yticklabels(sub["param"])
    ax.axvline(0, color="#94A3B8", lw=0.8, ls="--")
    ax.set_title("v33: 广义标度律参数 Bootstrap CI (n=810, B=300)")
    fig.tight_layout(); fig.savefig(os.path.join(EX, "v33_p2_boot_ci.png"), dpi=200)
    plt.close(fig)

    with open(os.path.join(EX, "v33_p2_boot_ci.json"), "w", encoding="utf-8") as f:
        json.dump({"n_boot": len(M), "rows": rows}, f, ensure_ascii=False, indent=2)
    print("\ndone v33")


if __name__ == "__main__":
    main()