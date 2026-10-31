# -*- coding: utf-8 -*-
"""ACMG 评级技能群 · 确定性证据档位引擎 acmg_evidence.py

把各 ev-* 子 SKILL 中"数据值 → 证据码强度档位"的纯查表 / 累分逻辑脚本化，
替代 LLM 手工查表（防档位标错、累分错误、中空档误判）。阈值统一读 config/thresholds.json；
缺失的强度表以带 source+version 的内联常量给出（与对应子 SKILL 的现行口径一致）。

设计铁律：
- 本引擎只做"数据 → 档位"的确定性映射，不做取数 / 文献核验 / 语义判断；
- 输入"数据值"由各子 SKILL（LLM/库查询）提取；取不到则返回 None 并说明，不得默认档位；
- 每个函数返回 (档位, 依据说明)；档位格式如 "PM2_Supporting"、"PP3_Strong"、"PM3_Moderate"；
  不成立时返回 (None, "不成立原因")，供子 SKILL 写入"查不到/不适用"。

用法：python acmg_evidence.py 函数名 参数...
或：import acmg_evidence; acmg_evidence.revel_band(0.972)
"""
import json
import os
import math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(BASE, "config", "thresholds.json")


def _load():
    with open(CONF, encoding="utf-8") as f:
        return json.load(f)


T = _load()


# ============ 1. REVEL → PP3/BP4 档位（thresholds.revel；指南解读 slide 53/Table 2） ============
def revel_band(revel):
    """REVEL 值 → PP3_Strong/Moderate/Supporting 或 BP4_VeryStrong/Strong/Moderate/Supporting。
    中空档 (0.290, 0.644) → PP3/BP4 均不适用（必须返回 None，不得默认任一侧）。"""
    r = T["revel"]
    if revel is None:
        return None, "REVEL 取不到"
    # D31（2026-10-15）：依据说明从 config 格式化，禁止硬编码字面量——改 config 后逻辑与打印必须同步
    if revel >= r["pp3_strong_min"]:
        return "PP3_Strong", f"REVEL={revel} ≥{r['pp3_strong_min']} → PP3_Strong"
    if revel >= r["pp3_moderate_min"]:
        return "PP3_Moderate", f"REVEL={revel} ∈[{r['pp3_moderate_min']},{r['pp3_strong_min']}) → PP3_Moderate"
    if revel >= r["pp3_supporting_min"]:
        return "PP3_Supporting", f"REVEL={revel} ∈[{r['pp3_supporting_min']},{r['pp3_moderate_min']}) → PP3_Supporting"
    if revel <= r["bp4_very_strong_max"]:
        return "BP4_VeryStrong", f"REVEL={revel} ≤{r['bp4_very_strong_max']} → BP4_VeryStrong"
    if revel <= r["bp4_strong_max"]:
        return "BP4_Strong", f"REVEL={revel} ∈({r['bp4_very_strong_max']},{r['bp4_strong_max']}] → BP4_Strong"
    if revel <= r["bp4_moderate_max"]:
        return "BP4_Moderate", f"REVEL={revel} ∈({r['bp4_strong_max']},{r['bp4_moderate_max']}] → BP4_Moderate"
    if revel <= r["bp4_supporting_max"]:
        return "BP4_Supporting", f"REVEL={revel} ∈({r['bp4_moderate_max']},{r['bp4_supporting_max']}] → BP4_Supporting"
    return None, f"REVEL={revel} 落中空档 ({r['bp4_supporting_max']},{r['pp3_supporting_min']})，PP3/BP4 均不适用"


# ============ 2. PM2 AF → 档位（ev-pm2 第3.5步：AD/XL 0.0005、AR 0.001；特异性阈值优先） ============
def pm2_band(af, mode="AD", gene_specific=None):
    """PM2：AF vs 阈值 → 档位。mode=AD/XL|AR；gene_specific 为基因/疾病特异性阈值（优先）。
    满足阈值 → PM2_Supporting（ev-pm2 自检口径，SVI 降级）；AF=0 → Supporting。
    gene_specific 可传 ev-pm2 子技能从 VCEP 原文现场解析的主阈值（路由方案）。"""
    pm2 = T["pm2"]
    if af is None:
        return None, "AF 取不到"
    if gene_specific is not None:
        th, src = gene_specific, f"基因特异性阈值 {gene_specific}"
    else:
        # 读配置表"本实验室现行通用口径"（af_lab_generic），与子技能 ev-pm2 口径一致
        lab = pm2.get("af_lab_generic", {})
        th = lab.get(mode.upper(), lab.get("AD", 0.0005))
        src = f"{mode} 通用阈值 {th}（af_lab_generic，{lab.get('version','lab-v1')}）"
    if af < th:
        return "PM2_Supporting", f"AF={af} < 阈值{th}（{src}）→ PM2_Supporting"
    return None, f"AF={af} ≥ 阈值{th}（{src}），PM2 不成立（罕见前提不满足）"


# ============ 3. PM3 反式累分 → 档位（ev-pm3 计分表 + 第3步强度表） ============
def pm3_points(examples, phase_A=0, phase_B_P=0, phase_B_LP=0, homozyg=0, vus_trans=0):
    """PM3 累分：examples 为逐例清单[权重]，或直接传各分档例数。
    权重（ev-pm3 计分表 / thresholds.pm3_score）：
      confirmed in trans(A) 1.0；phase-unknown P(B-P) 0.5、LP(B-LP) 0.25；
      纯合（P1-1 修正，SVI PM3 Table I 两档）：非近亲 hom_nonconsang 1.0 无上限、近亲 hom_consang 0.5 每家系封顶 1.0；
      VUS 0.25。
    强度（第3步表）：<0.5→不计/Supporting? ；0.5→Supporting；1.0–1.9→Moderate；2.0–3.9→Strong；≥4.0→VeryStrong。
    """
    pm3 = T["pm3_score"]
    weights = {
        "A": pm3["confirmed_in_trans"], "B_P": pm3["phase_unknown_P"],
        "B_LP": pm3["phase_unknown_LP"],
        "hom": pm3["homozygous"], "hom_consang": pm3["homozygous"],
        "hom_nonconsang": pm3["homozygous_nonconsang"],
        "VUS": pm3["VUS_in_trans"],
    }
    # P1-1：近亲纯合(hom/hom_consang) 封顶 1.0；非近亲(hom_nonconsang) 无上限
    caps = {"hom": pm3.get("homozygous_cap", 1.0), "hom_consang": pm3.get("homozygous_cap", 1.0),
            "VUS": pm3.get("VUS_cap", 0.5)}
    # 逐例累分（examples 每项形如 {"type": "A"|"B_P"|"B_LP"|"hom"|"hom_consang"|"hom_nonconsang"|"VUS", "n": 例数}）
    total = 0.0
    detail = []
    for ex in examples or []:
        typ = ex.get("type", "A")
        n = ex.get("n", 1)
        w = weights.get(typ)
        if w is None:
            continue
        if typ in caps:
            # 近亲纯合封顶 1.0 / VUS 封顶 0.5（官网核对 Q9：表 'VUS 变异（上限 0.5）'，引擎此前漏实现）
            add = min(caps[typ], w * n)
        else:
            add = w * n
        total += add
        detail.append(f"{typ}×{n}(w={w})=+{add:.2f}")
    if total < 0.5:
        return None, f"PM3 累分={total:.2f} <0.5，不足以定档（若为反式例但相位无佐证→按 C 不计分）"
    if total >= 4.0:
        band = "PM3_VeryStrong"
    elif total >= 2.0:
        band = "PM3_Strong"
    elif total >= 1.0:
        band = "PM3_Moderate"
    else:
        band = "PM3_Supporting"
    return band, f"PM3 累分={total:.2f}（{' + '.join(detail)}）→ {band}"


def pm3_vcep_band(examples, gene, spec=None, max_band=None):
    """PM3 VCEP 基因特异档位判定（v1.13.0 路由方案，与 pm3_points 共用逐例计分权重）。

    逐例计分权重全基因一致（SVI Table 1：confirmed in trans(A) 1.0 / phase-unknown P(B_P) 0.5、
    LP(B_LP) 0.25 / 纯合(hom) 0.5 / VUS 0.25，读 thresholds.pm3_score）——各 VCEP 均引用此表。
    PM3 的『基因特异』只在『档位切点』（累分多少→哪档强度），由 spec 定义。

    参数：
      examples: 逐例清单[{"type": "A"|"B_P"|"B_LP"|"hom"|"VUS", "n": 例数}]
      gene:     基因名（用于 spec 缺省时回退标准档并标注来源）
      spec:     档位表 dict：{"supporting": 0.5, "moderate": 1, "strong": 2, "vs": 4}
                （VCEP 特异档如 ATM/PALB2/FOXN1=1/2/4/8）。缺省=None=标准 SVI 档 0.5/1/2/4。
      max_band: 封顶档位（如 BRCA1/2 无 VS→max_band="PM3_Strong"；LDLR 仅 Moderate→"PM3_Moderate"）。
                命中累分超过 max_band 档时封顶在该档。

    返回 (档位, 说明)；无 spec 且未指定特异 → 走标准档（调用 pm3_points 逻辑）。
    """
    pm3 = T["pm3_score"]
    weights = {
        "A": pm3["confirmed_in_trans"], "B_P": pm3["phase_unknown_P"],
        "B_LP": pm3["phase_unknown_LP"],
        "hom": pm3["homozygous"], "hom_consang": pm3["homozygous"],
        "hom_nonconsang": pm3["homozygous_nonconsang"],
        "VUS": pm3["VUS_in_trans"],
    }
    # P1-1：近亲纯合(hom/hom_consang) 封顶 1.0；非近亲(hom_nonconsang) 无上限
    caps = {"hom": pm3.get("homozygous_cap", 1.0), "hom_consang": pm3.get("homozygous_cap", 1.0),
            "VUS": pm3.get("VUS_cap", 0.5)}
    total = 0.0
    detail = []
    for ex in examples or []:
        typ = ex.get("type", "A")
        n = ex.get("n", 1)
        w = weights.get(typ)
        if w is None:
            continue
        add = min(caps[typ], w * n) if typ in caps else w * n
        total += add
        detail.append(f"{typ}×{n}(w={w})=+{add:.2f}")
    if total < 0.5:
        return None, f"PM3 累分={total:.2f} <0.5，不足以定档（若为反式例但相位无佐证→按 C 不计分）"
    # 档位切点：spec 缺省→标准 SVI 档 0.5/1/2/4
    s = spec or {"supporting": 0.5, "moderate": 1, "strong": 2, "vs": 4}
    src = "VCEP 特异档" if spec else "标准 SVI 档"
    if total >= s["vs"]:
        band = "PM3_VeryStrong"
    elif total >= s["strong"]:
        band = "PM3_Strong"
    elif total >= s["moderate"]:
        band = "PM3_Moderate"
    elif total >= s["supporting"]:
        band = "PM3_Supporting"
    else:
        return None, f"PM3 累分={total:.2f} < 特异档 Supporting 切点 {s['supporting']}，不足以定档"
    if max_band is not None and band != max_band:
        # 封顶：仅当命中档高于 max_band 时封顶；同档或低于不受影响
        order = ["PM3_Supporting", "PM3_Moderate", "PM3_Strong", "PM3_VeryStrong"]
        if order.index(band) > order.index(max_band):
            band = max_band
            return band, f"PM3 累分={total:.2f}（{' + '.join(detail)}）→ 命中 {band} 但 {gene} VCEP 封顶 {max_band}（{src}）"
    return band, f"PM3 累分={total:.2f}（{' + '.join(detail)}）→ {band}（{src}）"

