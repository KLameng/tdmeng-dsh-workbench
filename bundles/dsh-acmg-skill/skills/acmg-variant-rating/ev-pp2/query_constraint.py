import sys
import io
import csv
import os
import urllib.request
import ssl


V4_URL = "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.0/constraint/gnomad.v4.0.constraint_metrics.tsv"
V2_URL = "https://storage.googleapis.com/gcp-public-data--gnomad/release/2.1.1/constraint/gnomad.v2.1.1.lof_metrics.by_transcript.txt.bgz"
EXAC_RMC_URL = "https://storage.googleapis.com/gcp-public-data--gnomad/legacy/exac_browser/regional_missense_constraint.tsv"

# SSL 证书校验（安全优先，v1.0.1 修复：默认校验证书，消除中间人注入风险）
# 之前为"sandbox SSL date mismatch"无条件关闭校验(check_hostname=False/CERT_NONE)，属安全欠账。
# 现默认恢复校验；仅在证书确实错位、且显式设置环境变量 GNOMAD_INSECURE=1 时才临时降级。
if os.environ.get("GNOMAD_INSECURE", "").lower() in ("1", "true", "yes"):
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE
else:
    _SSL_CTX = ssl.create_default_context()

# 落盘缓存（v1.0.1 新增，P1-3）：gnomAD 约束数据整表较大（v4 约 82MB / v2 约 13MB），
# 首次下载后落盘缓存，后续查询直接读本地缓存，避免单次 95MB 重复下载。--refresh 强制更新。
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")


def _cache_path(name):
    return os.path.join(_CACHE_DIR, name)


def _load(url, name, timeout, refresh):
    """下载 URL 并落盘缓存；缓存存在且未 --refresh 时直接读缓存。返回 bytes。"""
    path = _cache_path(name)
    if not refresh and os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    os.makedirs(_CACHE_DIR, exist_ok=True)
    resp = urllib.request.urlopen(url, timeout=timeout, context=_SSL_CTX)
    data = resp.read()
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    print(f"  [cache] downloaded -> {path} ({len(data)} bytes)")
    return data


def query_v4(gene, refresh=False):
    """Query gnomAD v4.0 constraint metrics for a gene."""
    print(f"--- gnomAD v4.0 Constraint Metrics (gene: {gene}) ---")
    try:
        text = _load(V4_URL, "gnomad_v4_constraint.tsv", 60, refresh).decode("utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to download/load v4 data: {e}")
        return

    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    found = False
    for row in reader:
        if row.get("gene", "").upper() == gene.upper():
            found = True
            print(f"  Gene: {row.get('gene')}")
            print(f"  Transcript: {row.get('transcript')}")
            print(f"  MANE Select: {row.get('mane_select', 'N/A')}")
            print(f"  LOF:")
            print(f"    pL.I: {row.get('lof.pLI', 'N/A')}")
            print(f"    obs: {row.get('lof.obs', 'N/A')}")
            print(f"    exp: {row.get('lof.exp', 'N/A')}")
            print(f"    o/e: {row.get('lof.oe', 'N/A')}")
            print(f"    o/e CI lower: {row.get('lof.oe_ci.lower', 'N/A')}")
            print(f"    o/e CI upper (LOEUF): {row.get('lof.oe_ci.upper', 'N/A')}")
            print(f"  Missense:")
            print(f"    obs: {row.get('mis.obs', 'N/A')}")
            print(f"    exp: {row.get('mis.exp', 'N/A')}")
            print(f"    o/e: {row.get('mis.oe', 'N/A')}")
            print(f"    o/e CI lower: {row.get('mis.oe_ci.lower', 'N/A')}")
            print(f"    o/e CI upper: {row.get('mis.oe_ci.upper', 'N/A')}")
            print(f"    Z-score: {row.get('mis.z_score', 'N/A')}")
            print(f"  Synonymous:")
            print(f"    obs: {row.get('syn.obs', 'N/A')}")
            print(f"    exp: {row.get('syn.exp', 'N/A')}")
            print(f"    o/e: {row.get('syn.oe', 'N/A')}")
            break

    if not found:
        print(f"  [NOT FOUND] Gene '{gene}' not found in gnomAD v4.0 constraint dataset.")


