---
name: arad-inheritance-judgment
version: 1.0.4
description: AR/AD 遗传模式判断工具（单病变异评级子技能）。输入致病变异（基因名+cDNA/蛋白改变），查询 ClinVar/PubMed 中该变异及同基因同类型变异患者的基因型（zygosity），推断关联疾病为常染色体显性（AD）或常染色体隐性（AR）。作为前置判断工具，供 PVS1、PM3、PS2/PM6、PP1 等证据码判定前调用。需判断变异/基因是 AD 还是 AR、遗传方式判断、或证据码判定前需先明确遗传模式时使用。
---

# AR/AD 遗传模式判断

根据致病变异的现有报道信息，推断其所在基因/变异关联疾病的遗传模式（常染色体显性 AD / 常染色体隐性 AR），供遗传咨询及变异评级的 PVS1 等证据码判定作前置依据。

## 在技能群中的定位（前置子技能）

> 本技能是单病变异评级技能群的**独立子技能工具**，被多个证据码子SKILL 在判定前调用：
> - **PVS1**：确认该基因的 LOF 是否为疾病机制——AR/半显性（semidominant）下 LOF 双等位致病机制明确，杂合 LOF 是机制变异；AD 下若致病机制非 LOF（如功能获得/显性负效错义），杂合 LOF 对 AD 表型不适用 PVS1。**故 PVS1 判定前须先调用本技能确认遗传方式，不得默认 AD 或 AR。**
> - **PM3**：AR 遗传下反式另一致病变异计分的前提是确认该病为 AR。
> - **PS2/PM6（新发）**、**PP1（共分离）**：显性/隐性家系模式的判定依据。
>
> 调度层可在进入各证据码判定前，先以本技能输出该变异的遗传模式，作为后续证据码圈定与判定的前提。

## 输入

用户或调度层提供致病变异信息，格式为以下任一种：
- 基因名 + cDNA改变：如 `FGFR3 c.1138G>A`、`NM_000142.4:c.1138G>A`
- 基因名 + 蛋白改变：如 `FGFR3 p.Gly380Arg`
- 仅变异描述：如 `c.1138G>A`（需从上下文推断基因名）

从输入中提取 **gene**（基因名）和 **variant**（变异描述，保留原始格式）。

## 第0步：基因双模式确认（前置门，v1.0.2 新增）

> **目的**：确认该基因是否**同时存在 AD 和 AR 两种遗传模式的关联疾病**（"双模式基因"）。仅对双模式基因跑后续步骤 1-3；单一模式基因直接输出已知模式，不跑本流程，避免空查。

**操作（先确认，再进入后续步骤）：**

1. **查 ClinGen GenCC（首选权威）**：https://search.clinicalgenome.org/kb/genes 或通过 `ClinGen Gene Curation` 页面按基因名检索，查看该基因 **Mode of Inheritance（MOI）** 字段是否同时列出 AD 和 AR；
2. **查 OMIM**：若基因有 OMIM 条目，查看该基因关联疾病列表中各疾病的遗传模式（AD / AR），确认是否并存（OMIM 需订阅时，改走 GenCC / search 间接确认）；
3. **search_web 兜底**：搜索 `基因名 OMIM inheritance autosomal dominant recessive`，查看结果是否同时出现 AD 和 AR 描述。

**判断：**

| 确认结果 | 处理 |
|---|---|
| 该基因关联疾病中**同时存在 AD 和 AR** | 确认双模式 → 进入**步骤1/2/3** |
| 仅 AD 或仅 AR（单一模式） | **不进入后续步骤**，直接输出该已知模式 |
| 无法确认双模式（数据缺失） | 保守继续跑步骤1-3，输出时标注"双模式未经 GenCC/OMIM 确认" |

> **记录格式**：将确认结果写入输出证据表——关联疾病 / OMIM编号 / 遗传模式 / 证据来源（GenCC链接 或 search结果链接）。
>
> **铁律**：本前置门**必须先执行**；未确认双模式就进入步骤1-3，或对单一模式基因空跑 ClinVar/PubMed，均属流程违规。

## 执行流程

三个步骤按顺序执行，使用同目录 `main.py` 脚本查询数据：

### 步骤1：查ClinVar数据库

```bash
python main.py clinvar <gene> "<variant>"
```

从返回的JSON中提取每个证据的 `classification`（致病性分级）与 `traits`（关联疾病）字段，用于遗传方式与 MOI 判断；`zygosity` 不在此路径返回，由步骤2 PubMed 文献路径提供。字段含 `clinvar_id / accession / variant / protein_change / classification / traits / clinvar_url / target_match`；**命中目标变异的记录集中于 `target_evidence`（v1.0.4 新增：目标变异匹配，兼容 ClinVar 省略碱基写法如 c.35delG↔c.35del），优先用 `target_evidence` 作为目标变异的 ClinVar 收录/致病性依据**。

> ⚠ **基因型缺失时下钻 RCV 详情页（v1.0.2 补充）**：ClinVar 记录通常为**变异级别**，`zygosity` 可能缺失。若 main.py 返回或 ClinVar 详情页未标注患者基因型，须点击 **Submissions → 对应 RCV 记录链接**，进入 RCV 详情页查找患者基因型描述（关注关键词 `heterozygous` / `homozygous` / `compound heterozygous`，可能出现在 assertion criteria、observation details 或 submitter comment 中）。仍未找到则记录"未记录"，转入步骤2补充。

