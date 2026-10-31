# ev-bs1-bs2 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.9.0（BP2 VCEP 适用性路由，2026-10-21）

- **全量探查**：134 个 VCEP 基因文件 **100 个含 `#### BP2` 档位判据**、33 个无段、1 个纯通用。
- **关键形态结论**：多数基因的 BP2 是"反式+已知致病变异（完全外显显性）/顺式+已知致病变异→Supporting"（标准型）；少数计数/点数（APC：反式 1 个 P/LP 或未知相位 ≥3 次→Supporting；BRAF：点数制 ≥-1/-2/-4 Point→Supporting/Moderate/Strong）；个别 NA/升档（KCNQ1 双等位 Jervell-Lange-Nielsen 不适用、SGCG 仅顺式+LGMD VCEP 判 P/LP、VHL 反式+排除先天性红细胞增多症→Strong）。
- 新增【BP2 VCEP 适用性路由协议】：查索引→读 BP2 段→判定形态（标准型/计数点数型/NA/升档）→附加到通用 BP2 判定。通用 BP2 判定（旁置等位穷尽检索 + 相位核对 + 表型旁置）保留不动。
- 自检清单新增【BP2 VCEP 路由闸（v1.9.0）】：评 BP2 前必走路由。

## v1.8.0（BS2 VCEP 路由方案，2026-10-20）

- **全量探查（Windows 重建工作区）**：134 个 VCEP 基因文件扫描，**103 个含 `#### BS2` 段**；其中 **67 个为纯通用定义**（"Observed in a healthy adult individual" 无特异档位，走通用 BS2 判定）、**36 个含特异规则**（19 点数型 + 10 计数型 + 4 数值型 + 2 语义型 + 1 NA）。
- **关键形态结论**：BS2 特异规则是**数值/计数/点数 → 档位**分档（非 AF 频率切点），如 BRCA1 点数 ≥4/2/1（Strong/Moderate/Supporting）、CDH1 例数 ≥10/3、TP53 无癌女性 ≥8/4-7/2-3、F8 因子活性 >40%。少数基因（KCNQ1）VCEP 声明 NA（不完全外显，PMID 23392653）。
- 新增【BS2 VCEP 路由读取协议】第 3.7 步：查 `00-索引.md` → 定位 `VCEP-<gene>.md` → 读 `#### BS2` 段 → 判定段形态（纯通用/NA/特异档位）→ 有特异档位按原文档位喂引擎 `bs2_vcep_band` 确定性比较，纯通用走通用判定，NA 写 BS2 不成立。
- 引擎新增 `bs2_vcep_band(value, gene, spec)` + helper `_bs2_band_match`：spec 形态 `{"type":"band","bands":{"strong":X,"moderate":Y,"supporting":Z},"direction":"ge"|"gt","unit":"points"|"count"|"percent"}`，从高到低取最高达标档，返回 `BS2_Strong/BS2_Moderate/BS2_Supporting` 或 None；已注册 CLI。
- **BS2 取数前提（写死）**：健康成人例数/点数须来自可靠来源（健康人群队列/文献明确"未受累+对应合子状态+早期完全外显"），单来源、不跨源累加（TP53 明确 Cases cannot be counted across sources）；VCEP 额外语义限定（BRCA1 排除 FA 表型、VHL 完整表型筛查）须一并遵守。
- 自检清单新增【BS2 VCEP 路由闸（v1.8.0）】：评 BS2 前必走路由，VCEP 有特异档位则用 VCEP，纯通用用通用判定，NA 写不成立；禁止凭手抄漏查。

## v1.7.0（BA1 VCEP 路由方案，2026-10-20，Windows 重建工作区重做）

- **方向定稿（用户拍板，BA1 与 BS1 完全独立）**：BA1 是强良性独立证据码（Stand Alone，AF 高于疾病发病率的强良性证据），**不能被 BS1 路由覆盖、也不可互相替代**。特异基因 BA1 最终权威源是 ClinGen VCEP 官方规范原文，评级时**直接路由读取** `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### BA1` 段（单一权威源、不落库造副本）。
- **全量探查（Windows 重建工作区重做）**：134 个 VCEP 基因文件扫描，**132 个含 `#### BA1` 段**，全部为单一 `**Stand Alone**` 档位 + 数值切点；无真 NA 基因（个别正文含 "PV=Not Applicable" 仅指致病性判定附注）。形态：单一切点（方向 `ge`/`gt`，如 CDH1 0.2%、ATM >0.5%、SGCA Grpmax FAF >0.002）+ 按遗传方式双切点（如 CDH23/GJB2/USH2A AR≥0.5%/AD≥0.1%、KCNQ1 gnomAD≥0.4%）。
- 新增【BA1 VCEP 路由读取协议】第 3.6 步：查 `00-索引.md` → 定位 `VCEP-<gene>.md` → 读 `#### BA1` 段 → 按原文档位判定（单一切点/按遗传方式分档，切点方向忠实原文 ≥/>，喂引擎 `ba1_vcep_band` 确定性比较）→ 无 BA1 段回退通用阈值（AF>5% 且 ≥2,000 observed alleles，SVI 口径）。
- 引擎新增 `ba1_vcep_band(af, gene, mode, spec)` + helper `_ba1_spec_match`：支持 BA1 切点两种形态（单一切点 `{"cutoff":X,"direction":"ge"|"gt"}` / 按遗传方式 `{"AR":{…},"AD":{…}}`），返回固定档位 `BA1_Stand_Alone` 或 None；已注册 CLI。现有 `bs1_band`/`bs1_vcep_band` 保留不动。
- 自检清单新增【BA1 VCEP 路由闸（v1.7.0）】：评 BA1 前必走路由（查索引→读 BA1 段），VCEP 有规则则用 VCEP，确无才回退通用；禁止凭手抄漏查、禁止与 BS1 混同。

