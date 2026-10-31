# ev-ps1-pm5 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.6.0（同位点同一性核验硬闸，2026-10-24 APOE 判例复盘）

- **新增第 2.5 步：同位点同一性核验硬闸**——PS1/PM5 的前提是"两个变异真的在同一个物理位点上"，位点不对齐整个证据就不成立。
- **三条核验规则**：
  1. 字面对齐优先：查到的已知致病变异 p.HGVS 位点与送检变异字面一致，直接采信。
  2. 编号不一致时必须双编号映射坐实：若文献/数据库里的位点编号与送检变异字面不一致（旧编号/成熟蛋白编号/不同转录本），必须找到同一文献或权威数据库同时写出两个编号，才能判定为同一物理位点；找不到则不计入 PS1/PM5。
  3. 禁止心算偏移对齐：禁止靠"信号肽约 N 个氨基酸""转录本差几位"手算对齐文献位置——编号偏移必须由文献原文或权威数据库给出双编号映射才算数。
- **反面判例（APOE 2026-10-24，与 PS4 同源）**：APOE c.480_488del p.Leu162_Lys164del（Tokyo/Maebashi）。摘要写 residues 142–144，手算信号肽偏移≈18 认为差 2 位"可能是同一个位点"——实际上 PMID 35761986 白纸黑字写了双编号映射：traditional 142_144 = MANE p.Leu162_Lys164del。
- **自检清单新增一条**：已完成同位点同一性核验——每篇计入的已知致病变异位点编号字面一致，或已找到双编号映射，未用心算偏移对齐。
- 纯流程层改动，不改引擎、不改 VCEP 路由、不改通用档位表。

## v1.5.0（元素解耦：PM5 计数升级移出通用函数，2026-10-24 COL2A1 判例复盘）

- **根因**：通用函数 `ps1_pm5_band` 里内置了 `other_p_count >= 2 → PM5_Strong` 分支，把 VCEP 路由层的计数逻辑混进了通用基本单元，违反"元素解耦，路由关联"八字方针。
- **问题**：COL2A1（无 VCEP 文件）按"通用=通用、特异=特异"铁律应走通用规则，但通用函数自带 Strong 分支导致过度取档——把 VCEP 才有的"≥2 个 P 升 Strong"套到了无 VCEP 的基因上。
- **修复（方案 A，最干净）**：
  1. 删掉 `ps1_pm5_band` 里 `other_p_count >= 2 → PM5_Strong` 分支；
  2. 通用 PM5 只输出：已知 P → PM5_Moderate；已知 LP → PM5_Supporting；最高 Moderate，不得升 Strong；
  3. 计数升级（≥2→Strong）完全交给 `pm5_vcep_band` 路由函数，只有 VCEP 基因有此规则时才生效；
  4. SKILL.md 强度调节表删除"PM5 上调"行，明确标注"≥2 个 P→Strong 是 VCEP 特异规则，不是通用规则"；
  5. 加反面判例：COL2A1 无 VCEP 文件，PM5 应为 Moderate(+2)，不该因"同一位点有 2 个其他 P"就升 Strong。
- **影响范围**：纯流程层/引擎层改动，不改 VCEP 路由逻辑、不改通用档位表、不改输出格式。
- **自检**：通用 `ps1_pm5_band(False,"P")` 返回 `PM5_Moderate`；VCEP 路由 `pm5_vcep_band(2,"TP53",spec)` 仍返回 `PM5_Strong`。

## v1.4.0（PS1/PM5 VCEP 路由方案，2026-10-20）

