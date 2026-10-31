#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
疾病信息查询_jb — 数据查询脚本
封装NCBI E-utilities (MedGen/ClinVar/Books/PubMed)、ClinGen、Mutalyzer的API调用。
所有API均为公开接口，无需凭证。
"""

import sys
import os
import json
import re
import time
import argparse
from html import unescape

from coze_workload_identity import requests

# NCBI E-utilities基础配置
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_TOOL = "disease-info-query-jb"
NCBI_EMAIL = "tool@example.com"
REQUEST_DELAY = 0.34  # NCBI建议3次/秒，间隔约0.34秒

# 三字母→单字母氨基酸缩写
AA3TO1 = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
    "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
    "Ter": "*", "*": "*"
}

BOOKS_GENE_STOP = {
    "THE", "AND", "FOR", "NOT", "WITH", "TYPE", "GENE", "REVIEW",
    "OMIM", "ALL", "VIEW", "MAJOR", "CLINICAL", "FREQUENCY",
    "RECOMMENDED", "SURVEILLANCE", "INDIVIDUALS", "OTHER", "ALLELIC",
    "DISORDERS", "DIFFERENTIAL", "DIAGNOSIS", "SYNDR", "GENES", "DATABASES",
    "DIAGNOSIS", "TABLE", "FIGURE", "CHAPTER", "APPENDIX", "SUMMARY",
    "MANAGEMENT", "EVALUATION", "TREATMENT", "GENETIC", "COUNSELING",
    "RESOURCES", "MOLECULAR", "PATHOGENESIS", "CLINICAL", "FEATURES",
    "INTRODUCTION", "REFERENCES", "ACKNOWLEDGMENTS", "NOTES", "SEARCH",
    "STRATEGY", "SELECTED", "HERITABLE", "CONNECTIVE", "TISSUE",
    "DISABILITY", "HEREDITARY", "AORTOPATHIES", "DISEASE", "SYNDROME"
}


def _get(url, params=None, timeout=30):
    """统一GET请求，带错误处理；NCBI 429时等待1秒后重试一次。"""
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 429 and attempt == 0:
                time.sleep(1.1)
                continue
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]}
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return resp.json()
            text = resp.text
            try:
                return json.loads(text)
            except Exception:
                return text
        except Exception as e:
            return {"error": str(e)}
    return {"error": "HTTP 429 after retry", "detail": "NCBI API rate limit exceeded"}


def _ncbi_params(extra=None):
    """构建NCBI E-utilities通用参数。"""
    p = {"tool": NCBI_TOOL, "email": NCBI_EMAIL, "retmode": "json"}
    if extra:
        p.update(extra)
    return p


def _clean_text(value):
    if not value:
        return ""
    if isinstance(value, dict):
        value = value.get("value", "") or ""
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_xml_all(xml, tag):
    """从XML片段提取某标签的所有文本。"""
    if not xml:
        return []
    return [unescape(t) for t in re.findall(fr"<{tag}[^>]*>(.*?)</{tag}>", xml, flags=re.S)]


def _extract_named_values(xml, section):
    """从MedGen conceptmeta中提取某节下的Name值；无Name标签时退化为节内纯文本。"""
    values = []
    for block in _extract_xml_all(xml, section):
        names = [_clean_text(x) for x in re.findall(r"<Name[^>]*>(.*?)</Name>", block, flags=re.S)]
        if names:
            values.extend([x for x in names if x])
        else:
            text = _clean_text(block)
            if text:
                values.append(text)
    return list(dict.fromkeys(values))


def _protein_short_from_long(protein):
    """p.Arg1981Ter → p.R1981*；p.Gln1756ProfsTer? → p.Q1756Pfs。"""
    if not protein:
        return ""
    m = re.match(r"p\.([A-Za-z]{3}|\*)(\d+)([A-Za-z]{3}|\*|=)?(.*)$", protein)
    if not m:
        m2 = re.search(r"(p\.[A-Z]\d+[A-Za-z*=]*(?:fs)?)", protein)
        return m2.group(1) if m2 else ""
    aa1 = AA3TO1.get(m.group(1), m.group(1)[0] if m.group(1) else "")
    pos = m.group(2)
    aa2_raw = m.group(3)
    tail = m.group(4) or ""
    aa2 = AA3TO1.get(aa2_raw, aa2_raw[0] if aa2_raw else "") if aa2_raw else ""
    if tail.lower().startswith("fs"):
        return f"p.{aa1}{pos}{aa2}fs" if aa2 else f"p.{aa1}{pos}fs"
    return f"p.{aa1}{pos}{aa2}" if aa2 else f"p.{aa1}{pos}"


# ============================================================
# MedGen搜索
# ============================================================
def cmd_medgen(args):
    """搜索MedGen，返回标准疾病名、UID、定义、同义词、遗传方式、OMIM等。"""
    term = args.query
    search_data = _get(f"{EUTILS_BASE}/esearch.fcgi", _ncbi_params({
        "db": "medgen", "term": term, "retmax": 20, "sort": "relevance"
    }))
    if isinstance(search_data, dict) and "error" in search_data:
        print(json.dumps(search_data, ensure_ascii=False, indent=2))
        return
    time.sleep(REQUEST_DELAY)
    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        print(json.dumps({
            "query": term,
            "results": [],
            "note": "MedGen未找到匹配条目。中文病名通常不被MedGen直接收录，请先做中英文映射后用英文标准病名检索。"
        }, ensure_ascii=False, indent=2))
        return

    summary_data = _get(f"{EUTILS_BASE}/esummary.fcgi", _ncbi_params({
        "db": "medgen", "id": ",".join(id_list)
    }))
    if isinstance(summary_data, dict) and "error" in summary_data:
        print(json.dumps(summary_data, ensure_ascii=False, indent=2))
        return

    results = []
    result_data = summary_data.get("result", {})
    for uid in id_list:
        entry = result_data.get(uid, {})
        if not entry:
            continue
        meta = entry.get("conceptmeta", "") or ""
        definitions = _extract_xml_all(meta, "Definition")
        synonyms = _extract_named_values(meta, "Names")
        moi = _extract_named_values(meta, "ModesOfInheritance")
        omim = _extract_xml_all(meta, "MIM")
        clinical_features = _extract_named_values(meta, "ClinicalFeatures")
        related_disorders = _extract_named_values(meta, "RelatedDisorders")
        associated_genes = _extract_named_values(meta, "AssociatedGenes")
        semantic_type = _clean_text(entry.get("semantictype"))
        results.append({
            "uid": uid,
            "concept_id": entry.get("conceptid", ""),
            "title": _clean_text(entry.get("title")),
            "semantic_type": semantic_type,
            "definition": _clean_text("; ".join(definitions))[:800],
            "synonyms": list(dict.fromkeys([_clean_text(s) for s in synonyms if _clean_text(s)]))[:20],
            "modes_of_inheritance": list(dict.fromkeys([_clean_text(x) for x in moi if _clean_text(x)])),
            "omim": list(dict.fromkeys(omim)),
            "clinical_features_sample": list(dict.fromkeys([_clean_text(x) for x in clinical_features if _clean_text(x)]))[:15],
            "related_disorders_count": len(related_disorders),
            "related_disorders_sample": related_disorders[:10],
            "associated_genes": list(dict.fromkeys([_clean_text(x) for x in associated_genes if _clean_text(x)]))[:10],
            "url": f"https://www.ncbi.nlm.nih.gov/medgen/{uid}",
            "note": "表型特异性判定请用fetch_web打开上述URL，查看RelatedDisorders关联疾病数量。"
        })
    # 二次排序：标题精确匹配 > 标题包含查询词（词首/词中）> 同义词匹配 > 疾病类型优先 > 字母序
    q_lower = term.lower().strip()
    q_words = [w for w in q_lower.split() if len(w) > 1]
    def _medgen_sort_key(r):
        t = (r.get("title") or "").lower()
        syns = [s.lower() for s in (r.get("synonyms") or [])]
        sem = (r.get("semantic_type") or "").lower()
        # exact title
        exact = 0 if t == q_lower else 1
        # exact synonym
        syn_exact = 0 if q_lower in syns else 1
        # title starts with
        prefix = 0 if t.startswith(q_lower) else 1
        # title contains as word
        contains = 0 if q_lower in t else 1
        # all query words in title
        all_words = 0 if (q_words and all(w in t for w in q_words)) else 1
        # disease/syndrome priority (findings last)
        is_finding = 1 if "finding" in sem or "laboratory" in sem else 0
        return (exact, syn_exact, prefix, contains, all_words, is_finding, t)
    results.sort(key=_medgen_sort_key)
    results = results[:10]
    print(json.dumps({"query": term, "count": len(results), "results": results}, ensure_ascii=False, indent=2))


# ============================================================
# ClinVar变异标准化
# ============================================================
def _clinvar_entry(entry):
    title = entry.get("title", "")
    acc_match = re.search(r'(NM_\d+\.\d+)', title)
    transcript = acc_match.group(1) if acc_match else ""

    # cDNA变化：优先title中括号后的c.xxx，避免把转录本前缀当成纯cDNA
    cdna = ""
    m = re.search(r'\)\s*:\s*(c\.[^\s()]+)', title)
    if m:
        cdna = m.group(1).rstrip('(),')
    else:
        m = re.search(r'(c\.\S+)', title)
        if m:
            cdna = m.group(1).rstrip('(),')

    # 蛋白变化：ClinVar esummary的top-level protein_change字段有时是多注释拼接，
    # 对标准化展示不稳定；变异主注释优先使用title中的(p.XxxYyy)，其次top-level。
    protein = ""
    pm = re.search(r'\(p\.([^)]+)\)', title)
    if pm:
        protein = "p." + pm.group(1).strip()
    else:
        pm = re.search(r'(p\.[A-Za-z]{3}\S+)', title)
        if pm:
            protein = pm.group(1).rstrip('(),')
    if not protein:
        raw_prot = _clean_text(entry.get("protein_change", ""))
        # 只在它像标准蛋白注释时采用，避免多注释拼接污染
        if re.match(r"^p\.[A-Za-z*]", raw_prot) and "," not in raw_prot:
            protein = raw_prot

    var_set_list = entry.get("variation_set") or []
    var_set = var_set_list[0] if var_set_list else {}
    if not cdna:
        raw_cdna = var_set.get("cdna_change", "")
        m = re.search(r'(c\.[^\s()]+)', str(raw_cdna))
        cdna = m.group(1).rstrip('(),') if m else ""

    protein_short = ""
    aliases = var_set.get("aliases", []) or []
    for alias in aliases:
        psm = re.search(r'(p\.[A-Z]\d+[A-Za-z*=]*)', alias)
        if psm:
            protein_short = psm.group(1)
            break
    if not protein_short:
        protein_short = _protein_short_from_long(protein)

    rs_id = ""
    for xref in var_set.get("variation_xrefs", []) or []:
        if xref.get("db_source") == "dbSNP":
            rs_id = f"rs{xref.get('db_id', '')}"
            break

    germline = entry.get("germline_classification") or {}
    clinical_significance = _clean_text(germline.get("description"))
    review_status = _clean_text(germline.get("review_status"))
    last_evaluated = _clean_text(germline.get("last_evaluated"))[:10]

    invalid_conditions = {"not provided", "not applicable", "cardiovascular phenotype", "cardiomyopathy"}
    conditions = []
    for t in germline.get("trait_set", []) or []:
        name = _clean_text(t.get("trait_name"))
        if name and name.lower() not in invalid_conditions:
            conditions.append(name)
    if not conditions:
        for t in entry.get("trait_set", []) or []:
            nested = t.get("trait_set", [{}])[0] if t.get("trait_set") else {}
            name = _clean_text(nested.get("value") or t.get("title"))
            if name and name.lower() not in invalid_conditions:
                conditions.append(name)

    # 基因组坐标
    locations = []
    for loc in var_set.get("variation_loc", []) or []:
        loc_chr = loc.get("chr", "")
        start = loc.get("start", "")
        stop = loc.get("stop", "")
        pos = start if start == stop or not stop else f"{start}-{stop}"
        if loc_chr and start:
            locations.append({
                "assembly": "GRCh38" if loc.get("assembly_name") == "GRCh38" else (
                    "GRCh37" if loc.get("assembly_name") == "GRCh37" else loc.get("assembly_name", "")),
                "chromosome": loc_chr,
                "position": pos,
                "band": loc.get("band", "")
            })

    spdi = var_set.get("canonical_spdi", "")
    if spdi:
        parts = spdi.split(":")
        if len(parts) >= 4 and not any(l["assembly"] == "GRCh38" for l in locations):
            locations.insert(0, {"assembly": "GRCh38(SPDI)", "chromosome": parts[0], "position": str(int(parts[1])+1), "ref": parts[2], "alt": parts[3]})

    return {
        "uid": entry.get("uid", ""),
        "accession": entry.get("accession", ""),
        "title": title,
        "gene": entry.get("gene_sort", ""),
        "transcript": transcript,
        "cdna_change": cdna,
        "protein_change": protein,
        "protein_short": protein_short,
        "rs_id": rs_id,
        "clinical_significance": clinical_significance,
        "review_status": review_status,
        "last_evaluated": last_evaluated,
        "conditions": list(dict.fromkeys(conditions))[:10],
        "genomic_locations": locations,
        "canonical_spdi": spdi,
        "url": f"https://www.ncbi.nlm.nih.gov/clinvar/{entry.get('accession', entry.get('uid', ''))}/"
    }


def _score_clinvar_match(item, query, gene=None, cdna=None, protein_q=None):
    title = (item.get("title") or "").lower()
    prot = (item.get("protein_change") or "").lower()
    q = (query or "").lower()
    score = 0
    if gene and gene.lower() in title:
        score += 5
    if cdna:
        norm_q = cdna.lower().replace(">", "")
        if norm_q in title:
            score += 10
        else:
            base = re.sub(r"(dup|del|ins)[a-z]+$", r"\1", norm_q)
            if base and base in title:
                score += 8
    if protein_q:
        pq = protein_q.lower().replace(">", "")
        # 三字母蛋白注释在title或protein_change中匹配
        if pq in title or pq in prot:
            score += 10
        else:
            # 尝试单字母匹配 p.Gln1756fs → p.Q1756fs
            pq_short = re.sub(r"p\.([A-Za-z]{3})", lambda m: "p." + AA3TO1.get(m.group(1).capitalize(), m.group(1)[0].upper()), pq)
            if pq_short.lower() in title or pq_short.lower() in prot:
                score += 8
    if q and q in title:
        score += 3
    if item.get("clinical_significance"):
        score += 1
    return score


def cmd_clinvar(args):
    """通过ClinVar esearch+esummary获取变异标准化信息，并在返回结果过多时按title相关性排序。"""
    term = args.query.strip()
    gene = ""
    cdna = ""
    protein_q = ""
    # GENE c.xxx
    gm = re.match(r"^([A-Za-z0-9-]+)\s+(c\.\S+)", term)
    # GENE p.XxxYyy（蛋白变化输入）
    gp = re.match(r"^([A-Za-z0-9-]+)\s+(p\.\S+)", term)
    if gm:
        gene, cdna = gm.group(1), gm.group(2).rstrip('(),')
        search_term = f"{gene}[Gene] AND {cdna}[All Fields]"
    elif gp:
        gene, protein_q = gp.group(1), gp.group(2).rstrip('(),')
        search_term = f"{gene}[Gene] AND {protein_q}[All Fields]"
    elif re.match(r"^rs\d+$", term, re.I):
        search_term = term
    elif re.match(r"^NM_\d+\.\d+:c\.\S+", term):
        search_term = term
        m = re.search(r"(c\.[^\s()]+)", term)
        if m:
            cdna = m.group(1)
    else:
        search_term = term
        m = re.search(r"(c\.[^\s()]+)", term)
        if m:
            cdna = m.group(1)

    search_data = _get(f"{EUTILS_BASE}/esearch.fcgi", _ncbi_params({
        "db": "clinvar", "term": search_term, "retmax": 10
    }))
    if isinstance(search_data, dict) and "error" in search_data:
        print(json.dumps(search_data, ensure_ascii=False, indent=2))
        return
    time.sleep(REQUEST_DELAY)
    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        print(json.dumps({"query": term, "results": [], "note": "ClinVar未找到该变异"}, ensure_ascii=False, indent=2))
        return

    summary_data = _get(f"{EUTILS_BASE}/esummary.fcgi", _ncbi_params({
        "db": "clinvar", "id": ",".join(id_list)
    }))
    if isinstance(summary_data, dict) and "error" in summary_data:
        print(json.dumps(summary_data, ensure_ascii=False, indent=2))
        return

    result_data = summary_data.get("result", {})
    parsed = []
    for uid in id_list:
        entry = result_data.get(uid, {})
        if entry:
            parsed.append(_clinvar_entry(entry))

    # 过滤：如果用户给了基因，优先保留该基因；给了cDNA，优先保留title含cDNA/标准化前缀
    filtered = parsed
    if gene:
        same_gene = [x for x in parsed if x.get("gene", "").upper() == gene.upper()]
        if same_gene:
            filtered = same_gene
    if cdna:
        exact_cdna = cdna.lower().replace(">", "")
        cdnas = []
        for x in filtered:
            t = (x.get("title") or "").lower().replace(">", "")
            xcdna = (x.get("cdna_change") or "").lower().replace(">", "")
            if exact_cdna in t or exact_cdna in xcdna:
                cdnas.append(x)
            else:
                base = re.sub(r"(dup|del|ins)[a-z]+$", r"\1", exact_cdna)
                if base and (base in t or base in xcdna):
                    cdnas.append(x)
        if cdnas:
            filtered = cdnas

    filtered.sort(key=lambda x: _score_clinvar_match(x, term, gene, cdna, protein_q), reverse=True)
    filtered = filtered[:5]
    print(json.dumps({
        "query": term,
        "search_term_used": search_term,
        "count": len(filtered),
        "results": filtered,
        "note": "已按基因名和HGVS变异名做相关性排序；若用户输入c.5266dupC而ClinVar标准名为c.5266dup，以ClinVar title为准。"
    }, ensure_ascii=False, indent=2))


# ============================================================
# NCBI Books (GeneReviews)
# ============================================================
def _extract_books_genes(chapter_title, is_genereviews):
    """GeneReviews章节通常是 FBN1-Related Marfan Syndrome，提取首个基因名。非GeneReviews不强行猜基因。"""
    genes = []
    if is_genereviews:
        m = re.match(r"^([A-Z0-9]+?)(?:-Related|-related|-Related\b|-related\b|\s)", chapter_title)
        if m and m.group(1) not in BOOKS_GENE_STOP and not m.group(1).isdigit():
            genes.append(m.group(1))
    return list(dict.fromkeys(genes))[:5]


def cmd_books(args):
    """搜索NCBI Bookshelf，优先GeneReviews，返回章节信息。"""
    term = args.query.strip()
    search_term = f"{term}[Title]"
    search_data = _get(f"{EUTILS_BASE}/esearch.fcgi", _ncbi_params({
        "db": "books", "term": search_term, "retmax": 10, "sort": "relevance"
    }))
    if isinstance(search_data, dict) and "error" in search_data:
        print(json.dumps(search_data, ensure_ascii=False, indent=2))
        return
    time.sleep(REQUEST_DELAY)
    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        search_data = _get(f"{EUTILS_BASE}/esearch.fcgi", _ncbi_params({
            "db": "books", "term": term, "retmax": 10, "sort": "relevance"
        }))
        if isinstance(search_data, dict) and "error" in search_data:
            print(json.dumps(search_data, ensure_ascii=False, indent=2))
            return
        id_list = search_data.get("esearchresult", {}).get("idlist", [])

    if not id_list:
        print(json.dumps({"query": term, "results": [], "note": "Books未找到匹配条目"}, ensure_ascii=False, indent=2))
        return

    summary_data = _get(f"{EUTILS_BASE}/esummary.fcgi", _ncbi_params({
        "db": "books", "id": ",".join(id_list)
    }))
    if isinstance(summary_data, dict) and "error" in summary_data:
        print(json.dumps(summary_data, ensure_ascii=False, indent=2))
        return

    results = []
    result_data = summary_data.get("result", {})
    for uid in id_list:
        entry = result_data.get(uid, {})
        if not entry:
            continue
        chapter_title = _clean_text(entry.get("title", ""))
        if not chapter_title or chapter_title.upper().startswith("TABLE") or chapter_title.upper().startswith("FIGURE"):
            continue
        book_acc = entry.get("bookaccessionid", "")
        is_genereviews = book_acc == "NBK1116"
        if is_genereviews:
            book_title = "GeneReviews"
        else:
            bookinfo = entry.get("bookinfo", "")
            book_match = re.search(r"<Title>([^<]+)</Title>", bookinfo or "", flags=re.S)
            book_title = _clean_text(book_match.group(1) if book_match else entry.get("book", ""))
        chapter_acc = entry.get("accessionid", "")
        url = f"https://www.ncbi.nlm.nih.gov/books/{chapter_acc}/" if chapter_acc else f"https://www.ncbi.nlm.nih.gov/books/{uid}/"
        results.append({
            "uid": uid,
            "accession": chapter_acc,
            "book_title": book_title,
            "chapter_title": chapter_title,
            "is_genereviews": is_genereviews,
            "genes": _extract_books_genes(chapter_title, is_genereviews),
            "pubdate": _clean_text(entry.get("pubdate", ""))[:10],
            "url": url
        })

    results.sort(key=lambda x: (not x["is_genereviews"], x["chapter_title"]))
    results = results[:5]
    print(json.dumps({
        "query": term,
        "count": len(results),
        "results": results,
        "note": "用fetch_web获取URL页面提取疾病概述、penetrance章节、治疗/预后/发病年龄等。"
    }, ensure_ascii=False, indent=2))


# ============================================================
# ClinGen基因-疾病有效性
# ============================================================
def cmd_clingen(args):
    """查询ClinGen基因-疾病有效性和剂量敏感性。"""
    gene = args.query.strip()
    url = "https://search.clinicalgenome.org/kb/gene-dosage"
    params = {"page": 1, "size": 25, "search": gene, "type": "GENE"}
    try:
        resp = requests.get(url, params=params, timeout=30, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in (data.get("_embedded", {}) or {}).get("gene_dosage", []) or []:
                item_gene = item.get("gene", "")
                if gene.upper() == item_gene.upper() or gene.upper() in item_gene.upper():
                    haplo = item.get("haploinsufficiency") or {}
                    triplo = item.get("triplosensitivity") or {}
                    results.append({
                        "gene": item_gene,
                        "disease": item.get("disease", ""),
                        "dosage_haplo": haplo.get("assertion", ""),
                        "dosage_triplo": triplo.get("assertion", ""),
                        "classification_date": item.get("classification_date", "")
                    })
            if results:
                print(json.dumps({"gene": gene, "count": len(results), "results": results}, ensure_ascii=False, indent=2))
                return
        print(json.dumps({
            "gene": gene,
            "results": [],
            "fallback_url": f"https://search.clinicalgenome.org/kb/gene-dosage?page=1&size=25&search={gene}",
            "note": f"ClinGen API未返回可解析JSON（HTTP {resp.status_code}）。请用fetch_web打开fallback_url查看基因-疾病有效性和剂量敏感性。"
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({
            "gene": gene,
            "results": [],
            "fallback_url": f"https://search.clinicalgenome.org/kb/gene-dosage?page=1&size=25&search={gene}",
            "note": f"ClinGen API直接请求失败（{str(e)[:120]}）。请用fetch_web打开fallback_url解析基因-疾病有效性和剂量敏感性。"
        }, ensure_ascii=False, indent=2))


# ============================================================
# PubMed检索
# ============================================================
def cmd_pubmed(args):
    """PubMed检索，返回文献列表（PMID、标题、作者、期刊、年份）。"""
    term = args.query.strip()
    count = args.count if args.count else 5

    # 兼容用户/旧指令写 la[chinese]：PubMed正确字段是 Chinese[Language] / chi[la] / chinese[lang]
    if re.search(r"\bla\[chinese\]", term, re.I):
        term = re.sub(r"\s*AND\s+la\[chinese\]", " AND Chinese[Language]", term, flags=re.I)
        term = term.replace("la[chinese]", "Chinese[Language]")

    search_data = _get(f"{EUTILS_BASE}/esearch.fcgi", _ncbi_params({
        "db": "pubmed", "term": term, "retmax": count, "sort": "relevance"
    }))
    if isinstance(search_data, dict) and "error" in search_data:
        print(json.dumps(search_data, ensure_ascii=False, indent=2))
        return
    time.sleep(REQUEST_DELAY)
    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        print(json.dumps({"query": term, "count": 0, "results": [], "note": "PubMed未找到相关文献"}, ensure_ascii=False, indent=2))
        return

    summary_data = _get(f"{EUTILS_BASE}/esummary.fcgi", _ncbi_params({
        "db": "pubmed", "id": ",".join(id_list)
    }))
    if isinstance(summary_data, dict) and "error" in summary_data:
        print(json.dumps(summary_data, ensure_ascii=False, indent=2))
        return

    results = []
    result_data = summary_data.get("result", {})
    for pmid in id_list:
        entry = result_data.get(pmid, {})
        if not entry:
            continue
        authors = [a.get("name", "") for a in (entry.get("authors") or [])[:5]]
        if len(entry.get("authors") or []) > 5:
            authors.append("et al.")
        results.append({
            "pmid": pmid,
            "title": _clean_text(entry.get("title", "")),
            "authors": ", ".join(authors),
            "journal": _clean_text(entry.get("fulljournalname", entry.get("source", ""))),
            "year": _clean_text(entry.get("pubdate", ""))[:4],
            "doi": next((aid.get("value", "") for aid in entry.get("articleids", []) if aid.get("idtype") == "doi"), ""),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        })
    print(json.dumps({"query": term, "count": len(results), "results": results, "note": "需要摘要时用fetch_web获取URL页面"}, ensure_ascii=False, indent=2))


# ============================================================
# Mutalyzer HGVS标准化
# ============================================================
def cmd_mutalyzer(args):
    """调用Mutalyzer API校验和标准化HGVS描述。"""
    hgvs = args.query.strip()
    url = f"https://mutalyzer.nl/api/normalize/{hgvs}"
    try:
        resp = requests.get(url, timeout=30, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "input": hgvs,
                "normalized_description": data.get("normalized_description", ""),
                "corrected_description": data.get("corrected_description", data.get("normalized_description", "")),
                "reference_id": data.get("reference_id", data.get("assembly_name", "")),
                "seq_id": data.get("seq_id", ""),
                "mutalyzer_url": f"https://mutalyzer.nl/normalizer?description={hgvs}"
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({
                "input": hgvs,
                "error": f"HTTP {resp.status_code}",
                "detail": resp.text[:500],
                "mutalyzer_url": f"https://mutalyzer.nl/normalizer?description={hgvs}"
            }, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({
            "input": hgvs,
            "error": str(e),
            "mutalyzer_url": f"https://mutalyzer.nl/normalizer?description={hgvs}",
            "note": "沙箱SSL证书可能不可用；请用fetch_web打开mutalyzer_url或在浏览器/Mutalyzer官网复核HGVS语法。"
        }, ensure_ascii=False, indent=2))


# ============================================================
# 命令行入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="疾病信息查询_jb — 数据查询脚本")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    p_medgen = subparsers.add_parser("medgen", help="搜索MedGen")
    p_medgen.add_argument("query", help="疾病名或表型名")

    p_clinvar = subparsers.add_parser("clinvar", help="ClinVar变异标准化查询")
    p_clinvar.add_argument("query", help="变异任意形式（rs号/基因名+cDNA/蛋白变化等）")

    p_books = subparsers.add_parser("books", help="NCBI Books (GeneReviews)搜索")
    p_books.add_argument("query", help="疾病名或基因名")

    p_clingen = subparsers.add_parser("clingen", help="ClinGen基因-疾病有效性查询")
    p_clingen.add_argument("query", help="基因名")

    p_pubmed = subparsers.add_parser("pubmed", help="PubMed文献检索")
    p_pubmed.add_argument("query", help="PubMed检索词")
    p_pubmed.add_argument("--count", type=int, default=5, help="返回文献数量，默认5")

    p_mut = subparsers.add_parser("mutalyzer", help="Mutalyzer HGVS校验标准化")
    p_mut.add_argument("query", help="HGVS描述")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "medgen": cmd_medgen,
        "clinvar": cmd_clinvar,
        "books": cmd_books,
        "clingen": cmd_clingen,
        "pubmed": cmd_pubmed,
        "mutalyzer": cmd_mutalyzer,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
