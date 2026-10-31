---
name: ev-variant-standardization
version: 1.1.0
description: 基因变异标准化查询工具（变异身份归一化唯一主入口）。输入任意形式变异标识（rs号、基因名+cDNA/蛋白变化、转录本号+cDNA、基因组坐标），经 GeneBe API 输出标准化信息：基因现用名/曾用名对齐、各转录本核苷酸与氨基酸变化、MANE Select 标注、rs号、hg38/hg19 坐标、pHGVS。变异标准化、注释、转录本查询、HGVS 转换、基因名查询时使用。铁律：GeneBe 仅限查基础注释，其 acmg_classification/clinvar_classification 等评级判断字段一律不输出、不引用。
---

# 变异标准化

基因变异的标准化查询与全转录本注释工具。将任意形式的变异输入转换为标准化的完整输出。

> **🔒 唯一主入口声明（必读）**：本技能为变异群**变异身份归一化的唯一主入口**（总调度层前置硬步骤）。评级任何变异进行身份归一化时，**一律优先走本技能（GeneBe 主流程）**。`ev-disease-info` 附录的变异标准化流程（ClinVar esummary + AutoPVS1 + Mutalyzer）仅为**候补**：仅当本技能主流程（GeneBe API）无法返回结果（网络不可达/无收录/格式不支持/超时）时，才可降级启用该候补；主流程可用时**禁止**改用候补通道，避免两套流程口径漂移。归一化只做身份匹配，不改变任何证据码标准。

> **⚠️ GeneBe 使用边界铁律（必读）**：本技能使用 GeneBe **仅限查询基础注释信息**——转录本、核苷酸改变(c.HGVS)、氨基酸改变(p.HGVS)、外显子信息、hg19/hg38 坐标、软件预测分值（REVEL/AlphaMissense/BayesDel/SpliceAI 等）。**GeneBe 返回的任何评级判断字段（`acmg_classification` / `acmg_criteria` / `acmg_score` / `clinvar_classification` / `clinvar_submissions_summary` 等）对变异证据的判断均不可用**：本技能一律不提取、不输出、不引用这些评级字段作为任何证据码的判定依据。变异证据是否成立、用哪个等级，须由各证据码子SKILL 按各自流程判定。

> **单文件说明**：本 Skill 只有一个 SKILL.md。完整可执行逻辑以 Python 脚本形式内嵌在文末「内嵌实现脚本」代码块中，运行方式与独立脚本一致（见「运行方式」）。前端说明、函数接口与内嵌脚本一一对应。

> **⚠️ 示例声明（必读）**：本文档中出现的基因名、变异标识（如 `BRCA1`、`rs80357906`、`NM_007294.4`）、核苷酸/蛋白变化（如 `c.5266dup`、`p.Arg403Gln`）、基因组坐标（如 `chr17:43091022`）及所有输出样例，**均为格式示例，仅用于说明输入输出写法，不代表真实数据，也不代表该变异真实存在或真实查询结果**。
> - 实际执行时，输入一律采用**用户本次提供的真实变异标识**，不预设、不套用、不猜测示例中的任何基因或变异；
> - 输出一律以 **GeneBe / HGNC API 的真实返回结果**为准，不做任何填充或改写；
> - **严禁**在查询结果中回显、引用、拼凑或模拟本文档示例中的任何内容（包括 `BRCA1 c.5266dup`、`rs80357906`、`chr17:43091022`、`NM_007294.4` 等及其对应输出）。

## 辅助支撑要素（ClinGen CA ID 归一化，可选，仅供跨库匹配，不改变评级标准）

以下内容**仅作为变异身份的跨数据库归一化辅助**（帮助同一变异在不同数据库/转录本/坐标间对齐），**不改变任何证据码的使用标准、阈值、等级或互斥规则**。

- **ClinGen Allele Registry CA ID（可选）**：可将编码（NM_*）、基因组（NC_*）或蛋白（NP_*）HGVS 变异解析为 ClinGen Allele Registry 的规范等位基因 ID（CA ID），从而在一个 ID 下关联 ClinVar、dbSNP、COSMIC、gnomAD 等多个数据库的交叉引用，避免同一物理变异因转录本/坐标差异被误判为不同变异（尤其辅助 PS1/PM5 同氨基酸位点识别、反式对匹配、频率核对）。
- **入口**：ClinGen Allele Registry https://reg.clinicalgenome.org/ （CA ID 解析）。
- **坐标注意（仅辅助，须按各库口径换算）**：Allele Registry 的 `genomic_alleles[].start/end` 为 0-based 半开区间，非 HGVS g./VCF/gnomAD 的 1-based 位置；需 +1 对齐，且每行 `coordinate_system` 字段会明确说明坐标系。
- **约束**：CA ID 归一化**不提供评级**，仅作身份匹配辅助；任何证据码的判定数据仍须来自对应子SKILL 规定的真实查询通道，评级字段不可用（见总调度层【证据来源铁律】）。

