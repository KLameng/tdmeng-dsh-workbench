#!/usr/bin/env python3
"""变异文献检索-查患者：8路多路文献检索引擎（v17）

检索路径：HGMD, ClinVar elink, PubTator 3.0, LitSense, PubMed,
        OpenAlex, Semantic Scholar, Europe PMC

v17 变更：
- 新增 LLM 结构化提取：8字段（基因型/反式变异/de novo/表型/表型一致性/生化指标/家系/父母基因型）批量提取
- 新增 HGMD 变异数据库调用（subprocess），匹配目标变异并补充 PMID
- 429限流优化：退避3s起/5次重试/2.5倍因子/EUTILS 0.5s；全局>50次自动跳过OpenAlex/S2
- 缩写歧义处理：歧义基因名（DMD/RET/MYC等）上下文验证，标注ambiguous_match
- p.?退化处理：深内含子/非编码区变异增强cDNA策略，>300篇时警告基因级召回

v16 变更：
- 移除 LitVar2 搜索通道
- 3个Bug修复：PubTator Entity ID跨基因假阳性、LitSense别名截断、OpenAlex *字符编码
- 3个零成本预过滤：PubTator基因名精确匹配、LitSense词边界过滤、S2变异签名匹配
- 新增分层过滤框架：<50篇LLM精筛，>=50篇关键词快速过滤

模式：
  all / hgmd / clinvar / pubtator / litsense / pubmed /
  openalex / semantic_scholar / europepmc  —  文献检索（v17，新增HGMD）
  abstract  —  批量获取摘要
  fulltext  —  获取全文
"""

import re
import sys
import json
import time
import argparse
import xml.etree.ElementTree as ET
from urllib.parse import quote

from coze_workload_identity import requests
import requests as _std_requests  # 标准 requests，用于避开代理限速的 API（OpenAlex 等）


# ---------------------------------------------------------------------------
# LLM 闸门（v1.5.0 新增，统一所有 LLM 调用的"不静默出口"）
# 铁律：LLM 不可用/未配置时，禁止静默降级为关键词过滤，必须硬中断并引导配置 KEY。
# 代码层面弹不出系统弹窗，引导由承载平台（AI 助手/宿主）读取本异常携带的指引文案后接管。
# 2026-10-22 用户拍板：启动即校验 + 全局所有 LLM 调用统一走本闸门 + 引导随包走。
# ---------------------------------------------------------------------------

class LLMConfigError(RuntimeError):
    """LLM 配置缺失或调用失败的统一异常。

    携带完整配置指引，供任何承载平台（豆包或其他 AI 助手）读取后引导用户配置 KEY。
    这是"不静默出口"的强制实现：宁可中断评级，也不悄悄退化为关键词过滤。
    """

    @staticmethod
    def _guide_text() -> str:
        return (
            "\n[LLM 闸门] 本技能依赖 LLM 通道做文献精筛与结构化字段提取（评级必需），"
            "当前未配置可用 Key，评级已中断，请配置后重跑。\n"
            "（说明：本闸门不会静默降级为关键词过滤——那会显著削弱评级质量，"
            "故一律中断并引导你完成配置。）\n\n"
            "请配置以下 3 个环境变量（任一 OpenAI 兼容平台通用：火山方舟 / DeepSeek / "
            "智谱 / Kimi / 通义 / OpenAI 等）：\n"
            "  1. LLM_BASE_URL  平台 OpenAI 兼容 base_url，例如\n"
            "     方舟: https://ark.cn-beijing.volces.com/api/v3\n"
            "     DeepSeek: https://api.deepseek.com/v1\n"
            "  2. LLM_MODEL     模型名，例如 ep-2025xxxx 或 deepseek-chat 或 glm-4\n"
            "  3. LLM_API_KEY   平台 API Key（在对应平台控制台创建）\n\n"
            "获取路径示例（火山方舟）:\n"
            "  登录 https://console.volcengine.com/ark → 开通方舟 → 左侧「API Key 管理」"
            "→ 创建 API Key（ark- 开头，仅显示一次）。\n\n"
            "配置方法（示例，按承载平台调整）:\n"
            "  Windows:  setx LLM_BASE_URL \"https://ark.cn-beijing.volces.com/api/v3\"\n"
            "            setx LLM_MODEL \"<你的模型名>\"\n"
            "            setx LLM_API_KEY \"<你的Key>\"\n"
            "  macOS/Linux: export LLM_BASE_URL=... 并写入 shell 配置。\n\n"
            "配置完成后重新运行本技能即可正常使用。"
        )

    def __init__(self, msg: str = ""):
        super().__init__((msg + self._guide_text()).strip())


def _ensure_llm_env() -> None:
    """启动即校验 LLM 环境变量，缺失/不完整时抛 LLMConfigError 硬中断。

    判定口径：
    - 通用兼容通道（LLM_BASE_URL/LLM_MODEL/LLM_API_KEY）任一缺失 → 不满足；
    - 或方舟专用通道（ARK_API_KEY / COZE_ARK_API_KEY 任一）可用 → 满足（向后兼容）；
    - 两通道都不可用 → raise LLMConfigError。
    CodeAct SDK（sdk.call_llm）为宿主注入通道，无环境变量校验（调用时再判），不在此前置判断。
    """
    import os
    base = os.environ.get("LLM_BASE_URL", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    ark_key = os.environ.get("ARK_API_KEY", "").strip() or \
        os.environ.get("COZE_ARK_API_KEY", "").strip()

    if (base and model and api_key) or ark_key:
        return  # 任一通道已配置，放行
    raise LLMConfigError(
        "[LLM 闸门] 启动校验未通过：未检测到可用的 LLM 通道"
        "（通用兼容通道需 LLM_BASE_URL/LLM_MODEL/LLM_API_KEY，"
        "或方舟通道需 ARK_API_KEY/COZE_ARK_API_KEY）。"
    )


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

# API 限速（秒）
EUTILS_SLEEP = 0.5    # NCBI E-utilities: 2次/秒（v17: 从0.35s增加到0.5s，降低限流风险）
PUBTATOR_SLEEP = 0.35  # PubTator: 3次/秒
GENERIC_SLEEP = 0.2   # 其他 API 基础间隔
SEMANTIC_SCHOLAR_SLEEP = 1.0  # Semantic Scholar: 无API Key时限速较严

_last_call = {}  # key -> timestamp

# v17: 全局 429 计数器，用于 all 模式下自动跳过限流严重的数据源
_global_429_count = 0
RATE_LIMIT_SKIP_THRESHOLD = 50  # 429 超过 50 次时跳过 OpenAlex/S2
_rate_limit_skipped_sources = set()  # 被跳过的数据源名


def _rate_limit(key: str, min_interval: float):
    """简易速率限制：确保同组 API 调用间隔 >= min_interval 秒。"""
    now = time.monotonic()
    prev = _last_call.get(key, 0)
    wait = min_interval - (now - prev)
    if wait > 0:
        time.sleep(wait)
    _last_call[key] = time.monotonic()


def _request_with_retry(method: str, url: str, max_retries: int = 5,
                        base_sleep: float = 3.0, backoff_factor: float = 2.5,
                        **kwargs):
    """带 429 指数退避重试的请求。backoff_factor 控制退避倍数。
    
    v17: 初始退避从1s增加到3s，最大重试从3增加到5，退避因子从2.0增加到2.5；
         每次 429 计入全局计数器，用于自动跳过限流严重的数据源。
    """
    global _global_429_count
    for attempt in range(max_retries):
        try:
            r = requests.request(method, url, timeout=30, **kwargs)
            if r.status_code == 429:
                _global_429_count += 1
                wait = base_sleep * (backoff_factor ** attempt)
                print(f"  [429] 第{attempt+1}次重试，等待 {wait:.1f}s"
                      f"（全局429计数:{_global_429_count}）: {url}",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            return r
        except Exception as e:
            if attempt < max_retries - 1:
                wait = base_sleep * (backoff_factor ** attempt)
                print(f"  [网络错误] 第{attempt+1}次重试，等待 {wait:.1f}s: {e}",
                      file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    # 超过重试次数，返回最后一次 429 响应
    return r


def _safe_get(url: str, api_group: str = "eutils",
              min_interval: float = EUTILS_SLEEP, source_name: str = "",
              **kwargs):
    """带限速 + 重试的 GET 请求，失败返回 None。

    v17: 新增 source_name 参数，429 超限（>50 次）时自动跳过
         openalex / semantic_scholar 数据源。
    """
    if source_name and _global_429_count > RATE_LIMIT_SKIP_THRESHOLD:
        if source_name in ("openalex", "semantic_scholar"):
            print(f"  [跳过] 429超限（{_global_429_count}次），跳过 {source_name}",
                  file=sys.stderr)
            return None
    try:
        _rate_limit(api_group, min_interval)
        r = _request_with_retry("GET", url, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [GET失败] {url.split('?')[0]}: {e}", file=sys.stderr)
        return None


def _check_rate_limit_skip(source_name: str, mode: str = "all") -> bool:
    """v17: 检查是否应因限流跳过该数据源。
    
    仅在 all 模式下生效；全局 429 计数超过阈值时，跳过 OpenAlex 和 Semantic Scholar。
    返回 True 表示应跳过。
    """
    global _rate_limit_skipped_sources
    if mode != "all":
        return False
    if source_name in _rate_limit_skipped_sources:
        return True
    if _global_429_count >= RATE_LIMIT_SKIP_THRESHOLD:
        if source_name in ("openalex", "semantic_scholar"):
            _rate_limit_skipped_sources.add(source_name)
            print(f"  [限流保护] 全局429计数={_global_429_count}，"
                  f"跳过 {source_name} 数据源", file=sys.stderr)
            return True
    return False


# ---------------------------------------------------------------------------
# v17: 缩写歧义处理
# ---------------------------------------------------------------------------

# 已知歧义基因名集合（这些缩写在生物学外有其他常见含义，容易误匹配）
AMBIGUOUS_GENES = {
    "DMD", "RET", "MYC", "SRC", "HER2", "ABL", "RAF",
    "FOS", "JUN", "MYB", "MAP", "ACT", "MHC", "ACE", "APP",
}

# 生物学语境关键词（用于验证基因名匹配是否在生物学上下文中）
BIO_CONTEXT_WORDS = [
    "gene", "protein", "mutation", "variant", "disease",
    "patient", "syndrome", "carrier", "heterozygous", "homozygous",
    "pathogenic", "exon", "intron", "transcript", "allele",
    "genomic", "chromosomal", "DNA", "RNA", "sequencing",
    "clinical", "diagnostic", "therapeutic", "disorder",
    "phenotype", "genotype",
]

_BIO_CONTEXT_PATTERN = None  # 延迟编译


def _is_gene_ambiguous(gene: str) -> bool:
    """v17: 判断基因名是否为已知歧义缩写。"""
    return gene.upper() in AMBIGUOUS_GENES


def _verify_gene_context(text: str, gene: str) -> bool:
    """v17: 对歧义基因，在匹配位置周围 ±30 字符范围内搜索生物学语境词。

    如果找到至少 1 个语境词，返回 True（确认是基因）；
    否则返回 False（可能是同缩写非基因术语）。
    """
    global _BIO_CONTEXT_PATTERN
    if _BIO_CONTEXT_PATTERN is None:
        _BIO_CONTEXT_PATTERN = re.compile(
            '|'.join(re.escape(w) for w in BIO_CONTEXT_WORDS),
            re.IGNORECASE
        )
    # 找到基因名在文本中的位置
    match = re.search(r'\b' + re.escape(gene) + r'\b', text, re.IGNORECASE)
    if not match:
        return False
    start = max(0, match.start() - 30)
    end = min(len(text), match.end() + 30)
    context = text[start:end]
    return bool(_BIO_CONTEXT_PATTERN.search(context))



# ---------------------------------------------------------------------------
# 1. ClinVar elink
# ---------------------------------------------------------------------------

def _normalize_cdna_for_match(cdna: str) -> str:
    """归一化 cDNA 表达，兼容 ClinVar 常见的 HGVS 简写。

    例如：
      c.5266dupC  → c.5266dup
      c.1521_1523delCTT → c.1521_1523del
      c.5266_5267insA → c.5266_5267ins
    这样就能与 ClinVar 标题中省略了碱基的写法匹配。
    注意：delins（替换突变）不做归一化，避免 del 正则误匹配。
    """
    if not cdna:
        return cdna
    # delins 包含 del 和 ins，先排除，不做归一化
    if "delins" in cdna.lower():
        return cdna
    # dup: 去掉 dup 后面的碱基字母（保留位置信息）
    m = re.search(r'(dup)[ACGTUacgtu]+$', cdna)
    if m:
        cdna = cdna[:m.start()] + m.group(1)
    # del: 去掉 del 后面的碱基字母
    m = re.search(r'(del)[ACGTUacgtu]+$', cdna)
    if m:
        cdna = cdna[:m.start()] + m.group(1)
    # ins: 去掉 ins 后面的碱基字母
    m = re.search(r'(ins)[ACGTUacgtu]+$', cdna)
    if m:
        cdna = cdna[:m.start()] + m.group(1)
    return cdna


def _extract_variant_signature(cdna: str) -> tuple:
    """提取变异的类型签名（忽略位置），用于不同转录本间的宽松匹配。

    返回值示例：
      - c.123G>A        → ('snv', 'G', 'A')
      - c.123del        → ('del',)
      - c.123delCTT     → ('del', 'CTT')
      - c.123dup        → ('dup',)
      - c.123dupA       → ('dup', 'A')
      - c.123_124insT   → ('ins', 'T')
      - c.123delinsAT   → ('delins', 'AT')
      - 无法识别         → ()
    """
    if not cdna:
        return ()
    cdna_lower = cdna.lower()

    # delins（替换突变，需在 del/ins 之前判断）
    if "delins" in cdna_lower:
        m = re.search(r'delins([ACGTacgt]*)', cdna)
        if m:
            return ('delins', m.group(1).upper())
        return ('delins',)

    # dup
    if "dup" in cdna_lower:
        m = re.search(r'dup([ACGTacgt]*)', cdna)
        if m and m.group(1):
            return ('dup', m.group(1).upper())
        return ('dup',)

    # del
    if "del" in cdna_lower:
        m = re.search(r'del([ACGTacgt]*)', cdna)
        if m and m.group(1):
            return ('del', m.group(1).upper())
        return ('del',)

    # ins
    if "ins" in cdna_lower:
        m = re.search(r'ins([ACGTacgt]*)', cdna)
        if m and m.group(1):
            return ('ins', m.group(1).upper())
        return ('ins',)

    # snv: 匹配最后的碱基变化 如 c.123G>A
    m = re.search(r'(\d+)([ACGTacgt])>([ACGTacgt])', cdna)
    if m:
        return ('snv', m.group(2).upper(), m.group(3).upper())

    return ()


def _verify_clinvar_uids(uids: list[str], gene: str,
                         variant_cdna: str = "", rs: str = "") -> str:
    """对 esearch 返回的多个 UID 通过 esummary 逐一验证，返回第一个匹配的。

    验证规则：
      1. title 中必须包含 (GENE) 格式的基因名（如 "(TP53)"）
      2. 如果提供了 cDNA：title 或 variation_set.cdna_change 需精确匹配
      3. 如果只有 rs 号无 cDNA：variation_xrefs 中需包含匹配的 dbSNP ID
      4. 仅 rs 匹配但 cDNA 不匹配时，不接受（同位置不同等位）

    返回第一个通过验证的 UID，全部不匹配返回空字符串。
    """
    if not uids:
        return ""

    ids_str = ",".join(uids[:10])
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=clinvar&id={ids_str}&retmode=json"
    )
    try:
        _rate_limit("eutils", EUTILS_SLEEP)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ClinVar-verify] esummary 失败: {e}", file=sys.stderr)
        return ""

    result = data.get("result", {})
    rs_num = rs.replace("rs", "") if rs else ""

    for uid in uids:
        info = result.get(uid)
        if not info:
            continue

        title = info.get("title", "") or ""
        # 验证基因名：title 中应有 (GENE) 格式
        gene_marker = f"({gene})"
        if gene_marker.lower() not in title.lower():
            print(f"  [验证-跳过] UID={uid} 基因不匹配: title={title}",
                  file=sys.stderr)
            continue

        # 如果提供了 cDNA，优先用 cDNA 精确匹配
        if variant_cdna:
            # 归一化 cDNA（兼容 ClinVar 的 HGVS 简写，如 dupC→dup）
            norm_cdna = _normalize_cdna_for_match(variant_cdna)
            # 检查 title 中的 cDNA（同时匹配原始和归一化形式）
            title_lower = title.lower()
            cdna_match = (variant_cdna.lower() in title_lower or
                          norm_cdna.lower() in title_lower)

            # 检查 variation_set 中的 cdna_change
            if not cdna_match:
                variation_set = info.get("variation_set", []) or []
                for vs in variation_set:
                    cdna_change = vs.get("cdna_change", "") or ""
                    cdna_change_lower = cdna_change.lower()
                    if (variant_cdna.lower() in cdna_change_lower or
                            norm_cdna.lower() in cdna_change_lower):
                        cdna_match = True
                        break

            # 宽松匹配：比较变异签名（忽略位置差异，处理不同转录本）
            # ⚠️ SNV 类型跳过：签名只有 (ref, alt) 不含位置，
            #    同基因内 c.524G>A 和 c.743G>A 签名相同但实际是不同变异
            if not cdna_match:
                input_sig = _extract_variant_signature(variant_cdna)
                if input_sig and input_sig[0] != 'snv':
                    variation_set = info.get("variation_set", []) or []
                    for vs in variation_set:
                        cdna_change = vs.get("cdna_change", "") or ""
                        vs_sig = _extract_variant_signature(cdna_change)
                        if vs_sig and vs_sig == input_sig:
                            cdna_match = True
                            print(
                                f"  [验证-通过] UID={uid} "
                                f"cDNA宽松匹配（转录本差异）: "
                                f"{variant_cdna} ~ {cdna_change}",
                                file=sys.stderr)
                            break

            if cdna_match:
                print(f"  [验证-通过] UID={uid} cDNA匹配: {variant_cdna} -> "
                      f"title={title}", file=sys.stderr)
                return uid
            else:
                print(f"  [验证-跳过] UID={uid} cDNA不匹配 "
                      f"(期望 {variant_cdna}): title={title}",
                      file=sys.stderr)
                continue

        # 只有 rs 号时，用 variation_xrefs 的 dbSNP 验证
        if rs_num and not variant_cdna:
            variation_set = info.get("variation_set", []) or []
            dbsnp_match = False
            for vs in variation_set:
                xrefs = vs.get("variation_xrefs", []) or []
                for xr in xrefs:
                    if xr.get("db_source", "") == "dbSNP" and \
                       xr.get("db_id", "") == rs_num:
                        dbsnp_match = True
                        break
                if dbsnp_match:
                    break

            if dbsnp_match:
                print(f"  [验证-通过] UID={uid} dbSNP匹配: rs{rs_num} -> "
                      f"title={title}", file=sys.stderr)
                return uid
            else:
                print(f"  [验证-跳过] UID={uid} dbSNP不匹配 "
                      f"(期望 rs{rs_num}): title={title}",
                      file=sys.stderr)
                continue

        # 没有 cDNA 也没有 rs 时，仅基因匹配就接受（兜底）
        if not variant_cdna and not rs_num:
            print(f"  [验证-通过] UID={uid} 仅基因匹配: title={title}",
                  file=sys.stderr)
            return uid

    return ""


def _lookup_clinvar_uid(gene: str, variant_cdna: str = "",
                        rs: str = "") -> str:
    """通过 ClinVar esearch 自动查找变异对应的 ClinVar UID。

    查找策略（按优先级）：
      1. rs号 + [Variation ID] 精确匹配
      2. 基因名[Gene Name] + cDNA描述
      3. 仅基因名（兜底）

    对每个查询返回的多个 UID，通过 esummary 验证基因/cDNA/rs 是否匹配，
    返回第一个通过验证的 UID，未找到返回空字符串。
    """
    queries = []

    # 策略1: rs 号精确匹配
    if rs:
        queries.append(f"{rs}[rs]")
        queries.append(rs)  # 裸 rs 号作为兜底

    # 策略2: 基因 + cDNA
    if gene and variant_cdna:
        queries.append(
            f'"{gene}"[Gene Name] AND "{variant_cdna}"'
        )
        queries.append(f'"{gene}"[Gene Name] AND {variant_cdna}')
        # 归一化 cDNA（兼容 ClinVar HGVS 简写：dupC→dup, delCTT→del 等）
        norm_cdna = _normalize_cdna_for_match(variant_cdna)
        if norm_cdna != variant_cdna:
            queries.append(
                f'"{gene}"[Gene Name] AND "{norm_cdna}"'
            )
            queries.append(f'"{gene}"[Gene Name] AND {norm_cdna}')

    # 策略3: 仅基因（兜底，结果太多时不采用）
    # 不使用基因兜底，防止误匹配

    for query in queries:
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=clinvar&term={quote(query)}&retmax=10&retmode=json"
        )
        try:
            _rate_limit("eutils", EUTILS_SLEEP)
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            if id_list:
                print(f"[ClinVar-lookup] query={query!r} 返回 {len(id_list)} "
                      f"个UID: {id_list}", file=sys.stderr)
                # 验证每个 UID
                verified = _verify_clinvar_uids(id_list, gene, variant_cdna, rs)
                if verified:
                    return verified
        except Exception as e:
            print(f"[ClinVar-lookup] 查询失败 query={query!r}: {e}",
                  file=sys.stderr)
            continue

    return ""


def search_clinvar_elink(clinvar_uid: str) -> dict:
    """通过 ClinVar UID 获取关联的 PubMed PMID。"""
    result = {"count": 0, "pmids": [], "status": "ok"}

    if not clinvar_uid:
        result["status"] = "skipped: no clinvar_uid"
        return result

    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        f"?dbfrom=clinvar&db=pubmed&id={quote(clinvar_uid)}&retmode=json"
    )
    r = _safe_get(url, "eutils", EUTILS_SLEEP)
    if r is None:
        result["status"] = "error"
        return result

    try:
        data = r.json()
        linksets = data.get("linksets", [])
        if not linksets:
            return result
        linksetdbs = linksets[0].get("linksetdbs", [])
        for db in linksetdbs:
            # 只取 pubmed 库的链接，避免混入 PMC 等其他库的 ID
            if db.get("dbto", "").lower() != "pubmed":
                continue
            links = db.get("links", [])
            result["pmids"].extend(links)
        # 去重
        result["pmids"] = list(dict.fromkeys(result["pmids"]))
        result["count"] = len(result["pmids"])
    except Exception as e:
        print(f"[ClinVar-elink] 解析失败: {e}", file=sys.stderr)
        result["status"] = "parse_error"

    return result


