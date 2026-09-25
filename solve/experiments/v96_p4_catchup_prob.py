# -*- coding: utf-8 -*-
"""
v96 实验: 开源家族追赶时间的 Bootstrap 概率化 (锚定 §8 追赶分析)
v69 给出确定性 T_catch = gap / (g_fam - g_lead)。本实验对整个管道
(逐族月 90 分位 -> 对数线性斜率 -> 相对领跑者 gap -> T_catch) 做
模型层 case bootstrap (逐族逐月按模型重抽, 300 次), 零额外参数假设,
给出每族追赶时间的分布与概率:
  P(T <= 12 月), P(T <= 24 月), 中位 T 的 90% 区间;
领跑者身份允许在 bootstrap 中变化 (真实的"谁领跑"不确定性)。
输入: 附件 C 的 leaderboard_cleaned.csv (与 v69 相同过滤)
输出: experiments/v96_p4_catchup_prob.json/.csv/.png
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, BASE

EX = os.path.join(os.path.dirname(__file__))
B = 300
RNG = np.random.default_rng(7)


FAMILIES = ["llama", "qwen", "gemma", "deepseek", "mistral", "phi", "olmo",
            "gpt", "claude", "baichuan", "yi", "falcon"]


def fam_of(n):
    n = (n or "").lower()
    for f in FAMILIES:
        if f in n:
            return f
    return "other"


def run_pipeline(lb):
    """v69 管道: 返回 {family: {"S90_now","g_month","T_catch"}}"""
    lb = lb.copy()
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb = lb[lb["date"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[(lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0) & lic
             & (lb["date"] >= "2024-06-01")].copy()
    dfm["ym"] = dfm["date"].dt.to_period("M").astype(str)
    dfm["family"] = dfm["Model"].apply(fam_of)
    rows = {}
    for f, g in dfm.groupby("family"):
        if len(g) < 30:
            continue
        gm = g.groupby("ym")["Average ⬆️"].quantile(0.9)
        gm = gm[gm.notna()].sort_index()
        if len(gm) < 4:
            continue
        ts = np.arange(len(gm)); ys = np.log(gm.to_numpy())
        b = float(np.polyfit(ts, ys, 1)[0])
        rows[f] = {"S90_now": float(gm.iloc[-1]), "g_month": b,
                   "n_models": int(len(g)), "months": list(gm.index)}
    return rows


def catchup(rows):
    """v69 追赶计算 -> {family: T_catch or None}"""
    if not rows:
        return {}
    lead = max(rows, key=lambda f: rows[f]["S90_now"])
    out = {}
    for f, r in rows.items():
        gap = np.log(rows[lead]["S90_now"] / r["S90_now"])
        rel = r["g_month"] - rows[lead]["g_month"]
        out[f] = float(gap / rel) if rel > 0 else np.nan
    return out


def main():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    base = run_pipeline(lb)
    base_T = catchup(base)
    fams = sorted(base_T)
    print("基线(确定性)追赶月数:", {f: (None if np.isnan(base_T[f]) else round(base_T[f], 1)) for f in fams})

    # 逐步族月索引, 供 case bootstrap 抽样
    cells = {}
    lb2 = lb.copy()
    lb2["date"] = pd.to_datetime(lb2["Submission Date"], errors="coerce")
    lic = lb2["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb2[(lb2["#Params (B)"] > 0) & (lb2["Average ⬆️"] > 0) & lic
              & (lb2["date"] >= "2024-06-01")].copy()
    dfm["ym"] = dfm["date"].dt.to_period("M").astype(str)
    dfm["family"] = dfm["Model"].apply(fam_of)
    for f, g in dfm.groupby("family"):
        if len(g) < 30:
            continue
        gm = g.groupby("ym")["Average ⬆️"].quantile(0.9)
        gm = gm[gm.notna()]
        if len(gm) < 4:
            continue
        for ym, q in gm.items():
            sub = g[g["ym"] == ym]["Average ⬆️"].to_numpy()
            cells[(f, str(ym))] = sub

    Ts = {f: [] for f in fams}
    for b in range(B):
        # 每个 (族,月) 格点按原样本量有放回重抽
        boots = {}
        for (f, ym), vals in cells.items():
            boots[f] = boots.get(f, {})
            boots[f][ym] = RNG.choice(vals, size=len(vals), replace=True)
        resampled = []
        for f, ymvals in boots.items():
            # 按完整 yyyy-mm 键排序 (字符串序即时间序), 构建月度 90 分位序列
            ents = {ym: float(np.quantile(v, 0.9)) for ym, v in ymvals.items()}
            ks = sorted(ents)
            gm = pd.Series([ents[k] for k in ks])
            ys = np.log(gm.to_numpy())
            if np.std(ys) < 1e-12 or len(ys) < 4:
                continue
            try:
                bslope = float(np.polyfit(np.arange(len(ys)), ys, 1)[0])
            except np.linalg.LinAlgError:
                continue
            resampled.append({"family": f, "S90_now": float(gm.iloc[-1]), "g_month": bslope})
        if len(resampled) < 3:
            continue
        tmap = catchup({r["family"]: r for r in resampled})
        for f in fams:
            Ts[f].append(tmap.get(f, np.nan))

    out_rows = []
    for f in fams:
        v = np.array([t for t in Ts[f] if not np.isnan(t)])
        any_catch = len(v)
        med = np.median(v) if any_catch else np.nan
        lo = np.percentile(v, 5) if any_catch else np.nan
        hi = np.percentile(v, 95) if any_catch else np.nan
        p12 = float(np.mean(np.array(Ts[f]) <= 12.0)) if Ts[f] else 0.0
        p24 = float(np.mean(np.array(Ts[f]) <= 24.0)) if Ts[f] else 0.0
        never = float(np.mean(np.isnan(np.array(Ts[f])))) if Ts[f] else 1.0
        out_rows.append({"family": f, "T_base_nonas": (None if np.isnan(base_T[f]) else float(base_T[f])),
                         "n_boot_nancatch": int(any_catch),
                         "T_median": float(med), "T_ci90": [float(lo), float(hi)],
                         "P_catch_12m": p12, "P_catch_24m": p24, "P_never": never})
        print(f"{f:10s} 基线 {'' if np.isnan(base_T[f]) else round(base_T[f],1):>5} 月 | "
              f"Bootstrap 中位 {med:.1f} [5-95% {lo:.1f},{hi:.1f}] | "
              f"P(<=12月)={p12:.2f} P(<=24月)={p24:.2f} P(永不)={never:.2f}")

    out = {"n_boot": B, "rows": out_rows}
    with open(os.path.join(EX, "v96_p4_catchup_prob.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    pd.DataFrame(out_rows).to_csv(os.path.join(EX, "v96_p4_catchup_prob.csv"),
                                  index=False, encoding="utf-8-sig")

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
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ys = np.arange(len(out_rows))[::-1]
    for y, r in zip(ys, out_rows):
        if np.isnan(r["T_median"]):
            ax.text(2, y, f"{r['family']}  永不 (P={r['P_never']:.0%})", va="center", fontsize=8)
            continue
        lo, hi = r["T_ci90"]; med = r["T_median"]
        ax.plot([lo, hi], [y, y], color="#177cb0", lw=5, alpha=0.55, solid_capstyle="round")
        ax.plot([med], [y], "o", color="#44cef6", ms=7)
        ax.text(hi + 1.5, y, f"{med:.0f} 月 (5-95%: {lo:.0f}-{hi:.0f})", va="center", fontsize=8)
    ax.axvline(12, color="#1685a9", ls="--", lw=1); ax.axvline(24, color="#3eede7", ls="--", lw=1)
    ax.set_yticks(ys); ax.set_yticklabels([r["family"] for r in out_rows][::-1])
    ax.set_xlabel("追赶月数 (对数)"); ax.set_xscale("log")
    ax.set_title("开源家族追赶时间的 Bootstrap 分布 (300 次, 点线=12/24 月)")
    fig.tight_layout()
    fig.savefig(os.path.join(EX, "v96_p4_catchup_prob.png"), dpi=200)
    plt.close(fig)
    print("\nDONE v96")


if __name__ == "__main__":
    main()