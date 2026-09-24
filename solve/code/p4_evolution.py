# -*- coding: utf-8 -*-
"""
问题四: 技术演进分析与前沿预测 (稳健版)
核心设计:
  1) 综合能力度量: C1 leaderboard 6 维平均 Average (口径说明见论文);
  2) 开源筛选: C1 Hub License 含 apache/mit/bsd/llama 等开源许可, 或 C4 open weights;
  3) 时间轴: Submission Date (C1); 历史年份用 C3;
  4) 前沿模型: 分位数回归 (tau=0.9) ln S = c + b_N lnN + b_t t  (2022-2025 开源模型)
     分解: 总增长 = 规模贡献(b_N*dlnN) + 非规模技术贡献(b_t + 残差趋势)
  5) Loss-Benchmark 桥接: C6 (75模型) logit(A)=b0+b1*ln(Loss), 分组误差;
  6) 前沿预测: 按历史 N 增速(基础情景)与增速减半(放缓情景)外推 lnN, 结合技术趋势,
     自助法 90% 区间 (12/24 个月);
  7) C8 逐任务聚合: detailed_results 的 results[group]['acc_norm,none'] 提取,
     与 C1 对照 (Spearman).
"""
import os, json, glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from common import C, RES, FIG, BASE

for _f in ("SimHei.ttf", "simsun.ttf"):
    _p = os.path.join(BASE, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

DIM_GROUPS = {"leaderboard_ifeval": "IFEval", "leaderboard_bbh": "BBH",
              "leaderboard_math_hard": "MATH", "leaderboard_gpqa": "GPQA",
              "leaderboard_musr": "MUSR", "leaderboard_mmlu_pro": "MMLU"}
# 各维度主指标键 (C8 中不同任务使用不同指标; acc_norm 优先, 否则按任务专用键)
DIM_METRIC = {"IFEval": ("inst_level_strict_acc", "prompt_level_strict_acc"),
              "BBH": ("acc_norm", "acc"),
              "MATH": ("exact_match", "acc_norm"),
              "GPQA": ("acc_norm", "acc"),
              "MUSR": ("acc_norm", "acc"),
              "MMLU": ("acc_norm", "acc")}


def quantile_fit(X, y, tau=0.9):
    """简单分位数回归 (线性规划)"""
    n, m = X.shape
    # 用迭代重加权最小二乘近似分位数回归
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    for _ in range(60):
        resid = y - X @ beta
        w = np.where(resid > 0, tau, 1 - tau)
        beta = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)[0]
    return beta


def load_c8():
    rows, n_bad = [], 0
    base = os.path.join(C, "detailed_results")
    dirs = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))
    for d in dirs:
        jsons = glob.glob(os.path.join(base, d, "*.json"))
        best = None
        for jp in jsons:
            try:
                data = json.load(open(jp, encoding="utf-8"))
                if isinstance(data, list):
                    data = data[0] if data else {}
                results = data.get("results", {})
                vals = {}
                for g, cn in DIM_GROUPS.items():
                    gr = results.get(g, {})
                    for k, v in gr.items():
                        if any(k.startswith(m) for m in DIM_METRIC[cn]) and isinstance(v, (int, float)):
                            vals[cn] = v
                            break
                if not vals:
                    continue
                date = data.get("date", 0)
                if best is None or date > best[0]:
                    best = (date, d, vals)
            except Exception:
                n_bad += 1
        if best:
            rows.append({"model_dir": best[1], **best[2]})
    return pd.DataFrame(rows), n_bad