## 何时触发

用户提到以下意图时使用：
- 变异标准化 / 变异注释 / HGVS 转换
- 查询某个变异的转录本信息
- 查基因名 / 基因曾用名
- 输入 rs号、cDNA、蛋白变化进行标准化

## 输入格式

支持以下任意格式（用户可能用中文或英文表述，灵活解析）。**下方均为格式举例（仅说明写法，非真实数据）**，实际查询时以用户给出的真实变异为准：
- **rs号**：如 `rs123456`（举例）
- **基因名 + cDNA**：如 `BRCA1 c.5266dup` 或 `BRCA1:c.5266dupC`（举例）
- **基因名 + 蛋白变化**：如 `MYH7 p.Arg403Gln`（举例；仅限简单蛋白变化：错义、无义等；复杂变化如移码不支持）
- **转录本号 + cDNA**：如 `NM_007294.4:c.5266dup`（举例）
- **基因组坐标 (hg38)**：如 `chr17:43091022 C>T` 或 `17-43091022-C-T`（举例，VCF格式）
- **基因组坐标 (hg19)**：如 `chr17:41243039:C:T&genome=hg19` 或带 `hg19` 关键词的输入（举例，自动转换为 hg38）

**输入预处理（内嵌脚本已内置）**：
- 全角标点自动转半角（`：`→`:`、`，`→`,`、`＞`→`>`）
- 自动补 `c.` 前缀：基因名 + 空格 + 数字开头（但无 `c./p./m./g./r.` 前缀）时，如 `SLC25A13 852_855del` → `SLC25A13 c.852_855del`（举例）
- 检测不完整格式并提前报错（如 `TP53 c.248`、`GENE 248` 缺少变化类型），避免 API 超时 30s（举例）
- 线粒体基因（`MT-`）若误用 `c.` 前缀，提示改用 `m.` 前缀（如 `m.8993T>G`，举例）或基因组坐标

**注意**：GeneBe convert API 对蛋白变化格式的支持有限，仅支持简单的错义/无义变异（如 `p.Arg403Gln`，举例），不支持复杂变化（如移码 `p.Gln1756ProfsTer74`，举例）。对于复杂蛋白变化，建议先查询对应 cDNA 格式。

## 变异身份归一化硬闸（强制，v1.1.0 起）

> **🔒 注释硬闸（必读，总调度层前置）**：cDNA 进入本技能后，**必须在线注释确认以下四项身份要素**，缺一不可，全部须来自真实 API 返回数据：
>
> 1. **蛋白改变 p.HGVS**：对蛋白改变类变异（错义 / 无义 / 移码 / 框内插入缺失）必须从注释结果取得 p.HGVS；剪接类与同义类变异"无蛋白改变（p. 为空或 =）"本身即确认结果，不算缺失；
> 2. **变异类型**：必须判明属于错义 / 无义 / 同义 / 移码 / 框内插入缺失 / 剪接 / 非编码 中的一类，不能笼统写"变异"或留空；
> 3. **框内框外**：对插入缺失类变异必须判明移码（frameshift）还是框内（inframe）；错义 / 无义 / 同义 / 剪接天然确定，标记为不适用；
> 4. **基因内位置**：外显子 / 内含子位置（如"外显子 20/24"、"内含子 1/23"）须从注释结果取得；缺失时标"待核"，**不单独构成阻塞**（位置字段缺失不致命，变异类型与蛋白改变已确认即可进入圈定）。
>
> **四项全部确认** → `identity_status = annotated`，可进入证据码圈定。
>
> **构成硬阻塞（评级暂停）的情形**：① 变异类型无法从注释后果判定（既非错义/无义/同义/移码/框内/剪接/非编码中任何一类，或后果为空）；② 蛋白改变类变异（错义/无义/移码/框内/其他蛋白改变）未从注释结果取得 p.HGVS。命中任一 → 输出 `identity_status = blocked`，附"变异身份未确认，评级中止，待人工复核"提示，并给出可恢复的回退方式（人工确认真实变异后，以标准格式重新传入即可继续）。**禁止**以"按密码子推断""假设为错义/无义"等推断方式填补身份要素后继续评级。
>
> **执行问题 vs 数据缺口（必须区分，防止误伤）**：
> - **执行问题**（网络不可达 / 格式不支持 / 超时 / 未取到但该转录本有数据）→ 阻塞并**强制补查 / 重试**，不跳过；
> - **数据缺口**（该转录本在注释源中真实无数据，如非编码区无注释）→ 标 `data_gap`（身份部分待核），走既有"缺数据 ≠ 反对"规则，**不阻塞为卡死**，也不视为"该区域无此特征"的证据。
>
> 本硬闸只做身份匹配与确认，不改变任何证据码标准、阈值或等级。

## 执行流程

