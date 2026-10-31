# ACMG 评级技能群 · 变更同步载体清单（sync-manifest）

> **用途（P3-1，收敛计划 v9 教训）**：任何"口径 / 枚举值 / 识别串"的变更，必须按本清单逐项同步，**禁止凭记忆当场清点**——九轮里 4 次缺陷（改名漏 2 处、口径漏同步、BA1 盲区）全部落在"人工清点同步"和"人工设想输入"两件事上。
> **改 X 时必须同步 Y/Z；改完在对应行勾 ✓。**

## 1. confidence 边界口径（确信/有争议）

| 载体 | 位置 | 状态 |
|---|---|---|
| 判定规则权威 | `config/golden.json` → `confidence_ruler`（当前 v2.1：边界擦边=确信） | ✓ 已按 v2.1 |
| 操作规则（给执行者看） | `acmg-conflict-summary-output/SKILL.md` §3 全码两分「适用组」边界口径 | ✓ D14 已对齐 v2.1 |
| 历史记录 | `acmg-conflict-summary-output/CHANGELOG.md`（certain/contested 数字） | ✓ D18 已回填 65/20 |
| 人读清单 | 金标准确信度标注表（交付物，随轮更新） | 手动 |
| **改 ruler 时必须同步** | SKILL.md 边界口径 + CHANGELOG 数字 + 标注表 | — |

## 2. Tavtigian interval 枚举（2020 / 2023 / bmpR2_gn125_v2）

| 载体 | 位置 | 状态 |
|---|---|---|
| 阈值配置 | `config/thresholds.json` → `tavtigian_interval`（含 default） | ✓ |
| 引擎 choices+校验 | `scripts/acmg_combine.py`（`--interval` choices、`--gene` 校验、usage docstring L36） | ✓ D11 |
| 评测 choices | `scripts/combination_eval.py`（`--interval` choices、`--gene` 透传） | ✓ D11 |
| 契约文档 | `acmg-conflict-summary-output/input-schema.md`（interval 行 + BA1 契约） | ✓ D12/D15 |
| 收尾规则 | `acmg-conflict-summary-output/SKILL.md` §2（bmpR2 说明 + --gene 强制） | ✓ D11 |
| 历史记录 | `acmg-conflict-summary-output/CHANGELOG.md`（历史条目保留 vcep 旧名，不视为残留） | ✓ |
| 回归网 | `scripts/regression_gate.py`（分值穷举三区间引用；用内部方法不经 combine 校验） | ✓ |
| **改名/增删区间时必须同步** | 上表全部 + **全仓 grep 旧名逐一确认** | — |

## 3. 官方裁定识别串（`VCEP官方裁定` / `{"class":...}` / status 提取）

| 载体 | 位置 | 状态 |
|---|---|---|
| 引擎解析 | `scripts/acmg_combine.py`（`_extract_official` / parse 内官方识别） | ✓ |
| 契约文档 | `acmg-conflict-summary-output/input-schema.md` §3 | ✓ |
| 契约测试 | `scripts/contract_test.py`（官方 4 例 + status 三例） | ✓ |
| 缓存命名空间 | `scripts/acmg_cache.py`（`vcep` 为命名空间名，合法非残留） | ✓ |
| **改识别串时必须同步** | 引擎解析 + input-schema §3 + contract_test + 全仓 grep | — |

## 4. BA1 等级契约（BA1 门控，D19/D20 修订）

> **本组载体只有一个前提**：stand-alone 系列写法（Standalone/Stand-alone/Stand_alone/SA/Stand Alone/Stand Alone (BA1)/(BA1) Stand Alone）**仅对 BA1 生效**；非 BA1 码写该写法 → 整条 skip，绝不升格 VeryStrong（D19）。D27（v5.5.2）：引擎 `_is_standalone_form` 剥括号对，兼容 ClinGen VCEP 官方原文 "Stand Alone (BA1)"，知识库原文不改。