def main():
    res = {}
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    ts = pd.read_csv(os.path.join(C, "leaderboard_extended_timeseries.csv"))
    bridge = pd.read_csv(os.path.join(C, "loss_benchmark_bridge_expanded.csv"))
    ep = pd.read_csv(os.path.join(C, "epoch_all_ai_models.csv"))
    print("C1:", lb.shape, "C3:", ts.shape, "C6:", bridge.shape, "C4:", ep.shape)

    # ---- 时间轴: C1 用 Submission Date ----
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb["year"] = lb["date"].dt.year
    lb = lb[lb["year"].notna()]

    # ---- 开源筛选 (双口径, 取并集) ----
    lic_open = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    lb["is_open"] = lic_open
    ep["open_weights"] = ep.get("Open model weights?").astype(str).str.lower().str.contains("yes|open|true")
    print("\nC1 开源(许可)模型:", int(lb["is_open"].sum()), "/", len(lb))

    # ---- 前沿分位数回归 (2022-2025 开源模型) ----
    dfm = lb[lb["is_open"] & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0)].copy()
    dfm = dfm[dfm["year"] >= 2022]
    dfm["lnS"] = np.log(dfm["Average ⬆️"])
    dfm["lnN"] = np.log(dfm["#Params (B)"])
    dfm["t"] = dfm["year"] - 2022
    X = np.column_stack([np.ones(len(dfm)), dfm["lnN"], dfm["t"]])
    y = dfm["lnS"].to_numpy()
    beta = quantile_fit(X, y, tau=0.9)
    c0, bN, bT = beta
    yhat = X @ beta
    # 前沿残差 (最接近前沿的样本)
    resid = y - yhat
    print(f"\n前沿分位数回归(90%): lnS = {c0:.3f} + {bN:.3f}·lnN + {bT:.4f}·t, "
          f"前沿平均残差={np.percentile(resid, 90):.3f}, n={len(dfm)}")
    res["frontier_qr"] = {"c0": c0, "bN": bN, "bT": bT, "n": int(len(dfm))}

    # ---- 规模/非规模分解 (按年度) ----
    # 用每年前沿样本 (该年得分最高的开源模型) 的 lnN 变化
    years = sorted(dfm["year"].unique())
    frontier_by_year = []
    for yy in years:
        g = dfm[dfm["year"] == yy]
        best = g.loc[g["lnS"].idxmax()]
        frontier_by_year.append({"year": int(yy), "S": float(np.exp(best["lnS"])),
                                 "lnN": float(best["lnN"]), "N": float(best["#Params (B)"])})
    fy = pd.DataFrame(frontier_by_year)
    fy.to_csv(os.path.join(RES, "p4_frontier_years.csv"), index=False, encoding="utf-8-sig")
    print("\n逐年前沿样本 (C1 开源):")
    print(fy.to_string(index=False))

    # 合并历史 (C3, 2019-2021) 前沿: 取累计最大值保证前沿单调不降
    hist = ts[ts["Year"] <= 2021]
    hist_f = {}
    cmax = -1.0
    for yy in sorted(hist["Year"].unique()):
        cmax = max(cmax, float(hist[hist["Year"] == yy]["Average"].max()))
        hist_f[int(yy)] = cmax
    decomp_rows = []
    years_all = sorted(set(list(hist_f.keys()) + list(fy["year"])))
    S_prev = None
    lnN_prev = None
    for yy in years_all:
        if yy in hist_f:
            S_cur, lnN_cur = float(hist_f[yy]), np.log(max(ts[ts["Year"] == yy]["Params_B"].max(), 0.1))
        else:
            r = fy[fy["year"] == yy]
            if not len(r):
                continue
            S_cur, lnN_cur = float(r["S"].iloc[0]), float(r["lnN"].iloc[0])
        if S_prev is not None and S_prev > 0 and S_cur > 0:
            total = np.log(S_cur) - np.log(S_prev)
            scale = bN * (lnN_cur - lnN_prev)
            non_scale = total - scale
            decomp_rows.append({"year": f"{years_all[years_all.index(yy)-1]}-{yy}",
                                "S_prev": S_prev, "S_cur": S_cur, "growth": total,
                                "scale": scale, "non_scale": non_scale,
                                "scale_share": scale / total if abs(total) > 1e-12 else np.nan})
        S_prev, lnN_prev = S_cur, lnN_cur
    decomp = pd.DataFrame(decomp_rows)
    decomp.to_csv(os.path.join(RES, "p4_decomposition.csv"), index=False, encoding="utf-8-sig")
    print("\n前沿增长分解:")
    print(decomp.to_string(index=False))
    res["decomposition"] = decomp.to_dict("records")

    # ---- Loss-Benchmark 桥接 (C6) ----
    br = bridge[bridge["Val_Loss"] > 0].copy()
    br["A"] = br["LB_Average"].clip(1.0, 99.0) / 100.0
    br["logitA"] = np.log(br["A"] / (1 - br["A"]))
    br["lnLoss"] = np.log(br["Val_Loss"])
    Xb = np.column_stack([np.ones(len(br)), br["lnLoss"]])
    betab, *_ = np.linalg.lstsq(Xb, br["logitA"], rcond=None)
    yb = br["logitA"].to_numpy()
    r2b = 1 - np.sum((yb - Xb @ betab) ** 2) / np.sum((yb - yb.mean()) ** 2)
    print(f"\nLoss-Benchmark 桥接: logit(A) = {betab[0]:.3f} + {betab[1]:.3f}·ln(Loss), R2={r2b:.3f}")
    res["bridge"] = {"b0": float(betab[0]), "b1": float(betab[1]), "r2": float(r2b), "n": int(len(br))}

    def loss_to_avg(loss):
        la = betab[0] + betab[1] * np.log(loss)
        return 100.0 / (1 + np.exp(-la))

    br["predA"] = loss_to_avg(br["Val_Loss"])
    br["err"] = br["predA"] - br["LB_Average"]
    grp = br.groupby("Loss_Comparability")["err"].agg(["mean", "std", "count"])
    print("\n桥接误差按可比性:")
    print(grp.to_string())
    res["bridge_error"] = {str(k): {"mean": float(v["mean"]), "std": float(v["std"]),
                                    "count": int(v["count"])} for k, v in grp.iterrows()}

    # ---- 前沿预测 (12/24 个月, 基础 vs 放缓情景) ----
    # 历史参数量增速: 用 C4 开源模型按年份 90% 分位参数量对数增长拟合 (稳健)
    ep_op = ep[ep["open_weights"]].copy()
    ep_op["params_B"] = pd.to_numeric(ep_op["Parameters"], errors="coerce")
    ep_op["pub"] = pd.to_datetime(ep_op["Publication date"], errors="coerce").dt.year
    ep_op = ep_op[ep_op["params_B"] > 0 & ep_op["pub"].notna()]
    g90 = ep_op.groupby("pub")["params_B"].quantile(0.9)
    gN = float(np.polyfit(g90.index, np.log(g90), 1)[0])
    gN_slow = gN * 0.5
    print(f"\nC4 开源模型参数量 lnN 年均增速: {gN:.3f} (放缓情景 {gN_slow:.3f})")
    res["gN"] = float(gN)

    # 前沿基准点: 用分位数前沿在最新年份(2025)的值 (对 2025 年样本不足/样本差异稳健)
    lnN_90 = float(dfm[dfm["year"] == 2025]["lnN"].quantile(0.9)) if 2025 in dfm["year"].values else float(dfm["lnN"].quantile(0.9))
    S_now = float(np.exp(c0 + bN * lnN_90 + bT * (2025 - 2022)))
    lnN_now = lnN_90
    print(f"前沿基准点(分位数前沿@2025): S={S_now:.2f}, lnN_90={lnN_90:.2f}")

    rng = np.random.default_rng(42)
    nboot = 800
    t_now = 2025
    horizons = [12, 24]
    pred_rows = []
    for h in horizons:
        t_h = t_now + h / 12.0
        for scen, gNsc in [("base", gN), ("slowdown", gN_slow)]:
            paths = []
            for _ in range(nboot):
                eps = rng.normal(0, 0.12)   # 前沿外推不确定性
                lnS = c0 + bN * (lnN_now + gNsc * h / 12.0) + bT * (t_h - 2022) + eps
                paths.append(np.exp(lnS))
            paths = np.array(paths)
            pred_rows.append({"horizon_months": h, "scenario": scen,
                              "year": t_h, "median": float(np.median(paths)),
                              "p10": float(np.percentile(paths, 10)),
                              "p90": float(np.percentile(paths, 90))})
    pred_df = pd.DataFrame(pred_rows)
    pred_df.to_csv(os.path.join(RES, "p4_prediction.csv"), index=False, encoding="utf-8-sig")
    print("\n前沿预测:")
    print(pred_df.to_string(index=False))
    res["prediction"] = pred_df.to_dict("records")
    # 分解口径: 每年前沿增速 = 规模贡献(bN*gN) + 非规模技术贡献(bT)
    g_front = bN * gN + bT
    scale_share = bN * gN / g_front if g_front > 0 else np.nan
    print(f"\n前沿年增速分解: 规模贡献={bN*gN:.4f} ({bN*gN/g_front*100:.1f}%), "
          f"非规模技术={bT:.4f} ({bT/g_front*100:.1f}%), 合计={g_front:.4f}")
    res["annual_decomp"] = {"scale": float(bN * gN), "tech": float(bT),
                            "total": float(g_front), "scale_share": float(scale_share)}

    # ---- C8 逐任务聚合 ----
    c8, n_bad = load_c8()
    print("\nC8 解析模型数:", len(c8), "跳过损坏:", n_bad)
    if len(c8):
        dims = list(DIM_GROUPS.values())
        c8 = c8.reindex(columns=c8.columns.union(dims))
        c8["agg"] = c8[dims].mean(axis=1, skipna=True)
        task_stats = c8[dims].describe().T[["mean", "std", "count"]].sort_values("mean", ascending=False)
        task_stats.to_csv(os.path.join(RES, "p4_c8_task_stats.csv"), encoding="utf-8-sig")
        print("\nC8 六维逐任务聚合 (按均值排序):")
        print(task_stats.to_string())
        # 与 C1 对照
        lb["norm"] = lb["Model"].astype(str).str.replace("/", "_", regex=False).str.lower()
        c8["norm"] = c8["model_dir"].astype(str).str.lower()
        m = c8.merge(lb[["norm", "Average ⬆️"]], on="norm", how="inner")
        if len(m) > 5:
            rho = m["agg"].corr(m["Average ⬆️"], method="spearman")
            print("C8 聚合 vs C1 Average Spearman:", round(rho, 4), "n=", len(m))
            res["c8"] = {"n": int(len(c8)), "n_bad": int(n_bad), "match_n": int(len(m)),
                         "spearman": float(rho)}
        else:
            res["c8"] = {"n": int(len(c8)), "n_bad": int(n_bad), "match_n": int(len(m))}

    with open(os.path.join(RES, "p4_results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    # ---- 图 ----
    # (a) 前沿 + 预测
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    all_years = sorted(set(hist_f.keys()) | set(fy["year"]))
    S_all = []
    for yy in all_years:
        if yy in hist_f:
            S_all.append(hist_f[yy])
        else:
            r = fy[fy["year"] == yy]
            S_all.append(r["S"].iloc[0] if len(r) else np.nan)
    ax.plot(all_years, S_all, "o-", color="#2563EB", lw=2, label="历史前沿 (C1 开源 + C3)")
    for s, p in pred_df.iterrows():
        color = "#10B981" if p["scenario"] == "base" else "#F59E0B"
        ax.plot([t_now, p["year"]], [S_all[-1], p["median"]], "--", color=color, lw=1.5,
                label=f"{p['scenario']} {int(p['horizon_months'])}M" if s % 2 == 0 else None)
        ax.errorbar(p["year"], p["median"], yerr=[[p["median"] - p["p10"]], [p["p90"] - p["median"]]],
                    fmt="s", color=color, capsize=3)
    ax.set_xlabel("年份"); ax.set_ylabel("开源模型前沿 Average")
    ax.set_title("开源大语言模型能力前沿与 12/24 个月预测")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p4_frontier.png"), dpi=200); plt.close(fig)

    # (b) 分解
    if len(decomp):
        fig, ax = plt.subplots(figsize=(8.5, 5))
        d = decomp.dropna(subset=["scale_share"])
        ax.bar(d["year"], d["growth"], label="总增长", color="#2563EB", alpha=0.45)
        ax.bar(d["year"], d["scale"], label="规模贡献", color="#10B981")
        ax.bar(d["year"], d["non_scale"], bottom=d["scale"], label="非规模技术贡献", color="#F59E0B")
        ax.axhline(0, color="gray", lw=0.8)
        ax.set_ylabel("对数能力增长"); ax.set_title("前沿能力增长分解: 规模 vs 非规模技术")
        ax.legend()
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "p4_decomposition.png"), dpi=200); plt.close(fig)

    # (c) 桥接
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.scatter(br["Val_Loss"], br["LB_Average"], c="#2563EB", s=14, alpha=0.7)
    xs = np.linspace(br["Val_Loss"].min(), br["Val_Loss"].max(), 100)
    ax.plot(xs, loss_to_avg(xs), "r-", lw=2, label="桥接映射")
    ax.set_xlabel("验证 Loss"); ax.set_ylabel("Benchmark 平均分")
    ax.set_title(f"Loss-Benchmark 桥接 (C6, R2={r2b:.3f})")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "p4_bridge.png"), dpi=200); plt.close(fig)

    # (d) C8 任务聚合
    if len(c8):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ts_top = task_stats.head(6)
        ax.barh(ts_top.index[::-1], ts_top["mean"][::-1], color="#7C3AED", alpha=0.85)
        ax.set_xlabel("平均 acc"); ax.set_title("C8 逐任务聚合 (6 维)")
        fig.tight_layout(); fig.savefig(os.path.join(FIG, "p4_c8_tasks.png"), dpi=200); plt.close(fig)

    print("\ndone p4")


if __name__ == "__main__":
    main()
