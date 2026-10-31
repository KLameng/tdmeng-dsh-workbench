---
name: ev-pm1
version: 1.2.0
description: PM1 中等致病证据（位于热点突变区域和/或已知无良性变异的关键功能域）判定。按 指南解读 slide 41-42 与 变异解读查询路径 5.4.1 执行：需文献支撑功能域为突变热点、Regional constraint score(ExAC)≤0.6、Decipher missense constraint≤0.6，并绘制功能域。PM1 仅适用于错义变异；依赖文献时须调用 `ev-variant-literature-patient` 核验并上报可疑文献。特异基因 PM1 位置档位（热点区域/关键功能域的氨基酸/密码子区间、单点集合、结构域类型）以 ClinGen VCEP 官方规范原文为权威源，评级时路由读取 clingen-vcep/VCEP-<gene>.md 的 #### PM1 段（见第 3.5 步路由协议，v1.2.0 新增）。
---


# PM1：热点区域 / 关键功能域证据

## 定义（原文）

PM1：位于热点突变区域，和/或位于已知无良性变异的关键功能域（如酶的活性位点）。

## 操作步骤（指南解读 slide 41；变异解读查询路径 5.4.1）

1. **文献支撑**：有文献支撑待分类变异所在蛋白功能域为突变热点。

> **⚠ 文献核验 + 可疑文献上报（引用唯一权威，PM1 凡依赖文献支撑"功能域为热点"时必须执行）**
> **PM1 的"文献支撑功能域为突变热点"依赖文献检索，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」判定（L1/L2/L3 分级 + 挂载默认可疑 + 强制上报的完整判定标准，唯一以该技能为准）；判定输出须含"本次计入文献核验等级(L1/L2/L3)"。**

2. **Regional constraint score（ExAC）≤ 0.6**：在 DECIPHER 数据库查询。https://www.deciphergenomics.org/
3. **绘制功能域**：在 pubvar、gnomAD variant、HGMD/ClinVar 上标注变异位点位置。
4. **Decipher missense constraint ≤ 0.6**。

> PM1 仅适用于错义变异。

> **⚠ 约束取数 fallback 分支（v1.1.0，硬步骤——防"把 RMC NOT FOUND 当无约束证据 / 漏查 DECIPHER / 带可解争议进收尾"，实证 COL7A1：ExAC RMC 仅 2701 基因未覆盖，第一轮误标"争议"且 DECIPHER 基因级约束漏查）**
> 约束取数（区域级 RMC + 基因级）走固定链路，区域级用 `ev-gnomad-constraint` 的 `query_constraint.py --exac-rmc`、基因级用 gnomAD v4/v2（`mis.z_score`/`mis_z`）+ DECIPHER 基因级 missense 约束（Missense Z / pDN）。**任一通道返回 NOT FOUND，不得直接判"无约束证据"，必须依次走完：**
> 1. **先识别 NOT FOUND 类型**：是"基因不在数据集（资源未覆盖，如 ExAC RMC 仅 2701 基因）"还是"该基因有数据但该区域/指标确无约束"；
> 2. **缺数据≠反对（写死）**：基因不在数据集 → **不得据此作为不支持 PM1 的证据**（ev-gnomad-constraint §结果解读："若基因不在数据集中，不能以此作为不支持 PM1 的证据"）；
> 3. **同轮切替代通道（fallback，写死）**：区域级 RMC 取不到时，**必须同一判定轮内立即**走 DECIPHER 基因级 missense 约束 + G2P/ClinGen 致病机制（显性负效/功能获得等）+ 结构域热点文献（走 `ev-variant-literature-patient` 可疑文献核验），综合判断"该位点所在功能域是否为关键/热点"，能定则定；
> 4. **替代通道能定 → 直接"确信"**：若基因级强约束 + 机制 + 结构域热点文献足以支撑功能域关键/热点 → 本码**直接定"确信"**（按 PM1 正常档位），**不得带"争议"进收尾**；
> 5. **替代通道也取不到** → 才允许写"查不到"，并如实标注是"资源未覆盖（基因不在数据集）"还是"确无约束数据"；
> 6. **铁律（漏做≠查不到）**：约束取数必须**实际发起**（区域级 RMC + 基因级至少各查一次），不得因"没发起查询"而写"查不到"或标"争议"——把"没查"当"查不到"是违规，须补查后再判。

### 第 3.5 步：PM1 VCEP 路由读取协议（v1.2.0 新增，权威源=clingen-vcep 原文）

> **⚠ 有 ClinGen VCEP 文件的基因，其 PM1 特异位置档位（热点区域/关键功能域的氨基酸/密码子区间、单点集合、结构域类型）一律以 `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### PM1` 段原文为权威源，由本步路由读取，不靠手抄（对标 ev-pm2 路由方案，单一权威源）。** 通用 PM1 判定（文献 + Regional constraint + Decipher constraint）用于**无 VCEP PM1 规则**的基因；有 VCEP 特异位置档位的基因**优先以 VCEP 位置匹配定档**。