| 载体 | 位置 | 状态 |
|---|---|---|
| 引擎门控 | `scripts/acmg_combine.py` 调用点 `_is_standalone_form`（空白/连字符/括号对归一，剥 `(...)` 兼容 VCEP 原文 "Stand Alone (BA1)"；**仅 BA1 门控**，非 BA1 skip） | ✓ D27 v5.5.2 |
| 契约文档 | `acmg-conflict-summary-output/input-schema.md` §2.3（接受 "Stand Alone" 原文写法） | ✓ D20 |
| 契约测试 | `scripts/contract_test.py` 4d/4e/4f/4h 正向 + 5a/5b/5c 负向（非 BA1+standalone 不升格） | ✓ D16/D21/D27 |
| 门禁穷举 | `scripts/regression_gate.py` 2b 写法变体维度（26 码×7 写法，含 "Stand Alone (BA1)" / "(BA1) Stand Alone"） | ✓ D21/D27 |
| 知识库原文 | `clingen-vcep/knowledge-base/`（22 处 "Stand Alone (BA1)" 含 `(BA1)` 后缀，引擎已剥括号对识别，**知识库原文不改**） | ✓ D27 不改 |

## 5. 版本号一致性

| 载体 | 位置 | 状态 |
|---|---|---|
| SKILL frontmatter | 每个 `ev-*`/调度/收尾 `SKILL.md` → `version:` | ✓ |
| 变更历史 | 同目录 `CHANGELOG.md` 最高版本 == SKILL version | ✓ 门禁遍历 23 |
| 打包校验 | `scripts/verify_counts.py` / 门禁版本一致性 | ✓ |
| **正文内嵌版本号（⚠ 人工义务）** | 各 SKILL 正文中出现的版本号引用（如收尾正文 `v5.6.0`、ev-* 正文 `v1.x.y`）；**不在门禁扫描范围** | ⚠ 手动 |

> **⚠ 正文内嵌版本号同步义务（P3-1 实证，2026-10-16）**：版本号除 frontmatter `version:` / CHANGELOG 外，还会以"正文内嵌引用"形式出现（如收尾正文写 `v5.6.0`、ev-* 正文写 `v1.6.0`）。**版本一致性门禁只扫描 frontmatter `version:` vs 各自 CHANGELOG 最高版本，不扫描正文内嵌版本号**——收尾正文 `v5.6.0` 曾两次漏过 23/23 门禁。改版本时**必须全仓 grep 旧版本号**（`v5.x.y` / `v1.x.y`）逐一核对正文引用并同步，此为人工义务，门禁不可代查。

## 6. 可疑文献机制（唯一权威）

| 载体 | 位置 | 状态 |
|---|---|---|
| 唯一权威 | `ev-variant-literature-patient/SKILL.md`（L1/L2/L3 分级 + 挂载默认可疑 + 强制上报） | ✓ |
| 各子技能引用段 | `ev-*`/调度 中"引用唯一权威"一行（不得写独立取舍结论） | ✓ 已收敛 |
| **改判定标准时必须同步** | 唯一权威 SKILL + 各子技能引用行（仅措辞引用，不复制规则） | — |

## 7. 提交门禁（P5）

改任何引擎/解析/金标准数据前，先跑：
```
python -m py_compile <package>/**/*.py     # 语法
python regression_gate.py                    # 回归：FAIL=0 且 SKIP=0
python contract_test.py                      # 契约：FAIL=0（现含 BA1 4d-4f + 负向 5a-5c）
```
门禁不过 → **先回滚，不在红的状态上继续改**。

## 8. PM2 永久固定裁定（D9′，2026-10-15 用户拍板确认）

