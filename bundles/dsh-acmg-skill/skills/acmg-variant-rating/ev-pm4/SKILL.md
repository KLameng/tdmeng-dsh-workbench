---
name: ev-pm4
version: 1.3.0
description: PM4 中等致病证据（非重复区框内插入/缺失或终止密码子丧失导致蛋白长度变化）与 BP3（支持良性，框内 indel 位于功能未知重复区域且进化非保守）判定，成对放在同一SKILL。按 指南解读 slide 48 与 变异解读查询路径 5.3.4.1/5.3.4.2 执行：PM4 用于 indel 位于非重复区域、进化保守、插入/缺失小于 1 个外显子或终止密码子变异引起蛋白长度变化；BP3 用于框内 indel 位于重复/功能未知区域且进化非保守、预期不改变蛋白功能时，为 PM4 的良性镜像。特异基因 PM4 的框内 indel AA 长度切点（≥2 AA→Moderate、1 AA→Supporting）与 BP3 适用性/区域限定（特定重复区位置/NA）以 ClinGen VCEP 官方规范原文为权威源，评级时路由读取 clingen-vcep/VCEP-<gene>.md 的 #### PM4 / #### BP3 段（见第 4 步路由协议 + BP3 VCEP 适用性路由协议，v1.3.0 新增 BP3 路由）。
---

# PM4 / BP3：框内插入/缺失证据

## 定义（原文）

PM4：非重复区框内插入/缺失或终止密码子丧失导致的蛋白质长度变化。

## 操作步骤（指南解读 slide 48；变异解读查询路径 5.3.4.1）

须同时满足：
1. 插入/缺失位于**非重复区域**；
2. **进化保守**；
3. 插入/缺失变异**小于 1 个外显子**，或为终止密码子变异引起蛋白长度变化。

> 良性端对应 BP3（变异解读查询路径 5.3.4.2）：插入/缺失位于功能未知重复区域、且进化非保守。

## BP3：框内插入/缺失位于功能未知重复区域（良性 Supporting）

### 定义（原文）
BP3：框内插入/缺失位于蛋白质的重复区域或功能未知区域，且插入/缺失不改变蛋白质功能。证据强度：良性 Supporting。

### 操作步骤（变异解读查询路径 5.3.4.2，PM4 的良性镜像）
须同时满足：
1. 插入/缺失位于**重复区域（重复序列/结构域重复）或功能未知区域**；
2. **进化非保守**（该区域跨物种不保守）；
3. 插入/缺失为**框内**（不引起移码），且预期**不改变蛋白质功能**。

### 与 PM4 的关系
PM4（非重复区+保守+蛋白长度变化 → 致病）与 BP3（重复区+非保守+不改变功能 → 良性）是**同一框内 indel 判定的两侧**，**互斥**——裁决统一以收尾技能 `acmg-conflict-summary-output` §1.1 互斥矩阵为准。

### 案例（教学演示，非真实评级数据）
- 某基因蛋白含串联重复结构域，某框内插入位于该重复结构域内且进化不保守 → 可考虑 BP3。

### 真实判例（已核实真实判例，查询路径可复现；评级时仍须按查询路径实际查询）

> 以下判例仅用于展示 BP3 判定路径，**禁止**作为评级数据直接套用；评级时须重新核对 indel 位置（是否重复/功能未知区）、进化保守性与框内状态。

**判例 BP3-成立（重复区内框内 indel，判良性 → BP3 结构适用）**
- 变异：**ARX c.441_464del（p.Ala148_Ala155del），rs398124510**（24 bp 缺失 = 8 个框内丙氨酸缺失）。
- 来源：ClinVar VCV000096454.60（https://www.ncbi.nlm.nih.gov/clinvar/variation/96454/ ），多提交者判 **Benign/Likely benign（Benign 4 + Likely benign 4）**，X 连锁神经发育障碍。
- 权威分类：Benign/Likely benign（多提交者一致，无冲突）。
- 判定路径要点：该 24 bp 缺失位于 ARX **多聚丙氨酸（polyalanine）串联重复区内**、为框内缺失、删除 8 个 Ala——正是 BP3"框内 indel 位于重复区域"的结构范式。**如实标注**：提交者实际明确标注的良性码为 BS2（CeGaT："ARX: BS2"，即在未受累个体中观察到）+ 通用良性组合，BP3 为该变异在机制上可适用的旁证码，而非提交者逐字标注；评级时不得把本例直接当 BP3 计，须自行复核"重复区+进化非保守+不改变功能"三要素。
- **查不到如实标注**：经本轮检索，ClinVar 中**逐字以 BP3 为标注码的多星/VCEP 良性判例极少**（多数 VCEP 因基因不含"无功能重复区"而将 BP3 设为不适用，见下），故以本结构判例 + 机制闸补足，未编造逐字 BP3 标注案例。

