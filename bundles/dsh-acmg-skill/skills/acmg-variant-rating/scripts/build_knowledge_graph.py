"""
build_knowledge_graph.py — 构建评级技能群"知识图"（knowledge_graph.json）

定位（遵守"不要把裁定权交给模型"原则）：
  知识图 = 纯规范层（ACMG 指南 / 指南解读 / 阈值表 / ClinGen VCEP 载体），【不做任何裁定】。
  它只回答四类"事实查询"，供模型在评级时【优先从知识图取数，不从内部知识库臆想】：
    (1) 证据适用表：某变异类型 → 可用证据码集合（确定性，来自总调度层证据适用表=ACMG/AMP 2015）
    (2) 分值权重   ：证据码/使用等级 → 通用分值（确定性，来自 config/thresholds.json score）
    (3) 外部阈值   ：REVEL/SpliceAI/PM2/PP1 等切点（确定性，来自 config/thresholds.json）
    (4) 基因-遗传模式种子：gene-gn-file-mapping.csv 中已知 VCEP 基因 → 载体存在性（仅索引，
                          遗传模式实际判定仍走 arad-inheritance-judgment 实时查询，不在此硬编码 MOI）

铁律（2026-10-19 重构，用户纠正）：
  - 知识图【只来源于 ACMG 指南/指南解读/阈值表/ClinGen VCEP 载体】等规范层。
  - 【禁止】把测试集/金标准（171/39 变异）写入知识图——测试集是验收层，用来测技能群准不准，
    不是用来定义规则；金标准变异索引会造成"查答案"污染（评级命中即采信，而非独立查证），
    与盲测禁查 ClinVar 官方分类同理。金标准数据保留在验收层（acmg-evaluation-framework/tests/ 与
    Desktop 金标准目录），供验收/回测用，不进入评级运行时的知识图查询闸 G2。
  - 本图禁止包含"模型可凭此直接给最终分类"的裁定逻辑；最终分类永远由收尾引擎决定。
  - 遗传模式不在此硬编码，只标记"该基因是否有 VCEP 载体可加速"，实际 MOI 以 arad 实时查询为准。

输出：config/knowledge_graph.json（版本化，与 thresholds.json 同步升版）
"""
import json
import csv
import os
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ...\.user_skills
CONFIG = os.path.join(ROOT, "config")
THRESH = os.path.join(CONFIG, "thresholds.json")
OUT = os.path.join(CONFIG, "knowledge_graph.json")

# ── (1) 证据适用表：变异类型 → 可用证据码（确定性，与总调度层"证据适用表"一致）──────────────
EVIDENCE_APPLICABILITY = {
    "truncating":   ["PVS1","PS2","PS3","PS4","PM2","PM3","PM6","PP1","PP4","BA1","BS1","BS2","BS3","BS4","BP2","BP5"],
    "missense":     ["PS1","PS2","PS3","PS4","PM1","PM2","PM3","PM5","PM6","PP1","PP2","PP3","PP4","BA1","BS1","BS2","BS3","BP4","BS4","BP1","BP2","BP5"],
    "inframe_indel":["PS2","PS3","PS4","PM2","PM3","PM4","PM6","PP1","PP3","PP4","BA1","BS1","BS2","BS3","BP4","BS4","BP2","BP3","BP5"],
    "synonymous":   ["PS2","PS3","PS4","PM2","PM3","PM6","PP1","PP3","PP4","BA1","BS1","BS2","BS3","BP4","BS4","BP5","BP7"],
}

