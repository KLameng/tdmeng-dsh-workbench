# acmg-conflict-summary-output CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v5.6.7（归档结构升级：两池 + 溯源 + deps_version，2026-10-22）

- **两池架构落地**：`evidence_items` 每条新增 `pool`（评级池 `rating` / 提示池 `hint`）——指南合规证据进评级池（进引擎参与评级）、指南外相关性信息进提示池（作人工最终评估的弹性证据、不参与评级）；对应用户"两池架构"决策。
- **证据溯源**：`evidence_items` 每条新增 `source_url`（来源 PMID/URL）+ `l1_skill_version`（来源子技能版本），补全证据可回溯。
- **deps_version 审计字段**：归档新增 `deps_version`（本次评级依赖版本，如 `requests-2.34.2+pyliftover-0.4.1`；锁文件给构建用、deps_version 给审计用）；**可选、旧条目缺它仍有效**（向后兼容）。
- **确定/争议分级**：`confidence`（确信/有争议）已在 v5.3.4 存在，本次**不重复添加**。
- 全部为归档 schema 的**增量新增**，不改变既有字段（final_class / confidence / rated_at / skills_version / data_snapshot）语义，不引入新问题。

## v5.6.6（G5 双套并列闸衔接，用户体系化指令"用边界制约模型不可靠"落地）

- **新增 §0 前置衔接**：本收尾为**G5 双套并列闸落点**——方案A 表5 + 方案B Tavtigian 各自输出、并列展示、不取值归一、不做取舍（引用调度层 v4.15.0 前置规范层门禁）。与既有 §2.3 双套并列、不取值归一规则（v5.6.2 用户拍板）一致，仅补显式门禁落点声明，**未改动任何既有双套/取值规则**，不引入新问题。
- **description 补铁律**：全程证据依据来自知识图/阈值表/实时查询，禁止用训练记忆自由裁定；G5 双套并列闸落点在此。

## v5.6.5（变异身份前置闸 + 证据码三态 + 报告跨基因疾病名校验，2026-10-19 措施②④落地，衔接 ev-variant-standardization v1.1.0）

- **根因**：171 盲测缺陷 C——"假设极低频"顶替真实查询、未核验当已查就计分；"评级总不往深里走"（能核验却不核验）。措施①先立身份硬闸后，收尾须承接。
- **新增变异身份前置闸**：进入收尾前输入清单必须带 `identity_status`；`blocked`（变异类型无法判定 / 蛋白改变类缺 p.HGVS）→ 收尾拒绝定级，停留在身份归一化环节待人工复核；`data_gap` → 标待核，走"缺数据≠反对"规则。
- **新增证据码三态（确信/推断/未核验）**：把 v5.5.7「有争议」细分为两态——**推断**先强制补查（读 ClinVar submission 明细 + 多提交者交叉确认 + 补全文/补数）再判，补查未坐实才降一档计；**未核验**不计分剔除。禁止把"我没查"包装成"推断"。
- **新增报告跨基因疾病名校验（措施④）**：报告疾病名必须与所评基因已知疾病/表型关联一致，禁止跨基因疾病名、不引入新来源；关联存疑标"待核"。交付自检每个疾病名须可回溯基因关联证据。
- **与既有规则关系**：三态是 contested 的细分，进入结算的所有码不得存在"推断/未核验且保留原档位"；v5.5.7 闭环闸、v5.6.3 多提交者信任、防误伤口径均保留不冲突。combine 引擎不改（收尾层把关输入清单）。

## v5.6.4（PS3↔PP3 专门取舍规则修正，2026-10-19 v20 审计 N3 处置）

- **根因（v20 审计 N3，实测有效）**：v5.6.3 的"PS3↔PP3 无论档位一律保留 PS3、弃 PP3"被审计实测出**只降不升**（如 PS3_M+PP3_VS 并存=LP/P，弃 PP3 后=VUS，最深降 3 级）——本质是"证据丢弃"而非"互斥取舍"，且与 §2.3「禁止静默取保守档」「不得以保守为名压权已确证证据」矛盾。我上轮把用户"PS3_Strong 弃 PP3_Strong（同分取功能实验）"原意扩写成了"含分值反转一律保留 PS3"，扩写过头。
- **修正（v5.6.4）**：改为——**档位相同时优先保留 PS3（同分取功能实验，尊重用户原意）；档位不同时仍按通用"保留分值高者"裁决**（PS3_Supporting vs PP3_Strong → 保留 PP3_Strong，不因 PS3 类别固定优先压掉更强 PP3）。只限定 PS3↔PP3 这一对，其他互斥对仍按通用 §1.2 表。消除只降不升副作用。
- **不引入新问题**：§1.2 表（PS3(4) vs PP3(1)→保留 PS3）与示例（PS3(4)≫PP3(1)）与本修正一致（PS3 高时保留 PS3），无需改；PM1+PP3 封顶、其他互斥对不受影响。
- **版本**：收尾 **5.6.3→5.6.4**；引擎/ev-* 未因本条动。

## v5.6.3（多提交者信任 + PS3↔PP3 固定保留 + PM3–PS4 防重复 + PM3/PS4 证据话术固定格式，2026-10-16 用户复盘 5 条修法）

- **根因（用户复盘两个位点评级问题，5 条）**：①把"自己没读全文"当"证据有争议"（四家独立实验室读全文均给 P、评论含酶活 0-5%/7 先证者/3 同胞共分离）；②PS3 强度给低（成纤维细胞酶活 0-5% 只给 Supporting）；③PS3↔PP3 互斥反复摇摆；④PM3 与 PS4 重复计入同一批先证者；⑤contested 标签滥用。用户要求流程根治、不引入新问题。
- **落地（本 SKILL 三处 + ev-ps3/ev-ps4 各一处）**：
  - §3 第0点防误伤段后新增**「ClinVar 多提交者数据信任规则」**（修法1+5①）：≥2 家**独立**机构提交者（criteria provided，非同一集团）评论中明确列出的硬数据（病例数/合子/酶活/共分离）直接采信为确信，未读全文不构成 contested 理由；信任的是具体数据而非其 P/LP 分类结论；挂载 PMID 文献仍走可疑文献上报；只有分类无明细不适用；提交者互相矛盾才标 contested；**强制动作=疑似 contested 先读 submission 明细再判（防"评级总不往深走"）**。
  - §1.1 新增**「PM3–PS4 重复计入提醒」**（软提醒，修法4）：PM3 已逐例累分的患者 PS4 不得重复使用；PS4 须基于独立病例对照统计（AR 须 OR>5 且 CI 不含 1；AD/XL 独立先证者数）；仅文献零散报道或与 PM3 同批患者不构成 PS4 独立证据。
  - §1.2 新增**「PS3↔PP3 专门取舍规则」**（修法3）：无论双方实际档位（含分值反转），一律保留 PS3、弃 PP3（功能实验直接测量 vs 计算预测间接推断，证据层级不同不按分值比较）；只限定该对，其他互斥对仍按通用"保留分值高者"。
  - §3 新增**「证据话术固定格式」**（用户新要求）：采用 PM3 时强制输出隐性 PM3 话术、采用 PS4 时强制输出显性 PS4 话术（句式固定、[] 内填实际查得数据、禁止保留示例值、未给出写"未给出"）；PM3/PP1 逐患者结构化模板不变。
  - §4 自检清单补 2 项（多提交者信任 + 话术）。
- **REVEL/PM2 不标争议（修法5②③）**：v2.1 用户拍板已存在，本次仅确认表述一致，未重复新增。
- **版本**：收尾 **5.6.3**；ev-ps3-bs3 **1.5.0**、ev-ps4 **1.3.0**；引擎未动（话术/信任/固定保留 PS3 均为 SKILL 层判定）。

## v5.6.2（去掉点数法优先仲裁，回到两套并列+定位：表5=现行报告 / 点数法=未来布局，2026-10-16 用户方法论拍板）

