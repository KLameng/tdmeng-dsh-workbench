---
name: ev-variant-literature-patient
version: 1.7.0
description: 基于变异标准化Skill的输出，多路径检索携带该变异的患者文献，结构化提取基因型（杂合/纯合/复合杂合）、反式变异、表型、生化指标、家系信息，支持ACMG PM3/BS2证据评估；联动HGMD获取已知PMID基线，覆盖中英文文献。可疑文献必须逐条输出PMID+链接+原因交用户人工核验，不得静默当作已核实证据。当用户需要查找变异的患者报道、PM3证据、携带者文献、患者表型、gene+variant文献检索时使用。
required_skills:
  - coze_store_name: HGMD变异查询
    reason: 本技能需要调用HGMD变异查询获取已知PMID列表作为检索基线，未安装将缺少已知文献覆盖
---

# 变异文献检索-查患者（PM3/BS2）

基于变异标准化结果，**四级架构**多路检索携带该变异的患者文献，一步到位提取基因型、表型、生化指标、家系信息。

## 核心原则

**能提就提，提不了再降级**：默认尝试获取每篇文献的完整全文/摘要并做结构化提取；
如果某篇文献全文无法获取，则降级为摘要；摘要也无法获取的，降级为 PMID + 标题 + 一句话 TLDR，不阻塞整体输出。

**可疑文献必须上报，不得静默降级为"已核实"**：凡命中「可疑文献判定标准」（L1/L2，见第三级后）的文献，**必须逐条输出"PMID+链接+可疑原因"**交用户人工核验；**只有全文已核验（L3）的文献才能作为证据码的已核实数据计入**。降级为摘要/TLDR 的文献不满足 L3，若被证据码引用须同时标注"仅摘要级，建议全文核验"。

**API 限速与错误处理**：
- NCBI E-utilities（PubMed/LitVar2/LitSense/ClinVar elink/PMC）：3 次/秒，调用间隔 0.35s
- PubTator 3.0：独立限速 3 次/秒
- OpenAlex / Europe PMC：基础间隔 0.2s
- **Semantic Scholar**：调用间隔 1.0s（无 API Key 限流较严）
- 429 限流自动指数退避重试（最多 3 次，默认 1s/2s/4s；Semantic Scholar 为 5s/15s/45s）
- 单路径失败不阻塞其他路径，失败均记录 status
- 总超时控制：all 模式单次执行不超过 120 秒

## 输入

变异标准化 Skill 的 JSON 输出，必须包含：
- `gene`：基因现用名
- `gene_aliases`：`{current, aliases[]}` 含曾用名
- `mane_csq`：MANE Select 注释 `{transcript, hgvs_c, hgvs_p, consequences}`
- `consequences`：全转录本注释列表，每项含 `{transcript, hgvs_c, hgvs_p}`

可选输入：
- `rs`：rs 号（用于 LitVar2 / PubMed 检索）
- `clinvar_uid`：ClinVar UID（用于 ClinVar elink）
- `disease_cn`：疾病中文名（用于中文搜索链接生成 + LitSense 语义查询）

## 执行流程

### 第零级：变异标准化（前置）

由上游「变异标准化」Skill 完成，输出：
- 基因现用名 + 曾用名
- MANE Select 转录本的 hgvs_c / hgvs_p
- 全转录本注释列表
- rs 号（如有）
- ClinVar 关联（如有）

### 第一级：确定文献池

