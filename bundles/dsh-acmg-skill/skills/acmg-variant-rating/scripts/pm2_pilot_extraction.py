# -*- coding: utf-8 -*-
"""
PM2 特异基因全量提取 · 试点脚本
目的：从 clingen-vcep/knowledge-base/VCEP-<gene>.md 的 "#### PM2" 段，
抽取每个基因的 PM2 特异规则，验证能否结构化提取 + 摸清规则形态分布，
为"全量提取 131 基因 PM2 特异阈值"做试点。

试点范围：6 个代表性基因（覆盖 4 种规则形态）
  已在 af_genetic 表内可核对：PTEN, CDH1, GJB2
  复合形态新基因：MYH7(数值+等位数), USH2A(双遗传方式), BRCA1(条件型), SCN1A(等位数), FBN1(数值+亚群)

输出：试点提取结果（控制台 + 可选 json 落盘）
不修改任何现有 config/scripts/SKILL（本脚本为独立试点工具）。
"""
import os, re, json, sys

KB = r"C:\Users\DELL\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\clingen-vcep\knowledge-base"

# 试点基因 + 其已知形态说明（用于人工核对提取是否正确）
PILOT = [
    ("PTEN",   "已在表内，单值型：0.001%"),
    ("CDH1",   "已在表内，单值+亚群：0.001% / 0.002%"),
    ("GJB2",   "已在表内，AR-HL 0.007%"),
    ("MYH7",   "复合型：popmax≤0.00004 + 单等位限制 + 95%CI"),
    ("USH2A",  "双遗传方式：AR≤0.00007 / AD≤0.00002"),
    ("BRCA1",  "条件型：Absent 无数值 + gnomAD 特定子集 + 深度≥25"),
    ("SCN1A",  "等位数型：≤1 等位 / ≥10000 等位"),
    ("FBN1",   "数值+亚群：<0.000005 + 禁用芬兰/犹太 + 最小等位数 2000"),
]

def extract_pm2_block(gene):
    """抽取 VCEP-<gene>.md 的 '#### PM2' 段（到下一个 '####' 或 '###' 为止）"""
    p = os.path.join(KB, f"VCEP-{gene}.md")
    if not os.path.exists(p):
        return None, f"文件不存在: VCEP-{gene}.md"
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^####\s*PM2", ln.strip()):
            start = i
            break
    if start is None:
        return None, "未找到 '#### PM2' 段"
    end = start + 1
    while end < len(lines):
        s = lines[end].strip()
        if re.match(r"^#{2,3}\s", s) or (s.startswith("####") and "PM2" not in s):
            break
        end += 1
    return "".join(lines[start:end]).strip(), None


def classify_pm2(block):
    """粗判 PM2 规则形态：单值 / 双遗传方式 / 等位数 / 条件型(无显式数值) / 数值复合"""
    if block is None:
        return "无PM2段"
    # 找显式数值（阈值形式）
    nums = re.findall(r"(?:≤|≥|<|>|<=|>=|less than|fewer than)\s*([0-9][0-9.]*[Ee]?-?[0-9]*)", block)
    pct = re.findall(r"([0-9.]+)\s*%", block)
    allele = re.findall(r"([0-9,]+)\s*(?:alleles|allele|individuals|of\s*1)", block, re.I)
    # 形态判断
    has_num = bool(nums) or bool(pct)
    has_allele = bool(allele)
    has_dual = ("autosomal recessive" in block and "autosomal dominant" in block) or ("AR" in block and "AD" in block and re.search(r"recessive|dominant", block))
    if not has_num and not has_allele:
        if "absent" in block.lower() and "frequency" not in block.lower():
            return "条件型(Absent/无数值)"
        return "条件型"
    if has_num and has_allele:
        return "数值+等位数复合"
    if has_num:
        if has_dual:
            return "数值(双遗传方式)"
        return "数值(单值/单遗传方式)"
    if has_allele:
        return "等位数型"
    return "未归类"


def extract_thresholds(block, gene):
    """尝试抽取可量化阈值（尽力而为，供人工核对）"""
    out = {"gene": gene, "num_thresholds": [], "percent_thresholds": [], "allele_limits": [], "raw_len": len(block) if block else 0}
    if not block:
        return out
    # 百分比阈值（带方向）
    for m in re.finditer(r"(≤|≥|<|>|<=|>=|less than|greater than|more than)\s*([0-9.]+)\s*%", block, re.I):
        out["percent_thresholds"].append(f"{m.group(1)}{m.group(2)}%")
    # 小数/科学计数阈值
    for m in re.finditer(r"(≤|≥|<|>|<=|>=)\s*([0-9][0-9.]+(?:[Ee][+-]?[0-9]+)?)", block):
        # 过滤掉像 1/500 分母、0.5 之类
        val = float(m.group(2))
        if val <= 1.0:
            out["num_thresholds"].append(f"{m.group(1)}{m.group(2)}")
    # 等位数限制
    for m in re.finditer(r"([0-9,]+)\s*(?:alleles|allele|individuals)", block, re.I):
        out["allele_limits"].append(m.group(1))
    # 95%CI / 深度 / 亚群限定标记
    out["has_ci"] = "95% CI" in block or "confidence interval" in block.lower()
    out["has_depth"] = "depth" in block.lower() or "≥25" in block or "25×" in block
    out["has_popmax"] = "popmax" in block.lower() or "highest frequency" in block.lower() or "subpopulation with the highest" in block.lower()
    out["has_subpop_exclusion"] = ("do not use" in block.lower() and ("finnish" in block.lower() or "ashkenazi" in block.lower())) or "exclude" in block.lower()
    return out


def main():
    print("=" * 80)
    print("PM2 特异基因全量提取 · 试点（6 基因形态覆盖）")
    print("=" * 80)
    results = {}
    for gene, desc in PILOT:
        block, err = extract_pm2_block(gene)
        print(f"\n### {gene}  [{desc}]")
        if err:
            print(f"  !! {err}")
            results[gene] = {"error": err}
            continue
        morph = classify_pm2(block)
        thr = extract_thresholds(block, gene)
        results[gene] = {"morph": morph, "thresholds": thr, "pm2_block": block}
        print(f"  形态判定: {morph}")
        print(f"  数值阈值: {thr['num_thresholds']}")
        print(f"  百分比阈值: {thr['percent_thresholds']}")
        print(f"  等位数限制: {thr['allele_limits']}")
        print(f"  95%CI={thr['has_ci']} 深度={thr['has_depth']} popmax={thr['has_popmax']} 亚群排除={thr['has_subpop_exclusion']}")
        # 打印 PM2 段前 2 行看原始文本
        print(f"  原始段预览: {block[:200].replace(chr(10),' ')}")

    print("\n" + "=" * 80)
    print("形态分布统计")
    print("=" * 80)
    from collections import Counter
    morphs = Counter(r["morph"] for r in results.values() if "morph" in r)
    for m, c in morphs.items():
        print(f"  {m}: {c} 基因")

    # 落盘（试点 json，不覆盖任何现有文件）
    out_path = os.path.join(os.path.dirname(__file__), "pm2_pilot_extraction.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n试点结果已落盘: {out_path}")


if __name__ == "__main__":
    main()