def pp4_vcep_band(value, gene, spec=None, max_band=None):
    """PP4 VCEP 基因特异档位判定（v1.4.0 路由方案）。

    PP4 证据本质：先查文献/临床数据拿到受检者实际数值（表型分/生化值/酶活%/MSI 肿瘤计数/多因素
    LR 等），再拿数值对照该基因 VCEP 特异规则匹配档位——VCEP 只定义『多少数值→哪档』，数值本身
    必须由执行者先查取（ev-disease-info + 文献通道），引擎不做取数。

    支持 PP4 的数值型形态（由 spec["type"] 区分，与 pp1/pp3 路由同源）：
      - points 点数型：spec["bands"]={"supporting":[lo,hi), "moderate":[lo,hi), "strong":[lo,hi), ...}
        如 ADA/DCLRE1C/IL2RG/IL7R/JAK3（1-<2 SU / 2-<6 MO / ≥6 ST）、RAG1/RAG2/FOXN1/RMRP、
        RPGR 表型分（4-7 SU / >8 MO）、RPE65/GUCY2D（4-7.5 SU / 8 MO）、GAMT/GATM（1-2/3/4）、OTC；
      - count 计数型：spec["bands"] 同上，value 为整数例数。如 MLH1/MSH2/MSH6/PMS2（1 SU / 2 MO / ≥3 ST）；
      - lr 似然比型：spec["bands"] 同上，value 为 LR 值。如 BRCA1/BRCA2（≥2.08 SU / ≥4.3 MO / ≥18.7 ST）。
    条件式/纯表型特异（酶活%、生化条件、表型高度特异等）→ spec["type"]="phenotype"，引擎不判数值，
    返回需执行者按 VCEP 原文核临床条件。

    参数：
      value: 受检者实际数值（点数/计数/LR；phenotype 型不传）
      gene:  基因名
      spec:  形态与档位 spec（缺省=None=回退通用表型特异 Supporting，标注通用口径）
      max_band: 封顶档（VCEP 只定义到某档时，如纯表型仅 Supporting）

    返回 (档位, 说明)；数值型不足任何档→None；phenotype 型→(None, "需路由读 VCEP 原文核临床条件")。
    """
    if not spec:
        return "PP4_Supporting" if not max_band else max_band, \
            f"PP4 通用口径（无 VCEP 特异 spec）：表型高度特异→Supporting{'; 封顶 '+max_band if max_band else ''}"
    typ = spec.get("type", "phenotype")
    if typ == "phenotype":
        return None, f"{gene} VCEP PP4 为条件式/表型特异（{spec.get('note','按原文')}）：需执行者路由读 VCEP-{gene}.md 原文核临床/生化条件，引擎不判数值"
    bands = spec.get("bands", {})
    if value is None:
        return None, f"{gene} VCEP PP4 数值未取到（{typ}型）：先查文献/临床数据拿数值再匹配，不得默认给档"
    order = [("vs", "PP4_VeryStrong"), ("strong", "PP4_Strong"), ("moderate", "PP4_Moderate"), ("supporting", "PP4_Supporting")]
    for key, band in order:
        if key not in bands:
            continue
        lo, hi = bands[key]
        if lo is not None and value < lo:
            continue
        if hi is not None and value >= hi:
            continue
        if max_band is not None and band != max_band:
            ob = ["PP4_Supporting", "PP4_Moderate", "PP4_Strong", "PP4_VeryStrong"]
            if ob.index(band) > ob.index(max_band):
                return max_band, f"{gene} VCEP PP4（{typ}型）：value={value} 命中 {band} 但封顶 {max_band}"
        return band, f"{gene} VCEP PP4（{typ}型）：value={value} 落 {key} 档 → {band}"
    return None, f"{gene} VCEP PP4（{typ}型）：value={value} 不落任何档位（不足 Supporting 下限）"

def pp1_lod_adxl(segregations, gene=None):
    """PP1 显性/XL：LOD = log10(1 / 0.5^segregations)。
    强度（phenocopy 不成立，阈值读 config pp1_lod【通用 J&B 2016 原值】）：Supporting LOD≥0.9；Moderate ≥1.2；Strong ≥1.5。
    ⚠ 通用=通用、特异=特异（2026-10-20 用户拍板分流）：通用位置一律 J&B 2016 原值（3/4/5 减数分裂）；
    疾病特异档（CMP-EP 0.9/1.5/2.1、HL VCEP 0.6/1.2/1.5）分别走 pp1_lod_cmp_ep / hl_vcep_pp1，按基因选用，不塞通用。
    传 gene 命中 CMP-EP（心肌病）锚点时自动改用 CMP-EP 档 0.9/1.5/2.1；命中 HL VCEP 时 AR 走 hl_vcep_pp1。"""
    if gene is not None and _in_cmp_ep(gene):
        pp1 = T.get("pp1_lod_cmp_ep", {"supporting": 0.9, "moderate": 1.5, "strong": 2.1})
        src = "CMP-EP 疾病特异档"
    else:
        pp1 = T.get("pp1_lod", {"supporting": 0.9, "moderate": 1.2, "strong": 1.5})
        src = "通用 J&B 2016 档"
    if segregations is None or segregations < 2:
        return None, "共分离分离次数不足"
    lod = math.log10(1 / (0.5 ** segregations))
    if lod >= pp1["strong"]:
        band = "PP1_Strong"
    elif lod >= pp1["moderate"]:
        band = "PP1_Moderate"
    elif lod >= pp1["supporting"]:
        band = "PP1_Supporting"
    else:
        band = None
    return band, f"分离次数={segregations} → LOD={lod:.2f} → {band if band else '不成立'}（{src}，阈值 {pp1['supporting']}/{pp1['moderate']}/{pp1['strong']}）"


def pp1_lod_ar(affected, unaffected, parental_both_carrier=True, gene=None):
    """PP1 隐性：LOD = log10(1 / (0.25^(affected-1) × 0.75^unaffected))（父母均携带者典型模型）；
    若父母一方携带者一方患病，用 0.5/0.5。返回 LOD（强度映射同 AD/XL，读 config pp1_lod【通用 J&B 2016 原值 0.9/1.2/1.5】）。

    ⚠ HL VCEP 闸（v1.6.0/证据层强制）：传 gene 且命中 HL VCEP 覆盖基因（如 USH2A）时，
    自动改用 HL VCEP 官方口径 pp1_lod_hl_ar（受累个体数含先证者、分离数=个体数−1、阈值 0.6/1.2/1.5）；
    无 gene 或未命中则保持通用口径。注（v1.6.1 归因修正 + 2026-10-20 通用/特异分流）：通用版 0.25^(affected-1) 与官网 −1 口径一致，
    数值无"排除先证者"问题；通用版档位偏低的真实原因是阈值错配——通用 0.9/1.2/1.5 是 AD(LOD 底数0.5)阈值，
    套在 AR(底数0.25) LOD 上偏低；HL VCEP 基因必须走官方 0.6/1.2/1.5 阈值，禁用通用阈值。"""
    if gene is not None and _in_hl_vcep(gene):
        return pp1_lod_hl_ar(affected, unaffected)
    pp1 = T.get("pp1_lod", {"supporting": 0.9, "moderate": 1.2, "strong": 1.5})
    if affected is None or affected < 2:
        return None, "患者分离次数不足（AR 需 ≥2 患者）"
    p_aff, p_un = (0.25, 0.75) if parental_both_carrier else (0.5, 0.5)
    lod = math.log10(1 / (p_aff ** (affected - 1) * p_un ** max(unaffected or 0, 0)))
    if lod >= pp1["strong"]:
        band = "PP1_Strong"
    elif lod >= pp1["moderate"]:
        band = "PP1_Moderate"
    elif lod >= pp1["supporting"]:
        band = "PP1_Supporting"
    else:
        band = None
    return band, f"AR 患者={affected} 非患者={unaffected or 0} → LOD={lod:.2f} → {band if band else '不成立'}（通用口径，阈值 {pp1['supporting']}/{pp1['moderate']}/{pp1['strong']}）"