# ---------------------------------------------------------------------------
# 2. PubTator 3.0
# ---------------------------------------------------------------------------

def search_pubtator(gene: str, protein_full: str, protein_short: str,
                    cdna: str, rs: str = "", max_results: int = 30,
                    gene_aliases: list[str] = None) -> dict:
    """PubTator 3.0 双模式检索：自由文本 + Entity ID 精确搜索。"""
    result = {"count": 0, "pmids": [], "entity_ids": [], "status": "ok"}
    all_pmids = []
    entity_ids_found = []
    filtered_out = 0  # v16: 预过滤丢弃计数

    # 模式一：自由文本搜索（多个检索词）
    text_queries = []
    if gene and cdna:
        text_queries.append(f"{gene} {cdna}")
    if gene and protein_full:
        text_queries.append(f"{gene} {protein_full}")
    if gene and protein_short:
        text_queries.append(f"{gene} {protein_short}")
    if rs:
        text_queries.append(rs)

    # 基因别名扩展：别名 + cDNA / 蛋白简写 组合查询
    if gene_aliases:
        for alias in gene_aliases:
            alias = alias.strip()
            if not alias:
                continue
            if cdna:
                text_queries.append(f"{alias} {cdna}")
            if protein_short:
                text_queries.append(f"{alias} {protein_short}")

    for q in text_queries:
        url = (
            "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/"
            f"?text={quote(q)}&limit={max_results}"
        )
        r = _safe_get(url, "pubtator", PUBTATOR_SLEEP)
        if r is None:
            continue
        try:
            data = r.json()
            results_list = data.get("results", [])
            gene_lower = gene.lower()
            for item in results_list:
                pmid = str(item.get("pmid", ""))
                if not pmid:
                    continue
                # v16 预过滤1: 基因名精确匹配（词边界正则）+ 别名匹配
                title = item.get("title") or ""
                if title:
                    # 基因名精确匹配（词边界正则）
                    gene_found = bool(
                        re.search(r'\b' + re.escape(gene) + r'\b',
                                  title, re.IGNORECASE)
                    )
                    if not gene_found and gene_aliases:
                        for alias in gene_aliases:
                            alias = alias.strip()
                            if alias and re.search(
                                    r'\b' + re.escape(alias) + r'\b',
                                    title, re.IGNORECASE):
                                gene_found = True
                                break
                    if not gene_found:
                        filtered_out += 1
                        continue
                    # v17: 歧义基因做上下文验证，不通过的标记 ambiguous_match（保留给后过滤）
                    ambiguous_match = False
                    if _is_gene_ambiguous(gene):
                        if not _verify_gene_context(title, gene):
                            ambiguous_match = True
                    if ambiguous_match:
                        if "ambiguous_pmids" not in result:
                            result["ambiguous_pmids"] = set()
                        result["ambiguous_pmids"].add(pmid)
                all_pmids.append(pmid)
        except Exception as e:
            print(f"[PubTator-text] 解析失败 query={q!r}: {e}",
                  file=sys.stderr)

    # 模式二：Entity ID 精确搜索（用蛋白简写格式）
    if protein_short and gene:
        # 先 autocomplete 获取 entity ID（基因+蛋白简写组合查询更精准）
        ac_queries = [f"{gene} {protein_short}", protein_short]
        for ac_q in ac_queries:
            if entity_ids_found:
                break  # 已找到则不再尝试
            ac_url = (
                "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/entity/"
                f"autocomplete/?query={quote(ac_q)}&concept=variant&limit=5"
            )
            r = _safe_get(ac_url, "pubtator", PUBTATOR_SLEEP)
            if r is None:
                continue
            try:
                ac_data = r.json()
                candidates = []
                for item in ac_data:
                    eid = item.get("_id", "") or item.get("id", "")
                    desc = item.get("description", "") or ""
                    # entity ID 格式: @VARIANT_{蛋白简写}_{基因名}_human
                    expected_suffix = f"_{gene}_human"
                    if eid and eid.startswith("@VARIANT_"):
                        # 优先匹配带基因名的
                        if expected_suffix.lower() in eid.lower() or \
                           f"{gene} (human)".lower() in desc.lower():
                            entity_ids_found.insert(0, eid)
                        else:
                            candidates.append(eid)

                # v16 Bug修复：不再补入非基因匹配的候选，防止跨基因假阳性

            except Exception as e:
                print(f"[PubTator-autocomplete] 解析失败 q={ac_q!r}: {e}",
                      file=sys.stderr)

        # 去重，最多 3 个
        entity_ids_found = list(dict.fromkeys(entity_ids_found))[:3]

        # 用 entity ID 搜索
        for eid in entity_ids_found:
            search_url = (
                "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/"
                f"?text={quote(eid)}&limit={max_results}"
            )
            r2 = _safe_get(search_url, "pubtator", PUBTATOR_SLEEP)
            if r2 is None:
                continue
            try:
                sdata = r2.json()
                for item in sdata.get("results", []):
                    pmid = str(item.get("pmid", ""))
                    if pmid:
                        all_pmids.append(pmid)
            except Exception as e:
                print(f"[PubTator-entity] 解析失败 id={eid!r}: {e}",
                      file=sys.stderr)

    result["entity_ids"] = entity_ids_found
    result["pmids"] = list(dict.fromkeys(all_pmids))
    result["count"] = len(result["pmids"])
    if filtered_out > 0:
        result["prefilter_dropped"] = filtered_out
        print(f"  [PubTator-预过滤] 丢弃 {filtered_out} 篇基因不匹配文献", file=sys.stderr)
    # v17: 歧义PMID集合转列表
    if "ambiguous_pmids" in result:
        result["ambiguous_pmids"] = list(result["ambiguous_pmids"])
        if result["ambiguous_pmids"]:
            print(f"  [PubTator-歧义] {len(result['ambiguous_pmids'])} 篇可能为缩写歧义",
                  file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# 3. LitSense
# ---------------------------------------------------------------------------

def search_litsense(gene: str, protein_full: str, protein_short: str,
                    disease: str = "", topk: int = 10,
                    gene_aliases: list[str] = None,
                    cdna: str = "", rs: str = "") -> dict:
    """LitSense 语义搜索：用描述性句子搜索句子级匹配。
    
    v18: 新增变异签名过滤——句子中必须出现 cDNA 或蛋白变化某种形式才算命中，
         仅基因名匹配不再保留。
    """
    result = {"count": 0, "pmids": [], "sentences": [], "status": "ok"}
    all_pmids = []
    all_sentences = []
    # pmid -> 命中的句子（供后续过滤使用）
    pmid_sentences: dict[str, list[str]] = {}
    litsense_filtered_out = 0  # v16: 预过滤丢弃计数
    litsense_variant_dropped = 0  # v18: 变异签名不匹配丢弃计数

    # v18: 构建变异签名列表
    variant_signatures = []
    if cdna:
        variant_signatures.append(cdna)
        norm_cdna = _normalize_cdna_for_match(cdna)
        if norm_cdna and norm_cdna != cdna:
            variant_signatures.append(norm_cdna)
        if cdna.startswith("c."):
            variant_signatures.append(cdna[2:])
    if protein_full:
        variant_signatures.append(protein_full)
        # 三字母转单字母的常见形式
        variant_signatures.append(re.sub(r'(\d+)', r'\1', protein_full))
    if protein_short:
        variant_signatures.append(protein_short)
        if not protein_short.startswith("p."):
            variant_signatures.append(f"p.{protein_short}")
    if rs:
        variant_signatures.append(rs)
    # 去重
    variant_signatures = list(set(v for v in variant_signatures if v))

    # 构造描述性检索句
    sentences = []
    if gene and protein_full:
        if disease:
            sentences.append(
                f"{gene} {protein_full} causes {disease}"
            )
            sentences.append(
                f"patients with {gene} {protein_full} {disease}"
            )
        sentences.append(f"{gene} {protein_full} variant")
        sentences.append(f"{gene} {protein_full} mutation")
    if gene and protein_short:
        sentences.append(f"{gene} {protein_short}")
    if gene and disease:
        sentences.append(f"{gene} mutation {disease} patient")

    # 基因别名扩展：用别名构造的检索句
    if gene_aliases:
        for alias in gene_aliases:
            alias = alias.strip()
            if not alias:
                continue
            if alias and protein_full:
                sentences.append(f"{alias} {protein_full} variant")
                sentences.append(f"{alias} {protein_full} mutation")
            if alias and protein_short:
                sentences.append(f"{alias} {protein_short}")

    for query in sentences[:15]:  # v16: 扩大到15条，确保基因别名构造的query不被截断
        url = (
            "https://www.ncbi.nlm.nih.gov/research/litsense-api/api/"
            f"?query={quote(query)}&topk={topk}"
        )
        r = _safe_get(url, "eutils", EUTILS_SLEEP)
        if r is None:
            continue
        try:
            data = r.json()
            # LitSense 返回 list 格式，每项含 pmid/text/section 等
            results_list = data if isinstance(data, list) else data.get("results", [])
            for item in results_list:
                pmid = str(item.get("pmid", ""))
                sentence = item.get("text", item.get("sentence", "")) or ""
                if not pmid:
                    continue
                # v16: 词边界正则过滤（基因名+别名）
                gene_found = bool(
                    re.search(r'\b' + re.escape(gene) + r'\b',
                              sentence, re.IGNORECASE)
                )
                if not gene_found and gene_aliases:
                    for alias in gene_aliases:
                        alias = alias.strip()
                        if alias and re.search(
                                r'\b' + re.escape(alias) + r'\b',
                                sentence, re.IGNORECASE):
                            gene_found = True
                            break
                if not gene_found:
                    litsense_filtered_out += 1
                    continue
                # v18: 变异签名检查——句子中必须出现变异标识
                variant_found = False
                for sig in variant_signatures:
                    if sig and sig.lower() in sentence.lower():
                        variant_found = True
                        break
                if not variant_found:
                    litsense_variant_dropped += 1
                    continue
                # v17: 歧义基因做上下文验证，不通过的标记 ambiguous_match（保留给后过滤）
                ambiguous_match = False
                if _is_gene_ambiguous(gene):
                    if not _verify_gene_context(sentence, gene):
                        ambiguous_match = True
                if ambiguous_match:
                    if "ambiguous_pmids" not in result:
                        result["ambiguous_pmids"] = set()
                    result["ambiguous_pmids"].add(pmid)
                all_pmids.append(pmid)
                all_sentences.append({
                    "pmid": pmid,
                    "sentence": sentence,
                    "query": query,
                })
                # v18: 保存 pmid -> 命中句子，供后续过滤使用
                if pmid not in pmid_sentences:
                    pmid_sentences[pmid] = []
                pmid_sentences[pmid].append(sentence)
        except Exception as e:
            print(f"[LitSense] 解析失败 query={query!r}: {e}",
                  file=sys.stderr)

    result["pmids"] = list(dict.fromkeys(all_pmids))
    result["count"] = len(result["pmids"])
    result["sentences"] = all_sentences[:30]
    result["pmid_sentences"] = pmid_sentences  # v18: 供后过滤使用
    if litsense_filtered_out > 0:
        result["prefilter_dropped"] = litsense_filtered_out
        print(f"  [LitSense-预过滤] 丢弃 {litsense_filtered_out} 篇基因不匹配句子", file=sys.stderr)
    if litsense_variant_dropped > 0:
        result["variant_filter_dropped"] = litsense_variant_dropped
        print(f"  [LitSense-变异过滤] 丢弃 {litsense_variant_dropped} 篇变异不匹配句子", file=sys.stderr)
    # v17: 歧义PMID集合转列表
    if "ambiguous_pmids" in result:
        result["ambiguous_pmids"] = list(result["ambiguous_pmids"])
        if result["ambiguous_pmids"]:
            print(f"  [LitSense-歧义] {len(result['ambiguous_pmids'])} 篇可能为缩写歧义",
                  file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# 5. PubMed esearch + esummary
# ---------------------------------------------------------------------------


def search_pubmed(gene: str, cdna: str, protein_full: str,
                  protein_short: str, rs: str = "",
                  gene_aliases: list[str] = None,
                  max_results: int = 30) -> dict:
    """PubMed esearch：多种变异格式分别搜索取并集。"""
    result = {"count": 0, "pmids": [], "papers": [], "status": "ok"}
    all_pmids = []
    papers_by_pmid = {}

    queries = []
    if gene and cdna:
        queries.append(f"{gene} {cdna}")
    if gene and protein_full:
        queries.append(f"{gene} {protein_full}")
    if gene and protein_short:
        queries.append(f"{gene} {protein_short}")
    if gene and rs:
        queries.append(f"{gene} {rs}")

    # 基因曾用名 + 主要变异格式
    if gene_aliases:
        for alias in gene_aliases:
            if cdna:
                queries.append(f"{alias} {cdna}")
            if protein_short:
                queries.append(f"{alias} {protein_short}")

    for query in queries:
        esearch_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&retmax={max_results}&retmode=json"
            f"&term={quote(query)}"
        )
        r = _safe_get(esearch_url, "eutils", EUTILS_SLEEP)
        if r is None:
            continue
        try:
            es = r.json()
            id_list = es.get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            print(f"[PubMed-search] 解析失败 query={query!r}: {e}",
                  file=sys.stderr)
            continue

        if not id_list:
            continue

        all_pmids.extend(id_list)

        # ESummary 获取元信息
        ids_str = ",".join(id_list)
        esummary_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&id={ids_str}&retmode=xml"
        )
        _rate_limit("eutils", EUTILS_SLEEP)
        try:
            r2 = _request_with_retry("GET", esummary_url)
            r2.raise_for_status()
            root = ET.fromstring(r2.content)

            for docsum in root.findall("DocSum"):
                pmid_el = docsum.find("Id")
                if pmid_el is None:
                    continue
                pmid = pmid_el.text

                title = ""
                journal = ""
                year = ""
                authors = []
                doi = ""

                for item in docsum.findall("Item"):
                    name = item.get("Name", "")
                    if name == "Title":
                        title = item.text or ""
                    elif name == "Source":
                        journal = item.text or ""
                    elif name == "PubDate":
                        pub_date = (item.text or "").strip()
                        year = pub_date.split()[0] if pub_date else ""
                    elif name == "DOI":
                        doi = item.text or ""
                    elif name == "AuthorList":
                        for au in item:
                            if au.get("Name") == "Author":
                                author_name = (au.text or "").strip()
                                if author_name:
                                    authors.append(author_name)
                    elif name == "Author":
                        author_name = (item.text or "").strip()
                        if author_name:
                            authors.append(author_name)

                authors = authors[:5]

                if pmid not in papers_by_pmid:
                    papers_by_pmid[pmid] = {
                        "pmid": pmid,
                        "title": title,
                        "authors": authors,
                        "journal": journal,
                        "year": year,
                        "doi": doi,
                        "abstract": "",
                        "pmcid": "",
                        "oa_url": "",
                        "sources": [],
                    }
                if "PubMed" not in papers_by_pmid[pmid]["sources"]:
                    papers_by_pmid[pmid]["sources"].append("PubMed")

        except Exception as e:
            print(f"[PubMed-esummary] 失败: {e}", file=sys.stderr)

    result["pmids"] = list(dict.fromkeys(all_pmids))
    result["count"] = len(result["pmids"])
    result["papers"] = list(papers_by_pmid.values())
    return result


