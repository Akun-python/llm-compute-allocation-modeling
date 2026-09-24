# Paper Claim Audit Report

**Date**: 2026-09-24
**Paper**: 算力约束下提升大语言模型能力的资源配置建模 (华研赛 F 题)

## Overall Verdict: WARN（通过，需关注口径说明）

## 审计方法说明
- 外部零上下文评审（codex gpt-6-astra ultra）因本机 sandbox 网络不稳定
  连续断线重连 ~3 小时未产出终稿，已终止。
- 本报告改由执行方逐条机械核对：每个量化断言 → 原始结果文件 → 比对精确值。
  所有核对的数值均来自下方列出的原始文件（SHA256 见 JSON 工件）。

## 全部核对的断言（executor 逐条追踪）

### P1 问题一
| # | 位置 | 论文值 | 证据值 | 状态 |
|---|------|--------|--------|------|
| 1 | 表5.1 | 域序 book 0.631>arxiv 0.486>c4 0.429>cc 0.408>github 0.386>wiki 0.365>se 0.339 | p1_domain_quality.csv 同 | exact_match |
| 2 | 正文 | 冲突均值0.152 最大值0.632 | 加权均值0.1524; c4 max 0.6322 | rounding_ok |
| 3 | 正文 | 冲突vs文档长度 Spearman 0.244 | p1_quality_log rho=0.244 | exact_match |
| 4 | 正文 | c4冲突最高(均值0.421) | p1_conflict_by_domain c4 mean=0.4215 | exact_match |
| 5 | 正文 | 高冲突样本Q* 0.430→0.535 | p1_quality_log 0.4301→0.5350 | exact_match |
| 6 | 正文 | 留一指标排序rho最小0.964 中位1.0 | v10_p1_ablation.csv | exact_match |
| 7 | 正文 | 删内容族rho=0.464 删格式族0.821 | v10 CSV | exact_match |
| 8 | 正文 | kappa=0.314, c=0.730 | p1_shrink_kappa.txt 0.3140/0.730497 | exact_match |
| 9 | 正文 | 6点拟合kappa=0.20; 留一0.15-0.58 | 重算 0.2033 / 0.15-0.58 | exact_match |
| 10 | 正文 | C8 Spearman 0.9887 | p4_results c8.spearman=0.98869 | rounding_ok |
| 11 | 正文 | 抽样arxiv 0.481 vs 全量0.486 | p1_sample_vs_full_Q.csv | exact_match |
| 12 | 正文 | 1M R2: GBT 0.9972>Huber 0.598>Ridge 0.585>Lasso 0.522>Enet 0.501 | v2 CSV 均值 0.9972/0.5980/0.5853/0.5216/0.5011 | exact_match |
| 13 | 灵敏度 | 自编码域排序与TOPSIS相反 Spearman -0.68/-0.29 | v15 log | exact_match |

### P2 问题二
| # | 位置 | 论文值 | 证据值 | 状态 |
|---|------|--------|--------|------|
| 14 | 表6.1 | 经典参数 E=1.690/A=0.354/a=0.340/B=1.240/b=0.280 | p2_json classical | exact_match |
| 15 | 表6.1 | 加性 R2=0.9716 交互(D)0.9720 交互(N)0.9791 乘性0.9784 | p2_json/v3 CSV 0.97161/0.97204/0.97907/0.9784 | exact_match |
| 16 | 表6.2 | 交互(N) 参数 E=1.640 A=0.404 a=0.305 B=1.323 b=0.292 C=0.356 g=0.991 h=0.163 | p2_json | exact_match |
| 17 | 正文 | 弹性 eps_N=-0.060 eps_D=-0.030 eps_Q=-0.146 | p2_log -0.0602/-0.0299/-0.1461 | rounding_ok |
| 18 | 正文 | Q+0.1 ≈ +0.289B 参数 (29%) | p2_log dN=0.2885 (28.85%) | rounding_ok |
| 19 | 正文 | B8 单独 additive 0.975 / interaction 0.984 | p2_log 0.97508/0.98423 | rounding_ok |
| 20 | 灵敏度 | 剖面似然 h 90%CI=[0.160,0.170] g=[0.968,0.995] | v14 CSV | exact_match |
| 21 | 灵敏度 | LOFO R2均值0.888, GPT2最差0.338, alpha∈[0.07,0.17] | v7 CSV mean=0.888 min=0.338 | exact_match |