def _in_hl_vcep(gene):
    """HL VCEP（GN005）覆盖基因锚点（非穷举）：命中即 PP1 须走官方口径。来源：ClinGen Hearing Loss EP。
    锚点集以常用遗传性耳聋基因为主，HL 相关基因遇不确定回官方核对，不得因锚点漏列而误用通用口径。"""
    hl = {"USH2A", "GJB2", "MYO15A", "OTOF", "SLC26A4", "CDH23", "MYO7A", "TMPRSS3", "TMC1", "STRC", "LOXHD1", "TRIOBP", "PCDH15", "GJB6", "KCNQ4"}
    return gene.strip().upper() in hl


def _in_cmp_ep(gene):
    """ClinGen Cardiomyopathy EP（GN101）覆盖基因锚点（知识图 gene_vcep_index gn=101 系）：命中即 PP1（显性/XL）须走 CMP-EP 疾病特异档 0.9/1.5/2.1。
    锚点集 = Cardiomyopathy VCEP 覆盖基因（ACTC1/MYBPC3/MYH7/MYL2/MYL3/TNNI3/TNNT2/TPM1）；
    遇不确定回官方核对，不得因锚点漏列而误用通用口径（2026-10-20 通用/特异分流）。"""
    cmp_genes = {"ACTC1", "MYBPC3", "MYH7", "MYL2", "MYL3", "TNNI3", "TNNT2", "TPM1"}
    return gene.strip().upper() in cmp_genes


def pp1_lod_hl_ar(affected, unaffected):
    """HL VCEP（GN005）PP1 AR 官方口径（v1.6.1 修正 off-by-one）：LOD = log10(1/(0.25^(affected-1) × 0.75^unaffected))，
    affected = 受累个体数（含先证者），受累分离数 = affected − 1（官网 v2 明文："do not count probands as a
    segregation；Affected segregations = # affected individuals − 1"）；unaffected 不含携带者父母；
    阈值 0.6/1.2/1.5（4:1/16:1/32:1，HL VCEP v2 Table 2 / General Recommendations）。来源：ClinGen HL EP v2 PMID 30311386。"""
    hlv = T.get("hl_vcep_pp1", {"supporting": 0.6, "moderate": 1.2, "strong": 1.5})
    if affected is None or affected < 2:
        return None, "HL VCEP AR 受累分离数不足（受累个体数含先证者需 ≥2，分离数=个体数−1；仅先证者分离数=0）"
    lod = math.log10(1 / (0.25 ** (affected - 1) * (0.75 ** max(unaffected or 0, 0))))
    if lod >= hlv["strong"]:
        band = "PP1_Strong"
    elif lod >= hlv["moderate"]:
        band = "PP1_Moderate"
    elif lod >= hlv["supporting"]:
        band = "PP1_Supporting"
    else:
        band = None
    return band, f"受累个体数(含先证者)={affected} 受累分离数=个体数−1={affected-1} 非患者={unaffected or 0} → LOD={lod:.2f} → {band if band else '不成立'}（HL VCEP v2 官方口径，阈值 {hlv['supporting']}/{hlv['moderate']}/{hlv['strong']}）"


def _pp1_spec_match(count, spec, gene, mode=None):
    """PP1 VCEP 档位 spec 的确定性判定（内部 helper，供 pp1_vcep_band 递归调用）。
    spec 由子技能路由读取 VCEP-<gene>.md #### PP1 段后按原文档位解析传入，形态（真实还原指南 2026-10-20）：
      分离次数档  {"type": "count", "strong": N, "moderate": M, "supporting": S}
                 → count>=N→Strong; M<=count<N→Moderate; S<=count<M→Supporting
      LOD 档     {"type": "lod", "lod_strong": X, "lod_moderate": Y, "lod_supporting": Z}
                 → count 视为 LOD 值比较
      按遗传方式  {"type": "by_moi", "AR": {…子档位…}, "AD": {…子档位…}} → 按 mode 选分支再判
    返回 (档位, 说明)。gene/mode 用于留痕。"""
    if not isinstance(spec, dict):
        return None, f"PP1 VCEP spec 非法（{gene}，须为 dict），路由解析有误"
    stype = spec.get("type")
    if stype is None:
        return None, f"PP1 VCEP spec 缺 type（{gene}，须为 count/lod/by_moi），路由解析有误"
    if count is None:
        return None, "共分离分离次数/LOD 取不到"
    src = f"VCEP-{gene}.md PP1 段（路由读取，type={stype}, mode={mode or '?'}）"
    if stype == "by_moi":
        branch = spec.get(mode) if mode in ("AR", "AD") else None
        if not isinstance(branch, dict):
            return None, f"PP1 VCEP spec 按遗传方式分档但 mode={mode} 无对应分支（{gene}）"
        return _pp1_spec_match(count, branch, gene, mode)
    if stype == "count":
        strong, moderate, supporting = spec.get("strong"), spec.get("moderate"), spec.get("supporting")
        if strong is None or moderate is None or supporting is None:
            return None, f"PP1 VCEP spec(count) 缺档位（{gene}，须有 strong/moderate/supporting）"
        if count >= strong:
            return "PP1_Strong", f"分离次数/LOD={count} ≥ {strong} → PP1_Strong（{src}）"
        if count >= moderate:
            return "PP1_Moderate", f"分离次数/LOD={count} ≥ {moderate} → PP1_Moderate（{src}）"
        if count >= supporting:
            return "PP1_Supporting", f"分离次数/LOD={count} ≥ {supporting} → PP1_Supporting（{src}）"
        return None, f"分离次数/LOD={count} < supporting={supporting} → PP1 不成立（{src}）"
    if stype == "lod":
        ls, lm, lsup = spec.get("lod_strong"), spec.get("lod_moderate"), spec.get("lod_supporting")
        if ls is None or lm is None or lsup is None:
            return None, f"PP1 VCEP spec(lod) 缺档位（{gene}，须有 lod_strong/lod_moderate/lod_supporting）"
        if count >= ls:
            return "PP1_Strong", f"LOD={count} ≥ {ls} → PP1_Strong（{src}）"
        if count >= lm:
            return "PP1_Moderate", f"LOD={count} ≥ {lm} → PP1_Moderate（{src}）"
        if count >= lsup:
            return "PP1_Supporting", f"LOD={count} ≥ {lsup} → PP1_Supporting（{src}）"
        return None, f"LOD={count} < lod_supporting={lsup} → PP1 不成立（{src}）"
    return None, f"PP1 VCEP spec type 不支持（{gene}，type={stype}）"


def pp1_vcep_band(count, gene, spec, mode=None):
    """PP1 VCEP 路由判定（2026-10-20 新增）：共分离分离次数/LOD 与 VCEP-<gene>.md #### PP1 段原文档位 spec 做确定性比较。
    ⚠ spec 由子技能 ev-pp1 路由读取 VCEP 原文后按原文档位解析传入（不硬编码 124 基因），
    引擎只做数值比较、不做文本解析；count 为"分离次数（meioses/受累亲属数）或 LOD 值"，
    由路由按 spec type 决定传哪种。现有 pp1_lod_adxl / pp1_lod_ar / pp1_lod_hl_ar 保留不动（通用/HL/CMP-EP 回退路径）。"""
    return _pp1_spec_match(count, spec, gene, mode)


# ============ 5. PS4 先证者数 / OR / VCEP → 档位（ev-ps4 通用 + VCEP 路由） ============
# ⚠ 2026-10-20 路由方案：原 PS4_VCEP 手抄表（MYH7/HL/RASopathy/PTEN/CDH1）已撤销（制造官方副本必漂移），
# 基因特异档位一律由 ev-ps4 路由读 clingen-vcep/VCEP-<gene>.md 的 `#### PS4` 段原文（单一权威源），
# 引擎 ps4_vcep_band 只做"数值→档位"确定性映射；ps4_band 保留通用 ≥2/≥6/≥15 分支。

def ps4_vcep_band(value, gene, spec=None, max_band=None):
    """PS4 VCEP 基因特异档位判定（v1.4.0 路由方案）。

    PS4 证据本质（同 PP4）：先查文献/临床数据拿到实际数值（先证者数/表型点数/OR 等），再拿数值
    对照该基因 VCEP 特异规则匹配档位——VCEP 只定义『多少数值→哪档』，数值本身须执行者先查取
    （病例/家系/队列 + 文献 OR），引擎不做取数。

    支持 PS4 的数值型形态（spec["type"] 区分，与 pp1/pp3/pm3/pp4 路由同源）：
      - count 计数型：spec["bands"]={"supporting":[lo,hi),...}，value 为先证者/家系/病例数。
        如 ABCD1、ACVRL1/ENG（4+/2-3/1）、CDH1（≥16/4-15/2-3/1 家系）、F8/F9（≥8/4-7/2-3/1）、
        LDLR（≥10/6-9/2-5）、MYO15A 等；
      - points 点数型：spec["bands"] 同上，value 为表型点数。如 APC（≥16/4-15.5/2-3.5/1-1.5）、
        PTEN/FBN1/DICER1/FOXN1/IL2RG/BRAF/KRAS/HRAS/RASopathy（≥5/≥3/≥1）、AKT3/MTOR 等；
      - lr 型：spec["bands"] 同上，value 为 OR/LR 值（如 ATM/BRCA1/BRCA2 case-control OR）。
    病例对照/条件式（酶活、表型分+条件、OR 须配合 CI 判定等）→ spec["type"]="phenotype"，
    引擎不判数值，返回需执行者按 VCEP 原文核临床/统计条件（含 OR 的 CI 不含 1 判定）。

    参数：
      value: 实际数值（先证者/家系/点数/OR；phenotype 型不传）
      gene:  基因名
      spec:  形态与档位 spec（缺省=None=回退通用 AD/XL ≥2/≥6/≥15，标注通用口径）
      max_band: 封顶档

    返回 (档位, 说明)；数值不足任何档→None；phenotype 型→(None, "需路由读 VCEP 原文核条件")。
    """
    if not spec:
        return "PS4_Supporting" if (value is not None and value >= 2) else None, \
            ("PS4 通用口径（无 VCEP 特异 spec）：AD/XL 先证者 ≥2→Supporting；≥6→Moderate；≥15→Strong"
             if value is not None else "PS4 通用口径：先证者数未取到，不得默认给档")
    typ = spec.get("type", "phenotype")
    if typ == "phenotype":
        return None, f"{gene} VCEP PS4 为病例对照/条件式（{spec.get('note','按原文')}）：需执行者路由读 VCEP-{gene}.md 原文核临床/统计条件（含 OR 与 CI），引擎不判数值"
    bands = spec.get("bands", {})
    if value is None:
        return None, f"{gene} VCEP PS4 数值未取到（{typ}型）：先查文献/临床数据拿数值再匹配，不得默认给档"
    order = [("vs", "PS4_VeryStrong"), ("strong", "PS4_Strong"), ("moderate", "PS4_Moderate"), ("supporting", "PS4_Supporting")]
    for key, band in order:
        if key not in bands:
            continue
        lo, hi = bands[key]
        if lo is not None and value < lo:
            continue
        if hi is not None and value >= hi:
            continue
        if max_band is not None and band != max_band:
            ob = ["PS4_Supporting", "PS4_Moderate", "PS4_Strong", "PS4_VeryStrong"]
            if ob.index(band) > ob.index(max_band):
                return max_band, f"{gene} VCEP PS4（{typ}型）：value={value} 命中 {band} 但封顶 {max_band}"
        return band, f"{gene} VCEP PS4（{typ}型）：value={value} 落 {key} 档 → {band}"
    return None, f"{gene} VCEP PS4（{typ}型）：value={value} 不落任何档位（不足 Supporting 下限）"


