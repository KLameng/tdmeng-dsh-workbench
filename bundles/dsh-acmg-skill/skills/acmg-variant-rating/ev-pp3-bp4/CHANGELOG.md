# ev-pp3-bp4 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.10.0（BP7 VCEP 适用性路由，2026-10-21）

- **全量探查（两轮，修正 NA 误判）**：134 个 VCEP 基因文件 **130 个含 `#### BP7` 档位判据**、3 个无段、1 个纯通用。修正：NA 仅在 BP7 段明确声明不适用且无档位判据时判定（首轮正则误伤含"not applicable"字样的基因如 TP53/RUNX1/MLH1/BRAF，二轮改为锚定档位判据）。
- **关键形态结论**：绝大多数基因的 BP7 是"同义/内含子变异 + 剪接预测无影响 + 保守性"判据（标准型 Supporting）；少数有数值切点（HNF1A：SpliceAI<0.2 且 phyloP100<2.0；AKT3/MTOR/PIK3CA/PIK3R2：PhyloP<0.1）；部分有 RNA 实验升档（ACADVL/AIPL1/ATM/BRCA1/BRCA2/GAMT/GATM/GUCY2D/IDUA/OTC/PALB2/PAH/PIK3R1/RPE65/RS1/SGCA/SGCB/SGCD/SGCG/TP53 等→Strong/个别 Moderate）；个别 BP4 联动（ABCD1/VHL）或特定限定（RUNX1 排除剪接供体前 3nt、BRCA1 功能域外错义需 RNA）。
- 新增【BP7 VCEP 适用性路由协议】：查索引→读 BP7 段→判定形态（标准型/数值切点型/RNA 升档型/BP4 联动/NA）→附加到通用 BP7 判定。通用 BP7 判定（变异类型 + 剪接全低分 + 实测剪接）保留不动。
- 自检清单新增【BP7 VCEP 路由闸（v1.10.0）】：评 BP7 前必走路由。

## v1.9.0（BP1 VCEP 适用性路由，2026-10-21）

- **全量探查（Windows 重建工作区）**：134 个 VCEP 基因文件 **17 个含 `#### BP1` 特异规则**、4 个 NA、2 个纯通用、**111 个无段**。
- **关键形态结论**：RASopathy 基因（BRAF/HRAS/KRAS/MAP2K1/MAP2K2/MRAS/NRAS/PPP1CB/PTPN11/RAF1/RIT1/RRAS2/SHOC2/SOS1/SOS2，14 个）VCEP 明确"BP1 不用于 RASopathy（GOF 错义机制）"，改为截短变异在无 LOF 关联基因中判良性（非 BP1 本义）；PALB2 适用于所有错义变异；APC 适用于除 β-catenin 结合域（codon 1021-1035）外错义；KCNQ1/ITGA2B/ITGB3 为 NA。
- 新增【BP1 VCEP 适用性路由协议】：查索引→读 BP1 段→判定形态（RASopathy GOF 不适用错义/截断机制适用所有错义/区域排除/NA/无段）→附加到通用 BP1 判定。通用 BP1 判定（机制前提+例外排除）保留不动。
- 自检清单新增【BP1 VCEP 路由闸（v1.9.0）】：评 BP1 前必走路由，VCEP 有特异则用 VCEP，声明不适用则写不成立，无段则用通用；禁止凭手抄漏查。

## v1.8.0（BP4 VCEP 基因特异阈值路由，2026-10-20）

- **新增 BP4 第 3.5 步 VCEP 基因特异 BP4 阈值路由协议**（与 PP3 第 3.5 步 / ev-pm2 / ev-bs1-bs2 同源）：判定 BP4 前先判断该基因是否有 ClinGen VCEP cspec 且 BP4 段定义可路由规则；有 → 路由读 `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### BP4` 段原文，按原文档位判定，**优先于通用 REVEL BP4 强度表**；无 BP4 段/引用式无数值 → 回退通用表并标注。
- **明确 BP4 与 PP3 的本质差异（写死）**：BP4 是良性侧，规则核心是"按变异类型分派"——同一基因 missense/synonymous/intronic 往往各自走不同工具与切点，某类型可能明文 not applicable（如 APC missense NA）。判定必须按实际变异类型选分支，不得拿错切点、不得在 VCEP 明文 NA 的类型上给 BP4。
- **新增引擎 `acmg_evidence.py::bp4_vcep_band`**（spec 驱动确定性比较，良性侧）：支持按变异类型分派（by_type）+ 主数值切点（tool/le：REVEL/CADD/BayesDel）+ 剪接排除（spliceai_le）+ and_tools 且逻辑 + NA 分支 + 多档（Moderate/Supporting/Strong 逐级）+ reference_only 回退 + 前置排除（exclusions）。不硬编码 124 基因，spec 由路由读原文传。
- **封顶原则**：VCEP 只定义某档的基因（绝大多数仅 Supporting），BP4 封顶该档，即便 REVEL/CADD 远超切点也不得升更高档（对齐 PP3 封顶，特异=特异）。
- **契约测试**：`contract_test.py` 新增第 11 节 bp4_vcep_band 15 条用例（GJB2/HBB/APC/TP53 真实 VCEP 规则 + 引用式/排除/非法 spec），全 PASS，无回归（104 通过 / 0 失败）。
- **判例写死**：GJB2 常隐耳聋——VCEP BP4=REVEL≤0.15 或 MaxEnt 无剪接影响（通用表 [0.183,0.290] BP4_Supporting 区间比 VCEP 0.15 宽）；REVEL=0.20 通用表是 BP4_Supporting、按 VCEP 0.15 不成立，必须路由读 VCEP 用 0.15 切点。

## v1.7.0（PP3 VCEP 基因特异阈值路由，2026-10-20）

