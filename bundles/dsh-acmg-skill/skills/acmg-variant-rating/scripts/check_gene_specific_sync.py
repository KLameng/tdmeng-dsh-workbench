# -*- coding: utf-8 -*-
"""
gene_specific_rules.json 一致性校验（第 0 步纯迁移守卫）
职责：把 config/gene_specific_rules.json（权威数据层）与「现有散落数据源」
     （thresholds.json 的 af_genetic / pp1_lod_cmp_ep / hl_vcep_pp1，
       ev-bs1-bs2 / ev-pp2 / ev-pvs1 SKILL 里的手抄特异表）
     逐值核对，确保第 0 步迁移【行为零变化、无漂移】。

用法：python scripts/check_gene_specific_sync.py
  退出码 0 = 全部一致（纯迁移成功，可安全进入后续全量提取）；
  退出码 1 = 存在不一致（迁移有误或源已变，先修再进下一步）。

设计：本脚本是『注册表作为单一权威源』的看门人——第 0 步校验源与注册表一致；
后续每码全量提取后，本脚本更新为『校验注册表 vs clingen-vcep VCEP 原文』。
本步只做迁移核对，不改任何引擎读取逻辑（引擎仍读原位置）。
"""
import os, re, json, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config")
REG = os.path.join(CFG, "gene_specific_rules.json")
THR = os.path.join(CFG, "thresholds.json")
SKILLS = os.path.join(ROOT, "ev-*")

def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def normalize(v):
    """归一化比较：字符串去空白，数值转 float"""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return float(v)
    return v

def check_pm2(reg, thr):
    """PM2 af_genetic：注册表 vs thresholds.json 逐基因核对"""
    errs = []
    reg_pm2 = reg.get("pm2", {}).get("af_genetic", {})
    src_pm2 = thr.get("pm2", {}).get("af_genetic", {})
    # 只核对纯基因键（剔除 note/source/version 等元键）
    reg_genes = {k: v for k, v in reg_pm2.items() if isinstance(v, (int, float))}
    src_genes = {k: v for k, v in src_pm2.items() if isinstance(v, (int, float))}
    if set(reg_genes) != set(src_genes):
        errs.append(f"PM2 基因集合不一致：注册表={sorted(reg_genes)} vs thresholds={sorted(src_genes)}")
    for g in sorted(set(reg_genes) & set(src_genes)):
        if normalize(reg_genes[g]) != normalize(src_genes[g]):
            errs.append(f"PM2 {g} 阈值不一致：注册表={reg_genes[g]} vs thresholds={src_genes[g]}")
    return errs

def check_pp1(reg, thr):
    """PP1 CMP-EP / HL 档：注册表 vs thresholds.json 核对"""
    errs = []
    for block in ("cmp_ep", "hl_vcep"):
        r = reg.get("pp1", {}).get(block, {})
        # 映射到 thresholds.json 对应键
        thr_key = {"cmp_ep": "pp1_lod_cmp_ep", "hl_vcep": "hl_vcep_pp1"}[block]
        t = thr.get(thr_key, {})
        for k in ("supporting", "moderate", "strong"):
            if k in r and k in t:
                if normalize(r[k]) != normalize(t[k]):
                    errs.append(f"PP1 {block}.{k} 不一致：注册表={r[k]} vs thresholds.{thr_key}={t[k]}")
            elif k in r or k in t:
                errs.append(f"PP1 {block}.{k} 键存在性不一致：注册表有={k in r}, thresholds.{thr_key}有={k in t}")
    return errs