**探查结论（2026-10-20，Windows 重建工作区）**：134 个 VCEP 基因文件 87 个含 `#### PM1` 段，形态分布——**54 个 POSITIONS**（有明确氨基酸/密码子区间或单点集合，如 MYH7 密码子 167-931、MYBPC3 485-502+1248-1266、BMPR2 关键氨基酸列表、ACADVL 区间+单点混合、PAH 活性位点列表）+ **13 个 STRUCTURAL_DOMAIN**（结构域/基序/表引用型，如 FBN1 cbEGF、SCN1A Pathogenic Enriched Region 附表）+ **18 个 NA**（不适用）+ **2 个 CANCERHOTSPOTS**（TP53/VHL，依赖 cancerhotspots 体细胞计数 + 特定位置）。

1. **定位 VCEP 文件**：查 `clingen-vcep/knowledge-base/00-索引.md`，定位该基因的 `VCEP-<gene>.md`；
2. **读 PM1 段**：打开 `VCEP-<gene>.md`，定位 `#### PM1` 段（若文件无此段 → 该基因 VCEP 无 PM1 规则，跳第 4 步）；
3. **判定 PM1 段形态**：
   - **POSITIONS（有明确氨基酸/密码子区间或单点）**：提取各档位位置集合，喂引擎 `pm1_vcep_band(aa_pos, gene, spec)` 做位置匹配（spec 形态：`{"type":"region","bands":{"strong":[{"pos":X}...或{"lo":L,"hi":H}...],"moderate":[...],"supporting":[...]}}`，从高到低取最高命中档）。**取数前提必须执行**：确定变异的**氨基酸位置**（由变异 cDNA 改变换算，须注明转录本，如 MYH7 NM_000257.4、TP53 NM_00546.4）并核对是否在 VCEP 指定区域/转录本内；VCEP 有额外限定（MYH7/MYBPC3 仅限 HCM 表型、不得与 PM5 合用）须一并遵守（表型限定由执行者判，与 PM5 合用由收尾互斥矩阵管）。输出须标注 `PM1 规则来源=VCEP-<gene>.md（ClinGen VCEP 官方）`；
   - **CANCERHOTSPOTS（TP53/VHL 等）**：位置匹配 + cancerhotspots 体细胞计数（≥10 次同 AA → 高档，2-9 次 → 低档），位置喂引擎、计数由执行者从 cancerhotspots.org 取数判档；
   - **STRUCTURAL_DOMAIN（FBN1 cbEGF、SCN1A 附表等）**：按原文结构域/基序描述人工判定（无法单值位置匹配），需参考结构域表/附图；
   - **NA / Not applicable** → 该基因 VCEP 声明 PM1 不适用，写"该基因 VCEP 声明 PM1 不适用"，PM1 不成立；
   - **无特异位置档位（纯通用）** → 用通用 PM1 判定（上述文献 + Regional constraint + Decipher constraint）。
4. **索引无该基因 / 该基因 VCEP 无 PM1 段** → 回退通用 PM1 判定，并注明"该基因无 ClinGen VCEP PM1 规则，用通用判定"。

**阈值选择优先级（写死）**：

1. **VCEP 有 PM1 特异位置档位**（POSITIONS/CANCERHOTSPOTS）→ 一律以 VCEP 原文档位判定（如 MYH7 167-931 Moderate、BMPR2 关键氨基酸、TP53 密码子 175/245/248/249/273/282 + cancerhotspots 计数）；
2. **VCEP 结构域型**（STRUCTURAL_DOMAIN）→ 按原文结构域描述判定；
3. **VCEP 纯通用 / 无 PM1 段** → 用通用 PM1 判定（文献 + 约束分值）；
4. **VCEP 声明 NA** → PM1 不成立；
5. **记录要求**：判定 PM1 时必须在输出中写明"所用判据（通用/VCEP 官方位置档位）"及"该判据来源"，查不到特异位置档位时写"查不到特异 PM1 位置档位，用通用判定"。
6. **铁律**：**不得以"本表没有该基因"为由漏查 VCEP 路由**——评 PM1 前必先走上述路由（查索引→读 PM1 段），VCEP 有规则则用 VCEP，确无才回退。**禁止**凭手抄表把某基因判为"无特异位置"。

> **🔧 确定性比较（acmg_evidence.py）**：变异氨基酸位置 vs 位置集合用 `scripts/acmg_evidence.py` 的 `pm1_vcep_band(aa_pos, gene, spec)` 确定性输出（spec 为路由读取的 VCEP 位置档位结构，返回 `PM1_Strong/PM1_Moderate/PM1_Supporting` 或 None）。用法：`python acmg_evidence.py pm1_vcep_band <AA_POS> <GENE> <spec-json>`。

## 辅助支撑要素（可选，仅供佐证，不改变判定标准）