**核心路径**（最精准，优先执行）：
1. **ClinVar elink** — 通过 ClinVar UID 直接获取官方关联的 PubMed 文献；未提供 UID 时自动通过 esearch 按 rs 号或基因+cDNA 查找对应 UID
2. **HGMD 知识库** — 调用 HGMD 变异查询 Skill，获取已知致病性变异的 PMID 基线
   - **可选配置（不静默）**：HGMD 为商业数据库、不随技能群分发。取数脚本路径来自环境变量 `HGMD_QUERY_DIR`（指向含 `search.py` 的目录，如 `C:\Users\DELL\Desktop\HGMD数据专用区\hgmd-variant-query`）。
   - **未配置**：输出「HGMD 数据缺失」提示 + 前往配置指引，HGMD 块明确跳过（状态 `missing_config`）、走 ClinVar/文献检索通道、不静默；其余通道不受影响。
   - **用户确认不配置**：设 `HGMD_SKIP=1` 显式跳过（状态 `skipped_user_opted_out`），明确记录、不静默。
   - **HGMD 配置指南（可操作步骤）**：
     1. **准备三件套（须在同一目录，`HGMD_QUERY_DIR` 指向该目录）**：`search.py`（取数脚本）+ `hgmd_pro_2024.1.hg19_multianno.xlsx`（商业授权数据表，11 列含 `Gene.refGene`/`AAChange.refGene`/`hgmdpro-2024.1`）+ `.hgmd.db`（SQLite 索引，**首次查询自动生成**，需 `pip install openpyxl`）。
     2. **目录示例**：`C:\Users\<你>\Desktop\HGMD数据专用区\hgmd-variant-query`。
     3. **设置环境变量**：
        - Windows 持久（推荐）：`setx HGMD_QUERY_DIR "C:\Users\<你>\Desktop\HGMD数据专用区\hgmd-variant-query"`
        - Windows 临时（当前会话）：`set HGMD_QUERY_DIR=C:\Users\<你>\Desktop\HGMD数据专用区\hgmd-variant-query`
     4. **验证**：重跑评级，HGMD 步骤不再提示缺失（应显示「X 变异/Y 篇」）；或手动 `python search.py --gene GJB2 --format json` 应返回该基因变异。
     5. **暂无商业授权数据**：设 `HGMD_SKIP=1` 跳过 HGMD 资源块（走 ClinVar/文献检索通道，不静默）。

**补充路径**（多种格式并行搜索，去重合并）：
3. **PubTator 3.0** — 双模式检索：
   - 模式一：自由文本搜索（基因+cDNA / 基因+蛋白全写 / 基因+蛋白简写 / rs号）
   - 模式二：Entity ID 精确搜索（autocomplete 获取 `@VARIANT_{蛋白简写}_{基因名}_human`，再检索）
4. **LitVar2** — 4 种变异格式分别查询取并集：蛋白简写、蛋白全写、cDNA、rs号
   - 注意：移码变异不被 LitVar2 收录
   - 检查 gene 字段列表匹配目标基因
5. **PubMed esearch** — 多种变异格式（基因+cDNA、基因+蛋白全写、基因+蛋白简写、基因+rs）+ 基因曾用名分别搜索
6. **LitSense** — 语义搜索，用描述性句子（如 `{gene} {protein_full} causes {disease}`）匹配句子级证据
7. **OpenAlex** — 搜索论文 + 引用网络扩展（已知 PMID 反查引用列表 + OA 状态）

**扩展路径**：
8. **Semantic Scholar** — 学术搜索，补充 TLDR 和摘要
9. **Europe PMC** — 欧洲文献库，补充 PMCID 和摘要

### 第二级：获取全文

按优先级逐级尝试，确保每篇文献尽可能获取全文内容：

| 优先级 | 来源 | 说明 | 可靠性 |
|--------|------|------|--------|
| 1 | **PubTator 3.0 全文导出** | `biocjson` 格式，结构化段落 | ⭐⭐⭐⭐⭐ |
| 2 | **Europe PMC 全文 XML** | 需 PMCID，JATS XML 格式 | ⭐⭐⭐⭐ |
| 3 | **PMC efetch** | 需 PMCID，XML 全文 | ⭐⭐⭐⭐ |
| 4 | **OpenAlex OA** | 仅返回 OA 链接，需外部抓取 | ⭐⭐⭐ |
| 5 | **PubMed efetch** | 仅摘要，兜底使用 | ⭐⭐⭐⭐⭐ |

### 第三级：搜索引擎补漏

- **英文通用搜索**：Google Scholar / 通用搜索引擎补漏
- **中文文献**：搜索中文关键词（基因名 + 疾病中文名 + 变异），对结果抓取摘要；抓取失败则附搜索链接

### ⚠ 可疑文献上报（硬步骤，强制，禁止静默跳过）