def check_bs1(reg):
    """BS1 表：注册表 vs ev-bs1-bs2 SKILL 手抄表（v1.6.0 路由收缩后，仅核对 GJB6 兜底）"""
    errs = []
    table = reg.get("bs1", {}).get("table", [])
    if not table:
        return ["BS1 注册表缺 table（应为无 VCEP 基因兜底表）"]
    # 路由收缩后：仅无 VCEP 文件基因兜底，目前唯一 GJB6（HL-AR 两档）
    expected = {
        "GJB6": {"mode": "AR", "strong": 0.003, "supporting": 0.0007},
    }
    # 注册表映射 gene → (mode, strong, supporting)
    reg_map = {}
    for row in table:
        g = row.get("gene", "")
        if g:
            reg_map[g] = (row.get("mode"), row.get("strong"), row.get("supporting"))
    for g, exp in expected.items():
        if g not in reg_map:
            errs.append(f"BS1 缺失 {g} 兜底（注册表无此项）")
            continue
        rm, rs, rsup = reg_map[g]
        if rm != exp["mode"]:
            errs.append(f"BS1 {g} 遗传方式不一致：注册表={rm} vs SKILL={exp['mode']}")
        if normalize(rs) != normalize(exp["strong"]):
            errs.append(f"BS1 {g} strong 阈值不一致：注册表={rs} vs SKILL={exp['strong']}")
        if normalize(rsup) != normalize(exp["supporting"]):
            errs.append(f"BS1 {g} supporting 阈值不一致：注册表={rsup} vs SKILL={exp['supporting']}")
    # 防复发：注册表不得再出现有 VCEP 文件的基因兜底（有 VCEP 基因走 VCEP 路由，不入本表）
    vcep_gene_markers = ("RASopathy", "CDH1", "PTEN", "Cardiomyopathy", "PAH", "Hearing loss", "GJB2")
    for g in reg_map:
        if any(mk in g for mk in vcep_gene_markers):
            errs.append(f"BS1 注册表残留有 VCEP 文件的疾病类/基因兜底项 {g}（应走 VCEP 路由）")
    return errs

