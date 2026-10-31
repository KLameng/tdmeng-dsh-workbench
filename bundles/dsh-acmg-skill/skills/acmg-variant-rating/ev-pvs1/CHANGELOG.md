# ev-pvs1 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此；同日修复版本序列非单调（原 1.7-1.10.1 与 1.2-1.6.1 两条版本线合并，现已按版本号单调升序重排；末尾 v1.10.2/v1.11.0 为最新整改，frontmatter version 不变）。

## v1.13.0（PVS1 VCEP 适用性路由方案，2026-10-21）

- **全量探查（Windows 重建工作区）**：134 个 VCEP 基因文件 **102 个含 `#### PVS1` 段**（94 特异规则 + 8 NA）、32 个无段。
- **关键形态结论**：PVS1 的 VCEP 特异规则本质是**基因特异的适用性/位置限定**（决策树型语义路由），**非统一数值切点引擎**——不同基因切点语义各异（起始密码子例外、3'端/末外显子/50nt 切点、功能域截断、特定密码子 NMD 分界、剪接/RNA、LOF 机制适用性、转录本）。**不硬造统一 codons spec**（违反"不引入新问题"铁律），与 PS1 同型走适用性路由。
- 新增【PVS1 VCEP 适用性路由协议】第 3.7 步：查索引→读 PVS1 段→逐项提取并核对特异限定（LOF 机制适用性/起始密码子例外/3'端末外显子切点/功能域截断/剪接RNA/转录本/档位调整）→附加到通用决策树；VCEP 声明 LOF 非机制/不适用→写不适用；无段/索引无→用通用决策树。
- **判例（写死）**：VHL codon 54 前截断不适用+10% downgrade 不适用；GAA codon 916 前→PVS1、3'端 916 后无NMD→Moderate、活性位点外显子 8/10 框内缺失→PVS1、起始密码子→Strong、催化桶 6/9→Strong；TP53 p.Lys351 上游→PVS1、351-355 非NMD→Strong；RYR1 4800-4950/外显子100-103 框内缺失→Strong；MYBPC3 p.1254 上游50nt 后无义可能逃逸 NMD；MYH7/GFAP LOF 非机制不适用。
- 自检清单新增【PVS1 VCEP 路由闸（v1.13.0）】：评 PVS1 前必走路由，VCEP 有特异限定则用 VCEP，声明不适用则写不适用，无段则用通用决策树；禁止凭手抄漏查。

## v1.12.0（D32 权威来源标注补全，2026-10-15）

- **D32（spliceai 阈值权威来源标注补全）**：剪接影响判定段 `spliceai_band` 标注"阈值权威来源=config/thresholds.json → `spliceai.v2_thresholds`，读 config 不硬编码（D31 联动）"。纯标注增强，不改阈值与判定规则。


## v1.2.0

- 按 ClinGen SVI 官方原文校准——"位置不是绝对评级"：末外显子/无NMD 变异不固定 Strong，须按"下游致病变异(热点)+病例数+关键功能证据+基因机制强度"整体评估档位；PVS1 满档仅限 Definitive/Strong 关联且 ≥10% 表型变异为 LOF 且 ≥3个非PVS1独立致病LOF 的基因；深内含子/非±1/2剪接档位取决于剪接后果(是否移码+NMD)与 RNA 实证，而非位置本身。

## v1.3.0

- 新增遗传方式前置判定（arad-inheritance-judgment），禁止默认 AD/AR。

## v1.4.0

- 新增第 1.1 步 ClinVar 截短变异计数（≥3 个 P/LP Frameshift+Nonsense+Splice 变异作为关联/机制核心判据，适用于所有遗传方式，AR 病同样先过此关）。

## v1.5.0

- 新增【机制确认证据层级】——维度A(gene-disease validity 明确 mechanism=LOF)优先于维度B(HI 剂量评分)，HI=0/No evidence 不否定 LOF 机制（ACD 判例）；第 1 步强制记录基因-疾病对的分类等级+MOI+mechanism 三字段。

## v1.6.0

- 新增【文献核验+可疑文献上报】强制子步骤（截断点下游致病变异支撑先核验，ClinVar截短计数本身正常执行）

## v1.6.1

- 补跨技能引用声明——凡本技能判定依赖文献检索/核验时，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」与按用途差异化提取；本技能 description 显式声明该跨技能依赖，不再隐式引用。

## v1.7.0

- 新增第 0.5 步【VCEP 官方已定级优先】硬步骤（整改，实证 var006 GJB2 c.109G>A / var030 HBB IVS-II-654）——判定前先查 ClinGen cspec 是否有 VCEP 官方对本变异的裁定，有则直接采用官方结论、通用决策树档位不得覆盖官方整体裁定；无该变异裁定或无 VCEP 则走通用调度并标注。