def fetch_pubmed_abstracts(pmids: list[str]) -> dict[str, str]:
    """批量获取 PubMed 摘要，返回 {pmid: abstract_text}。"""
    if not pmids:
        return {}

    # 分批，每批最多 100 个
    batch_size = 100
    abstracts: dict[str, str] = {}

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        ids_str = ",".join(batch)
        efetch_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={ids_str}&retmode=xml"
        )
        r = _safe_get(efetch_url, "eutils", EUTILS_SLEEP)
        if r is None:
            continue

        try:
            root = ET.fromstring(r.content)
        except ET.ParseError as e:
            print(f"[PubMed-abstract] XML 解析失败: {e}", file=sys.stderr)
            continue

        for article in root.iter("PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None:
                continue
            pmid = pmid_el.text

            parts: list[str] = []
            for abs_text in article.iter("AbstractText"):
                label = abs_text.get("Label", "")
                text = "".join(abs_text.itertext()).strip()
                if not text:
                    continue
                parts.append(f"{label}: {text}" if label else text)

            abstracts[pmid] = "\n".join(parts)

    return abstracts


# ---------------------------------------------------------------------------
# 6. OpenAlex
# ---------------------------------------------------------------------------

def _safe_get_std(url: str, api_group: str,
                  min_interval: float = GENERIC_SLEEP, source_name: str = "",
                  **kwargs):
    """使用标准 requests（不经代理）的带限速 + 重试 GET，失败返回 None。

    v17: 新增 source_name 参数，429 超限（>50 次）时自动跳过
         openalex / semantic_scholar 数据源。
    """
    if source_name and _global_429_count > RATE_LIMIT_SKIP_THRESHOLD:
        if source_name in ("openalex", "semantic_scholar"):
            print(f"  [跳过] 429超限（{_global_429_count}次），跳过 {source_name}",
                  file=sys.stderr)
            return None
    try:
        _rate_limit(api_group, min_interval)
        r = _request_with_retry_std("GET", url, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [GET失败(std)] {url.split('?')[0]}: {e}", file=sys.stderr)
        return None


def _request_with_retry_std(method: str, url: str, max_retries: int = 5,
                            base_sleep: float = 3.0, backoff_factor: float = 2.5,
                            **kwargs):
    """使用标准 requests 的带 429 指数退避重试请求。
    
    v17: 初始退避从1s增加到3s，最大重试从3增加到5，退避因子从2.0增加到2.5；
         每次 429 计入全局计数器。
    """
    global _global_429_count
    for attempt in range(max_retries):
        try:
            r = _std_requests.request(method, url, timeout=30, **kwargs)
            if r.status_code == 429:
                _global_429_count += 1
                wait = base_sleep * (backoff_factor ** attempt)
                print(f"  [429] 第{attempt+1}次重试(std)，等待 {wait:.1f}s"
                      f"（全局429计数:{_global_429_count}）: {url}",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            return r
        except Exception as e:
            if attempt < max_retries - 1:
                wait = base_sleep * (backoff_factor ** attempt)
                print(f"  [网络错误(std)] 第{attempt+1}次重试，等待 {wait:.1f}s: {e}",
                      file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    return r


def search_openalex(gene: str, cdna: str, protein_short: str,
                    known_pmids: list[str] = None,
                    max_results: int = 30,
                    gene_aliases: list[str] = None) -> dict:
    """OpenAlex 搜索 + 引用网络扩展。

    使用标准 requests（不经代理）以避免共享 IP 下的速率限制；
    代理下 OpenAlex 免费配额很快耗尽，标准直连可正常使用。
    """
    result = {
        "count": 0, "pmids": [], "citation_refs": [],
        "oa_info": {}, "status": "ok"
    }
    all_pmids = []
    oa_info = {}
    citation_refs = set()

    # 搜索论文
    search_queries = []
    if gene and cdna:
        search_queries.append(f"{gene} {cdna}")
    if gene and protein_short:
        search_queries.append(f"{gene} {protein_short}")

    # 基因别名扩展：别名 + cDNA / 蛋白简写 组合查询
    if gene_aliases:
        for alias in gene_aliases:
            alias = alias.strip()
            if not alias:
                continue
            if cdna:
                search_queries.append(f"{alias} {cdna}")
            if protein_short:
                search_queries.append(f"{alias} {protein_short}")

    search_ok = False  # 是否至少有一个搜索请求成功
    for q in search_queries:
        url = (
            "https://api.openalex.org/works"
            f"?search={quote(q, safe="")}&per_page={min(max_results, 50)}"
            "&select=id,title,open_access,referenced_works,ids"
        )
        r = _safe_get_std(url, "openalex_std", GENERIC_SLEEP, source_name="openalex")
        if r is None:
            continue
        search_ok = True
        try:
            data = r.json()
            for work in data.get("results", []):
                # OpenAlex 用 ids 字段，格式: {"pmid": "https://pubmed.ncbi.nlm.nih.gov/123/", ...}
                ids = work.get("ids") or work.get("external_ids") or {}
                pmid = ""
                pmid_url = ids.get("pmid", "")
                if isinstance(pmid_url, str) and pmid_url:
                    pmid = pmid_url.replace(
                        "https://pubmed.ncbi.nlm.nih.gov/", ""
                    ).rstrip("/")
                doi = ids.get("doi", "") or ""

                if pmid:
                    all_pmids.append(pmid)

                # OA 信息
                oa = work.get("open_access") or {}
                oa_url = oa.get("oa_url", "") or ""
                oa_status = oa.get("oa_status", "") or ""

                if pmid:
                    oa_info[pmid] = {
                        "oa_status": oa_status,
                        "oa_url": oa_url,
                        "doi": doi,
                    }

                # 引用列表
                refs = work.get("referenced_works") or []
                for ref in refs[:20]:
                    citation_refs.add(ref)
        except Exception as e:
            print(f"[OpenAlex-search] 解析失败 query={q!r}: {e}",
                  file=sys.stderr)

    # 用已知 PMID 反查引用和 OA
    pmid_lookup_ok = True  # 没有 known_pmids 时也视为 ok
    if known_pmids:
        pmid_lookup_ok = False
        for pmid in known_pmids[:10]:  # 限制数量防超时
            url = (
                "https://api.openalex.org/works"
                f"?filter=pmid:{pmid}"
                "&select=id,title,open_access,best_oa_location,referenced_works,ids"
            )
            r = _safe_get_std(url, "openalex_std", GENERIC_SLEEP, source_name="openalex")
            if r is None:
                continue
            pmid_lookup_ok = True
            try:
                data = r.json()
                results = data.get("results", [])
                if results:
                    work = results[0]
                    oa = work.get("open_access") or {}
                    best_oa = work.get("best_oa_location") or {}
                    oa_url = (best_oa.get("url") or oa.get("oa_url") or "")

                    # 提取 doi（与搜索路径保持一致）
                    ids_obj = work.get("ids") or {}
                    doi = ids_obj.get("doi", "") or ""

                    if pmid not in oa_info:
                        oa_info[pmid] = {}
                    oa_info[pmid].update({
                        "oa_status": oa.get("oa_status", ""),
                        "oa_url": oa_url,
                    })
                    if doi and not oa_info[pmid].get("doi"):
                        oa_info[pmid]["doi"] = doi

                    refs = work.get("referenced_works") or []
                    for ref in refs[:30]:
                        citation_refs.add(ref)
            except Exception as e:
                print(f"[OpenAlex-pmid] 解析失败 pmid={pmid}: {e}",
                      file=sys.stderr)

    # 状态判断：所有请求都失败时标记为 error
    if not search_queries and not known_pmids:
        result["status"] = "ok"  # 无查询项，正常
    elif not search_ok and not pmid_lookup_ok:
        result["status"] = "error: all requests failed (likely rate-limited)"
    elif not search_ok and search_queries:
        result["status"] = "warning: search failed, pmid lookup ok"

    result["pmids"] = list(dict.fromkeys(all_pmids))
    result["count"] = len(result["pmids"])
    result["citation_refs"] = list(citation_refs)[:100]
    result["oa_info"] = oa_info
    return result


def get_openalex_oa(pmid: str) -> dict:
    """通过 PMID 查询 OpenAlex OA 链接（使用标准 requests 避免代理限速）。"""
    url = (
        "https://api.openalex.org/works"
        f"?filter=pmid:{pmid}"
        "&select=id,open_access,best_oa_location"
    )
    r = _safe_get_std(url, "openalex_std", GENERIC_SLEEP, source_name="openalex")
    if r is None:
        return {}
    try:
        data = r.json()
        results = data.get("results", [])
        if not results:
            return {}
        work = results[0]
        oa = work.get("open_access") or {}
        best_oa = work.get("best_oa_location") or {}
        return {
            "oa_status": oa.get("oa_status", ""),
            "oa_url": best_oa.get("url") or oa.get("oa_url") or "",
        }
    except Exception as e:
        print(f"[OpenAlex-OA] 解析失败 pmid={pmid}: {e}", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# 7. Semantic Scholar
# ---------------------------------------------------------------------------

def search_semantic_scholar(gene: str, cdna: str, protein_full: str,
                            protein_short: str, rs: str = "",
                            limit: int = 30,
                            gene_aliases: list[str] = None) -> dict:
    """Semantic Scholar 检索（使用 bulk search 端点 + 标准 requests）。

    原 /paper/search 端点在共享 IP 下极易触发 429，
    bulk search 端点限流更宽松，且使用标准 requests 避开代理限速。
    """
    result = {
        "count": 0, "pmids": [], "papers": [], "status": "ok"
    }
    all_pmids = []
    papers_by_id = {}
    s2_filtered_out = 0  # v16: 预过滤丢弃计数

    queries = []
    if gene and cdna:
        queries.append(f"{gene} {cdna}")
    if gene and protein_full:
        queries.append(f"{gene} {protein_full}")
    if gene and protein_short:
        queries.append(f"{gene} {protein_short}")
    if gene and rs:
        queries.append(f"{gene} {rs}")

    any_success = False
    # v16: 预计算归一化cDNA（避免循环内重复调用）
    _norm_cdna = _normalize_cdna_for_match(cdna) if cdna else ""

    for query in queries:
        # v17: 429 超限直接跳过
        if _global_429_count > RATE_LIMIT_SKIP_THRESHOLD:
            print(f"  [跳过] 429超限（{_global_429_count}次），跳过 semantic_scholar",
                  file=sys.stderr)
            break
        url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": "title,authors,year,venue,externalIds,abstract",
        }
        try:
            _rate_limit("semanticscholar_bulk", 2.0)  # bulk 端点限流约 5次/分钟
            r = _request_with_retry_std(
                "GET", url, params=params,
                max_retries=3, base_sleep=10.0, backoff_factor=2.0,
            )
            if r.status_code == 429:
                print("[SemanticScholar] 触发限流（重试后仍429），跳过剩余查询",
                      file=sys.stderr)
                break
            r.raise_for_status()
            data = r.json()
            any_success = True
        except Exception as e:
            print(f"[SemanticScholar] 检索失败 query={query!r}: {e}",
                  file=sys.stderr)
            continue

        for paper in data.get("data", []):
            ext = paper.get("externalIds") or {}
            pmid = ext.get("PubMed") or ext.get("PMID") or ""
            s2_id = paper.get("paperId", "") or paper.get("id", "")
            doi = ext.get("DOI", "") or ""

            dedup_key = pmid if pmid else s2_id
            if not dedup_key:
                continue

            if pmid:
                all_pmids.append(pmid)

            # bulk 端点 authors 格式: [{"name": "...", "authorId": "..."}, ...]
            # 与普通搜索格式一致，兼容处理
            authors_raw = paper.get("authors") or []
            authors = []
            for a in authors_raw[:5]:
                if isinstance(a, dict):
                    name = a.get("name", "")
                elif isinstance(a, str):
                    name = a
                else:
                    continue
                if name:
                    authors.append(name)

            # v16+v17: 预过滤3: 基因名匹配（含歧义上下文验证）+ 变异签名匹配
            title_text = paper.get("title", "") or ""
            abstract_text = paper.get("abstract", "") or ""
            combined_text = title_text + " " + abstract_text
            
            # 基因名词边界匹配（基因名+别名）
            gene_found = bool(
                re.search(r'\b' + re.escape(gene) + r'\b',
                          combined_text, re.IGNORECASE)
            )
            if not gene_found and gene_aliases:
                for alias in gene_aliases:
                    alias = alias.strip()
                    if alias and re.search(
                            r'\b' + re.escape(alias) + r'\b',
                            combined_text, re.IGNORECASE):
                        gene_found = True
                        break
            if not gene_found:
                s2_filtered_out += 1
                continue
            # v17: 歧义基因做上下文验证，不通过的标记 ambiguous_match（保留给后过滤）
            ambiguous_match = False
            if _is_gene_ambiguous(gene):
                if not _verify_gene_context(combined_text, gene):
                    ambiguous_match = True
            if ambiguous_match:
                if "ambiguous_pmids" not in result:
                    result["ambiguous_pmids"] = set()
                if pmid:
                    result["ambiguous_pmids"].add(pmid)
            
            # 变异签名匹配检查
            sig_match = False
            # 构建变异签名表示
            variant_forms = []
            if cdna:
                variant_forms.append(cdna)
            if protein_short:
                variant_forms.append(protein_short)
                # 也检查带 p. 前缀的形式
                variant_forms.append(f"p.{protein_short}")
            if protein_full:
                variant_forms.append(protein_full)
                variant_forms.append(f"p.{protein_full}")
            if rs:
                variant_forms.append(rs)
            # 检查任一变异形式是否出现在文本中
            for vf in variant_forms:
                if vf and vf in combined_text:
                    sig_match = True
                    break
            # 也检查归一化的 cDNA 形式（如 dupC→dup）
            if not sig_match and _norm_cdna:
                if _norm_cdna != cdna and _norm_cdna in combined_text:
                    sig_match = True
            if not sig_match:
                s2_filtered_out += 1
                continue

            papers_by_id[dedup_key] = {
                "pmid": pmid,
                "s2_id": s2_id,
                "title": paper.get("title", ""),
                "authors": authors,
                "journal": paper.get("venue", ""),
                "year": str(paper.get("year") or ""),
                "abstract": paper.get("abstract", "") or "",
                "tldr": "",  # bulk 端点不支持 tldr
                "doi": doi,
                "pmcid": "",
                "oa_url": "",
                "sources": ["SemanticScholar"],
            }

    # 状态判断：所有查询都失败时标记 error
    if queries and not any_success:
        result["status"] = "error: all queries failed (likely rate-limited)"

    result["pmids"] = list(dict.fromkeys(all_pmids))
    result["count"] = len(result["pmids"])
    result["papers"] = list(papers_by_id.values())
    if s2_filtered_out > 0:
        result["prefilter_dropped"] = s2_filtered_out
        print(f"  [S2-预过滤] 丢弃 {s2_filtered_out} 篇变异不匹配文献", file=sys.stderr)
    # v17: 歧义PMID集合转列表
    if "ambiguous_pmids" in result:
        result["ambiguous_pmids"] = list(result["ambiguous_pmids"])
        if result["ambiguous_pmids"]:
            print(f"  [S2-歧义] {len(result['ambiguous_pmids'])} 篇可能为缩写歧义",
                  file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# 7. Europe PMC（v16: 原第8项，LitVar2移除后）
# ---------------------------------------------------------------------------

def search_europepmc(gene: str, cdna: str, protein_short: str,
                     max_results: int = 30) -> dict:
    """Europe PMC 搜索。"""
    result = {"count": 0, "pmids": [], "papers": [], "status": "ok"}
    all_pmids = []
    papers_by_pmid = {}

    queries = []
    if gene and cdna:
        queries.append(f"{gene} {cdna}")
    if gene and protein_short:
        queries.append(f"{gene} {protein_short}")

    for q in queries:
        url = (
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            f"?query={quote(q)}&format=json&pageSize={min(max_results, 100)}"
        )
        r = _safe_get(url, "europepmc", GENERIC_SLEEP)
        if r is None:
            continue
        try:
            data = r.json()
            result_list = data.get("resultList", {}).get("result", [])
            for item in result_list:
                pmid = str(item.get("pmid", ""))
                if not pmid:
                    continue
                all_pmids.append(pmid)

                authors_str = item.get("authorString", "")
                authors = [a.strip() for a in authors_str.split(",")
                           if a.strip()][:5]

                pmcid = item.get("pmcid", "") or ""
                doi = item.get("doi", "") or ""
                title = item.get("title", "") or ""
                journal = item.get("journalTitle", "") or ""
                year = str(item.get("pubYear", ""))
                abstract = item.get("abstractText", "") or ""

                papers_by_pmid[pmid] = {
                    "pmid": pmid,
                    "title": title,
                    "authors": authors,
                    "journal": journal,
                    "year": year,
                    "abstract": abstract,
                    "pmcid": pmcid,
                    "doi": doi,
                    "oa_url": "",
                    "sources": ["EuropePMC"],
                }
        except Exception as e:
            print(f"[EuropePMC] 解析失败 query={q!r}: {e}",
                  file=sys.stderr)

    result["pmids"] = list(dict.fromkeys(all_pmids))
    result["count"] = len(result["pmids"])
    result["papers"] = list(papers_by_pmid.values())
    return result


def get_europepmc_pmcid(pmid: str) -> str:
    """从 Europe PMC 获取 PMCID。"""
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        f"?query=EXT_ID:{pmid}+AND+SRC:MED&format=json&resultType=core"
    )
    r = _safe_get(url, "europepmc", GENERIC_SLEEP)
    if r is None:
        return ""
    try:
        data = r.json()
        results = data.get("resultList", {}).get("result", [])
        if results:
            return results[0].get("pmcid", "") or ""
    except Exception as e:
        print(f"[EuropePMC-pmcid] 解析失败: {e}", file=sys.stderr)
    return ""


# ---------------------------------------------------------------------------
# 全文获取
# ---------------------------------------------------------------------------

def fetch_fulltext_pubtator(pmid: str) -> dict | None:
    """PubTator 3.0 全文导出（最可靠）。"""
    url = (
        "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/"
        f"export/biocjson?pmids={pmid}&full=true"
    )
    r = _safe_get(url, "pubtator", PUBTATOR_SLEEP)
    if r is None:
        return None
    try:
        data = r.json()
        pubtator3 = data.get("PubTator3", [])
        if not pubtator3:
            return None

        passages = []
        for doc in pubtator3:
            for p in doc.get("passages", []):
                section = p.get("infons", {}).get("section_type", "") or \
                          p.get("infons", {}).get("type", "") or ""
                text = p.get("text", "") or ""
                if text.strip():
                    passages.append({"section": section, "text": text})

        if passages:
            return {
                "source": "PubTator",
                "passages": passages,
                "pmcid": "",
            }
    except Exception as e:
        print(f"[PubTator-fulltext] 解析失败 pmid={pmid}: {e}",
              file=sys.stderr)
    return None


def fetch_fulltext_europepmc(pmcid: str) -> dict | None:
    """Europe PMC 全文 XML（需 PMCID）。"""
    if not pmcid:
        return None
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/"
        f"{pmcid}/fullTextXML"
    )
    r = _safe_get(url, "europepmc", GENERIC_SLEEP)
    if r is None:
        return None
    try:
        root = ET.fromstring(r.content)
        passages = []

        # 遍历 body 下的所有 section
        body = root.find(".//body")
        if body is not None:
            for sec in body.iter("sec"):
                title_el = sec.find("title")
                sec_title = (title_el.text or "").strip().lower() if title_el is not None else ""

                # 提取段落文本
                sec_texts = []
                for p in sec.findall("p"):
                    text = "".join(p.itertext()).strip()
                    if text:
                        sec_texts.append(text)

                if sec_texts:
                    passages.append({
                        "section": sec_title or "unknown",
                        "text": "\n".join(sec_texts),
                    })

        if passages:
            return {
                "source": "EuropePMC",
                "passages": passages,
                "pmcid": pmcid,
            }
    except ET.ParseError as e:
        print(f"[EuropePMC-fulltext] XML解析失败: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[EuropePMC-fulltext] 失败: {e}", file=sys.stderr)
    return None


def _get_pmc_id_from_pubmed(pmid: str) -> str:
    """通过 PubMed elink 获取 PMC ID。"""
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        f"?dbfrom=pubmed&db=pmc&id={pmid}&retmode=json"
    )
    r = _safe_get(url, "eutils", EUTILS_SLEEP)
    if r is None:
        return ""
    try:
        data = r.json()
        linksets = data.get("linksets", [])
        if not linksets:
            return ""
        for linksetdb in linksets[0].get("linksetdbs", []):
            dbname = linksetdb.get("dbto", "")
            # linkname=pubmed_pmc 表示文章在 PMC
            if dbname == "pmc":
                links = linksetdb.get("links", [])
                if links:
                    return str(links[0])
    except Exception as e:
        print(f"[PMC-elink] 解析失败: {e}", file=sys.stderr)
    return ""


def fetch_fulltext_pmc(pmcid: str) -> dict | None:
    """PMC efetch 全文 XML。"""
    if not pmcid:
        return None
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pmc&id={pmcid}&rettype=full&retmode=xml"
    )
    r = _safe_get(url, "eutils", EUTILS_SLEEP)
    if r is None:
        return None
    try:
        root = ET.fromstring(r.content)
        passages = []

        # 提取 body 中的 section
        body = root.find(".//body")
        if body is not None:
            for sec in body.iter("sec"):
                title_el = sec.find("title")
                sec_title = (title_el.text or "").strip() if title_el is not None else ""

                sec_texts = []
                for p in sec.findall("p"):
                    text = "".join(p.itertext()).strip()
                    if text:
                        sec_texts.append(text)

                if sec_texts:
                    passages.append({
                        "section": sec_title or "unknown",
                        "text": "\n".join(sec_texts),
                    })

        if passages:
            return {
                "source": "PMC",
                "passages": passages,
                "pmcid": pmcid,
            }
    except Exception as e:
        print(f"[PMC-fulltext] 解析失败: {e}", file=sys.stderr)
    return None


def fetch_fulltext_pubmed_abstract(pmid: str) -> dict | None:
    """PubMed efetch 摘要兜底。"""
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&id={pmid}&rettype=abstract&retmode=text"
    )
    r = _safe_get(url, "eutils", EUTILS_SLEEP)
    if r is None:
        return None
    try:
        text = r.text.strip()
        if text:
            return {
                "source": "PubMed_abstract",
                "passages": [{"section": "abstract", "text": text}],
                "pmcid": "",
            }
    except Exception as e:
        print(f"[PubMed-abstract-fallback] 失败: {e}", file=sys.stderr)
    return None