def ps4_band(probands, gene=None, ar=False, significant=True):
    """PS4：先证者数 → 档位（通用口径）。⚠ 2026-10-20 路由方案：VCEP 基因的特异档位一律走
      ps4_vcep_band（由 ev-ps4 路由读 clingen-vcep VCEP-<gene>.md 原文），本函数仅通用：
      AD/XL 罕见病例对照无统计意义但 AF 符合 PM2 且有多个相同表型患者 → 随患者数下降：≥2→Supporting，≥6→Moderate，≥15→Strong。
    AR 需 OR>5 且 CI 不含 1（见 ps4_or_ci）。
    P1-3 校准（证据码核对报告 + ACMG Table 3 Note 2）：significant=False（case-control 无统计意义 /
    仅多患者+无对照观察）时，PS4 最多 Moderate，≥15 不升 Strong——Note 2 原文"may be used as
    moderate level of evidence"，通用多先证者数不构成 Strong 前提；Strong 需 case-control 显著
    （significant=True）或 VCEP 基因特异规则。"""
    if probands is None:
        return None, "先证者数取不到"
    # P1-3：无统计显著性时封顶 Moderate（Note 2 语境）
    if probands >= 15:
        if significant:
            return "PS4_Strong", f"通用：先证者 {probands} ≥15 且 case-control 显著 → PS4_Strong"
        return "PS4_Moderate", f"通用：先证者 {probands} ≥15 但 case-control 无统计显著性（Note 2 语境）→ 封顶 PS4_Moderate"
    if probands >= 6:
        return "PS4_Moderate", f"通用：先证者 {probands} ≥6 → PS4_Moderate"
    if probands >= 2:
        return "PS4_Supporting", f"通用：先证者 {probands} ≥2（AF 符合 PM2 时）→ PS4_Supporting"
    return None, f"通用：先证者 {probands} <2，PS4 不成立"


def ps4_or_ci(cases_exposed, cases_control, ctr_exposed, ctr_control):
    """PS4 OR 与 95%CI（AR 必需：OR>5 且 CI 不含 1）。
    输入 2×2：cases_exposed=cases 携带者数，cases_control=cases 未携带；ctr_exposed=对照携带者，ctr_control=对照未携带。
    返回 (OR, CI_low, CI_high)；用 Haldane 校正处理零单元格。"""
    a, b, c, d = cases_exposed, cases_control, ctr_exposed, ctr_control
    # Haldane 零校正
    a2, b2, c2, d2 = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    or_ = (a2 * d2) / (b2 * c2)
    ln_or = math.log(or_)
    se = math.sqrt(1 / a2 + 1 / b2 + 1 / c2 + 1 / d2)
    ci_low = math.exp(ln_or - 1.96 * se)
    ci_high = math.exp(ln_or + 1.96 * se)
    return or_, ci_low, ci_high


# ============ 6. SpliceAI 剪接影响 → 档位（thresholds.spliceai） ============
def spliceai_band(score, version="v2"):
    """SpliceAI 分数 → 剪接影响判定。
    v2（SpliceAI2）：0.1=Supporting(高召回)、0.25=Moderate、0.5=Strong；
    v1：>0.2 判有剪接影响（高召回档）。返回 (影响, 说明)。
    ⚠ 版本绑定（官网核对 Q10）：调用方必须按取数通道显式传 version——取数来自 SpliceAI2 预计算/引擎默认 → v2；
    取数来自初代 SpliceAI（如部分 VCEP 原文刻度 ≤0.1/≤0.2）→ v1。禁止默认 v2 却喂初代分数（[0.1,0.2) 区间方向会误判）。"""
    sa = T["spliceai"]
    if score is None:
        return None, "SpliceAI 分数取不到"
    # D31（2026-10-15）：依据说明从 config 格式化，禁止硬编码字面量（改 config 后逻辑与打印同步）
    if version == "v2":
        v2 = sa["v2_thresholds"]
        if score >= v2["strong"]:
            return "影响(Strong)", f"SpliceAI2 score={score} ≥{v2['strong']} → 强剪接影响"
        if score >= v2["moderate"]:
            return "影响(Moderate)", f"SpliceAI2 score={score} ≥{v2['moderate']} → 中度剪接影响"
        if score >= v2["supporting"]:
            return "影响(Supporting)", f"SpliceAI2 score={score} ≥{v2['supporting']} → 支持剪接影响"
        return "无影响", f"SpliceAI2 score={score} <{v2['supporting']} → 无剪接影响"
    else:  # v1
        if score > sa["v1_threshold"]:
            return "影响", f"SpliceAI v1 score={score} >{sa['v1_threshold']}（高召回档）→ 判有剪接影响"
        return "无影响", f"SpliceAI v1 score={score} ≤{sa['v1_threshold']} → 无剪接影响"


# ============ 7. PS1 / PM5 映射（ev-ps1-pm5：同氨基酸→PS1，异氨基酸→PM5） ============
def ps1_pm5_band(same_aa, known_class, other_p_count=0):
    """PS1/PM5 通用档位（v1.5.0 解耦：通用只做基础判定，计数升级走 pm5_vcep_band 路由）：
      same_aa=True（同密码子同氨基酸，不同核苷酸）→ PS1：known_class=P→PS1(强)；known_class=LP→PS1_Moderate；
      same_aa=False（同一位置不同氨基酸，且该等位已确立 P/LP）→ PM5：
          known_class=LP →PM5_Supporting；known_class=P →PM5_Moderate。
      ⚠ 注意：other_p_count>=2 → PM5_Strong 是 VCEP 基因特异规则（TP53/LDLR/BRAF 等 39 个基因），
        已移出本通用函数，统一走 pm5_vcep_band 路由读取 VCEP 原文。通用基因 PM5 最高 Moderate。
    已知变异分类必须不依赖本证据。"""
    if same_aa:
        if known_class == "P":
            return "PS1", "同氨基酸已知 P → PS1（Strong）"
        if known_class == "LP":
            return "PS1_Moderate", "同氨基酸已知 LP → PS1_Moderate（降级）"
        return None, f"同氨基酸但已知分类={known_class}（非 P/LP），PS1 不成立"
    else:
        if known_class == "P":
            return "PM5_Moderate", "同位置不同氨基酸且已知 P → PM5_Moderate（通用）"
        if known_class == "LP":
            return "PM5_Supporting", "同位置不同氨基酸且已知 LP → PM5_Supporting（通用）"
        return None, f"异氨基酸但已知分类={known_class}，PM5 不成立"


# ============ 8. BS1 AF → 判定（ev-bs1-bs2：AF 大于疾病发病率） ============
def bs1_band(af, prevalence, high_penetrance_early=True):
    """BS1：等位基因频率 > 疾病发病率（且疾病高外显、早发前提，由 LLM/疾病检索判断）。
    返回 (是否成立, 说明)。"""
    if af is None or prevalence is None:
        return None, "AF 或发病率取不到"
    if af > prevalence:
        return "BS1成立", f"AF={af} > 发病率={prevalence}（高外显早发前提={high_penetrance_early}）→ BS1 可考虑"
    return None, f"AF={af} ≤ 发病率={prevalence}，BS1 不成立"