> **适用**：本技能输出的每一条文献，凡命中"可疑文献判定标准"（见下），**必须逐条输出"PMID + 文献链接 + 可疑原因"**，交由用户人工核查或下载全文后回传，**不得当作已核实证据计入任何证据码**。

**可疑文献判定标准（命中任一条即判为可疑）：**

### 第一类：数据库挂载文献（ClinVar / HGMD）→ 一律可疑

**凡由 ClinVar（elink / 提交关联）或 HGMD 知识库挂载的文献，一律默认为"可疑文献"，不论自动层能否取到摘要/全文。**

> 理由：数据库"挂载"仅表示"该文献与变异相关"，**不保证变异在其标题/摘要/表格中直接可核验**。这类文献常为队列/谱系/数据库研究（变异列于 Table，标题摘要不可见，如 PMID 26540129），也可能挂载错误。故**必须逐条上报人工核验，或全文核验（L3）通过后才可计入证据**。

**处理**：强制上报，输出 PMID + PubMed链接 + DOI，标"数据库挂载，默认可疑，需人工全文核验"。即使能取到摘要，也**不豁免**（摘要可能只提及该变异、未核验基因型/表型/反式细节）。

### 第二类：其他检索路径（PubTator / LitVar2 / PubMed / LitSense / OpenAlex / Semantic Scholar / EuropePMC / 搜索引擎 / 中文）→ 按"变异本体可核验性"分级

**核心判据**：能否在自动可核验层面（标题/摘要/全文）确认**该具体变异**（本变异的 c.HGVS 或 p.HGVS）真实出现。

| 等级 | 标准 | 典型情形 | 处理 |
|---|---|---|---|
| **L1 不可核验/假阳性** | 标题/摘要/全文自动层**均无法确认该具体变异**，或明确是异源蛋白/不同基因/不同物种假阳性 | 异源蛋白假阳性（如 F7 检索命中 PMID 1898726=NADH-b5还原酶、35330881=ACAN、12533470=SecE）；检索词模糊命中同基因其他位置；LitVar2/LitSense 别名截断误匹配到其他变异类型 | **强制上报**，剔除或人工核验 |
| **L2 部分可核验** | 摘要/全文提到该基因或疾病，但**未明确列出该具体变异** | 队列研究摘要只说"报道 F7 多个变异"，未逐变异列 c./p.；Semantic Scholar 仅 TLDR 无摘要；中文文献抓取失败（仅搜索链接） | 上报，标注"需全文核验该具体变异" |
| **L3 变异本体已核验** | 标题/摘要/全文**明确列出该具体变异**（c.HGVS 或 p.HGVS 匹配本变异） | 摘要直接写 "c.379T>C (p.Ser127Pro)" | 正常计入（全文核验后更可靠） |

**其他路径特有可疑情形（并入对应等级）**：
- 异源蛋白/跨基因假阳性、别名截断误匹配 → **L1**
- 仅 TLDR/无摘要、中文抓取失败 → **L2**
- 检索词命中但未列具体变异 → **L1**（无法确认到变异本体）

**核心原则**：**"自动检索层全部为空" ≠ "全文没有"**。尤其当 HGMD/ClinVar 已挂载某 PMID 时，该文献**极可能把变异列在 Table/正文中**（标题摘要检索不到），此时必须把 PMID 作为可疑文献上报给用户人工核验——这正是"非开放获取文献的表格变异只能靠全文核验"的铁律。

**上报格式（强制，每条可疑文献必须输出）：**

```
### 可疑文献上报（需人工核验）
- PMID: [号] | 可疑等级: L1/L2 | 原因: [无法获取全文/摘要不可见]
- PubMed 链接: https://pubmed.ncbi.nlm.nih.gov/[PMID]/
- DOI 链接: [如有]
- 挂载来源: HGMD / ClinVar / 检索命中
- 处理: 请人工下载全文核验是否报道该变异，或下载后回传进行全文核验
```

### 第四级：LLM 结构化提取

对成功获取全文/摘要的文献，调用 LLM 提取：
- 基因型、反式变异、de novo
- 表型、表型一致性
- 生化指标
- 家系信息、父母基因型

