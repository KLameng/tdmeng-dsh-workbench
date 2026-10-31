# -*- coding: utf-8 -*-
"""
PM2 特异规则 · 全量形态扫描（131 基因）
只做形态分类统计，不落库、不改任何 config/scripts/SKILL。
目的：摸清 131 基因 PM2 段的真实形态分布，为"复合规则对象 schema"设计提供依据。

形态判定维度：
- 数值型（显式阈值：≤/≥/</> + 小数/科学计数/百分比）
- 等位数型（≤1 allele 等）
- 双遗传方式（AR+AD 双切点）
- 条件型（Absent 无数值 / 依赖特定子集/深度）
- 复合（数值+亚群/深度/CI 等附加条件）
- popmax（popmax/highest frequency/subpopulation with highest）
- 亚群排除（do not use Finnish/Ashkenazi 等）
"""
import os, re, json, sys
from collections import Counter

KB = r"C:\Users\DELL\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\clingen-vcep\knowledge-base"

def get_pm2_block(gene):
    p = os.path.join(KB, f"VCEP-{gene}.md")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^####\s*PM2", ln.strip()):
            start = i
            break
    if start is None:
        return None
    end = start + 1
    while end < len(lines):
        s = lines[end].strip()
        if re.match(r"^#{2,3}\s", s) or (s.startswith("####") and "PM2" not in s):
            break
        end += 1
    return "".join(lines[start:end]).strip()

def classify(block):
    if not block:
        return "NO_PM2_SECTION"
    low = block.lower()
    # 数值存在性
    has_num = bool(re.search(r"(?:≤|≥|<|>|<=|>=|less than|fewer than|greater than)\s*[0-9][0-9.]*[Ee]?-?[0-9]*", block)) or bool(re.search(r"[0-9.]+\\s*%", block))
    has_pct = bool(re.search(r"[0-9.]+\\s*%", block))
    # 等位数
    has_allele = bool(re.search(r"[0-9,]+\s*(?:alleles|allele|individuals|of 1)\b", block, re.I)) or "alleles" in low or "allele" in low
    # 双遗传方式
    has_dual = (("autosomal recessive" in low and "autosomal dominant" in low) or
                ("recessive" in low and "dominant" in low))
    # popmax
    has_popmax = "popmax" in low or "highest frequency" in low or "subpopulation with the highest" in low or "popmax" in low
    # 亚群排除
    has_subpop_excl = ("do not use" in low and ("finnish" in low or "ashkenazi" in low)) or "exclude" in low or "excluding" in low
    # 条件型（Absent 无显式数值）
    has_absent = "absent" in low
    has_depth = "depth" in low or "coverage" in low or "≥25" in block or "25×" in block

    flags = []
    if has_num: flags.append("数值")
    if has_pct: flags.append("百分比")
    if has_allele: flags.append("等位数")
    if has_dual: flags.append("双遗传方式")
    if has_popmax: flags.append("popmax")
    if has_subpop_excl: flags.append("亚群排除")
    if has_depth: flags.append("深度/覆盖")
    if has_absent: flags.append("Absent")
    if not has_num and not has_allele and has_absent:
        return "条件型(Absent无数值)" + ("+" + "+".join(flags) if flags else "")
    if len(flags) >= 3:
        return "复合型(" + "+".join(flags) + ")"
    return "单形态(" + "+".join(flags) + ")" if flags else "未归类"

def main():
    files = [f for f in os.listdir(KB) if f.startswith("VCEP-") and f.endswith(".md")]
    genes = sorted([f.replace("VCEP-", "").replace(".md", "") for f in files])
    results = {}
    morph_counter = Counter()
    for g in genes:
        block = get_pm2_block(g)
        m = classify(block)
        results[g] = m
        # 归类主形态（去括号细节）
        base = m.split("(")[0]
        morph_counter[base] += 1
    print(f"基因总数: {len(genes)}")
    print("\n主形态分布:")
    for k, v in morph_counter.most_common():
        print(f"  {k}: {v}")
    print("\n复合型/条件型明细（需人工关注）:")
    for g in sorted(results):
        if "复合" in results[g] or "条件" in results[g] or "未归类" in results[g]:
            print(f"  {g}: {results[g]}")
    # 落盘全量形态表（供后续 schema 设计）
    out = {"genes": len(genes), "morph": dict(morph_counter), "detail": results}
    with open(os.path.join(os.path.dirname(__file__), "pm2_all_morph_scan.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n全量形态表已落盘: scripts/pm2_all_morph_scan.json")

if __name__ == "__main__":
    main()