## v1.8.0

- 新增第 0.5 步【两级官方优先】（整改 var023 CFTR 5T 盲区）——第 0.5 步从"仅 ClinGen VCEP/EP cspec"扩展为两级：①第一级 ClinGen VCEP/EP cspec 对本变异（具体到 c.HGVS/rsID）的官方裁定（原规则保留）；②第二级：基因无 ClinGen VCEP cspec，但存在**权威专家组/官方技术标准的共识性定级**（ACMG 官方专项技术标准/专项指南、基因特异 Expert Panel 共识库如 CFTR2、ClinVar 专家评审 reduced-penetrance/variable-expressivity 等；须为权威共识，非 ClinVar 一般提交者聚合分类、非单篇文献），同样优先采用共识定级、通用决策树档位不得覆盖该共识，交付显式标注"非 cspec 官方，按权威专家组共识定级（来源+版本+结论）"。

## v1.9.0

- 升级第 3.1 步【末外显子无NMD 档位评估】为强制闭环硬步骤（整改 PVS1 档位边界偏低，实证 var032 CNGA3——SKILL.md 判例写明该升满档、实际评级却保守落 Strong）：①强制下游热点三通道穷尽检索（ClinVar/HGMD/文献）并输出"下游热点检索结果表"（下游致病变异+独立变异数+病例数+功能证据）；②判定闸写死——截断区关键 + 下游 ≥3 个独立致病变异 + 多病例 + 功能/临床证据 → **必须升满档 VS**，禁止保守停在 Strong；③仅当关键区证据确实查不到才据缺失蛋白长度定档（>10%→Strong、<10%→Moderate）并标注"关键区证据查不到，据缺失长度定档"。

## v1.10.0

- 新增【gene-validity 官方档位缺失/未确认时回中间复核】硬步骤（整改 P1 偏高项，实证 var028 CCDC88C——gene-validity 官方档位未确认时技能群按 Strong+PM2 组合类推取 LP，金标准 VUS，方法学取档偏松）——官方档位查不到/无法确认时，不得按 VS/Definitive 类推升满档：①回中间复核（ClinGen/GenCC/OMIM/文献再确认三字段）；②仍无法确认 → PVS1 **封顶 Strong（4 分，VUS 边界），不得类推满档 VS（对齐金标准：gene-validity 留空 → PVS1 最高 Strong）**，输出标注"gene-validity 官方档位未确认，取档受限，最高 Strong，不得升满档 VS"；③不得以"PVS1_Strong+PM2_Supporting"组合类推 LP，组合取档回落证据不足水平回中间复核。

## v1.10.1

- 修正取档上限——原"最高 Moderate"与金标准 var001/004/007 "gene-validity 留空→封顶 Strong"口径不符，统一为封顶 Strong

## v1.10.2（全局维护收敛整改）

- ①官方已定级优先（两级）第 0.5 步由"内嵌完整规则"收敛为"识别 + 一行引用收尾 §0 唯一裁决"，本技能不再内嵌完整官方优先规则、不做最终裁决；②gene-validity 官方档位缺失/未确认时的取档由"一律封顶 Strong"改为"条件定档"——先复核关键区证据，成立→PVS1_Strong、查不到→据缺失蛋白长度定档（>10%→Strong、<10%→Moderate），官方档位未确认时无论关键区证据多强都封顶 Strong、不得升满档 VS。

## v1.11.0（SpliceAI2 剪接 LOF 判定接入，直接接入）

- 本技能剪接区（±1,2 / 深内含子 / 隐蔽剪接 / 非编码）变异判定剪接后果前，优先用 SpliceAI2（`spliceai2_summary_score` 0.1=高召回、0.25=平衡、0.5=高精度，对应初代 SpliceAI 0.2/0.5/0.8，Jaganathan 2019）评估是否影响剪接/激活隐蔽剪接——深内含子隐蔽剪接是初代灵敏度短板（SpliceAI2 约半数隐蔽剪接位点位于 >50bp 深内含子，外显子测序常漏），SpliceAI2 优先可降低漏判；来源版本绑定 SpliceAI2 v2（Illumina BioInsight AI Lab，2026-10-08，technical article + manuscript preprint，github.com/Illumina/SpliceAI2，预计算 40 亿 SNV + 1.5 亿 indel，学术免费，PyPI 安装需 CUDA GPU）；不可达/无 GPU 时回退初代 spliceailookup 官方 API 0.2 高召回切点并交叉验证；SpliceAI2 只做剪接预测取数，不替代 RNA 实证（PVS1_Strength(RNA)）与成熟功能实验（PS3/BS3）。