### ⚠ 按用途证据码定制提取要求（强制，v1.3.0 新增）

> **不同证据码从同一篇文献中需要提取的信息不同。** 检索时须明确本检索服务于哪个证据码（传入用途证据码），并按下表提取该证据码的**关键字段**；其他字段可次要提取。**该证据码的关键字段提取不到时，必须逐字段标"未报告/未检测"，不得凭推测填充、不得略去。**

**证据码 → 文献关键提取字段映射表：**

| 用途证据码 | 文献中必须提取的关键字段 | 字段缺失时标注 |
|---|---|---|
| **PM3**（反式） | ①合子状态（纯合/复合杂合）②反式另一变异（cis/trans）③**相位验证状态**（confirmed in trans 父母验相位 / phase unknown）④是否双基因/外显不全反证 | 标"未报告/相位未知" |
| **PS4**（病例-对照） | ①先证者个数 ②病例数/对照数 ③**OR 值与置信区间 CI**（AR 必需）④患者表型一致性 | 标"未报告/未提供对照" |
| **PS2/PM6**（新发） | ①**de novo 状态**（是/否/未检测）②双亲验证情况 ③表型吻合度 ④是否生殖腺嵌合 | 标"未检测/未报告" |
| **PS3/BS3**（功能） | ①实验方法（体内/体外）②**是否针对本特异变异** ③阳性/阴性对照 ④结果（功能受损/无影响） | 标"未报告/非本变异实验" |
| **PM5/PS1**（同位点） | ①同位置已知致病变异 ②相同/不同氨基酸改变 ③已知变异分类（P/LP） | 标"未报告/未查到位点" |
| **PVS1**（下游热点） | ①截断点**下游**已报道致病变异 ②下游热点聚集情况 ③关键功能区证据 ④病例数 | 标"未报告/查不到下游" |
| **PP1**（共分离） | ①患者数 ②分离次数（患者数−1）③家系数 ④受累/非受累成员 | 标"未报告" |
| **BS2**（健康成人） | ①健康成人携带 ②合子状态（AR纯合/AD杂合/XL半合）③无表型确认 | 标"未报告" |
| **PM2/BS1**（频率） | 主要为频率数据库（gnomAD/1000G/ESP），一般不提取患者文献；仅特异性阈值出处需提取 | 标"查不到" |

**强制约束：**
1. **检索调用须声明"用途证据码"**（如 `--for pm3` / `--for ps4`），输出按该证据码的关键字段优先呈现；
2. **关键字段缺失须逐字段标注**（"未报告/未检测/相位未知"），**不得用通用字段模板或推测数据代替**；
3. **提取结果须回填到对应证据码判定**：如 PM3 计分表需要"合子+相位+计分"，PS4 需要"先证者数/OR+CI"——提取缺字段则该证据码相应数据标"待全文核验"或不计；
4. **多用途检索**：一个变异通常先跑 PM3/BS2（患者文献），其他证据码按需补充检索；每次检索都声明用途。


- 基因型、反式变异、de novo
- 表型、表型一致性
- 生化指标
- 家系信息、父母基因型

## main.py 调用方式

### 检索模式

```bash
# 全路径检索（默认）
python main.py --gene BRCA1 --variant-cdna "c.5266dupC" \
    --variant-protein-full "Arg1756Pro" --variant-protein-short "R1756P" \
    --rs "rs80357906" --clinvar-uid "12345" \
    --gene-aliases "BRCAI,FANCS" --disease-cn "乳腺癌" \
    --mode all --max 30

# 单路径检索
python main.py --gene BRCA1 --variant-cdna "c.5266dupC" \
    --variant-protein-short "R1756P" --mode pubtator

# 按用途证据码定制提取（v1.3.0 强制要求：检索须声明用途证据码）
python main.py --gene BRCA1 --variant-cdna "c.5266dupC" \
    --variant-protein-full "Arg1756Pro" --variant-protein-short "R1756P" \
    --rs "rs80357906" --clinvar-uid "12345" \
    --for pm3 --mode all --max 30
# --for 可选值：pm3 / ps4 / ps2 / pm6 / ps3 / bs3 / pm5 / ps1 / pvs1 / pp1 / bs2 / pm2 / bs1

# 可选 mode: all / clinvar / pubtator / litvar2 / litsense /
#             pubmed / openalex / semantic_scholar / europepmc
```

