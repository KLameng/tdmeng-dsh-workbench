---
name: acmg-variant-rating
description: 孟德尔疾病基因序列变异的 ACMG/AMP 2015 致病性分类成套技能群（22 个 SKILL：1 总调度 + 1 收尾 + 1 遗传方式前置 + 19 证据码/取数）。给定基因名+cDNA/蛋白改变（或 rsID/CA ID），按"身份归一化→遗传方式前置→按变异类型圈定证据码→逐码判定→互斥汇总双套定级"出 P/LP/VUS/LB/B。触发词：ACMG 评级、变异评级、致病性分类、证据码、PVS1/PS/PM/PP/BS/BP/BA1、这个变异致不致病、给变异定个级。
---

# ACMG 单病变异评级技能群 · 身份说明书（dsh 挂载版）

> 本文件是给 dsh 调度大模型看的"身份说明书 + 路由图"。**完整判定方法论不在此重复**——读到本说明书后，按下面的路由去读对应子技能的 `SKILL.md`，并严格照其流程执行。所有路径相对本技能群根目录 `skills/acmg-variant-rating/`（下称"群根"）。

智能分析结果，仅供参考。本技能群**给证据不给最终医疗结论**，P/LP/VUS/LB/B 分类与 PGT/报出决策须由有资质人员复核。

## 1. 我是谁

一套对**孟德尔疾病相关基因的序列变异**做 ACMG/AMP 2015 致病性分类的**技能群**，不是单一技能。核心原则：**裁决权不下放给模型内部知识**——所有外部事实（遗传模式、频率、阈值、疾病表型、文献结论）必须来自知识图 `config/knowledge_graph.json`、阈值表 `config/thresholds.json`、确定性引擎 `scripts/acmg_evidence.py`·`scripts/acmg_combine.py` 或实时数据库，**禁止用"我记得/一般这种基因是 X"填补**。

## 2. 什么时候调用我

- 用户给了一个**具体变异**（基因名 + c.HGVS / p.HGVS，或 rsID / ClinGen CA ID / 基因组坐标），问它致不致病、要 ACMG 证据码、要 P/LP/VUS 定级。
- 用户要对单个变异做证据梳理、频率/计算预测/文献/功能实验取证、或要双套定级（表5 卡式 + Tavtigian 分值）。
- 高频形态：单变异直查（基因+cDNA/蛋白改变），不是上传全 VCF 批量筛选。

## 3. 什么时候**别**调用我（边界与转接）

- **SF 次要发现报出 / WES 报出位置 / PGT-M 决策**：不属本群，转独立的携筛-WES-PGT 遗传咨询技能群（`carrier-screen-wes-pgt-counseling`）。本群只出变异评级。
- **AI/大模型系统自身的错误归类**：那是 TACT 三轴检查法的活，不是本群。
- 纯医学知识问答但不涉及具体变异评级（如"ACMG 有哪些证据码"的科普）可答，但**不进入评级流程、不出定级**。
- 肿瘤体细胞变异（不是 Mendelian germline）：本群是 germline 孟德尔框架，不适用。
- 没有具体变异、只有疾病名/基因名想泛泛了解：走普通检索，不要硬跑评级。

## 4. 唯一入口与执行顺序（写死，缺步不得定级）

**一切评级从总调度开始，不要直接跳进某个证据码。**

1. 先读 `acmg-total-scheduler/SKILL.md`（唯一入口），完成：
   - **G1 范式输入闸**：先经 `ev-variant-standardization` 把任意输入规范成标准变异对象（gene + c.HGVS + variant_class + identity_status）。`blocked` → 中止评级待人工；`data_gap` → 标待核继续。
   - 查"已确认评级归档"是否命中（命中则复用，标数据时点）。
   - **遗传方式前置**：调 `arad-inheritance-judgment` 判 AD/AR/多模式/LOF，写入圈定清单（PVS1/PM3/PS2/PM6/PP1 依赖它）。
   - **G2/G3**：从知识图按变异类型（Truncating/Missense/In-frame indel/Synonymous）圈定证据码；阈值一律取 `config/thresholds.json`。