以下内容**仅作为 PM1 判定"该位点是否位于关键功能域/热点区域"的辅助参考**，**不改变 PM1 证据码的使用标准、阈值、等级或互斥规则**；PM1 是否成立、用哪个等级，仍以上方操作步骤（文献 + Regional constraint + Decipher constraint）为准。

- **结构辅助（AlphaFold2 / PDB）**：可用 AlphaFold2 预测结构或 PDB 实验结构辅助判断残基是否位于催化/活性位点、结构核心、配体结合界面等。参考维度（仅辅助）：
  - 残基埋藏（buried）/表面（surface）；
  - 是否位于已知功能域/活性位点（可查 UniProt feature、InterPro）；
  - 结构置信度 pLDDT：>90 极高、70–90 高、50–70 中、<50 低（无序区）。
  - **约束**：AlphaFold2 为预测结构，不能单独作为 PM1 依据；结构辅助仅在文献/约束分值已指向关键功能域时作为佐证，不得反向推翻判定。AlphaFold2 对超大蛋白（>2700 aa）可能无预测，需回退 PDB 实验结构或文献。
- **查询入口（仅辅助取数，评级字段不可用）**：UniProt https://www.uniprot.org/ ；PDB https://www.rcsb.org/ ；AlphaFold Protein Structure Database https://alphafold.ebi.ac.uk/ （或经相关 API）。

## 案例（指南解读 slide 42）

GCDH c.416C>G：PM1（热点区域/关键功能域，PMID:24332224），配合 PM2_Supporting、PM5（同一位点 p.Ser139Leu 致病）、PP3_Strong(REVEL=0.98)，评为可能致病。

## 自检清单

- [ ] 变异为错义。
- [ ] 有文献证明该功能域为热点。
- [ ] **已执行「可疑文献上报」核验（强制，判定标准唯一以 `ev-variant-literature-patient` 为准，对应正文 v4.2.0 文献核验子步骤）：凡依赖文献支撑"功能域为热点"，命中 ClinVar/HGMD 挂载文献默认可疑、或无法核验全文/标题摘要检索不到该功能域的判定标准时，已把 PMID+链接+原因上报用户人工核验；未核验到"该功能域确为突变热点"事实前，未把文献静默当作已核实证据计入；输出已含"本次计入文献核验等级(L1/L2/L3)"。**
- [ ] ExAC Regional constraint ≤0.6 且 Decipher missense constraint ≤0.6。
- [ ] **已执行"约束取数 fallback 分支"（v1.1.0）：约束取数（区域级 RMC + 基因级）均已实际发起；任一通道 NOT FOUND 时已先识别是"资源未覆盖"还是"确无约束数据"——基因不在数据集已按"缺数据≠反对"处理（未据此作为不支持 PM1 的证据）；区域级取不到已同轮切替代通道（DECIPHER 基因级约束 + 机制 + 结构域热点文献），能定已直接定"确信"、未带"争议"进收尾；实在取不到才写"查不到"并标注类型；未把"没查"当"查不到"。**
- [ ] 已绘制功能域并标注位点。
- [ ] **PM1 VCEP 路由闸（v1.2.0）：已查 00-索引→读 VCEP-<gene>.md 的 #### PM1 段；VCEP 有特异位置档位（POSITIONS/CANCERHOTSPOTS）→ 已按原文档位喂 pm1_vcep_band 判定并标注来源（注明转录本）；VCEP 结构域型 → 已按原文结构域描述判定；VCEP 声明 NA → 已写 PM1 不成立；VCEP 纯通用/无段 → 已用通用 PM1 判定。未凭手抄漏查 VCEP 路由。**

## 输出格式（强制，本 SKILL 判定完成后必须按此输出）

每个证据码判定完成后，**必须**按下述三点完整输出；缺一不可，查不到的数据明确写 **"查不到"**，严禁用本 SKILL 内的举例数据或推测代替。

### 1. 证据码 + 对应等级
`[证据码]_[使用等级]`，如 `PM3_Strong`、`PP3_Moderate`、`PM2_Supporting`。未成立则写"本证据不成立/弃用"。

### 2. 支持该等级使用的规则性数据内容 + 定级规则
- 写明支撑该等级判定的**具体数据值**（如人群频率、REVEL 分数、反式例数、对照数目、OR 值、分离次数等）；
- 对照本 SKILL 的定级规则/阈值表，说明该数据落在哪个区间/档位，从而定为该等级；
- 即：数据值 → 落入的规则档位 → 所得等级，三步闭环。

### 3. 查询路径
列出本次判定**实际查询过**的数据库链接、文献编号(PMID)及对应链接；**每次查询都必须是真实查询**。
- 数据库：名称 + URL（如 ClinVar、gnomAD、Pubvar、OMIM、HGMD、ClinGen 等）；
- 文献：PMID 编号 + 链接；
- 某项查不到：写 **"查不到"**，不得以举例数据填充。

> **铁律**：本 SKILL 内所有"案例/示例/举例"仅供教学演示，**禁止**作为评级数据套用；评级数据一律来自实际查询，否则该证据码不得计入。