> **🔒 缓存先行（v1.1.0，慢优化）**：调用 GeneBe convert/variant API 前，先查 `scripts/acmg_cache.py` 跨变异缓存（命名空间 `genebe`，键=归一化后的变异标识），命中直接引用并标注"缓存命中(存储时间)"；未命中才发 GeneBe 请求，返回后回写缓存。**缓存只复用同一变异的已查标准化结果，不得据此跳过本流程任何步骤**（身份归一化/坐标换算/转录本对齐照常执行）；变异坐标或基因别名变化时以缓存命中时间为准、必要时 `--refresh` 语义重查。用法：
> ```
> python scripts/acmg_cache.py get --ns genebe --key "<变异标识>"
> python scripts/acmg_cache.py set --ns genebe --key "<变异标识>" --value '<JSON结果>'
> ```

1. **解析输入**：识别变异格式，检测是否指定 hg19 基因组版本
2. **获取基因组坐标**：调用 GeneBe `convert` API，将各种格式转为 hg38 坐标；若输入为 hg19 原始坐标，通过 pyliftover 手动转换；若为 hg19 rs号/HGVS，直接传 `genome=hg38` 给 API（基因组无关）
3. **查询变异注释**：调用 GeneBe `variant` API（useRefseq=true, useEnsembl=false），获取全转录本注释 + 顶层元信息（rs号、MANE Select 等）
4. **查询基因曾用名**：调用 HGNC REST API，获取基因现用名和别名列表
5. **hg19 坐标转换**：使用 pyliftover 将 hg38 坐标转为 hg19 坐标输出
6. **格式化输出**：按「基因信息」+「变异信息」两大块呈现结果

**hg19 处理策略细节**：
- GeneBe convert API 不支持 hg19 输入（会返回 "Only hg38 output is supported"）
- 对 hg19 原始坐标输入：手动解析后用 pyliftover 转为 hg38
- 对 hg19 rs号/HGVS 输入：基因组无关，直接传 `genome=hg38` 给 GeneBe
- hg19 检测用两步正则：`[&?]genome=hg19` 参数格式 + 独立 `hg19` 关键词，避免误匹配基因名

## 输出格式

输出分为「基因信息」和「变异信息」两大块。**下方输出模板仅为示意（举例，非真实查询结果），其中基因名、坐标、转录本、蛋白变化均为示例占位**；实际输出必须以本次查询的真实 API 返回数据为准，不得套用或回显此处的示例内容：

```
======================================================================
📋 变异标准化结果
======================================================================

【基因信息】
  现用名: BRCA1
  曾用名: FANCS, FANCD1, IRIS

【变异信息】
  基因组坐标:
    hg38: chr17:43091022 C>T  (VCF: 17-43091022-C-T)
    hg19: chr17:41243039 C>T  (VCF: 17-41243039-C-T)
  rs号: rs80357906

  转录本注释 (共 368 个 NM_ 转录本)
  --------------------------------------------------------------------
  ### 基因: BRCA1 (368 个 NM_ 转录本)

    ▶ 主转录本 (MANE Select): ⭐
      转录本: NM_007294.4  (外显子 20/24)
      cDNA: c.5266dup
      蛋白变化(全写): p.Gln1756ProfsTer74
      蛋白变化(简写): p.Q1756Pfs*74
      效应: frameshift_variant

    ▶ frameshift_variant (12 个)
      转录本                位置       cDNA                   蛋白(简写)
      ------------------------------------------------------------------------
      NM_007299.4           外显子 20/24 c.5266dup              p.Q1756Pfs*74
      NM_007300.4           外显子 20/24 c.5266dup              p.Q1756Pfs*74
      ...
      ... 还有 7 个已省略

======================================================================
智能分析结果，仅供参考
======================================================================
```

**展示规则**：
- 转录本过多时按效应类型分组，每组最多显示 5 个，超出部分折叠（`... 还有 N 个已省略`）
- 按 gene_symbol 分组输出，每个基因单独一段
- 内含子总数 = 外显子数 - 1（如 24 个外显子 → 23 个内含子）
- 仅输出 NM_ 转录本（通过 `useRefseq=true, useEnsembl=false` 过滤，不展示 ENST）
- 蛋白变化同时输出三字母全写和单字母简写格式

## 函数接口

### 核心函数

| 函数 | 说明 |
|------|------|
| `standardize_variant(variant_input)` | **主入口**。接收变异字符串，执行完整标准化流程并输出结果；同时返回结构化 dict（gene、gene_aliases、coord、rs_id、mane_csq、consequences） |
| `convert_variant(variant_str)` | 将各种格式（rs号/HGVS/VCF/坐标）转为基因组坐标。自动检测 hg19 输入 |
| `get_variant_data(chr, pos, ref, alt)` | 获取变异完整注释数据（consequences + dbsnp + mane_select） |
| `get_gene_aliases(gene_symbol)` | 通过 HGNC API 获取基因现用名和曾用名 |

### 辅助函数