- **根因（用户方法论裁定，整体否决取值归一）**：v5.5.8 W1 仲裁条款"两套不一致时最终分类以方案B Tavtigian 分值为准（点数法优先）"被用户否决——用户明确定位：**表5 是现行报告方法（报告必须用），点数法（Tavtigian 分值）是比表5 更准确的结论但应用于报告是在未来，当前设计点数法属于布局；两种是不同的计算方法，不横向对比、不取值归一**。故"取值归一 / 点数法优先仲裁"整层移除，回到收尾 §2.3 原始"两套独立定级、分别输出、不强行合并"语义，并补两套定位声明。
- **落地**：
  - 收尾 `SKILL.md`：description 去掉"点数法优先仲裁"、改两套定位（方案A 表5=现行报告方法、报告结论采用方案A【官方/共识已定级时按 §0 官方优先采用官方分类】；方案B 点数法=未来方法布局、不参与现行报告结论）；§2.3 补定位声明、③"点数法优先仲裁"条款删除（改为并列输出+标注两代方法差异、不取值归一，④边界联动保留）；§3 输出模板"最终分类（仲裁）"行改为"两套定位与呈现"；§4 自检清单仲裁项替换为两套并列+定位项；version 5.6.1→**5.6.2**。
  - 引擎 `scripts/acmg_combine.py` v20261015c→**v20261015d**：`combine()` 删除 `arbitrated_result`/`arbitration` 单点最终分类字段，改输出 `positioning`（scheme_a=现行报告方法 / scheme_b=未来方法布局 / comparability=不横向对比不取值归一）+ 保留 `agreement` 并列信号；`main()` CLI 打印改为两套定位+不取值归一说明。**engine_a/engine_b 各自定级逻辑、表5 规则、Tavtigian 区间、互斥、官方优先、confidence 均不变**。
- **订正 v5.5.8 归因（P2-1）**：v5.5.8 声称"39 集唯一 1 条不一致即 VCEP 点数表来源"，实测为 **var008（UGT1A1）单条 BP4_Moderate（良性侧单条良性码）**，与 VCEP 点数表 / (ii)≥2ST 无关；该仲裁条款现已整体移除。
- **验证**：contract_test 新增负向断言（combine() 输出含 engine_a/engine_b/agreement/positioning、不含 arbitrated_result/arbitration 单点最终分类键）；回归 PASS（agreement 97.4% 不变，engine_a/b 各自结果不变）；py_compile 过。
- **版本**：收尾 **5.6.2**、acmg_combine **v20261015d**；调度/ev-* 未动。

## v5.6.1（归档同步防丢加固：合并上传，2026-10-16 用户自查"是否引入新问题"指出）

- **根因（v5.6.0 引入的真实缺口，用户审查发现）**：v5.6.0 的上传动作是"本地 result → `sync --to-archive` → `upload` 覆盖云盘"。当**评级前云盘拉取失败**（新设备本地 result 为空/不全，且边界写"失败不阻断评级"）时，本次评级后 `to-archive` 会生成**只有本地不全条目的 archive**，`upload` 覆盖会把**云盘权威归档冲掉、丢异地已评结论**。sync 测试 5 场景只测了拉取（from-archive）合并，未覆盖"上传覆盖在本地不全时的防丢保护"。
- **根治（上传改为"先合并再覆盖"）**：
  - 引擎 `acmg_cache.py` v1.3.0→**v1.4.0** 新增 `sync --ns result --merge-upload <ARCHIVE>`：内部**先 `from-archive` 把云盘全量并回本地 result（本地 ⊇ 云盘）→ 再 `to-archive` 生成含"云盘全量+本地新增"的上传 archive**（rated_at 新者胜、幂等，复用已测合并语义）；**本地无云盘副本（archive 缺失）→ 返回 NO_LOCAL_ARCHIVE，拒绝生成覆盖归档**。
  - 收尾 §3.5.1 上传动作改为三步：①上传前 `lark-cli drive +download` 重新拉取云盘副本（**云盘不可达/下载失败 → 本次放弃覆盖上传、保留云盘原文件**，评级结论仍落本地 result，下次再同步）；②`sync --merge-upload`（NO_LOCAL_ARCHIVE → 拒绝覆盖上传）；③`upload` 覆盖云盘（archive 已含云盘全量+本地新增，覆盖不丢）。
  - 边界补**防丢闸**：绝不允许用"本地归档不全"覆盖冲掉云盘权威归档。
- **验证**：merge-upload 专项测试（本地新增不丢云盘全量 / 新设备本地 1 条+云盘副本→archive=云盘全量+1 / archive 缺失→NO_LOCAL_ARCHIVE 拒绝 / 幂等）；py_compile + 回归 + 契约全过。
- **版本**：收尾 **5.6.1**、acmg_cache **v1.4.0**；调度 **4.13.0**（评级前拉取逻辑不变）；ev-* 未动。

## v5.6.0（评级归档跨设备云盘同步，2026-10-16 用户拍板"上传云盘，新会话能读到存档"）

- **根因/需求**：评级归档 `result` 原本仅存本机 `_cache/result`，新评级会话读不到另一设备/异地评过的归档。用户确认场景=**跨设备/异地共享**、同步方式=**自动同步（固化进流程）**；并确认归档仅含单变异位点评级结论、不含患者报告/身份信息，不涉及医疗合规问题。
- **acmg_cache.py v1.2.0→v1.3.0（新增 sync 合并能力，纯 Python，引擎不耦合外部 CLI）**：
  - `sync --ns result --to-archive <ARCHIVE>`：本地 result 目录 → archive 文件（`{"<hash>.json": {value, expire, stored}}`），rated_at/stored 新者胜、幂等、原子写；
  - `sync --ns result --from-archive <ARCHIVE>`：archive → 本地 result，新者胜、幂等，本地更新条目不被云盘旧条目覆盖（`_entry_newer` 确定性判断）；
  - 同步测试 5 场景全过（to-archive/幂等/同内容 kept_local/远端新增/远端更新覆盖/本地更新保留）。
- **云盘共享层载体（唯一权威）**：云盘文件 `acmg_result_archive.json`，file-token `LKjSbAkpRoOYMixWyfYc022unsd`（url `https://my.feishu.cn/file/LKjSbAkpRoOYMixWyfYc022unsd`），已含现有 6 条评级归档；本地 archive 临时文件 `<TEMP>/acmg_result_archive.json`（lark-cli allowlist 允许 Temp，`_cache` 不在允许范围，故一律走临时目录）。
- **固化进流程（新增 §3.5.1 + 调度层评级前拉取）**：
  - 收尾 §3.5.1 上传（定级写入 result 归档后）：`acmg_cache.py sync --to-archive` + `lark-cli drive +upload`（覆盖保留 file-token）；
  - 调度层（acmg-total-scheduler v4.13.0）评级前拉取（在"评级结果归档命中检查"之前）：`lark-cli drive +download` + `acmg_cache.py sync --from-archive`。
- **边界（写死，防同步引入新问题）**：只同步 result 评级结论快照，查询缓存（gene_disease/vcep/genebe/freq/revel）不上云；失败不阻断评级（下载/上传/sync 失败 → 记录 warning，按本机继续，下次再同步）；新者胜、幂等；合规边界=仅单变异位点评级结论。
- **版本**：收尾 **5.6.0**、调度 **4.13.0**、acmg_cache **v1.3.0**；ev-* 子技能本轮未动。

## v5.5.8（W1 仲裁条款：点数法优先，2026-10-16 用户拍板，技能群整体评估建议2）

- **根因（技能群整体评估 W1）**：两套引擎（方案A 表5 卡式 / 方案B Tavtigian 分值）无仲裁条款——`1VS` 单独（A=VUS / B=LP）、`≥2VS`（A=VUS / B=P）、ClinGen VCEP 点数表组合（如 PM3_S+PP1_S+PM2_S → 表5 (ii)≥2ST→P **过冲一档** / 分值 LP）全部分歧且无"最终采用哪套"的裁决。评估判定：点数表规则喂表5 卡式会系统性过冲一档，影响**所有 VCEP 点数表案例**（39 集唯一 1 条不一致即此来源）。
- **仲裁条款（点数法优先）**：两套结论不一致，且经 §2.3 ①回中间复核确认"证据确实不足"、无官方/共识裁定覆盖时，**最终分类以方案B Tavtigian 分值结论为准**——ClinGen SVI 2020 加权体系（Tavtigian 2020，PMID 32525297）官方推荐，比 2015 表5 更忠实反映证据强度相对权重；表5 对「VS 单独 / ≥2VS / VCEP点数表组合」无覆盖或过冲。方案A 并列保留（过冲/漏判可见），agreement 不一致信号不消失；**禁止静默取保守档**。
- **引擎同步**：`scripts/acmg_combine.py` combine() 新增 `arbitrated_result`（分歧时=引擎B result）+ `arbitration` 字段（method/applied/winner/note），CLI 打印"仲裁(点数法优先)：最终分类=…"。一致时仲裁不生效（arbitrated=一致分类，applied=false，零影响）。**agreement 信号、engine_a/b 各自输出、confidence 逻辑均不变**。
- **文档同步**：收尾 §2.3 新增③仲裁条款（原③边界处理→④）、输出模板加"最终分类（仲裁）"行、自检清单加仲裁项、description 补"两套不一致时以方案B为最终分类"。
- 门禁实测：契约 22/22；回归 PASS——39 集 agreement **97.4%(38/39) 不变**（仲裁不改引擎输出）、版本一致性 23/23；仲裁专项验证（1VS→LP、2VS→P、VCEP组合→LP、一致案例零影响）全部符合预期。
- 版本：收尾 **5.5.8**（引擎 acmg_combine.py v20261015b→c；子技能 ev-* 本轮未动）。
- ⚠ **本条仲裁条款已于 v5.6.2 移除**（用户拍板"不取值归一"，回到两套并列+定位）；"39 集唯一 1 条不一致即 VCEP 点数表来源"的归因经实测为 var008 UGT1A1 单条 BP4_Moderate（良性侧单条良性码），与 VCEP 点数表/(ii)≥2ST 无关（P2-1 订正）。