def fetch_fulltext(pmid: str) -> dict | None:
    """按优先级逐级尝试获取全文。

    优先级：PubTator > Europe PMC > PMC efetch > OpenAlex OA > PubMed efetch
    """
    # 1. PubTator 3.0
    result = fetch_fulltext_pubtator(pmid)
    if result:
        return result

    # 先获取 PMCID（用于后续 Europe PMC 和 PMC）
    pmcid = get_europepmc_pmcid(pmid)
    if not pmcid:
        pmcid = _get_pmc_id_from_pubmed(pmid)
        if pmcid and not pmcid.startswith("PMC"):
            pmcid = f"PMC{pmcid}"

    # 2. Europe PMC 全文 XML
    if pmcid:
        result = fetch_fulltext_europepmc(pmcid)
        if result:
            return result

    # 3. PMC efetch
    if pmcid:
        result = fetch_fulltext_pmc(pmcid)
        if result:
            return result

    # 4. OpenAlex OA 链接（仅返回 URL，不拉取全文）
    oa_info = get_openalex_oa(pmid)
    if oa_info and oa_info.get("oa_url"):
        return {
            "source": "OpenAlex_OA",
            "passages": [{"section": "oa_link", "text": oa_info["oa_url"]}],
            "pmcid": pmcid,
            "oa_url": oa_info["oa_url"],
            "oa_status": oa_info.get("oa_status", ""),
        }

    # 5. PubMed efetch 兜底（仅摘要）
    result = fetch_fulltext_pubmed_abstract(pmid)
    if result:
        if pmcid:
            result["pmcid"] = pmcid
        return result

    return None




# ---------------------------------------------------------------------------
# 分层过滤框架（v16）
# ---------------------------------------------------------------------------

def _build_variant_forms(cdna: str, protein_full: str, protein_short: str,
                         rs: str = "") -> list[str]:
    """构建变异的多种表示形式，用于关键词过滤。
    
    v17: 当蛋白全写和简写都为空（p.?）时，增强cDNA级别变体格式，
         包括去c.前缀、IVS命名法等，提高深内含子/非编码区变异的召回率。
    """
    forms = []
    if cdna:
        forms.append(cdna)
        # 归一化形式
        norm = _normalize_cdna_for_match(cdna)
        if norm != cdna:
            forms.append(norm)
        
        # v17: p.? 退化处理 — 增强 cDNA 变体格式
        if not protein_full and not protein_short:
            # 去除 c. 前缀的形式（如 3718-2477C>T）
            if cdna.startswith("c."):
                no_prefix = cdna[2:]
                forms.append(no_prefix)
            # IVS 命名法转换（仅剪接/深内含子变异）
            # 例: c.3718-2477C>T → IVS24-2477C>T (粗略估算内含子号)
            ivs_match = re.match(r'c\.(\d+)([+-]\d+)([A-Z]>[A-Z]|del|dup|ins)', cdna)
            if ivs_match:
                # 粗略：用c.位置估算内含子号（每外显子约150bp），实际不精确，仅用于匹配
                exon_num = max(1, int(ivs_match.group(1)) // 150 + 1)
                ivs_form = f"IVS{exon_num}{ivs_match.group(2)}{ivs_match.group(3)}"
                forms.append(ivs_form)
            # 去除 c. 前缀的归一化形式
            if norm and norm.startswith("c.") and norm != cdna:
                forms.append(norm[2:])
    
    if protein_short:
        forms.append(protein_short)
        forms.append(f"p.{protein_short}")
    if protein_full:
        forms.append(protein_full)
        forms.append(f"p.{protein_full}")
    if rs:
        forms.append(rs)
    # 去重
    seen = set()
    unique_forms = []
    for f in forms:
        if f and f not in seen:
            seen.add(f)
            unique_forms.append(f)
    return unique_forms


def _keyword_fast_filter(papers: list[dict], variant_forms: list[str],
                         gene: str, gene_aliases: list[str],
                         cdna: str = "", protein_full: str = "",
                         protein_short: str = "",
                         core_pmids: set[str] = None) -> list[dict]:
    """关键词快速过滤：零成本，检查 title+abstract 中是否包含变异签名。
    
    v18: ClinVar/HGMD核心文献直接保留；非核心文献必须匹配变异签名；
         无标题无摘要的文献，如果有LitSense命中句子则用句子做匹配，
         否则丢弃（不再盲留）；取消放宽到仅基因名匹配的逻辑。
    """
    if not variant_forms:
        return papers
    
    # v17: p.? 退化 — 蛋白为空且有 cDNA 时，优先用 cDNA 精确匹配
    is_p_question = not protein_full and not protein_short and bool(cdna)
    core_pmids = core_pmids or set()
    
    kept = []
    dropped = 0
    no_info_count = 0
    core_kept = 0
    for paper in papers:
        pmid = str(paper.get("pmid", ""))
        title = paper.get("title", "") or ""
        abstract = paper.get("abstract", "") or ""
        litsense_sents = paper.get("litsense_sentences", []) or []
        combined = title + " " + abstract + " " + " ".join(litsense_sents)
        
        # v18: 核心文献（ClinVar/HGMD关联）直接保留
        if pmid in core_pmids:
            kept.append(paper)
            core_kept += 1
            continue
        
        # 无标题无摘要无LitSense句子的文献，丢弃
        if not combined.strip():
            dropped += 1
            no_info_count += 1
            continue
        
        # 先检查基因名（词边界）
        gene_found = bool(re.search(r'\b' + re.escape(gene) + r'\b',
                                    combined, re.IGNORECASE))
        if not gene_found and gene_aliases:
            for alias in gene_aliases:
                alias = alias.strip()
                if alias and re.search(r'\b' + re.escape(alias) + r'\b',
                                       combined, re.IGNORECASE):
                    gene_found = True
                    break
        if not gene_found:
            dropped += 1
            continue
        
        # 再检查变异签名
        variant_found = False
        # v17: p.? 模式下优先用 cDNA 形式精确匹配
        if is_p_question and cdna:
            cdna_forms = [vf for vf in variant_forms
                          if vf and (vf == cdna
                                     or (cdna.startswith("c.")
                                         and vf == cdna[2:])
                                     or vf.startswith("IVS"))]
            for vf in cdna_forms:
                if vf in combined:
                    variant_found = True
                    break
        if not variant_found:
            for vf in variant_forms:
                if vf and vf in combined:
                    variant_found = True
                    break
        if variant_found:
            kept.append(paper)
        else:
            dropped += 1
    
    # v18: 取消放宽到仅基因名匹配的逻辑——非核心文献必须匹配变异签名
    info_parts = []
    if core_kept:
        info_parts.append(f"核心{core_kept}篇")
    if no_info_count:
        info_parts.append(f"{no_info_count}篇无信息(丢弃)")
    info_parts.append(f"丢弃{len(papers) - len(kept)}篇")
    print(f"  [关键词过滤] 保留{len(kept)}/{len(papers)}篇（{'，'.join(info_parts)}）",
          file=sys.stderr)
    return kept


def _llm_precision_filter(papers: list[dict], variant_forms: list[str],
                          gene: str, gene_aliases: list[str] = None,
                          is_p_question: bool = False) -> list[dict]:
    """LLM精筛：逐篇判断标题+摘要是否真正讨论目标变异。

    v1.5.0 LLM 闸门：LLM 调用失败/解析失败时抛 LLMConfigError 硬中断，
    不再静默降级为关键词过滤（引导用户配置 KEY 后重跑）。
    无标题无摘要的文献直接保留。
    
    v17: 新增 is_p_question 参数，当蛋白信息缺失时在 prompt 中特别说明
         这是深内含子/非编码区变异，需要精确匹配 cDNA 表示。
    """
    if not papers:
        return papers
    
    # 分离有信息和无信息的论文
    info_papers = []
    no_info_papers = []
    info_indices = {}  # 原始索引 -> info_papers 中的位置
    for i, paper in enumerate(papers):
        title = paper.get("title", "") or ""
        abstract = paper.get("abstract", "") or ""
        if title or abstract:
            info_indices[i] = len(info_papers)
            info_papers.append(paper)
        else:
            no_info_papers.append(paper)
    
    if not info_papers:
        print(f"  [LLM精筛] 全部{len(papers)}篇无详情，全部保留", file=sys.stderr)
        return papers
    
    variant_desc = ", ".join(variant_forms[:4]) if variant_forms else "目标变异"
    
    # 构建论文列表文本（只对有信息的做精筛）
    paper_items = []
    for i, paper in enumerate(info_papers):
        title = paper.get("title", "") or "(无标题)"
        abstract = paper.get("abstract", "") or ""
        # 截断到 500 字符
        text = (title + " " + abstract)[:500]
        paper_items.append(f"[{i}] PMID:{paper.get('pmid','?')} | {text}")
    
    prompt_lines = [
        f"判断以下文献是否真正讨论了变异 {variant_desc} 在基因 {gene} 中的临床意义、功能研究或病例报告。",
    ]
    
    # v17: p.? 退化处理 — 深内含子/非编码区变异特别说明
    if is_p_question:
        prompt_lines.append(
            "注意：这是一个深内含子/非编码区变异（蛋白改变未知，即 p.?），"
            "请特别关注文献中是否精确匹配 cDNA 表示形式（如 c.xxxx 或 IVSxx 等），"
            "不要因为文献讨论了该基因或其他变异而误判。"
        )
    
    prompt_lines.extend([
        "只返回真正讨论该特定变异的文献序号（用逗号分隔的数字列表）。",
        f"如果只是泛泛讨论该基因或某类变异，不包含具体变异 {variant_desc}，请不要列入。",
        "",
        "文献列表：",
        "\n".join(paper_items),
        "",
        "请返回符合条件的文献序号，格式如：0,2,5,7",
        "如果都不符合，返回：NONE",
    ])
    prompt = "\n".join(prompt_lines)

    try:
        # 尝试调用 LLM（在 CodeAct 环境中通过 SDK 调用）
        result_text = _call_llm_for_filter(prompt)
        
        if result_text and result_text.strip().upper() == "NONE":
            print(f"  [LLM精筛] 有信息的{len(info_papers)}篇均不匹配，"
                  f"保留{len(no_info_papers)}篇无详情", file=sys.stderr)
            return no_info_papers
        
        # 解析序号
        indices = []
        for part in re.findall(r'\d+', result_text or ""):
            idx = int(part)
            if 0 <= idx < len(info_papers):
                indices.append(idx)
        
        if indices:
            kept_info = [info_papers[i] for i in indices]
            result = kept_info + no_info_papers
            print(f"  [LLM精筛] 有信息的保留{len(kept_info)}/{len(info_papers)}篇"
                  f"，加{len(no_info_papers)}篇无详情，共{len(result)}篇",
                  file=sys.stderr)
            return result
        else:
            # v1.5.0 LLM 闸门：解析失败不再退化为关键词过滤（静默降级），改硬中断引导。
            raise LLMConfigError("[LLM 闸门] LLM 精筛返回结果无法解析，评级已中断（不静默降级为关键词过滤）。")
    
    except LLMConfigError:
        raise  # 闸门异常直接上抛，中断评级
    except Exception as e:
        # v1.5.0 LLM 闸门：调用失败不再退化为关键词过滤，改硬中断引导。
        raise LLMConfigError(
            f"[LLM 闸门] LLM 精筛调用失败，评级已中断（不静默降级为关键词过滤）：{e}"
        ) from e


def _call_llm_for_filter(prompt: str, system_prompt: str = None) -> str:
    """调用 LLM，支持结构化提取和文献精筛。

    优先级：
    1. CodeAct SDK（sdk.call_llm）— 当技能通过 CodeAct 运行时可用
    2. 通用 OpenAI 兼容通道（_call_compat_llm）— 任意兼容平台，环境变量配置
    3. Ark API（火山方舟）— 技能独立运行时的直接 HTTP 调用（向后兼容）
    v1.5.0 LLM 闸门：所有路径都失败时 raise LLMConfigError 硬中断，
    不再返回空字符串触发关键词降级（引导用户配置 KEY 后重跑）。
    """
    # ---------- 路径1: CodeAct SDK ----------
    try:
        import __main__
        sdk = getattr(__main__, 'sdk', None)
        if sdk is not None:
            sys_msg = system_prompt or "你是一个文献筛选助手，需要精确判断文献是否讨论特定基因变异。只返回序号列表，不要多余解释。"
            result = sdk.call_llm(
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": prompt}
                ]
            )
            if isinstance(result, str):
                return result
            elif hasattr(result, 'content'):
                return result.content
            else:
                return str(result)
    except Exception:
        pass  # 继续尝试 Ark API

    # ---------- 路径2: 通用 OpenAI 兼容通道（可配置任意平台，2026-10-21 改造） ----------
    # 读 LLM_BASE_URL / LLM_MODEL / LLM_API_KEY；未配置 LLM_BASE_URL 时返回 None，回退方舟。
    try:
        compat = _call_compat_llm(prompt, system_prompt)
        if compat is not None:
            return compat
    except Exception as e:
        print(f"  [LLM] 通用兼容通道调用失败: {e}", file=sys.stderr)

    # ---------- 路径3: Ark API（火山方舟，向后兼容） ----------
    try:
        return _call_ark_llm(prompt, system_prompt)
    except Exception as e:
        print(f"  [LLM] Ark API 调用失败: {e}", file=sys.stderr)
        # v1.5.0 LLM 闸门：不再返回空字符串触发关键词降级，改为硬中断 + 引导配置。
        raise LLMConfigError("[LLM 闸门] LLM 调用全部失败（CodeAct SDK / 通用兼容通道 / Ark 均不可用）。") from e


