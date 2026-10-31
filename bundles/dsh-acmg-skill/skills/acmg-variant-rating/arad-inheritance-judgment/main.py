#!/usr/bin/env python3
"""
AR/AD遗传模式判断 - 查询ClinVar和PubMed获取患者基因型（zygosity）信息
用法:
  python main.py clinvar <gene> "<variant>"
  python main.py pubmed <gene> "<variant>"
  python main.py same_type <gene> "<variant_type>"
"""

import sys
import os
import json
import re
import xml.etree.ElementTree as ET
try:
    import requests  # 第三方库（非 Python 标准库），使用前需安装：python -m pip install requests
except ImportError:
    print("错误：缺少第三方依赖 requests。请先安装：python -m pip install requests，再重新运行本脚本。",
          file=sys.stderr)
    sys.exit(2)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_PARAM = {"tool": "arad-inheritance-judgment-jb", "email": os.environ.get("NCBI_EMAIL", "variant-rating-skill@example.com")}


def esearch(db, term, retmax=50):
    """NCBI E-utilities esearch, return list of IDs"""
    params = {"db": db, "term": term, "retmax": retmax, "retmode": "json"}
    params.update(TOOL_PARAM)
    try:
        resp = requests.get(f"{BASE_URL}/esearch.fcgi", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("esearchresult", {})
        ids = result.get("idlist", [])
        count = result.get("count", "0")
        return ids, int(count)
    except Exception as e:
        print(json.dumps({"error": f"esearch failed: {str(e)}"}, ensure_ascii=False))
        return [], 0


def efetch_xml(db, ids):
    """NCBI E-utilities efetch in XML mode, return ElementTree root"""
    params = {"db": db, "id": ",".join(ids), "retmode": "xml"}
    params.update(TOOL_PARAM)
    resp = requests.get(f"{BASE_URL}/efetch.fcgi", params=params, timeout=60)
    resp.raise_for_status()
    return ET.fromstring(resp.text)


def extract_zygosity_from_text(text):
    """Extract zygosity keywords from free text, return deduplicated list"""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    # Check compound heterozygous before heterozygous
    if "compound heterozygous" in text_lower or "compound heterozygote" in text_lower:
        found.append("compound_heterozygous")
    if "homozygous" in text_lower or "homozygote" in text_lower:
        found.append("homozygous")
    # Only add heterozygous if not already captured as compound
    if ("heterozygous" in text_lower or "heterozygote" in text_lower) and "compound heterozygous" not in text_lower:
        found.append("heterozygous")
    elif "heterozygous" in text_lower and "compound heterozygous" in text_lower:
        # Both present - add heterozygous too
        if "heterozygous" not in found:
            found.append("heterozygous")
    if "hemizygous" in text_lower or "hemizygote" in text_lower:
        found.append("hemizygous")
    return list(dict.fromkeys(found))  # deduplicate preserving order

# ---- 目标变异匹配（v1.0.4 修复，全修 arad P0-1：ClinVar 泛基因查询回退时未筛目标变异）----
_ARAD_AA3TO1 = {
    "ala": "A", "arg": "R", "asn": "N", "asp": "D", "cys": "C", "gln": "Q",
    "glu": "E", "gly": "G", "his": "H", "ile": "I", "leu": "L", "lys": "K",
    "met": "M", "phe": "F", "pro": "P", "ser": "S", "thr": "T", "trp": "W",
    "tyr": "Y", "val": "V", "xaa": "X", "ter": "*",
}


def _arad_norm_cdna(s):
    """cDNA 归一化：c.35delG → c.35del（剥 del/dup/ins 后碱基，兼容 ClinVar 省略碱基写法）。"""
    if not s:
        return ""
    m = re.search(r"c\.[A-Za-z0-9_*>\-delins]+", str(s))
    cdna = m.group(0) if m else str(s).strip()
    if "delins" in cdna.lower():
        return cdna
    for pat in ("dup", "del", "ins"):
        mm = re.search(rf"({pat})[ACGTUacgtu]+$", cdna)
        if mm:
            cdna = cdna[:mm.start()] + mm.group(1)
    return cdna


def _arad_norm_protein(s):
    """蛋白归一化：p.Gly12fs → G12fs；单字母 p.G12fs 也 → G12fs（统一大写，三字母转一字母）。"""
    if not s:
        return ""
    t = str(s).strip().lower()
    if t.startswith("p."):
        t = t[2:]
    out, i = [], 0
    while i < len(t):
        tri = t[i:i + 3]
        if tri in _ARAD_AA3TO1:
            out.append(_ARAD_AA3TO1[tri])
            i += 3
        else:
            out.append(t[i].upper() if t[i].isalpha() else t[i])
            i += 1
    return "".join(out)


def _arad_signature(cdna):
    """变异类型签名：snv/del/dup/ins/delins（忽略位置）。"""
    l = cdna.lower()
    if "delins" in l:
        m = re.search(r"delins([ACGTacgt]*)", cdna)
        return ("delins", m.group(1).upper()) if m and m.group(1) else ("delins",)
    if "dup" in l:
        m = re.search(r"dup([ACGTacgt]*)", cdna)
        return ("dup", m.group(1).upper()) if m and m.group(1) else ("dup",)
    if "del" in l:
        m = re.search(r"del([ACGTacgt]*)", cdna)
        return ("del", m.group(1).upper()) if m and m.group(1) else ("del",)
    if "ins" in l:
        m = re.search(r"ins([ACGTacgt]*)", cdna)
        return ("ins", m.group(1).upper()) if m and m.group(1) else ("ins",)
    m = re.search(r"([ACGT])>([ACGT])", cdna, re.I)
    if m:
        return ("snv", m.group(1).upper(), m.group(2).upper())
    return ()


def _arad_variant_matches(record_variant, record_protein, target):
    """判断 ClinVar 记录是否命中目标变异（cDNA 位置+类型 或 蛋白归一化）。target 为 cDNA 或蛋白表达。"""
    if not target:
        return False
    t = str(target).strip()
    if re.match(r"^p\.", t, re.I):
        tn = _arad_norm_protein(t)
        rn = _arad_norm_protein((record_variant or "") + " " + (record_protein or ""))
        return bool(tn) and tn in rn
    tn = _arad_norm_cdna(t)
    rn = _arad_norm_cdna(record_variant or "")
    if not (tn and rn):
        return False
    m1 = re.match(r"c\.(\d+)", tn)
    m2 = re.match(r"c\.(\d+)", rn)
    if not (m1 and m2) or m1.group(1) != m2.group(1):
        return False
    t_sig = _arad_signature(tn)
    r_sig = _arad_signature(rn)
    if t_sig and r_sig and t_sig[0] == r_sig[0]:
        if t_sig[0] == "snv":
            return len(t_sig) > 1 and t_sig[1:] == r_sig[1:]
        return True
    return False


def search_clinvar(gene, variant):
    """Query ClinVar via esummary (2026-10-21: NCBI efetch db=clinvar 已改为 IdList，
    旧 XML(ClinVarSet/Measure/Trait/Zygosity) 解析失效，迁移到 esummary JSON)。
    返回变异收录状态/致病性/关联疾病(trait)；基因型(zygosity)由 PubMed 文献路径承担。"""
    evidence = []

    # esearch 找 ClinVar UID
    search_term = f'{gene}[gene] AND "{variant}"'
    ids, count = esearch("clinvar", search_term, retmax=30)

    if not ids:
        search_term = f"{gene}[gene] AND {variant}"
        ids, count = esearch("clinvar", search_term, retmax=30)

    if not ids:
        return {
            "source": "ClinVar",
            "found": False,
            "total_hits": count,
            "evidence": [],
            "search_url": f"https://www.ncbi.nlm.nih.gov/clinvar/?term={gene}+{variant}"
        }

    # esummary 获取结构化 JSON（2026-10-21 迁移，替代失效的 efetch XML 解析）
    import requests as _req
    params = {"db": "clinvar", "id": ",".join(ids), "retmode": "json", "retmax": "30"}
    params.update(TOOL_PARAM)
    try:
        resp = _req.get(f"{BASE_URL}/esummary.fcgi", params=params, timeout=60)
        resp.raise_for_status()
        result = resp.json().get("result", {})
    except Exception as e:
        return {"source": "ClinVar", "found": False, "error": f"esummary failed: {str(e)}", "evidence": []}

    seen = set()
    for uid in result.get("uids", []):
        item = result.get(str(uid), {})
        if not item:
            continue

        record_id = item.get("uid", uid)
        accession = item.get("accession", "")

        # 变异名（title 或 protein_change）
        variant_name = item.get("title", "")
        protein = item.get("protein_change", "")

        # 致病性分类
        classification = ""
        gc = item.get("germline_classification", {}) or {}
        if isinstance(gc, dict):
            classification = gc.get("description", "")
        # 关联疾病（trait）
        traits = []
        ts = gc.get("trait_set", []) if isinstance(gc, dict) else []
        for t in ts:
            name = t.get("trait_name", "") if isinstance(t, dict) else ""
            if name:
                traits.append(name)

        ev_key = accession or record_id
        if ev_key in seen:
            continue
        seen.add(ev_key)

        evidence.append({
            "clinvar_id": str(record_id),
            "accession": accession,
            "variant": variant_name,
            "protein_change": protein,
            "classification": classification,
            "traits": list(dict.fromkeys(traits))[:8],
            "clinvar_url": f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{record_id}/",
            "target_match": _arad_variant_matches(variant_name, protein, variant),
        })

    return {
        "source": "ClinVar",
        "found": len(evidence) > 0,
        "total_hits": count,
        "evidence": evidence,
        "target_evidence": [e for e in evidence if e.get("target_match")],
        "search_url": f"https://www.ncbi.nlm.nih.gov/clinvar/?term={gene}+{variant}"
    }


def search_pubmed(gene, variant):
    """Query PubMed for variant in literature, extract zygosity from abstracts"""
    evidence = []

    # Build search query - use variant notation for precision
    search_term = f"{gene}[Title/Abstract] AND {variant}"
    ids, count = esearch("pubmed", search_term, retmax=30)

    if not ids:
        # Broader search
        search_term = f"{gene} AND {variant}"
        ids, count = esearch("pubmed", search_term, retmax=30)

    if not ids:
        return {
            "source": "PubMed",
            "found": False,
            "total_hits": count,
            "evidence": [],
            "search_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={gene}+{variant}"
        }

    try:
        root = efetch_xml("pubmed", ids)
    except Exception as e:
        return {"source": "PubMed", "found": False, "error": f"efetch failed: {str(e)}", "evidence": []}

    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID", "")
        title = article.findtext(".//ArticleTitle", "")

        # Get full abstract text
        abstract_parts = []
        for abs_text in article.findall(".//AbstractText"):
            parts = []
            if abs_text.text:
                parts.append(abs_text.text)
            # Handle mixed content (text + sub-elements)
            for child in abs_text:
                if child.text:
                    parts.append(child.text)
                if child.tail:
                    parts.append(child.tail)
            if parts:
                abstract_parts.append("".join(parts))
        abstract = " ".join(abstract_parts)

        if not abstract:
            continue

        # Extract zygosity from abstract
        zygosities = extract_zygosity_from_text(abstract)

        if zygosities:
            evidence.append({
                "pmid": pmid,
                "title": title[:200],
                "zygosity": zygosities,
                "abstract_snippet": abstract[:500],
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            })

    return {
        "source": "PubMed",
        "found": len(evidence) > 0,
        "total_hits": count,
        "evidence": evidence,
        "search_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={gene}+{variant}"
    }


def search_same_gene_same_type(gene, variant_type):
    """Search PubMed for other variants of same gene and same variant type"""
    evidence = []

    # Map common variant types to search terms
    type_map = {
        "missense": "missense",
        "nonsense": "nonsense",
        "frameshift": "frameshift",
        "splice_site": "splice",
        "splice": "splice",
        "inframe_deletion": "inframe deletion",
        "inframe_insertion": "inframe insertion",
        "indel": "indel",
        "deletion": "deletion",
        "insertion": "insertion",
        "truncating": "truncating",
        "loss_of_function": "loss of function",
        "lof": "loss of function"
    }
    search_type = type_map.get(variant_type.lower().replace(" ", "_"), variant_type)

    search_term = f"{gene}[Title/Abstract] AND {search_type}[Title/Abstract]"
    ids, count = esearch("pubmed", search_term, retmax=30)

    if not ids:
        return {
            "source": "PubMed_SameType",
            "found": False,
            "total_hits": count,
            "evidence": [],
            "variant_type_searched": variant_type,
            "search_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={gene}+{search_type}"
        }

    try:
        root = efetch_xml("pubmed", ids)
    except Exception as e:
        return {"source": "PubMed_SameType", "found": False, "error": str(e), "evidence": []}

    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID", "")
        title = article.findtext(".//ArticleTitle", "")

        abstract_parts = []
        for abs_text in article.findall(".//AbstractText"):
            parts = []
            if abs_text.text:
                parts.append(abs_text.text)
            for child in abs_text:
                if child.text:
                    parts.append(child.text)
                if child.tail:
                    parts.append(child.tail)
            if parts:
                abstract_parts.append("".join(parts))
        abstract = " ".join(abstract_parts)

        if not abstract:
            continue

        zygosities = extract_zygosity_from_text(abstract)

        if zygosities:
            # Try to extract specific variant descriptions from abstract
            variant_mentions = re.findall(
                r'(?:c\.\d+[ACGT]>[ACGT]|c\.\d+_[A-Za-z]+\d+del|p\.[A-Z][a-z]{2}\d+[A-Z][a-z]{0,3}|[A-Z][a-z]{2}\d+[A-Z][a-z]{0,3}[^a-z])',
                abstract
            )

            evidence.append({
                "pmid": pmid,
                "title": title[:200],
                "zygosity": zygosities,
                "variant_mentions": list(dict.fromkeys(variant_mentions))[:5] if variant_mentions else [],
                "abstract_snippet": abstract[:500],
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            })

    return {
        "source": "PubMed_SameType",
        "found": len(evidence) > 0,
        "total_hits": count,
        "evidence": evidence,
        "variant_type_searched": variant_type,
        "search_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={gene}+{search_type}"
    }


def main():
    if len(sys.argv) < 4:
        print(json.dumps({
            "error": "Usage: python main.py <mode> <gene> <variant_or_type>",
            "modes": "clinvar, pubmed, same_type"
        }, ensure_ascii=False))
        sys.exit(1)

    mode = sys.argv[1].lower()
    gene = sys.argv[2]
    variant = sys.argv[3]

    if mode == "clinvar":
        result = search_clinvar(gene, variant)
    elif mode == "pubmed":
        result = search_pubmed(gene, variant)
    elif mode == "same_type":
        result = search_same_gene_same_type(gene, variant)
    else:
        result = {"error": f"Unknown mode: {mode}. Use: clinvar, pubmed, same_type"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
