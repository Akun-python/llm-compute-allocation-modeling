# -*- coding: utf-8 -*-
"""
v91 实验: P3 结构性转移的激活/饱和阈值一键复算 (锚定 §9/附录B)
复刻 p3_optimization.main() 的结构性转移扫描:
  - Cgrid = logspace(17, 26, 181), L_ctx=4096, solve_opt 24 初值;
  - 转移识别: Q_active (Q > Q0+0.005) 与 dominant (份额主导成分切换);
  - 首饱和: Q 首次 >= 1-1e-9 的预算 (对应 append B 饱和预算)。
交叉核对: p3_results.json transitions (Q_active/dominant) 与
p3_structural_scan.csv 首饱和行 -- 逐位一致才算通过。
输出: experiments/v91_p3_activation_sat.json/.csv/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from p3_optimization import solve_opt, Q0, G_FORMS

EX = os.path.join(os.path.dirname(__file__))
RES = os.path.join(os.path.dirname(__file__), "..", "results")
L_CTX = 4096
Q0 = float(Q0)

def main():
    Cgrid = np.logspace(17, 26, 181)
    rows = []
    for form in G_FORMS:
        for C in Cgrid:
            s = solve_opt(C, form, L_CTX)
            if s is None:
                continue
            total = s["C_train"] + s["C_Q"] + s["C_attn"]
            rows.append({"C": C, "form": form, "N": s["N"], "D": s["D"], "Q": s["Q"],
                         "L": s["L"], "C_train": s["C_train"], "C_Q": s["C_Q"],
                         "C_attn": s["C_attn"], "C_total": total,
                         "s_train": s["C_train"] / total, "s_Q": s["C_Q"] / total,
                         "s_attn": s["C_attn"] / total})
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v91_p3_activation_sat.csv"), index=False, encoding="utf-8-sig")

    # ---- 转移/首饱和识别 (与 p3_optimization 相同判据) ----
    detects = {}
    for form in G_FORMS:
        g = rdf[rdf["form"] == form].sort_values("C")
        dom_prev, q_prev = None, False
        q_active_C, first_sat_C, dom_flips = None, None, []
        was_sat = False
        for _, r in g.iterrows():
            sh = [("train", r["s_train"]), ("Q", r["s_Q"]), ("attn", r["s_attn"])]
            dom = max(sh, key=lambda t: t[1])[0]
            q_act = bool(r["Q"] > Q0 + 0.005)
            sat = bool(r["Q"] >= 1.0 - 1e-9)
            if dom_prev is not None and dom != dom_prev:
                dom_flips.append({"C": r["C"], "flip": f"{dom_prev}->{dom}"})
            if not q_prev and q_act and q_active_C is None:
                q_active_C = r["C"]
            if sat and not was_sat and first_sat_C is None:
                first_sat_C = r["C"]
            dom_prev, q_prev, was_sat = dom, q_act, sat
        detects[form] = {"Q_active_C": q_active_C, "first_saturation_C": first_sat_C,
                         "dominant_flips": dom_flips}

    # ---- 交叉核对 ----
    ref = json.load(open(os.path.join(RES, "p3_results.json"), encoding="utf-8"))
    reftr = ref["transitions"]
    scan = pd.read_csv(os.path.join(RES, "p3_structural_scan.csv"), encoding="utf-8-sig")
    checks = []
    for form in G_FORMS:
        exp_qact = next((t[1] for t in reftr.get(form, []) if t[0] == "Q_active"), None)
        ds = scan[scan["form"] == form]
        ds = ds[np.abs(ds["Q"] - 1.0) < 1e-9].sort_values("C")
        exp_sat = ds.iloc[0]["C"] if len(ds) else None
        got_qact = detects[form]["Q_active_C"]
        got_sat = detects[form]["first_saturation_C"]
        q_ok = (got_qact is not None and exp_qact is not None and abs(got_qact - exp_qact) < 1e-9)
        s_ok = (got_sat is not None and exp_sat is not None and abs(got_sat - exp_sat) < 1e-9)
        checks.append({"form": form, "Q_active": got_qact, "Q_active_ref": exp_qact,
                       "Q_active_match": bool(q_ok), "first_sat": got_sat, "first_sat_ref": float(exp_sat),
                       "first_sat_match": bool(s_ok)})
        print(f"[{form}] Q_active={got_qact:.6e} (ref {exp_qact:.6e}) {'OK' if q_ok else 'MISMATCH'} | "
              f"first_sat={got_sat:.6e} (ref {exp_sat:.6e}) {'OK' if s_ok else 'MISMATCH'}")
    all_ok = all(c["Q_active_match"] and c["first_sat_match"] for c in checks)

    out = {"n_grid": int(len(Cgrid)), "L_ctx": L_CTX, "Q0": Q0, "all_match": bool(all_ok),
           "activation": {f: {"C": detects[f]["Q_active_C"]} for f in G_FORMS},
           "saturation": {f: {"C": detects[f]["first_saturation_C"]} for f in G_FORMS},
           "checks": checks}
    with open(os.path.join(EX, "v91_p3_activation_sat.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # ---- 图 (水色系) ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from common import BASE
    for _f in ("SimHei.ttf", "simsun.ttf"):
        _p = os.path.join(BASE, _f)
        if os.path.exists(_p):
            fm.fontManager.addfont(_p)
    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["axes.prop_cycle"] = "cycler(color=['#177cb0', '#1685a9', '#3eede7', '#70f3ff', '#44cef6', '#88ada6'])"
    import plotstyle
    fig, ax = plt.subplots(figsize=(8, 5))
    for f in G_FORMS:
        g = rdf[rdf["form"] == f].sort_values("C")
        ax.plot(g["C"], g["Q"], "o-", ms=2.5, lw=1.2, label=f"g(Q)={f}")
        ax.axvline(detects[f]["Q_active_C"], color="#88ada6", ls=":", lw=1)
        ax.axvline(detects[f]["first_saturation_C"], color="#44cef6", ls="--", lw=1)
    ax.axhline(Q0, color="#3eede7", ls="--", lw=1)
    ax.set_xscale("log"); ax.set_ylim(0.35, 1.02)
    ax.set_xlabel("预算 C (FLOPs)"); ax.set_ylabel("最优质量 Q*")
    ax.set_title("P3 结构性转移: 激活/饱和预算 (点线=激活, 虚线=饱和)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v91_p3_activation_sat.png"), dpi=200)
    plt.close(fig)
    print("\nALL MATCH" if all_ok else "\nMISMATCH FOUND")
    print("done v91")

if __name__ == "__main__":
    main()