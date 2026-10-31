# -*- coding: utf-8 -*-
"""变异标准化脚本 - 从 SKILL.md 内嵌脚本提取运行"""
import re
import json
import subprocess
import sys
from urllib.parse import urlencode
from pyliftover import LiftOver

BASE_URL = "https://api.genebe.net/cloud/api-public/v1"

AA3_TO_AA1 = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
    "Glu": "E", "Gln": "Q", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
    "Ter": "*", "Asx": "B", "Glx": "Z", "Xaa": "X", "Xle": "J",
    "Sec": "U", "Pyl": "O",
}

def protein_3to1(hgvs_p_full):
    if not hgvs_p_full:
        return hgvs_p_full
    def replace_aa(match):
        aa3 = match.group(0)
        return AA3_TO_AA1.get(aa3, aa3)
    return re.sub(r'[A-Z][a-z]{2}', replace_aa, hgvs_p_full)

def exon_label(csq):
    er = csq.get("exon_rank"); ec = csq.get("exon_count"); ir = csq.get("intron_rank")
    if er is not None:
        return f"exon {er}/{ec}" if ec else f"exon {er}"
    if ir is not None:
        it = (ec - 1) if ec else None
        return f"intron {ir}/{it}" if it else f"intron {ir}"
    return ""

def _display_width(s):
    return sum(2 if ('\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f') else 1 for c in s)

def _pad_right(s, width):
    return s + ' ' * max(0, width - _display_width(s))

def curl_get(url, params=None):
    if params:
        url = f"{url}?{urlencode(params)}"
    try:
        result = subprocess.run(["curl", "-s", "--max-time", "30", url], capture_output=True, text=True, timeout=35)
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        else:
            return {"error": f"curl failed: {result.stderr}"}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except json.JSONDecodeError:
        return {"error": "parse fail"}

def get_gene_aliases(gene_symbol):
    url = f"https://rest.genenames.org/fetch/symbol/{gene_symbol}"
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        docs = data.get("response", {}).get("docs", [])
        if not docs:
            return {"current": gene_symbol, "aliases": []}
        doc = docs[0]
        return {"current": doc.get("symbol", gene_symbol), "aliases": doc.get("alias_symbol", []) or []}
    except Exception as e:
        return {"current": gene_symbol, "aliases": [], "error": str(e)}

def _parse_raw_coords(query_id):
    m = re.match(r'^(?:chr)?(\w+)[:\-](\d+)[:>\-](\w+)[:>\-](\w+)$', query_id, re.IGNORECASE)
    if m:
        return m.group(1), int(m.group(2)), m.group(3), m.group(4)
    return None

def convert_variant(variant_str):
    url = f"{BASE_URL}/convert"
    query_id = variant_str.strip()
    is_hg19 = False
    query_id = query_id.replace('：', ':').replace('，', ',').replace('＞', '>')
    query_id = re.sub(r'^([A-Za-z0-9_-]+)\s+(?![cpmgr]\.)(\d)', r'\1 c.\2', query_id)
    if re.match(r'^[A-Za-z0-9_-]+\s+c\.\d+$', query_id):
        return {"error": f"incomplete format: {variant_str}"}
    hg19_param = re.compile(r'[&?]genome=hg19\b', re.IGNORECASE)
    hg19_keyword = re.compile(r'(?:^|\s)hg19(?:\s|$)', re.IGNORECASE)
    if hg19_param.search(query_id) or hg19_keyword.search(query_id):
        is_hg19 = True
        query_id = hg19_param.sub('', query_id)
        query_id = hg19_keyword.sub(' ', query_id).strip()
    if is_hg19:
        parsed = _parse_raw_coords(query_id)
        if parsed:
            hg19_chr, hg19_pos, hg19_ref, hg19_alt = parsed
            try:
                lo = LiftOver('hg19', 'hg38')
                result = lo.convert_coordinate(f"chr{hg19_chr}", int(hg19_pos))
                if result and len(result[0]) >= 2:
                    return {"chr": result[0][0].replace("chr",""), "pos": result[0][1], "ref": hg19_ref, "alt": hg19_alt, "genome": "hg38", "input_genome": "hg19", "converted_from_hg19": True}
                else:
                    return {"error": f"liftover fail chr{hg19_chr}:{hg19_pos}"}
            except Exception as e:
                return {"error": f"liftover exception: {str(e)}"}
    params = {"id": query_id, "genome": "hg38"}
    result = curl_get(url, params)
    if "error" in result:
        return result
    if isinstance(result, list) and len(result) > 0:
        first = result[0]
        if "variants" in first and len(first["variants"]) > 0:
            v = first["variants"][0]
            return {"chr": v.get("chr",""), "pos": v.get("pos",""), "ref": v.get("ref",""), "alt": v.get("alt",""), "genome": v.get("genome","hg38"), "input_genome": "hg19" if is_hg19 else "hg38"}
    if re.match(r'(?i)MT-', query_id) and re.search(r'(?i)\bc\.', query_id):
        return {"error": f"mt gene c. prefix not supported: {variant_str}"}
    return {"error": f"unrecognized format: {variant_str}"}