**判例 BP3-不成立（基因不含无功能重复区 / indel 位于保守功能区 → BP3 不成立）**
- 依据：**ClinGen 髓系肿瘤 VCEP（RUNX1）规范原文——"RUNX1 does not contain a repetitive region without known function. BP3 is therefore deemed not applicable."**
- 判定路径要点：当该基因**不存在"功能未知的重复区域"**（如 RUNX1），或本 indel 虽为框内但位于**进化保守的关键功能域**（应反向走 PM4）时，BP3 **不成立出口**：写"基因无适用重复区 / indel 位于保守功能域，BP3 不成立"。

### BP3 穷尽检索专项 / 判定完成闸
判定 BP3 前**必须**完成：
1. **三要素同时成立核对**：①indel 为框内（不引起移码）；②位于重复序列/结构域重复或功能未知区（经 Pfam/Uniprot/RepeatMasker 核对）；③该区域**进化非保守**且预期不改变蛋白功能；
2. **重复区性质检索**：确认该重复区确为"功能未知/多态性重复"，而非已知致病重复扩增区（如 ARX polyA 扩张、HTT CAG 扩张等属致病区，其 indel 不能套 BP3）；
3. **与 PM4 互斥核对**：若 indel 位于**非重复且保守**区域 → 反向走 PM4，BP3 不成立；
4. **不成立出口**：基因无适用重复区、indel 跨保守功能域、或为已知致病重复区的改变 → 一律写"BP3 不成立"。

### BP3 VCEP 适用性路由协议（v1.3.0 新增，权威源=clingen-vcep 原文）

> **⚠ 有 ClinGen VCEP 文件的基因，其 BP3 适用性/区域限定（该基因是否适用 BP3、特定重复区位置、是否 NA）一律以 `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### BP3` 段原文为权威源，由本步路由读取，不靠手抄。** 通用 BP3 判定（三要素 + 重复区性质 + PM4 互斥）用于**无 VCEP BP3 特异规则**的基因。

**探查结论（2026-10-21，Windows 重建工作区）**：134 个 VCEP 基因文件 **34 个含 `#### BP3` 档位判据**、99 个无段、1 个 NA（verification-evidence）。核心形态——
- **标准型（多数）**：框内 indel 位于重复区且不影响蛋白功能 → Supporting（SCN1A/SCN2A/SCN8A/PDHA1/POLG 等，与 Richards 2015 原文一致）；
- **特定重复区限定型**：VHL（仅 8x GXEEX AA 重复基序 AA14-AA48，其余编码区无重复→不适用）；RPGR（仅 ORF15 重复区 AA585-1078）；CDH23/COCH/GJB2/KCNQ4/MYO6/MYO7A/OTOF/SLC26A4/TECTA/USH2A（重复区无已知功能→Supporting）；
- **NA / not applicable** → 该基因 VCEP 声明该码不适用，写"该基因 VCEP 声明 BP3 不适用"。

1. **定位 VCEP 文件**：查 `clingen-vcep/knowledge-base/00-索引.md`，定位该基因的 `VCEP-<gene>.md`；
2. **读 BP3 段**：打开 `VCEP-<gene>.md`，定位 `#### BP3` 段（若无 → 该基因 VCEP 无 BP3 特异规则，跳第 4 步）；
3. **判定各段形态**：
   - **标准型**（框内 indel 重复区无已知功能→Supporting）→ 套通用 BP3 判据，注明"该基因 VCEP 为标准型 BP3"；
   - **特定重复区限定型**（VHL GXEEX AA14-48 / RPGR ORF15 AA585-1078）→ 按原文位置集合判定：indel 位于指定重复区→Supporting，否则不成立；
   - **NA / not applicable** → 该码不成立，写"该基因 VCEP 声明 BP3 不适用"；
