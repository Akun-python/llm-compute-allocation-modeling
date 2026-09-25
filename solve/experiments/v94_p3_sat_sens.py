# -*- coding: utf-8 -*-
"""
v94 实验: P3 激活/饱和预算对成本参数 (eta, g(Q) 幅度) 的敏感性
在基准配置 (eta=2e-4, gscale=1, L_ctx=4096) 上扫描两个最不确定的
成本参数:
  eta   in {1e-4, 2e-4, 4e-4}  (注意力成本系数)
  gscale in {0.3, 1.0, 3.0}     (质量成本 g(Q) 整体幅度)
9 配置 x 3 形式, 网格 logspace(17,26,91) (步长 0.1 dex, 全部基准
阈值点 17.8/18.3/18.5/19.95/20.25 均落在网格上, 与 v91 逐位闭合)。
每个配置识别 Q_active (Q>Q0+0.005) 与首饱和 (Q>=1-1e-9) 的预算,
以 dex 位移报告灵敏度。输出 v94 json/csv/png。
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
import p3_optimization as p3
from common import BASE

EX = os.path.join(os.path.dirname(__file__))
L_CTX = 4096
CGRID = np.logspace(17, 26, 91)

def scan(eta, gscale):
    """返回 {form: {"Q_active_C": ..., "first_sat_C": ...}}"""
    orig_g = p3.g_cost
    p3.ETA = eta
    if gscale != 1.0:
        p3.g_cost = lambda Q, form: orig_g(Q, form) * gscale
    out = {}
    for form in p3.G_FORMS:
        q_act, first_sat, was_sat = None, None, False
        prev_act = False
        for C in CGRID:
            s = p3.solve_opt(C, form, L_CTX)
            if s is None:
                continue
            act = bool(s["Q"] > p3.Q0 + 0.005)
            sat = bool(s["Q"] >= 1.0 - 1e-9)
            if act and not prev_act and q_act is None:
                q_act = C
            if sat and not was_sat and first_sat is None:
                first_sat = C
            prev_act, was_sat = act, sat
        out[form] = {"Q_active_C": q_act, "first_sat_C": first_sat}
    p3.g_cost = orig_g
    return out

def main():
    etas = [1e-4, 2e-4, 4e-4]
    gscales = [0.3, 1.0, 3.0]
    rows = []
    base = None
    for eta in etas:
        for gs in gscales:
            r = scan(eta, gs)
            for form in p3.G_FORMS:
                rows.append({"eta": eta, "gscale": gs, "form": form,
                             "Q_active_C": r[form]["Q_active_C"],
                             "first_sat_C": r[form]["first_sat_C"]})
            if eta == 2e-4 and gs == 1.0:
                base = r
    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v94_p3_sat_sens.csv"), index=False, encoding="utf-8-sig")

    # 基准闭合 vs v91 (0.1 网格应逐位一致)
    v91 = json.load(open(os.path.join(EX, "v91_p3_activation_sat.json"), encoding="utf-8"))
    closure = {}
    for form in p3.G_FORMS:
        b = base[form]
        closure[form] = {
            "sat": b["first_sat_C"], "sat_v91": v91["saturation"][form]["C"],
            "sat_match": bool(b["first_sat_C"] is not None and
                              abs(b["first_sat_C"] - v91["saturation"][form]["C"]) < 1e-9),
            "act": b["Q_active_C"], "act_v91": v91["activation"][form]["C"],
            "act_match": bool(b["Q_active_C"] is not None and
                              abs(b["Q_active_C"] - v91["activation"][form]["C"]) < 1e-9)}
        print(f"[{form}] sat {b['first_sat_C']:.4e} (v91 {v91['saturation'][form]['C']:.4e}) "
              f"{'OK' if closure[form]['sat_match'] else 'MISMATCH'} | "
              f"act {b['Q_active_C']:.4e} (v91 {v91['activation'][form]['C']:.4e}) "
              f"{'OK' if closure[form]['act_match'] else 'MISMATCH'}")

    # 灵敏度汇总 (基准=eta 2e-4, gscale 1)
    sens = {}
    for form in p3.G_FORMS:
        base_sat = base[form]["first_sat_C"]
        shifts = []
        for _, rr in rdf[(rdf.form == form) & (rdf.eta == 2e-4)].iterrows():
            shifts.append(np.log10(rr["first_sat_C"] / base_sat))
        g_shifts = shifts  # eta fixed
        eta_shifts = []
        for _, rr in rdf[(rdf.form == form) & (rdf.gscale == 1.0)].iterrows():
            eta_shifts.append(np.log10(rr["first_sat_C"] / base_sat))
        sens[form] = {"sat_base_dex": float(np.log10(base_sat)),
                      "gscale_dex_shift": [float(v) for v in g_shifts],
                      "eta_dex_shift": [float(v) for v in eta_shifts],
                      "max_abs_shift_dex": float(max(
                          max(abs(float(v)) for v in g_shifts),
                          max(abs(float(v)) for v in eta_shifts)))}
        print(f"[{form}] 饱和灵敏度: |dex 位移|max={sens[form]['max_abs_shift_dex']:.3f}")

    out = {"grid": "logspace(17,26,91)", "L_ctx": L_CTX,
           "closure_v91": closure, "sens": sens}
    with open(os.path.join(EX, "v94_p3_sat_sens.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # ---- 图 ----
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
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    forms = p3.G_FORMS
    for ax, key, label in [(axes[0], "gscale", "质量成本幅度 g(Q)×"), (axes[1], "eta", "注意力系数 η")]:
        for i, form in enumerate(forms):
            vals = []
            for eta in etas:
                for gs in gscales:
                    if (key == "gscale" and eta == 2e-4) or (key == "eta" and gs == 1.0):
                        rr = rdf[(rdf.form == form) & (rdf.eta == eta) & (rdf.gscale == gs)].iloc[0]
                        vals.append(np.log10(rr["first_sat_C"]))
            xs = (gscales if key == "gscale" else etas)
            ax.plot(xs, vals, "o-", lw=1.3, label=form)
        ax.set_xscale("log")
        ax.set_xlabel(label)
        ax.set_ylabel("log10 首饱和预算 (FLOPs)")
        ax.legend(fontsize=8)
    axes[0].set_title("饱和预算对质量成本幅度的敏感性")
    axes[1].set_title("饱和预算对注意力系数的敏感性")
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v94_p3_sat_sens.png"), dpi=200)
    plt.close(fig)
    print("\nDONE v94")


if __name__ == "__main__":
    main()