## v5.5.7（contested 强制闭环闸，2026-10-16 用户复盘"标了争议仍按原档计分"）

- **根因**：`有争议(contested)` 此前只做展示、不做约束——适用组标了 contested 的码仍按原档位计分进入结算（实证 PM5/PP1 均标 contested 却仍按 Moderate(+2) 结算），被当装饰标签。
- **落地**：收尾 §3 输出层第 0 点后新增「contested 强制闭环闸」，凡标 contested 的码进入结算前必须二选一：
  - 路径A 转确信：执行对应子 SKILL 完整核验（穷尽检索/LOD 逐家系/逐位点全位点/L1·L2·L3 文献分级+逐条 PMID+URL），核验通过按结果重定档转确信；
  - 路径B 核验不足：不得按原档计——确有一定证据但档位不能坐实 → 一律降一档计（VeryStrong→Strong→Moderate→Supporting）并标确信注明"因争议未核验，降档计"；证据完全不可核验 → 不计分、从证据池剔除。
  - **结算自检（写死）**：进入最终证据码集合/双套结算的所有码不得存在「contested 且保留原档位」。
- **防误伤（写死）**：已按官方区间裁定、来源无冲突、结论无保留的码不得标 contested（REVEL 擦边按 v2.1 确信、PM2 永久固定 Supporting 固定档位均不受影响）；本闸只约束 contested 码，certain 码零影响。
- **引擎零改动**：降档/剔除发生在收尾结算前，引擎 acmg_combine.py 收到的已是处理后的集合；表5/分值/互斥/官方优先/confidence 均不变。
- 版本一致性 23 对齐，39 集回归需实测。

## v5.5.6（经典联合规则新增"1 VS + 1 SU → LP"用户拍板口径，2026-10-16）

- **新增规则（用户拍板）**：方案A 经典联合规则（表5）结算新增一条——**1 VeryStrong + 1 Supporting → Likely Pathogenic**。收尾 §2.1 LP 规则补"或 1 PVS1+1 PP"。
- **精确触发**：仅当无更强组合时落到此（1 VS + 1 SU，SU=1、无 MO/ST）；`1 VS+≥2 SU`、`1 VS+1 MO`、`1 VS+1 MO+1 SU`、`1 VS+1 ST` 已按致病规则判 P/LP（原行为不变）。引擎实测：`1VS+1SU→LP`、`1VS+2SU→P`、`1VS+1MO→LP`、`1VS+1MO+1SU→P`、`1VS→VUS`、`1SU→VUS` 全部符合预期。
- **引擎同步**：`scripts/acmg_combine.py` `_classic_likely_pathogenic` 加 (i′) 1VS+1SU→LP，`_lp_rules` 加对应规则串。
- **出处说明**：该条非 Richards 2015 Table 5 原表（v4.3.0 曾以"无出处"删除），现为**用户作为领域专家拍板的业务口径**，标注"用户拍板补充口径"。
- 纯引擎规则 + §2.1 文字同步；不影响 Tavtigian 分值引擎、互斥、官方优先、confidence。版本一致性 23 对齐，39 集回归需实测。

## v5.5.5（confidence 流程完成度强制降档，2026-10-16 用户复盘"争议实为跳步"）

- **根因**：评级实证（Y3900F）暴露执行层跳步——PS4 未调 ev-ps4、PM5"分类标准不依赖 PM5"用逻辑推理替代查证、可疑文献该上报未上报、圈定码以"不适用"一笔带过。这些并非结论争议，而是"结论对但流程没走全"，但旧 confidence 无此维度，跳步不现形，仍可标 medium/high。
- **新增 §2.4 confidence"流程完成度强制降档"硬闸（核心）**：命中任一跳步情形（①成立/弃用码未调对应子 SKILL、凭经验给强度或"不适用"一笔带过；②判定条件用逻辑推理替代实际查证（PM5 条件3/PS4 患者数等）；③可疑文献该上报未上报）→ **confidence 强制 low**，输出附触发条目，不得因"结论对/数据硬/两套一致"标 medium/high。
- **定位**：把"跳步"从执行层问题升级为 confidence 可见信号——执行者想拿 high/medium 就必须真走完子技能流程。纯 L1 文本契约，引擎零改动，39 集零扰动。
- 版本：收尾 **5.5.5**（ev-ps4/ev-ps1-pm5 查证绑定补强同步见 CHANGELOG 各自版本）。

## v5.5.4（PM3/PP1 文献证据结构化逐例输出，2026-10-16 用户拍板）

- **PM3/PP1 文献类证据结构化**：§3 文献呈现强制规则补一句——PM3 按 `ev-pm3` 第 2 点"反式证据逐患者"模板（症状/正反式关系/相位/另一变异/是否确信 P-LP/另一变异致病性自评或文献/PMID+URL），PP1 按 `ev-pp1` 第 2 点"共分离证据逐家系"模板（规模/携带人数/是否受累/表型/PMID+URL）；未给出字段写"未给出"，不得空着、不得捏造。
- 配套子技能：ev-pm3 **1.11.0**、ev-pp1 **1.5.0**（各自第 2 点新增结构化模板）。
- 纯 L1 输出层文本契约，**不改组合引擎/枚举/阈值/计分**，39 集一致率与引擎门禁零影响。
- 版本：收尾 **5.5.4**。
- 措辞防照抄修正（同版本 5.5.4，逻辑不变）：PM3/PP1 模板明确为"字段清单（数据采集项），不是要输出的句子"，输出须填实际值、禁止照抄模板字段名/示例枚举（详见 ev-pm3/ev-pp1 对应条目）。

## v5.5.3（文献呈现强制规则：PMID+链接成对输出，2026-10-16）

- **用户实证缺陷**：最终评级输出中 PM3_Strong 只给"PMID 29899460等"缺 URL，PP1_Moderate（≥2受累亲属共分离）连 PMID 都没有——契约虽已写"文献 PMID 及链接"但无强制成对校验、且"无文献证据"无标准标注方式。
- **文献呈现强制规则（§3 输出模板新增）**：凡证据判定**依赖文献/数据库条目** → "数据/规则闭环"与"查询路径"**必须成对输出「PMID + URL」**（文献 URL 统一 `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`，数据库条目给条目链接）；只给号缺链接、或给链接缺号 → 判三点缺失回补，不得定级。
- **无文献证据标准标注（堵捏造/堵含糊）**：确不依赖文献的（纯家系谱共分离、纯人群频率、纯功能实验原始数据）→ 显式标注数据来源（"家系谱数据（无独立文献）"/"gnomAD vX 人群频率"）并注明 **"无 PMID（非文献来源）"**；**禁止**捏造文献、**禁止**以"无链接/待补"含糊代替。
- 适用范围：§3 五点之"证据码适用性总览（第0点）"每个适用已定级码 + "查询路径（第4点）"一律强制；自检清单新增对应核对项。
- 纯 L1 输出层文本契约，**不改组合引擎/枚举/阈值**，39 集一致率与引擎门禁零影响。
- 版本：收尾 **5.5.3**（ev-pvs1 1.12.0、ev-pp3-bp4 1.6.2、ev-pm2 1.4.1、input-schema v1.4.0 本轮未动）。

## v5.5.2（D27：BA1 standalone 剥括号对，2026-10-16）