# 证据码 → 子技能（确定性，供模型"先查技能组"）
CODE_TO_SKILL = {
    "PVS1":"ev-pvs1", "PS1":"ev-ps1-pm5", "PM5":"ev-ps1-pm5", "PS2":"ev-ps2-pm6", "PM6":"ev-ps2-pm6",
    "PS3":"ev-ps3-bs3", "BS3":"ev-ps3-bs3", "PS4":"ev-ps4", "PM1":"ev-pm1", "PM2":"ev-pm2",
    "PM3":"ev-pm3", "PM4":"ev-pm4", "PP1":"ev-pp1", "PP2":"ev-pp2", "PP3":"ev-pp3-bp4",
    "BP4":"ev-pp3-bp4", "PP4":"ev-pp4", "BA1":"ev-bs1-bs2", "BS1":"ev-bs1-bs2", "BS2":"ev-bs1-bs2",
    "BS4":"ev-pp1", "BP1":"ev-pp3-bp4", "BP2":"ev-bs1-bs2", "BP3":"ev-pm4", "BP5":"ev-ps2-pm6", "BP7":"ev-pp3-bp4",
}

# 证据码 → 支持强度域（确定性，供圈定基线）
CODE_BASE_STRENGTH = {
    "PVS1":"VeryStrong", "PS1":"Strong", "PM5":"Moderate", "PS2":"Strong", "PM6":"Moderate",
    "PS3":"Strong", "BS3":"Strong", "PS4":"Strong", "PM1":"Moderate", "PM2":"Supporting",
    "PM3":"Moderate", "PM4":"Moderate", "PP1":"Supporting", "PP2":"Supporting", "PP3":"Supporting",
    "BP4":"Supporting", "PP4":"Supporting", "BA1":"Standalone", "BS1":"Strong", "BS2":"Strong",
    "BS4":"Supporting", "BP1":"Supporting", "BP2":"Supporting", "BP3":"Supporting", "BP5":"Supporting", "BP7":"Supporting",
}

# 证据码 → 语义（确定性，供模型理解码的含义，不做裁定）
CODE_MEANING = {
    "PVS1":"预测性无义变异/移码/经典剪接致功能丧失(LOF)",
    "PS1":"与已知致病变异相同的氨基酸改变",
    "PM5":"与已知致病变异不同的氨基酸改变(新错义)",
    "PS2":"新发(de novo)变异(确认父母未携带)",
    "PM6":"新发变异(未经确认/推测)",
    "PS3":"功能实验证实功能损害",
    "BS3":"功能实验证实无功能损害",
    "PS4":"患者群体中富集/病例对照显著",
    "PM1":"位于热点突变区或关键功能域",
    "PM2":"正常对照数据库中极低频/缺失",
    "PM3":"隐性遗传反式位置检出致病变异",
    "PM4":"框内插入缺失/终止密码子丧失致蛋白长度变化",
    "PP1":"变异与疾病在家系中共分离",
    "PP2":"错义变异位于低频良性比例低的基因/机制为错义",
    "PP3":"计算预测有害(多工具一致)",
    "BP4":"计算预测无影响/良性",
    "PP4":"表型/家族史高度特异于该病",
    "BA1":"等位基因频率>疾病发病率(独立良性)",
    "BS1":"等位基因频率过高不支持致病",
    "BS2":"早期完全外显疾病在健康成年人中发现",
    "BS4":"变异在受影响个体中不共分离",
    "BP1":"错义变异在仅LOF机制的基因中",
    "BP2":"反式检出已知致病变异(或与另一病致病变异共存)",
    "BP3":"框内indel位于重复区/功能未知区",
    "BP5":"新发变异但另一机制已确认致病",
    "BP7":"同义/非编码变异不影响剪接",
}

# 分值等级关键字（thresholds.score）。⚠ BA1 映射修复（2026-10-19 深入核查）：
# Standalone 不再映射 SU(1) —— Tavtigian 2020 中 BA1 是独立 Very Strong 权重（-8，独立良性，
# 对应表5 "1 BA1→B"），引擎B 对 BA1 解析为 VeryStrong→VS→8。此前映射 Standalone→SU 使知识图
# score_map["BA1"]=1，与引擎实际 -8 结算不一致，属规范层索引错误，已修正为 VS(8)。Standalone 仅 BA1 使用。
STRENGTH_KEY = {"VeryStrong": "VS", "Strong": "ST", "Moderate": "MO", "Supporting": "SU", "Standalone": "VS"}


