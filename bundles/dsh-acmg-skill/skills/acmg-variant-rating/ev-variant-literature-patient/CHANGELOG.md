# ev-variant-literature-patient CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.7.0

- **新增 HGMD 可选配置闸门（不静默，2026-10-23）**：HGMD 为商业库、不随包分发；缺配置时不再只返回截断 error，新增可识别状态 `missing_config`（提示「HGMD 数据缺失」+ 前往配置指引，走 ClinVar/文献检索通道、不静默）与显式跳过开关 `HGMD_SKIP=1`（状态 `skipped_user_opted_out`，用户确认不配置后跳过 HGMD 数据库资源、明确记录不静默）；其余检索通道不受影响，有配置时行为完全不变。

## v1.6.0

- **新增 LLM 提取校验层（2026-10-22）**：LLM 提取的 8 字段（genotype/trans_variant/de_novo/phenotype/phenotype_consistency/biochemical/family/parental_genotype）未经校验不得直接进入证据累分。三类自动化校验，只标注/降置信度、绝不替 LLM 编答案、异常显式记录不静默：C1 枚举合法性（genotype 限 杂合/纯合/复合杂合、de_novo 限 是/否、phenotype_consistency 白名单，越界→invalid）；C2 内部一致性（纯合+反式第二变异、复合杂合无反式、de_novo=是 但双亲未报告→conflict）；C3 权威基线交叉核对（trans_variant 与 ClinVar 公开 API 核对，查不到→unverified；HGMD 为商业库留接口默认关闭）。每篇提取结果带 `validation.status`（clean/has_issue/invalid）+ `confidence` + `issues`，供下游证据码识别可信度。配套 `scripts/test_extraction_validation.py` 契约测试（V1-V8）。

## v1.5.0

- **新增 LLM 闸门（2026-10-22）**：统一所有 LLM 调用的"不静默出口"。新增 `LLMConfigError`（携带完整配置指引）与 `_ensure_llm_env()` 启动即校验；`_call_llm_for_filter` 末路由 `return ""` 改为 `raise LLMConfigError`，`_llm_precision_filter`/`_extract_structured_fields` 两处降级点改中断上报，main() 对 LLM 依赖模式（all/hgmd/clinvar/pubtator/litsense/pubmed/openalex/semantic_scholar/europepmc）启动校验，abstract/fulltext 不触发。脚本入口非零退出码（LLMConfigError→exit 2，其他→exit 1）。配套 `scripts/test_llm_gate.py` 契约测试（G1-G5）。LLM 不可用/未配置时禁止静默降级为关键词过滤，必须硬中断并引导配置 KEY。

## v1.3.1

- 确定为**可疑文献机制唯一权威**：其余证据码子技能中"文献核验 + 可疑文献上报"一律引用本技能（L1/L2/L3 分级 + 挂载默认可疑 + 强制上报的完整判定标准唯一以本技能为准）；正文版本号标注剥除，保留"引用唯一权威"措辞。

## v1.3.0

- 新增【按用途证据码定制提取】——检索须声明用途证据码，按“证据码→关键提取字段映射表”差异化提取（PM3=合子+反式+相位、PS4=先证者数+OR+CI、PS2/PM6=de novo+双亲验证、PS3/BS3=实验+对照+结果、PM5/PS1=同位点变异、PVS1=下游热点、PP1=分离次数、BS2=健康成人合子态），关键字段缺失须逐字段标“未报告/未检测”，不得凭推测填充。

## v1.2.0

- 升级判定标准：①ClinVar/HGMD 挂载文献一律默认可疑（无条件上报，不论能否取到摘要/全文）；②其他检索路径（PubTator/LitVar2/PubMed/LitSense/OpenAlex/SemanticScholar/EuropePMC/搜索引擎/中文）按"变异本体可核验性"分 L1(不可核验/假阳性)/L2(部分可核验)/L3(已核验)。命中可疑者必须逐条输出 PMID+链接+原因 交用户人工核验，不得把无法核验的文献静默当作已核实证据（Rath 2015 PMID 26540129 判例）。

## v1.1.0

- 新增【可疑文献上报】硬步骤。