- **D27（知识库 22 处 "Stand Alone (BA1)" 写法）**：ClinGen VCEP 官方原文 `1 Stand Alone (BA1)` 的 `(BA1)` 后缀曾使引擎 standalone 识别（整串归一==STANDALONE）不命中 → BA1 按 VCEP 原文标注时被 skip、该判 Benign 落成 VUS（系统性偏保守）。用户拍板改引擎、知识库原文不动。修正 `_is_standalone_form`：剥括号对（含配对检测，防误伤非括号写法）后再归一，`Stand Alone (BA1)` / `(BA1) Stand Alone` / `SA (BA1)` 均识别为 standalone → BA1 升格 VeryStrong。
- 边界防护（零回归）：剥括号只作用于 standalone 判断、不触其他路径；非 BA1 码写带括号 standalone 仍 skip 不升格；不配对括号不剥。
- 门禁：contract 20→22 条（新增 4h 后缀 + 前缀变体断言）；regression 2b 写法变体 26 码×5→7 写法（BA1 升格 + 非 BA1 skip 全过）。
- 版本：收尾 **5.5.2**（ev-pvs1 1.12.0、ev-pp3-bp4 1.6.2、ev-pm2 1.4.1、input-schema v1.4.0 本轮未动）。

## v5.5.1（F1′ 处置对称 + F6 cap 可审计，2026-10-16）

- **F1′（PM2 cap 处置不对称修正）**：v5.5.0 对 PM2 的合法升级等级只让 Moderate/Strong 封顶到 Supporting(+1)，**VeryStrong 仍整条丢弃**（54/4096 组结论偏低），且 ev-pm2 裁定原文"只按 Supporting 计、不取更高档"未区分各档。修正为**所有合法升级等级（VeryStrong/Strong/Moderate）一律封顶到 Supporting 计入**（`acmg_combine.py` dict+list 双分支），与原文对称；regression_gate 2c 加 VeryStrong 用例钉住。
- **F6（cap 留痕透传到输出，可审计）**：此前 cap 只在解析层 items 记 note，最终 CLI/JSON 输出看不到"某条 PM2 被封顶过"。修正：解析层 cap 的 item 加 `capped: True`，`combine()` 输出新增 `capped` 字段（`含被引擎封顶的码(cap)`），CLI 打印器可见；contract_test 加 items 层 + CLI 双层断言。
- 门禁：契约 19→20 条（新增 F6 CLI 断言）；回归 2c 加 VeryStrong 用例 + capped 断言。
- 版本：收尾 **5.5.1**（ev-pvs1 1.12.0、ev-pp3-bp4 1.6.2、input-schema v1.4.0 本轮未动）。

## v5.5.0（v13 审计 F1 cap 修正 + F2/F3/F4，2026-10-16）

- **F1（P1，PM2 skip→cap 修正）**：D24 上一轮实现为"非 Supporting 等级 → 整条 skip（计 0）"，与包内 ev-pm2 v1.4.1 裁定原文（"只按 Supporting(+1) 计，不取更高档""计入 Supporting 桶/分值"= **cap 语义**）矛盾。4096 组穷举 162 组结论不同、且全部在 skip 侧更低（例 4×Supporting+PM2=Moderate → skip VUS / cap LP），PM2 真实证据分被整条误丢。**改回 cap**：`acmg_combine.py` dict+list 双分支 PM2 非 Supporting → 封顶 Supporting 计入（skip=False，note 标注"按永久 Supporting 封顶计入(cap)"），保留 PM2 成立贡献、只封顶强度，防 v11 Pathogenic 效果不变（PM2 恒 +1）。
- **F2（P2，BA1 降档等级零测试）**：`contract_test.py` 补 4g——`{"BA1":"Supporting"}` → 引擎A Benign / 引擎B Likely Benign（不 skip 不升格），钉住 §2.3 声明。
- **F3（P2，input-schema 版本回退）**：`input-schema.md` §2.3 D26 内容实变但版本停在 v1.2.0，升 **v1.4.0**（单调递增，历史可追溯）。
- **F4（P2，5e/5f 子串匹配）**：`contract_test.py` 5e/5f 去掉 `"跳过" in out` 子串断言，改为 CLI 结果断言（Pathogenic not in + Likely Pathogenic in）+ items 层断言（`parse_evidence_items` 检查 PM2 level=Supporting、skip=False、note 含 cap）。
- 门禁：契约 17→19 条（新增 4g + items 层断言）；回归 2c `run_pm2_fixed` 改 cap 断言（skip=False + level=Supporting + note cap）。
- 版本：收尾 **5.5.0** / input-schema **v1.4.0**（ev-pvs1 1.12.0、ev-pp3-bp4 1.6.2 本轮未动）。

## v5.4.0（v11 审计 D24/D26/D28–D31 修复，2026-10-15）

- **D24（P0，PM2 永久固定补代码执行者）**：`acmg_combine.py` 加 `PM2_FIXED_LEVEL="Supporting"`——dict+list 双分支非 Supporting 等级显式跳过（note 标注），`PM2=Strong+PP3_S+PS3_S` 由 **Pathogenic 降为 VUS**（v11 审计实证）。门禁 `regression_gate.py` 新增 2c `run_pm2_fixed`（dict+list）、`contract_test.py` 新增 5e/5f 负向断言；受 D24 影响的 `PM2:Moderate` 测试输入改为 `PM3:Moderate`。sync-manifest §8 补"引擎门控"载体。
- **D26（P1，BA1 降档等级声明≠实现）**：`input-schema.md` §2.3 原写 `{"BA1":"Supporting"}`→skip，实测判 **Benign/LB**（BA1 规则只看 code、成立即判良性，不因降档等级 skip）。改为如实描述 + 明示"调用方不得用降档等级给 BA1（会静默削弱为 LB）"。
- **D28（P1，contract 5c 无牙齿）**：原 `"Pathogenic" not in out` 对良性侧恒真。改为断言"BS1+SA 被 skip、结论与空背景一致（VUS，不含 Benign/Pathogenic）"。
- **D29（P1，list 分支零断言）**：`regression_gate.run_level_variants` 加 dict+list 双形态穷举；`contract_test` 加 5d（list 非 BA1+Standalone 不升格）。
- **D30（P2，删 build 副本）**：`build_package_20261015.py` 回归/契约门禁改跑权威源 `scripts/` 脚本（HERE 可重定位）；删除 PROJ 副本 `regression_gate.py`/`contract_test.py`；sync-manifest §9 改"已废除（无副本）"，明确"复制单一事实源+人工清单同步=复发模式"。
- **D31（P2，依据串硬编码）**：`acmg_evidence.py` `revel_band`/`spliceai_band` 依据说明从 config 格式化，改 config 即逻辑与打印同步，不再硬编码字面量。
- **D32（P2，SpliceAI 标注×2）**：`ev-pp3-bp4` §SpliceAI2 映射、`ev-pvs1` 剪接影响段补"权威来源=thresholds.json → spliceai.v2_thresholds"；sync-manifest §10 `splice_band`→`spliceai_band` 名称对齐。
- 门禁：契约 14→17 条（5d/5e/5f 新增）、回归 2b 加 list + 2c 新增；版本：ev-pvs1 **1.12.0** / ev-pp3-bp4 **1.6.2** / 收尾 **5.4.0**（均与 CHANGELOG 最高一致）。


## v5.3.9（结构性冗余/循环约束核查，2026-10-15）

- **sync-manifest 新增 §10「阈值集中表 vs SKILL 内嵌表」**：核心循环约束缺口——REVEL / SpliceAI / PM3 / PP1-LOD / 分值五组阈值都在「集中配置 thresholds.json + SKILL 内嵌表 + 确定性引擎」三处双写，此前无强制同步机制（PP1 LOD 历史上裂过一次）。§10 列出五组双写矩阵 + 强制同步规则 + 改前 grep 逐处核对。
- **SKILL 内嵌表头补「权威来源」标注**：`SKILL.md` §0.4 分值表、`ev-pp3-bp4` REVEL 表、`ev-pm3` 计分表各加一行"权威=thresholds.json，改此处必须三处同步（sync-manifest §10）"；`ev-pp1` 原已标注。
- 纯文档增强，不改变任何判定规则/阈值，39 集一致率与门禁不变。

## v5.3.8（D9′ 落定：PM2 永久固定拍板确认，2026-10-15）

- **D9′ 落定（用户拍板确认）**：2026-10-15 用户在对话中**明确表态「永久固定 PM2_Supporting」**。此前 v5.3.7 的"待用户拍板确认"措辞改为**已确认固化**。落地：①`ev-pm2` SKILL.md 补永久固定声明（v1.4.0→1.4.1：PM2 永久 `PM2_Supporting`，不得因频率更低/数据更足取 Moderate/Strong）；②收尾 `SKILL.md` 分值表 PM2 行标注永久固定仅 Supporting(+1)，Moderate/Strong 行仅作通用参考、不适用于 PM2。引擎行为此前已与该裁定一致，无需改代码；sync-manifest 该载体条目同步更新。

