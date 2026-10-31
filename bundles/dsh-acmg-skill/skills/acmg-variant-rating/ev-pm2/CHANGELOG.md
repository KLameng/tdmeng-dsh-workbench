# ev-pm2 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.5.0（VCEP 路由方案，2026-10-20）

- **方向定稿（用户拍板）**：特异基因的最终权威源是 ClinGen VCEP 官方规范原文，评级时**直接路由读取** `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### PM2` 段，**不再落库制造官方副本**（撤回此前 `gene_specific_rules.json` 的 `pm2.rules` 规则对象层，避免副本漂移，符合"单一权威源"铁律）。
- 新增【VCEP 路由读取协议】第 3.5 步：查 `00-索引.md` → 定位 `VCEP-<gene>.md` → 读 `#### PM2` 段 → 按原文规则判定（主阈值喂引擎 `pm2_band` 确定性比较 + 取数前提如 Grpmax 分流/亚群排除/95%CI 工具/大变异检查必须执行）→ 索引无该基因/无 PM2 段回退本表或通用。
- 阈值优先级写死：VCEP 官方 > 疾病级特异（第 3 步手抄表）> 通用；**不得以"本表没有该基因"为由漏查 VCEP 路由**。
- **手抄表收缩（对拍后）**：原 7 项疾病级特异与 clingen-vcep 131 基因文件逐一对拍——GJB2/SLC26A4/CDH23/MYO15A/OTOF、PTEN、CDH1、RASopathy、心肌病、PAH 均有 VCEP 基因级规则（更高权威），其疾病级阈值从第 3 步手抄表移除、改走 VCEP 路由；第 3 步表仅保留【无 VCEP 文件基因】TMPRSS3/STRC/GJB6 的 AR-HL 兜底 0.007%（这三个基因特异阈值仅此表这一来源）。thresholds.json / gene_specific_rules.json 的 af_genetic 同步收缩为这 3 基因，与一致性校验对齐。
- **兜底范围锁定（用户拍板）**：0.007% **严格仅限 TMPRSS3/STRC/GJB6 三基因**（无 VCEP 文件，AR-HL 疾病级特异出处《变异解读查询路径》p7 表 + 指南解读 slide 43，仅此来源）。其他 AR-HL 基因（GJB2/SLC26A4/CDH23/MYO15A/OTOF）有 VCEP 文件，禁止套用此值、走 VCEP 路由。三处（SKILL 第 3 步 / thresholds.json / gene_specific_rules.json）均已写死"仅这三基因"。
- 引擎侧同步：`acmg_evidence.py` 撤 `_load_reg()`/全局 `G`/`pm2_by_gene` 规则对象分支/`pm2_band` 的 `gene_specific_src` 参数，恢复"af_genetic 扁平层→通用回退"纯净形态；VCEP 主阈值由子技能路由读取后直传 `pm2_band`。

## v1.1.0

- 新增【阈值选择优先级】——存在基因/疾病特异性阈值时必须优先用特异性阈值，不得一律套用通用阈值；新增【频率数据质量核验】——gnomAD 等低质量/呼叫质量差的位点频率不可靠时须标注并作降权/弃用处理。

## v1.2.0

- 新增遗传方式前置判定硬步骤——判定前必须先调用 `arad-inheritance-judgment` 确认该变异为 AD/XL 或 AR，再选对应 PM2 阈值（通用与特异性阈值均分 AD/AR），禁止默认遗传方式；遗传方式以 ClinVar 患者基因型+PubMed报道+GenCC MOI 三方交叉为准。

## v1.3.0

- 新增【文献核验+可疑文献上报】强制子步骤（特异性阈值出处文献/频率降权引用文献先核验，纯数据库频率判定不触发）

## v1.3.2

- 补跨技能引用声明——凡本技能判定依赖文献检索/核验时，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」与按用途差异化提取；本技能 description 显式声明该跨技能依赖，不再隐式引用。

## v1.3.3（全局维护收敛整改）

- 可疑文献判定完整标准（L1/L2/L3 分级 + 挂载默认可疑 + 强制上报）收敛到唯一权威 `ev-variant-literature-patient`，本技能仅保留按用途定制提取要求，不再内嵌重复完整段。

## v1.4.1（D9′ 落定，2026-10-15）

- **用户拍板确认**：2026-10-15 用户在对话中明确表态「永久固定 PM2_Supporting」——v1.4.0 的领域拍板声明从"待确认"转为**已确认固化**。
- 落地：SKILL.md 补充「永久固定」声明（不得因频率更低/数据更足给 Moderate/Strong）；收尾 `acmg-conflict-summary-output` 分值表 PM2 行同步标注仅 Supporting(+1)。

## v1.4.0（领域拍板，2026-10-15）

- **PM2 强度裁定**：PM2 **永久固定为 `PM2_Supporting`**（除非未来 ACMG/ClinGen 指南更新），现版本一律按 Supporting 强度处理，不降级、不升档争议。
- **两种评级结算方式（经典联合规则 Table5 + Tavtigian 分值）均以证据等级（VeryStrong/Strong/Moderate/Supporting）为统一量纲**：`PM2_Supporting` 即 Supporting，计入 Supporting 桶/SU=1，**不因码属 PM 类而打折、也不升档为 Moderate**；证据码升降级对应"最终使用等级"，与码前缀基线解耦（引擎 `acmg_combine.py` 已按此实现）。