| 载体 | 位置 | 状态 |
|---|---|---|
| 判定规则 | `ev-pm2/SKILL.md`（永久 `PM2_Supporting`，不得取 Moderate/Strong） | ✓ v1.4.1 |
| 收尾分值表 | `acmg-conflict-summary-output/SKILL.md` §0.4（PM2 行标注仅 Supporting(+1)） | ✓ v5.5.1 |
| **非 Supporting 等级兜底（F1 cap + F1′ 对称 + F6 留痕，v5.5.1）** | `scripts/acmg_combine.py`（`PM2_FIXED_LEVEL="Supporting"`，dict+list 双分支 PM2 合法升级等级 **VeryStrong/Strong/Moderate → 封顶 Supporting 计入（cap，skip=False，note + `capped:True`，combine() 输出含 `capped` 字段、CLI 可见）**；standalone 等非合法等级 → skip。不整条丢弃（v13 曾错用 skip 致 162 组低估；v5.5.0 漏 VeryStrong 致 54 组，已对称修复）；门禁 `regression_gate.py` 2c `run_pm2_fixed`（含 VeryStrong 用例）+ `contract_test.py` 5e/5f + items 层 + F6 CLI 断言） | ✓ v5.5.1 |
| 历史记录 | `ev-pm2/CHANGELOG.md` v1.4.1 + 收尾 CHANGELOG v5.5.1 | ✓ |
| **改 PM2 强度/兜底时必须同步** | ev-pm2 + 收尾分值表 + 引擎门控(cap) + 两处 CHANGELOG + 契约文档(input-schema) + 输出契约(capped) + 门禁断言 | — |

## 9. build 侧脚本副本同步（**已废除，2026-10-15 D30**）

> **现状（D30）**：build 侧副本已删除，`build_package_20261015.py` 的回归/契约门禁改为**直接跑权威源 `scripts/` 下脚本**（四脚本已 `HERE=dirname(abspath(__file__))` 可重定位）。**不再存在"build 侧副本"这一事实源**，故本组同步义务作废，仅留此条说明防误以为仍需副本。
> 若将来门禁再出现"打包跑旧版"，根因改为"权威源脚本本身未更新"或"build 脚本路径指向错误"，不是副本不同步。

- 教训保留：**单一事实源原则**——复制单一事实源 + 人工清单同步 = 复发模式（本轮 D30 删副本即为此）；任何门禁脚本只有权威源一份，build 直接调用。

## 10. 阈值集中表 vs SKILL 内嵌表（循环约束：改一处必同步其余，2026-10-15）

**核心问题**：每个阈值同时写在"集中配置 + SKILL 内嵌可读表 + 确定性引擎"三处（都是双写/三写）。当前数值一致，但**没有任何强制同步机制**——改 `thresholds.json` 忘 SKILL 表即裂。历史教训：PP1 LOD 曾在 SKILL 表（J&B 0.6/1.2/1.5）与 thresholds（CMP-EP 0.9/1.5/2.1）不一致；**2026-10-20 已按用户拍板"通用=通用、特异=特异"分流**——通用位置一律 J&B 2016 原值 0.9/1.2/1.5，CMP-EP 档独立为 `pp1_lod_cmp_ep`（仅心肌病基因启用），不得再统一塞进通用位置。