def query_v2(gene, refresh=False):
    """Query gnomAD v2.1.1 constraint metrics for a gene."""
    print(f"\n--- gnomAD v2.1.1 Constraint Metrics (gene: {gene}) ---")
    try:
        import gzip
        raw = _load(V2_URL, "gnomad_v2_lof_metrics.bgz", 120, refresh)
        text = gzip.decompress(raw).decode("utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to download/load v2 data: {e}")
        return

    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    # Collect all matching rows; prefer canonical, fallback to most observed missense
    canonical_row = None
    best_row = None
    best_obs = -1
    for row in reader:
        if row.get("gene", "").upper() != gene.upper():
            continue
        if row.get("canonical", "").lower() == "true":
            canonical_row = row
        try:
            obs = int(row.get("obs_mis", 0))
        except ValueError:
            obs = 0
        if obs > best_obs:
            best_obs = obs
            best_row = row

    target = canonical_row or best_row
    if not target:
        print(f"  [NOT FOUND] Gene '{gene}' not found in gnomAD v2.1.1 constraint dataset.")
        return

    is_canonical = target is canonical_row
    tag = " (canonical)" if is_canonical else " (longest transcript, no canonical marked)"
    print(f"  Gene: {target.get('gene')}")
    print(f"  Transcript: {target.get('transcript')}{tag}")
    print(f"  LOF:")
    print(f"    obs: {target.get('obs_lof', 'N/A')}")
    print(f"    exp: {target.get('exp_lof', 'N/A')}")
    print(f"    o/e: {target.get('oe_lof', 'N/A')}")
    print(f"    o/e CI lower: {target.get('oe_lof_lower', 'N/A')}")
    print(f"    o/e CI upper (LOEUF): {target.get('oe_lof_upper', 'N/A')}")
    print(f"    pLI: {target.get('pLI', 'N/A')}")
    print(f"  Missense:")
    print(f"    obs: {target.get('obs_mis', 'N/A')}")
    print(f"    exp: {target.get('exp_mis', 'N/A')}")
    print(f"    o/e: {target.get('oe_mis', 'N/A')}")
    print(f"    o/e CI lower: {target.get('oe_mis_lower', 'N/A')}")
    print(f"    o/e CI upper: {target.get('oe_mis_upper', 'N/A')}")
    print(f"    Z-score: {target.get('mis_z', 'N/A')}")
    print(f"  Synonymous:")
    print(f"    obs: {target.get('obs_syn', 'N/A')}")
    print(f"    exp: {target.get('exp_syn', 'N/A')}")
    print(f"    o/e: {target.get('oe_syn', 'N/A')}")


def query_exac_rmc(gene, refresh=False):
    """Query ExAC regional missense constraint for a gene."""
    print(f"\n--- ExAC Regional Missense Constraint (gene: {gene}) ---")
    try:
        text = _load(EXAC_RMC_URL, "exac_regional_missense_constraint.tsv", 60, refresh).decode("utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to download/load ExAC RMC data: {e}")
        return

    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    found = False
    for row in reader:
        if row.get("gene", "").upper() == gene.upper():
            found = True
            print(f"  Gene: {row.get('gene')}")
            print(f"  Transcript: {row.get('transcript', 'N/A')}")
            print(f"  Region: {row.get('region_name', 'N/A')}")
            print(f"  Chromosome: {row.get('chr', 'N/A')}")
            print(f"  Genomic range: {row.get('genomic_start', 'N/A')}-{row.get('genomic_end', 'N/A')}")
            print(f"  Amino acids: {row.get('amino_acids', 'N/A')}")
            print(f"  Observed missense: {row.get('obs_mis', 'N/A')}")
            print(f"  Expected missense: {row.get('exp_mis', 'N/A')}")
            print(f"  Obs/Exp: {row.get('obs_exp', 'N/A')}")
            print(f"  Chi-sq diff (null): {row.get('chisq_diff_null', 'N/A')}")
            print("  ---")

    if not found:
        print(f"  [NOT FOUND] Gene '{gene}' not in ExAC RMC dataset (only 2701 genes have RMC data).")


def main():
    if len(sys.argv) < 2:
        print("Usage: python query_constraint.py <gene_symbol> [--v4] [--v2] [--exac-rmc] [--all] [--refresh]")
        print("  Default (no flags): query all three datasets")
        print("  --refresh: force re-download (ignore disk cache)")
        sys.exit(1)

    gene = sys.argv[1]
    args = sys.argv[2:]
    refresh = "--refresh" in args
    flags = set(a for a in args if a != "--refresh")
    if not flags:
        flags = {"--all"}

    if "--all" in flags or not flags:
        query_v4(gene, refresh)
        query_v2(gene, refresh)
        query_exac_rmc(gene, refresh)
    else:
        if "--v4" in flags:
            query_v4(gene, refresh)
        if "--v2" in flags:
            query_v2(gene, refresh)
        if "--exac-rmc" in flags:
            query_exac_rmc(gene, refresh)


if __name__ == "__main__":
    main()
