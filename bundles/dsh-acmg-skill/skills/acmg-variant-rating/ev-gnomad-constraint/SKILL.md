---
name: ev-gnomad-constraint
version: 1.0.0
description: 查询gnomAD/ExAC基因约束指标（missense Z-score、pLI、LOEUF、o/e ratio、ExAC区域missense约束），支持v2.1.1和v4.0版本。当用户需要查missense Z-score、mis_z、pLI、LOEUF、gnomAD constraint、gnomAD约束分数、ExAC regional missense constraint、PP2/BP2评估所需的mis_z值、基因对功能变异的耐受程度、基因constraint metrics时使用。
---

# gnomAD 约束指标查询

通过下载 gnomAD 官方 GCS 公共存储桶的 TSV 文件，查询基因的约束指标。无需 API 认证，数据与 gnomAD 浏览器同源。

## 数据来源与覆盖

| 数据集 | 版本 | 关键指标 | 适用场景 |
|--------|------|---------|---------|
| gnomAD v4.0 | MANE Select 转录本 | mis.z_score, lof.pLI, lof.oe_ci.upper (LOEUF), mis.oe | 最新约束数据，推荐首选 |
| gnomAD v2.1.1 | canonical 转录本 | mis_z, pLI, oe_lof_upper (LOEUF), oe_mis | 历史对照，部分文献引用此版本 |
| ExAC RMC | 区域级 | obs_exp, region_name, chisq_diff_null | 仅 2701 个基因有数据，用于评估特定区域约束 |

## 使用方式

运行 `query_constraint.py`，传入基因符号：

```bash
# 查询全部三个数据集
python query_constraint.py COL4A4

# 仅查询 gnomAD v4.0
python query_constraint.py COL4A4 --v4

# 仅查询 gnomAD v2.1.1
python query_constraint.py COL4A4 --v2

# 仅查询 ExAC 区域约束
python query_constraint.py COL4A4 --exac-rmc
```

## 结果解读要点

### missense Z-score (mis_z / mis.z_score)
- **≥ 3.09**：基因对 missense 变异有显著约束，可用于 ACMG PP2
- **< 3.09**：不满足 PP2 条件
- v2 和 v4 的 Z-score 可能不同（样本量差异），以评估时选用的版本为准

### pLI (Probability of Loss-of-function Intolerance)
- **≥ 0.9**：高度 intolerant to LOF
- **0.1–0.9**：中等
- **< 0.1**：tolerant

### LOEUF (Loss-of-function Observed/Expected Upper confidence interval)
- 即 `lof.oe_ci.upper` (v4) 或 `oe_lof_upper` (v2)
- **越低越 intolerant**，通常 < 0.35 为高度约束

### ExAC Regional Missense Constraint
- 仅 2701 个基因有此数据，大多数基因查不到
- obs_exp < 0.6 表示该区域对 missense 变异高度约束
- 若基因不在数据集中，不能以此作为不支持 PM1 的证据

## 注意事项

- 数据直接从 gnomAD 官方 GCS 下载，与浏览器展示同源
- v4 TSV 约 30MB，v2 bgz 约 15MB，首次查询需下载完整文件
- 若查询失败（网络超时等），可重试或使用 `--v4` / `--v2` 单独查询某个数据集
- 脚本仅依赖 Python 标准库，无需额外安装
