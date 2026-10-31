# arad-inheritance-judgment CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.0.4

- （全修 arad P0-1，2026-10-23）ClinVar 泛基因查询回退时未筛目标变异：esearch `GJB2[gene] AND "c.35delG"` 返回 30 条 GJB2 泛集合，目标变异（如 ClinVar 收录为 c.35del 的 VCV000017004）在列但未标注 target。新增本地目标变异匹配（_arad_variant_matches，cDNA 位置+类型 / 蛋白归一化，兼容 ClinVar 省略碱基写法 c.35delG↔c.35del），每条 ClinVar 证据加 `target_match` 标注，返回加 `target_evidence`（命中的目标变异记录，如 GJB2 c.35delG → VCV000017004 Pathogenic）。
- zygosity 职责不变：ClinVar 路径仍不暴露患者基因型（NCBI API 现实），zygosity 由 PubMed 路径（extract_zygosity_from_text）承担；GJB2 c.35delG 的 PubMed 路径实测返回 homozygous/heterozygous/compound_heterozygous 权威证据（PMID 33333757 等）。

## v1.0.3

- ClinVar 查询路径修复：NCBI efetch db=clinvar 返回已从 ClinVarSet/Measure/Trait XML 变更为 IdList，旧解析全部失效（found=false 空转）。迁移到 esummary JSON（title/accession/germline_classification/trait/protein_change），修复 FGFR3 c.1138G>A 等命中却解析为空的问题。
- 基因型（zygosity）判定职责明确：ClinVar 当前 API 不再暴露患者基因型，zygosity 由 PubMed 文献路径（extract_zygosity_from_text + search_pubmed）承担。
- SKILL.md 文档同步：步骤1 与输出模板中 ClinVar 证据行由"提取 zygosity"改为"提取 classification/traits（致病性+关联疾病）"，明确 zygosity 由步骤2 PubMed 提供；与 esummary 代码返回字段（clinvar_id/accession/variant/protein_change/classification/traits/clinvar_url）对齐。

## v1.0.2

- AR/AD 遗传模式判定：查 ClinVar/PubMed 患者报道，按遗传方式与 LOF 机制推断 AD/AR/多模式。
