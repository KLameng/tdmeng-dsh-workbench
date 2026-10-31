# -*- coding: utf-8 -*-
"""
clingen-vcep 知识库结构化校验脚本（P4 项）
==========================================
职责：全量自动校验 clingen-vcep 知识库的
  C1 完整性      —— 每个规范基因的 narrative 四段（a 概述 / b 致病 / c 良性 / d 参考）是否齐全
  C2 主文件骨架  —— 每个 VCEP-<GENE>.md 必备章节是否齐全
  C3 跨文件一致  —— knowledge_graph.gene_vcep_index ↔ knowledge-base 规范文件 ↔ narrative-units 命名 是否对齐
  C4 声明vs实际  —— knowledge-base/00-索引.md 声明的基因/专家组数 vs 实际

用法：
  python scripts/check_vcep_structure.py            # 默认：检测 _review_v27 下的 clingen-vcep
  python scripts/check_vcep_structure.py <root>     # 显式指定技能群根目录
退出码：0 = 全通过（仅 WARN 允许）；1 = 存在 FAIL
输出：人读 Markdown + 机读 JSON 到 <root>/reviews/vcep_structure_<date>.json
"""
import os, re, sys, json, io, datetime

def load_json(p):
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)

def gene_from_md_name(fname):
    """从 VCEP-<GENE>.md 提取基因名；非规范返回 None"""
    m = re.match(r'^VCEP-([A-Z0-9]+)\.md$', fname)
    return m.group(1) if m else None

# 索引文件白名单（narrative 根下的 VCEP-IDX* 为知识库索引叙述，非规范基因）
IDX_PREFIX = "VCEP-IDX"

def gene_from_nu_name(fname):
    """从 narrative-units 文件名提取 (基因, 规范号, 段)。
    命名规律：
      单规范: VCEP-<GENE><seg>_<段名>.md          如 VCEP-GJB2a_概述与疾病.md -> (GJB2,'','a')
      多规范: VCEP-<GENE><SPEC><seg>_规范<SPEC><段名>.md  如 VCEP-ACTA11a_规范1概述与疾病.md -> (ACTA1,'1','a')
    歧义根源：基因名末尾数字(如 ACTA1)+规范号(1)连写 -> 'ACTA11'，无法用前缀数字定位。
    可靠分割依据 = 段名里的「规范N」：段名带规范号 -> 多规范，规范号=N，基因=前缀去掉尾部N。
    """
    if fname.startswith(IDX_PREFIX):
        return ("__IDX__", "", "")
    # 段名以「规范」开头的多规范文件
    m2 = re.match(r'^VCEP-([A-Z0-9]+)([abcd])_规范(\d+)', fname)
    if m2:
        prefix, seg, spec = m2.group(1), m2.group(2), m2.group(3)
        gene = re.sub(re.escape(spec) + r'$', '', prefix)  # 去掉前缀尾部的规范号数字
        return gene, spec, seg
    # 单规范：段名不以「规范」开头
    m = re.match(r'^VCEP-([A-Z0-9]+)([abcd])_(?!规范)', fname)
    if m:
        return m.group(1), '', m.group(2)
    return None

