# -*- coding: utf-8 -*-
"""
v92 实验: P2 弹性与质量-参数等价性的自动核验 (锚定 §6)
复刻 p2_scaling.py 弹性/等价计算并扩展:
  1) 有限差分对数弹性 (hh=1e-3 前向, 基准 N=1.0B/D=300B/Q=0.6):
     eps_N/eps_D/eps_Q vs p2_scaling_results.json elasticity;
  2) 代码口径一阶等价 dN(0.1) = |dLdQ/dLdN|*0.1 (dLdN 仅 A 项)
     -> 0.289B 声称;
  3) 全导数口径 (含 h 项 ∂L/∂N) 的一阶近似 -> 记录差异;
  4) 严格非线性等价: 解 L(N+dN,D,Q+0.1)=L(N,D,Q) 求 dN
     -> 与 v33 equiv_B (0.216 [0.210,0.224]) 对照。
输出: experiments/v92_p2_elasticity_check.json/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import BASE

EX = os.path.join(os.path.dirname(__file__))
RES = os.path.join(os.path.dirname(__file__), "..", "results")

def main():
    ref = json.load(open(os.path.join(RES, "p2_scaling_results.json"), encoding="utf-8"))
    g = ref["generalized"]
    chosen = g["chosen"]
    p = g["forms"][chosen]["params"]
    E, A, a, B, b, C, gq, h = (float(p[k]) for k in ["E", "A", "a", "B", "b", "C", "g", "h"])
    N0, D0, Q0 = 1.0, 300.0, 0.6

    def Lfun(NN, DD, QQ):
        qterm = C * np.maximum(1 - QQ, 0) ** gq
        qterm *= NN ** (-h)
        return E + A * NN ** (-a) + B * DD ** (-b) + qterm

    # ---- 1. 有限差分对数弹性 (与 p2_scaling 相同口径) ----
    hh = 1e-3
    L0 = Lfun(N0, D0, Q0)
    eps_N = (Lfun(N0 * (1 + hh), D0, Q0) - L0) / (hh * L0)
    eps_D = (Lfun(N0, D0 * (1 + hh), Q0) - L0) / (hh * L0)
    eps_Q = (Lfun(N0, D0, Q0 + hh) - L0) / (hh * L0)
    ref_e = ref["elasticity"]
    eN_ok = abs(eps_N - ref_e["eps_N"]) < 1e-9
    eD_ok = abs(eps_D - ref_e["eps_D"]) < 1e-9
    eQ_ok = abs(eps_Q - ref_e["eps_Q"]) < 1e-9
    print(f"eps_N={eps_N:.8f} (ref {ref_e['eps_N']:.8f}) {'OK' if eN_ok else 'MISMATCH'}")
    print(f"eps_D={eps_D:.8f} (ref {ref_e['eps_D']:.8f}) {'OK' if eD_ok else 'MISMATCH'}")
    print(f"eps_Q={eps_Q:.8f} (ref {ref_e['eps_Q']:.8f}) {'OK' if eQ_ok else 'MISMATCH'}")

    # ---- 2. 代码口径一阶等价 (dLdN 仅 A 项) ----
    dLdN_code = A * a * N0 ** (-a - 1)
    dLdQ = -C * gq * (1 - Q0) ** (gq - 1) * N0 ** (-h)
    eq_code = -(dLdQ / dLdN_code) * 0.1
    ref_eq = ref["equivalence"]["dN_per_dQ0.1"]
    eq_code_ok = abs(eq_code - ref_eq) < 1e-9
    print(f"eq_dN(code)={eq_code:.5f} (ref {ref_eq:.5f}) {'OK' if eq_code_ok else 'MISMATCH'}")

    # ---- 3. 全导数一阶口径 (含 h 项) ----
    dLdN_full = A * a * N0 ** (-a - 1) + h * C * (1 - Q0) ** gq * N0 ** (-h - 1)
    eq_full = -(dLdQ / dLdN_full) * 0.1
    print(f"eq_dN(full-deriv)={eq_full:.5f}")

    # ---- 4. 严格非线性等价 ----
    from scipy.optimize import brentq
    # 4a. 参数节省口径 (v33/v20): 求 N'<N0 使 L(N',D0,Q0+0.1)=L(N0,D0,Q0)
    L0base = Lfun(N0, D0, Q0)
    f_shrink = lambda NN: Lfun(NN, D0, Q0 + 0.1) - L0base
    Np = brentq(f_shrink, 0.3, N0)
    dN_shrink = N0 - Np
    # 4b. 参数增量口径 (§6 一阶近似 0.289B 的严格版本):
    #     求 dN>0 使 L(N0+dN,D0,Q0)=L(N0,D0,Q0+0.1)  (同损失降幅)
    Ltarget = Lfun(N0, D0, Q0 + 0.1)
    f_inc = lambda dN: Lfun(N0 + dN, D0, Q0) - Ltarget
    dN_inc = brentq(f_inc, 1e-6, 5.0)
    v33 = json.load(open(os.path.join(EX, "v33_p2_boot_ci.json"), encoding="utf-8"))
    eb = next(r for r in v33["rows"] if r["param"] == "equiv_B")
    in_ci = eb["ci_lo"] <= dN_shrink <= eb["ci_hi"]
    print(f"eq_save(strict)={dN_shrink:.5f} (N'={Np:.5f}) vs v33 equiv_B {eb['boot_median']:.4f} "
          f"[{eb['ci_lo']:.4f},{eb['ci_hi']:.4f}] {'IN-CI' if in_ci else 'OUTSIDE'}")
    print(f"eq_inc(strict)={dN_inc:.5f} vs 一阶 0.2885 (差异来自非线性)")

    out = {"baseline": {"N0": N0, "D0": D0, "Q0": Q0},
           "elasticity": {"eps_N": eps_N, "eps_D": eps_D, "eps_Q": eps_Q,
                          "ref_match": bool(eN_ok and eD_ok and eQ_ok)},
           "equiv": {"code_convention_0_289": float(eq_code), "code_ref": float(ref_eq),
                     "full_deriv_1st_order": float(eq_full),
                     "strict_save": float(dN_shrink), "N_shrink_to": float(Np),
                     "strict_increment": float(dN_inc),
                     "v33_equiv_B_median": float(eb["boot_median"]),
                     "v33_ci": [float(eb["ci_lo"]), float(eb["ci_hi"])],
                     "strict_in_v33_ci": bool(in_ci)}}
    with open(os.path.join(EX, "v92_p2_elasticity_check.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nDONE v92")

if __name__ == "__main__":
    main()