def check_pp3(reg):
    """PP3 防残留（v1.7.0 路由方案）：PP3 特异规则由 ev-pp3-bp4 路由读 clingen-vcep VCEP-<gene>.md 原文，
    不落注册表制造官方副本。校验注册表不得残留 PP3 手抄阈值块（有即漂移风险，须移除改走路由）。"""
    errs = []
    pp3 = reg.get("pp3")
    if pp3:
        # 允许存在的是"纯声明块"（note/form 说明走路由），不允许存在"数值/阈值/规则体"
        body_keys = [k for k in pp3 if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"PP3 注册表残留规则体 {body_keys}（PP3 特异规则应走 VCEP 路由读取原文，不入本表制造副本）")
    # 防复发：注册表不得出现 PP3 相关的手抄阈值键（如 revel_threshold / pp3_table / revel_ge 等）
    for topk in ("pp3", "pp3_table", "pp3_threshold", "revel_threshold"):
        if topk in reg and topk != "pp3":
            errs.append(f"注册表残留 PP3 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_ba1(reg):
    """BA1 防残留（v1.7.0 路由方案）：BA1 特异切点由 ev-bs1-bs2 第 3.6 步路由读 clingen-vcep VCEP-<gene>.md 原文，
    不落注册表制造官方副本。校验注册表不得残留 BA1 数值/阈值/切点块（有即漂移风险，须移除改走路由）。"""
    errs = []
    ba1 = reg.get("ba1")
    if ba1:
        # 允许存在的是"纯声明块"（note/form/source/version/governance 说明走路由），不允许存在"数值/阈值/切点规则体"
        body_keys = [k for k in ba1 if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BA1 注册表残留规则体 {body_keys}（BA1 特异切点应走 VCEP 路由读取原文，不入本表制造副本）")
    # 防复发：注册表不得出现 BA1 相关的手抄阈值键（如 ba1_cutoff / ba1_table / ba1_faf 等）
    for topk in ("ba1", "ba1_table", "ba1_cutoff", "ba1_faf", "ba1_af"):
        if topk in reg and topk != "ba1":
            errs.append(f"注册表残留 BA1 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_bs2(reg):
    """BS2 防残留（v1.8.0 路由方案）：BS2 特异档位（数值/计数/点数）由 ev-bs1-bs2 第 3.7 步路由读 clingen-vcep VCEP-<gene>.md 原文，
    不落注册表制造官方副本。校验注册表不得残留 BS2 手抄档位/阈值/切点块（有即漂移风险，须移除改走路由）。"""
    errs = []
    bs2 = reg.get("bs2")
    if bs2:
        # 允许"纯声明块"（note/form/source/version/governance 说明走路由），不允许"数值/档位/规则体"
        body_keys = [k for k in bs2 if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BS2 注册表残留规则体 {body_keys}（BS2 特异档位/阈值应走 VCEP 路由读取原文，不入本表制造副本）")
    # 防复发：注册表不得出现 BS2 相关的手抄阈值/档位键
    for topk in ("bs2", "bs2_table", "bs2_bands", "bs2_spec", "bs2_cutoff"):
        if topk in reg and topk != "bs2":
            errs.append(f"注册表残留 BS2 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_pm1(reg):
    """PM1 防残留（v1.2.0 路由方案）：PM1 特异位置档位（热点/关键功能域的 AA/密码子区间、单点集合）由 ev-pm1 第 3.5 步路由读 clingen-vcep VCEP-<gene>.md 原文，
    不落注册表制造官方副本。校验注册表不得残留 PM1 手抄位置/阈值块（有即漂移风险，须移除改走路由）。"""
    errs = []
    pm1 = reg.get("pm1")
    if pm1:
        # 允许"纯声明块"（note/form/source/version/governance 说明走路由），不允许"位置/阈值/规则体"
        body_keys = [k for k in pm1 if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"PM1 注册表残留规则体 {body_keys}（PM1 特异位置档位应走 VCEP 路由读取原文，不入本表制造副本）")
    # 防复发：注册表不得出现 PM1 相关的手抄位置/阈值键
    for topk in ("pm1", "pm1_table", "pm1_bands", "pm1_spec", "pm1_positions"):
        if topk in reg and topk != "pm1":
            errs.append(f"注册表残留 PM1 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_ps1_pm5(reg):
    """PS1/PM5 防残留（v1.4.0 路由方案）：PS1 附加条件与 PM5 计数档位由 ev-ps1-pm5 第 3.5 步路由读 clingen-vcep VCEP-<gene>.md 原文，
    不落注册表制造官方副本。校验注册表不得残留 PS1/PM5 手抄档位/阈值块（有即漂移风险，须移除改走路由）。"""
    errs = []
    for code in ("ps1", "pm5"):
        blk = reg.get(code)
        if blk:
            body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
            if body_keys:
                errs.append(f"{code.upper()} 注册表残留规则体 {body_keys}（{code.upper()} 特异档位/附加条件应走 VCEP 路由读取原文，不入本表制造副本）")
    # 防复发：注册表不得出现 PS1/PM5 相关手抄档位键
    for topk in ("ps1", "pm5", "pm5_bands", "pm5_spec", "ps1_spec", "ps1_pm5_table"):
        if topk in reg and topk not in ("ps1", "pm5"):
            errs.append(f"注册表残留 {topk.upper()} 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_pvs1(reg):
    """PVS1 防残留（v1.13.0 适用性路由方案）：PVS1 特异适用性限定（起始密码子例外/3'端末外显子切点/功能域截断/剪接RNA/机制适用性）
    由 ev-pvs1 第 3.7 步路由读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。校验注册表不得残留 PVS1 手抄切点/限定块。"""
    errs = []
    blk = reg.get("pvs1")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"PVS1 注册表残留规则体 {body_keys}（PVS1 特异切点/适用性限定应走 VCEP 路由读取原文，不入本表制造副本）")
    # 防复发：注册表不得出现 PVS1 相关手抄切点/限定键
    for topk in ("pvs1", "pvs1_cutoff", "pvs1_spec", "pvs1_codon", "pvs1_exon", "pvs1_table"):
        if topk in reg and topk != "pvs1":
            errs.append(f"注册表残留 PVS1 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_pm4(reg):
    """PM4 防残留（v1.2.0 路由方案）：PM4 特异 AA 长度切点（≥2 AA→Moderate/1 AA→Supporting）与特定残基位置
    由 ev-pm4 第 4 步路由读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。校验注册表不得残留 PM4 手抄 AA 切点/位置块。"""
    errs = []
    blk = reg.get("pm4")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"PM4 注册表残留规则体 {body_keys}（PM4 特异 AA 切点/残基位置应走 VCEP 路由读取原文，不入本表制造副本）")
    # 防复发：注册表不得出现 PM4 相关手抄键
    for topk in ("pm4", "pm4_bands", "pm4_spec", "pm4_aa", "pm4_residue", "pm4_table"):
        if topk in reg and topk != "pm4":
            errs.append(f"注册表残留 PM4 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_bp1(reg):
    """BP1 防残留（v1.9.0 适用性路由方案）：BP1 特异适用性限定（RASopathy GOF 不适用/截断机制适用/区域排除/NA）
    由 ev-pp3-bp4 BP1 VCEP 适用性路由协议读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    blk = reg.get("bp1")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BP1 注册表残留规则体 {body_keys}（BP1 特异适用性限定应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("bp1", "bp1_spec", "bp1_region", "bp1_mech", "bp1_table"):
        if topk in reg and topk != "bp1":
            errs.append(f"注册表残留 BP1 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_bp7(reg):
    """BP7 防残留（v1.10.0 适用性路由方案）：BP7 特异判据（标准型/数值切点/RNA升档/BP4联动/NA）
    由 ev-pp3-bp4 BP7 VCEP 适用性路由协议读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    blk = reg.get("bp7")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BP7 注册表残留规则体 {body_keys}（BP7 特异判据应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("bp7", "bp7_spec", "bp7_splice", "bp7_phylop", "bp7_rna", "bp7_table"):
        if topk in reg and topk != "bp7":
            errs.append(f"注册表残留 BP7 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_bp2(reg):
    """BP2 防残留（v1.9.0 适用性路由方案）：BP2 特异判据（标准型反式/顺式/计数点数/NA/升档）
    由 ev-bs1-bs2 BP2 VCEP 适用性路由协议读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    blk = reg.get("bp2")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BP2 注册表残留规则体 {body_keys}（BP2 特异判据应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("bp2", "bp2_spec", "bp2_count", "bp2_points", "bp2_phase", "bp2_table"):
        if topk in reg and topk != "bp2":
            errs.append(f"注册表残留 BP2 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_bp3(reg):
    """BP3 防残留（v1.3.0 适用性路由方案）：BP3 特异判据（标准型重复区/特定重复区限定/NA）
    由 ev-pm4 BP3 VCEP 适用性路由协议读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    blk = reg.get("bp3")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BP3 注册表残留规则体 {body_keys}（BP3 特异判据应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("bp3", "bp3_spec", "bp3_repeat", "bp3_region", "bp3_table"):
        if topk in reg and topk != "bp3":
            errs.append(f"注册表残留 BP3 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_bs4(reg):
    """BS4 防残留（v1.8.0 适用性路由方案）：BS4 特异判据（信息量门槛/定量共分离/单多家系档位/非分离语义/NA）
    由 ev-pp1 BS4 VCEP 适用性路由协议读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    blk = reg.get("bs4")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BS4 注册表残留规则体 {body_keys}（BS4 特异判据应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("bs4", "bs4_spec", "bs4_family", "bs4_meios", "bs4_bayes", "bs4_table"):
        if topk in reg and topk != "bs4":
            errs.append(f"注册表残留 BS4 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_bp5(reg):
    """BP5 防残留（v1.5.0 适用性路由方案）：BP5 特异判据（标准型新发旁置/校准阈值/计数/NA）
    由 ev-ps2-pm6 BP5 VCEP 适用性路由协议读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    blk = reg.get("bp5")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BP5 注册表残留规则体 {body_keys}（BP5 特异判据应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("bp5", "bp5_spec", "bp5_calib", "bp5_count", "bp5_na", "bp5_table"):
        if topk in reg and topk != "bp5":
            errs.append(f"注册表残留 BP5 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_pm3(reg):
    """PM3 防残留（v1.13.0 路由方案）：PM3 特异档位由 ev-pm3 路由读 clingen-vcep VCEP-<gene>.md 原文，
    不落注册表制造官方副本。校验注册表不得残留 PM3 手抄档位/阈值块（有即漂移风险，须移除改走路由）。"""
    errs = []
    pm3 = reg.get("pm3")
    if pm3:
        # 允许"纯声明块"，不允许"数值/档位/规则体"
        body_keys = [k for k in pm3 if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"PM3 注册表残留规则体 {body_keys}（PM3 特异档位应走 VCEP 路由读取原文，不入本表制造副本）")
    # 防复发：注册表不得出现 PM3 相关手抄档位键
    for topk in ("pm3", "pm3_spec", "pm3_table", "pm3_bands"):
        if topk in reg and topk != "pm3":
            errs.append(f"注册表残留 PM3 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_pp4(reg):
    """PP4 防残留（v1.4.0 路由方案）：PP4 特异档位/数值规则由 ev-pp4 路由读 clingen-vcep VCEP-<gene>.md 原文，
    不落注册表制造官方副本。校验注册表不得残留 PP4 手抄档位/数值块（有即漂移风险，须移除改走路由）。"""
    errs = []
    pp4 = reg.get("pp4")
    if pp4:
        body_keys = [k for k in pp4 if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"PP4 注册表残留规则体 {body_keys}（PP4 特异档位/数值应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("pp4", "pp4_spec", "pp4_table", "pp4_bands"):
        if topk in reg and topk != "pp4":
            errs.append(f"注册表残留 PP4 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_ps4(reg):
    """PS4 防残留（v1.4.0 路由方案）：PS4 特异档位由 ev-ps4 路由读 clingen-vcep VCEP-<gene>.md 原文，
    不落注册表制造官方副本。校验注册表不得残留 PS4 手抄档位/阈值块（有即漂移风险，须移除改走路由）。"""
    errs = []
    ps4 = reg.get("ps4")
    if ps4:
        body_keys = [k for k in ps4 if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"PS4 注册表残留规则体 {body_keys}（PS4 特异档位/数值应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("ps4", "ps4_spec", "ps4_table", "ps4_bands"):
        if topk in reg and topk != "ps4":
            errs.append(f"注册表残留 PS4 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_bp4(reg):
    """BP4 防残留（路由方案，2026-10-23 补齐校验链）：BP4 特异阈值/判据（PP3 良性镜像、剪接侧 SpliceAI 切点、REVEL 对照）
    由 ev-pp3-bp4 BP4 VCEP 适用性路由协议读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    blk = reg.get("bp4")
    if blk:
        body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
        if body_keys:
            errs.append(f"BP4 注册表残留规则体 {body_keys}（BP4 特异阈值/判据应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("bp4", "bp4_spec", "bp4_revel", "bp4_splice", "bp4_table"):
        if topk in reg and topk != "bp4":
            errs.append(f"注册表残留 BP4 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_ps3_bs3(reg):
    """PS3/BS3 防残留（路由方案，2026-10-23 补齐校验链）：PS3/BS3 特异功能实验档位（实验类型/定性/定量/切点）
    由 ev-ps3-bs3 第 3.5 步路由读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    for code in ("ps3", "bs3"):
        blk = reg.get(code)
        if blk:
            body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
            if body_keys:
                errs.append(f"{code.upper()} 注册表残留规则体 {body_keys}（{code.upper()} 特异功能实验档位应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("ps3", "bs3", "ps3_bands", "bs3_bands", "ps3_spec", "bs3_spec", "ps3_bs3_table"):
        if topk in reg and topk not in ("ps3", "bs3"):
            errs.append(f"注册表残留 {topk.upper()} 相关块 {topk}（应走 VCEP 路由）")
    return errs

def check_ps2_pm6(reg):
    """PS2/PM6 防残留（路由方案，2026-10-23 补齐校验链）：PS2/PM6 特异新发判定（新发验证/亲缘验证/适用性/计数档位）
    由 ev-ps2-pm6 第 3.5 步路由读 clingen-vcep VCEP-<gene>.md 原文，不落注册表制造官方副本。"""
    errs = []
    for code in ("ps2", "pm6"):
        blk = reg.get(code)
        if blk:
            body_keys = [k for k in blk if k not in ("note", "form", "source", "version", "governance")]
            if body_keys:
                errs.append(f"{code.upper()} 注册表残留规则体 {body_keys}（{code.upper()} 特异新发判据应走 VCEP 路由读取原文，不入本表制造副本）")
    for topk in ("ps2", "pm6", "ps2_bands", "pm6_bands", "ps2_spec", "pm6_spec", "ps2_pm6_table"):
        if topk in reg and topk not in ("ps2", "pm6"):
            errs.append(f"注册表残留 {topk.upper()} 相关块 {topk}（应走 VCEP 路由）")
    return errs

def main():
    reg = load_json(REG)
    thr = load_json(THR)
    all_errs = []
    all_errs += check_pm2(reg, thr)
    all_errs += check_pp1(reg, thr)
    all_errs += check_bs1(reg)
    all_errs += check_ba1(reg)
    all_errs += check_bs2(reg)
    all_errs += check_pm1(reg)
    all_errs += check_ps1_pm5(reg)
    all_errs += check_pvs1(reg)
    all_errs += check_pm4(reg)
    all_errs += check_bp1(reg)
    all_errs += check_bp7(reg)
    all_errs += check_bp2(reg)
    all_errs += check_bp3(reg)
    all_errs += check_bs4(reg)
    all_errs += check_bp5(reg)
    all_errs += check_bp4(reg)
    all_errs += check_ps3_bs3(reg)
    all_errs += check_ps2_pm6(reg)
    all_errs += check_pp3(reg)
    all_errs += check_pm3(reg)
    all_errs += check_pp4(reg)
    all_errs += check_ps4(reg)
    # PP2 为排除清单型，无法数值核对，做结构完整性检查
    if "pp2" not in reg or not reg["pp2"].get("exclude"):
        all_errs.append("PP2 注册表缺 exclude 清单")
    # PVS1 已于 v1.13.0 改为 VCEP 适用性路由：特异切点/适用性限定走 clingen-vcep VCEP-<gene>.md 原文，
    # 注册表不得残留 special_genes/rule 副本（见 check_pvs1），故移除旧的 special_genes 结构强制检查。

    if all_errs:
        print("❌ 不一致项：")
        for e in all_errs:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ 全部一致：注册表与现有散落数据逐值核对通过，第 0 步纯迁移成功（行为零变化）")
        sys.exit(0)

if __name__ == "__main__":
    main()
