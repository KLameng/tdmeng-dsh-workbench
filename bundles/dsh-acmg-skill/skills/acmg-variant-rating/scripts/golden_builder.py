# -*- coding: utf-8 -*-
"""golden_builder.py — 从 39变异技能群评级汇总.json 生成双尺子 golden.json
每条含 methodA（经典联合 Table5）与 methodB（Tavtigian 分值）两把尺子的金标准；
官方裁定条目 basis=VCEP官方。金标准为暂用版本，随更新重建。
输出：随包 config/golden.json（相对脚本同目录；输入 39变异集仅在构建环境可用，重建时请指明输入路径）。
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "..", "..", "Doubao", "chats", "2026-10-13", "new-chat", "39变异技能群评级汇总.json")
OUT = os.path.join(HERE, "..", "config", "golden.json")

# 分类规范化（全称，与引擎 CLASS 对齐）
def norm_class(s, allow_par=False):
    """从任意串提取分类全称。allow_par=True 时容忍"（官方）/（共识）"等括号备注。"""
    if not s:
        return None
    s = str(s)
    # 括号备注剥离
    base = re.sub(r"（[^）]*）|\([^)]*\)", "", s).strip() if allow_par else s
    if "Likely Pathogenic" in base or base.startswith("LP") or "可能致病" in base:
        return "Likely Pathogenic"
    if "Pathogenic" in base or base.startswith("P") or "致病" in base:
        return "Pathogenic"
    if "Likely Benign" in base or base.startswith("LB") or "可能良性" in base:
        return "Likely Benign"
    if "Benign" in base or base.startswith("B") or "良性" in base:
        return "Benign"
    if "VUS" in base or "意义不明确" in base or "不确定" in base:
        return "VUS"
    return None


def norm_methodA(x):
    # methodA：LP / P / P（官方）/ VUS / VUS（High）等
    if not x:
        return None
    s = str(x).strip()
    if "官方" in s:
        c = norm_class(s)
        return c
    return norm_class(s, allow_par=True)


# ---------- basis 自检（金标准两套结算：区分 methodA 是表5推还是点值法推） ----------
def criteria_counts(criteria):
    """criteria→表5分桶计数（跳过状态含"待核验/未核验/待人工"的码，与引擎不计 pending 对齐）。"""
    c = {"VS": 0, "ST": 0, "MO": 0, "SU": 0, "BA1": 0, "BS": 0, "BP": 0}
    for it in criteria:
        code = (it.get("code") or "").strip()
        lvl = (it.get("level") or "").strip()
        st = (it.get("status") or "").strip()
        if not code or code == "VCEP官方裁定":
            continue
        if any(k in st for k in ("待核验", "未核验", "待人工", "待全文核验")):
            continue
        n = 1
        if code == "BA1":
            c["BA1"] += n
        elif code.startswith("BS"):
            c["BS"] += n
        elif code.startswith("BP"):
            c["BP"] += n
        else:  # 致病码按等级入桶
            if lvl in ("VeryStrong", "VS"):
                c["VS"] += n
            elif lvl in ("Strong", "ST"):
                c["ST"] += n
            elif lvl in ("Moderate", "MO"):
                c["MO"] += n
            else:
                c["SU"] += n
    return c


def table5_ref(c):
    """Richards 2015 Table5 参考实现（独立推导，与 combination_eval/regression_gate 同语义）。"""
    benign = c["BA1"] >= 1 or c["BS"] >= 2
    patho = (c["VS"] >= 1 and (c["ST"] >= 1 or c["MO"] >= 2 or (c["MO"] >= 1 and c["SU"] >= 1) or c["SU"] >= 2)) \
        or (c["ST"] >= 2) or (c["ST"] >= 1 and (c["MO"] >= 3 or (c["MO"] >= 2 and c["SU"] >= 2) or (c["MO"] >= 1 and c["SU"] >= 4)))
    lp = (c["VS"] >= 1 and c["MO"] >= 1) or (c["ST"] >= 1 and 1 <= c["MO"] <= 2) \
        or (c["ST"] >= 1 and c["SU"] >= 2) or (c["MO"] >= 3) or (c["MO"] >= 2 and c["SU"] >= 2) or (c["MO"] >= 1 and c["SU"] >= 4)
    lb = (c["BS"] >= 1 and c["BP"] >= 1) or (c["BP"] >= 2)
    if patho and benign:
        return "VUS"
    if patho:
        return "Pathogenic"
    if benign:
        return "Benign"
    if lp and lb:
        return "VUS"
    if lp:
        return "Likely Pathogenic"
    if lb:
        return "Likely Benign"
    return "VUS"


def basis_by_methodA(criteria, methodA, is_official):
    """两套结算基准判定：官方→VCEP官方；否则 methodA 表5可达→Table5；表5不可达→点值法（methodA 由点值推）。"""
    if is_official:
        return "VCEP官方"
    derive = table5_ref(criteria_counts(criteria))
    return "Table5" if methodA == derive else "点值法"


def norm_methodB(x):
    # methodB：LP(+9) / P(+10) / VUS(+2) / P(~+14) / LB(-2) / VUS(0)→官方P覆盖
    if not x:
        return None
    s = str(x).strip()
    # "→官方P覆盖"：官方覆盖 → 取"官方"后分类
    if "官方" in s:
        # 取官方指向的分类（如 "官方P覆盖" / "官方裁定"）
        m = re.search(r"官方\s*([PBLVUS]{1,3}|Pathogenic|Benign|Likely)", s, re.I)
        if m:
            return norm_class(m.group(1))
        return "Pathogenic" if "P" in s else None
    # 取括号前分类部分
    base = re.split(r"[（(]", s)[0].strip()
    return norm_class(base, allow_par=True)


def main():
    data = json.load(open(SRC, encoding="utf-8")).get("variants", [])
    cases = []
    for r in data:
        vid = r["id"]
        criteria = []
        is_official = False
        for ev in r.get("evidence", []):
            code = ev.get("code", "")
            lvl = ev.get("strength", "")
            if code == "VCEP官方裁定":
                is_official = True
            criteria.append({"code": code, "level": lvl, "status": ev.get("status", "")})
        ma = norm_methodA(r.get("methodA"))
        mb = norm_methodB(r.get("methodB"))
        basis = basis_by_methodA(criteria, ma, is_official)
        cases.append({
            "id": vid,
            "gene": r.get("gene", ""),
            "criteria": criteria,
            "methodA": ma,
            "methodB": mb,
            "basis": basis,
            "official": is_official,
            "source": f"金标准暂用版（来源 {SRC.split(chr(92))[-1]}）；methodA=经典联合规则、methodB=Tavtigian 分值；basis={basis}；会随金标准更新",
            "note": (r.get("caveat") or "")[:200],
        })

    doc = {
        "frozen_at": "2026-10-15",
        "status": "暂用版（随金标准更新重建，非永久冻结）",
        "ruler_A": "ACMG/AMP 2015 Table 5 组合规则 (Richards et al., Genet Med 2015)",
        "ruler_B": "Tavtigian 点值法 (Tavtigian et al. 2020, PMID 32720330)",
        "official_ruler": "ClinGen VCEP 官方裁定（最高真值层）",
        "cases": cases,
    }
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 验证
    import collections
    cnt = collections.Counter(c["basis"] for c in cases)
    na = sum(1 for c in cases if c["methodA"])
    nb = sum(1 for c in cases if c["methodB"])
    print(f"生成 golden.json: {len(cases)} 条")
    print(f"  basis: {dict(cnt)}")
    print(f"  methodA 可解析 {na} / methodB 可解析 {nb}")
    print(f"  官方裁定: {sum(1 for c in cases if c['official'])} 条")


if __name__ == "__main__":
    main()