def _call_compat_llm(prompt: str, system_prompt: str = None):
    """通用 OpenAI 兼容通道（2026-10-21 新增）：可接任意 OpenAI 兼容平台
    （火山方舟 / DeepSeek / 智谱 GLM / Kimi / 通义 / OpenAI 等）。

    凭证/配置读取（全部环境变量，不硬编码平台）：
      LLM_BASE_URL — 平台 base_url，如 https://ark.cn-beijing.volces.com/api/v3
                     或 https://api.deepseek.com/v1；未配置时返回 None（表示未启用通用通道）
      LLM_MODEL    — 模型名，如 ep-xxx / deepseek-chat / glm-4 等
      LLM_API_KEY  — 平台 API Key

    返回：
      - 配置了 LLM_BASE_URL：返回 LLM 输出文本
      - 未配置 LLM_BASE_URL：返回 None（调用方回退方舟通道）
    异常时向上抛，由调用方决定降级。
    """
    import os

    base = os.environ.get("LLM_BASE_URL", "").strip()
    if not base:
        return None
    model = os.environ.get("LLM_MODEL", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not model or not api_key:
        raise RuntimeError(
            "通用兼容通道：已配置 LLM_BASE_URL 但缺少 LLM_MODEL 或 LLM_API_KEY；"
            "请补齐这三个环境变量（或改用方舟通道 ARK_API_KEY）。"
        )

    api_url = base.rstrip("/") + "/chat/completions"
    sys_msg = system_prompt or "你是一个文献筛选助手，需要精确判断文献是否讨论特定基因变异。只返回序号列表，不要多余解释。"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"通用兼容通道 HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"通用兼容通道返回空 choices: {json.dumps(data, ensure_ascii=False)[:200]}")
    content = choices[0].get("message", {}).get("content", "")
    return content.strip()


def _call_ark_llm(prompt: str, system_prompt: str = None) -> str:
    """通过火山方舟 Ark API 调用 LLM（OpenAI 兼容接口，方舟专用，向后兼容）。

    凭证读取顺序：
    1. 环境变量 ARK_API_KEY
    2. 环境变量 COZE_ARK_API_KEY（技能平台注入）
    未配置时明确报错并提示配置方式（v1.4.0 起移除内置兜底 key，避免凭据随技能分发泄露）。
    注：新代码优先走通用兼容通道 _call_compat_llm（LLM_BASE_URL/LLM_MODEL/LLM_API_KEY）；
    本函数保留供方舟专用调用与向后兼容。
    """
    import os

    api_key = (
        os.environ.get("ARK_API_KEY")
        or os.environ.get("COZE_ARK_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "未配置火山方舟 API Key：请设置环境变量 ARK_API_KEY"
            "（或 COZE_ARK_API_KEY）后重试；本技能不内置兜底 key，"
            "禁止将凭据写入代码随技能分发。"
        )
    model = os.environ.get("ARK_MODEL", "ep-20260106113130-tj2pt")
    api_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

    sys_msg = system_prompt or "你是一个文献筛选助手，需要精确判断文献是否讨论特定基因变异。只返回序号列表，不要多余解释。"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Ark API HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"Ark API 返回空 choices: {json.dumps(data, ensure_ascii=False)[:200]}")

    content = choices[0].get("message", {}).get("content", "")
    return content.strip()


def _post_filter_results(papers: list[dict], cdna: str, protein_full: str,
                         protein_short: str, rs: str, gene: str,
                         gene_aliases: list[str],
                         core_pmids: set[str] = None) -> tuple[list[dict], dict]:
    """分层过滤：
    - 去重后 < 50 篇：使用 LLM 精筛
    - 去重后 >= 50 篇：使用关键词/正则快速过滤（零成本）
    
    v18: core_pmids（ClinVar/HGMD关联文献）直接保留不参与过滤；
         非核心文献必须变异签名匹配；无信息文献不再盲留。
    """
    total = len(papers)
    filter_info = {}
    if total == 0:
        return papers, filter_info
    
    variant_forms = _build_variant_forms(cdna, protein_full, protein_short, rs)
    
    # v17: 判断是否为 p.? 情况（蛋白信息缺失）
    is_p_question = not protein_full and not protein_short and bool(cdna)
    filter_info["is_p_question"] = is_p_question
    
    # v18: 分离核心文献和非核心文献
    core_pmids = core_pmids or set()
    core_papers = [p for p in papers if str(p.get("pmid", "")) in core_pmids]
    non_core_papers = [p for p in papers if str(p.get("pmid", "")) not in core_pmids]
    
    print(f"  [分层过滤] 共 {total} 篇（核心{len(core_papers)}篇 + 非核心{len(non_core_papers)}篇），"
          f"{'LLM精筛模式' if len(non_core_papers) < 50 else '关键词快速过滤模式'}"
          f"{' (p.? 退化模式)' if is_p_question else ''}",
          file=sys.stderr)
    
    if len(non_core_papers) < 50:
        filtered_non_core = _llm_precision_filter(
            non_core_papers, variant_forms, gene, gene_aliases,
            is_p_question=is_p_question
        )
    else:
        filtered_non_core = _keyword_fast_filter(
            non_core_papers, variant_forms, gene, gene_aliases,
            cdna=cdna, protein_full=protein_full,
            protein_short=protein_short,
            core_pmids=core_pmids,
        )
    
    result = core_papers + filtered_non_core
    filter_info["core_preserved"] = len(core_papers)
    filter_info["non_core_after_filter"] = len(filtered_non_core)
    
    # v17: p.? 模式下文献数 > 300 时发出警告
    if is_p_question and len(result) > 300:
        print("[警告] 无蛋白预测，大量文献可能为基因级而非变异特异性",
              file=sys.stderr)
    
    return result, filter_info


# ---------------------------------------------------------------------------
# v17: LLM 结构化提取
# ---------------------------------------------------------------------------

STRUCTURED_EXTRACTION_SCHEMA = {
    "genotype": "杂合/纯合/复合杂合/未报告",
    "trans_variant": "复合杂合的第二变异 + cis/trans 状态/未报告",
    "de_novo": "是/否/未检测",
    "phenotype": "诊断、症状、发病年龄、严重度/未报告",
    "phenotype_consistency": "与已知疾病谱一致/可能表型扩展/无法判断",
    "biochemical": "指标名+值+参考范围/未报告",
    "family": "受累人数、共分离、近亲婚配/未报告",
    "parental_genotype": "父母各自的携带状态/未报告",
}

# v1.3.0: 按用途证据码定制提取（对应 SKILL.md「证据码 → 文献关键提取字段映射表」）
EVIDENCE_CODE_KEY_FIELDS = {
    "pm3": "①合子状态（纯合/复合杂合）②反式另一变异（cis/trans）"
           "③相位验证状态（confirmed in trans 父母验相位 / phase unknown）"
           "④是否双基因/外显不全反证",
    "ps4": "①先证者个数 ②病例数/对照数 ③OR 值与置信区间 CI（AR 必需）④患者表型一致性",
    "ps2": "①de novo 状态（是/否/未检测）②双亲验证情况 ③表型吻合度 ④是否生殖腺嵌合",
    "pm6": "①de novo 状态（是/否/未检测）②双亲验证情况 ③表型吻合度 ④是否生殖腺嵌合",
    "ps3": "①实验方法（体内/体外）②是否针对本特异变异 ③阳性/阴性对照 ④结果（功能受损/无影响）",
    "bs3": "①实验方法（体内/体外）②是否针对本特异变异 ③阳性/阴性对照 ④结果（功能受损/无影响）",
    "pm5": "①同位置已知致病变异 ②相同/不同氨基酸改变 ③已知变异分类（P/LP）",
    "ps1": "①同位置已知致病变异 ②相同/不同氨基酸改变 ③已知变异分类（P/LP）",
    "pvs1": "①截断点下游已报道致病变异 ②下游热点聚集情况 ③关键功能区证据 ④病例数",
    "pp1": "①患者数 ②分离次数（患者数−1）③家系数 ④受累/非受累成员",
    "bs2": "①健康成人携带 ②合子状态（AR纯合/AD杂合/XL半合）③无表型确认",
    "pm2": "主要为频率数据库（gnomAD/1000G/ESP），一般不提取患者文献；仅特异性阈值出处需提取",
    "bs1": "主要为频率数据库（gnomAD/1000G/ESP），一般不提取患者文献；仅特异性阈值出处需提取",
}


def _extract_structured_fields(papers: list[dict], gene: str,
                               batch_size: int = 8,
                               evidence_for: str = "") -> int:
    """v17: 对过滤后的有摘要文献，调用 LLM 提取 8 个结构化字段。
    
    每批 5-10 篇，减少 LLM 调用次数。提取结果存入 paper["structured_extraction"]。
    提取失败时保留原文献但不含 structured_extraction 字段。
    
    返回成功提取的文献数。
    """
    # 筛选有摘要的文献
    papers_with_abstract = [p for p in papers if p.get("abstract")]
    if not papers_with_abstract:
        print("  [结构化提取] 无摘要文献，跳过", file=sys.stderr)
        return 0
    
    total = len(papers_with_abstract)
    print(f"  [结构化提取] 共 {total} 篇有摘要文献，分批提取...", file=sys.stderr)
    
    success_count = 0
    batch_size = max(5, min(10, batch_size))  # 限制在 5-10 之间
    
    for batch_start in range(0, total, batch_size):
        batch = papers_with_abstract[batch_start:batch_start + batch_size]
        batch_indices = list(range(batch_start, batch_start + len(batch)))
        
        # 构建批处理 prompt
        paper_items = []
        for i, paper in enumerate(batch):
            title = paper.get("title", "") or "(无标题)"
            abstract = paper.get("abstract", "") or ""
            # 截断摘要避免过长
            abs_text = abstract[:800] if len(abstract) > 800 else abstract
            paper_items.append(
                f"[{i}] PMID:{paper.get('pmid', '?')}\n"
                f"  标题: {title}\n"
                f"  摘要: {abs_text}"
            )
        
        prompt = (
            f"你是一个医学文献信息提取助手。请从以下文献的标题和摘要中，"
            f"为每篇文献提取以下 8 个字段（基因: {gene}）：\n"
            f"1. genotype（基因型）: 杂合/纯合/复合杂合/未报告\n"
            f"2. trans_variant（反式变异）: 复合杂合的第二变异 + cis/trans 状态/未报告\n"
            f"3. de_novo: 是/否/未检测\n"
            f"4. phenotype（表型）: 诊断、症状、发病年龄、严重度/未报告\n"
            f"5. phenotype_consistency（表型一致性）: 与已知疾病谱一致/可能表型扩展/无法判断\n"
            f"6. biochemical（生化指标）: 指标名+值+参考范围/未报告\n"
            f"7. family（家系）: 受累人数、共分离、近亲婚配/未报告\n"
            f"8. parental_genotype（父母基因型）: 父母各自的携带状态/未报告\n\n"
            f"请严格按 JSON 格式返回，格式为一个对象数组，每个对象对应一篇文献，"
            f"键为序号（如 \"0\", \"1\"...），值为包含上述8个字段的对象。\n"
            f"如果某字段在文献中未提及，请填 \"未报告\"（或对应字段的默认值）。\n\n"
            f"文献列表：\n"
            f"{chr(10).join(paper_items)}\n\n"
            f"只返回 JSON，不要任何其他解释文字。"
        )

        # v1.3.0: 按用途证据码定制提取——把证据码关键字段要求并入提取 prompt
        if evidence_for:
            key_fields = EVIDENCE_CODE_KEY_FIELDS.get(evidence_for)
            if key_fields:
                prompt += (
                    f"\n【按用途证据码定制提取（本次检索服务于证据码 {evidence_for.upper()}）】\n"
                    f"除上述 8 个通用字段外，请优先提取以下该证据码的关键字段；"
                    f"提取不到必须逐字段标\"未报告/未检测/相位未知\"，"
                    f"不得用通用字段模板或推测数据填充：\n{key_fields}\n"
                )
        
        try:
            result_text = _call_llm_for_filter(
                prompt,
                system_prompt="你是一个医学文献信息提取助手，擅长从文献摘要中精确提取患者基因型、表型、家系等临床信息。只返回JSON格式结果，不要任何解释文字。"
            )
            if not result_text:
                print(f"  [结构化提取] 批次 {batch_start//batch_size + 1} LLM无响应，跳过",
                      file=sys.stderr)
                continue
            
            # 解析 JSON 结果
            extracted = _parse_structured_json(result_text, len(batch))
            if not extracted:
                print(f"  [结构化提取] 批次 {batch_start//batch_size + 1} 解析失败，跳过",
                      file=sys.stderr)
                continue
            
            # 将结果写入对应 paper
            for i, paper in enumerate(batch):
                key = str(i)
                if key in extracted and extracted[key]:
                    # v1.6.0: 写入前先过 LLM 提取校验层（C1/C2/C3），只标注不编答案。
                    # 校验状态（validation.status）随提取结果下发，供下游证据码识别可信度；
                    # 命中 invalid/conflict 的字段不得作为证据，且不静默跳过（记录在 issues）。
                    paper["structured_extraction"] = _validate_extraction(extracted[key], gene)
                    success_count += 1
            
            print(f"  [结构化提取] 批次 {batch_start//batch_size + 1} 完成，"
                  f"已提取 {success_count}/{total}", file=sys.stderr)
            
        except LLMConfigError:
            raise  # v1.5.0 LLM 闸门：LLM 通道不可用直接上抛，中断评级，不跳过批次静默继续。
        except Exception as e:
            # 非闸门异常（如单个批次 JSON 解析问题）保留原跳过逻辑，不阻断后续批次
            print(f"  [结构化提取] 批次 {batch_start//batch_size + 1} 异常: {e}",
                  file=sys.stderr)
            continue
    
    print(f"  [结构化提取] 完成，成功提取 {success_count}/{total} 篇", file=sys.stderr)
    return success_count


def _parse_structured_json(text: str, expected_count: int) -> dict:
    """v17: 解析 LLM 返回的结构化提取 JSON。
    
    兼容多种格式：标准 JSON 对象数组、markdown 代码块、纯文本数组等。
    返回 {index_str: extraction_dict} 形式的字典。
    """
    if not text:
        return {}
    
    # 清理 markdown 代码块
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    
    # 尝试直接解析
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取第一个 JSON 对象/数组
        obj_match = re.search(r'\{.*\}', text, re.DOTALL)
        arr_match = re.search(r'\[.*\]', text, re.DOTALL)
        if obj_match:
            try:
                data = json.loads(obj_match.group())
            except json.JSONDecodeError:
                data = None
        elif arr_match:
            try:
                data = json.loads(arr_match.group())
            except json.JSONDecodeError:
                data = None
        else:
            data = None
    
    if data is None:
        return {}
    
    result = {}
    
    # 如果是列表，转为 {index: item}
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                result[str(i)] = item
    # 如果是字典
    elif isinstance(data, dict):
        # 检查是否是 {"0": {...}, "1": {...}} 格式
        for key, value in data.items():
            if isinstance(value, dict):
                result[str(key)] = value
            # 尝试解析可能的嵌套
            elif key.isdigit() and isinstance(value, dict):
                result[key] = value
    
    # 标准化字段名
    standardized = {}
    valid_fields = set(STRUCTURED_EXTRACTION_SCHEMA.keys())
    for idx, fields in result.items():
        if not isinstance(fields, dict):
            continue
        std = {}
        for field in valid_fields:
            if field in fields:
                std[field] = str(fields[field])
            else:
                std[field] = "未报告"
        standardized[idx] = std
    
    return standardized


# ---------------------------------------------------------------------------
# LLM 提取校验层（v1.6.0 新增，2026-10-22）
# 铁律：LLM 提取的 8 字段未经校验不得直接进入证据累分。
# 三类校验：C1 枚举合法性 / C2 内部一致性 / C3 ClinVar 权威基线交叉核对。
# 只"标注 + 降置信度"，绝不替 LLM 编答案；冲突字段必须显式记录，不得静默。
# ---------------------------------------------------------------------------

# C1：枚举字段合法取值（LLM 乱填自由文本 → invalid）
_EXTRACTION_ENUMS = {
    "genotype": {"杂合", "纯合", "复合杂合", "未报告"},
    "de_novo": {"是", "否", "未检测", "未报告"},
    "phenotype_consistency": {"与已知疾病谱一致", "可能表型扩展", "无法判断", "未报告"},
}


def _validate_c1_enums(fields: dict) -> list:
    """C1 枚举合法性：genotype/de_novo/phenotype_consistency 必须是白名单取值。
    LLM 返回的自由文本/越界取值直接判 invalid，不得当作真实证据。
    """
    issues = []
    for field, allowed in _EXTRACTION_ENUMS.items():
        val = (fields.get(field) or "").strip()
        if val and val != "未报告" and val not in allowed:
            issues.append({"field": field, "level": "invalid", "got": val,
                           "expected": "|".join(sorted(allowed))})
    return issues


def _validate_c2_consistency(fields: dict) -> list:
    """C2 内部一致性：抓 LLM 逻辑自相矛盾的提取。
    纯合+反式第二变异、复合杂合无反式、de novo 无双亲验证，均为内部矛盾。
    """
    issues = []
    gt = (fields.get("genotype") or "").strip()
    trans = (fields.get("trans_variant") or "").strip()
    denovo = (fields.get("de_novo") or "").strip()
    parental = (fields.get("parental_genotype") or "").strip()

    # 纯合不可能有反式第二变异（反式=两个不同等位基因，纯合仅一个）
    if gt == "纯合" and trans and trans != "未报告":
        issues.append({"field": "trans_variant", "level": "conflict",
                       "reason": f"genotype=纯合 但 trans_variant 非空({trans[:40]})，纯合无第二等位基因"})
    # 复合杂合必须给出第二变异
    if gt == "复合杂合" and (not trans or trans == "未报告"):
        issues.append({"field": "trans_variant", "level": "conflict",
                       "reason": "genotype=复合杂合 但未报告反式第二变异"})
    # de novo 必须要有双亲验证信息
    if denovo == "是" and (not parental or parental == "未报告"):
        issues.append({"field": "parental_genotype", "level": "conflict",
                       "reason": "de_novo=是 但 parental_genotype=未报告，de novo 需双亲验证"})
    return issues


# C3：权威基线交叉核对。ClinVar 公开 API 默认开启；HGMD 为商业库不随包，接口保留默认关闭。
_C3_CLINVAR_ENABLED = True
_C3_HGMD_ENABLED = False  # HGMD 商业库；如需接入，在此设 True 并实现 _hgmd_lookup


def _clinvar_lookup(variant_str: str, gene: str = "", timeout: int = 8) -> dict:
    """ClinVar Variant API 查询给定变异（HGVS/rs），返回是否存在于权威库。
    仅作"提取的 trans_variant 是否真实存在"的交叉核对，不做裁决。
    语义约定：exists=True 仅表示 ClinVar 存在含该变异串的记录，不判致病性
    （pathogenic_cls 统一为 "exists"，不再称 known，避免把"存在记录"误当"已知致病"）。
    检索式拼入基因限定（gene 可用时）以降低跨基因假阳性；查询前走限速对齐文件内其他 E-utilities 调用。
    HGMD 通道为预留接口（默认关闭），见 _hgmd_lookup。
    """
    if not variant_str or variant_str == "未报告":
        return {"exists": None, "pathogenic_cls": None, "source": "skip"}
    try:
        g = (gene or "").strip()
        if g:
            term = '{0}[Gene Name] AND "{1}"[All Fields]'.format(g, variant_str)
        else:
            term = '"{0}"[All Fields]'.format(variant_str)
        # ESearch ClinVar：term 用 基因+变异 / 变异 查询，retmax=5
        _rate_limit("eutils", EUTILS_SLEEP)
        url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
               "?db=clinvar&term=" + quote(term) +
               "&retmode=json&retmax=5")
        r = _std_requests.get(url, timeout=timeout,
                              headers={"User-Agent": "acmg-literature-skill/1.6"})
        if r.status_code != 200:
            return {"exists": None, "pathogenic_cls": None, "source": "unreachable",
                    "status": r.status_code}
        ids = (r.json().get("esearchresult", {}).get("idlist", []) or [])
        if not ids:
            return {"exists": False, "pathogenic_cls": None, "source": "clinvar"}
        return {"exists": True, "pathogenic_cls": "exists", "source": "clinvar"}
    except Exception as e:  # noqa: BLE001
        return {"exists": None, "pathogenic_cls": None, "source": "error",
                "error": str(e)[:60]}