def load_thresholds():
    if not os.path.exists(THRESH):
        raise SystemExit(f"[KG] 缺失阈值表: {THRESH}")
    with open(THRESH, encoding="utf-8") as f:
        return json.load(f)


def load_gene_vcep():
    """gene-gn-file-mapping.csv：基因 → VCEP 载体存在性（仅索引）"""
    p = os.path.join(ROOT, "clingen-vcep", "gene-gn-file-mapping.csv")
    if not os.path.exists(p):
        return {}
    m = {}
    with open(p, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            g = row.get("基因","").strip()
            if g:
                m[g.upper()] = {"gn": row.get("GN编号",""), "vcep": row.get("VCEP专家组",""),
                                "file": row.get("知识库文件",""), "multi_spec": row.get("多规范","")}
    return m


def build():
    th = load_thresholds()
    gene_vcep = load_gene_vcep()

    score_tbl = th.get("score", {})
    score_map = OrderedDict()
    for code, base in CODE_BASE_STRENGTH.items():
        key = STRENGTH_KEY.get(base, "SU")
        score_map[code] = score_tbl.get(key, 1)

    # 分值方向：致病码正分、良性码负分
    benign = {"BA1","BS1","BS2","BS3","BS4","BP1","BP2","BP3","BP4","BP5","BP7"}
    sign_map = {}
    for code in CODE_BASE_STRENGTH:
        if code in benign:
            sign_map[code] = -1
        else:
            sign_map[code] = 1

    graph = {
        "meta": {
            "name": "ACMG 评级技能群 · 知识图（规范层）",
            "purpose": "确定性查询索引+规范前置；不做裁定，最终分类由收尾引擎决定",
            "built_from": ["ACMG/AMP 2015 指南（Richards et al.）", "指南解读/变异解读查询路径",
                           "config/thresholds.json", "clingen-vcep（ClinGen VCEP 载体索引）",
                           "总调度层证据适用表"],
            "version": "2.0.2",
            "updated": "2026-10-20",
            "scope": "仅规范层。禁止写入测试集/金标准（171/39）变异——金标准是验收层，用于测准不准，"
                     "不进入评级运行时的知识图查询闸 G2，避免'查答案'污染。",
            "usage": "评级模型【优先从本图取数】，不从内部知识库臆想；本图只提供事实查询，不提供最终分类裁决",
        },
        "evidence_applicability": EVIDENCE_APPLICABILITY,
        "code_to_skill": CODE_TO_SKILL,
        "code_base_strength": CODE_BASE_STRENGTH,
        "code_meaning": CODE_MEANING,
        "score": {
            "score_map": score_map,          # 证据码 → 通用分值(正负已含方向)
            "sign_map": sign_map,            # 证据码 → 方向(+1致病/-1良性)
            "score_table_ref": th.get("score", {}),
        },
        "thresholds_ref": {
            "path": "config/thresholds.json",
            "revel": th.get("revel", {}),
            "spliceai": th.get("spliceai", {}),
            "pm2": th.get("pm2", {}),
            "pp1_lod": th.get("pp1_lod", {}),
            "pp1_lod_cmp_ep": th.get("pp1_lod_cmp_ep", {}),
            "hl_vcep_pp1": th.get("hl_vcep_pp1", {}),
            "pm3_score": th.get("pm3_score", {}),
            "tavtigian_interval": th.get("tavtigian_interval", {}),
        },
        "gene_vcep_index": gene_vcep,  # 基因 → VCEP 载体存在性（仅索引，MOI 以 arad 实时为准）
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print(f"[KG] 已写入 {OUT}")
    print(f"    证据适用类型: {len(EVIDENCE_APPLICABILITY)} 类; 证据码: {len(CODE_TO_SKILL)} 个")
    print(f"    基因VCEP索引={len(gene_vcep)} 个; 纯规范层，不含金标准/测试集")
    print(f"    meta.version={graph['meta']['version']}")


if __name__ == "__main__":
    build()