### 步骤2：查PubMed文献

```bash
python main.py pubmed <gene> "<variant>"
```

从返回的JSON中提取每个证据的 `zygosity` 字段和 `pubmed_url`。

> **三层字段标签检索式（v1.0.2 补充，提升对检索词模糊位点的召回）**：`main.py` 检索命中原位点文献不足时（尤其蛋白改变检索词模糊、如 `p.Ser127Pro` 与简写 `S127P` 混用时），改用下列 PubMed 字段标签检索式逐层尝试，并把每层命中结果回填为证据：
>
> - **第二层（推荐首选，同密码子扩展）**：
>   ```
>   基因名[tiab] AND ("蛋白改变"[tiab] OR "cDNA编号"[tiab] OR "codon 氨基酸位置"[tiab])
>   ```
> - **第一层（精确匹配，第二层无结果时）**：
>   ```
>   基因名[tiab] AND "cDNA编号"[tiab]
>   ```
> - **第三层（MeSH + 变异）**：
>   ```
>   "基因对应MeSH词"[mh] AND "mutation"[mh]
>   ```
>   > MeSH 词可通过 NCBI Gene 页面「See related」区域查找，或搜索 `基因名 MeSH term`。
>
> 注意：同密码子的不同变异也可作为参考证据，但须标注实际变异与目标变异不同。

**步骤1和步骤2为并列关系，需同时执行，交叉印证。**

### 步骤3：查同基因同类型其他变异（仅在步骤1、2均无证据时启动）

首先从用户输入的变异推断变异类型（missense / nonsense / frameshift / splice_site / inframe_deletion 等），然后：

```bash
python main.py same_type <gene> "<variant_type>"
```

> 注意：其他变异在蛋白/基因水平上越靠近该位点，可信度越高（同一结构域、同一外显子优先于远距离变异）。
> ⚠ **检索干扰警示**：裸基因名若为常见疾病缩写（如 ACD=肺泡毛细血管发育不良/软骨发育不全等），`same_type` 可能命中无关基因。此时须用「基因名 + 特定疾病/蛋白关键词」精化检索（如 ACD+TPP1+telomere），排除干扰后再提取基因型。

## 判断规则

汇总步骤1/2/3中所有证据的 zygosity 信息，按以下规则推断：

| 患者基因型汇总 | 推断遗传模式 |
|---|---|
| 仅有杂合（heterozygous）患者 | AD |
| 仅有纯合（homozygous）或复合杂合（compound_heterozygous）患者 | AR |
| 杂合与纯合/复合杂合患者均有 | AD |

> hemizygous（半合子）通常提示X连锁遗传，不纳入AR/AD判断。
>
> ⚠ **特殊基因注意**：部分基因关联**多种表型/遗传方式**（如 ACD 同时关联 semidominant 短端粒综合征、AD 的 DKCA6、AR 的隐性端粒病）。此时本技能的"推断遗传模式"是针对**该变异对应的疾病关联**，须结合 ClinVar/GenCC 标注的具体关联疾病与 MOI（如 ClinGen 关联的 MOI 字段）综合判断，不能只凭单一 OMIM 条目。

## 输出格式

```
## 遗传模式推断结果

**推断遗传模式：** [AD / AR / 无法推断]

**证据汇总：**

### ClinVar证据
- [ClinVar ID]: 致病性=[classification], 疾病=[traits], 链接=[url]
- ...

### PubMed文献证据
- PMID [id]: 基因型=[zygosity], 标题=[title], 链接=[url]
- ...

### 同基因同类型变异证据（如有）
- PMID [id]: 基因型=[zygosity], 变异=[variant_description], 链接=[url]
- ...

**推断依据：** [说明如何根据上表规则得出结论]
```

若无任何证据：

```
未检索到该变异及相关变异的患者报道证据，无法推断遗传模式。
```

## 供证据码调用的结构化输出

作为子技能被 PVS1/PM3 等调用时，除上述文本外，还须给出供下游判定用的结论字段：

```
遗传模式: [AD / AR / 无法推断 / 多模式(注明各关联MOI)]
LOF是否为已知致病机制: [是 / 否 / 证据不足]
关键关联疾病+MOI+等级: [疾病名, MOI, ClinGen等级]
```

## 局限性说明（每次输出必须附带）

- 推断结果受数据库和文献收录完整度影响，不排除遗漏可能
- 遗传模式的最终判定应结合家系segregation分析、基因功能、疾病数据库（如OMIM、ClinGen GenCC）等综合评估
- 本流程产出为推断，不可替代临床遗传咨询师的专业判断

## 运行方式

```bash
cd <技能目录>
python main.py clinvar <gene> "<variant>"   # 步骤1
python main.py pubmed <gene> "<variant>"    # 步骤2
python main.py same_type <gene> "<variant_type>"  # 步骤3（前两步无证据时）
```

依赖：`requests`（**第三方库，非标准库**，须先安装：`python -m pip install requests`）；`xml`、`re` 为 Python 标准库，无需安装。未安装 requests 时脚本启动即明确报错并提示安装命令（不静默崩溃）。脚本运行需网络访问 NCBI E-utilities（https://eutils.ncbi.nlm.nih.gov）。