def _hgmd_lookup(variant_str: str, gene: str = "") -> dict:
    """HGMD 交叉核对接口（预留，默认关闭，见 _C3_HGMD_ENABLED）。
    HGMD 为商业数据库，不随包分发；需用户自备授权（HGMD_QUERY_DIR 桌面目录）后启用。
    当前实现返回 disabled，不发起任何商业查询。
    """
    return {"exists": None, "pathogenic_cls": None, "source": "hgmd_disabled"}


def _validate_c3_baseline(fields: dict, gene: str) -> list:
    """C3 权威基线核对：trans_variant 是否在 ClinVar 已知致病位点（HGMD 接口默认关闭）。"""
    issues = []
    trans = (fields.get("trans_variant") or "").strip()
    if not trans or trans == "未报告":
        return issues

    if _C3_CLINVAR_ENABLED:
        res = _clinvar_lookup(trans, gene)
        if res["source"] == "clinvar" and res["exists"] is False:
            issues.append({"field": "trans_variant", "level": "unverified",
                           "reason": f"trans_variant '{trans[:40]}' 在 ClinVar 未检索到记录，需人工核实"})
        elif res["source"] == "unreachable":
            issues.append({"field": "trans_variant", "level": "check_failed",
                           "reason": "ClinVar 查询不可达，无法交叉核对，标待核实"})
    elif _C3_HGMD_ENABLED:
        res = _hgmd_lookup(trans, gene)
        if res["source"] == "hgmd_disabled":
            issues.append({"field": "trans_variant", "level": "check_failed",
                           "reason": "HGMD 通道未启用，trans_variant 无法交叉核对"})
    return issues


def _validate_extraction(fields: dict, gene: str = "") -> dict:
    """对单篇文献的 8 字段提取做 C1/C2/C3 三重校验，返回带 validation 的增强 dict。
    只标注/降置信度，绝不替 LLM 编答案；异常必须显式记录（不静默出口）。

    校验状态语义：
      clean      无任何问题，confidence=high
      has_issue  仅 unverified/check_failed 级（如 ClinVar 查不到），字段仍可用，confidence=medium
      invalid    存在枚举非法或内部矛盾（conflict/invalid），该字段不可作为证据，confidence=low
    """
    issues = []
    issues += _validate_c1_enums(fields)
    issues += _validate_c2_consistency(fields)
    issues += _validate_c3_baseline(fields, gene)

    level_count = {}
    for it in issues:
        level_count[it["level"]] = level_count.get(it["level"], 0) + 1

    if not issues:
        status = "clean"
    elif "invalid" in level_count or "conflict" in level_count:
        status = "invalid"
    else:
        status = "has_issue"

    validated = dict(fields)
    validated["validation"] = {
        "status": status,
        "issues": issues,
        "confidence": "high" if status == "clean"
                       else ("low" if status == "invalid" else "medium"),
        "checks": {"c1_enum": True, "c2_consistency": True,
                    "c3_clinvar": _C3_CLINVAR_ENABLED, "c3_hgmd": _C3_HGMD_ENABLED},
    }
    return validated


# ---------------------------------------------------------------------------
# 合并与去重
# ---------------------------------------------------------------------------

def merge_results(search_summary: dict, papers_by_pmid: dict) -> tuple[list[dict], dict]:
    """合并所有检索结果，去重并记录来源。

    返回 (papers_list, dedup_info)
    """
    # 按来源统计 PMID 数
    by_source = {}
    source_map = {
        "hgmd": "HGMD",  # v17: HGMD 变异数据库
        "clinvar_elink": "ClinVar",
        "pubtator": "PubTator",
        "litsense": "LitSense",  # v16: LitVar2 已移除
        "pubmed": "PubMed",
        "openalex": "OpenAlex",
        "semantic_scholar": "SemanticScholar",
        "europepmc": "EuropePMC",
    }

    for key, source_name in source_map.items():
        info = search_summary.get(key, {})
        if isinstance(info, dict):
            pmids = info.get("pmids", [])
            by_source[source_name] = len(pmids)

    # 预先构建 source -> set(pmid) 映射，避免 O(n²) 重复查找
    source_pmids: dict[str, set] = {}
    for key, source_name in source_map.items():
        info = search_summary.get(key, {})
        if isinstance(info, dict):
            source_pmids[source_name] = set(
                str(p) for p in info.get("pmids", [])
            )
        else:
            source_pmids[source_name] = set()

    # 补全 papers 信息
    all_pmids = set()
    for pmid_set in source_pmids.values():
        all_pmids.update(pmid_set)

    # 确保每个 PMID 都有一条 paper 记录
    for pmid in all_pmids:
        if pmid not in papers_by_pmid:
            papers_by_pmid[pmid] = {
                "pmid": pmid,
                "title": "",
                "authors": [],
                "journal": "",
                "year": "",
                "abstract": "",
                "pmcid": "",
                "doi": "",
                "sources": [],
                "oa_url": "",
            }
        # 确保 sources 是 list 类型（兼容 set 输入）
        if not isinstance(papers_by_pmid[pmid]["sources"], list):
            papers_by_pmid[pmid]["sources"] = list(papers_by_pmid[pmid]["sources"])
        # 添加来源 — 使用 set 做 O(1) 查找
        for source_name, pmid_set in source_pmids.items():
            if pmid in pmid_set:
                if source_name not in papers_by_pmid[pmid]["sources"]:
                    papers_by_pmid[pmid]["sources"].append(source_name)

    # 从 openalex oa_info 补充 OA URL
    oa_info = search_summary.get("openalex", {}).get("oa_info", {})
    for pmid, info in oa_info.items():
        pmid_str = str(pmid)
        if pmid_str in papers_by_pmid:
            if info.get("oa_url"):
                papers_by_pmid[pmid_str]["oa_url"] = info["oa_url"]
            if info.get("doi") and not papers_by_pmid[pmid_str].get("doi"):
                papers_by_pmid[pmid_str]["doi"] = info["doi"]

    papers_list = sorted(
        papers_by_pmid.values(),
        key=lambda x: (len(x.get("sources", [])), x.get("year", "")),
        reverse=True,
    )

    dedup_info = {
        "total_unique_pmids": len(all_pmids),
        "by_source": by_source,
    }

    return papers_list, dedup_info


# ---------------------------------------------------------------------------
# v17: HGMD 变异查询（通过 subprocess 调用）
# ---------------------------------------------------------------------------

# HGMD 变异匹配辅助（v1.7.1：修复 cDNA 位置近似 bug——cDNA 位置编号≠基因组坐标，改为 aa_change 抽 c. 精确匹配）
_AA3TO1 = {
    "ala": "A", "arg": "R", "asn": "N", "asp": "D", "cys": "C", "gln": "Q",
    "glu": "E", "gly": "G", "his": "H", "ile": "I", "leu": "L", "lys": "K",
    "met": "M", "phe": "F", "pro": "P", "ser": "S", "thr": "T", "trp": "W",
    "tyr": "Y", "val": "V", "xaa": "X", "ter": "*",
}


def _protein_norm(prot):
    """蛋白表达归一化：去 p. 前缀 + 三字母氨基酸转一字母。
    例：p.Gly12Valfs*2 → G12Vfs*2（与 HGMD 单字母写法一致，可比）。"""
    if not prot:
        return prot
    s = prot.strip().lower()
    if s.startswith("p."):
        s = s[2:]
    out, i = [], 0
    while i < len(s):
        tri = s[i:i + 3]
        if tri in _AA3TO1:
            out.append(_AA3TO1[tri])
            i += 3
        else:
            # 单字母氨基酸（HGMD 单字母写法）转大写，与三字母转出对齐
            out.append(s[i].upper() if s[i].isalpha() else s[i])
            i += 1
    return "".join(out)


def _hgmd_cdna_from_aa_change(aa_change):
    """从 HGMD aa_change（如 GJB2:NM_004004.6:exon2:c.35delG:p.G12Vfs*2）抽 cDNA 表达 c.35delG。"""
    if not aa_change:
        return ""
    m = re.search(r"c\.[A-Za-z0-9_*>\-delins]+", aa_change, re.IGNORECASE)
    return m.group(0) if m else ""


def _cdna_pos_and_type_match(a, b):
    """HGMD 变异 cDNA 匹配：位置编号一致且变异类型一致；del/dup/ins 带碱基时须碱基一致（防跨位置/跨碱基误配）。
    输入用未归一化的原始 cDNA（保留 del/dup 后的碱基），避免 normalize 剥碱基造成 c.35delG 与 c.35delT 误配。"""
    if not a or not b:
        return False
    m1 = re.match(r"c\.(\d+)", a)
    m2 = re.match(r"c\.(\d+)", b)
    if not (m1 and m2) or m1.group(1) != m2.group(1):
        return False
    s1 = _extract_variant_signature(a)
    s2 = _extract_variant_signature(b)
    if not (s1 and s2) or s1[0] != s2[0]:
        return False
    if s1[0] == "snv":
        return len(s1) > 1 and s1[1:] == s2[1:]
    # del/dup/ins/delins：两边都带碱基时须碱基一致；任一边无碱基（省略写法）则按类型一致兜底
    if len(s1) > 1 and len(s2) > 1 and s1[1] and s2[1]:
        return s1[1] == s2[1]
    return True