| 函数 | 说明 |
|------|------|
| `_parse_raw_coords(query_id)` | 解析原始基因组坐标字符串（支持 chr:start:ref:alt、chr-start-ref-alt 等格式，分隔符支持 `:` `>` `-` 任意组合） |
| `protein_3to1(hgvs_p_full)` | 三字母氨基酸 → 单字母氨基酸转换（如 Gln→Q, Ter→*；内置 24 组 AA3_TO_AA1 映射，含 Asx→B、Glx→Z、Xaa→X、Xle→J、Sec→U、Pyl→O） |
| `exon_label(csq)` | 根据 consequences 数据生成位置标签（外显子 X/Y 或内含子 X/Y；内含子总数 = 外显子数 - 1） |
| `_display_width(s)` / `_pad_right(s, width)` | 中文按宽度 2 计算的表格对齐辅助（用于中文/英文混排的列对齐） |
| `curl_get(url, params)` | 通用 HTTP GET 请求（用 curl 子进程避免 Python SSL 证书问题，超时 30s） |

## API 端点

| API | 基础 URL | 用途 |
|-----|----------|------|
| GeneBe convert | `https://api.genebe.net/cloud/api-public/v1/convert` | 变异格式 → 基因组坐标 |
| GeneBe variant | `https://api.genebe.net/cloud/api-public/v1/variant` | 全转录本变异注释 |
| HGNC | `https://rest.genenames.org/fetch/symbol/{symbol}` | 基因现用名 + 曾用名（需 `Accept: application/json` 头） |

**依赖**：`pyliftover`（hg19↔hg38 坐标转换）。运行环境需具备 `curl` 命令和网络访问能力。

## 运行方式

内嵌脚本为可直接运行的 Python 脚本（`if __name__ == "__main__"` 入口），用法：

```
python SKILL.md_embedded_script.py <变异标识>
# 以下为命令用法举例（仅说明写法，非真实数据），实际运行时替换为用户的真实变异标识
python SKILL.md_embedded_script.py rs80357906
python SKILL.md_embedded_script.py "BRCA1:c.5266dup"
python SKILL.md_embedded_script.py "NM_007294.4:c.5266dup"
```

在未拆分脚本文件的运行环境中，可直接调用 `standardize_variant("...")` 主函数完成标准化。

## 注意事项

- **真实查询原则**：所有查询一律使用用户本次提供的真实变异标识，输出一律以真实 API 返回数据为准；本文档任何示例（如 `BRCA1 c.5266dup`、`rs80357906` 等）仅作格式说明，**严禁作为查询输入或出现在输出结果中**。
- 结果末尾必须标注"智能分析结果，仅供参考"
- 使用领域标准术语，禁止自造词
- MANE Select 转录本用 ⭐ 标注
- 蛋白变化同时输出三字母全写和单字母简写格式
- 如果 GeneBe API 无法查询到结果，提示用户检查输入格式
- **不提取、不输出** GeneBe API 返回数据中的 `clinvar_classification`、`clinvar_count`、`acmg_classification`、`acmg_criteria` 等字段。本 Skill 仅负责变异标准化（基因名、转录本、坐标、HGVS），临床分类和致病性评估由其他专项 Skill 负责

---

## 内嵌实现脚本

> 以下代码块为完整可执行实现，自包含，无外部文件依赖（仅需 `pyliftover` 库与系统 `curl`）。