def _bs1_spec_match(af, spec, gene, mode):
    """BS1 VCEP 档位 spec 的确定性判定（内部 helper，供 bs1_vcep_band 递归调用）。
    spec 由子技能路由读取 VCEP-<gene>.md #### BS1 段后按原文档位解析传入，形态：
      单值:      {"strong": X}                        → AF>=X → BS1_Strong
      两段式:    {"strong": X, "supporting": Y}       → AF>=X→Strong; Y<=AF<X→Supporting
      按遗传方式: {"AR": {…}, "AD": {…}}              → 按 mode 选对应分支再判
    返回 (档位, 说明)。gene/mode 用于留痕。"""
    if not isinstance(spec, dict):
        return None, f"BS1 VCEP spec 非法（{gene}，须为 dict），路由解析有误"
    # 形态3：按遗传方式分档（mode 选分支）
    if "AR" in spec and "AD" in spec and isinstance(spec.get("AR"), dict) and isinstance(spec.get("AD"), dict):
        branch = spec.get(mode) if mode in ("AR", "AD") else None
        if branch is None:
            return None, f"BS1 VCEP spec 按遗传方式分档但 mode={mode} 无对应分支（{gene}，AR/AD 缺一不可）"
        return _bs1_spec_match(af, branch, gene, mode)
    # 形态1/2：单值或两段式阈值
    strong = spec.get("strong")
    supporting = spec.get("supporting")
    if strong is None:
        return None, f"BS1 VCEP spec 缺 strong 主阈值（{gene}），路由解析有误"
    if af is None:
        return None, "AF 取不到"
    src = f"VCEP-{gene}.md BS1 段（路由读取，mode={mode or '?'}）"
    if af >= strong:
        return "BS1_Strong", f"AF={af} ≥ strong={strong} → BS1_Strong（{src}）"
    if supporting is not None and af >= supporting:
        return "BS1_Supporting", f"AF={af} ≥ supporting={supporting} 且 <strong={strong} → BS1_Supporting（{src}）"
    return None, f"AF={af} < {'supporting' if supporting is not None else 'strong'}阈值 → BS1 不成立（{src}）"


def bs1_vcep_band(af, gene, mode, spec):
    """BS1 VCEP 路由判定（v1.6.0 新增）：AF 与 VCEP-<gene>.md #### BS1 段原文档位 spec 做确定性比较。
    ⚠ spec 由子技能 ev-bs1-bs2 路由读取 VCEP 原文后按原文档位解析传入（不硬编码 131 基因），
    引擎只做数值比较、不做文本解析。形态见 _bs1_spec_match。现有 bs1_band（通用疾病发病率比较）保留不动。"""
    return _bs1_spec_match(af, spec, gene, mode)


def _ba1_spec_match(af, spec, gene, mode):
    """BA1 VCEP 档位 spec 的确定性判定（内部 helper，供 ba1_vcep_band 递归调用）。
    spec 由子技能路由读取 VCEP-<gene>.md #### BA1 段后按原文档位解析传入，形态：
      单一切点:  {"cutoff": X, "direction": "ge"|"gt"}
                 → AF>=X（ge）或 AF>X（gt）→ BA1_Stand_Alone（BA1 是强良性独立证据，唯一档位）
      按遗传方式: {"AR": {…}, "AD": {…}}              → 按 mode 选对应分支再判
    返回 (档位, 说明)。gene/mode 用于留痕。"""
    if not isinstance(spec, dict):
        return None, f"BA1 VCEP spec 非法（{gene}，须为 dict），路由解析有误"
    # 形态2：按遗传方式分档（mode 选分支）
    if "AR" in spec and "AD" in spec and isinstance(spec.get("AR"), dict) and isinstance(spec.get("AD"), dict):
        branch = spec.get(mode) if mode in ("AR", "AD") else None
        if branch is None:
            return None, f"BA1 VCEP spec 按遗传方式分档但 mode={mode} 无对应分支（{gene}，AR/AD 缺一不可）"
        return _ba1_spec_match(af, branch, gene, mode)
    # 形态1：单一切点
    cutoff = spec.get("cutoff")
    if cutoff is None:
        return None, f"BA1 VCEP spec 缺 cutoff 主阈值（{gene}），路由解析有误"
    direction = spec.get("direction", "ge")
    if af is None:
        return None, "AF 取不到"
    src = f"VCEP-{gene}.md BA1 段（路由读取，mode={mode or '?'}）"
    if direction == "gt":
        if af > cutoff:
            return "BA1_Stand_Alone", f"AF={af} > cutoff={cutoff} → BA1_Stand_Alone（{src}）"
        return None, f"AF={af} ≤ cutoff={cutoff}（direction=gt，须严格 >）→ BA1 不成立（{src}）"
    if af >= cutoff:
        return "BA1_Stand_Alone", f"AF={af} ≥ cutoff={cutoff} → BA1_Stand_Alone（{src}）"
    return None, f"AF={af} < cutoff={cutoff} → BA1 不成立（{src}）"


def ba1_vcep_band(af, gene, mode, spec):
    """BA1 VCEP 路由判定（v1.7.0 新增）：AF 与 VCEP-<gene>.md #### BA1 段原文档位 spec 做确定性比较。
    ⚠ spec 由子技能 ev-bs1-bs2 路由读取 VCEP 原文后按原文档位解析传入（不硬编码 131 基因），
    引擎只做数值比较、不做文本解析。形态见 _ba1_spec_match。现有 bs1_band（通用疾病发病率比较）保留不动。"""
    return _ba1_spec_match(af, spec, gene, mode)


def _bs2_band_match(value, spec, gene, code_prefix="BS2"):
    """BS2 VCEP 档位 spec 的确定性判定（内部 helper，供 bs2_vcep_band / pm5_vcep_band 递归调用）。
    spec 由子技能路由读取 VCEP-<gene>.md #### <code> 段后按原文档位解析传入，形态：
      数值/计数/点数分档: {"type": "band", "bands": {"strong": X, "moderate": Y, "supporting": Z},
                          "direction": "ge"|"gt", "unit": "points"|"count"|"percent"|"known_pathogenic"}
                 → value>=X(ge) 或 value>X(gt) → {code}_Strong；>=Y→Moderate；>=Z→Supporting（从高到低取最高达标档）
      按遗传方式:        {"AR": {…}, "AD": {…}}   → 按 mode 选对应分支再判（BS2 少见，兼容）
    返回 (档位, 说明)。gene 用于留痕。code_prefix 默认 BS2，PM5 复用传 "PM5"。"""
    if not isinstance(spec, dict):
        return None, f"{code_prefix} VCEP spec 非法（{gene}，须为 dict），路由解析有误"
    # 按遗传方式分档（兼容）
    if "AR" in spec and "AD" in spec and isinstance(spec.get("AR"), dict) and isinstance(spec.get("AD"), dict):
        # 需要 mode 参数，此处由外层传入；BS2 段较少见该形态，若出现说明无法单 value 判定
        return None, f"{code_prefix} VCEP spec 按遗传方式分档（{gene}），需 mode 分支解析（当前引擎单值判定不支持，回退通用）"
    bands = spec.get("bands")
    if not isinstance(bands, dict):
        return None, "%s VCEP spec 缺 bands（%s，须为 strong/moderate/supporting 档位表），路由解析有误" % (code_prefix, gene)
    direction = spec.get("direction", "ge")
    if value is None:
        return None, "%s 数值/计数取不到" % code_prefix
    src = f"VCEP-{gene}.md {code_prefix} 段（路由读取）"
    unit = spec.get("unit", "")
    # 从高到低取最高达标档
    for band_name in ("strong", "moderate", "supporting"):
        thr = bands.get(band_name)
        if thr is None:
            continue
        if direction == "gt":
            if value > thr:
                return f"{code_prefix}_{band_name.capitalize()}", f"{unit}={value} > {band_name}={thr} → {code_prefix}_{band_name.capitalize()}（{src}）"
        else:
            if value >= thr:
                return f"{code_prefix}_{band_name.capitalize()}", f"{unit}={value} ≥ {band_name}={thr} → {code_prefix}_{band_name.capitalize()}（{src}）"
    lowest = next((str(bands.get(b)) for b in ("strong", "moderate", "supporting") if bands.get(b) is not None), "?")
    return None, f"{unit}={value} < 最低档阈值={lowest} → {code_prefix} 不成立（{src}）"


def bs2_vcep_band(value, gene, spec):
    """BS2 VCEP 路由判定（v1.7.0 新增）：数值/计数/点数与 VCEP-<gene>.md #### BS2 段原文档位 spec 做确定性比较。
    ⚠ spec 由子技能 ev-bs1-bs2 路由读取 VCEP 原文后按原文档位解析传入（不硬编码基因），
    引擎只做数值比较、不做文本解析。形态见 _bs2_band_match。现有通用 BS2 逻辑（健康成人观察判定）由子技能承担。"""
    return _bs2_band_match(value, spec, gene)


def _pm1_pos_match(aa_pos, spec, gene):
    """PM1 VCEP 位置匹配 spec 的确定性判定（内部 helper，供 pm1_vcep_band 调用）。
    spec 由子技能 ev-pm1 路由读取 VCEP-<gene>.md #### PM1 段后按原文档位解析传入，形态：
      {"type":"region",
       "bands":{
         "strong":  [{"lo":L,"hi":H}, ...] 或 [{"pos":X}, ...],   # 有 Strong 档才给
         "moderate":[...],
         "supporting":[...]},
       "exclude_bands":["moderate"]}   # 可选：某档存在但本基因不含（占位防误判）
    每个元素：{"lo":L,"hi":H} 命中区间 [L,H]；{"pos":X} 命中单点 X（X 即氨基酸位置，含端点）。
    从高到低取最高命中档位。返回 (档位, 说明)。"""
    if not isinstance(spec, dict):
        return None, f"PM1 VCEP spec 非法（{gene}，须为 dict），路由解析有误"
    if aa_pos is None:
        return None, "变异氨基酸位置取不到"
    bands = spec.get("bands")
    if not isinstance(bands, dict):
        return None, "PM1 VCEP spec 缺 bands（%s，须为 strong/moderate/supporting 位置集合）" % gene
    src = f"VCEP-{gene}.md PM1 段（路由读取）"
    # 命中判断 helper
    def hit(items):
        if not isinstance(items, list):
            return False
        for it in items:
            if not isinstance(it, dict):
                continue
            if "pos" in it and it["pos"] == aa_pos:
                return True
            if "lo" in it and "hi" in it and it["lo"] <= aa_pos <= it["hi"]:
                return True
        return False
    for band_name in ("strong", "moderate", "supporting"):
        items = bands.get(band_name)
        if items is None or items == []:
            continue
        if hit(items):
            return f"PM1_{band_name.capitalize()}", f"变异氨基酸位置={aa_pos} 命中 {band_name} 档区域 → PM1_{band_name.capitalize()}（{src}）"
    return None, f"变异氨基酸位置={aa_pos} 未命中任何 PM1 区域 → PM1 不成立（{src}）"