## v5.3.7（v10 报告 D19–D23 + D9′ 措辞更正，2026-10-15）

- **D19（P0 方向性，stand-alone 归 BA1 门控）**：`_normalize_level` 的全局 standalone→VeryStrong 白名单**移除**，改为调用点 **BA1 门控**：`_is_standalone_form`（空白/连字符归一）仅在 `code=="BA1"` 时把 `Standalone/Stand-alone/Stand_alone/SA/Stand Alone` → VeryStrong；**非 BA1 码写该写法 → 整条 skip，绝不升格**（v10 实测 100 组偏移全部消除）。
- **D20（P0，接受 ACMG 原文写法）**：`input-schema.md` §2.3 由"禁止 `"Stand Alone"`"改为**接受**（含带空格原文），版本升 **v1.2.0**；实测 `BA1="Stand Alone"` → Benign。
- **D21（门禁补负向 + 写法变体维度）**：`contract_test.py` 增 5a/5b/5c 负向断言（非 BA1+Standalone/SA 不升格）→ 14 条；`regression_gate.py` 增 2b「等级写法变体维度」（26 码 × 5 写法穷举）→ 全过。
- **D22（sync-manifest 接入 + 对齐）**：§4 标题与范围对齐为「BA1 门控」，修正"靠引擎白名单兼容"错误注记（现为"接受 'Stand Alone'，含 (BA1) 后缀仍 skip"）；README 门禁表新增 `sync-manifest.md` 引用（改口径前必读），接入流程。
- **D23（版本/卫生）**：`SKILL.md:349` 版本引用 v5.3.5→v5.3.6；`input-schema.md` 升 v1.2.0；删除误入库构建产物 `scripts/gate_d14_out.txt`。
- **D9′ 措辞更正**：CHANGELOG 此前的"用户已拍板"更正为**待用户拍板确认**（v10 第三次请求；引擎行为与该裁定一致，用户确认后固化）。

## v5.3.6（v9 报告 D14–D18 全部落地 + sync-manifest，2026-10-15）

- **D14（边界口径对齐 ruler v2.1）**：收尾 `SKILL.md` §3 全码两分「适用组」边界口径原抄 ruler v2.0（边界擦边=有争议），与 `golden.json` `confidence_ruler` v2.1（边界擦边=确信）相反。**已以 v2.1 为准改 SKILL.md**：数值查到、严格按官方区间裁决即确信，即使落在区间边界擦边也不标争议；仅当"码本身是否成立存疑"（来源/ClinVar 冲突、phase 未确认、可疑文献、降档封顶、依据无具体数值）才标有争议。→ 消除两权威文本相反指令。
- **D15（BA1 level 契约 + 白名单）**：`acmg_combine.py` `_normalize_level` 白名单补 `Standalone/Stand-alone/Stand_alone/SA` → `VeryStrong`（BA1 原始等级名，独立即判良性；此前缺它，用户照抄 clingen-vcep 知识库 "Stand Alone (BA1)" 会被当非等级标记静默 skip→VUS）；`input-schema.md` 增 §2.3 BA1 等级契约（成立不带 level / 显式 Standalone/VeryStrong；禁止带空格 "Stand Alone" 或降档等级）。
- **D16（堵"成立的 BA1"断言盲区）**：`contract_test.py` 增 4d/4e/4f 三条——BA1 不带 level / Standalone / Stand-alone → 均 Benign。不改 golden.json 39 集（保 D13 口径），用确定性契约断言堵盲区。
- **D17（参数错误 vs 数据 skip 不混同）**：`combination_eval.py` 单独捕获 `ACMGCombineError` → 打印参数/契约错误 + `return 2`（exit≠0），不再被宽泛 `except Exception` 吞成 SKIP=39 + exit=0（P5-8）。与 `acmg_combine.py` 行为一致。
- **D18（CHANGELOG 回填 confidence 数字）**：v5.3.4 段 `64/21` 回填为 `65/20`（ruler 升 v2.1 后 golden 实测，var024 擦边改确信）。
- **新增 `sync-manifest.md`（P3-1 载体清单资产）**：固化"改 X 时必须同步 Y/Z"——confidence 边界口径 / interval 枚举 / 官方识别串 / BA1 契约 / 版本号 / 可疑文献 / 提交门禁 七组载体清单，防"改了数据层漏了文档层"连续复发。
- **D9′（待用户拍板，v10 第三次请求）**：PM2 永久固定 `PM2_Supporting`（SVI/变异解读查询路径 降级）——**该裁定在本对话中尚未获用户明确表态**，CHANGELOG 此前的"用户已拍板"表述更正为**待确认**；引擎当前行为与该裁定一致（ev-pm2 v1.4.0），若用户确认则固化、若否定则回退为按实际强度定档，并同步 ev-pm2 与收尾规则。

## v5.3.5（D11/D12 落地：BMPR2 单基因区间强制基因校验，2026-10-15）

- **D11 强制基因校验（用户拍板=方案 a，引擎加 --gene，最硬）**：`scripts/acmg_combine.py` 的 `combine()` 新增 `gene` 参数——当 `interval=bmpR2_gn125_v2` 且 `gene` 为空或非 `BMPR2`（大写）时**抛 `ACMGCombineError` 拒绝执行**（防评其他基因误用该单基因区间；校验置于 official 短路之前）。CLI 新增 `--gene` 参数并透传；usage docstring 同步 `[--gene BMPR2]`。`scripts/combination_eval.py` 同步加 `--gene` 透传（评测金标准默认 2020 不涉及；仅显式 bmpR2 时触发校验）。回归网 `regression_gate.py` 分值穷举用内部方法（`_class_by_total`/`engine_b_score`）不经 `combine()`，不受校验影响，仍可独立测 bmpR2 区间逻辑。
- **D12 输入契约同步**：`input-schema.md` 升 v1.1.0，interval 旧名 `vcep` → `bmpR2_gn125_v2` 并注明"须 --gene BMPR2 否则拒绝"；`acmg_combine.py:36` usage 由 `2023|2020` 补为 `2023|2020|bmpR2_gn125_v2`。已全仓 grep：CHANGELOG 历史条目与 clingen-vcep 载体/缓存命名空间中的 `vcep` 均为合法非残留。
- **D13 保持 26/39（用户拍板，不改代码）**：`combination_eval.py` agreement 分母仍含官方 4 条（恒一致），口径声明不变。

## v5.3.4（金标准治理 v2：已定级证据码 确信/有争议 标注，2026-10-15）

- **金标准治理**：`golden.json` 每个**已定级证据码**加 `confidence`（`certain` 确信 / `contested` 有争议），判定标准写入 `confidence_ruler`（用户口径 2026-10-15）——certain=数值落在明确阈值/区间、来源无冲突、结论无保留；contested=数值边界擦边 / 来源或 ClinVar 冲突 / phase 未确认或待核验 / 可疑文献 / 降档封顶 / 依据无具体数值。**已定级码 85 个 = certain 65 / contested 20**（回填 v2.1 修订：REVEL 数值查到、按官方区间裁决即确信，即使落在区间边界也不标争议——var024 PP3 REVEL=0.939 擦 0.932 边界由 contested 改 certain；此修订并入 v5.3.4 打包的 golden v2.1，CHANGELOG 同步回填，D18）；未成立/未计/互斥剔除/边界码标 `null`（不参与标注）。
- **归档联动（用户要求"存档变异也加这一条"）**：收尾 §3 全码两分「适用组」逐码标「确信/有争议」；§3.5 归档 `evidence_items` 每个已定级证据码带 `confidence`（确信/有争议）；`input-schema` 的 golden `authoritative_evidence` / result `evidence_codes` 均加 `confidence` 可选字段。
- **评测兼容**：新 golden（含 confidence 字段）经 combination_eval 实测不崩、一致率不变（表5 93.8% / 分值 97.1% / 官方遵循率 100% / agreement 66.7% / SKIP=0）。

## v5.3.3（领域拍板落地 + 断言盲区补全 + 官方条目单列，2026-10-15）

