# -*- coding: utf-8 -*-
"""
v11 实验: 问题四前沿预测的机器学习对比
用 (lnN, t) 预测 lnS / 前沿分, 机器学习家族 (GBDT/随机森林/KNN/线性) vs
分位数回归基线, 做滚动时间外推 (train<=2024.5, test>2024.5) 比较 RMSE,
并比较 12 个月末前沿预测 (分位数回归 vs GBDT 残差法).
回答: 前沿外推该用统计回归还是机器学习? 线性可解释 vs 非线性拟合的外推性.
输出: experiments/v11_p4_ml.csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import C, RES, FIG, BASE
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import RobustScaler

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)


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
    return dfm


def main():
    dfm = load_frontier()
    X = dfm[["lnN", "t"]].to_numpy()
    y = dfm["lnS"].to_numpy()
    cut = 2.5  # 2024.5
    tr, te = dfm["t"] < cut, dfm["t"] >= cut
    print("train n=", tr.sum(), "test n=", te.sum(), " (断点=2024.5)")

    models = {
        "qreg90": None,  # 特殊处理
        "linear": LinearRegression(),
        "gbr": GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0),
        "rf": RandomForestRegressor(n_estimators=200, max_depth=6, random_state=0),
        "knn": KNeighborsRegressor(n_neighbors=30, weights="distance"),
    }
    rows = []
    Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]
    for name in ["linear", "gbr", "rf", "knn"]:
        m = models[name].fit(Xtr, ytr)
        yh = m.predict(Xte)
        rmse = float(np.sqrt(np.mean((yh - yte) ** 2)))
        # 时间外推指标: 只比较测试集 (前沿分位数) 的尾端误差
        rows.append({"model": name, "rmse": rmse,
                     "p90_abs_err": float(np.percentile(np.abs(yh - yte), 90))})
        print(f"{name}: 外推RMSE={rmse:.4f} P90残差={np.percentile(np.abs(yh - yte), 90):.4f}")

    # 分位数回归 (LP) 基线: 用训练段拟合, 测试段验证
    from scipy.optimize import linprog
    def qr_fit(Xa, ya, tau=0.9):
        n, m = Xa.shape
        Xa = np.column_stack([np.ones(n), Xa])
        c = np.concatenate([np.zeros(m + 1), tau * np.ones(n), (1 - tau) * np.ones(n)])
        Aeq = np.hstack([Xa, np.eye(n), -np.eye(n)])
        res = linprog(c, A_eq=Aeq, b_eq=ya, bounds=[(None, None)] * (m + 1) + [(0, None)] * (2 * n),
                      method="highs")
        return res.x[: m + 1]
    bt = qr_fit(Xtr, ytr, 0.9)
    Xte1 = np.column_stack([np.ones(len(yte)), Xte])
    yh = Xte1 @ bt
    rmse_q = float(np.sqrt(np.mean((yh - yte) ** 2)))
    rows.append({"model": "qreg90_LP", "rmse": rmse_q, "p90_abs_err": float(np.percentile(np.abs(yh - yte), 90))})
    print(f"qreg90_LP: 外推RMSE={rmse_q:.4f} P90残差={np.percentile(np.abs(yh - yte), 90):.4f}")

    abl = pd.DataFrame(rows)
    abl.to_csv(os.path.join(EX, "v11_p4_ml.csv"), index=False, encoding="utf-8-sig")

    # 12 个月前沿预测对比 (以 2025 起预测 2026): 各模型前沿分 (90分位)
    print("\n12 个月前沿预测对比 (2026.0, 基础情景):")
    fut = pd.DataFrame({"lnN": [14.7 * (1.251 / 1.0) ** 0], "t": [4.0]})
    # 分位数回归预测
    lnS_qr = bt[0] + bt[1] * np.log(14.7) + bt[2] * 2.0  # 2025(对数增速1.251年/1) -> t=4
    # 更规范: 由 t=3 (2025) 的90分位 N 起步, 12个月后 lnN += gN
    lnN0 = np.log(14.7)
    lnS_qr2 = bt[0] + bt[1] * (lnN0 + 1.251 * 1.0) + bt[2] * 4.0
    print("QR: 2026 前沿(ln)=", round(lnS_qr2, 4), " S=", round(np.exp(lnS_qr2), 1))
    for name in ["linear", "gbr", "rf", "knn"]:
        m = models[name]
        pred = m.predict(np.array([[lnN0 + 1.251 * 1.0, 4.0]]))[0]
        print(f"{name}: 2026 前沿(ln)={pred:.4f} S={np.exp(pred):.1f}")
    print("\ndone v11")


if __name__ == "__main__":
    main()