```python
"""
变异标准化查询工具 - 基于 GeneBe API + HGNC
支持：rs号、cDNA、蛋白变化、基因组坐标等多种输入格式的标准化输出
输出：基因名（现用名+曾用名）、转录本号、cDNA、蛋白变化、rs号、基因组坐标(hg38+hg19)
"""
import re
import json
import subprocess
import sys
from urllib.parse import urlencode
from pyliftover import LiftOver

BASE_URL = "https://api.genebe.net/cloud/api-public/v1"

# 三字母氨基酸代码 → 单字母氨基酸代码
AA3_TO_AA1 = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
    "Glu": "E", "Gln": "Q", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
    "Ter": "*", "Asx": "B", "Glx": "Z", "Xaa": "X", "Xle": "J",
    "Sec": "U", "Pyl": "O",
}


def protein_3to1(hgvs_p_full):
    """
    将三字母全写 HGVS 蛋白描述转为单字母简写
    例: p.(Gln1756ProfsTer74) → p.(Q1756Pfs*74)
         p.(Arg123*) → p.(R123*)
    """
    if not hgvs_p_full:
        return hgvs_p_full

    def replace_aa(match):
        aa3 = match.group(0)
        return AA3_TO_AA1.get(aa3, aa3)

    # 替换所有三字母氨基酸代码（首字母大写+两小写）
    result = re.sub(r'[A-Z][a-z]{2}', replace_aa, hgvs_p_full)
    return result


def exon_label(csq):
    """根据 consequences 数据返回外显子/内含子位置标签"""
    er = csq.get("exon_rank")
    ec = csq.get("exon_count")
    ir = csq.get("intron_rank")
    if er is not None:
        return f"外显子 {er}/{ec}" if ec else f"外显子 {er}"
    if ir is not None:
        # 内含子总数 = 外显子数 - 1
        intron_total = (ec - 1) if ec else None
        return f"内含子 {ir}/{intron_total}" if intron_total else f"内含子 {ir}"
    return ""


def classify_variant_class(csq):
    """
    从单条 consequence 判定变异大类与框内框外（硬闸身份要素 2/3）。
    返回 (variant_class, is_frameshift, is_inframe)
    variant_class ∈ missense/nonsense/synonymous/frameshift/inframe/splicing/noncoding/other_protein，None=无法判定
    is_frameshift / is_inframe：仅对插入缺失类有意义，错义/无义/同义/剪接为 None
    """
    if not csq:
        return None, None, None
    effects = [str(e).lower() for e in (csq.get("consequences") or [])]
    if not effects:
        return None, None, None
    joined = "|".join(effects)
    if any(k in joined for k in ("frameshift_variant", "frameshift")):
        return "frameshift", True, False
    if any(k in joined for k in ("inframe_deletion", "inframe_insertion", "inframe_variant")):
        return "inframe", False, True
    if "missense_variant" in joined:
        return "missense", False, None
    if any(k in joined for k in ("stop_gained", "nonsense")):
        return "nonsense", False, None
    if "synonymous_variant" in joined:
        return "synonymous", False, None
    if any(k in joined for k in ("splice_donor_variant", "splice_acceptor_variant", "splice_region_variant",
                                 "splice_donor", "splice_acceptor", "splice_region")):
        return "splicing", False, None
    if any(k in joined for k in ("5_prime_utr", "3_prime_utr", "intron_variant", "upstream_gene",
                                 "downstream_gene", "non_coding", "nc_transcript")):
        return "noncoding", False, None
    if any(k in joined for k in ("stop_lost", "start_lost", "stop_retained")):
        return "other_protein", False, None
    return None, None, None


def _display_width(s):
    """计算字符串的显示宽度（中文字符算2，其他算1）"""
    width = 0
    for c in s:
        if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f':
            width += 2
        else:
            width += 1
    return width


def _pad_right(s, width):
    """右填充空格到指定显示宽度"""
    current = _display_width(s)
    return s + ' ' * max(0, width - current)


def curl_get(url, params=None):
    """使用 curl 发送 GET 请求，避免 Python SSL 问题"""
    if params:
        url = f"{url}?{urlencode(params)}"

    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "30", url],
            capture_output=True,
            text=True,
            timeout=35
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        else:
            return {"error": f"curl 请求失败: {result.stderr}"}
    except subprocess.TimeoutExpired:
        return {"error": "请求超时"}
    except json.JSONDecodeError:
        return {"error": "响应解析失败"}


def get_gene_aliases(gene_symbol):
    """
    通过 HGNC API 获取基因曾用名
    返回：{current: "现用名", aliases: ["曾用名1", "曾用名2", ...]}
    """
    url = f"https://rest.genenames.org/fetch/symbol/{gene_symbol}"

    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return {"current": gene_symbol, "aliases": []}

        doc = docs[0]
        current = doc.get("symbol", gene_symbol)
        aliases = doc.get("alias_symbol", [])

        return {
            "current": current,
            "aliases": aliases if aliases else []
        }
    except Exception as e:
        # 查询失败时保留明确错误，避免静默输出为"无曾用名"
        return {"current": gene_symbol, "aliases": [], "error": str(e)}


def _parse_raw_coords(query_id):
    """
    尝试从输入字符串中解析原始基因组坐标
    支持格式: chr17:41209079:C:T, chr17:41209079:C>T, 17-41209079-C-T, 17:41209079:C>T
    分隔符支持 : > - 的任意组合
    返回: (chr, pos, ref, alt) 或 None
    """
    # 统一格式: 支持 : > - 作为分隔符的任意组合
    # 匹配: [chr]chr_num SEP pos SEP ref SEP alt
    m = re.match(r'^(?:chr)?(\w+)[:\-](\d+)[:>\-](\w+)[:>\-](\w+)$', query_id, re.IGNORECASE)
    if m:
        return m.group(1), int(m.group(2)), m.group(3), m.group(4)

    # 格式: chr17:41209079 (仅坐标，无 ref/alt - 不足以确定变异)
    return None


def convert_variant(variant_str):
    """
    将各种格式的变异转换为基因组坐标（hg38）
    支持：rs号、HGVS cDNA/蛋白格式、VCF格式、基因组坐标（hg38/hg19）

    hg19 处理策略：
    - GeneBe convert API 不支持 hg19 输入（会返回 "Only hg38 output is supported"）
    - 对于 hg19 原始坐标输入：手动解析后用 pyliftover 转换为 hg38
    - 对于 hg19 rs号/HGVS 输入：这些是基因组无关的，直接传 genome=hg38 给 GeneBe
    """
    url = f"{BASE_URL}/convert"

    query_id = variant_str.strip()
    is_hg19 = False

    # 预处理1：全角标点转半角（中文冒号、逗号等）
    query_id = query_id.replace('：', ':').replace('，', ',').replace('＞', '>')

    # 预处理2：自动补 c. 前缀
    # 匹配模式：基因名 + 空格 + 数字开头（但没有 c. / p. / m. / g. / r. 前缀）
    # 例: "SLC25A13 852_855del" → "SLC25A13 c.852_855del"
    query_id = re.sub(
        r'^([A-Za-z0-9_-]+)\s+(?![cpmgr]\.)(\d)',
        r'\1 c.\2',
        query_id
    )

    # 预处理3：检测不完整的变异格式（只有位置没有变化类型）
    # 例: "TP53 c.248" 或 "GENE 248" → 直接报错，避免 API 超时 30s
    if re.match(r'^[A-Za-z0-9_-]+\s+c\.\d+$', query_id):
        return {"error": f"变异格式不完整: {variant_str}（缺少变化类型，如 c.248A>T 或 c.248del）"}

    # 检查是否指定 hg19（匹配 genome=hg19 参数或独立 hg19 关键词）
    hg19_param = re.compile(r'[&?]genome=hg19\b', re.IGNORECASE)
    hg19_keyword = re.compile(r'(?:^|\s)hg19(?:\s|$)', re.IGNORECASE)
    if hg19_param.search(query_id) or hg19_keyword.search(query_id):
        is_hg19 = True
        query_id = hg19_param.sub('', query_id)
        query_id = hg19_keyword.sub(' ', query_id).strip()

    # hg19 原始坐标：手动解析 + pyliftover 转换
    if is_hg19:
        parsed = _parse_raw_coords(query_id)
        if parsed:
            hg19_chr, hg19_pos, hg19_ref, hg19_alt = parsed
            try:
                lo = LiftOver('hg19', 'hg38')
                result = lo.convert_coordinate(f"chr{hg19_chr}", int(hg19_pos))
                if result and len(result[0]) >= 2:
                    hg38_chr = result[0][0].replace("chr", "")
                    hg38_pos = result[0][1]
                    return {
                        "chr": hg38_chr,
                        "pos": hg38_pos,
                        "ref": hg19_ref,
                        "alt": hg19_alt,
                        "genome": "hg38",
                        "input_genome": "hg19",
                        "converted_from_hg19": True
                    }
                else:
                    return {"error": f"hg19→hg38 坐标转换失败：chr{hg19_chr}:{hg19_pos} 无对应 hg38 坐标"}
            except Exception as e:
                return {"error": f"hg19→hg38 转换异常: {str(e)}"}
        # hg19 但非原始坐标（如 rs号/HGVS）→ 直接走 GeneBe（genome=hg38，基因组无关）

    # GeneBe convert API（始终使用 genome=hg38）
    params = {"id": query_id, "genome": "hg38"}
    result = curl_get(url, params)

    if "error" in result:
        return result

    # API 返回格式: [{"variants": [{"genome": "hg38", "chr": "17", ...}]}]
    if isinstance(result, list) and len(result) > 0:
        first = result[0]
        if "variants" in first and len(first["variants"]) > 0:
            v = first["variants"][0]
            return {
                "chr": v.get("chr", ""),
                "pos": v.get("pos", ""),
                "ref": v.get("ref", ""),
                "alt": v.get("alt", ""),
                "genome": v.get("genome", "hg38"),
                "input_genome": "hg19" if is_hg19 else "hg38"
            }

    # 线粒体基因特殊提示
    if re.match(r'(?i)MT-', query_id) and re.search(r'(?i)\bc\.', query_id):
        return {"error": f"线粒体基因不支持 c. 前缀: {variant_str}，请使用 m. 前缀格式（如 m.8993T>G）或基因组坐标"}

    return {"error": f"无法识别的变异格式: {variant_str}"}


def get_variant_data(chr_val, pos, ref, alt, genome="hg38"):
    """获取变异注释数据（含转录本注释和顶层元信息）"""
    url = f"{BASE_URL}/variant"
    params = {
        "chr": chr_val, "pos": pos, "ref": ref, "alt": alt,
        "useRefseq": "true", "useEnsembl": "false", "genome": genome
    }
    result = curl_get(url, params)
    if "error" in result:
        return result
    if isinstance(result, dict) and "variants" in result and len(result["variants"]) > 0:
        return result["variants"][0]
    return {}


def standardize_variant(variant_input):
    """
    主流程：变异标准化
    输出完整信息：基因名（现用名+曾用名）、转录本号、cDNA、蛋白变化、rs号、基因组坐标(hg38+hg19)、pHGVS
    """
    print(f"🔍 正在查询变异: {variant_input}\n")

    # Step 1: 转换为基因组坐标
    coord = convert_variant(variant_input)
    if "error" in coord:
        print(f"❌ {coord['error']}")
        return

    # Step 2+3: 并行查询变异注释 (GeneBe) + 基因曾用名 (HGNC)
    # 先从 consequences 获取 gene_symbol 用于 HGNC 查询，但需要先拿到 variant_data
    # 所以改为：先启动 GeneBe variant 请求，同时从 convert 结果无法获取 gene_symbol
    # 最优方案：GeneBe variant 和 HGNC 串行，共 3 次 API 调用

    variant_data = get_variant_data(coord["chr"], coord["pos"], coord["ref"], coord["alt"])
    if "error" in variant_data:
        print(f"❌ {variant_data['error']}")
        return

    consequences = variant_data.get("consequences", [])
    data_gap = False
    if not consequences:
        data_gap = True
        print("⚠️ 该转录本未返回注释数据（数据缺口）：变异身份要素无法从注释源确认，标注 data_gap 待核，不阻塞为卡死。")

    gene_from_consequence = ""
    if consequences:
        gene_from_consequence = consequences[0].get("gene_symbol", "")

    # 获取基因曾用名（通过 HGNC）
    gene_symbol = gene_from_consequence or ""
    alias_info = {"current": gene_symbol, "aliases": []}
    if gene_symbol:
        alias_info = get_gene_aliases(gene_symbol)
        if "error" in alias_info:
            print(f"⚠️ HGNC 曾用名查询失败（将显示为无）：{alias_info['error']}")

    # Step 4: 提取 rs号（从 variant 顶层 dbsnp 字段）
    rs_id = variant_data.get("dbsnp", "") or ""

    # Step 5: 提取 MANE Select 转录本
    # MANE Select 的判断：如果 consequence 有 mane_select 字段，说明它属于 MANE Select 转录本
    mane_csq = None
    for csq in consequences:
        if csq.get("mane_select"):
            mane_csq = csq
            break

    # ── 变异身份归一化硬闸（v1.1.0）：确认变异类型 / 框内框外 / 蛋白改变 / 基因内位置 ──
    primary_csq = mane_csq
    if primary_csq is None and consequences:
        primary_csq = next((c for c in consequences if c.get("consequences")), consequences[0])
    variant_class, is_frameshift, is_inframe = (None, None, None)
    hgvs_p_primary = ""
    gene_region = ""
    identity_status = "annotated"
    blocked_reason = ""
    if data_gap:
        identity_status = "data_gap"
        blocked_reason = "该转录本无注释数据，身份要素待核"
    elif primary_csq is None:
        identity_status = "blocked"
        blocked_reason = "无任何转录本后果，无法判定变异类型"
    else:
        variant_class, is_frameshift, is_inframe = classify_variant_class(primary_csq)
        hgvs_p_primary = (primary_csq.get("hgvs_p") or "")
        gene_region = exon_label(primary_csq) or ""
        protein_required = variant_class in ("missense", "nonsense", "frameshift", "inframe", "other_protein")
        if variant_class is None:
            identity_status = "blocked"
            blocked_reason = "无法从注释后果判定变异类型（禁止按密码子推断）"
        elif protein_required and not hgvs_p_primary:
            identity_status = "blocked"
            blocked_reason = "蛋白改变类变异未取得 p.HGVS（禁止推断蛋白改变）"
        else:
            identity_status = "annotated"
        if not gene_region:
            gene_region = "待核（注释源未给外显子/内含子位置）"

    if identity_status in ("blocked", "data_gap"):
        print()
        print("=" * 70)
        if identity_status == "blocked":
            print("🔒 变异身份未确认 · 评级中止 · 待人工复核（阻塞态，可恢复）")
        else:
            print("⚠️ 变异身份部分待核（data_gap）")
        print(f"   状态: {identity_status}")
        print(f"   原因: {blocked_reason}")
        print(f"   变异类型: {variant_class or '未判定'}  框内框外: {('移码' if is_frameshift else ('框内' if is_inframe else '不适用/未判定'))}  基因内位置: {gene_region}")
        print("   处理: 人工确认真实变异后以标准格式重新传入即可继续评级；禁止用推断填补身份要素。")
        print("=" * 70)

    # Step 6: 输出结果（两大块：基因信息 + 变异信息）
    print()
    print("=" * 70)
    print("📋 变异标准化结果")
    print("=" * 70)
    print()

    # ── 第一块：基因信息 ──
    print("【基因信息】")
    print(f"  现用名: {alias_info['current']}")
    if alias_info['aliases']:
        print(f"  曾用名: {', '.join(alias_info['aliases'])}")
    else:
        print(f"  曾用名: 无")
    print()

    # ── 第二块：变异信息 ──
    print("【变异信息】")

    chr_val = coord['chr']
    pos = coord['pos']
    ref = coord['ref']
    alt = coord['alt']

    # 基因组坐标
    print("  基因组坐标:")
    print(f"    hg38: chr{chr_val}:{pos} {ref}>{alt}  (VCF: {chr_val}-{pos}-{ref}-{alt})")
    try:
        lo = LiftOver('hg38', 'hg19')
        hg19 = lo.convert_coordinate(f"chr{chr_val}", int(pos))
        if hg19 and len(hg19[0]) >= 2:
            hg19_chr = hg19[0][0].replace("chr", "")
            hg19_pos = hg19[0][1]
            print(f"    hg19: chr{hg19_chr}:{hg19_pos} {ref}>{alt}  (VCF: {hg19_chr}-{hg19_pos}-{ref}-{alt})")
        else:
            print(f"    hg19: 转换失败（该位点可能无对应坐标）")
    except Exception:
        print(f"    hg19: 转换失败")

    # rs号
    if rs_id:
        print(f"  rs号: {rs_id}")
    print()

    # 转录本注释
    nm_consequences = [c for c in consequences if (c.get("transcript") or "").startswith("NM_")]

    print(f"  转录本注释 (共 {len(nm_consequences)} 个 NM_ 转录本)")
    print("  " + "-" * 68)

    # 按 gene_symbol 分组
    genes = {}
    for csq in nm_consequences:
        g = csq.get("gene_symbol", "Unknown")
        if g not in genes:
            genes[g] = []
        genes[g].append(csq)

    MAX_DISPLAY = 5  # 每组效应最多显示的转录本数

    for gene, csq_list in genes.items():
        print(f"\n  ### 基因: {gene} ({len(csq_list)} 个 NM_ 转录本)")

        # 分离 MANE 和其他
        mane_csqs = [c for c in csq_list if c.get("mane_select")]
        other_csqs = [c for c in csq_list if not c.get("mane_select")]

        # 按效应类型分组
        effect_groups = {}
        for csq in other_csqs:
            effects = csq.get("consequences", [])
            primary = effects[0] if effects else "unknown"
            if primary not in effect_groups:
                effect_groups[primary] = []
            effect_groups[primary].append(csq)

        # 主转录本 (MANE Select)
        if mane_csqs:
            print(f"    ▶ 主转录本 (MANE Select): ⭐")
            for csq in mane_csqs:
                tx = csq.get("transcript", "") or ""
                hgvs_c = csq.get("hgvs_c", "-") or "-"
                hgvs_p = csq.get("hgvs_p", "-") or "-"
                hgvs_p_short = protein_3to1(hgvs_p) if hgvs_p != "-" else "-"
                effect = ",".join(csq.get("consequences", [])) or "-"
                el = exon_label(csq)
                print(f"      转录本: {tx}" + (f"  ({el})" if el else ""))
                print(f"      cDNA: {hgvs_c}")
                print(f"      蛋白变化(全写): {hgvs_p}")
                print(f"      蛋白变化(简写): {hgvs_p_short}")
                print(f"      效应: {effect}")

        # 按效应类型汇总其他转录本
        for effect_type, group in sorted(effect_groups.items(), key=lambda x: -len(x[1])):
            shown = group[:MAX_DISPLAY]
            print(f"\n    ▶ {effect_type} ({len(group)} 个)")
            print(f"      {_pad_right('转录本', 20)} {_pad_right('位置', 12)} {_pad_right('cDNA', 22)} {_pad_right('蛋白(简写)', 20)}")
            print(f"      {'-' * 77}")
            for csq in shown:
                tx = csq.get("transcript", "") or ""
                el = exon_label(csq) or "-"
                hgvs_c = csq.get("hgvs_c", "-") or "-"
                hgvs_p = csq.get("hgvs_p", "-") or "-"
                hgvs_p_short = protein_3to1(hgvs_p) if hgvs_p != "-" else "-"
                print(f"      {_pad_right(tx, 20)} {_pad_right(el, 12)} {_pad_right(hgvs_c, 22)} {_pad_right(hgvs_p_short, 20)}")
            if len(group) > MAX_DISPLAY:
                print(f"      ... 还有 {len(group) - MAX_DISPLAY} 个已省略")

    print()
    print("=" * 70)
    print("智能分析结果，仅供参考")
    print("=" * 70)

    return {
        "gene": gene_symbol,
        "gene_aliases": alias_info,
        "coord": coord,
        "rs_id": rs_id,
        "mane_csq": mane_csq,
        "consequences": consequences,
        # ── 变异身份归一化硬闸字段（v1.1.0）──
        "identity_status": identity_status,          # annotated / blocked / data_gap
        "identity_reason": blocked_reason or "",     # blocked/data_gap 原因
        "variant_class": variant_class,              # missense/nonsense/synonymous/frameshift/inframe/splicing/noncoding/other_protein/None
        "is_frameshift": is_frameshift,              # 移码 True/False/None(不适用)
        "is_inframe": is_inframe,                    # 框内 True/False/None(不适用)
        "gene_region": gene_region,                  # 外显子/内含子位置或"待核"
        "protein_change": hgvs_p_primary             # 主转录本 p.HGVS（蛋白类变异须非空）
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python main.py <变异标识>")
        sys.exit(1)

    variant_input = sys.argv[1]
    standardize_variant(variant_input)
```