def pm1_vcep_band(aa_pos, gene, spec):
    """PM1 VCEP 路由判定（新增）：变异氨基酸位置与 VCEP-<gene>.md #### PM1 段原文档位位置集合做确定性匹配。
    ⚠ spec 由子技能 ev-pm1 路由读取 VCEP 原文后按原文档位解析传入（不硬编码基因），
    引擎只做位置匹配、不做文本解析。形态见 _pm1_pos_match。适用性前提（PM2 稀有/无良性变异/不与 PM5 合用）由子技能协议承担。"""
    return _pm1_pos_match(aa_pos, spec, gene)


def pm5_vcep_band(n_known, gene, spec):
    """PM5 VCEP 路由判定（新增）：同密码子已知致病错义变异计数与 VCEP-<gene>.md #### PM5 段原文档位档位做确定性比较。
    ⚠ spec 由子技能 ev-ps1-pm5 路由读取 VCEP 原文后按原文档位解析传入（不硬编码基因），
    引擎只做计数比较、不做文本解析。spec 形态与 _bs2_band_match 相同：
      {"type":"band","bands":{"strong":2,"moderate":1,"supporting":1},"unit":"known_pathogenic"}
    从高到低取最高达标档。通用 ps1_pm5_band(same_aa, known_class, other_p_count) 保留，用于无 VCEP PM5 档位的基因。"""
    return _bs2_band_match(n_known, spec, gene, code_prefix="PM5")


def pm4_vcep_band(n_aa, gene, spec):
    """PM4 VCEP 路由判定（v1.2.0 新增）：框内插入/缺失的氨基酸数与 VCEP-<gene>.md #### PM4 段原文档位档位做确定性比较。
    ⚠ spec 由子技能 ev-pm4 路由读取 VCEP 原文后按原文档位解析传入（不硬编码基因），
    引擎只做 AA 数比较、不做文本解析。spec 形态与 _bs2_band_match 相同（AA 数≥阈值为达标）：
      {"type":"band","bands":{"moderate":2,"supporting":1},"unit":"amino_acid"}
    从高到低取最高达标档（≥2 AA→Moderate、≥1 AA→Supporting）。前置条件（非重复区/进化保守/PhyloP/终止密码子丧失）
    由执行者核验，引擎只做 AA 数档位比较；通用 PM4 判定（小于 1 个外显子）保留用于无 VCEP PM4 AA 切点的基因。"""
    return _bs2_band_match(n_aa, spec, gene, code_prefix="PM4")


def pm2_by_gene(af, gene, mode="AD"):
    """PM2 便捷入口：按基因查特异性阈值（config af_genetic，若无则回退通用 af_lab_generic）。
    注：VCEP 官方特异规则（CAPN3/MYH7 等复合形态）不走本函数——由 ev-pm2 子技能路由读
    clingen-vcep/VCEP-<gene>.md 原文、现场解析主阈值后调 pm2_band 传入（路由方案 2026-10-20）。
    本函数只处理『本实验室/疾病级手抄』af_genetic 扁平层 + 通用回退。"""
    pm2 = T.get("pm2", {})
    spec = (pm2.get("af_genetic") or {}).get(gene.upper()) if gene else None
    if spec is not None:
        return pm2_band(af, mode=mode, gene_specific=spec)
    return pm2_band(af, mode=mode, gene_specific=None)


# ============ 8.5 PP3 VCEP 路由判定（ev-pp3-bp4：计算机预测有害，基因特异阈值） ============
def pp3_vcep_band(scores, gene, spec, variant_type="missense", exclusions=None):
    """PP3 VCEP 路由判定（2026-10-20 新增）：变异预测分数 与 VCEP-<gene>.md #### PP3 段原文档位 spec 做确定性比较。
    ⚠ spec 由子技能 ev-pp3-bp4 路由读取 VCEP 原文后按原文档位解析传入（不硬编码 127 基因），
    引擎只做"分数 vs 阈值"的确定性比较；**变异类型分流（错义/同义/内含子/框内）、功能域位置、
    前置排除（RNA 实证剪接 / canonical splice / 机制不符）等语义判据由路由/执行者按原文判断后
    传入 variant_type / exclusions，引擎不臆断**。不成立返回 (None, 原因)。

    参数：
      scores        dict：{工具: 分数}，如 {"revel": 0.81, "cadd": 26.0, "spliceai": 0.3,
                        "bayesdel": 0.35, "alphamissense": 0.85}。取不到的键留空即可。
      gene          基因名（仅留痕）。
      spec          VCEP PP3 段解析出的规则（见下各 type）。
      variant_type  变异类型："missense" / "synonymous" / "intronic" / "inframe" / "other"。
      exclusions    dict：前置排除已由执行者按原文确认，如 {"rna_proven_splice": False,
                    "canonical_splice": False, "mechanism_mismatch": False}；True 表示命中排除 → 不成立。

    spec 形态（真实还原指南 2026-10-20，对应 VCEP 原文）：
      单工具阈值  {"type": "tool_threshold", "tool": "revel", "ge": 0.7}
                 → scores[tool] >= ge → PP3_Supporting（封顶 Supporting，VCEP 只给该档）
      或逻辑     {"type": "revel_or_spliceai", "revel_ge": 0.644, "spliceai_ge": 0.2}
                 → revel>=revel_ge 或 spliceai>=spliceai_ge → PP3_Supporting
      且逻辑     {"type": "revel_and_cadd", "revel_ge": 0.644, "cadd_ge": 25.3}
                 → 两工具都达标 → PP3_Supporting
      n/m 多工具 {"type": "n_of_m", "tools": {"revel":0.644,"alphamissense":0.792,"cadd":25.3}, "n": 2}
                 → ≥n 个工具达标 → PP3_Supporting
      多档       {"type": "multi_band", "bands": {"strong":{"revel_ge":0.932},
                 "moderate":{"revel_ge":0.773}, "supporting":{"revel_ge":0.644}}}
                 → 按档位逐级比较（VCEP 给了多档才用，档位内逻辑同 tool_threshold）
      spliceai 剪接型 {"type": "spliceai_only", "ge": 0.2, "variant_types": ["synonymous","intronic"]}
                 → 仅当 variant_type 在 variant_types 内且 spliceai>=ge → PP3_Supporting
      bayesdel 功能域型 {"type": "bayesdel_domain", "ge": 0.28, "domains": [...]}
                 → bayesdel>=ge（功能域命中由执行者按原文判）→ PP3_Supporting
      maxent 剪接型 {"type": "revel_or_maxent", "revel_ge": 0.7}
                 → revel>=revel_ge（MaxEnt 剪接影响由执行者按原文判）→ PP3_Supporting
      引用式/无数值 {"type": "reference_only", "note": "..."} → 回退通用表（由子技能处理），引擎返回 None
    """
    # 前置排除（执行者按原文确认）
    if exclusions:
        for k, v in exclusions.items():
            if v:
                return None, f"{gene} VCEP PP3：前置排除命中（{k}），PP3 不成立（{k} 为 True，按原文）"
    if not isinstance(spec, dict):
        return None, f"PP3 VCEP spec 非法（{gene}，须为 dict），路由解析有误"
    stype = spec.get("type")
    if stype is None:
        return None, f"PP3 VCEP spec 缺 type（{gene}，须为 tool_threshold/revel_or_spliceai/...），路由解析有误"
    src = f"VCEP-{gene}.md PP3 段（路由读取，type={stype}, variant={variant_type}）"

    def _ge(tool, thr):
        v = scores.get(tool)
        if v is None:
            return False, f"{tool} 取不到"
        return v >= thr, f"{tool}={v} {'≥' if v >= thr else '<'}{thr}"

    if stype == "tool_threshold":
        tool, thr = spec.get("tool"), spec.get("ge")
        if tool is None or thr is None:
            return None, f"PP3 VCEP spec(tool_threshold) 缺 tool/ge（{gene}）"
        ok, detail = _ge(tool, thr)
        if ok:
            return "PP3_Supporting", f"{gene} VCEP PP3：{detail} → PP3_Supporting（{src}，封顶 Supporting）"
        return None, f"{gene} VCEP PP3：{detail} → PP3 不成立（{src}）"

    if stype == "revel_or_spliceai":
        rge, sge = spec.get("revel_ge"), spec.get("spliceai_ge")
        ok_r, d_r = _ge("revel", rge)
        ok_s, d_s = _ge("spliceai", sge)
        if ok_r or ok_s:
            win = d_r if ok_r else d_s
            return "PP3_Supporting", f"{gene} VCEP PP3：{win} → PP3_Supporting（{src}，REVEL 或 SpliceAI）"
        return None, f"{gene} VCEP PP3：{d_r} 且 {d_s} → PP3 不成立（{src}，REVEL 与 SpliceAI 均未达）"

    if stype == "revel_and_cadd":
        rge, cge = spec.get("revel_ge"), spec.get("cadd_ge")
        ok_r, d_r = _ge("revel", rge)
        ok_c, d_c = _ge("cadd", cge)
        if ok_r and ok_c:
            return "PP3_Supporting", f"{gene} VCEP PP3：{d_r} 且 {d_c} → PP3_Supporting（{src}，双工具 agree）"
        return None, f"{gene} VCEP PP3：{d_r}、{d_c} → 需双工具均达标，PP3 不成立（{src}）"

    if stype == "n_of_m":
        tools, n = spec.get("tools"), spec.get("n", 2)
        if not isinstance(tools, dict) or not tools:
            return None, f"PP3 VCEP spec(n_of_m) 缺 tools（{gene}）"
        met = []
        for tool, thr in tools.items():
            ok, d = _ge(tool, thr)
            if ok:
                met.append(d)
        if len(met) >= n:
            return "PP3_Supporting", f"{gene} VCEP PP3：{n}/{len(tools)} 工具达标（{'; '.join(met)}）→ PP3_Supporting（{src}）"
        return None, f"{gene} VCEP PP3：仅 {len(met)}/{len(tools)} 工具达标（{'; '.join(met) or '无'}），需 ≥{n} → PP3 不成立（{src}）"

    if stype == "multi_band":
        bands = spec.get("bands") or {}
        order = [("strong", "PP3_Strong"), ("moderate", "PP3_Moderate"), ("supporting", "PP3_Supporting")]
        for key, label in order:
            b = bands.get(key)
            if not isinstance(b, dict):
                continue
            tool, thr = b.get("tool", "revel"), b.get("ge") or b.get("revel_ge")
            if thr is None:
                continue
            ok, d = _ge(tool, thr)
            if ok:
                return label, f"{gene} VCEP PP3：{d} → {label}（{src}）"
        return None, f"{gene} VCEP PP3：未达任何档位阈值 → PP3 不成立（{src}）"

    if stype == "spliceai_only":
        ge = spec.get("ge")
        allowed = spec.get("variant_types") or ["synonymous", "intronic"]
        if variant_type not in allowed:
            return None, f"{gene} VCEP PP3：此 spec 仅适用于 {allowed} 变异，当前为 {variant_type} → PP3 不适用（{src}）"
        ok, d = _ge("spliceai", ge)
        if ok:
            return "PP3_Supporting", f"{gene} VCEP PP3：{d} → PP3_Supporting（{src}）"
        return None, f"{gene} VCEP PP3：{d} → PP3 不成立（{src}）"

    if stype == "bayesdel_domain":
        ge = spec.get("ge")
        ok, d = _ge("bayesdel", ge)
        if ok:
            return "PP3_Supporting", f"{gene} VCEP PP3：{d}（功能域命中由执行者按原文核对）→ PP3_Supporting（{src}）"
        return None, f"{gene} VCEP PP3：{d} → PP3 不成立（{src}）"

    if stype == "revel_or_maxent":
        rge = spec.get("revel_ge")
        ok, d = _ge("revel", rge)
        if ok:
            return "PP3_Supporting", f"{gene} VCEP PP3：{d} → PP3_Supporting（{src}，REVEL 达标；MaxEnt 剪接侧由执行者按原文判）"
        return None, f"{gene} VCEP PP3：{d}（MaxEnt 剪接侧由执行者按原文判）→ PP3 不成立（{src}）"

    if stype == "reference_only":
        return None, f"{gene} VCEP PP3：引用式/无数值规则（{spec.get('note','')}），引擎不做数值判定，回退通用 REVEL 表（由子技能处理）"

    return None, f"PP3 VCEP spec type 不支持（{gene}，type={stype}）"