- **新增第 3.5 步 VCEP 基因特异 PP3 阈值路由协议**（与 ev-pm2/ev-bs1-bs2/ev-pp1 同源）：判定 PP3 前先判断该基因是否有 ClinGen VCEP cspec 且 PP3 段定义可路由规则；有 → 路由读 `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### PP3` 段原文，按原文档位判定，**优先于本表通用 REVEL 强度表**；无 PP3 段/引用式无数值 → 回退通用表并标注。
- **新增引擎 `acmg_evidence.py::pp3_vcep_band`**（spec 驱动确定性分数比较，覆盖 9 种 VCEP PP3 形态：tool_threshold / revel_or_spliceai / revel_and_cadd / n_of_m / multi_band / spliceai_only / bayesdel_domain / revel_or_maxent / reference_only），支持变异类型分流、前置排除（exclusions）。不硬编码 127 基因，spec 由路由读原文传。
- **封顶原则（2026-10-20 用户拍板）**：VCEP 只定义 Supporting 档的基因，PP3 封顶 Supporting（REVEL 多高也不得升 Moderate/Strong）——指南基于贝叶斯框架，VCEP 只给到 Supporting 说明该基因计算预测证据权重即 Supporting 级，补造更高档违反"特异=特异"、over-call。Moderate/Strong 仅当 VCEP 明确给多档时启用。
- **VCEP 原文异常须上报**：AIPL1 官网 PP3 Strong=REVEL≥0.093 < Supporting 0.644（疑笔误，文件内已注明照录原文未改值）→ 不盲目套用，回退通用表并标注，禁止把异常阈值喂进引擎。
- **判例写死**：OTOF c.5098G>C——VCEP OTOF PP3=REVEL≥0.7（通用表 [0.644,0.773] 区间覆盖但 VCEP 收紧到 0.7）；REVEL=0.68 通用表是 PP3_Supporting、按 VCEP 0.7 不成立，必须路由读 VCEP 用 0.7 阈值。



- **D32（spliceai 阈值权威来源标注补全）**：SpliceAI2 阈值映射段标"权威来源=config/thresholds.json → `spliceai.v2_thresholds`，判定统一走 `acmg_evidence.py spliceai_band`（D31 联动，读 config 不硬编码）"。纯标注增强，不改阈值与判定规则。


## 本版新增（预测工具网址+GeneBe兜底通道）

- 本版新增各预测工具官方网址与当前调用方式，并补充 **GeneBe api-public 端点作为正式兜底取数通道**（REVEL/AlphaMissense/BayesDel/SpliceAI/gnomAD/ClinVar 全字段，替代被 robots 反爬拦截的 genebe api-x 老端点）。

## v1.3.0

- 同技能补齐 BP1 与 BP7（良性 Supporting）判定段——BP1 为错义变异但基因仅 LOF 机制（变异解读查询路径 5.3.2.5，需排除 GOF/DN 错义致病例外）；BP7 为同义/非编码变异且不影响剪接（变异解读查询路径 5.3.2.6，SpliceAI 阈值 >0.2 判有剪接影响则 BP7 不成立，剪接预测取不到不得默认无影响）。

## v1.4.0

- REVEL 主通道强制优先（整改 P1，实证 var022 SLC22A5 c.338G>A——技能群取多工具共识给 PP3_Supporting，金标准 REVEL=0.972≥0.932 → PP3_Strong，通道遗漏致偏低）：REVEL 能取到（VEP/dbNSFP、GeneBe api-public、MyVariant.info 任一通道）时，**必须以 REVEL 值对照强度表定档**，多工具共识（CADD+SIFT+PolyPhen 等）**不得替代 REVEL 定档**，只能作为 REVEL 全部通道取不到时的兜底且仅佐证方向/Supporting 上限。

## v1.5.0（BP4 使用限定条件硬闸门）

- 给 BP4 前必须穷尽检索该特异变异的成熟功能实验——检出功能受损/酶活降低证据（PS3 侧，如 UGT1A1*6 酶活降低 PMID 9630669/19830808）时，BP4（预测无害）与功能实验冲突，功能实验优先，BP4 强制不成立、回致病证据链；功能实验检索取不到/不明确时不得默认无功能受损而给 BP4（实证 UGT1A1 c.211G>A 预测良性但功能受损被误给 BP4）。

## v1.6.1（阈值双写同步标注，2026-10-15）

- REVEL 强度对照表头补「权威来源 = `config/thresholds.json` → `revel`，改切点必须在 thresholds.json + 本表 + `scripts/acmg_evidence.py::revel_band` 三处同步（sync-manifest §10）」——纯文档增强，阈值/规则不变。

## v1.6.0（SpliceAI2 剪接侧升级通道，直接接入）

- 本技能 PP3 的剪接侧（剪接相关/非编码变异预测有害）、BP7 剪接影响判定、BP4 剪接无害侧，新增 SpliceAI2 作为剪接预测主升级通道——`spliceai2_summary_score`（0-1）阈值：0.1=高召回（对应初代 SpliceAI 0.2，Jaganathan 2019）、0.25=平衡（对应 0.5）、0.5=高精度（对应 0.8）；来源版本绑定 SpliceAI2 v2（Illumina BioInsight AI Lab，2026-10-08，technical article + manuscript preprint，GitHub `Illumina/SpliceAI2`，预计算 40 亿 SNV + 1.5 亿 indel，学术免费，PyPI 安装需 CUDA GPU）；SpliceAI2 只做实剪接侧，**不替代 REVEL 错义主通道**；SpliceAI2 不可达/无 GPU 时回退初代 SpliceAI 官方 API（spliceailookup）0.2 高召回切点并交叉验证，标注来源版本。