def search_hgmd(gene: str, cdna: str = "", protein_full: str = "",
                protein_short: str = "") -> dict:
    """v17: 通过 subprocess 调用 HGMD 变异查询脚本。
    
    返回格式: {
        "status": "ok" | "error",
        "pmids": [...],         # 匹配到目标变异的 PMID 列表
        "all_pmids": [...],     # 基因所有变异的 PMID（去重）
        "matched_variants": [...],  # 匹配到的变异详情
        "total_variants": int,  # 基因总变异数
        "error": "...",         # 错误信息（如有）
    }
    
    如果 HGMD 调用失败，返回 status="error" 但不抛出异常，不阻塞主流程。
    """
    import subprocess
    import os
    
    result = {
        "status": "error",
        "pmids": [],
        "all_pmids": [],
        "matched_variants": [],
        "total_variants": 0,
        "error": "",
    }
    
    if not gene:
        result["error"] = "无基因名，跳过HGMD查询"
        return result
    
    # 确定脚本路径（2026-10-21 HGMD 剥离）：优先读环境变量 HGMD_QUERY_DIR（指向外部专用文件夹），
    # 其次回退技能群内部相对路径。数据已从技能群摘出，外部专用文件夹承载 HGMD 数据 + search.py。
    # HGMD_QUERY_DIR 指向含 search.py 的目录（如 C:\Users\DELL\Desktop\HGMD数据专用区\hgmd-variant-query）。
    script_dir = os.path.dirname(os.path.abspath(__file__))
    query_dir = os.environ.get("HGMD_QUERY_DIR", "").strip()
    if query_dir:
        hgmd_script = os.path.join(os.path.abspath(query_dir), "search.py")
    else:
        hgmd_script = os.path.join(script_dir, "..", "hgmd-variant-query", "search.py")
        hgmd_script = os.path.abspath(hgmd_script)
    
    # 用户显式确认"不配置 HGMD"：HGMD_SKIP=1 → 跳过 HGMD 数据库资源（走 ClinVar/文献通道，明确记录不静默）
    if os.environ.get("HGMD_SKIP", "").strip().lower() in ("1", "true", "yes", "y"):
        result["status"] = "skipped_user_opted_out"
        result["error"] = ("用户确认不配置 HGMD（HGMD_SKIP=1）：本次跳过 HGMD 数据库资源，"
                           "走 ClinVar/文献检索通道（已明确跳过、不静默）。")
        return result

    if not os.path.exists(hgmd_script):
        result["status"] = "missing_config"
        result["error"] = (
            f"HGMD 数据缺失：未找到取数脚本 search.py（期望路径 {hgmd_script}）。"
            "【配置 HGMD】HGMD 为商业数据库、不随技能群分发，需在目标机器准备三件套并设环境变量："
            "① 建目录（如 C:\\Users\\<你>\\Desktop\\HGMD数据专用区\\hgmd-variant-query），放入 search.py + "
            "hgmd_pro_2024.1.hg19_multianno.xlsx（商业授权数据表，同名同列结构）；"
            "② 设环境变量 HGMD_QUERY_DIR=<该目录>（Windows 持久：setx HGMD_QUERY_DIR \"<该目录>\"；"
            "临时：set HGMD_QUERY_DIR=<该目录>）；"
            "③ 首次查询自动建 .hgmd.db 索引（需 pip install openpyxl）。"
            "若暂无 HGMD 商业授权数据：设 HGMD_SKIP=1 跳过 HGMD 资源（走 ClinVar/文献检索通道，不静默）。"
            "详细步骤见 ev-variant-literature-patient SKILL.md「HGMD 配置指南」。"
        )
        return result
    
    try:
        proc = subprocess.run(
            [sys.executable, hgmd_script, "--gene", gene, "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        
        if proc.returncode != 0:
            result["error"] = f"HGMD脚本执行失败 (exit={proc.returncode}): {proc.stderr.strip()[:200]}"
            return result
        
        data = json.loads(proc.stdout)
        
        if "error" in data:
            result["error"] = data["error"]
            return result
        
        variants = data.get("variants", [])
        result["total_variants"] = data.get("total", len(variants))
        
        # 收集所有 PMID
        all_pmids_set = set()
        for v in variants:
            for pmid in v.get("pmids", []):
                all_pmids_set.add(str(pmid))
        result["all_pmids"] = list(all_pmids_set)
        
        # 匹配目标变异（用 cDNA 或蛋白名匹配）
        matched_variants = []
        matched_pmids = set()

        # 归一化目标变异用于匹配
        target_cdna_norm = _normalize_cdna_for_match(cdna) if cdna else ""
        target_protein = (protein_full or protein_short or "").strip().lower()
        target_protein_norm = _protein_norm(target_protein)

        for v in variants:
            aa_change = v.get("aa_change", "") or ""
            var_text = " ".join([aa_change, v.get("exonic_func", "") or ""]).lower()

            # 蛋白名匹配（先归一化单字母，兼容标准 HGVS 三字母 ↔ HGMD 单字母）
            hgmd_protein_norm = ""
            pm = re.search(r"p\.[A-Za-z0-9*]+", aa_change, re.IGNORECASE)
            if pm:
                hgmd_protein_norm = _protein_norm(pm.group(0))
            if target_protein_norm and hgmd_protein_norm and target_protein_norm in hgmd_protein_norm:
                matched_variants.append(v)
                for pmid in v.get("pmids", []):
                    matched_pmids.add(str(pmid))
                continue
            # 兼容 HGMD 单字母蛋白原文直接子串
            if target_protein and target_protein in var_text:
                matched_variants.append(v)
                for pmid in v.get("pmids", []):
                    matched_pmids.add(str(pmid))
                continue

            # cDNA 匹配（v1.7.1）：从 HGMD aa_change 抽 c. 表达，位置+类型一致才匹配（修位置近似 bug）
            if cdna:
                hgmd_cdna = _hgmd_cdna_from_aa_change(aa_change)
                if hgmd_cdna:
                    # 用原始 cDNA（保留碱基）比较，防 c.35delG vs c.35delT 误配
                    if _cdna_pos_and_type_match(hgmd_cdna, cdna):
                        matched_variants.append(v)
                        for pmid in v.get("pmids", []):
                            matched_pmids.add(str(pmid))
                        continue
                else:
                    # 深内含子等 aa_change 无 cDNA：保留位置近似兜底（cDNA 位置编号≠基因组坐标，结果仅供参考）
                    pos_match = re.match(r"c\.(\d+)", cdna)
                    if pos_match:
                        target_pos = int(pos_match.group(1))
                        var_pos_str = v.get("position", "")
                        if var_pos_str.isdigit() and abs(int(var_pos_str) - target_pos) <= 10:
                            matched_variants.append(v)
                            for pmid in v.get("pmids", []):
                                matched_pmids.add(str(pmid))

        result["matched_variants"] = matched_variants
        result["pmids"] = list(matched_pmids)
        result["status"] = "ok"
        
        print(f"  [HGMD] 基因{gene}共{result['total_variants']}条变异，"
              f"匹配到{len(matched_variants)}条目标变异相关，"
              f"{len(matched_pmids)}篇相关文献", file=sys.stderr)
        
        return result
        
    except subprocess.TimeoutExpired:
        result["error"] = "HGMD查询超时"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

SEARCH_MODES = [
    "all", "hgmd", "clinvar", "pubtator", "litsense",
    "pubmed", "openalex", "semantic_scholar", "europepmc"
]
FULLTEXT_MODES = ["abstract", "fulltext"]
ALL_MODES = SEARCH_MODES + FULLTEXT_MODES


def main():
    """主函数：解析参数并执行文献检索。"""
    parser = argparse.ArgumentParser(
        description="变异文献检索-查患者：8路多路检索引擎（v17）")

    # 变异参数
    parser.add_argument("--gene", default="", help="基因名（如 BRCA1）")
    parser.add_argument("--variant-cdna", default="",
                        help="cDNA 描述（如 c.5266dupC）")
    parser.add_argument("--variant-protein-full", default="",
                        help="蛋白全写（如 Arg1756Pro）")
    parser.add_argument("--variant-protein-short", default="",
                        help="蛋白简写（如 R1756P）")
    parser.add_argument("--variant-aa-pos", default="",
                        help="氨基酸位置（如 1756）")
    parser.add_argument("--rs", default="", help="rs号（可选）")
    parser.add_argument("--clinvar-uid", default="",
                        help="ClinVar UID（可选）")
    parser.add_argument("--gene-aliases", default="",
                        help="基因曾用名，逗号分隔（可选）")
    parser.add_argument("--disease-cn", default="",
                        help="疾病中文名（可选，用于中文搜索链接）")
    parser.add_argument("--for", dest="evidence_for", default="",
                        help="用途证据码（pm3/ps4/ps2/pm6/ps3/bs3/pm5/ps1/"
                             "pvs1/pp1/bs2/pm2/bs1）：按证据码定制结构化提取的"
                             "关键字段（对应 SKILL.md 证据码→关键字段映射表，"
                             "v1.3.0 强制要求声明）")

    # 控制参数
    parser.add_argument("--max", type=int, default=30,
                        help="每个检索式最大返回数（默认 30）")
    parser.add_argument("--mode", default="all",
                        help="检索模式: all/hgmd/clinvar/pubtator/"
                             "litsense/pubmed/openalex/semantic_scholar/"
                             "europepmc/abstract/fulltext (v17新增HGMD)")
    parser.add_argument("--pmids", default="",
                        help="abstract/fulltext 模式下逗号分隔的 PMID 列表")

    # 兼容旧版：位置参数 queries
    parser.add_argument("queries", nargs="*", help="（兼容旧版）检索式列表")

    args = parser.parse_args()

    # v1.5.0 LLM 闸门：启动即校验（仅对本技能需要 LLM 的模式生效）。
    # all 模式（多路检索+分层过滤）与 abstract/fulltext 模式下若走结构化提取/LLM精筛
    # 都依赖 LLM 通道；纯取摘要/全文的 abstract/fulltext 子模式不依赖 LLM，放行。
    # 具体判定在调用点由 _call_llm_for_filter 再次把关，这里做前置硬闸门。
    mode_lc = args.mode.strip().lower()
    if mode_lc in ("all", "hgmd", "pubtator", "litsense", "pubmed",
                   "openalex", "semantic_scholar", "europepmc", "clinvar"):
        _ensure_llm_env()

    gene = args.gene.strip()
    cdna = args.variant_cdna.strip()
    protein_full = args.variant_protein_full.strip()
    protein_short = args.variant_protein_short.strip()
    rs = args.rs.strip()
    clinvar_uid = args.clinvar_uid.strip()
    gene_aliases = [a.strip() for a in args.gene_aliases.split(",")
                    if a.strip()] if args.gene_aliases else []
    disease_cn = args.disease_cn.strip()
    max_results = args.max
    mode = args.mode.strip().lower()
    evidence_for = args.evidence_for.strip().lower()
    if evidence_for and evidence_for not in EVIDENCE_CODE_KEY_FIELDS:
        print(json.dumps(
            {"warning": f"未知用途证据码: {evidence_for}，可选: "
                        f"{', '.join(sorted(EVIDENCE_CODE_KEY_FIELDS))}。"
                        f"将按通用 8 字段提取，不启用按证据码定制。"},
            ensure_ascii=False, indent=2))

    # --- abstract 模式 ---
    if mode == "abstract":
        pmids = [p.strip() for p in args.pmids.split(",") if p.strip()]
        if not pmids:
            print(json.dumps({"error": "未提供 PMID"},
                             ensure_ascii=False, indent=2))
            return
        try:
            abstracts = fetch_pubmed_abstracts(pmids)
            print(json.dumps({"abstracts": abstracts},
                             ensure_ascii=False, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e), "abstracts": {}},
                             ensure_ascii=False, indent=2))
        return

    # --- fulltext 模式 ---
    if mode == "fulltext":
        pmids = [p.strip() for p in args.pmids.split(",") if p.strip()]
        if not pmids:
            print(json.dumps({"error": "未提供 PMID"},
                             ensure_ascii=False, indent=2))
            return

        try:
            fulltexts = {}
            for pmid in pmids:
                try:
                    result = fetch_fulltext(pmid)
                    if result:
                        fulltexts[pmid] = result
                except Exception as e:
                    print(f"[fulltext] pmid={pmid} 获取失败: {e}",
                          file=sys.stderr)

            print(json.dumps({"fulltexts": fulltexts},
                             ensure_ascii=False, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e), "fulltexts": {}},
                             ensure_ascii=False, indent=2))
        return

    # --- 检索模式 ---
    if mode not in SEARCH_MODES:
        print(json.dumps(
            {"error": f"无效模式: {mode}，可选: {', '.join(ALL_MODES)}"},
            ensure_ascii=False, indent=2))
        return

    # 检查必要参数
    if not gene:
        print(json.dumps(
            {"error": "必须提供 --gene 参数"},
            ensure_ascii=False, indent=2))
        return

    start_time = time.monotonic()
    search_summary: dict = {}
    papers_by_pmid: dict = {}

    def _collect_papers(papers: list[dict]):
        """从 paper 列表收集到 papers_by_pmid。"""
        for p in papers:
            pmid = str(p.get("pmid", ""))
            if not pmid:
                continue
            if pmid not in papers_by_pmid:
                papers_by_pmid[pmid] = {
                    "pmid": pmid,
                    "title": p.get("title", ""),
                    "authors": p.get("authors", []),
                    "journal": p.get("journal", ""),
                    "year": p.get("year", ""),
                    "abstract": p.get("abstract", ""),
                    "pmcid": p.get("pmcid", ""),
                    "doi": p.get("doi", ""),
                    "sources": sorted(p.get("sources", set())),
                    "oa_url": p.get("oa_url", ""),
                }
            else:
                # 补全信息
                existing = papers_by_pmid[pmid]
                if not existing.get("title") and p.get("title"):
                    existing["title"] = p["title"]
                if not existing.get("abstract") and p.get("abstract"):
                    existing["abstract"] = p["abstract"]
                if not existing.get("pmcid") and p.get("pmcid"):
                    existing["pmcid"] = p["pmcid"]
                if not existing.get("doi") and p.get("doi"):
                    existing["doi"] = p["doi"]
                if not existing.get("journal") and p.get("journal"):
                    existing["journal"] = p["journal"]
                if not existing.get("year") and p.get("year"):
                    existing["year"] = p["year"]
                if not existing.get("authors") and p.get("authors"):
                    existing["authors"] = p["authors"]
                if not existing.get("oa_url") and p.get("oa_url"):
                    existing["oa_url"] = p["oa_url"]
                if p.get("sources"):
                    for s in p["sources"]:
                        if s not in existing["sources"]:
                            existing["sources"].append(s)

    try:

        # 0. HGMD 变异数据库（v17，本地 subprocess 调用，不影响网络超时）
        if mode in ("all", "hgmd"):
            print("[0/8] HGMD 变异数据库 ...", file=sys.stderr)
            try:
                hgmd_result = search_hgmd(gene, cdna, protein_full, protein_short)
                search_summary["hgmd"] = hgmd_result
                # 将匹配到的 PMID 加入 papers_by_pmid，标记来源为 "HGMD"
                if hgmd_result.get("status") == "ok":
                    for pmid in hgmd_result.get("pmids", []):
                        pmid = str(pmid)
                        if pmid not in papers_by_pmid:
                            papers_by_pmid[pmid] = {
                                "pmid": pmid,
                                "title": "",
                                "authors": [],
                                "journal": "",
                                "year": "",
                                "abstract": "",
                                "pmcid": "",
                                "doi": "",
                                "sources": ["HGMD"],
                                "oa_url": "",
                            }
                        else:
                            if "HGMD" not in papers_by_pmid[pmid]["sources"]:
                                papers_by_pmid[pmid]["sources"].append("HGMD")
                    status_info = f"{hgmd_result['total_variants']}变异/{len(hgmd_result['pmids'])}篇"
                else:
                    status_info = hgmd_result.get("error", "error")[:50]
                    if hgmd_result.get("status") in ("missing_config", "skipped_user_opted_out"):
                        # 完整打印 HGMD 缺失/跳过提示（不静默），其余检索通道照常继续
                        print(f"  [HGMD-可选配置] {hgmd_result.get('error', '')}", file=sys.stderr)
                print(f"  → {hgmd_result.get('status', 'error')}: {status_info}",
                      file=sys.stderr)
            except Exception as e:
                print(f"  → 异常: {e}", file=sys.stderr)
                search_summary["hgmd"] = {
                    "status": f"error: {e}",
                    "pmids": [], "all_pmids": [],
                    "matched_variants": [], "total_variants": 0,
                    "error": str(e),
                }

        # 1. ClinVar elink
        if mode in ("all", "clinvar"):
            print("[1/8] ClinVar elink ...", file=sys.stderr)
            try:
                # 未提供 clinvar_uid 时自动查找
                auto_uid = ""
                if not clinvar_uid and gene and (cdna or rs):
                    auto_uid = _lookup_clinvar_uid(gene, cdna, rs)
                    if auto_uid:
                        print(f"  → 自动查找到 ClinVar UID: {auto_uid}",
                              file=sys.stderr)
                        clinvar_uid = auto_uid

                cv_result = search_clinvar_elink(clinvar_uid)
                if auto_uid:
                    cv_result["auto_looked_up_uid"] = auto_uid
                search_summary["clinvar_elink"] = cv_result
                print(f"  → {cv_result['count']} PMIDs ({cv_result['status']})",
                      file=sys.stderr)
            except Exception as e:
                print(f"  → 异常: {e}", file=sys.stderr)
                search_summary["clinvar_elink"] = {
                    "count": 0, "pmids": [], "status": f"error: {e}"
                }

            if time.monotonic() - start_time > 110:
                print("[超时] 接近 120s 限制，终止剩余检索", file=sys.stderr)
                mode = "_timeout"

        # v21: ClinVar 优先短路 — ClinVar 文献充分时跳过低收益路径
        _cv_count = search_summary.get("clinvar_elink", {}).get("count", 0)
        _clinvar_rich = _cv_count >= 10
        if _clinvar_rich:
            print(f"[优化] ClinVar 已关联 {_cv_count} 篇文献，"
                  f"跳过 LitSense / Semantic Scholar（低收益路径）",
                  file=sys.stderr)

        # 2. PubTator
        if mode in ("all", "pubtator"):
            print("[2/8] PubTator 3.0 ...", file=sys.stderr)
            try:
                pt_result = search_pubtator(
                    gene, protein_full, protein_short, cdna, rs,
                    max_results, gene_aliases
                )
                search_summary["pubtator"] = pt_result
                print(f"  → {pt_result['count']} PMIDs", file=sys.stderr)
            except Exception as e:
                print(f"  → 异常: {e}", file=sys.stderr)
                search_summary["pubtator"] = {
                    "count": 0, "pmids": [], "entity_ids": [],
                    "status": f"error: {e}"
                }

            if time.monotonic() - start_time > 110:
                print("[超时] 接近 120s 限制，终止剩余检索", file=sys.stderr)
                mode = "_timeout"

        # 3. LitSense（v21: ClinVar 文献充分时跳过）
        if mode in ("all", "litsense") and not _clinvar_rich:
            print("[3/8] LitSense ...", file=sys.stderr)
            try:
                ls_result = search_litsense(
                    gene, protein_full, protein_short, disease_cn,
                    topk=min(max_results, 20), gene_aliases=gene_aliases,
                    cdna=cdna, rs=rs
                )
                search_summary["litsense"] = ls_result
                print(f"  → {ls_result['count']} PMIDs", file=sys.stderr)
            except Exception as e:
                print(f"  → 异常: {e}", file=sys.stderr)
                search_summary["litsense"] = {
                    "count": 0, "pmids": [], "status": f"error: {e}"
                }

            if time.monotonic() - start_time > 110:
                print("[超时] 接近 120s 限制，终止剩余检索", file=sys.stderr)
                mode = "_timeout"

        # 5. PubMed
        if mode in ("all", "pubmed"):
            print("[4/8] PubMed ...", file=sys.stderr)
            try:
                pm_result = search_pubmed(
                    gene, cdna, protein_full, protein_short, rs,
                    gene_aliases, max_results
                )
                search_summary["pubmed"] = {
                    "count": pm_result["count"],
                    "pmids": pm_result["pmids"],
                    "status": pm_result["status"],
                }
                _collect_papers(pm_result["papers"])
                print(f"  → {pm_result['count']} PMIDs", file=sys.stderr)
            except Exception as e:
                print(f"  → 异常: {e}", file=sys.stderr)
                search_summary["pubmed"] = {
                    "count": 0, "pmids": [], "status": f"error: {e}"
                }

            if time.monotonic() - start_time > 110:
                print("[超时] 接近 120s 限制，终止剩余检索", file=sys.stderr)
                mode = "_timeout"

        # 6. OpenAlex（需要已知 PMID 来扩展引用，放在 PubMed 之后）
        if mode in ("all", "openalex"):
            print("[5/8] OpenAlex ...", file=sys.stderr)
            # v17: 限流保护 — 检查是否应跳过
            if _check_rate_limit_skip("openalex", mode):
                search_summary["openalex"] = {
                    "count": 0, "pmids": [], "citation_refs": [],
                    "oa_info": {}, "status": "skipped_due_to_rate_limit",
                }
                print("  → 因限流跳过", file=sys.stderr)
            else:
                known_pmids = search_summary.get("pubmed", {}).get("pmids", [])[:5]
                try:
                    oa_result = search_openalex(
                        gene, cdna, protein_short, known_pmids, max_results,
                        gene_aliases
                    )
                    search_summary["openalex"] = oa_result
                    print(f"  → {oa_result['count']} PMIDs"
                          f" ({len(oa_result['citation_refs'])} refs)",
                          file=sys.stderr)
                except Exception as e:
                    print(f"  → 异常: {e}", file=sys.stderr)
                    search_summary["openalex"] = {
                        "count": 0, "pmids": [], "citation_refs": [],
                        "oa_info": {}, "status": f"error: {e}"
                    }

            if time.monotonic() - start_time > 110:
                print("[超时] 接近 120s 限制，终止剩余检索", file=sys.stderr)
                mode = "_timeout"

        # 7. Europe PMC（稳定快速，放在 Semantic Scholar 前，避免被 429 重试超时跳过）
        if mode in ("all", "europepmc"):
            print("[6/8] Europe PMC ...", file=sys.stderr)
            try:
                ep_result = search_europepmc(
                    gene, cdna, protein_short, max_results
                )
                search_summary["europepmc"] = {
                    "count": ep_result["count"],
                    "pmids": ep_result["pmids"],
                    "status": ep_result["status"],
                }
                _collect_papers(ep_result["papers"])
                print(f"  → {ep_result['count']} PMIDs", file=sys.stderr)
            except Exception as e:
                print(f"  → 异常: {e}", file=sys.stderr)
                search_summary["europepmc"] = {
                    "count": 0, "pmids": [], "status": f"error: {e}"
                }

            if time.monotonic() - start_time > 110:
                print("[超时] 接近 120s 限制，终止剩余检索", file=sys.stderr)
                mode = "_timeout"

        # 8. Semantic Scholar（限流严/重试耗时长，放最后；v21: ClinVar 文献充分时跳过）
        if mode in ("all", "semantic_scholar") and not _clinvar_rich:
            print("[7/8] Semantic Scholar ...", file=sys.stderr)
            # v17: 限流保护 — 检查是否应跳过
            if _check_rate_limit_skip("semantic_scholar", mode):
                search_summary["semantic_scholar"] = {
                    "count": 0, "pmids": [], "papers": [],
                    "status": "skipped_due_to_rate_limit",
                }
                print("  → 因限流跳过", file=sys.stderr)
            else:
                try:
                    ss_result = search_semantic_scholar(
                        gene, cdna, protein_full, protein_short, rs, max_results,
                        gene_aliases=gene_aliases
                    )
                    search_summary["semantic_scholar"] = {
                        "count": ss_result["count"],
                        "pmids": ss_result["pmids"],
                        "status": ss_result["status"],
                    }
                    _collect_papers(ss_result["papers"])
                    print(f"  → {ss_result['count']} PMIDs", file=sys.stderr)
                except Exception as e:
                    print(f"  → 异常: {e}", file=sys.stderr)
                    search_summary["semantic_scholar"] = {
                        "count": 0, "pmids": [], "status": f"error: {e}"
                    }

        # 合并去重
        papers_list, dedup_info = merge_results(search_summary, papers_by_pmid)

        # v18: 标记 ClinVar 核心文献 + 注入 LitSense 句子
        clinvar_pmids = set(
            str(p) for p in search_summary.get("clinvar_elink", {}).get("pmids", [])
        )
        hgmd_pmids = set(
            str(p) for p in search_summary.get("hgmd", {}).get("pmids", [])
        )
        litsense_pmid_sentences = search_summary.get("litsense", {}).get("pmid_sentences", {})
        for paper in papers_list:
            pmid = str(paper.get("pmid", ""))
            paper["is_core"] = pmid in clinvar_pmids or pmid in hgmd_pmids
            # 注入 LitSense 命中句子，供后过滤使用
            if pmid in litsense_pmid_sentences:
                paper["litsense_sentences"] = litsense_pmid_sentences[pmid]

        # v18: 批量拉取摘要（对没有摘要的文献）
        pmids_needing_abstract = [
            str(p.get("pmid", "")) for p in papers_list
            if not p.get("abstract") and p.get("pmid")
        ]
        if pmids_needing_abstract:
            print(f"  [摘要获取] 批量拉取 {len(pmids_needing_abstract)} 篇文献摘要...",
                  file=sys.stderr)
            fetched_abstracts = fetch_pubmed_abstracts(pmids_needing_abstract)
            abstract_filled = 0
            for paper in papers_list:
                pmid = str(paper.get("pmid", ""))
                if not paper.get("abstract") and pmid in fetched_abstracts:
                    paper["abstract"] = fetched_abstracts[pmid]
                    abstract_filled += 1
            print(f"  [摘要获取] 成功填充 {abstract_filled}/{len(pmids_needing_abstract)} 篇摘要",
                  file=sys.stderr)
            dedup_info["abstracts_fetched"] = abstract_filled

        # v20: 批量补全缺失的元数据（title/authors/journal/year/doi）
        pmids_needing_meta = [
            str(p.get("pmid", "")) for p in papers_list
            if (not p.get("title")) and p.get("pmid")
        ]
        if pmids_needing_meta:
            print(f"  [元数据补全] 批量拉取 {len(pmids_needing_meta)} 篇文献元数据...",
                  file=sys.stderr)
            fetched_meta = fetch_pubmed_metadata(pmids_needing_meta)
            meta_filled = 0
            for paper in papers_list:
                pmid = str(paper.get("pmid", ""))
                m = fetched_meta.get(pmid)
                if not m:
                    continue
                if not paper.get("title") and m.get("title"):
                    paper["title"] = m["title"]
                if not paper.get("authors") and m.get("authors"):
                    paper["authors"] = m["authors"]
                if not paper.get("journal") and m.get("journal"):
                    paper["journal"] = m["journal"]
                if not paper.get("year") and m.get("year"):
                    paper["year"] = m["year"]
                if not paper.get("doi") and m.get("doi"):
                    paper["doi"] = m["doi"]
                if m.get("title"):
                    meta_filled += 1
            print(f"  [元数据补全] 成功补全 {meta_filled}/{len(pmids_needing_meta)} 篇文献标题",
                  file=sys.stderr)
            dedup_info["metadata_filled"] = meta_filled

        # v17: 标记缩写歧义文献
        if _is_gene_ambiguous(gene):
            ambiguous_pmids = set()
            for source_key in ("pubtator", "litsense", "semantic_scholar"):
                src_info = search_summary.get(source_key, {})
                if isinstance(src_info, dict):
                    amb_list = src_info.get("ambiguous_pmids", [])
                    for pmid in amb_list:
                        ambiguous_pmids.add(str(pmid))
            if ambiguous_pmids:
                for paper in papers_list:
                    if str(paper.get("pmid", "")) in ambiguous_pmids:
                        paper["ambiguous_match"] = True
                dedup_info["ambiguous_papers"] = len(ambiguous_pmids)
                print(f"  [歧义标记] {len(ambiguous_pmids)} 篇文献可能为缩写歧义，"
                      f"已标记 ambiguous_match=True", file=sys.stderr)

        # v16+v17: 分层后过滤（v18: 传入核心PMID集合）
        pre_filter_count = len(papers_list)
        # v18: 构建核心 PMID 集合（ClinVar + HGMD）
        core_pmids = set(
            str(p) for p in search_summary.get("clinvar_elink", {}).get("pmids", [])
        ) | set(
            str(p) for p in search_summary.get("hgmd", {}).get("pmids", [])
        )
        papers_list, filter_info = _post_filter_results(
            papers_list, cdna, protein_full, protein_short, rs, gene, gene_aliases,
            core_pmids=core_pmids
        )
        post_filter_count = len(papers_list)
        
        # 更新去重信息
        dedup_info["after_post_filter"] = post_filter_count
        dedup_info["post_filter_dropped"] = pre_filter_count - post_filter_count
        if filter_info:
            dedup_info["filter_info"] = filter_info

        # v17: LLM 结构化提取（仅对过滤后的文献）
        extraction_count = _extract_structured_fields(papers_list, gene,
                                                      evidence_for=evidence_for)
        if extraction_count > 0:
            dedup_info["structured_extraction_count"] = extraction_count

        # v18: 对核心文献尝试获取全文（优先有PMCID的，最多10篇防超时）
        fulltext_fetched = 0
        core_for_ft = [p for p in papers_list if p.get("is_core") and not p.get("abstract")]
        core_for_ft.sort(key=lambda p: (0 if p.get("pmcid") else 1, -len(p.get("sources", []))))
        for paper in core_for_ft[:10]:
            if time.monotonic() - start_time > 100:
                break
            try:
                ft = fetch_fulltext(str(paper.get("pmid", "")))
                if ft and ft.get("passages"):
                    paper["fulltext_available"] = True
                    paper["fulltext_source"] = ft.get("source", "")
                    # 把全文段落拼入一个字段，供结构化提取使用
                    ft_text = "\n".join(
                        seg.get("text", "") for seg in ft["passages"] if seg.get("text")
                    )
                    if ft_text and not paper.get("abstract"):
                        paper["abstract"] = ft_text[:3000]
                    fulltext_fetched += 1
            except Exception:
                continue
        if fulltext_fetched:
            dedup_info["fulltext_fetched"] = fulltext_fetched
            print(f"  [全文获取] 成功获取 {fulltext_fetched} 篇核心文献全文", file=sys.stderr)
            # 全文填充后重新做一次结构化提取
            extraction_count2 = _extract_structured_fields(papers_list, gene,
                                                           evidence_for=evidence_for)
            if extraction_count2 > extraction_count:
                dedup_info["structured_extraction_count"] = extraction_count2

        # v18: 对核心文献做变异签名校验（在摘要+全文都获取完之后）
        variant_sigs = _build_variant_forms(cdna, protein_full, protein_short, rs)
        indirect_core = 0
        for paper in papers_list:
            if not paper.get("is_core"):
                continue
            title = paper.get("title", "") or ""
            abstract = paper.get("abstract", "") or ""
            litsense_sents = " ".join(paper.get("litsense_sentences", []) or [])
            combined = title + " " + abstract + " " + litsense_sents
            if not combined.strip():
                continue
            variant_in_text = any(
                sig and sig.lower() in combined.lower() for sig in variant_sigs
            )
            if not variant_in_text:
                paper["core_relevance"] = "indirect"
                indirect_core += 1
            else:
                paper["core_relevance"] = "direct"
        if indirect_core:
            dedup_info["indirect_core_count"] = indirect_core
            print(f"  [核心校验] {indirect_core} 篇核心文献未直接提及变异，标记为间接关联",
                  file=sys.stderr)

        # v18: 排序——直接核心优先，其次间接核心，再次非核心有摘要，最后其余
        def _paper_sort_key(p):
            has_fulltext = 1 if p.get("fulltext_available") else 0
            has_abstract = 1 if p.get("abstract") else 0
            has_title = 1 if p.get("title") else 0
            if p.get("is_core"):
                core_rank = 2 if p.get("core_relevance") == "direct" else 1
            else:
                core_rank = 0
            source_count = len(p.get("sources", []))
            return (core_rank, has_fulltext, has_abstract, has_title, source_count)
        papers_list.sort(key=_paper_sort_key, reverse=True)

        elapsed = time.monotonic() - start_time
        print(f"[完成] 共 {dedup_info['total_unique_pmids']} 篇去重文献"
              f"，过滤后 {post_filter_count} 篇"
              f"，耗时 {elapsed:.1f}s", file=sys.stderr)

        output = {
            "gene": gene,
            "variant": cdna or protein_full or protein_short or rs,
            "search_summary": search_summary,
            "dedup": dedup_info,
            "papers": papers_list,
            "elapsed_seconds": round(elapsed, 1),
        }

        print(json.dumps(output, ensure_ascii=False, indent=2))

    except Exception as e:
        elapsed = time.monotonic() - start_time
        error_output = {
            "gene": gene,
            "variant": cdna or protein_full or protein_short or rs,
            "error": str(e),
            "search_summary": search_summary,
            "papers": sorted(
                papers_by_pmid.values(),
                key=lambda x: len(x.get("sources", [])),
                reverse=True,
            ),
            "elapsed_seconds": round(elapsed, 1),
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        raise  # 仍然抛出，但先输出已有结果



def fetch_pubmed_metadata(pmids: list[str]) -> dict[str, dict]:
    """批量获取 PubMed 元数据（title/authors/journal/year/doi），返回 {pmid: meta}。

    用于补全 ClinVar 等只给 PMID 不带元数据的来源。
    """
    if not pmids:
        return {}

    batch_size = 100
    meta: dict[str, dict] = {}

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i:i + batch_size]
        ids_str = ",".join(batch)
        esummary_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&id={ids_str}&retmode=xml"
        )
        _rate_limit("eutils", EUTILS_SLEEP)
        try:
            r = _request_with_retry("GET", esummary_url)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except Exception as e:
            print(f"[PubMed-meta] 失败: {e}", file=sys.stderr)
            continue

        for docsum in root.findall("DocSum"):
            pmid_el = docsum.find("Id")
            if pmid_el is None:
                continue
            pmid = pmid_el.text or ""
            if not pmid:
                continue

            title = ""
            journal = ""
            year = ""
            authors = []
            doi = ""

            for item in docsum.findall("Item"):
                name = item.get("Name", "")
                if name == "Title":
                    title = item.text or ""
                elif name == "Source":
                    journal = item.text or ""
                elif name == "PubDate":
                    pub_date = (item.text or "").strip()
                    year = pub_date.split()[0] if pub_date else ""
                elif name == "DOI":
                    doi = item.text or ""
                elif name == "AuthorList":
                    for au in item:
                        if au.get("Name") == "Author":
                            author_name = (au.text or "").strip()
                            if author_name:
                                authors.append(author_name)
                elif name == "Author":
                    author_name = (item.text or "").strip()
                    if author_name:
                        authors.append(author_name)

            meta[pmid] = {
                "title": title,
                "authors": authors[:5],
                "journal": journal,
                "year": year,
                "doi": doi,
            }

    return meta
if __name__ == "__main__":
    try:
        main()
    except LLMConfigError as e:
        # v1.5.0 LLM 闸门：配置缺失/调用失败 → 非零退出码，明确"需配置 KEY 后重跑"。
        # 供上层（AI 助手 / CI / 平台）识别这不是正常完成，并读取指引引导用户配置。
        print(json.dumps({"error": str(e), "code": "LLM_CONFIG_REQUIRED"},
                         ensure_ascii=False, indent=2))
        sys.exit(2)
    except Exception as e:
        # 兜底：即使 main() 内部出现未捕获异常，也输出结构化 JSON
        print(json.dumps({"error": f"未捕获异常: {e}"}, ensure_ascii=False, indent=2))
        sys.exit(1)