| 阈值组 | 权威配置（改这里） | SKILL 内嵌表（必须同步） | 确定性引擎（必须同步） |
|---|---|---|---|
| REVEL 错义切点 | `config/thresholds.json`→`revel` | `ev-pp3-bp4/SKILL.md` §REVEL 强度对照 | `scripts/acmg_evidence.py` `revel_band` |
| SpliceAI 切点 | `config/thresholds.json`→`spliceai`（键 `v2_thresholds`） | `ev-pp3-bp4/SKILL.md` §SpliceAI2 映射、`ev-pvs1/SKILL.md` 剪接档位（均已标权威来源） | `scripts/acmg_evidence.py` `spliceai_band` |
| PM3 反式打分 | `config/thresholds.json`→`pm3_score` | `ev-pm3/SKILL.md` §计分表 | `scripts/acmg_evidence.py` `pm3_points` |
| PM3 VCEP 基因特异档位（**特异=特异**：FA 档 1/2/4/8→ATM/PALB2/FOXN1；BRCA1/2 条件式+封顶 Strong；LDLR 封顶 Moderate；其余标准档） | `clingen-vcep/knowledge-base/VCEP-<gene>.md` `#### PM3` 段（单一权威源，不落库） | `ev-pm3/SKILL.md` §第 2.8 步路由协议 | `scripts/acmg_evidence.py` `pm3_vcep_band`（spec 切点 + max_band 封顶） |
| PP4 VCEP 基因特异档位（**先查数值后匹配**：点数型→ADA/DCLRE1C/IL2RG/JAK3/IL7R/RAG1/RAG2/FOXN1/RMRP/RPGR/RPE65/GUCY2D/GAMT/GATM/OTC；MSI 计数→MLH1/MSH2/MSH6/PMS2；LR 型→BRCA1/BRCA2；条件式/纯表型→路由读原文核临床条件；通用表型特异→Supporting） | `clingen-vcep/knowledge-base/VCEP-<gene>.md` `#### PP4` 段（单一权威源，不落库） | `ev-pp4/SKILL.md` §第 3.5 步路由协议 + 先查数值硬步骤 | `scripts/acmg_evidence.py` `pp4_vcep_band`（points/count/lr + phenotype 回退 + max_band） |
| PS4 VCEP 基因特异档位（**先查数值后匹配**：计数型→ABCD1/ACVRL1/ENG/CDH1/F8/F9/LDLR/MYO15A/MTM1 等；点数型→APC/PTEN/FBN1/DICER1/FOXN1/IL2RG/AKT3/MTOR/BRAF/KRAS/HRAS 等；病例对照/条件式→MYH7/MYBPC3/ATM/BRCA1/BRCA2/HBB/HBA2/MECP2/KCNQ1 等（OR 须配合 CI）；通用先证者数→≥2/≥6/≥15） | `clingen-vcep/knowledge-base/VCEP-<gene>.md` `#### PS4` 段（单一权威源，不落库） | `ev-ps4/SKILL.md` §第 3.5 步路由协议 + 先查数值硬步骤 | `scripts/acmg_evidence.py` `ps4_vcep_band`（count/points + phenotype 回退 + max_band；ps4_band 收敛为通用） |
| PP1 共分离 LOD（**通用 J&B 2016 原值 0.9/1.2/1.5，3/4/5 减数分裂**） | `config/thresholds.json`→`pp1_lod` | `ev-pp1/SKILL.md` §第 2 步强度（通用=通用，明确标注特异档另列） | `scripts/acmg_evidence.py` `pp1_lod_adxl/pp1_lod_ar`（通用分支） |
| PP1 CMP-EP 疾病特异档（仅心肌病基因启用、默认不启用，0.9/1.5/2.1） | `config/thresholds.json`→`pp1_lod_cmp_ep` | `ev-pp1/SKILL.md` §第 2 步分流说明（CMP-EP 基因走此档） | `scripts/acmg_evidence.py` `pp1_lod_adxl`（传 gene 命中 `_in_cmp_ep` 自动走） |
| PP1 HL VCEP AR 专用（v1.6.2：受累个体数含先证者、受累分离数=个体数−1） | `config/thresholds.json`→`hl_vcep_pp1` | `ev-pp1/SKILL.md` §第 4 步官方矩阵闸（0.6/1.2/1.5，Oza et al. 2018 Table 4a/4b ↔ HL VCEP v2 General Recommendations 表，PMID 30311386） | `scripts/acmg_evidence.py` `pp1_lod_hl_ar`（指数 0.25^(affected−1)；`pp1_lod_ar` 传 gene 自动命中） |
| 证据等级分值 | `config/thresholds.json`→`score` | `acmg-conflict-summary-output/SKILL.md` §0.4 分值表 | `scripts/acmg_combine.py` engine_a/b |

**改任一阈值时必须同步**：对应 SKILL 内嵌表 + 引擎 + 本清单；改前先 `grep` 该数值在 `SKILL.md`/`acmg_evidence.py`/`acmg_combine.py` 出现处逐一核对。

## 11. 文献呈现输出契约（L1 层，v5.5.3→v5.5.4，2026-10-16）

**核心**：最终评级输出的文献相关证据，凡依赖文献/数据库条目 → **必须成对输出「PMID + URL」**（文献 URL 统一 `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`，数据库条目给条目链接）；只给号缺链接、或给链接缺号 = 三点缺失回补。确不依赖文献的证据（纯家系谱共分离/纯人群频率/纯功能实验原始数据）→ 显式标注来源 + 注明"无 PMID（非文献来源）"；禁止捏造、禁止"无链接/待补"含糊。

**v5.5.4 结构化扩展**：PM3/PP1 的文献类证据按**逐例结构化模板**输出——PM3 逐患者（症状/正反式/相位/另一变异/P-LP 确信/自评或文献/PMID+URL），PP1 逐家系（规模/携带人数/是否受累/表型/PMID+URL）；未给出字段写"未给出"。

