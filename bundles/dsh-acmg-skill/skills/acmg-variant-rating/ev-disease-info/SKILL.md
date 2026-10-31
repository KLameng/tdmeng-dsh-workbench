---
name: ev-disease-info
version: 1.0.0
description: 疾病表型、外显率、发病率、表现度/表型谱、治疗/预后/发病年龄的结构化检索工具。给定口语化疾病名/表型/基因变异，通过名称扩展、MedGen标准化、ClinVar变异对齐、NCBI Books(GeneReviews)、ClinGen基因-疾病有效性、PubMed文献检索四步流程获取疾病信息。当用户查询疾病症状、外显率、发病率、患病率、发病年龄、治疗预后、表现度、表型谱、基因外显率、变异外显率、疾病信息时使用。
---

# 疾病信息查询_jb

给定口语化的疾病名称、表型描述或基因变异，严格按4步流程获取疾病表型、外显率、发病率、治疗/预后/发病年龄等信息。

**规则：**
- 文献仅查PubMed，不使用其他搜索引擎或第三方网站
- 每类PubMed检索取前5篇
- 治疗/预后仅输出有效治疗方案+预后良好内容；无有效治疗或预后不良则直接省略
- 发病年龄有则输出，不受治疗/预后省略规则限制

## 查询类型

| 类型 | 说明 |
|---|---|
| 通用查询（疾病/表型） | 输入疾病名或表型，不限定特定类别 → 全量输出：表型特征+外显率+发病率+表现度/表型谱+治疗/预后/发病年龄。输入为表型时，先经Step 2判定特异性（ClinGen SVI框架）：①Pathognomonic（1个关联疾病）→ 映射到该疾病，输出全部属性；②高特异性（2-5个）或低/极低特异性（6+）→ 列出所有关联疾病，各自独立输出属性，低/极低特异性标注"非特异性表型" |
| 外显率 | 携带致病变异者表现出疾病/表型的比例（基因级+变异级双重查询）。基因级：该基因致病变异→疾病的整体外显率；变异级：一个基因可致多种疾病，特定变异对应特定疾病，查"该变异→该特定疾病"的外显率（通过ClinVar注释确定变异对应的疾病）。外显率绑定特定疾病/表型输出，并附带表现度 |
| 表现度/表型谱 | 同一基因型下不同个体的表型严重程度差异（表现度）和表现形式范围（表型谱），两者紧密关联常一起讨论。输出时绑定对应疾病/表型 |
| 发病率 | 疾病在人群中的发生频率（发病率/患病率），绑定特定疾病输出 |
| 治疗/预后/发病年龄 | 治疗/预后仅输出有效治疗+预后良好内容；无有效治疗或预后不良则省略。发病年龄有则输出 |

## 执行顺序

Step 1（名称扩展→中英文映射→双轨查询）→ Step 2（标准化）→ Step 3（Books→ClinGen串行）+ Step 4（PubMed文献检索）

Step 3与Step 4可并行：Step 3用标准化结果，Step 4用Step 1+2全部结果。

输入类型处理：
- **疾病名** → 直接进入Step 1
- **表型** → Step 1双轨查询 → Step 2判定特异性 → 映射到疾病 → 以该疾病名进入Step 1-4
- **基因+变异** → 变异对齐（见附录）→ ClinVar确定对应疾病 → 再以该疾病名进入Step 1-4。ClinVar查不到→ClinGen查基因-疾病有效性→Books按基因名搜索选相关疾病→进入Step 1-4

---

### 🔒 缓存先行（v1.1.0，慢优化——只复用已查结果，**不缩减穷尽检索**）

查询外部 API 前，先查 `scripts/acmg_cache.py` 跨变异缓存（命名空间 `gene_disease`），命中直接引用并标注"缓存命中(存储时间)"；未命中才发外部请求，返回后回写缓存。
用法：
```
python scripts/acmg_cache.py get --ns gene_disease --key "<基因或疾病名>"
python scripts/acmg_cache.py set --ns gene_disease --key "<基因或疾病名>" --value '<JSON结果>'
```
**边界铁律**：缓存**只消除"同一基因/疾病信息跨变异重复查询"**（评 10 个变异不再查 10 遍 Books/ClinGen/PubMed），**不得据此跳过或缩减 Step 1-4 的穷尽检索**——穷尽检索（Books→ClinGen 串行 + PubMed 全源、变异对齐、可疑文献 L1/L2/L3 核验）为防漏检硬步骤，强制保留、一律执行。缓存命中仅代表"该基因/疾病信息已查过"，不代表"该变异的证据判定已完成"。

## Step 1 — 名称扩展→中英文映射→双轨查询

