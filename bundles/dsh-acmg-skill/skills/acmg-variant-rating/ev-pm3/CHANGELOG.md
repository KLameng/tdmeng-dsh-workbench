# ev-pm3 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此；同日修复版本序列非单调（原 1.6-1.9 与 1.1-1.5 两条版本线合并，现已按版本号单调升序重排，frontmatter version=1.10.0 不变）。

## v1.13.0（PM3 VCEP 基因特异档位路由，2026-10-20）

- **新增第 2.8 步 VCEP 基因特异档位路由协议**（与 ev-pm2/ev-bs1-bs2/ev-pp1/ev-pp3-bp4 同源）：PM3 累分后定档先判断该基因是否有 ClinGen VCEP cspec 且 PM3 段定义非标准档位切点；有 → 路由读 `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### PM3` 段原文，按原文档位切点定档，优先于通用 SVI 强度表。
- **PM3 特异性本质澄清**：逐例计分权重全基因一致（confirmed 1.0 / phase-unknown P 0.5·LP 0.25 / 纯合 0.5 / VUS 0.25，SVI Table 1，所有 VCEP 引用）；只有"档位切点"（累分→强度档映射）可能基因特异。
- **新增引擎 `acmg_evidence.py::pm3_vcep_band`**（复用逐例计分权重 + spec 档位切点参数 + max_band 封顶），默认标准 SVI 档 0.5/1/2/4（与现有 pm3_points 完全一致、零变化），特异档/封顶由路由读原文生成。
- **特异档基因（已从 clingen-vcep 全量核实，含 FA/BRCA 通路 24 基因）**：**ATM/PALB2/FOXN1** 用 FA 档 1/2/4/8（Supporting≥1/Moderate≥2/Strong≥4/VeryStrong≥8）；**BRCA1/BRCA2** 条件式（需 FA 表型 + 同基因共发，封顶 Strong 无 VS）；**LDLR** 条件式（纯合家族性高胆固醇血症，封顶 Moderate）。
- **封顶原则（2026-10-20 用户拍板）**：VCEP 只定义到某档的基因（BRCA1/2 无 VS、LDLR 仅 Moderate）→ PM3 封顶该档，不升更高档。
- **已核实无遗漏**：FA/BRCA 通路 24 基因逐一核对 clingen-vcep 覆盖，仅 BRCA1/BRCA2/PALB2/ATM 有 VCEP+PM3 段；其余 20 个 FA 基因（FANCA/C/G/D2 等）无 VCEP 文件 → 走通用表。
- 与 v1.12.0 相位三态/大队列专项一致，未引入新矛盾；标准档基因行为零变化。

## v1.12.0（相位三态防虚高 + 大队列/降级通道根治，2026-10-16 用户实操审计）

- **根因**：家系 19178 仅"兄弟+姐妹同基因型共分离"（PMID 29899460 原文无父母验相位），被执行者误判 confirmed in trans（A 态 1.0），实应 phase unknown（B 态 0.5）。累分 3.50→3.00 档位未变（仍 Strong），但边界例（1.9–2.0）可被系统性顶高 0.5–1.0 分，属真实偏倚风险。
- **新增"家系共分离 ≠ confirmed in trans"硬闸**：仅兄弟姐妹/亲属共分离而无父母/后代验相位直接证据 → 强制 B 态（0.5/0.25），禁止误判 A 态（1.0）；A 态必须附原文"父母验相位"直接引语（`confirmed in trans`/`phase established`/`parental testing confirmed` 等），`in trans` 由共分离推断得来不得作 A 态判据。
- **新增验证来源二选一**：A 态须标 `父母/后代验证`；仅 `家系共分离推断` → 归 B 态并标注降权计分。
- **新增大队列补充表解析专项（三强制动作）**：PDF 表格行错位逐行核对（错位行弃用/回正文）、跨文献/大队列按患者ID+变异去重、多患者 ID 同双等位组合按同家系合并（同一家系共享同一对变异=1 个 proband，不翻倍）。
- **新增 PubMed 反爬降级路径**：全文不可达固定走 PMC/全文PDF/ClinVar 挂载；PMID↔PMC 映射核对主题一致，抓到无关 PMC 不得采用回 PMID 重映射；降级核验例标注通道并按三态计分。
- 纯流程/契约层改动，不改计分表、不改累分映射、不改组合引擎；与 v1.8.0 phase-unknown 封顶口径、v1.9.0 三态判据、v1.5.0 先累分后判成立一致，未引入新矛盾。

## v1.1.0

- 强度映射升级为硬约束——累分达 2.0→Strong、4.0→VeryStrong 必须给满档，禁止保守降档；新增"PM3 逐篇累分证据表"强制输出项（逐篇 PMID+合子+相位+计分），未输出该表不得给 PM3 等级。

## v1.2.0

- 新增遗传方式前置判定硬步骤——判定前必须先调用 `arad-inheritance-judgment` 确认该病为常染色体隐性(AR)，禁止默认 AR；遗传方式以 ClinVar 患者基因型+PubMed报道+GenCC MOI 三方交叉为准。

## v1.3.0

- 新增【文献核验+可疑文献上报】强制子步骤（第2.5步检索到的每条文献先按可疑文献判定再计分，ClinVar/HGMD挂载一律默认可疑，未核验到该变异不得计入累分）

## v1.3.1

- 补跨技能引用声明——凡本技能判定依赖文献检索/核验时，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」与按用途差异化提取；本技能 description 显式声明该跨技能依赖，不再隐式引用。

## v1.4.1