## v1.6.0（BS1 VCEP 路由方案，2026-10-20）

- **方向定稿（用户拍板）**：BS1 特异基因的最终权威源是 ClinGen VCEP 官方规范原文，评级时**直接路由读取** `clingen-vcep/knowledge-base/VCEP-<gene>.md` 的 `#### BS1` 段，**不再落库制造官方副本**（对标 ev-pm2 路由方案，单一权威源）。
- 新增【BS1 VCEP 路由读取协议】第 3.5 步：查 `00-索引.md` → 定位 `VCEP-<gene>.md` → 读 `#### BS1` 段 → 按原文档位判定（单值/两段式/按遗传方式分档，喂引擎 `bs1_vcep_band` 确定性比较）→ 索引无该基因/无 BS1 段回退本表兜底或通用。
- 引擎新增 `bs1_vcep_band(af, gene, mode, spec)` + helper `_bs1_spec_match`：支持 VCEP 档位三种形态（单值 `{"strong":X}` / 两段式 `{"strong":X,"supporting":Y}` / 按遗传方式 `{"AR":{…},"AD":{…}}`）；现有 `bs1_band(af, prevalence)` 通用疾病发病率比较保留不动。
- **手抄表收缩（对拍后）**：原 7 项疾病级特异（RASopathy/CDH1/PTEN/HL/心肌病/PAH）与 clingen-vcep 131 基因文件逐一对拍——所有对应基因均有 VCEP 文件（更高权威，含 MYBPC3=0.0002、MYO15A/OTOF 仅 Supporting 档等精确值），从手抄表移除、改走 VCEP 路由；本表仅保留【无 VCEP 文件基因】GJB6 的 HL-AR 兜底（BS1_Strong ≥0.003 / BS1_Supporting ≥0.0007，来源 ClinGen HL EP v2 PMC6188673，纯 AR 无 AD 档）。gene_specific_rules.json bs1 块同步收缩为 GJB6。
- **兜底范围锁定（用户拍板）**：0.003/0.0007 **严格仅限 GJB6 一基因**（无 VCEP 文件，HL-AR 疾病级特异）。其他 AR-HL 基因（GJB2/SLC26A4/CDH23/MYO7A/TECTA/MYO15A/OTOF）有 VCEP 文件，禁止套用此值、走 VCEP 路由。

## v1.4.0

- 新增跨技能调用声明——BS1 疾病发病率/患病率、BS2 外显率与早期完全外显判断、健康携带流行病学背景，须调用 `ev-disease-info`（NCBI Books GeneReviews 通道，books/medgen/clingen 子命令）获取结构化疾病数据，输出写明子命令与标准疾病名；AF 值仍由频率库取。

## v1.1.0

- 新增遗传方式前置判定硬步骤——判定前必须先调用 `arad-inheritance-judgment` 确认该变异为 AD/XL 或 AR，再选对应 BS1 阈值与 BS2 合子状态，禁止默认遗传方式；遗传方式以 ClinVar 患者基因型+PubMed报道+GenCC MOI 三方交叉为准。

## v1.2.0

- 新增【文献核验+可疑文献上报】强制子步骤（用文献报道健康成人/纯合无表型支撑 BS2 时先核验）

## v1.2.1

- 补跨技能引用声明——凡本技能判定依赖文献检索/核验时，须调用 `ev-variant-literature-patient` 完成「可疑文献上报」与按用途差异化提取；本技能 description 显式声明该跨技能依赖，不再隐式引用。

## v1.3.0

- 同技能补齐 BP2（良性 Supporting）判定段——AR 基因反式检出已知 P/LP（表型已由该 P/LP 或复合杂合组合解释）、或该变异与另一疾病致病变异共存（表型由后者解释）时使用，为 PM3 的方向性良性镜像（变异解读查询路径 5.2.2.4）。

## v1.4.1（全局维护收敛整改）

- 可疑文献判定完整标准（L1/L2/L3 分级 + 挂载默认可疑 + 强制上报）收敛到唯一权威 `ev-variant-literature-patient`，本技能仅保留按用途定制提取要求，不再内嵌重复完整段。

## v1.5.0（BS1 使用限定条件硬闸门）

- BS1 给分前必须满足"疾病高外显早发 + AF 真超疾病发病率阈值"两前提，且不得触发强制排除闸——ClinVar 该基因/变异已有 P/LP 提交、或权威共识/文献提示该变异为已知功能性（低外显率/可变外显率）致病变异（功能实验受损/纯合或复合杂合致病/病例对照富集，如 UGT1A1*6 酶活降低 PMID 9630669/19830808）时，BS1 强制不成立、回致病证据链；不符合任一前提不得给分（实证 UGT1A1 c.211G>A 高频低外显被误判 LB）。
