# ev-pp1 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.8.0（BS4 VCEP 适用性路由，2026-10-21）

- **全量探查**：134 个 VCEP 基因文件 **117 个含 `#### BS4` 档位判据**、16 个无段、1 个纯通用。
- **关键形态结论**：多数基因 BS4 是信息量门槛型（≥2 家系×≥2 informative 减数分裂→Strong，常附加未受累携带者/表型分门槛，如 LDLR 需 ≥1 未受累携带者（LDL-C <50th）、APC 需受累无变异者 ≥1 表型分）；少数定量共分离型（BRCA1/BRCA2 Bayes LR ≤0.05:1→BS4、≤0.00→BS4_VeryStrong）；单/多家系档位型（VHL ≥2 家系→Strong、1 家系→Supporting）；非分离语义型（CDH23/COCH/GJB2 等听觉组表型+/基因型-）。
- 新增【BS4 VCEP 适用性路由协议】：查索引→读 BS4 段→判定形态（信息量门槛/定量共分离/单多家系档位/非分离语义/NA）→附加到通用 BS4 判定。通用 BS4 判定（遗传方式前置 + 无共分离判定 + 样本量 + 拟表型核查）保留不动。
- 自检清单新增【BS4 VCEP 路由闸（v1.8.0）】：评 BS4 前必走路由。

## v1.7.0（PP1 VCEP 路由协议，2026-10-20 用户拍板"真实还原指南、不引入新问题"）

- **核心新增：第 3.5 步 VCEP 路由协议**——评某基因 PP1 先查 `clingen-vcep/knowledge-base/00-索引.md` 确认该基因是否有 `VCEP-<gene>.md` 且含 `#### PP1` 段；有 → 读原文档位，按形态解析 spec 喂引擎确定性比较。124 基因 PP1 段深度探查（2026-10-20）形态分布：
  - 纯数值档 93（meioses/受累亲属数）→ `{"type":"count","strong":N,"moderate":M,"supporting":S}`；
  - LOD 档 2（FOXN1/PALB2 等）→ `{"type":"lod","lod_strong":X,...}`；
  - 按遗传方式分档（HL 基因 GJB2/SLC26A4/CDH23/TECTA 等，AR/AD 档位不同）→ `{"type":"by_moi","AR":{子档},"AD":{子档}}`；
  - 引用式/无数值（"Co-segregation in multiple affected family members"或引外部表/PMID/图表，CDKL5/MECP2/BRCA1/2 等）→ 不数值化，标注"须回原文核对"回退第 4 步通用档；
  - 特殊条件式（CTLA4/PIK3CD/PIK3R1 需 PS4 积分、IDUA 附录积分制）→ 标注"有特殊条件须回原文核对"，不数值化。
- **新增引擎 `pp1_vcep_band(count, gene, spec, mode)` + `_pp1_spec_match`**：支持 count/lod/by_moi 三种 spec 形态，做确定性比较；**不硬编码 124 基因**（单一权威源=clingen-vcep 原文）；现有 `pp1_lod_adxl` / `pp1_lod_ar` / `pp1_lod_hl_ar` 保留不动（通用/HL/CMP-EP 回退路径）。CLI 已注册。
- **层级理顺（v1.7.0）**：现有第 4 步（HL VCEP 官方矩阵闸 + CMP-EP 档 + 通用 J&B）升级为"**回退档**"——仅用于第 3.5 步判定为"无 PP1 段 / 引用式无数值 / 特殊条件式须回退"时；有 VCEP PP1 段且可数值化者一律走第 3.5 步路由。HL/CMP-EP/通用值本身零改动。
- **验证**：pp1_vcep_band 功能测试 30 项全 PASS（count/lod/by_moi + 边界 + 非法 spec 防护）；py_compile 通过；现有 pp1_lod_* / bs1_vcep_band 未破坏。
- 版本：ev-pp1 **1.7.0**。

## v1.6.3（PP1 LOD 通用/特异分流，2026-10-20 用户拍板"通用=通用、特异=特异"）

- **核心修正**：通用 PP1 LOD 阈值位置被 CMP-EP 疾病特异档（0.9/1.5/2.1）污染。按用户拍板分流——
  - **通用位置 `pp1_lod`**：改回 **Jarvik & Browning 2016 原值 0.9/1.2/1.5**（3/4/5 减数分裂，PMID 27495972），适用于无疾病特异 VCEP 的基因；
  - **新增 `pp1_lod_cmp_ep`（特异块）**：CMP-EP 档 0.9/1.5/2.1（Supporting ≥3 / Moderate ≥5 / Strong ≥7 减数分裂），**仅 ClinGen Cardiomyopathy EP（GN101）覆盖基因启用、默认不启用**；
  - **HL VCEP 档不变**（`hl_vcep_pp1` 0.6/1.2/1.5）。