- 判定完成闸就位——①穷尽检索四段（本家系 + ClinVar + PubMed + HGMD）必须走完（第2.5步）；②已评级证据信任：ClinVar EP / 多星 P/LP 不视为可疑文献，按 confirmed 累分；③强度强制映射（≥4.0→VS、≥2.0→Strong）禁保守降档。

## v1.5.0

- 修复"整码删除策略过度保守"（整改 P0-1，实证 var002 F7 / var003 PYGM）——①判定逻辑改为"先按 SVI 逐例累分定档（≥1 例 confirmed-trans/无关纯合 → 至少 Moderate），再判是否成立"；②只有"检索到病例但均不可用（可疑文献/相位不明无佐证）"才允许整码删除，且必须逐条留痕（每条 PMID+不可用原因）；③判定闸新增：命中 ≥1 例已发表无关纯合/confirmed-trans 时禁止整码删除，必须输出"PM3 逐篇累分证据表"。

## v1.6.0

- 新增第 2.6 步【VCEP 官方已定级优先】硬步骤（整改，实证 var006 GJB2 c.109G>A / var030 HBB IVS-II-654）——累分前先查 ClinGen cspec 是否有 VCEP 官方对本变异的裁定，有则直接采用官方结论、通用累分档位不得覆盖官方整体裁定；无该变异裁定或无 VCEP 则走通用累分并标注。

## v1.7.0

- 新增第 2.6 步【两级官方优先】（整改 var023 CFTR 5T 盲区）——第 2.6 步从"仅 ClinGen VCEP/EP cspec"扩展为两级：①第一级 ClinGen VCEP/EP cspec 对本变异（具体到 c.HGVS/rsID）的官方裁定（原规则保留）；②第二级：基因无 ClinGen VCEP cspec，但存在**权威专家组/官方技术标准的共识性定级**（ACMG 官方专项技术标准/专项指南、基因特异 Expert Panel 共识库如 CFTR2、ClinVar 专家评审 reduced-penetrance/variable-expressivity 等；须为权威共识，非 ClinVar 一般提交者聚合分类、非单篇文献），同样优先采用共识定级、通用累分档位不得覆盖该共识，交付显式标注"非 cspec 官方，按权威专家组共识定级（来源+版本+结论）"。

## v1.8.0

- 统一 phase-unknown 封顶计分口径（整改 P0-1，实证 var034/036/037 偏低根因——金标准对相位未验证的反式病例按 phase-unknown 封顶计分，技能群"核验前不计/相位不明不计"导致系统性漏计）：①文献明确列了本变异的反式/纯合例（L3 或 ClinVar/HGMD 已挂载），即使全文未核验/相位未确证，**不得整码不计**——按 phase-unknown 档降权封顶计分（P 反式=0.5、LP 反式=0.25）并逐条标注"相位待核（按 phase-unknown 降权计分）"；②仅当文献完全未列本变异（L2）或不可核验/异源假阳性（L1）时才不计分；③相位未验证的例按计分表 phase-unknown 档降权，不当作 confirmed in trans 计 1.0，也不归零。

## v1.9.0

- 新增【相位三态强制】硬步骤（防虚高执行风险——把"查不到相位"宽松等同"phase-unknown 可计分"的执行歧义，改为强制 A/B/C 三态枚举 + 原文关键词锚定 + 判定闸）：①逐例相位状态只能填 A(confirmed in trans)/B(phase unknown 明确报道)/C(无佐证) 三态之一，且必须附文献原文短语为证据，禁止笼统"phase unknown"带过；②判定闸——文献未报道合子/相位（C）强制不计分，不得按 B 打折计分；只有明确 A 或 B 才计分；③一致性闸——同一变异既有 B 例又有 A 例、或跨文献合子报道矛盾时强制回中间复核，不得自行取高；④可机检关键词锚定（confirmed in trans/phase not determined/homozygous/variant identified 等）消除印象判断。

## v1.10.0（全局维护收敛整改）

- 官方已定级优先（两级）第 2.6 步由"内嵌完整规则"收敛为"识别 + 一行引用收尾 §0 唯一裁决"，本技能不再内嵌完整官方优先规则、不做最终裁决（联网核实见收尾 v3.10.0）。

## v1.11.0（PM3 反式证据逐患者结构化输出，2026-10-16 用户拍板）

- **PM3 反式证据结构化输出模板**：第 2 点"数据值"对每个计入 PM3 的反式/纯合先证者，**逐患者**列全——症状/表型、正反式关系（纯合/复合杂合）、相位（confirmed in trans / phase unknown + 是否经父母后代验证）、另一变异、另一变异是否确信 P/LP、另一变异致病性是本技能自评还是文献/ClinVar 挂载给出、参考文献号(PMID)+链接(URL)。有 N 例列 N 例；任一字段未给出**直接写"未给出"**，不得空着、不得捏造。
- 衔接收尾『文献呈现强制规则』：参考文献号+链接成对（PMID+URL）。纯 L1 输出层文本契约，**不改计分/判定/引擎**，phase-unknown 降权规则不变。
- 措辞防照抄修正（同版本 1.11.0，逻辑不变）：模板明确为"字段清单（数据采集项），不是要输出的句子"——输出须逐字段填本次查到的实际值，**禁止照抄模板字段名/示例枚举**（如"纯合/复合杂合""confirmed in trans"）；整段照抄模板或只输出字段名不填值判违规、不得定级。

## v1.10.1（阈值双写同步标注，2026-10-15）

- 反式计分表头补「权威来源 = `config/thresholds.json` → `pm3_score`，改打分表必须在 thresholds.json + 本表 + `scripts/acmg_evidence.py::pm3_points` 三处同步（sync-manifest §10）」——纯文档增强，阈值/规则不变。

