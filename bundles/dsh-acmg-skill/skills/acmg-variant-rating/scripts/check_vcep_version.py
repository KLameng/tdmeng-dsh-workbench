# -*- coding: utf-8 -*-
"""
check_vcep_version.py — clingen-vcep 知识库 CSpec 升版监控（M-3 落地）

检测技能群内置 VCEP 知识库（131 基因）所引用的 ClinGen CSpec 是否已出新版本，
输出「需重审 / 无更新 / 不可达 / legacy被取代」清单，供升版触发 VCEP 重审。

数据源：ClinGen CSpec Registry API（实测可用）
    GET https://cspec.genome.network/cspec/api/SequenceVariantInterpretation/id/GN<nn>
    返回 JSON：label(含版本) / lastUpdated / cspecStatus / currentStatus / legacy / legacyReplaced

用法：
    python check_vcep_version.py                     # 全量监控（读 gene-gn-file-mapping.csv，刷全部 GN）
    python check_vcep_version.py --genes GJB2,ABCA4  # 只查指定基因
    python check_vcep_version.py --refresh-baseline  # 把当前官方版本写入 manifest 作为新基线
    python check_vcep_version.py --out-dir <dir>     # 报告输出目录

退出码：0=无更新 / 1=有需重审或不可达（可挂 CI 阻断）
"""
import argparse
import csv
import json
import os
import re
import sys
import time

import requests

API = "https://cspec.genome.network/cspec/api/SequenceVariantInterpretation/id/GN{gn}"
UA = "acmg-vcep-version-monitor/1.0 (contact: variant-rating-skill@example.com)"
RATE_SLEEP = 1.0   # 对 ClinGen CSpec API 的礼貌限速（秒/请求）
TIMEOUT = 20
RETRY = 2

# 报告字段（与既有 reviews/ 命名一致，日期戳）
REPORT_NAME = "vcep_version_check_{date}.md"