- **同步改动**：`config/thresholds.json`（pp1_lod 通用回 J&B 原值 + 新增 pp1_lod_cmp_ep 特异块）；`scripts/acmg_evidence.py`（`pp1_lod_adxl` 加 gene 参数 + 新增 `_in_cmp_ep` 锚点，传心肌病基因自动走 CMP-EP 档；docstring/fallback 默认值同步 J&B 原值）；`ev-pp1/SKILL.md` §第 2 步通用阈值 + §第 4 步 HL 对照的通用值（0.9/1.5/2.1 → 0.9/1.2/1.5）；构建脚本（知识图透传 pp1_lod_cmp_ep，知识图升 2.0.2）。
- **消除的隐患**：此前通用位置塞 CMP-EP 档，评无特异 VCEP 基因的 PP1 会误用加严档（Moderate 1.5/Strong 2.1），共分离证据被低估；现分流后无特异基因走 J&B 通用值。
- 版本：ev-pp1 **1.6.3**。

## v1.6.2（Table 4a/4b 双引并列回填，2026-10-16 v17 审计自我更正后回改）

- 上一轮 v1.6.1 按 v16 审计把 HL VCEP 阈值来源改为 "Table 2 / General Recommendations"（v2 规范文档表名）。**v17 审计自我更正**：Table 4a/4b 是 Oza et al. 2018（PMID 30311386，Human Mutation 39:1593–1613）论文的正确编号，v2 规范 PDF（2022-03-29）另用 General Recommendations 表，**两者同源一致、只是引用对象不同（论文 vs 规范文档）**。
- **回改**：ev-pp1/SKILL.md §第 4 步 + 自检、config/thresholds.json source 改为**双引并列**——"Oza et al. 2018 [PMID 30311386] Table 4a/4b ↔ HL VCEP cspec v2 [2022-03-29] General Recommendations 表"，消除包内（SCID VCEP FOXN1 用 Table 4a 论文口径）两套表名的不一致。
- 纯文档引用修正，**判定逻辑/引擎/阈值零改动**（0.6/1.2/1.5 不变）。
- 版本：ev-pp1 **1.6.2**。

## v1.6.1（HL VCEP AR 口径修正 off-by-one，2026-10-16 外部审计 v16 + 官网原文核验）

- **修正根因（推翻 v1.6.0 结论）**：v1.6.0 误读 HL VCEP 官方为"受累分离数含先证者"，把"受累个体数"直接当分离数，USH2A 家系 3 个受累个体 → LOD 1.81 → **Strong（over-call 一档，错误）**。回官网 v2 原文核验：**"do not count probands as a segregation；Affected segregations = # affected individuals − 1"** → 受累分离数 = 个体数 − 1。
- **修正后**：USH2A 家系 3 个受累个体（unaff=0）→ 分离数 2 → LOD **1.20 → Moderate** ✅；1 名受累亲属（2 个体）→ 分离数 1 → LOD 0.60 → **Supporting** ✅（对照官网证据码表 "Segregation in one affected relative = PP1 Supporting"）；仅先证者（1 个体）→ 分离数 0 → 不成立 ✅。
- **归因修正**：真实低估来源是**阈值错配**——通用 pp1_lod 的 0.9/1.5/2.1 是 AD(LOD 底数 0.5) 的阈值，套在 AR(底数 0.25) LOD 上偏低；通用 0.25^(affected-1) 与官网 −1 口径**数值一致**，无"排除先证者"问题。HL VCEP 基因须走官方阈值 **0.6/1.2/1.5**（Table 2 / General Recommendations）。
- **同步改动**：`acmg_evidence.py::pp1_lod_hl_ar`（`0.25^affected` → `0.25^(affected−1)`，affected 参数=受累个体数含先证者）+ docstring/注释/返回文案；`ev-pp1/SKILL.md` 第 4 步、输出四要素、自检清单；`config/thresholds.json → hl_vcep_pp1` note/source（Table 4a/4b → Table 2/General Recommendations，PMID 28868250 → 30311386）。
- **回归影响（预期变化，非新问题）**：USH2A 实战组合由 v1.6.0 的 `PM3_S + PP1_Strong + PM2_S` = Pathogenic/A · LP/B（分歧、over-call）恢复为官网口径 `PM3_S + PP1_Moderate + PM2_S` = LP 双套一致。
- 版本：ev-pp1 **1.6.1**。

## v1.1.0

- 新增遗传方式前置判定硬步骤——判定前必须先调用 `arad-inheritance-judgment` 确认该变异为显性(AD)/隐性(AR)/X连锁，再选用对应 LOD 公式与强度表，禁止默认 AD 或 AR；遗传方式以 ClinVar 患者基因型+PubMed报道+GenCC MOI 三方交叉为准。

## v1.2.0

- 新增【文献核验+可疑文献上报】强制子步骤（引用文献家系做共分离累加时先核验，仅本家系数据不受限）

## v1.2.1