def get_variant_data(chr_val, pos, ref, alt, genome="hg38"):
    url = f"{BASE_URL}/variant"
    params = {"chr": chr_val, "pos": pos, "ref": ref, "alt": alt, "useRefseq": "true", "useEnsembl": "false", "genome": genome}
    result = curl_get(url, params)
    if "error" in result:
        return result
    if isinstance(result, dict) and "variants" in result and len(result["variants"]) > 0:
        return result["variants"][0]
    return {}

def classify_variant_class(csq):
    """从单条 consequence 判定变异大类（与 SKILL.md classify_variant_class 对齐）。
    返回 variant_class ∈ missense/nonsense/synonymous/frameshift/inframe/splicing/noncoding/other_protein/None
    """
    if not csq:
        return None
    effects = [str(e).lower() for e in (csq.get("consequences") or [])]
    if not effects:
        return None
    joined = "|".join(effects)
    if any(k in joined for k in ("frameshift_variant", "frameshift")):
        return "frameshift"
    if any(k in joined for k in ("inframe_deletion", "inframe_insertion", "inframe_variant")):
        return "inframe"
    if "missense_variant" in joined:
        return "missense"
    if any(k in joined for k in ("stop_gained", "nonsense")):
        return "nonsense"
    if "synonymous_variant" in joined or "stop_retained_variant" in joined:
        return "synonymous"
    if any(k in joined for k in ("splice_donor", "splice_acceptor", "splice_region", "splicing")):
        return "splicing"
    if any(k in joined for k in ("non_coding", "noncoding", "downstream_gene", "upstream_gene",
                                 "intron_variant", "intergenic", "utr", "regulatory", "transcript_")):
        return "noncoding"
    return "other_protein"


def standardize_variant(variant_input):
    """归一化变异并返回结构化结果 dict（G1 门禁输入契约）。
    保留原 print 输出（兼容），同时返回含 identity_status/variant_class/protein_change 的 dict。
    identity_status: annotated=已确认 / data_gap=缺数据继续 / blocked=无法判定暂停
    """
    result = {"gene": "", "hgvs_c": "", "hgvs_p": "",
              "identity_status": "data_gap", "variant_class": "", "protein_change": "",
              "error": "", "notes": []}
    print(f"### QUERY: {variant_input}")
    coord = convert_variant(variant_input)
    if "error" in coord:
        result["error"] = coord["error"]
        result["identity_status"] = "blocked"
        print("CONVERT_ERROR:", coord["error"]); return result
    variant_data = get_variant_data(coord["chr"], coord["pos"], coord["ref"], coord["alt"])
    if "error" in variant_data:
        result["error"] = variant_data["error"]
        result["identity_status"] = "blocked"
        print("VARIANT_ERROR:", variant_data["error"]); return result
    consequences = variant_data.get("consequences", [])
    if not consequences:
        result["error"] = "NO_CONSEQUENCES"
        result["identity_status"] = "blocked"
        print("NO CONSEQUENCES"); return result
    gene_symbol = consequences[0].get("gene_symbol", "")
    result["gene"] = gene_symbol
    alias_info = {"current": gene_symbol, "aliases": []}
    if gene_symbol:
        alias_info = get_gene_aliases(gene_symbol)
    rs_id = variant_data.get("dbsnp", "") or ""
    print("COORD:", json.dumps(coord, ensure_ascii=False))
    print("RSID:", rs_id)
    print("ALIAS:", json.dumps(alias_info, ensure_ascii=False))
    print("---MANE / ALL TRANSCRIPTS---")
    mane_tx = None; fallback_tx = None
    for csq in consequences:
        tx = csq.get("transcript", "")
        if not str(tx).startswith("NM_"):
            continue
        mane = csq.get("mane_select")
        if mane and mane_tx is None:
            mane_tx = csq
        if fallback_tx is None:
            fallback_tx = csq
        print(json.dumps({
            "transcript": tx, "mane": "MANE-SELECT" if mane else "", "hgvs_c": csq.get("hgvs_c", "-"),
            "hgvs_p": csq.get("hgvs_p", "-"), "effects": csq.get("consequences", []),
            "exon": exon_label(csq), "gene": csq.get("gene_symbol", "")
        }, ensure_ascii=False))
    print("RAW_TOP_KEYS:", json.dumps({k: variant_data.get(k) for k in ["dbsnp", "variation", "chromosome", "start", "end"] if k in variant_data}, ensure_ascii=False))
    primary = mane_tx or fallback_tx
    if primary is None:
        result["error"] = "NO_NM_TRANSCRIPT"
        result["identity_status"] = "blocked"
        return result
    vclass = classify_variant_class(primary)
    hgvs_c = primary.get("hgvs_c", "") or ""
    hgvs_p = primary.get("hgvs_p", "") or ""
    result.update({
        "gene": primary.get("gene_symbol") or gene_symbol,
        "hgvs_c": hgvs_c,
        "hgvs_p": hgvs_p,
        "variant_class": vclass or "",
        "protein_change": protein_3to1(hgvs_p) if hgvs_p else "",
    })
    if vclass is None:
        result["identity_status"] = "data_gap"
        result["notes"].append("consequence 无法判定变异类型，标 data_gap，按缺数据继续")
    else:
        result["identity_status"] = "annotated"
    return result


if __name__ == "__main__":
    standardize_variant(sys.argv[1])