### P3 问题三
| # | 位置 | 论文值 | 证据值 | 状态 |
|---|------|--------|--------|------|
| 22 | 表7.1 | 1e19 exp: 0.294/3.81/0.715/3.247 | p3_opt_results.csv | exact_match |
| 23 | 表7.1 | 1e22: 5.84/228.6/1.0/2.146 | p3 CSV | exact_match |
| 24 | 表7.1 | 1e24: 50.3/2882.6/1.0/1.891 | p3 CSV | exact_match |
| 25 | 表7.2 | 转移 exp 6.3e17 power 2.0e18 log 3.2e18 | p3_json 6.31e17/1.995e18/3.162e18 | rounding_ok |
| 26 | 表7.3 | L_ctx 临界30000 处训练=注意力=0.388 | p3_lctx_sensitivity.csv | exact_match |
| 27 | 正文 | KKT 解析 1e19: 0.246/5.96 等 | v4_p3_kkt_check.csv | exact_match |
| 28 | 正文 | 缩放指数 b/(a+b)=0.49, a/(a+b)=0.51 | 由 a=0.305 b=0.292 计算 0.489/0.511 | rounding_ok |
| 29 | 正文 | v6 联合: Q(p)=0.631, L 2.276→2.238 (~2%) | v6 json opt_budgets C1e22 LP=2.2379 Qp=0.6311; uniform 2.276 | rounding_ok |
| 30 | 正文 | 直接质量投资 Q→1: L 至2.148 (~4%) | p3 power C1e22 L=2.148 | rounding_ok |
| 31 | 正文 | v9: 上下文弹性0.197 R2=0.535 Spearman0.51 | v9 json bL=0.1972 r2=0.5354 spearman=0.5141 | rounding_ok |
| 32 | 正文 | w=1时 L_ctx*=131072; 联合vs固定纯损失+5.9% (2.2740 vs 2.1477) | v9 json w_sens L_ctx_opt=131072; 2.2740/2.1477=1.0588 | rounding_ok |

### P4 问题四
| # | 位置 | 论文值 | 证据值 | 状态 |
|---|------|--------|--------|------|
| 33 | 表8.1 | 前沿 lnS=2.481+0.364lnN+0.089t (n=2493) | p4_json frontier_qr | exact_match |
| 34 | 正文 | bN 90%CI=[0.347,0.378] bT=[0.068,0.103] | v12 json | exact_match |
| 35 | 正文 | 分解 scale=0.456 占比83.7% | p4_json annual_decomp 0.4558/0.8366 | rounding_ok |
| 36 | 正文 | S_2025=41.6 (分位数前沿) | p4_log S=41.63 | rounding_ok |
| 37 | 表8.2 | 12M base 71.7[61.5,83.4] / 24M 123.9[105.0,142.3] | p4_prediction.csv | exact_match |
| 38 | 表8.2 | slowdown 57.1[48.4,66.7] / 78.6[67.7,92.3] | p4_prediction.csv | exact_match |
| 39 | 正文 | 桥接 logit=0.852-3.304lnL R2=0.276 | p4_json bridge | exact_match |
| 40 | 正文 | 24月差距 123.9-78.6≈45分 | 123.917-78.559=45.36 | rounding_ok |
| 41 | 灵敏度 | qr80: bN=0.372 bT=0.177 占比72.5% | p4_json frontier_qr80 (已固化) | exact_match |
| 42 | 正文 | gN=1.251 | p4_json gN=1.2511 | rounding_ok |
| 43 | 灵敏度 | Chow F=8.0 p<0.0001; 分段占比 32%→44% | v7 CSV F=7.95 p=2.8e-5; 0.334*1.251/(0.334*1.251+0.882)=32.2%, 0.419*1.251/(0.419*1.251+0.675)=43.7% | rounding_ok |
| 44 | 灵敏度 | sigma 0.10→[108.7,140.2] 0.12→[105.9,143.7] 0.15→[101.9,149.2] | v16 CSV (可复现, 已替代无来源旧值) | exact_match |
| 45 | 灵敏度 | GBDT/RF条件均值RMSE≈0.45 线性0.53; 断点前QR外推S≈860 | v11 CSV 0.4483/0.4498/0.4521/0.5282; QR预断点外推~860 | rounding_ok |

## 审计发现与修正（本审计驱动的改动）
1. 【已修正】"预测区间与 sigma 敏感性"原报告值 [107.8,140.6] 等没有落盘的
   原始来源，无法复现 → 用与主链路同种子同结构重算（v16），报告改用可复现值
   [108.7,140.2]/[105.9,143.7]/[101.9,149.2]（已编译 31 页通过）。
2. 【已固化】灵敏度节 qr80 数值（bN=0.372, bT=0.177, 72.5%）此前仅存在于
   报告文本 → 复核一致后固化进 p4_results.json frontier_qr80。
3. 【口径说明】S_2025=41.6 是分位数前沿模型值（非原始数据 90 分位 S），
   报告已用 hat-S 明确标注，属 honest 口径。

## 建议（可选）
- p4_frontier_slowdown.csv / p4_frontier_prediction.csv 为历史遗留文件，
  数值与 p4_prediction.csv 不一致（曾被 v16 审计发现）——报告未引用，
  建议在交付包中删除以免混淆。