- **全量探查（Windows 重建工作区）**：134 个 VCEP 基因文件 **131 个含 `#### PS1` 段、131 个含 `#### PM5` 段**；PS1 形态——98 条件式 + 31 通用 Richards + 2 档位（SGCA/TP53）；PM5 形态——84 条件式 + **39 计数档位** + 8 NA + 3 无段。
- **关键形态结论**：PS1 本质是"本变异与已知致病变异**同氨基酸改变**"的**语义判定**（查 ClinVar 比对），VCEP 的"特异"主要是附加条件（剪接排除、旁系同源扩展如 BRAF/KRAS、同机制要求如 SGCA SpliceAI≤0.10）——**不做数值引擎**；PM5 有 **39 个计数档位基因**（≥N 个同密码子已知致病错义→档位，如 TP53 ≥2→Strong/1→Moderate/1LP→Supporting、LDLR/BRAF/KRAS ≥2→Strong/1→Moderate）——**可做计数引擎**。
- 新增【PS1/PM5 VCEP 路由读取协议】第 3.5 步：查索引→读 PS1/PM5 段→判定形态→PM5 计数档位喂引擎 `pm5_vcep_band`、PS1 按原文核验附加条件、条件式用通用 ps1_pm5_band、NA 写不成立、纯通用回退。
- 引擎新增 `pm5_vcep_band(n_known, gene, spec)`：复用 `_bs2_band_match`（加 code_prefix="PM5" 参数，输出 PM5_ 前缀），spec 形态 `{"type":"band","bands":{"strong":2,"moderate":1,"supporting":1},"unit":"known_pathogenic"}`，从高到低取最高达标档，返回 `PM5_Strong/PM5_Moderate/PM5_Supporting` 或 None；已注册 CLI。通用 `ps1_pm5_band(same_aa, known_class, other_p_count)` 保留不动。
- **PM5 取数前提（写死）**：穷尽检索同密码子已知致病错义变异数（ClinVar/HGMD/PubMed/GeneBe 多通道）；VCEP 附加限定（TP53 Supporting 需已知 LP 带临床数据、BRAF/KRAS Strong 需 ≥5 probands）由执行者判，引擎只做计数主档。
- 自检清单新增【PS1/PM5 VCEP 路由闸（v1.4.0）】：评 PS1/PM5 前必走路由，VCEP 有 PM5 计数档位则用 VCEP，PS1 按原文核验附加条件，条件式用通用，NA 写不成立；禁止凭手抄漏查。

## v1.3.2（PM5 条件3 查证绑定，2026-10-16 用户复盘"争议实为跳步"）

- **根因**：评级实证 Y3900F——PM5 的"已知变异分类标准不依赖 PM5"条件用逻辑推理（"PM5 只有 Moderate 撑不起 Pathogenic，所以必有独立证据"）替代实际查证 Y3900F 的 criteria 与挂载文献。
- **条件 3 补"查证绑定"**：必须实际列出该已知致病变异使用的证据码/支撑文献（独立由 PS3/PM2/PP1 等定级，非依赖 PM5 自己）；不得用逻辑推理替代；未查证 → 该码标"待核验"，收尾 confidence 按"流程完成度不足"强制 low（衔接收尾 v5.5.5）。
- 纯流程/契约层改动，不改判定表、不引擎。

## v1.1.0

- 新增【文献核验+可疑文献上报】强制子步骤（第2步查 ClinVar/HGMD 同位点已知致病变异及其挂载文献一律默认可疑，核验通过前 PS1/PM5 标注待全文核验）

## v1.2.1

- 补跨技能引用声明——凡本技能判定依赖文献检索/核验时，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」与按用途差异化提取；本技能 description 显式声明该跨技能依赖，不再隐式引用。

## v1.3.0

- 新增第 2 步【同位点错义穷尽检索】硬步骤（整改 PM5 漏用，实证 var009 TYR / var010 G6PD / var011 GNE / var013 ATP7B——技能群曾因"查不到"漏计 PM5 导致错义位点偏低）——判定 PM5 前必须穷尽检索"同一密码子/同一氨基酸位置其他氨基酸改变"（ClinVar+HGMD+PubMed+GeneBe 同蛋白位置变体列表多通道），逐条列同位置 P/LP 变异，判定完成闸：同位点检索未走完三通道或未逐条记录，不得定 PS1/PM5 不成立。

## v1.3.1（全局维护收敛整改）

- 可疑文献判定完整标准（L1/L2/L3 分级 + ClinVar/HGMD 挂载默认可疑 + 强制上报）收敛到唯一权威 `ev-variant-literature-patient`，本技能仅保留按用途定制提取要求，不再内嵌重复完整段。