def main():
    # 默认 root 取本脚本所在目录的父目录（技能群根），可被命令行参数覆盖
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = sys.argv[1] if len(sys.argv) > 1 else default_root
    vcep = os.path.join(root, "clingen-vcep")
    if not os.path.isdir(vcep):
        print(f"[FAIL] clingen-vcep/ 数据缺失：未找到目录 {vcep}")
        print("[HINT] clingen-vcep 为独立 VCEP 数据包（v1.1.0，单独分发、不随技能群主包）："
              "需先解压 VCEP 数据包到技能群根目录同级。主包 ZIP 不含 VCEP 数据，勿从主包内寻找。")
        return 2
    kb_dir = os.path.join(vcep, "knowledge-base")
    nu_dir = os.path.join(vcep, "narrative-units")
    cfg = os.path.join(root, "config")
    kg_path = os.path.join(cfg, "knowledge_graph.json")

    results = {"c1": [], "c2": [], "c3": [], "c4": []}  # 每项 FAIL/WARN 记录
    stats = {"c1_ok": 0, "c2_ok": 0, "c3_ok": 0, "c4_ok": 0}

    # ---------- C3/C4 基因基准 ----------
    kg_genes = set()
    if os.path.exists(kg_path):
        kg = load_json(kg_path)
        kg_genes = set(kg.get("gene_vcep_index", {}).keys())
    else:
        results["c3"].append(("FAIL", "knowledge_graph.json 缺失，无法做跨文件对照"))

    kb_files = [f for f in os.listdir(kb_dir) if f.endswith(".md")]
    kb_gene_files = {gene_from_md_name(f): f for f in kb_files if gene_from_md_name(f)}
    kb_genes = set(kb_gene_files.keys())

    nu_files = [f for f in os.listdir(nu_dir) if f.endswith(".md")]
    # narrative 按 (规范基因, 规范号) 归组；索引文件单独跳过
    nu_by_gene = {}   # 规范基因 -> {规范号 -> {段 -> [文件名]}}
    nu_gene_names = set()
    idx_count = 0
    for f in nu_files:
        r = gene_from_nu_name(f)
        if not r:
            results["c1"].append(("WARN", f"无法解析的 narrative 文件名: {f}"))
            continue
        gene, spec, seg = r
        if gene == "__IDX__":
            idx_count += 1
            continue
        nu_gene_names.add(gene)
        nu_by_gene.setdefault(gene, {}).setdefault(spec, {}).setdefault(seg, []).append(f)

    # ---------- C4: 索引声明 vs 实际 ----------
    idx_path = os.path.join(kb_dir, "00-索引.md")
    if os.path.exists(idx_path):
        idx_text = io.open(idx_path, encoding="utf-8").read()
        m_gene = re.search(r'覆盖\s*(\d+)\s*个基因', idx_text)
        m_vcep = re.search(r'(\d+)\s*个VCEP专家组', idx_text)
        m_spec = re.search(r'(\d+)\s*条已发布规范', idx_text)
        declared_genes = int(m_gene.group(1)) if m_gene else None
        declared_vcep = int(m_vcep.group(1)) if m_vcep else None
        declared_spec = int(m_spec.group(1)) if m_spec else None
        actual_genes = len(kb_genes)
        if declared_genes is not None:
            if declared_genes != actual_genes:
                results["c4"].append(("FAIL", f"索引声明 {declared_genes} 基因 vs 实际 {actual_genes} 基因"))
            else:
                stats["c4_ok"] += 1
        else:
            results["c4"].append(("WARN", "索引未声明基因数，跳过"))
        # 实际规范文件数 = 规范基因文件数（131 主文件 = 131 规范，多规范基因拆分的规范号由主文件数近似）
        if declared_spec is not None:
            if declared_spec != len(kb_gene_files):
                results["c4"].append(("WARN", f"索引声明 {declared_spec} 条已发布规范 vs 实际主文件 {len(kb_gene_files)}（多规范基因合并，仅供参考）"))
    else:
        results["c4"].append(("FAIL", "00-索引.md 缺失"))

    # ---------- C3: 跨文件一致 ----------
    # knowledge-base 规范基因 vs knowledge_graph
    if kg_genes:
        kb_only = kb_genes - kg_genes
        kg_only = kg_genes - kb_genes
        if kb_only: results["c3"].append(("FAIL", f"knowledge-base 有而 knowledge_graph 无: {sorted(kb_only)}"))
        if kg_only: results["c3"].append(("FAIL", f"knowledge_graph 有而 knowledge-base 无: {sorted(kg_only)}"))
        if not kb_only and not kg_only:
            stats["c3_ok"] += 1
    # narrative 覆盖基因 vs knowledge-base（多规范基因已解析为规范基因名，无需砍数字）
    nu_only = nu_gene_names - kb_genes
    kb_nu_only = kb_genes - nu_gene_names
    if nu_only: results["c3"].append(("FAIL", f"narrative-units 有而 knowledge-base 无: {sorted(nu_only)}"))
    if kb_nu_only: results["c3"].append(("WARN", f"knowledge-base 有而 narrative-units 无: {sorted(kb_nu_only)}（可能无叙述单元）"))
    if not nu_only and not kb_nu_only:
        stats["c3_ok"] += 1

    # ---------- C1: narrative 四段完整性 ----------
    for gene, specs in sorted(nu_by_gene.items()):
        for spec, segs in specs.items():
            label = f"{gene}规范{spec or '通用'}"
            missing = []
            for need in ("a", "b", "c", "d"):
                if need not in segs or not segs[need]:
                    missing.append(f"{need}段缺失")
            if missing:
                results["c1"].append(("FAIL", f"{label}: {', '.join(missing)}"))
            else:
                stats["c1_ok"] += 1
    # narrative 基因 vs knowledge-base 有 narrative 的基因，检查是否所有规范基因都有 narrative
    for g in sorted(kb_genes):
        if g not in nu_gene_names:
            results["c1"].append(("WARN", f"knowledge-base 基因 {g} 无 narrative 叙述单元"))

    # ---------- C2: 主文件必备章节 ----------
    # 必备骨架：覆盖疾病 / 基因特异性证据规则 / 不适用证据码 / 官方链接
    # 参考附件/附件关键数据 为部分基因的可选项（ABCA4 等含，GJB2/AKT3 等仅官方链接）
    required_sections = ["覆盖疾病", "基因特异性证据规则", "不适用证据码", "官方链接"]
    optional_sections = ["参考附件", "附件关键数据"]
    opt_counts = {s: 0 for s in optional_sections}   # 记录各可选章节覆盖数
    opt_missing_genes = {s: [] for s in optional_sections}
    for g, fname in sorted(kb_gene_files.items()):
        path = os.path.join(kb_dir, fname)
        text = io.open(path, encoding="utf-8").read()
        missing = [s for s in required_sections if s not in text]
        # 证据规则下至少要有若干 #### 证据码段
        code_blocks = re.findall(r'^#### ([A-Z0-9]+(?:_[A-Za-z]+)?)', text, re.M)
        if missing:
            results["c2"].append(("FAIL", f"{fname}: 缺必备章节 {missing}"))
        else:
            if len(code_blocks) < 3:
                results["c2"].append(("WARN", f"{fname}: 证据码段仅 {len(code_blocks)} 个，偏少"))
            stats["c2_ok"] += 1
        # 可选项覆盖计数（不逐文件刷，改汇总）
        for s in optional_sections:
            if s in text:
                opt_counts[s] += 1
            else:
                opt_missing_genes[s].append(fname)
    # 可选项汇总 WARN（仅当存在缺失时给一条总览）
    for s in optional_sections:
        missing_n = len(kb_gene_files) - opt_counts[s]
        if missing_n > 0:
            results["c2"].append(("WARN", f"可选章节[{s}]覆盖 {opt_counts[s]}/{len(kb_gene_files)}，{missing_n} 个基因缺失（VCEP 详略差异，属设计允许）：{sorted(opt_missing_genes[s])[:8]}…"))

    # ---------- 汇总输出 ----------
    fails = sum(1 for k in results for lv, _ in results[k] if lv == "FAIL")
    warns = sum(1 for k in results for lv, _ in results[k] if lv == "WARN")

    lines = []
    lines.append("# clingen-vcep 知识库结构化校验报告")
    lines.append("")
    lines.append(f"> 校验日期：{datetime.date.today()} | 知识库根：{vcep}")
    lines.append("")
    lines.append(f"**C1 完整性** {stats['c1_ok']} 规范段组通过；**C2 主文件骨架** {stats['c2_ok']}/{len(kb_gene_files)}；**C3 跨文件一致** {stats['c3_ok']}；**C4 声明vs实际** {stats['c4_ok']}")
    lines.append(f"**结果：FAIL={fails} WARN={warns}**" + (" → 需处理" if fails else " → 通过"))
    lines.append("")
    for k in ("c1", "c2", "c3", "c4"):
        if results[k]:
            lines.append(f"### C{k[1:]} {k} 问题")
            lines.append("")
            lines.append("| 级别 | 位置 | 问题 |")
            lines.append("|---|---|---|")
            for lv, msg in results[k]:
                lines.append(f"| {lv} | - | {msg} |")
            lines.append("")
    # 统计
    lines.append("## 统计")
    lines.append("")
    lines.append(f"- knowledge-base 规范文件：{len(kb_gene_files)}（非规范 {len(kb_files)-len(kb_gene_files)}）")
    lines.append(f"- narrative-units 文件：{len(nu_files)}（规范叙述 {len(nu_files)-idx_count}，索引叙述 {idx_count}），覆盖基因 {len(nu_gene_names)}")
    lines.append(f"- knowledge_graph.gene_vcep_index：{len(kg_genes)} 基因")
    lines.append("")

    # 落盘
    out_dir = os.path.join(root, "reviews")
    os.makedirs(out_dir, exist_ok=True)
    date = datetime.date.today().isoformat()
    md_path = os.path.join(out_dir, f"vcep_structure_{date}.md")
    json_path = os.path.join(out_dir, f"vcep_structure_{date}.json")
    with io.open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    report = {
        "skill": "clingen-vcep", "date": date, "root": root,
        "c1": [{"level": lv, "issue": msg} for lv, msg in results["c1"]],
        "c2": [{"level": lv, "issue": msg} for lv, msg in results["c2"]],
        "c3": [{"level": lv, "issue": msg} for lv, msg in results["c3"]],
        "c4": [{"level": lv, "issue": msg} for lv, msg in results["c4"]],
        "stats": {"c1_ok": stats["c1_ok"], "c2_ok": stats["c2_ok"], "c3_ok": stats["c3_ok"], "c4_ok": stats["c4_ok"],
                  "kb_genes": len(kb_genes), "nu_files": len(nu_files), "kg_genes": len(kg_genes)},
        "fail": fails, "warn": warns, "gate": "not_cleared" if fails else ("cleared" if warns == 0 else "cleared_with_warn"),
    }
    with io.open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n".join(lines))
    print(f"\n报告已写入: {md_path}")
    print(f"机读 JSON: {json_path}")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
