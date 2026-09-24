# -*- coding: utf-8 -*-
"""
v16 实验: 前沿外推噪声 sigma 敏感性 (可复现口径)
用与主链路完全一致的预测结构 (c0/bN/bT 取自 p4_results.json, lnN_90=2025年
0.9分位, gN=1.2511, nboot=800, seed=42, eps~N(0,sigma)), 对 sigma 0.10/0.12/0.15
生成 24 个月基础情景区间, 固化为 CSV 供报告引用.
输出: experiments/v16_p4_sigma.csv
"""
import os, sys, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
from common import RES

EX = os.path.join(os.path.dirname(__file__))
os.makedirs(EX, exist_ok=True)


def main():
    p4 = json.load(open(os.path.join(RES, "p4_results.json"), encoding="utf-8"))
    c0, bN, bT = (p4["frontier_qr"][k] for k in ["c0", "bN", "bT"])
    gN = p4["gN"]
    lnN_now = 2.69  # 2025 年 0.9 分位 (p4_log)
    t_h = 2027.0

    rows = []
    for sigma in [0.10, 0.12, 0.15]:
        rng = np.random.default_rng(42)
        paths = np.empty(800)
        for i in range(800):
            eps = rng.normal(0, sigma)
            lnS = c0 + bN * (lnN_now + gN * 2.0) + bT * (t_h - 2022) + eps
            paths[i] = np.exp(lnS)
        rows.append({"sigma": sigma, "median": float(np.median(paths)),
                     "p10": float(np.percentile(paths, 10)),
                     "p90": float(np.percentile(paths, 90)),
                     "nboot": 800, "seed": 42})
        print(f"sigma={sigma}: median={np.median(paths):.1f} "
              f"[p10={np.percentile(paths,10):.1f}, p90={np.percentile(paths,90):.1f}]")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(EX, "v16_p4_sigma.csv"), index=False, encoding="utf-8-sig")
    print("saved v16_p4_sigma.csv")


if __name__ == "__main__":
    main()