### 摘要模式

```bash
python main.py --mode abstract --pmids "12345,67890,34567"
```

输出：`{"abstracts": {"12345": "...", "67890": "..."}}`

### 全文模式

```bash
python main.py --mode fulltext --pmids "12345,67890"
```

输出：`{"fulltexts": {"12345": {"source": "...", "passages": [...], "pmcid": "..."}}}`

### 输出格式（检索模式）

```json
{
  "gene": "BRCA1",
  "variant": "c.5266dupC",
  "search_summary": {
    "clinvar_elink": {"count": 5, "pmids": ["12345", ...], "status": "ok"},
    "pubtator": {"count": 3, "pmids": [...], "entity_ids": [...]},
    "litvar2": {"count": 2, "pmids": [...], "rs_found": "rs80357906"},
    "litsense": {"count": 1, "pmids": [...], "sentences": [...]},
    "pubmed": {"count": 10, "pmids": [...]},
    "openalex": {"count": 4, "pmids": [...], "citation_refs": [...], "oa_info": {...}},
    "semantic_scholar": {"count": 8, "pmids": [...]},
    "europepmc": {"count": 2, "pmids": [...]}
  },
  "dedup": {
    "total_unique_pmids": 25,
    "by_source": {"ClinVar": 5, "PubTator": 3, "...": 0}
  },
  "papers": [
    {
      "pmid": "12345",
      "title": "...",
      "authors": ["Author1", "Author2"],
      "journal": "...",
      "year": "2024",
      "abstract": "...",
      "pmcid": "PMC123456",
      "doi": "...",
      "sources": ["ClinVar", "PubMed", "PubTator"],
      "oa_url": "https://..."
    }
  ],
  "elapsed_seconds": 32.5
}
```

## 结构化提取字段

| 字段 | 内容 | 缺失时 |
|------|------|--------|
| 基因型 | 杂合/纯合/复合杂合 | 标"未报告" |
| 反式变异 | 复合杂合的第二变异 + cis/trans 状态 | 标"未报告" |
| de novo | 是/否/未检测 | 标"未检测" |
| 表型 | 诊断、症状、发病年龄、严重度 | 标"未报告" |
| 表型一致性 | 与已知疾病谱一致 / 可能表型扩展 | 标"无法判断" |
| 生化指标 | 指标名+值+参考范围 | 标"未报告" |
| 家系 | 受累人数、共分离、近亲婚配 | 标"未报告" |
| 父母基因型 | 父母各自的携带状态 | 标"未报告" |

### 提取校验层（v1.6.0，强制：写入 `structured_extraction` 时同步下发 `validation` 状态）

LLM 提取的 8 字段写入 `structured_extraction` 前，统一过三层自动化校验，**只标注/降置信度、绝不替 LLM 编答案、异常显式记录不静默**：

| 校验 | 内容 | 命中 → 状态 |
|---|---|---|
| C1 枚举合法性 | genotype 限 杂合/纯合/复合杂合、de_novo 限 是/否/未检测、phenotype_consistency 白名单 | 越界 → invalid |
| C2 内部一致性 | 纯合+反式第二变异、复合杂合无反式、de_novo=是 但双亲未报告 | conflict |
| C3 权威基线 | trans_variant 与 ClinVar 公开 API 交叉核对（自动、无需 Key）；HGMD 商业库接口默认关闭 | 查不到 → unverified |

输出随 `structured_extraction` 一并下发 `validation`：`status`（clean / has_issue / invalid）+ `confidence`（high / medium / low）+ `issues`。

- **status=invalid（含 conflict）的字段不得作为证据计入**，且不得静默跳过（记录在 issues 交人工核验）；
- **status=has_issue（仅 unverified/check_failed）的字段仍可用，但 confidence=medium**，使用时须带出该状态；
- **status=clean 的字段 confidence=high**。