# ============ 8. BP4 → 良性 Supporting/Moderate/Strong（VCEP 路由；BP4 治理 2026-10-20） ============
def bp4_vcep_band(scores, gene, spec, variant_type="missense", exclusions=None):
    """BP4 VCEP 路由判定（2026-10-20 BP4 特异基因治理新增）：变异计算证据 与 VCEP-<gene>.md #### BP4 段
    原文档位 spec 做确定性比较（良性侧）。
    ⚠ spec 由子技能 ev-pp3-bp4 路由读取 VCEP 原文后按原文档位解析传入（不硬编码 124 基因），
    引擎只做"分数 vs 阈值"的确定性比较；**变异类型分派（错义/同义/内含子/框内）、功能域位置、
    前置排除（canonical splice / 机制不符 / VCEP 明文某类型 NA）等语义判据由路由/执行者按原文判断后
    传入 variant_type / exclusions / spec，引擎不臆断**。不成立返回 (None, 原因)。

    BP4 与 PP3 的本质差异：BP4 是**良性侧**，且规则核心是"**按变异类型分派**"——同一基因的
    missense / synonymous / intronic 往往各自走不同工具与切点，某类型可能明文 not applicable。
    因此 spec 顶层按 variant_type 分派，每分支是独立的档位结构。

    参数：
      scores        dict：{工具: 分数}，如 {"revel": 0.1, "cadd": 15.0, "spliceai": 0.05,
                        "bayesdel": -0.02, "maxentscan": 4.0}。取不到的键留空即可。
      gene          基因名（仅留痕）。
      spec          VCEP BP4 段解析出的规则（见下各 type）。
      variant_type  变异类型："missense" / "synonymous" / "intronic" / "inframe" / "indel" / "other"。
      exclusions    dict：前置排除已由执行者按原文确认，如 {"canonical_splice": False,
                    "mechanism_mismatch": False, "na_branch": False}；True 表示命中排除 → 不成立。

    spec 形态（真实还原指南 2026-10-20，对应 VCEP 原文 BP4 段；绝大多数基因仅 Supporting 档）：
      按类型分派+数值   {"type": "by_type", "bands": {"supporting": {"by_type": {
                          "missense": {"tool":"revel","le":0.15,"spliceai_le":0.1},
                          "synonymous": {"tool":"spliceai","le":0.1},
                          "intronic": {"tool":"spliceai","le":0.1},
                          "default": "NA"}}}}
                        → 按 variant_type 选分支：分支 dict 含 tool+le（单工具≤）或 spliceai_le 排除；
                          "NA" 字符串 → 该类型 BP4 不成立（VCEP 明文 NA）；分支缺失 → 不成立。
      多档（VCEP 给了 Moderate/Supporting）：
        {"type": "by_type", "bands": {"moderate": {"by_type": {...}}, "supporting": {"by_type": {...}}}}
                        → 从最高档往下逐档比较，命中即返回该档。
      引用式/无数值     {"type": "reference_only", "note": "..."} → 回退通用 REVEL BP4 表（由子技能处理），引擎返回 None

    分支 dict 支持字段：
      tool / le      主数值工具及上界（分数 ≤ le 才成立；如 revel≤0.15）。多工具用 and_tools: {tool: le}。
      and_tools      需同时满足的其它工具上界，如 {"spliceai": 0.1, "cadd": 20}（全部 ≤）。
      spliceai_le    需满足 SpliceAI ≤ 该值（无剪接效应排除；多数 VCEP BP4 用它）。
      require_absent 需满足某工具为"无影响"（剪接型），如 {"maxentscan": None} → 执行者判 MaxEnt 无剪接影响。
    """
    # 前置排除（执行者按原文确认）
    if exclusions:
        for k, v in exclusions.items():
            if v:
                return None, f"{gene} VCEP BP4：前置排除命中（{k}），BP4 不成立（{k} 为 True，按原文）"
    if not isinstance(spec, dict):
        return None, f"BP4 VCEP spec 非法（{gene}，须为 dict），路由解析有误"
    stype = spec.get("type")
    if stype is None:
        return None, f"BP4 VCEP spec 缺 type（{gene}，须为 by_type/reference_only），路由解析有误"
    src = f"VCEP-{gene}.md BP4 段（路由读取，type={stype}, variant={variant_type}）"

    def _le(tool, thr):
        v = scores.get(tool)
        if v is None:
            return False, f"{tool} 取不到"
        return v <= thr, f"{tool}={v} {'≤' if v <= thr else '>'}{thr}"

    def _eval_branch(br):
        """判定单分支（单档）是否成立。br 为分支 dict 或 "NA" 字符串。"""
        if isinstance(br, str):
            if br == "NA":
                return False, "该变异类型 VCEP 明文 BP4 not applicable（NA）"
            return False, f"分支无效（{br}）"
        if not isinstance(br, dict):
            return False, f"分支结构非法（{type(br).__name__}）"
        # 主工具 tool/le
        tool, le = br.get("tool"), br.get("le")
        if tool and le is not None:
            ok, d = _le(tool, le)
            if not ok:
                return False, d
            parts = [d]
        else:
            parts = []
        # 且逻辑 and_tools
        for at, ale in (br.get("and_tools") or {}).items():
            ok, d = _le(at, ale)
            if not ok:
                return False, d
            parts.append(d)
        # SpliceAI 排除
        if br.get("spliceai_le") is not None:
            ok, d = _le("spliceai", br["spliceai_le"])
            if not ok:
                return False, d
            parts.append(d)
        # require_absent（剪接型：执行者判无影响）
        for ra in (br.get("require_absent") or {}):
            if scores.get(ra) is not None and scores[ra] > 0:
                return False, f"{ra} 提示有剪接/功能影响（{scores[ra]}>0），BP4 不成立"
        if parts:
            return True, " 且 ".join(parts)
        return True, "（无数值条件，按原文适用）"

    if stype == "by_type":
        bands = spec.get("bands")
        if not isinstance(bands, dict):
            return None, f"BP4 VCEP spec(by_type) 缺 bands（{gene}）"
        # 档位优先级：VeryStrong > Strong > Moderate > Supporting（VCEP 给了几档按序）
        order = ["very_strong", "strong", "moderate", "supporting"]
        for b in order:
            if b not in bands:
                continue
            btype = bands[b].get("by_type") if isinstance(bands[b], dict) else None
            if not isinstance(btype, dict):
                continue
            # 按 variant_type 选分支；带 default 兜底
            br = btype.get(variant_type)
            if br is None:
                br = btype.get("default")
            if br is None:
                continue  # 该档不含此类型 → 试下一档（实际同档内通常只命中一支）
            ok, d = _eval_branch(br)
            if ok:
                band_label = {"very_strong": "VeryStrong", "strong": "Strong",
                              "moderate": "Moderate", "supporting": "Supporting"}[b]
                return f"BP4_{band_label}", f"{gene} VCEP BP4：{d} → BP4_{band_label}（{src}）"
        # 所有档都不成立：区分"该类型NA" vs "数值不达标"
        return None, f"{gene} VCEP BP4：{variant_type} 型在各档均不成立（数值未达切点或该类型 NA）（{src}）"

    if stype == "reference_only":
        return None, f"{gene} VCEP BP4：引用式/无数值规则（{spec.get('note','')}），引擎不做数值判定，回退通用 REVEL BP4 表（由子技能处理）"

    return None, f"BP4 VCEP spec type 不支持（{gene}，type={stype}）"


