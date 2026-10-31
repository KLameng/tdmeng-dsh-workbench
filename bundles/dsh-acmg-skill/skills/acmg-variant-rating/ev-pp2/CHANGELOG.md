# ev-pp2 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.1.0

- 新增基因特异性不适用清单——存在大量良性错义多态的基因（如 F7 的 rs6046 p.Arg413Gln、p.Arg353Gln 等凝血因子基因）PP2 不适用；F8 在 ClinGen Coagulation Factor Deficiency VCEP 中 PP2 明确 Not Applicable。

## v1.2.0

- 新增官方 mis_z 取数通道——配套 query_constraint.py 直连 gnomAD 官方 GCS 存储桶查询 v4/v2 missense Z-score，附 F7 实测判例（v4=0.361 / v2=0.320，均<3.09 → PP2 不适用）。

## v1.2.2

- 补跨技能引用声明——凡本技能判定依赖文献检索/核验时，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」与按用途差异化提取；本技能 description 显式声明该跨技能依赖，不再隐式引用。

## v1.2.3（全局维护收敛整改）

- 可疑文献判定完整标准（L1/L2/L3 分级 + 挂载默认可疑 + 强制上报）收敛到唯一权威 `ev-variant-literature-patient`，本技能仅保留按用途定制提取要求，不再内嵌重复完整段。
