# -*- coding: utf-8 -*-
"""
v82 实验: 前沿预测趋势模型的历史回测对比 (out-of-sample)
在 v18 同一窗口集上, 对 0.9 分位数回归目标 (pinball) 比较四种趋势形式:
  1) lin  : lnS = c0 + bN lnN + bT t            (主链路线性外推)
  2) quad : lnS = c0 + bN lnN + bT1 t + bT2 t^2 (二次加速/减速)
  3) sat  : lnS = c0 + bN lnN + g (1 - e^{-l t}) (饱和渐近)
  4) naive: 前沿 S 停在 y0 的数据 90 分位 (零增长基线)
预测口径同 v18: lnN 按 gN=1.251/年增长锚定; 对照目标年数据 90 分位 S.
输出: experiments/v82_p4_forecast_models.csv/.json
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C
from scipy.optimize import minimize, linprog

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)
TAU = 0.9


def load_frontier():
    lb = pd.read_csv(os.path.join(C, "leaderboard_cleaned.csv"))
    lb["date"] = pd.to_datetime(lb["Submission Date"], errors="coerce")
    lb["year"] = lb["date"].dt.year
    lb = lb[lb["year"].notna()]
    lic = lb["Hub License"].fillna("").astype(str).str.contains(
        "apache|mit|bsd|cc-by|llama|gemma|open", case=False, na=False)
    dfm = lb[lic & (lb["#Params (B)"] > 0) & (lb["Average ⬆️"] > 0)].copy()
    dfm = dfm[dfm["year"] >= 2022]
    dfm["lnS"] = np.log(dfm["Average ⬆️"])
    dfm["lnN"] = np.log(dfm["#Params (B)"])
    dfm["t"] = dfm["year"] - 2022.0
    ts = pd.read_csv(os.path.join(C, "leaderboard_extended_timeseries.csv"))
    hist = []
    for yy in [2022, 2023]:
        g = ts[(ts["Year"] == yy) & (ts["Average"] > 0)]
        if len(g):
            g = g.sort_values("Average", ascending=False).head(6)
            for _, r in g.iterrows():
                hist.append({"lnS": np.log(r["Average"]), "lnN": np.log(r["Params_B"]),
                             "t": yy - 2022.0, "year": yy})
    if hist:
        dfm = pd.concat([dfm, pd.DataFrame(hist)], ignore_index=True)
    return dfm


def pinball(y, yhat):
    d = y - yhat
    return np.mean(np.where(d >= 0, TAU * d, (TAU - 1) * d))


def fit_pinball(X, y, trend, p0):
    """最小化 pinball 损失 (L-BFGS-B); trend in {lin,quad,sat}"""
    def obj(theta):
        return pinball(y, X @ theta[:2] + trend(theta[2:]))
    res = minimize(obj, p0, method="L-BFGS-B")
    return res.x


def main():
    dfm = load_frontier()
    gN = 1.251125395176952
    lnN1 = dfm["lnN"].to_numpy()
    rows = []
    for y_target in [2024, 2025]:
        for y0 in [2022, 2023, 2024]:
            if y0 >= y_target:
                continue
            tr = dfm[dfm["year"] <= y0]
            if len(tr) < 12 or tr["year"].max() != y0:
                continue
            t = tr["t"].to_numpy()
            y = tr["lnS"].to_numpy()
            lnN = tr["lnN"].to_numpy()
            X0 = np.column_stack([np.ones(len(tr)), lnN])
            tgt = y_target - 2022.0
            lnN_anchor = tr[tr["year"] == y0]["lnN"].quantile(0.9)
            lnN_f = lnN_anchor + gN * (y_target - y0)

            # lin: QR-LP (同主链路)
            Xl = np.column_stack([X0, t])
            n, m = Xl.shape
            c = np.concatenate([np.zeros(m), TAU * np.ones(n), (1 - TAU) * np.ones(n)])
            Aeq = np.hstack([Xl, np.eye(n), -np.eye(n)])
            r = linprog(c, A_eq=Aeq, b_eq=y, bounds=[(None, None)] * m + [(0, None)] * (2 * n), method="highs")
            bl = r.x[:m]
            S_lin = float(np.exp(bl[0] + bl[1] * lnN_f + bl[2] * tgt))

            # quad: lnS = c0 + bN lnN + bT1 t + bT2 t^2
            bq = fit_pinball(X0, y, lambda q: q[0] * tgt + q[1] * tgt ** 2,
                             np.array([1.5, 0.3, 0.05, 0.0]))
            S_quad = float(np.exp(bq[0] + bq[1] * lnN_f + bq[2] * tgt + bq[3] * tgt ** 2))

            # sat: g(1 - e^{-l t})
            def sat_trend(th):
                g, l = th
                return g * (1 - np.exp(-l * tgt))
            bs = fit_pinball(X0, y, sat_trend, np.array([1.5, 0.3, 1.5, 0.4]))
            S_sat = float(np.exp(bs[0] + bs[1] * lnN_f + bs[2] * (1 - np.exp(-bs[3] * tgt))))

            # naive: 停在 y0 数据 90 分位
            S_naive = float(np.exp(tr["lnS"].quantile(0.9)))

            tt = dfm[dfm["year"] == y_target]
            S_data = float(np.exp(tt["lnS"].quantile(0.9))) if len(tt) else np.nan
            rows.append({"y0": y0, "y_target": y_target, "n_train": len(tr),
                         "S_lin": round(S_lin, 1), "S_quad": round(S_quad, 1),
                         "S_sat": round(S_sat, 1), "S_naive": round(S_naive, 1),
                         "S_data90": round(S_data, 1),
                         "err_lin": round((S_lin - S_data) / S_data, 3),
                         "err_quad": round((S_quad - S_data) / S_data, 3),
                         "err_sat": round((S_sat - S_data) / S_data, 3),
                         "err_naive": round((S_naive - S_data) / S_data, 3)})
            print(f"y0={y0}->{y_target}: data={S_data:.1f} | lin={S_lin:.1f} "
                  f"({(S_lin-S_data)/S_data*100:+.0f}%) quad={S_quad:.1f} "
                  f"({(S_quad-S_data)/S_data*100:+.0f}%) sat={S_sat:.1f} "
                  f"({(S_sat-S_data)/S_data*100:+.0f}%) naive={S_naive:.1f} "
                  f"({(S_naive-S_data)/S_data*100:+.0f}%)")

    rdf = pd.DataFrame(rows)
    rdf.to_csv(os.path.join(EX, "v82_p4_forecast_models.csv"), index=False, encoding="utf-8-sig")
    agg = {}
    for k in ["err_lin", "err_quad", "err_sat", "err_naive"]:
        e = np.abs(rdf[k].to_numpy())
        agg[k] = {"mape": float(np.mean(e) * 100), "max_abs": float(np.max(e) * 100)}
    # 符号偏差: 系统性高估率
    for k in ["err_lin", "err_quad", "err_sat", "err_naive"]:
        agg[k]["over_frac"] = float((rdf[k] > 0).mean())

    # ---- 第二阶段: 全样本(2022-2025)各趋势形式的 12/24 个月投影 ----
    y = dfm["lnS"].to_numpy(); lnN = dfm["lnN"].to_numpy(); t = dfm["t"].to_numpy()
    X0 = np.column_stack([np.ones(len(dfm)), lnN])
    lnN_anchor = dfm[dfm["year"] == 2025]["lnN"].quantile(0.9)
    proj = {}
    for h, tg in [("12m", 4.0), ("24m", 5.0)]:
        lnN_f = lnN_anchor + gN * (tg - 3.0)
        # lin (全样本 QR-LP, 同主链路)
        Xl = np.column_stack([X0, t])
        n, m = Xl.shape
        c = np.concatenate([np.zeros(m), TAU * np.ones(n), (1 - TAU) * np.ones(n)])
        Aeq = np.hstack([Xl, np.eye(n), -np.eye(n)])
        r = linprog(c, A_eq=Aeq, b_eq=y, bounds=[(None, None)] * m + [(0, None)] * (2 * n), method="highs")
        bl = r.x[:m]
        S_lin = float(np.exp(bl[0] + bl[1] * lnN_f + bl[2] * tg))
        # quad
        bq = fit_pinball(X0, y, lambda q: q[0] * tg + q[1] * tg ** 2,
                         np.array([1.5, 0.3, 0.05, 0.0]))
        S_quad = float(np.exp(bq[0] + bq[1] * lnN_f + bq[2] * tg + bq[3] * tg ** 2))
        # sat
        def sat_trend2(th):
            gg, ll = th
            return gg * (1 - np.exp(-ll * tg))
        bs = fit_pinball(X0, y, sat_trend2, np.array([1.5, 0.3, 1.5, 0.4]))
        S_sat = float(np.exp(bs[0] + bs[1] * lnN_f + bs[2] * (1 - np.exp(-bs[3] * tg))))
        proj[h] = {"lin": round(S_lin, 1), "quad": round(S_quad, 1), "sat": round(S_sat, 1)}
        print(f"全样本投影 {h} (t={tg}): lin={S_lin:.1f} quad={S_quad:.1f} sat={S_sat:.1f}")
    json.dump({"windows": len(rdf), "agg": agg, "full_proj": proj},
              open(os.path.join(EX, "v82_p4_forecast_models.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\nMAPE(%): ", {k: round(v["mape"], 1) for k, v in agg.items()})
    print("done v82")


if __name__ == "__main__":
    main()