核心原则：先扩展所有名称，再中英文映射，最后双轨全跑。

### 名称扩展

| 输入类型 | 扩展内容 |
|---|---|
| 疾病 | 曾用名、拓展名 |
| 表型 | 同义词、近义词 |

### 中英文映射

将扩展后的所有名称映射为中英文对照列表。中文名为用户输入或已知中文名，英文名为标准医学术语。

### 双轨查询

用中文名称和英文名称分别进入Step 2-4，结果合并去重。

用以下命令辅助搜索：
```bash
python main.py medgen "<中文或英文疾病/表型名>"
```

---

## Step 2 — 标准化

### 表型特异性判定（基于ClinGen SVI框架）

通过MedGen查询表型的关联疾病列表。先用 `python main.py medgen "<表型名>"` 获取MedGen UID，再用fetch_web获取MedGen页面解析RelatedDisorders：
```
https://www.ncbi.nlm.nih.gov/medgen/{UID}
```

按关联疾病数量判定特异性：

| 特异性级别 | 关联疾病数 | 处理方式 |
|---|---|---|
| Pathognomonic | 1个 | 直接映射到该疾病 |
| 高特异性 | 2-5个 | 列出所有，各自进入Step 1-4 |
| 低/极低特异性 | 6+ | 列出所有，各自进入Step 1-4，标注"非特异性表型" |

若用户提供多个表型，考虑组合特异性（如视网膜色素变性+听力损失→Usher综合征）。

依据：ClinGen SVI四级别框架（PMC11061282）+ ACGS PP4三档标准 + Haijes et al. 表型特异性信息量理论（PMID:31804708）。特异性本质是表型有多罕见。

### 标准化规则

- **疾病输入** → MedGen标准疾病名（中英文）
- **表型输入** → 特异性判定 → 映射到疾病 → 以该疾病名进入Step 1-4
- **基因+变异输入** → ClinVar确定对应疾病：
```bash
python main.py clinvar "<变异任意形式>"
```

---

## Step 3 — NCBI Books → ClinGen（串行）

⚠️ Books先执行获取关联基因名 → ClinGen用基因名查询。Books未返回基因名则ClinGen跳过。

### NCBI Books (GeneReviews)

```bash
python main.py books "<标准疾病名>"
```

检索标准疾病名，输出概括性原文（疾病概述+表型摘要）+关联基因名。

用fetch_web获取Books返回的章节URL，提取疾病概述、表型摘要、penetrance章节、治疗/预后/发病年龄等内容。

### ClinGen

```bash
python main.py clingen "<基因名>"
```

用Books获取的基因名查询基因-疾病有效性+剂量敏感性。无收录→跳过。若API不可用，用fetch_web获取：
```
https://search.clinicalgenome.org/kb/gene-dosage?page=1&size=25&search=<基因名>
```

### 输出规则

- 治疗/预后：仅输出有效治疗+预后良好内容，无则省略
- 发病年龄：有则输出，不受省略规则限制

---

## Step 4 — PubMed文献检索

仅查PubMed，每类检索取前5篇。

### 检索词模板

| 类型 | PubMed附加检索词 |
|---|---|
| 通用查询 | （无附加检索词） |
| 外显率 | AND (penetrance OR "incomplete penetrance" OR "asymptomatic carriers") |
| 表现度/表型谱 | AND (expressivity OR "phenotypic spectrum") |
| 发病率 | AND (prevalence OR incidence) |
| 治疗/预后/发病年龄 | AND (treatment OR prognosis OR therapy OR "age of onset") |

执行英文检索：
```bash
python main.py pubmed "<标准疾病英文名> <别名> <查询类型词>" --count 5
```

中文文献检索（在PubMed内用语言过滤器，不使用外部搜索引擎）：
```bash
python main.py pubmed "<标准疾病英文名> <别名> <查询类型词> AND Chinese[Language]" --count 5
```

⚠️ PubMed不对中文字符建索引，中文检索词被静默丢弃。中文检索必须使用英文检索词+Chinese[Language]语言过滤器。

从返回结果中提取每篇文献的标题、作者、期刊、年份和PMID，需要摘要时用fetch_web获取 `https://pubmed.ncbi.nlm.nih.gov/{PMID}/`。

---

## 外显率查询专项

基因级+变异级双重查询，两者都有则都展示。

### 变异对齐（必做）

见附录《变异标准化流程》，外显率查询前必须完成变异对齐，获取标准化HGVS和蛋白变化。

### Step 3 补充

| 查询对象 | 来源 | 说明 |
|---|---|---|
| 基因级外显率 | NCBI Books (GeneReviews) | 标准疾病名→penetrance章节 |
| 基因级外显率 | ClinGen | 基因名→基因-疾病有效性+剂量敏感性 |
| 变异级外显率 | ClinVar | 标准化HGVS→确定变异对应疾病+外显率注释 |