def fetch_gn(gn):
    """拉取单个 GN 的 CSpec 元信息；失败重试；返回 dict 或 None。"""
    url = API.format(gn=gn)
    last = None
    for attempt in range(RETRY + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = str(e)[:120]
        if attempt < RETRY:
            time.sleep(RATE_SLEEP * (attempt + 1))
    return {"_error": last, "_gn": gn}


def parse_version(label):
    """从 label 提取 'Version X.Y.Z'；失败返回 None。"""
    if not label:
        return None
    m = re.search(r"[Vv]ersion\s+([\d]+\.[\d]+(?:\.[\d]+)?)", label)
    return m.group(1) if m else None


def load_mapping(mapping_csv):
    """读 gene-gn-file-mapping.csv -> [(gene, [gn,...]), ...]；容忍多规范 '169 / 147'。"""
    rows = []
    with open(mapping_csv, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            gene = (row.get("基因") or "").strip()
            gn = (row.get("GN编号") or "").strip()
            if not gene:
                continue
            gns = [g.strip() for g in re.split(r"[/,]", gn) if g.strip()]
            rows.append((gene, gns))
    return rows


def load_manifest(path):
    """读基线 manifest：{gene: {"version","lastUpdated","cspecStatus","legacyReplaced","checked"}}。"""
    if not path or not os.path.exists(path):
        return {}
    base = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            base[row["基因"]] = {
                "version": row.get("官方CSpec版本", ""),
                "lastUpdated": row.get("lastUpdated", ""),
                "cspecStatus": row.get("cspecStatus", ""),
                "legacyReplaced": row.get("legacyReplaced", ""),
                "checked": row.get("最后检测日期", ""),
            }
    return base


def check(mapping, manifest, refresh_baseline, genes_filter=None):
    """逐基因检测，返回 (rows, needs_review, unreachable, updated)。"""
    rows, needs, unreach, updated = [], [], [], []
    for gene, gns in mapping:
        if genes_filter and gene not in genes_filter:
            continue
        metas = [fetch_gn(g) for g in gns]
        ok = [m for m in metas if m and "_error" not in m]
        err = [m for m in metas if m and "_error" in m]
        # 取非 legacy 的最高版本作为"当前规范"（legacy 优先给 needs_review 提示）
        versions = []
        for m in ok:
            v = parse_version(m.get("label"))
            leg_replaced = bool(m.get("legacyReplaced")) or bool(m.get("legacy"))
            versions.append((v, m.get("lastUpdated"), m.get("cspecStatus"),
                             m.get("currentStatus"), leg_replaced, m.get("label"), m.get("_gn")))
        versions.sort(key=lambda x: (x[4], x[0] or "0"), reverse=True)  # 非 legacy 优先、版本高者优先
        # 汇总该基因的"当前"信息
        cur = versions[0] if versions else None
        rec = manifest.get(gene, {})
        status = "fresh"
        reasons = []
        if err:
            status = "unreachable"
            reasons.append("CSpec API 不可达: " + err[0]["_error"])
            unreach.append(gene)
        elif not cur:
            status = "no_spec"
            reasons.append("CSpec 无版本信息（可能 GN 无效或无规范）")
        else:
            cur_v, cur_dt, cstat, curstat, leg_rep, label, gnid = cur
            base_v = rec.get("version")
            if leg_rep:
                status = "legacy_replaced"
                reasons.append(f"官方 CSpec 已标记 legacy/被取代（{label}）——须确认当前生效规范")
                needs.append(gene)
            elif base_v and cur_v and _ver_gt(cur_v, base_v):
                status = "update_available"
                reasons.append(f"官方版本 {cur_v} > 基线 {base_v}")
                needs.append(gene)
                updated.append(gene)
            elif not base_v:
                # 无基线（首次或基因不在 manifest）——refresh 后算 fresh，否则提示待建基线
                status = "baseline_missing"
                reasons.append("manifest 无该基因基线（首次检测，refresh-baseline 后记录）")
        rows.append({
            "gene": gene, "gn": "/".join(gns), "version": (cur[0] if cur else ""),
            "lastUpdated": (cur[1] if cur else ""), "cspecStatus": (cur[2] if cur else ""),
            "currentStatus": (cur[3] if cur else ""), "legacyReplaced": (cur[4] if cur else ""),
            "status": status, "reasons": "; ".join(reasons),
        })
        time.sleep(RATE_SLEEP)
    return rows, needs, unreach, updated


def _ver_gt(a, b):
    """版本串 a > b（支持 2.0 / 2.0.0 / 1.1）。"""
    pa = [int(x) for x in re.findall(r"\d+", a)]
    pb = [int(x) for x in re.findall(r"\d+", b)]
    for x, y in zip(pa, pb):
        if x != y:
            return x > y
    return len(pa) > len(pb)


def write_manifest(path, rows):
    """把本次检测到的官方版本写入 manifest（作为新基线；仅覆盖能取到版本的行）。"""
    fieldnames = ["基因", "GN编号", "官方CSpec版本", "lastUpdated", "cspecStatus",
                  "legacyReplaced", "最后检测日期"]
    now = time.strftime("%Y-%m-%d")
    # 合并既有 + 本次
    merged = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                merged[row["基因"]] = row
    for r in rows:
        if r["status"] in ("fresh", "update_available", "legacy_replaced", "baseline_missing") and r["version"]:
            merged[r["gene"]] = {
                "基因": r["gene"], "GN编号": r["gn"], "官方CSpec版本": r["version"],
                "lastUpdated": r["lastUpdated"], "cspecStatus": r["cspecStatus"],
                "legacyReplaced": str(r["legacyReplaced"]), "最后检测日期": now,
            }
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for g in sorted(merged):
            w.writerow({k: merged[g].get(k, "") for k in fieldnames})
    return len(merged)


def write_report(out_dir, date, rows, needs, unreach, updated, total):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, REPORT_NAME.format(date=date))
    lines = [
        f"# clingen-vcep CSpec 升版监控报告",
        f"> 检测日期：{date} | 检测基因：{total} | 需重审：{len(needs)} | 不可达：{len(unreach)} | 发现升级：{len(updated)}",
        f"> 数据源：ClinGen CSpec Registry API（cspec.genome.network）",
        "",
        "## 需重审清单",
    ]
    if needs:
        for g in sorted(set(needs)):
            r = next((x for x in rows if x["gene"] == g), None)
            lines.append(f"- **{g}**（{r['gn']}）：{r['reasons']}（官方版本 {r['version'] or '?'}）")
    else:
        lines.append("- （无）")
    lines += ["", "## 不可达 / 异常", ]
    if unreach:
        for g in sorted(set(unreach)):
            lines.append(f"- {g}：CSpec API 不可达")
    else:
        lines.append("- （无）")
    lines += ["", "## 逐基因明细", "", "| 基因 | GN | 官方版本 | lastUpdated | cspecStatus | legacy被取代 | 状态 | 说明 |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['gene']} | {r['gn']} | {r['version'] or '-'} | {r['lastUpdated'] or '-'} | "
                     f"{r['cspecStatus'] or '-'} | {r['legacyReplaced'] or '-'} | {r['status']} | {r['reasons']} |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    # 机读 JSON
    with open(path.replace(".md", ".json"), "w", encoding="utf-8") as f:
        json.dump({"date": date, "total": total, "needs_review": sorted(set(needs)),
                   "unreachable": sorted(set(unreach)), "updated": sorted(set(updated)),
                   "rows": rows}, f, ensure_ascii=False, indent=2)
    return path


def main():
    ap = argparse.ArgumentParser(description="clingen-vcep CSpec 升版监控")
    ap.add_argument("--mapping", default="clingen-vcep/gene-gn-file-mapping.csv")
    ap.add_argument("--manifest", default="clingen-vcep/vcep-version-manifest.csv")
    ap.add_argument("--out-dir", default="reviews")
    ap.add_argument("--genes", default=None, help="逗号分隔的基因名子集，如 GJB2,ABCA4")
    ap.add_argument("--refresh-baseline", action="store_true", help="把本次官方版本写入 manifest 作为新基线")
    args = ap.parse_args()

    if not os.path.exists(args.mapping):
        print(f"[FATAL] mapping 不存在: {args.mapping}", file=sys.stderr)
        print("[HINT] clingen-vcep 为独立 VCEP 数据包（v1.1.0，单独分发、不随技能群主包）："
              "需先解压 VCEP 数据包到技能群根目录同级，使 clingen-vcep/ 出现。"
              "主包 ZIP 不含 VCEP 数据，勿从主包内寻找。", file=sys.stderr)
        return 2
    mapping = load_mapping(args.mapping)
    manifest = load_manifest(args.manifest)
    genes_filter = set(args.genes.split(",")) if args.genes else None
    if genes_filter:
        mapping = [m for m in mapping if m[0] in genes_filter]

    print(f"检测基因数: {len(mapping)}（过滤: {args.genes or '无'}）")
    rows, needs, unreach, updated = check(mapping, manifest, args.refresh_baseline, genes_filter)

    date = time.strftime("%Y-%m-%d")
    if args.refresh_baseline:
        n = write_manifest(args.manifest, rows)
        print(f"[baseline] 已更新 manifest: {n} 条 → {args.manifest}")

    path = write_report(args.out_dir, date, rows, needs, unreach, updated, len(mapping))
    print(f"报告: {path}")
    print(f"需重审 {len(needs)} 条 | 不可达 {len(unreach)} | 发现升级 {len(updated)}")
    for g in sorted(set(needs)):
        print(f"  - {g}")
    # 退出码：有需重审或不可达 → 1（可挂 CI 阻断）
    return 1 if (needs or unreach) else 0


if __name__ == "__main__":
    sys.exit(main())