- **领域拍板三裁定（用户拍板，硬约束）**：
  1. **PM2 永久固定 PM2_Supporting**（除非 ACMG/ClinGen 指南更新），现版本一律按 Supporting 强度，不降级、不升档；两套结算（方案A 表5 + 方案B Tavtigian）均以证据码「最终使用等级」为统一量纲（VeryStrong/Strong/Moderate/Supporting），`PM2@Supporting` 计入 Supporting 桶/SU=1，与码前缀基线解耦。收尾 §2 方案A 处补「等级分桶」声明、`ev-pm2` v1.4.0 固化；引擎 `acmg_combine.py` 早已按此实现。
  2. **vcep 区间=特殊基因专用、默认不启用**：Tavtigian 第三套区间由 `vcep` 改名 `bmpR2_gn125_v2`（scope=仅 BMPR2/PAH 单基因 VCEP GN125 v2.0.0，`enabled_by_default=false`，note 引 v7 P1-A + PMC13069149），**禁止当通用区间**（2025 SVI 精炼后通用仍 0/−1，PMC13069149）。`thresholds.json` 与 combination_eval/acmg_combine/regression_gate 的 `--interval` choices 及注释同步。
  3. **金标准暂用版接受、覆盖面后续补**（用户拍板），先整体无问题，不做全量端到端复测。
- **断言盲区补全（v7 定向检查 P 项）**：
  - **P2-B 官方条目单列**：combination_eval.py + regression_gate.run_39 将「VCEP官方短路条目」从分值一致率分母剔除、单独统计「官方遵循率」，消除官方 4 条结构性虚高。
  - **P2-A 版本门禁遍历全量**：regression_gate 版本一致性由「只查收尾」改为**遍历全部 23 个 SKILL**（各自 version == 各自 CHANGELOG 最高版本）；补记 acmg-total-scheduler CHANGELOG v4.11/v4.12（归档+时效守卫）、ev-pm2 CHANGELOG v1.4.0（PM2 裁定），消除 4.12.0 vs 4.10.0 漂移。
  - **P2-D 穷举补 PM 类码×Supporting**：新增 `run_pm_supporting` 专项穷举（PVS1+PM2/PM3_SU 等 6 组，对照独立表5参考），验证 PM 类码 Supporting 按 SU 桶处理、与 PP 类 SU 等价，杜绝 var002 类「证据够了不敢给满档」盲区。
  - **P1-B requirements.txt 补 pyliftover**（standardize_variant.py 主入口依赖，缺失即 ImportError）。
- **一致率双分母声明（P2-C）**：**新口径实测——表5一致率 93.8%（15/16，仅 basis=Table5 精选子集）；全量不筛 basis 51.3%（20/39）；分值一致率 97.1%（34/35，剔除官方 4 条）；官方遵循率 100%（4/4）；agreement 66.7%（26/39）**。并列"精选/全量"与"含官方/剔除官方"分母，不再只写单一高值。

## v5.3.2（永久归档命中复用加"时效守卫"硬化，2026-10-15）

- **深度检查发现真实机制风险并修复**：`result` 永久归档（expire=None）+ 调度层"命中直接复用不重评"，若官方/数据源升版仍会无限期返回旧归档结论，绕过版本守卫。修复为**命中复用必须先过时效守卫**（写死）：
  1. `rated_at` 距今 > **90 天** → 不得复用，强制完整重评；
  2. 任一数据源（ClinGen cspec/VCEP/gnomAD/ClinVar/REVEL/SpliceAI）已升版（data_snapshot 版本 < 当前）→ 不得复用，强制重评；
  3. `skills_version` 落后当前技能群版本 → 不得复用，强制重评；
  4. 时效守卫通过才可复用，但仍显式标注 rated_at/skills_version/data_snapshot 作候选基线；高危位点（ClinVar EP/多星、HGMD 挂载、P/B 高置信）或官方裁定可能变化时，命中复用仍须人工确认。
- **收尾 §3.5 同步**：归档 `data_snapshot` 改为必填字段（各库取数时点/版本），缺此字段的归档视为无效条目、命中不得复用；命中复用须过时效守卫（联动调度层）。
- **时效守卫脚本化（acmg_cache v1.2.0）**：给 `scripts/acmg_cache.py` 加 `check` 动作，把三道闸固化为确定性脚本——运行 `python scripts/acmg_cache.py check --ns result --key "<基因|c.HGVS>"` 自动读归档 `rated_at / data_snapshot / skills_version`，与当前技能群版本（自动读收尾 frontmatter）+ fresh_days=90 对比，输出 STATUS（REUSE / RERATE / NOT_FOUND）+ 触发闸与原因；`--fresh-days` 可改阈值、`--current-version` / `--current-data-version` 可显式传当前版本。调度层 §0 命中检查、收尾 §3.5 均改为"命中必须跑 check 脚本，不得凭读字段自行判断"（把"依赖 LLM 执行纪律"换成确定性脚本）。
- 调度层 version 4.11.0 → 4.12.0（联动本硬化）。

## v5.3.1（已确认评级结果永久归档 + 命中复用，2026-10-15）

- **acmg_cache.py 升级 v1.1.0**：新增 `result` 命名空间 = **永久归档**（TTL=0，`cache_set` 时 expire=None，`cache_get` 对 expire=None 永不过期；CLI `set --ttl 0` 写永久、`get` 命中输出 `PERMANENT` 标记）。已测试永久读写通过。
- **边界（写死）**：`result` 是**唯一永久命名空间**；gene_disease/vcep/genebe/freq/revel 原始查询缓存仍按 TTL 过期（30天/24h），不得改永久——外部库升版会改 gnomAD AF / ClinVar 分类 / VCEP 官方裁定 / REVEL/SpliceAI 分值，永久化原始查询会引入过期数据。
- **收尾 §3.5 评级结果永久归档（强制）**：双套定级结论确定后，把 `final_class + evidence_items + confidence + rated_at + skills_version + data_snapshot` 以归一化变异主键（基因|c.HGVS，优先 CA ID/rsID）写入 result 归档；重复评级同一变异按主键 upsert 覆盖（更新 rated_at）；命中时显式标注 rated_at/skills_version/data_snapshot，不静默当最新。
- **调度层入口命中检查（v4.11.0 联动）**：评变异前先查 result 归档——命中直接复用已确认结论（标注快照时点），未命中走完整流程；官方/VCEP 升版或数据版本变化后需重评时才走完整流程覆盖归档。
- **combination_eval 官方条目展示标记修复（深度检查发现，纯展示不影响一致率）**：官方条目（basis=VCEP官方，status=official）此前因 `m_table5=None` 在明细误标 `✗`，现修正为 `官方✓`；官方短路已由 contract_test 单测 PASS，一致率数字不变（表5=93.8%、分值=97.4%）。

## v5.3.0（P0/P1 修复 + 金标准两套结算 + 缓存层 + 输出全码两分，2026-10-15）

- **P0-A combination_eval 默认分值区间漂移修复**：`--interval` 默认由写死的 `2023` 改为 `None`（读 `config/tavtigian_interval.default=2020`），与引擎 `combine()`/CLI 一致，消除"评测数字与门禁/配置不同尺子、不可复现"。
- **P0-B 分值引擎（engine_b）独立穷举对照**：新增 `run_exhaustive_score`——对全整数总分 [-24,24] × 三区间（2020/2023/vcep）对照独立参考 `class_by_total_ref`（覆盖 P/LP/VUS/LB/B 全边界 + 2023 VUS-Low/Mid/High 分支）+ 端到端 total 计算 + PM1+PP3 封顶 +4；此前 engine_b 只靠 39 集验证（覆盖不足）。
- **P1-C spliceai v2 三档切点来源绑定**：`thresholds.json` 的 `spliceai.v2_thresholds`（0.1/0.25/0.5）原只有 "SpliceAI2, Illumina" 无出处版本；修正为"本实验室内部口径：SpliceAI2 官方未发布分级切点，三档沿用初代/VCEP 通用切点，未经官方确认"，消除 D6⑩ 版本绑定缺口（不伪造来源）。
- **金标准两套结算体系**：`golden_builder.py` 增加 basis 自检（`criteria_counts`+`table5_ref`+`basis_by_methodA`）——methodA 表5可达→Table5，表5不可达→点值法，官方→VCEP官方；现有 golden.json 修正 19 条 basis（Table5→点值法，分布 Table5=16/点值法=19/VCEP官方=4）。`combination_eval.py` 按 basis 分口径：**表5一致率仅对 basis=Table5 条目**（engine_a vs methodA），点值法条目不参与表5（其 methodA 非表5推，混入则假性偏低）；分值一致率对全部 methodB。`regression_gate.run_39` 同步同口径。**实测：表5一致率 93.8%（15/16，此前 51.3% 系被 19 条点值法污染）、分值一致率 97.4%（38/39）**；唯一分值偏差 var009 为"PM3 待核验"口径（金标准计分 LP、引擎按铁律不计 VUS）。
- **缓存层落地（慢优化，只复用已查结果、不缩减穷尽检索）**：新增 `scripts/acmg_cache.py`（跨变异落盘查询缓存：命名空间 gene_disease/vcep/genebe/freq/revel，TTL 分级静态30天/变异24h，原子写防并发）。`ev-disease-info`、`ev-variant-standardization` 加"缓存先行"硬步骤——查询前先查缓存命中即用并标注时间，未命中才外部查并回写；**边界铁律：缓存只消重复查询，穷尽检索（Books/ClinGen/PubMed 全源、PVS1 三通道、PM3 反式穷尽、可疑文献 L1/L2/L3 核验）强制保留、一律执行**。
- **输出全码两分（收尾 §3 第0步新增）**：最终交付"证据码适用性总览"——把①圈定的全部证据码分「适用（互斥消解后保留，含等级+数据/规则闭环）」/「不适用（判定不成立，逐码注实据：AF超阈值/无家系/预测中性/查不到/待核验/被互斥弃用）」两组完整罗列，核对"适用+不适用==圈定全码数"（缺码不得定级）；强制交付四点升级为五点。