## 输出格式（路线A：病例报告部分）

```
## 变异患者文献检索结果

**变异**: [基因] [c.] ([p.])
**HGMD 收录**: 是/否（已知 N 篇）
**检索来源**: ClinVar / PubTator / LitVar2 / PubMed / ...

### 患者文献（共 N 篇，完整提取 M 篇，降级 K 篇）

#### 1. PMID:XXXXX — [标题]（完整提取）
- **年份**: YYYY | **作者**: XX et al. | **期刊**: XXX | **来源**: PubMed, PubTator
- **基因型**: 纯合
- **de novo**: 否
- **表型**: XXX病，主要症状...，发病年龄X岁
- **生化**: ALT=120 U/L（参考 7-56）
- **家系**: 先证者+1名受累同胞，父母均为携带者，共分离确认
- **父母基因型**: 父杂合，母杂合

#### 2. PMID:XXXXX — [标题]（降级）
- **年份**: YYYY | **作者**: XX et al. | **期刊**: XXX | **来源**: SemanticScholar
- TLDR: 报道了该变异在1例患者中的发现，摘要未提供详细表型信息

### 检索统计
- 检索路径: 8 路 | 总命中: M 篇 | 去重后: K 篇
- HGMD 已知: X 篇 | 新发现: Y 篇
- 全文获取: A 篇 | 仅摘要: B 篇 | 降级: C 篇

---
*智能分析结果，仅供参考*
```

## 证据饱和即停规则

**适用范围**：仅在 ACMG 证据评级场景下触发（如 PM3/PS3/BS3/PM1 等需要积累证据计分的任务）。
**不触发场景**：查遗传方式、查表型谱、查发病率等非评级任务时，尽量收全文献，不触发饱和停止。

评级场景下的阈值：

| 证据码 | 饱和阈值 | 说明 |
|--------|----------|------|
| **PM3（反式致病证据）** | 累计 4 个 in-trans 确认（=PM3_VeryStrong） | 详细展示 5-8 篇即可，更多列入 PMID 列表 |
| **PS3/BS3（功能实验）** | 2-3 项独立功能实验 + 充分对照（≥8）+ 结果一致 | 达到 Strong 级即可停止 |
| **PM1（热点区域）** | 确认为热点区域 + 无良性变异（二元判定） | 预计 2-3 篇即可确认 |

饱和后的处理：
- 已提取的文献正常展示
- 其余 PMID 汇总在列表末尾，不逐一展开
- 全部 PMID 列表最多展示 10 个

## 特殊情况

- **无 p. 的变异**（同义/非编码/内含子）：仅用 c. 检索，跳过蛋白相关检索式
- **移码变异**：LitVar2 不收录，不尝试该路径；代码中自动检测蛋白描述中包含 `fs` / `Profs` / `fsTer` 的变异并跳过 LitVar2 路径，避免 autocomplete 模糊匹配到同位置的其他变异类型（如无义/错义）导致文献误匹配
- **ClinVar UID 自动查找**：未提供 `--clinvar-uid` 时，自动通过 ClinVar esearch 按 rs 号或基因+cDNA 描述查找对应的 ClinVar UID，查找到后自动用于 elink 检索，结果会记录在 `search_summary.clinvar_elink.auto_looked_up_uid` 中
- **Semantic Scholar 限流**：Semantic Scholar 无 API Key 时限流较严（约 100 请求/5 分钟），调用间隔设为 1.0 秒，429 重试退避时间为 5s/15s/45s（3 倍指数退避），连续触发限流会跳过剩余查询
- **多转录本同 hgvs**：去重，不重复搜索
- **复合杂合**：重点确认反式状态，未确认标"相式未知(cis/trans unknown)"
- **近亲婚配**：标注并提示增加纯合致病可能性
- **表型扩展**：报道表型与已知不一致时标"可能表型扩展"
- **中文抓取失败**：附搜索链接，标"摘要获取失败"
- **单路径 API 故障**：自动跳过，不阻塞整体检索，在输出 status 中标记
- **429 限流**：指数退避自动重试 3 次，仍失败则跳过并记录