| 载体 | 位置 | 状态 |
|---|---|---|
| 收尾规则 | `acmg-conflict-summary-output/SKILL.md` §3 输出模板（文献呈现强制规则段 + PM3/PP1 结构化引用）+ §3 第0点引用 + §4 自检清单 | ✓ v5.5.4 |
| 子技能模板 | `ev-pm3/SKILL.md` 第 2 点（PM3 逐患者）、`ev-pp1/SKILL.md` 第 2 点（PP1 逐家系） | ✓ ev-pm3 1.12.0 / ev-pp1 1.6.2 |
| 历史记录 | 收尾 CHANGELOG v5.5.4 + ev-pm3 v1.11.0 + ev-pp1 v1.5.0 | ✓ |
| **改文献呈现口径时必须同步** | 收尾 §3 规则段 + 第0点引用 + §4 自检 + ev-pm3/ev-pp1 第 2 点模板 + 本清单 + 三处 CHANGELOG | — |
| **v1.12.0 相位/大队列/降级根治（同步义务）** | ev-pm3 §2.5 大队列补充表专项（行错位/去重/同家系） + §2.5 PubMed 降级路径（PMC/PDF/挂载 + PMID↔PMC 核对） + 三态"家系共分离≠confirmed in trans"硬闸 + 验证来源二选一 + §4 自检 + CHANGELOG | ✓ ev-pm3 1.12.0（计分表/累分映射/引擎不变） |
| **v5.5.5 confidence 流程完成度降档（同步义务）** | 收尾 §2.4 confidence 强制降档闸（三跳步情形→low）+ §4 自检 + CHANGELOG；配套 ev-ps1-pm5 条件3 查证绑定（1.3.2）+ ev-ps4 先证者独立性核对（1.2.3） | ✓ 收尾 5.5.5 / ev-ps1-pm5 1.3.2 / ev-ps4 1.2.3 |
| **v5.5.6 表5新增"1 VS + 1 SU → LP"（同步义务）** | 收尾 §2.1 LP 规则（或 1 PVS1+1 PP，用户拍板口径）+ `scripts/acmg_combine.py` `_classic_likely_pathogenic`(i′)/`_lp_rules` | ✓ 收尾 5.5.6（Tavtigian 分值引擎/互斥/官方优先/confidence 不变） |
| **v5.5.7 contested 强制闭环闸（同步义务）** | 收尾 §3 第0点后加"contested 强制闭环闸"（标争议的码结算前二选一：转确信/降一档或剔除，结算集合不得含"contested 且保留原档"）+ §4 自检 + CHANGELOG；防误伤 REVEL/PM2 确信；引擎零改动 | ✓ 收尾 5.5.7 |
| **ev-pm1 v1.1.0 约束取数 fallback（同步义务）** | ev-pm1 新增"约束取数 fallback 分支"（RMC NOT FOUND 识别类型 → 缺数据≠反对（引用 ev-gnomad-constraint §56）→ 同轮切 DECIPHER 基因级+机制+结构域热点文献 → 能定即确信/取不到才查不到 → 漏做≠查不到）；引用 ev-gnomad-constraint 为"缺数据≠反对"唯一权威，本技能不内嵌重复 | ✓ ev-pm1 1.1.0 |
| 不改引擎 | 组合层不接受过程记录/文献（input-schema §1），引擎/regression/contract 零改动 | ✓ |

## 12. 评级归档跨设备云盘同步

> 云盘做评级归档共享层：本地 `result` 目录 ↔ 云盘 archive 文件（`acmg_result_archive.json`），跨设备自动同步。合规边界（用户确认）：仅同步 result 评级结论（单变异位点评级），不含患者报告/身份信息。