## v5.2.0（v6 定向检查 P0 修复：评测可用 + 门禁随包，2026-10-15）

- **P0 combination_eval --help 崩溃修复**：help 文本 `（%）` 触发 argparse 旧式 % 格式化（ValueError）；改为 `（百分比）`，`--help` 与全参数运行恢复。
- **P0 一致率声明可随包复现**：`config/golden.json`（双尺子金标准 39 条）随包交付；`combination_eval.py` 默认 `--golden=config/golden.json`，直接运行即复现 表5=51.3%(20/39) / 分值=97.4%(38/39)。
- **P0 门禁随包交付**：`scripts/golden_builder.py`（生成说明）、`scripts/regression_gate.py`（穷举328+冒烟+39集双尺子+SKIP+版本）、`scripts/contract_test.py`（L1→L2 契约 8 项）随包，用户解压即可自检；脚本全部改为相对路径（同目录引擎 + ../config/golden.json），不再依赖绝对路径。
- **5-4 澄清**：var005/006/030/038 官方 P 短路在本真实 golden.json（criteria 含 status 描述）下已实测通过（combination_eval 双尺子明细均为 Pathogenic ✓）；审计侧测到 PENDING 系其使用无 status 的单尺子金标准，非引擎缺陷。
- 说明：golden.json 随包是"评测输入快照"（暂用版，随金标准更新重建）；39 变异集源文件仅在构建环境，重建 golden 请用 `golden_builder.py` 指明输入。

## v5.1.0（双尺子评测 + SKIP 门禁 + 契约测试，2026-10-15）

- **金标准双尺子口径（用户拍板）**：金标准暂用版、随更新重建；评测同尺子对同尺子——
  引擎 `engine_a`（Table5）对金标准 `methodA`（经典联合规则）算"表5一致率"，引擎 `engine_b`（Tavtigian）对金标准 `methodB`（分值）算"分值一致率"，不再拿单一 final 混尺子（消除第五轮审计 §7 指标失真根因）。
- **golden.json（双尺子金标准）**：由 `golden_builder.py` 从 39 变异集生成，每条含 `methodA`/`methodB`/`basis`（Table5/VCEP官方）/`official`/`source`；官方裁定 4 条（var005/006/030/038）作最高真值层，只验证官方短路。
- **combination_eval.py 重写为双尺子版**：实测表5一致率 51.3%（20/39）、分值一致率 97.4%（38/39）——分值引擎几乎全对，表5偏差源于金标准 methodA 混入点值法推导的 LP（var001/004/007/012/016/018/019/020/025/026/029/039 等"PVS1+PM2_S→LP"），非引擎错。
- **regression_gate.py 支持 SKIP 计数**：解析/引擎崩溃归 SKIP，SKIP>0 视为失败（退出码非0），堵住"静默跳过"。
- **contract_test.py（L1→L2 输入契约）**：官方带 class 短路 / 无 class→official_pending 不按 VUS / status 补分类 / 复合码方向（同向只计一次、对向 skip），纳入打包门禁。
- **打包门禁升级**：README 数字 + 嵌句检测 + py_compile（scripts/config 全 .py）+ 契约测试 + 回归门禁，全过才允许打包。
- 回滚机制：已启用 git 基线（git 2.55 可用，2026-10-22 起以 tag 为回滚锚点）；历史"版本快照回滚"（保留各版 zip，解压旧 zip）保留作补充手段。

## v5.0.0（第五轮审计 P0/P1 修复 + 回归门禁，2026-10-15）

- **P0-1 修复 list 输入双重计入**：`parse_evidence_items` list 分支普通码/复合码只 append 一次，不再"handle_key 一次 + 外层再 append 一次"；消除 39 集证据条数 1.95 倍放大的回归。
- **P0-2 同步 combination_eval.py 元组接口**：`items, official = parse_evidence_items(...)`，`official` 传入 `combine()`，恢复唯一回归验收通路；`--interval` 支持 `vcep`。
- **P0-3 CLI 打印器补 `official_pending` 分支**：不再因缺 `engine_a/engine_b` 抛 KeyError，输出"待补分类"提示。
- **P1-1 复合码拆分方向限定**：`PS2/PM6`（同向）只取一侧计一次；`PP3/BP4`、`PM2/BA1`（对向）整条 skip，杜绝双计/抵消/推良性；支持显式 `direction` 字段。
- **P1-2 官方裁定 status 补分类**：无 `class` 时从 `status/strength` 描述文字提取分类（"致病/Pathogenic"→Pathogenic 等），var005/006/030/038 官方 P 不再判 VUS。
- **回归门禁**：新增 `regression_gate.py`（穷举 328 对照 + 引擎/CLI 冒烟 + 39 集评测 + 版本一致性），并集成进 `build_package_20261015.py` 第三道防复发校验，全过才允许打包。
- 清理 `_lp_rules` 残留"补充 1VS+1SU→LP"死代码（判定已于 v4.3.0 删除）。

## v4.4.0（第四轮审计 Q5 输入契约 + Q7 VCEP 版本 + Tavtigian 第三套，2026-10-15）

- **组合层标准输入契约**：新增 `input-schema.md`，组合层输入严格三部分分离（证据码清单 / 官方裁定 / interval），过程记录（查询路径/文献列表/中间推理）不得进组合层；官方裁定支持 `class` 字段直接短路，pending 可由 `--official` 补分类，仍无则回 `official_pending` 不得按 VUS 处置。
- **Tavtigian 第三套区间补录**：config `tavtigian_interval.vcep`（P≥10/LP6–9/VUS−1~5/LB−2~−6/B≤−7，来源 CSpec GN125 v2.0.0，2026-01-30），引擎 `--interval` 新增 `vcep`。
- **SpliceAI 两套刻度分离**：PP3/PVS1 剪接致病侧用 SpliceAI2 v2 三档；BP4 良性侧排除按各基因 VCEP 原文（初代 <0.1，官方出处）；v1/v2 无官方换算映射，禁止混用/臆造换算。阈值见 config/thresholds.json。
- **Q7 VCEP 版本号补齐**：131 个 VCEP 规范中 40 个已有版本声明、91 个补齐统一版本声明（数据日期 + 官网核验指引；ABCD1/GALT/OTC/RPE65 附附件版本日期线索）。

## v4.3.0（第四轮审计 4.1/4.2/4.3，2026-10-15）

- **删除无出处补充句"1 VS + 1 SU → LP"**：Richards 2015 Table 5 的 Likely Pathogenic 仅 6 条（1VS+1MO / 1ST+1-2MO / 1ST+≥2SU / ≥3MO / 2MO+≥2SU / 1MO+≥4SU），无"1VS+1SU→LP"；点值法 8+1=9∈LP 的结论不得塞进自称 Table 5 的引擎。`PVS1+PP1` 应为 VUS。
- **官方裁定接口适配**：`parse_evidence_items` 识别 `{"code":"VCEP官方裁定",...}` 为官方短路（不再被当证据码 skip）；官方裁定须带分类（level 含 Pathogenic/LP/B/LB）才短路，无分类标 `official_pending` 待上游补分类。
- **复合码 dict 形式兼容**：`PP3/BP4`、`PM2/BA1`、`PS2/PM6` 拆分处理，不再抛 `ACMGCombineError`。

## v4.2.0（第三轮审计 P0-1~P0-6，2026-10-15）