4. **索引无该基因 / 该基因 VCEP 无 BP3 段** → 回退通用 BP3 判定，注明"该基因无 ClinGen VCEP BP3 规则，用通用判定"。

**BP3 记录要求（写死）**：判定时必须在输出写明"所用判据（通用/VCEP 官方）"及"该判据来源"；查不到特异规则时写"查不到特异 BP3 规则，用通用判定"。**禁止**凭手抄把某基因判为"无特异规则"——评 BP3 前必先走路由（查索引→读 BP3 段）。

## 第 4 步：PM4 VCEP 路由协议（v1.2.0 新增，权威源=clingen-vcep 原文）

> **⚠ 有 ClinGen VCEP 文件的基因，其 PM4 特异规则（框内 indel AA 长度切点）一律以 `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### PM4` 段原文为权威源，由本步路由读取，不靠手抄（对标 ev-pm2 路由方案，单一权威源）。** 通用 PM4 判定（框内 indel < 1 个外显子或终止密码子丧失）用于**无 VCEP PM4 AA 切点**的基因。

**探查结论（2026-10-21，Windows 重建工作区）**：134 个 VCEP 基因文件 **103 个含 `#### PM4` 段**（其中 7 个 AA_COUNT_BANDS + 2 个 RESIDUE_POS + 94 个 SEMANTIC/通用）、15 个 NA、16 个无段。可数值化的**AA 长度切点**（≥2 AA→Moderate、1 AA→Supporting）在 **7 个基因**明确给出（ABCA4/AIPL1/CTLA4/GAA/GUCY2D/IDUA/RPE65），另有 DICER1/RUNX1 为特定残基位置（类似 PM1）。

1. **定位 VCEP 文件**：查 `clingen-vcep/knowledge-base/00-索引.md`，定位该基因的 `VCEP-<gene>.md`；
2. **读 PM4 段**：打开 `VCEP-<gene>.md`，定位 `#### PM4` 段（若无 → 该基因 VCEP 无 PM4 特异规则，跳第 4 步）；
3. **判定各段形态**：
   - **AA 计数档位（7 基因）**：提取 AA 数档位表，喂引擎 `pm4_vcep_band(n_aa, gene, spec)` 做计数比较（spec 形态：`{"type":"band","bands":{"moderate":2,"supporting":1},"unit":"amino_acid"}`，≥2 AA→PM4_Moderate、1 AA→PM4_Supporting）。**前置条件由执行者核验**（见下），引擎只做 AA 数档位比较。输出须标注 `PM4 规则来源=VCEP-<gene>.md（ClinGen VCEP 官方）`；
   - **特定残基位置（2 基因）**：DICER1（RNase IIIb 域 p.Y1682–p.S1846 内→Moderate、域外且非重复区→Supporting）、RUNX1（RHD 内特定 AA 残基→Moderate、RHD 内其他 89-204 残基→Supporting、终止密码子丧失→PM4）——按原文位置集合判定，不喂 AA 数引擎；
   - **SEMANTIC / 纯通用（94 基因）**：用通用 PM4 判定（框内 indel < 1 个外显子或终止密码子丧失）；
   - **NA / Not applicable** → 该基因 VCEP 声明该码不适用（如 MYH7、MYBPC3、MYL2/MYL3、TNNI3 等心肌病基因，LOF/框内 indel 非致病机制），写"该基因 VCEP 声明该码不适用"，不成立；
   - **无特异规则（纯通用）** → 用通用 PM4 判定。
4. **索引无该基因 / 该基因 VCEP 无 PM4 段** → 回退通用 PM4 判定，注明"该基因无 ClinGen VCEP PM4 规则，用通用判定"。

**PM4 前置条件（无论通用或 VCEP，写死）**：①框内（不引起移码）；②位于**非重复区域**；③**进化保守**（VCEP AA 切点基因常附加 PhyloP 阈值，如 ABCA4 需 PhyloP≥7.367、GUCY2D/AIPL1/RPE65 需 PhyloP>2.0，ABCA4 的 >1 AA 或 1 核苷酸 PhyloP 阈值二选一）；④indel < 1 个外显子或终止密码子丧失。**引擎只做 AA 数档位比较；PhyloP/非重复区/框内由执行者先查数据核验后再喂引擎。**