| 载体 | 位置 | 状态 |
|---|---|---|
| 归档载体（唯一权威） | 云盘 file-token `LKjSbAkpRoOYMixWyfYc022unsd`（url `https://my.feishu.cn/file/LKjSbAkpRoOYMixWyfYc022unsd`）；本地 archive 临时文件 `<TEMP>/acmg_result_archive.json`（lark-cli allowlist 允许 Temp，`_cache` 不在允许范围故一律走临时目录） | ✓ v5.6.1 |
| 引擎合并 | `scripts/acmg_cache.py` v1.4.0（`sync --ns result --to-archive/--from-archive/--merge-upload`，rated_at/stored 新者胜、幂等、原子写，`_entry_newer` 确定性判断；**`--merge-upload`=上传前先 from-archive 把云盘全量并回本地（本地 ⊇ 云盘）再 to-archive 生成含云盘全量+本地新增的上传 archive，archive 缺失→NO_LOCAL_ARCHIVE 拒绝覆盖上传**） | ✓ v1.4.0 |
| 收尾上传 | `acmg-conflict-summary-output/SKILL.md` §3.5.1（v5.6.1 防丢：上传前 `download` 重新拉云盘副本→`sync --merge-upload`→`upload` 覆盖；云盘不可达放弃覆盖上传、NO_LOCAL_ARCHIVE 拒绝覆盖）+ §4 自检清单 | ✓ v5.6.1 |
| 调度拉取 | `acmg-total-scheduler/SKILL.md` 评级前云盘归档拉取合并（`lark-cli drive +download` + from-archive，放在"评级结果归档命中检查"之前） | ✓ v4.13.0 |
| 历史记录 | 收尾 CHANGELOG v5.6.1 + 调度 CHANGELOG v4.13.0 | ✓ |
| 边界（写死） | 只同步 result 评级结论快照，查询缓存（gene_disease/vcep/genebe/freq/revel）不上云；失败不阻断评级（记录 warning，按本机继续，下次再同步）；**防丢闸：上传前 download 云盘副本失败→放弃覆盖上传保留云盘原文件；`--merge-upload` 返回 NO_LOCAL_ARCHIVE→拒绝覆盖上传——绝不用本地不全归档覆盖冲掉云盘权威归档**；新者胜、幂等；合规=仅单变异位点评级结论 | ✓ |
| **改载体/file-token/同步口径时必须同步** | acmg_cache v1.4.0 + 收尾 §3.5.1/自检 + 调度拉取 + 本清单 + 两处 CHANGELOG + 全仓 grep file-token | — |

## 13. 新增脚本 / 随包产物登记（2026-10-22）

> **义务**：任何随包新增的脚本或产物目录，必须在此登记并同步至 README「随包门禁与自检」表，避免"文件在包里但清单查不到"（v27 补齐自检 D 项）。

| 载体 | 位置 | 状态 |
|---|---|---|
| LLM 闸门契约测试 | `scripts/test_llm_gate.py`（v1.5.0 配套，G1-G5；已加 sys.path 自处理，无需 PYTHONPATH） | ✓ README 已收录 |
| LLM 提取校验层（v1.6.0） | `ev-variant-literature-patient/main.py` 新增 `_validate_extraction`（C1/C2/C3）+ `scripts/test_extraction_validation.py`（V1-V8）；SKILL.md/CHANGELOG/README 版本锚定均升 1.6.0 | ✓ README 已收录 |
| clingen-vcep 结构化校验 | `scripts/check_vcep_structure.py`（C1-C4；默认 root 已相对定位） | ✓ README 已收录 |
| 复审/校验产物 | `reviews/`（当前实际产物 `vcep_structure_*.md/.json`；复审报告 `review__review_v27_*` 未随包，不在此列） | ✓ README 已收录 |
| 版本对齐（v27 补齐） | `ev-variant-literature-patient` 1.3.1 → **1.6.0**（SKILL.md frontmatter + CHANGELOG + README 版本锚定三处已同步） | ✓ |
| HGMD 可选配置闸门（v1.7.0） | `ev-variant-literature-patient/main.py` `search_hgmd` 缺脚本返回可识别状态 `missing_config`（完整缺失提示+配置指引）+ 新增 `HGMD_SKIP=1` 显式跳过（`skipped_user_opted_out`），main 完整打印缺失提示不静默；`ev-variant-literature-patient` 1.6.0 → **1.7.0**（SKILL.md frontmatter + CHANGELOG + README 版本锚定三处已同步） | ✓ README 已收录 |