- 补跨技能引用声明——凡本技能判定依赖文献检索/核验时，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」与按用途差异化提取；本技能 description 显式声明该跨技能依赖，不再隐式引用。

## v1.3.0

- 新增【共分离穷尽检索专项】对治"共分离家系漏用"——启用 PP1 前必须完成本家系+PubMed/ClinVar/HGMD 其他家系多通道穷尽检索（segregation/pedigree/family/co-segregation 关键词），逐家系核对受累/非受累成员按 LOD 累加，确认无共分离家系后才弃用，不得凭"查不到"直接漏用；内置 OTOF/GJB2/GALC 应用判例。

## v1.3.0

- 补齐 BS4（无共分离，良性 Strong）——BS4 为 PP1 的良性镜像（变异解读查询路径 5.5.7），在受影响个体中检测不到该变异/与该变异不共分离且样本量足够时使用；判定前同样须调用 `arad-inheritance-judgment` 确认遗传方式。

## v1.3.1（全局维护收敛整改）

- 可疑文献判定完整标准（L1/L2/L3 分级 + 挂载默认可疑 + 强制上报）收敛到唯一权威 `ev-variant-literature-patient`，本技能仅保留按用途定制提取要求，不再内嵌重复完整段。

## v1.6.0（HL VCEP 官方矩阵强制闸，2026-10-16 用户评级实证 USH2A）

- **根因**：USH2A 家系 3 受累分离被经验计数当 2 个，PP1 误给 Moderate（应为 Strong）。
- **第 4 步升级为强制官方矩阵闸**：PP1 第一步先判断该基因有无 ClinGen VCEP cspec；有 → 必须回官方规范原文逐格查表，禁止计数推理。
- **固化 HL VCEP（GN005）AR 口径**：受累分离数 **含先证者**、unaffected 不含携带者父母；LOD=log10(1/(0.25^affected×0.75^unaff))（Strande 2017/Table 4b）；阈值 0.6/1.2/1.5（Table 4a）。有 HL VCEP 基因**禁用通用 pp1_lod_ar**（其 0.25^(affected-1) 排除先证者、阈值 0.9/1.5/2.1，系统性低估档位）。
- **确定性工具**：新增 `acmg_evidence.py::pp1_lod_hl_ar`（官方口径），`pp1_lod_ar` 加 `gene` 参数自动命中 HL VCEP 基因；CLI 注册两入口。阈值集中 `config/thresholds.json → hl_vcep_pp1`。
- **输出强制四要素**：受累分离数（含先证者）+ unaffected 数 + 查表 LOD + 对照阈值，杜绝"≥2 亲属=Moderate"经验表述。
- 纯输出/工具契约，组合引擎与 39 集评测不受影响（golden 无 HL VCEP PP1 变异，回归需实测确认）。
- 版本：ev-pp1 **1.6.0**（收尾、acmg_evidence、thresholds 同步见 sync-manifest §10）。

## v1.5.0（PP1 共分离证据逐家系结构化输出，2026-10-16 用户拍板）

- **PP1 共分离证据结构化输出模板**：第 2 点"数据值"对每个计入 PP1 的家系，**逐家系**列全——家系规模（几人）、携带该变异的人数、携带者是否受累（有表型/无表型/未报告）、表型是什么、参考文献号(PMID)+链接(URL)。有 N 个家系列 N 个；任一字段未给出**直接写"未给出"**，不得空着、不得捏造。
- 当前先证者**本家系数据**（非文献来源）须注明"本家系数据（无独立文献，无 PMID）"，不得伪报文献。衔接收尾『文献呈现强制规则』（PMID+URL 成对）。纯 L1 输出层文本契约，**不改 LOD 计分/判定/引擎**。
- 措辞防照抄修正（同版本 1.5.0，逻辑不变）：模板明确为"字段清单（数据采集项），不是要输出的句子"——输出须逐字段填本次查到的实际值，**禁止照抄模板字段名/示例枚举**（如"几人""有表型"）；整段照抄模板或只输出字段名不填值判违规、不得定级。

## v1.4.0（第三方第三轮深度审计修复，2026-10-15）

- **PP1 共分离 LOD 强度阈值切换为 ClinGen 共识可核验值（0.9/1.5/2.1，来源 Jarvik & Browning 2016, PMID 27495972）**：原 0.6/1.2/1.5 来自内部 slide、不可外部核验，已弃用。判定语义：Supporting LOD≥0.9（3–4 个减数分裂）/ Moderate ≥1.5（5–6 个）/ Strong ≥2.1（7 个以上）。阈值统一读 `config/thresholds.json → pp1_lod`，由 `scripts/acmg_evidence.py` 的 `pp1_lod_adxl` / `pp1_lod_ar` 确定性定档（替代手工查表）。
- 备注：原 CHANGELOG 存在两个重复 v1.3.0 条目（一为共分离穷尽检索、一为 BS4 补齐），保留原文、未合并改动。
