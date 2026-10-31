# ev-pm1 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.2.0（PM1 VCEP 路由方案，2026-10-20）

- **全量探查（Windows 重建工作区）**：134 个 VCEP 基因文件扫描，**87 个含 `#### PM1` 段**；形态分布——**54 POSITIONS**（明确氨基酸/密码子区间或单点，如 MYH7 167-931、MYBPC3 485-502+1248-1266、BMPR2 关键 AA 列表、ACADVL 区间+单点、PAH 活性位点）+ **13 STRUCTURAL_DOMAIN**（FBN1 cbEGF、SCN1A 附表）+ **18 NA** + **2 CANCERHOTSPOTS**（TP53/VHL）。
- **关键形态结论**：PM1 特异规则本质是"变异氨基酸位置是否落入 VCEP 定义的热点/关键功能域位置集合"（区间/单点），非数值切点。通用 PM1（文献+Regional constraint+Decipher constraint）用于无 VCEP PM1 规则的基因。
- 新增【PM1 VCEP 路由读取协议】第 3.5 步：查索引→读 PM1 段→判定形态（POSITIONS/CANCERHOTSPOTS/STRUCTURAL_DOMAIN/NA/纯通用）→POSITIONS 喂引擎 `pm1_vcep_band` 位置匹配、CANCERHOTSPOTS 位置+体细胞计数、STRUCTURAL_DOMAIN 按原文描述、NA 写不成立、纯通用用通用判定。
- 引擎新增 `pm1_vcep_band(aa_pos, gene, spec)` + helper `_pm1_pos_match`：spec 形态 `{"type":"region","bands":{"strong":[{"pos":X}或{"lo":L,"hi":H}],"moderate":[...],"supporting":[...]}}`，从高到低取最高命中档，返回 `PM1_Strong/PM1_Moderate/PM1_Supporting` 或 None；已注册 CLI。
- **PM1 取数前提（写死）**：变异氨基酸位置由 cDNA 改变换算并注明转录本（MYH7 NM_000257.4、TP53 NM_00546.4）；VCEP 额外限定（MYH7/MYBPC3 仅限 HCM 表型、不得与 PM5 合用）须一并遵守（表型由执行者判，与 PM5 合用由收尾互斥矩阵管）。
- 自检清单新增【PM1 VCEP 路由闸（v1.2.0）】：评 PM1 前必走路由，VCEP 有位置档位则用 VCEP，结构域型按原文，NA 写不成立，纯通用用通用判定；禁止凭手抄漏查。

## v1.0.1

- 补跨技能引用声明——凡本技能判定依赖文献检索/核验时，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」与按用途差异化提取；本技能 description 显式声明该跨技能依赖，不再隐式引用。

## v1.0.2（全局维护收敛整改）

- 可疑文献判定完整标准（L1/L2/L3 分级 + 挂载默认可疑 + 强制上报）收敛到唯一权威 `ev-variant-literature-patient`，本技能仅保留按用途定制提取要求，不再内嵌重复完整段。

## v1.1.0（约束取数 fallback 分支，2026-10-16 用户复盘"RMC NOT FOUND 被当无约束/漏查 DECIPHER"）

- **根因**：COL7A1 实测——ExAC RMC 仅 2701 基因未覆盖 COL7A1，第一轮误判"该区域无约束证据"并标"争议"；且 DECIPHER 基因级约束分第一轮漏做（没发起查询），却写成"未取到"（把"没查"当"查不到"）。ev-pm1 操作步骤无 NOT FOUND 处理分支，且未引用 ev-gnomad-constraint 的"缺数据≠反对"规则（该技能第56行）。
- **落地**：ev-pm1 操作步骤新增「约束取数 fallback 分支」硬步骤——①识别 NOT FOUND 类型（资源未覆盖 vs 确无约束数据）；②基因不在数据集按"缺数据≠反对"处理（不得据此不支持 PM1，引用 ev-gnomad-constraint）；③区域级取不到**同轮立即**切替代通道（DECIPHER 基因级 missense 约束 + G2P/ClinGen 机制 + 结构域热点文献，走 ev-variant-literature-patient 核验）；④替代通道能定 → 直接定"确信"，不得带"争议"进收尾；⑤实在取不到才"查不到"并标注类型；⑥铁律"漏做≠查不到"（约束取数必须实际发起 RMC+基因级，不得因没查写查不到/标争议）。
- 纯文字规则，无引擎改动；与其他 ev-* 技能正交（缺数据≠反对唯一权威在 ev-gnomad-constraint，本技能仅引用）。