# ============ 9. PS3/BS3 → 功能实验档位（VCEP 路由；PS3/BS3 治理 2026-10-20） ============
def ps3_vcep_band(experiments, gene, spec=None, max_band=None, benign=False):
    """PS3（功能受损）→ 档位 或 BS3（功能无损伤）→ 档位（VCEP 路由判定，2026-10-20 新增）。

    PS3/BS3 的证据本质：**功能实验类型 + 判据 → 档位**（语义判定，非纯数值）。
    每基因的 VCEP 原文定义了可用的功能实验类型（RNA 剪接 / 酶活% / 电生理 / Kato 分档 /
    寡聚化 / GTPase / 免疫荧光 等，各不相同，无法穷举）与各档位的判据。
    引擎不硬编码基因，spec 由子技能路由读 VCEP-<gene>.md 的 #### PS3 / #### BS3 段解析传入。

    参数：
      experiments  dict：执行者按 VCEP 原文核验后填写的实验结果，形如
                   {"rna_out_of_frame": True, "rna_in_frame": False, "enzyme_activity_pct": 3.5,
                    "kato": "non-functional", "lof_majority": True, "splicing_abnormal": True}
                   —— 数值型判据给数值（如 enzyme_activity_pct=3.5），语义型判据给布尔/枚举。
      gene         基因名（仅留痕）。
      spec         VCEP PS3/BS3 段解析出的规则（见下各 type）。
      max_band     封顶档（VCEP 只定义到某档时）。
      benign       True 判定 BS3（良性侧，档位前缀 BP… 用 BS3）；False 判定 PS3（致病侧）。

    spec 形态（真实还原指南 2026-10-20，对应 VCEP 原文 PS3/BS3 段）：
      bands + 每档判据  {"type":"experiment","bands":{"strong":{判据dict},"moderate":{判据dict},
                         "supporting":{判据dict}}}
                        判据 dict 键为 experiments 的键，值为期望：
                          - 数值型：{"op":"le","v":5}（≤5）或 {"op":"lt","v":5} / {"op":"ge","v":5}
                          - 布尔型：True / False
                          - 枚举型："non-functional" 等
                        某档判据全满足 → 返回该档。
     引用式/无数值     {"type":"reference_only","note":"..."} → 回退通用 PS3/BS3（由子技能处理），引擎返回 None

    返回 (档位, 说明)。档位前缀：benign=False 用 "PS3_"，benign=True 用 "BS3_"。
    任一判据键在 experiments 中缺失（未核验）→ 不成立并提示，不得默认。
    """
    prefix = "BS3" if benign else "PS3"
    if not isinstance(spec, dict):
        return None, f"{prefix} VCEP spec 非法（{gene}，须为 dict），路由解析有误"
    stype = spec.get("type")
    if stype is None:
        return None, f"{prefix} VCEP spec 缺 type（{gene}，须为 experiment/reference_only），路由解析有误"
    src = f"VCEP-{gene}.md {prefix} 段（路由读取，type={stype}）"
    if stype == "reference_only":
        return None, f"{gene} VCEP {prefix}：引用式/无数值规则（{spec.get('note','')}），引擎不做判定，回退通用 {prefix}（由子技能处理）"
    if stype != "experiment":
        return None, f"{prefix} VCEP spec type 不支持（{gene}，type={stype}）"
    bands = spec.get("bands")
    if not isinstance(bands, dict):
        return None, f"{prefix} VCEP spec(experiment) 缺 bands（{gene}）"

    def _check(cond, exp):
        """检查单条判据。cond 为 spec 判据；exp 为 experiments 中该键的值。返回 (满足?, 说明)。"""
        if isinstance(cond, dict):
            op = cond.get("op")
            v = cond.get("v")
            if exp is None:
                return False, "该实验判据未核验（experiments 缺键）"
            if op in ("le", "lt", "ge", "gt"):
                if not isinstance(exp, (int, float)):
                    return False, f"判据{op}{v}需数值，但 experiments 给 {type(exp).__name__}"
                ok = {"le": exp <= v, "lt": exp < v, "ge": exp >= v, "gt": exp > v}[op]
                sym = {"le": "≤", "lt": "<", "ge": "≥", "gt": ">"}[op]
                return ok, f"数值={exp} {sym}{v}"
            # 布尔型判据
            if isinstance(cond, dict) and op is None:
                expect = cond.get("eq")
                if expect is None:
                    expect = True
                ok = (exp == expect)
                return ok, f"={exp}" + ("（达标）" if ok else "（未达标）")
        # 枚举/布尔直值
        return (exp == cond), f"={exp}" + ("（达标）" if exp == cond else "（未达标）")

    order = [("very_strong", f"{prefix}_VeryStrong"), ("strong", f"{prefix}_Strong"),
             ("moderate", f"{prefix}_Moderate"), ("supporting", f"{prefix}_Supporting")]
    for key, band in order:
        if key not in bands:
            continue
        conds = bands[key]
        if not isinstance(conds, dict):
            continue
        # 某档可能多条判据需全部满足（AND）；原文 OR 由路由拆成多档/多 spec 或标记 note
        all_ok = True
        details = []
        missing = []
        for k, c in conds.items():
            if k not in experiments:
                missing.append(k)
                all_ok = False
                continue
            ok, d = _check(c, experiments[k])
            details.append(f"{k}:{d}")
            if not ok:
                all_ok = False
        if missing:
            # 有判据未核验 → 该档跳过，继续尝试下一档（低档可能只需已核验的判据）
            continue
        if all_ok:
            if max_band is not None and band != max_band:
                ob = [f"{prefix}_Supporting", f"{prefix}_Moderate", f"{prefix}_Strong", f"{prefix}_VeryStrong"]
                if ob.index(band) > ob.index(max_band):
                    return max_band, f"{gene} VCEP {prefix}：{key} 判据满足但封顶 {max_band}（{src}）"
            return band, f"{gene} VCEP {prefix}：{key} 档判据全部满足（{'；'.join(details)}）→ {band}（{src}）"
    # 各档均不满足
    return None, f"{gene} VCEP {prefix}：各档判据均不满足（或实验判据未核验/未达标）（{src}）"


# ============ CLI 入口（可选，供手动单测） ============
if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        fn = sys.argv[1]
        args = sys.argv[2:]
        funcs = {
            "revel_band": (revel_band, [float]),
            "pm2_band": (pm2_band, [float, str, float]),
            "pm2_by_gene": (pm2_by_gene, [float, str, str]),
            "ps4_band": (ps4_band, [int, str]),
            "pp1_lod_adxl": (pp1_lod_adxl, [int, str]),
            "pp1_lod_ar": (pp1_lod_ar, [int, int, str, str]),
            "pp1_lod_hl_ar": (pp1_lod_hl_ar, [int, int]),
            "spliceai_band": (spliceai_band, [float, str]),
            "bs1_band": (bs1_band, [float, float]),
            "bs1_vcep_band": (bs1_vcep_band, [float, str, str, dict]),
            "ba1_vcep_band": (ba1_vcep_band, [float, str, str, dict]),
            "bs2_vcep_band": (bs2_vcep_band, [float, str, dict]),
            "pm1_vcep_band": (pm1_vcep_band, [int, str, dict]),
            "pm5_vcep_band": (pm5_vcep_band, [int, str, dict]),
            "pm4_vcep_band": (pm4_vcep_band, [int, str, dict]),
            "pp1_vcep_band": (pp1_vcep_band, [float, str, dict, str]),
            "pp3_vcep_band": (pp3_vcep_band, [dict, str, dict, str]),
            "pm3_vcep_band": (pm3_vcep_band, [dict, str, dict, str]),
            "pp4_vcep_band": (pp4_vcep_band, [float, str, dict, str]),
            "ps4_vcep_band": (ps4_vcep_band, [float, str, dict, str]),
            "bp4_vcep_band": (bp4_vcep_band, [dict, str, dict, str]),
            "ps3_vcep_band": (ps3_vcep_band, [dict, str, dict, str]),
        }
        if fn in funcs:
            f, conv = funcs[fn]
            # dict 参数用 json.loads 解析；list 参数（如 pm3 的 examples）同理；其余类型直接转换
            def _conv(t):
                if t is dict:
                    return lambda a: json.loads(a) if a != "-" else None
                if t is list:
                    return lambda a: json.loads(a) if a != "-" else None
                return t
            # 可选参数（gene_specific/mode）不足时以 None 填充
            vals = [_conv(c)(a) if i < len(args) and a != "-" else None
                    for i, (c, a) in enumerate(zip(conv, args))]
            print(f(*vals))
        else:
            print("用法: python acmg_evidence.py 函数名 参数...")
    else:
        # 自检样例
        for r in [0.972, 0.841, 0.955, 0.91, 0.05, 0.5]:
            print(revel_band(r))
        print(pm2_band(0.00005, "AD"))
        print(pm2_band(0.0008, "AR"))
        print(pm3_points([{"type": "A", "n": 1}]))
        print(pm3_points([{"type": "hom", "n": 2}]))
        print(pm3_points([{"type": "B_P", "n": 4}]))
        print(pp1_lod_adxl(4))
        print(pp1_lod_ar(3, 0))
        print(pp1_lod_hl_ar(3, 0))
        print(pp1_lod_ar(3, 0, True, "USH2A"))
        print(ps4_band(2, "MYH7"))
        print(ps4_band(16, None))
        print(spliceai_band(0.15, "v2"))
        print(spliceai_band(0.5, "v1"))
        print(ps1_pm5_band(True, "P"))
        print(ps1_pm5_band(False, "P", 2))
        print(bs1_band(0.02, 0.002))
