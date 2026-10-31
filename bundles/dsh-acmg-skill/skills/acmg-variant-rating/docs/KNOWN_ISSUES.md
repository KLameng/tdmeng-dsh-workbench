# 已知问题台账（KNOWN_ISSUES）

> 记录已确认的缺陷/未决项。登记过的 P0 问题必须先在此留痕，再谈发布。

## 缺陷登记格式

```
- 编号：KI-<N>
- 状态：open / fixed / verified / 撤案
- 严重度：P0（阻塞发布）/ P1 / P2
- 位置：<文件/模块>
- 描述：<问题现象与影响>
- 修复方向：<建议>
```

## 当前台账

| 编号 | 状态 | 严重度 | 位置 | 描述 |
|---|---|---|---|---|
| KI-1 | **fixed（2026-10-22 已同步并验证）** | P0 | `v27_eval\_review_v27\scripts\acmg_combine.py`（评估副本） | 已同步为 v20261022a（含 1VS+1SU→LP）。关键组合实测：1VS+1SU→LP / 1VS+2SU(两码)→P / 1VS+1MO→LP / 1VS+1MO+1SU→P / 1VS→VUS 全正确。可安全重跑评测 |
| KI-2 | verified | — | 引擎 `acmg_combine.py` | P0-1 1VS+1SU→LP 已采纳落地（v20261022a），12 条受影响位点 engineA 全对齐 methodA=LP |
| KI-3 | 撤案 | — | 评测脚本 | P0-3"官方短路评测口径"核实撤案：`combination_eval.py`/`regression_gate.py`/`contract_test.py` 本就走 `combine()`（含官方短路），官方短路正常工作 |
| KI-4 | 定案 | — | 口径 | P0-2 争议证据码口径定案"如实"：金标准固定确信、评级/归档如实展示、争议证据码原样保留、分歧作能力诊断信号（非缺陷） |

> 新确认的 P0 必须先登记到本表，再谈修复与发布。