2. **中间逐码判定**：对圈定的每个证据码，读对应 `ev-*/SKILL.md` 并执行（Python 取数脚本在各 ev 目录或 `scripts/`）。逐码勾选 ✓已调用 / ✗未适用(注原因) / ⚠待核验；进入收尾前做"圈定清单 vs 实际判定清单"逐码核对，缺码不得定级。
3. **收尾**：读 `acmg-conflict-summary-output/SKILL.md`，按互斥矩阵消解（PM3-BP2、PM4-BP3、PP3-BP4 等互斥对只留更可信一方），做官方已定级优先（两级：ClinGen VCEP/cspec > 非 ClinGen 权威专家组共识），**双套定级并列输出（G5：表5 + Tavtigian 分值，不取舍、不仲裁成单一结论）**。

## 5. 子技能路由图（写完整名，防 ev-pm3 与 ev-pp3-bp4 同名混淆）

| 角色 | 目录 | 职责 |
|---|---|---|
| 总调度（唯一入口） | `acmg-total-scheduler/` | 归一化→遗传前置→按变异类型圈证据码池 |
| 遗传方式前置 | `arad-inheritance-judgment/` | AD/AR/多模式/LOF（`main.py` 查 ClinVar/PubMed 基因型） |
| 收尾互斥汇总 | `acmg-conflict-summary-output/` | 互斥消解、官方优先、双套定级（见其 `input-schema.md`） |
| 身份归一化 | `ev-variant-standardization/` | MANE/CA ID/rsID/hg19↔hg38、变异分类（`standardize_variant.py` + GeneBe/VEP/gnomAD） |
| 基因身份/假基因 | `ev-gene-identity/` | `main.py same/pseudo`，NCBI Gene ID+别名 |
| 疾病表型 | `ev-disease-info/` | 外显率/发病/表型谱（`main.py` MedGen/GeneReviews/ClinGen/PubMed） |
| gnomAD 约束 | `ev-gnomad-constraint/` | missense Z/pLI/LOEUF（`query_constraint.py`，纯标准库） |
| 患者文献 | `ev-variant-literature-patient/` | ClinVar/PubMed 患者基因型、反式/家系、可疑文献 L1/L2/L3（`main.py`，含 LLM 精筛） |
| PVS1 | `ev-pvs1/` | 功能丧失（截短），强证据，需 LOF 已知机制 |
| PS1/PM5 | `ev-ps1-pm5/` | 同一位点已知致病变异（基于 CA ID/rsID） |
| PS2/PM6 | `ev-ps2-pm6/` | 新发变异（de novo，需家系） |
| PS3/BS3 | `ev-ps3-bs3/` | 功能实验证据/反向 |
| PS4 | `ev-ps4/` | 病例对照/先证者数、OR |
| PM1 | `ev-pm1/` | 突变热点/关键功能域 |
| PM2 | `ev-pm2/` | 人群频率极低/缺失（gnomAD，含基因特异阈值） |
| PM3 | `ev-pm3/` | 隐性病反式检出 |
| PM4 | `ev-pm4/` | 蛋白长度改变（非重复区 indel/终止丢失） |
| PP1 | `ev-pp1/` | 共分离（LOD） |
| PP2 | `ev-pp2/` | 错义为主要机制基因（约束） |
| PP3/BP4 | `ev-pp3-bp4/` | 计算预测有害/良性（REVEL/SpliceAI/AlphaMissense…，多算法一致） |
| PP4 | `ev-pp4/` | 表型高度特异吻合 |
| BS1/BS2 | `ev-bs1-bs2/` | 频率高于致病阈值 / 健康成人检出 |

> 另有 VCEP 基因特异规则载体 `clingen-vcep`（131 基因映射 + narrative-units）**为独立另包，本包不含**。若用户补装到群根同级，按基因特异规则判定，但**每次必须联网核实 ClinGen cspec 最新版**，本地仅快速检阅、非最终依据；未装载则显式标注"VCEP 载体缺失，走通用调度"，不得静默。

## 6. 运行前提（执行任何 Python 取数前先确认）

