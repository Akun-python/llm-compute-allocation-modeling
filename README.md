# llm-compute-allocation-modeling

**算力约束下提升大语言模型能力的资源配置建模** —— 2026 年中国研究生数学建模竞赛（华为杯）F 题完整建模方案。

Mathematical modeling solution for Huawei Cup 2026 China Postgraduate Mathematical Modeling Contest, Problem F: *resource allocation modeling for improving large language model capabilities under compute constraints*.

## 问题主线

四问构成一条递进主线，前一问的输出是后一问的输入：

- **问题一 · 数据质量与领域配比**：基于 22 维质量信号构建数据质量综合评价模型（含指标方向统一与质量冲突消解），并建立 17 领域配比 $p$ 与交叉熵损失之间的定量关系。
- **问题二 · 广义标度律**：将数据质量 $Q$ 与领域配比 $p$ 纳入经典标度律 $L(N,D)=E+AN^{-\alpha}+BD^{-\beta}$，建立同时包含 $N,D,Q,p$ 的广义标度律，完成弹性分析与"质量-规模"可替代性条件推导、参数估计与验证。
- **问题三 · 算力约束下的资源联合优化**：在算力预算 $C\in\{10^{19},10^{22},10^{24}\}$ FLOPs 下联合优化参数量 $N$、数据量 $D$、领域配比 $p$、数据质量 $Q$，计入训练开销 $C_{train}=6ND$、质量提升开销 $C_Q=D[g(Q)-g(Q_0)]_+$、长文本注意力开销 $C_{attn}=\eta N D L_{ctx}$，分析预算跨量级时的结构性转移与临界上下文长度 $L_{ctx}^{crit}=6/\eta$。
- **问题四 · 技术演进与前沿预测**：将开源大模型能力增长分解为规模扩张与非规模技术进步两部分贡献，建立 Loss–Benchmark 桥接映射，预测未来 12–24 个月开源大模型能力前沿并给出不确定性分析。

## 仓库结构

```
main.tex                  # 论文主文件（XeLaTeX + gmcmthesis 模板）
sections/                 # 各章节 LaTeX 源码（问题重述 → 评价）
figures/                  # 插图
solve/                    # 求解代码与结果
real_attachments/         # 赛题原始数据（体积过大，已 gitignore，不随仓库分发）
```

## 编译

```bash
xelatex main.tex          # 或 latexmk -xelatex main.tex
```

## 数据说明

- `real_attachments/`（约 700 MB 赛题数据）已被 `.gitignore` 排除，如需复现请从赛题附件获取。
- `solve/results/p1_quality_all.csv`（约 145 MB）超过 GitHub 单文件上限，已移出版本控制，可由 `solve/` 下的代码重新生成。