- **组合引擎方向性缺陷修复（P0-1~P0-6）**：`_counts()` 加方向过滤（良性码不进致病桶）、`{码:等级}` 输入支持（value 即等级）、`{"BA1":"未成立"}` 非等级标记 skip、删除死方法 `_classic_likely_benign`、`rules_hit` 从真实命中生成、移除 `LEVEL_ALIAS` 死代码与 `P`→Supporting 方向反转别名。良性侧穷举差分 0 不符。
- **PM1+PP3 软提醒升级硬封顶 Strong(+4)**：Pejaver 2022 官方建议，收尾/调度/引擎三处同步。
- **PMID 32525297 → 32720330**（Tavtigian 2020 正确 PMID，Hum Mutat 41(10):1734-1737）。
- **PP1 LOD 出处修正**：0.9/1.5/2.1 为 CMP-EP 疾病特异档（GN098-101），非 J&B 2016 原值（0.9/1.2/1.5）。

## v4.1.0（PM1+PP3 硬封顶，2026-10-15）

- PM1+PP3 合计封顶 Strong(+4)（Pejaver 2022），三处同步（收尾/调度/引擎实现含剔除留痕）。

## v3.4.0（第三方第三轮深度审计修复，2026-10-15）

- **默认 Tavtigian 区间切换为 2020 已发表版（LB −1~−6/B≤−7，PMID 32525297）**：原默认 2023 草案（B≤−4）无任何已发表来源、仅年会口头草案，且副作用是把单个 BS(−4 分) 判成 Benign（表5 需 ≥2 BS）。2023 仅作可选项，采用须显式标注"草案无已发表出处"。默认区间与 config `tavtigian_interval.default` 统一（=2020）。
- 描述/交付模板/自检清单同步：默认 2020，2023 可选标注。
- 组合层契约与引擎接口：`--interval` 缺省读 config default；`--official` 官方短路通道（官方已定级优先从文字收敛为代码）；输入支持 `verdict` 字段（非 established 拒收）。

## v3.3.0

- 补全 Tavtigian 分值系统完整信息——分值表(8/4/2/1、良性负) + 两版本分级区间（2020 原版 Table3：LB −1~−6/B≤−7；2023 更新草案：LB −3~−1/B≤−4，默认采用 2023 草案区间）

## v3.1.0

- 新增【强制：逐证据码互斥校验】写死步骤：收尾必须先对全部中间证据码（含已弃用者）逐对过互斥矩阵、显式输出"强制互斥校验表"、确认"✅ 无互斥对并存"后方可定级

## v3.4.0

- 新增【圈定清单 vs 实际判定清单逐码核对】硬步骤：进入互斥消解前，先把总调度层圈定清单与中间实际判定清单逐码比对，凡圈定未判者须补判或显式标注不适用/证据不足，并输出"圈定↔判定逐码核对表"作防漏码依据，缺码禁止定级。

## v3.5.0（证据方向一致性+累分衔接校验）

- 新增【证据方向一致性 + 累分衔接校验】硬步骤（对治"有证据不用"锚定失败）：①收集已读 ClinVar/ClinGen/已核验 PMID 外部证据方向，核对最终证据码净方向必须与其一致，方向相反（已读 P/LP 但净方向 VUS/良性）时禁止定级、须回中间子SKILL 复核被降档/漏用码；②逐码取中间判定使用等级按分值表赋分累加，总分须与中间判定清单逐码对应，不得漏成立码/多算弃用码。

## v3.5.0（互斥矩阵修复）

- 互斥矩阵修复：①PM4 行补入 PP3（官方明确 PM4–PP3 不可并用，CanVIG-UK 2021 / ClinGen SVI / YY/T 1865 佐证）；②删除末行"PS4/…/PP3/PP4 无互斥"歧义行，改为逐码列明真正互斥对象（仅 PS4/PM2/PM3/PP4 无互斥）；③新增 PM1/PM5/PP1/PP2/PP3 逐码互斥行；④§1.2 取舍表补 PM4 vs PP3。本矩阵为**互斥唯一裁决依据**，各 ev-* 子技能互斥段落仅为提示。

## v3.6.0

- 新增 6 个良性码的方向性镜像互斥：BS4↔PP1、BP1↔PP2、BP2↔PM3、BP3↔PM4、BP5↔PS2/PM6、BP7↔PP3——同一证据不得同时计入良性侧与致病侧，按 §1.2 保留分值更高者；矩阵补全对应互斥行。

## v3.7.0

- 新增【格式完整性自检】硬步骤（整改 P1-4，与评价引擎 D5/D6⑦ 双层兜底）：进入最终输出前，必须对上游每个中间证据码判定执行"三点完整性"逐项核对（证据码+等级 / 数据+规则 / 查询路径），输出"格式完整性自检表"，任一码缺字段→回对应子SKILL 补全后再进收尾，禁止带缺漏定级。

## v3.8.0

- 新增两项整改：①§0 前置【VCEP 官方已定级优先】全局最高优先级总则（实证 var006 GJB2 c.109G>A / var030 HBB IVS-II-654 官方 P 曾被降成 VUS）——先查 ClinGen cspec 是否有 VCEP 官方对本变异裁定，有则最终分类直接采用官方结论，通用证据码降档不得覆盖官方整体裁定；②§2.3 双套评级【分歧不得无条件取保守档】——两套结论不一致时先回中间复核证据是否真不足（查被降档/漏用/误删码），复核确认证据确实不足才允许并列输出差异，不得静默取保守档作为最终结论。

## v3.9.0

- 新增【两级官方优先】（整改 var023 CFTR 5T 盲区——非 ClinGen 但有权威专家组共识定级的基因被通用分值法系统性低估）：§0 前置【官方已定级优先】从"仅 ClinGen VCEP/EP cspec"扩展为**两级**——①第一级 ClinGen VCEP/EP cspec 对本变异（具体到 c.HGVS/rsID）的官方裁定（原规则保留）；②第二级：基因无 ClinGen VCEP cspec，但存在**权威专家组/官方技术标准的共识性定级**（ACMG 官方专项技术标准/专项指南、基因特异 Expert Panel 共识库如 CFTR2、ClinVar 专家评审标注 reduced-penetrance/variable-expressivity 等；须为权威共识，非 ClinVar 一般提交者聚合分类、非单篇文献），同样优先采用共识定级为最终分类，通用分值法（尤其对低外显率等位系统性低估的 VUS）不得覆盖该共识；交付显式标注"非 cspec 官方，按权威专家组共识定级（来源+版本+结论）"。

## v3.10.0

- 新增两项执行级硬步骤（修 var030 HBB 官方优先执行缺口 + var015 SPATA7 良性反证漏检）：①【官方已定级必须联网核实】——收尾判定前必须实际联网核实 ClinGen cspec 是否有官方裁定，不得仅凭本地载体/记忆判断"有无官方"（HBB IVS-II-654=GN170 官方 Pathogenic，须优先采用，不得走通用定 VUS）；②【良性反证/外显不全检索】——人群高频/founder/外显不全等位须主动走 ev-bs1-bs2 查 BS1/BS2 反证并与致病码互斥消解（SPATA7 EAS 健康纯合 → BS2 反证计入 → VUS 最多 LP，不得仅凭 PVS1_VS+PM2 判 LP）。

## v4.0.0（组合层工程化，优化版）

- §2.1 经典联合规则**按 Richards 2015 Table 5 修正**：致病(P)侧仅保留 (i)(ii)(iii) 三条主规则，移除错误置于 P 侧的"(v) ≥2 PM 且 ≥1 PP → P"（该条实为 LP 侧规则，且阈值应为 ≥2 Supporting，旧文本自相矛盾）。**表5 (v) 正确归属 LP 侧 = 2 Moderate AND ≥2 Supporting**（§2.1 LP 行已有，未变）。
- 新增 **§1.1.1 冲突类型标注**：互斥对按五类标注本质（SOURCE 同源重复 / CRITERION 判定重叠 / DIRECTIONAL 方向相反 / INVALID_STRENGTH 档位不合理 / ALGORITHM 方法学冲突，借鉴 ACMG-AMP MCP 冲突五类）；输出校验表每对标注冲突类型。
- 新增 **§2.4 结论 confidence 标签**：双套结论各附 high/medium/low（含查不到/待人工/边界 → low；两套分歧/官方覆盖 → medium；一致无缺 → high）。
- 新增 **§2.5 组合层可执行引擎交叉验证**：配套 `scripts/acmg_combine.py`（表5含v + Tavtigian 双套，读集中配置表 `config/thresholds.json`，双路径交叉、全程审计），文字定级与引擎结论互校，不一致回查不得静默取任一。
- §3 输出模板新增"方案A/B confidence"行。
- 配套新增集中阈值配置表 `config/thresholds.json`（分值/Tavtigian区间/PM2频率/REVEL切点/SpliceAI v1&v2/LOF/PM3累分，每项带 source+version）。