- **Python 3.13**（实测 3.13.15/3.13.16）+ 依赖：`pip install -r requirements.txt`（核心 `requests>=2.28`、`pyliftover>=0.4`）。建议隔离 venv。
  - 仅用标准库、无需 pip 包的：`ev-gnomad-constraint/query_constraint.py`、`ev-pp2/query_constraint.py`（gnomAD GCS 公共桶，免认证）。
  - 需 `requests`：`ev-gene-identity`、`ev-disease-info`、`ev-variant-literature-patient`、`arad-inheritance-judgment`。
  - 需 `pyliftover`：`ev-variant-standardization/standardize_variant.py`（hg19↔hg38）。
- 用 dsh 自带的 `bash`/`pwsh` 工具在**群根目录**执行脚本；脚本间用相对路径共享 `scripts/`、`config/`，**不要把某个 ev 目录单独拷走**（整包部署）。
- 环境变量（按需）：
  - `NCBI_EMAIL`：NCBI E-utilities 联系邮箱（建议真实邮箱防限流）。
  - `GNOMAD_INSECURE=1`：仅证书错位时临时降级 SSL（默认严格校验）。
  - `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`：`ev-variant-literature-patient` 的文献 LLM 精筛通道（OpenAI 兼容，可接方舟/DeepSeek/智谱/Kimi/通义）。**未配置或调用失败时该技能硬中断（退出码 2）并给配置指引，不静默降级为关键词过滤**；例外：文献 ≥50 篇走关键词快筛分支。
  - `HGMD_QUERY_DIR` / `HGMD_SKIP=1`：HGMD 为商业库**不随包分发**，未配置走 ClinVar/文献通道并显式标注 `missing_config`/`skipped_user_opted_out`，不静默。

## 7. 输入输出契约

- **输入**：基因符号 + 变异描述（c.HGVS 首选，可带 p.HGVS / 转录本 / rsID / CA ID / 坐标），必要时遗传方式、家系信息、人群。
- **规范化对象**：`{gene, c.HGVS, p.HGVS, variant_class∈{Truncating,Missense,In-frame indel,Synonymous}, identity_status∈{annotated,data_gap,blocked}, ca_id, rs_id, 坐标}`。
- **输出**：①变异身份与归一化同义词组 ②遗传方式 ③圈定证据码清单及逐码状态（证据码+使用等级+数据+规则+查询路径 PMID/数据库）④互斥消解记录 ⑤**双套定级并列**：方案A 表5（现行报告法）+ 方案B Tavtigian 分值法，不仲裁 ⑥官方已定级优先裁决（若有，注来源/版本）⑦待核/可疑文献清单（L1/L2/L3，交人工）。
- 收尾的结构化输入字段以 `acmg-conflict-summary-output/input-schema.md` 为准。

## 8. 红线（全群适用，违反即结论不可采信）

1. **禁内知**：外部事实只从知识图/阈值表/确定性引擎/实时库取；查不到写"数据缺失/待核"，不脑补。
2. **GeneBe 仅作基础注释取数**：其 `acmg_classification/acmg_criteria/acmg_score/clinvar_*` 等评级字段**一律不得作为证据判定依据**。
3. **G4 取数留痕**：查不到必须落"查不到 + N 路尝试"，禁止"假定极低频/假定罕见"。
4. **可疑文献不静默采信**：ClinVar/HGMD 挂载文献默认可疑，逐条 PMID 交人工核验。
5. **双套并列不取舍（G5）**：不得只输出一套或擅自仲裁成单一最终分类。
6. **给证据不给最终医疗结论**：输出固定带"智能分析结果，仅供参考"；诊断/治疗/胚胎决策由有资质人员作出。

## 9. 自检（可选，群根执行）

- `python scripts/regression_gate.py`：328 对照 + 冒烟 + 39 集双尺子评测（SKIP>0 失败）。
- `python scripts/combination_eval.py`：复现双引擎自洽率（注意：是**自洽率非准确率**，对外不得称准确率）。
- `python scripts/contract_test.py` / `test_llm_gate.py` / `test_extraction_validation.py`：契约与 LLM 闸门测试。