**阈值选择优先级（写死）**：

1. **VCEP 有 AA 计数档位**（7 基因）→ 一律以 VCEP 原文档位判定（如 ABCA4/GAA/IDUA ≥2→Moderate、1→Supporting）；
2. **VCEP 有特定残基位置**（DICER1/RUNX1）→ 按原文位置集合判定；
3. **VCEP SEMANTIC / 纯通用**（94 基因）→ 用通用 PM4 判定；
4. **VCEP 声明 NA** → 该码不成立；
5. **记录要求**：判定 PM4 时必须在输出中写明"所用判据（通用/VCEP 官方）"及"该判据来源"，查不到特异规则时写"查不到特异 PM4 规则，用通用判定"。
6. **铁律**：**不得以"本表没有该基因"为由漏查 VCEP 路由**——评 PM4 前必先走上述路由（查索引→读 PM4 段），VCEP 有规则则用 VCEP，确无才回退。**禁止**凭手抄表把某基因判为"无特异规则"。

> **🔧 确定性比较（acmg_evidence.py）**：框内 indel AA 数 vs 档位用 `scripts/acmg_evidence.py` 的 `pm4_vcep_band(n_aa, gene, spec)` 确定性输出（spec 为路由读取的 VCEP PM4 AA 档位结构，返回 `PM4_Moderate/PM4_Supporting` 或 None）。用法：`python acmg_evidence.py pm4_vcep_band <N_AA> <GENE> <spec-json>`。

## 互斥裁决（移交收尾技能，本技能不执行）

按全局约束：**互斥原则只在收尾技能 `acmg-conflict-summary-output` 统一裁决**，证据码子技能不做互斥。本技能只做 PM4 自身判定，**不因与 PVS1/PS1/PS3/PM5/PP1/PP2 等码互斥而弃用、降档或拒用 PM4**；是否保留/弃用由收尾技能按证据强度与互斥矩阵统一裁决。

## 案例（指南解读 slide 45）

MMACHC c.658_660del：使用 PM4（非重复区框内缺失致蛋白长度变化）。

## 自检清单

- [ ] 框内 indel 或终止密码子丧失。
- [ ] 位于非重复区域、进化保守。
- [ ] indel < 1 个外显子（或终止密码子丧失）。
- [ ] **BP3：已确认 indel 位于重复/功能未知区域、进化非保守、框内且不改变蛋白功能。**
- [ ] **BP3 穷尽闸（v19）：已经 Pfam/Uniprot/RepeatMasker 核对 indel 位于"功能未知重复区"（非已知致病重复扩增区）、进化非保守、框内；基因无适用重复区（如 RUNX1 VCEP 判 not applicable）或 indel 跨保守功能域（应反向走 PM4）者已走"BP3 不成立"出口（参照 ARX c.441_464del 重复区框内缺失 判例；逐字 BP3 标注多星判例查不到已如实标注）。**
- [ ] **BP3 VCEP 路由闸（v1.3.0）：已查 00-索引→读 VCEP-<gene>.md 的 #### BP3 段；标准型（框内 indel 重复区无已知功能→Supporting）→ 已按通用判据并注明 VCEP 标准型；特定重复区限定型（VHL GXEEX AA14-48 / RPGR ORF15 AA585-1078）→ 已按原文位置集合判定；VCEP 声明 NA → 已写不成立；VCEP 无段 → 已用通用判定。未凭手抄漏查 VCEP 路由。**
- [ ] 互斥裁决统一在收尾技能 `acmg-conflict-summary-output` 执行（本技能不据此弃用/降档）。
- [ ] **PM4 VCEP 路由闸（v1.2.0）：已查 00-索引→读 VCEP-<gene>.md 的 #### PM4 段；VCEP 有 AA 计数档位（≥2→Moderate/1→Supporting，7 基因）→ 已按原文档位喂 pm4_vcep_band 判定并标注来源；VCEP 有特定残基位置（DICER1/RUNX1）→ 已按原文位置集合判定；VCEP SEMANTIC/纯通用 → 已用通用判定；VCEP 声明 NA → 已写该码不成立。未凭手抄漏查 VCEP 路由。**

---

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