⚠️ 基因名已知，三个来源输入不同，可并行查询。Books/ClinGen通常只有基因级数据，变异级主要依赖文献。

### Step 4 补充

在通用PubMed检索基础上增加基因级和变异级专项检索，各取前5篇：

- **基因级**：
```bash
python main.py pubmed "({基因名} OR {标准疾病名}) AND (penetrance OR \"incomplete penetrance\" OR \"asymptomatic carriers\")" --count 5
```

- **变异级**：
```bash
python main.py pubmed "({标准化HGVS} OR {蛋白变化}) AND (penetrance OR \"incomplete penetrance\" OR \"asymptomatic carriers\")" --count 5
```

中英文各跑一次（中文加 `AND Chinese[Language]`）。

⚠️ 变异级penetrance检索可能返回0——特定变异+penetrance的文献极少，属预期行为。

---

## 检索优先级

1. 标准化前置：名称扩展→中英文映射→标准化（表型输入含特异性判定）
2. 数据库查询：NCBI Books (GeneReviews) > ClinGen
3. 外显率专项：基因级（Books+ClinGen+文献）+变异级（ClinVar+文献）；变异查询前必做变异对齐
4. 变异→疾病映射fallback：ClinVar → ClinGen → Books

---

## 附录：变异标准化流程（候补通道，非主入口）

> **🔒 定位声明（必读）**：本附录的变异标准化流程**不是**变异群变异身份归一化的主入口。变异身份归一化的**唯一主入口是 `ev-variant-standardization`（GeneBe 主流程）**（见总调度层前置硬步骤）。
> 本附录（ClinVar esummary + AutoPVS1 + Mutalyzer）仅为**候补**：**仅当 `ev-variant-standardization` 主流程无法返回结果**（GeneBe 网络不可达/该变异无收录/输入格式不支持/请求超时等）时，才允许降级到本附录完成变异对齐；主流程可用时**禁止**调用本附录做变异身份归一化。
> 若因外显率/疾病查询需要变异对齐（Step 3/4 的变异级查询），同样**先走 `ev-variant-standardization`**；其失败后再回落到本附录。

给定变异的任意一种形式（rs号/基因名+cDNA/基因名+蛋白变化/转录本号+cDNA），将所有命名形式对齐。

对齐目标：基因名、转录本号、cDNA变化、蛋白变化（全写/简写）、rs号、基因组坐标（hg38/hg37）、pHGVS

### ① ClinVar esummary（获取前6种）

```bash
python main.py clinvar "<任意已知形式>"
```

自动提取以下字段：

| 字段 | 提取来源 |
|---|---|
| 基因名 | gene_sort |
| 转录本号 | title中正则 NM_\d+\.\d+ |
| cDNA变化 | variation_set[0].cdna_change 或 title中正则 c\.\S+ |
| 蛋白全写 | title中正则 p\.\w+（三字母） |
| 蛋白简写 | variation_set[0].aliases中查找 p.XnnnY |
| rs号 | variation_set[0].variation_xrefs中db_source=dbSNP的db_id，加rs前缀 |

### ② AutoPVS1（补充第7-8种 + gnomAD直链）

用fetch_web获取：
```
https://autopvs1.bgi.com/search?q={cHGVS或基因名}&genome_version=hg38
```

提取：
- 基因组坐标（hg38/hg37）：CHR-POS-REF-ALT，标注版本
- pHGVS：NP_xxxx.x:p.XxxXxxXxx
- gnomAD直链：hg38用r4 / hg37用r2_1

AutoPVS1由华大基因（BGI）开发，基于ClinGen SVI推荐实现PVS1自动判读，同时提供变异命名格式互转。返回HTML页面（非JSON），需解析提取。

### ③ Mutalyzer（HGVS语法校验，必做）

```bash
python main.py mutalyzer "<HGVS描述>"
```

返回normalized_description（标准化HGVS）和corrected_description（修正后HGVS）。不一致时以Mutalyzer为准（LUMC官方实现，无需认证、无限流）。

### 注意事项

- **rs号校验**：用户提供rs号时与ClinVar返回值比对，不一致在报告中标注
- **蛋白简写缺失**：aliases中无标准格式时，用三字母→单字母转换表手动转
- **转录本版本**：以title中版本为准，aliases中可能有旧版本
- **多UID场景**：rs号可能映射多个ClinVar记录，用蛋白名或cDNA二次确认
- **后备**：ClinVar无收录时用Ensembl VEP（rest.ensembl.org/vep/human/id/{rs号}），返回ENST非NM
