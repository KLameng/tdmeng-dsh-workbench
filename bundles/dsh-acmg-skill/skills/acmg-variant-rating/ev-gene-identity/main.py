#!/usr/bin/env python3
"""
基因身份核实工具_jb
功能1: 判断两个/多个基因是否为同一个基因（基于NCBI Gene ID + 别名）
功能2: 查询某基因的假基因列表

用法：
  python main.py same <基因A> <基因B> [基因C ...]
  python main.py pseudo <基因名>
"""

import sys
import time
from coze_workload_identity import requests

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def gene_search(gene_name: str) -> dict:
    """搜索NCBI Gene，返回Gene ID和基本信息"""
    # esearch
    url = f"{EUTILS_BASE}/esearch.fcgi"
    params = {
        "db": "gene",
        "term": f"{gene_name}[Gene Name] AND Homo sapiens[Organism]",
        "retmode": "json",
        "retmax": 1
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        idlist = data.get("esearchresult", {}).get("idlist", [])
        if not idlist:
            return {"found": False, "query": gene_name}
        uid = idlist[0]
    except Exception as e:
        return {"found": False, "query": gene_name, "error": str(e)}

    # esummary
    time.sleep(0.35)
    url2 = f"{EUTILS_BASE}/esummary.fcgi"
    params2 = {
        "db": "gene",
        "id": uid,
        "retmode": "json"
    }
    try:
        r2 = requests.get(url2, params=params2, timeout=30)
        r2.raise_for_status()
        data2 = r2.json()
        result = data2.get("result", {})
        entry = result.get(uid, {})

        name = entry.get("name", "")
        otheraliases = entry.get("otheraliases", "")
        aliases_list = [a.strip() for a in otheraliases.split(",") if a.strip()] if otheraliases else []
        description = entry.get("description", "")
        maplocation = entry.get("maplocation", "")
        chromosome = entry.get("chromosome", "")

        return {
            "found": True,
            "query": gene_name,
            "uid": uid,
            "name": name,
            "aliases": aliases_list,
            "description": description,
            "chromosome": chromosome,
            "maplocation": maplocation
        }
    except Exception as e:
        return {"found": False, "query": gene_name, "uid": uid, "error": str(e)}


def cmd_same(gene_names: list):
    """判断多个基因是否为同一基因"""
    print(f"{'='*60}")
    print(f"基因身份比对：{', '.join(gene_names)}")
    print(f"数据源：NCBI Gene (实时)")
    print(f"{'='*60}\n")

    # 查询每个基因
    genes = []
    for name in gene_names:
        print(f"正在查询 {name} ...")
        info = gene_search(name)
        genes.append(info)
        if info["found"]:
            print(f"  Gene ID: {info['uid']}")
            print(f"  官方符号: {info['name']}")
            print(f"  别名: {', '.join(info['aliases']) if info['aliases'] else '无'}")
        else:
            print(f"  ❌ 未找到")
        print()
        time.sleep(0.35)

    # 检查是否有未找到的
    not_found = [g["query"] for g in genes if not g["found"]]
    if not_found:
        print(f"⚠️ 以下基因在NCBI Gene中未找到：{', '.join(not_found)}")
        print(f"无法完成完整比对。\n")
        print(f"智能分析结果，仅供参考")
        return

    # 两两比对
    print(f"{'='*60}")
    print(f"## 比对结果\n")

    all_same = True
    base = genes[0]

    for i in range(1, len(genes)):
        other = genes[i]
        same = False
        reason = ""

        # 规则1: Gene ID相同
        if base["uid"] == other["uid"]:
            same = True
            reason = f"Gene ID相同（{base['uid']}）"
        # 规则2: base的官方名在other的别名中
        elif base["name"].upper() in [a.upper() for a in other["aliases"]]:
            same = True
            reason = f"'{base['name']}'是'{other['name']}'的别名"
        # 规则3: other的官方名在base的别名中
        elif other["name"].upper() in [a.upper() for a in base["aliases"]]:
            same = True
            reason = f"'{other['name']}'是'{base['name']}'的别名"

        if same:
            print(f"  ✅ {base['query']} 与 {other['query']} 是同一基因")
            print(f"     理由：{reason}\n")
        else:
            print(f"  ❌ {base['query']} 与 {other['query']} 是不同基因")
            print(f"     {base['query']} → {base['name']} (Gene ID: {base['uid']})")
            print(f"     {other['query']} → {other['name']} (Gene ID: {other['uid']})\n")
            all_same = False

    print(f"{'='*60}")
    if all_same:
        print(f"## 结论\n")
        official_name = base["name"]
        print(f"✅ 所有输入名称均指向同一个基因：{official_name}（Gene ID: {base['uid']}）")
    else:
        print(f"## 结论\n")
        print(f"❌ 输入的基因名称指向不同基因，详见上方比对结果")

    print(f"\n{'='*60}")
    print(f"智能分析结果，仅供参考")


def cmd_pseudo(gene_name: str):
    """查询某基因的假基因"""
    print(f"{'='*60}")
    print(f"假基因查询：{gene_name}")
    print(f"数据源：NCBI Gene (实时)")
    print(f"{'='*60}\n")

    # esearch: 基因名+P*
    url = f"{EUTILS_BASE}/esearch.fcgi"
    params = {
        "db": "gene",
        "term": f"{gene_name}P*[Gene Name] AND Homo sapiens[Organism]",
        "retmode": "json",
        "retmax": 50
    }

    print(f"正在搜索 {gene_name}P* ...")
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        idlist = data.get("esearchresult", {}).get("idlist", [])
        total = data.get("esearchresult", {}).get("count", "0")
    except Exception as e:
        print(f"[错误] 搜索失败：{e}")
        return

    if not idlist:
        print(f"\n未找到 {gene_name}P* 相关记录。")
        print(f"\n⚠️ NCBI Gene库中无{gene_name}的假基因记录，不代表该基因确实无假基因。")
        print(f"\n{'='*60}")
        print(f"智能分析结果，仅供参考")
        return

    print(f"找到 {total} 条候选记录，正在获取详情...\n")

    # esummary批量获取
    time.sleep(0.35)
    url2 = f"{EUTILS_BASE}/esummary.fcgi"
    params2 = {
        "db": "gene",
        "id": ",".join(idlist),
        "retmode": "json"
    }

    try:
        r2 = requests.get(url2, params=params2, timeout=30)
        r2.raise_for_status()
        data2 = r2.json()
        result = data2.get("result", {})
    except Exception as e:
        print(f"[错误] 获取详情失败：{e}")
        return

    # 筛选pseudogene
    pseudogenes = []
    for uid in idlist:
        entry = result.get(uid, {})
        if not entry:
            continue
        desc = entry.get("description", "").lower()
        if "pseudogene" in desc:
            pseudogenes.append({
                "name": entry.get("name", ""),
                "uid": uid,
                "chromosome": entry.get("chromosome", ""),
                "maplocation": entry.get("maplocation", ""),
                "description": entry.get("description", "")
            })

    # 输出
    print(f"{'='*60}")
    print(f"## {gene_name} 的假基因列表\n")

    if not pseudogenes:
        print(f"  在 {total} 条候选记录中未找到标记为 pseudogene 的记录。")
        print(f"\n⚠️ NCBI Gene库中无{gene_name}的假基因记录，不代表该基因确实无假基因。")
    else:
        for i, pg in enumerate(pseudogenes, 1):
            chr_info = f"chr{pg['chromosome']}" if pg['chromosome'] else "位置未知"
            loc_info = f" ({pg['maplocation']})" if pg['maplocation'] else ""
            print(f"  {i}. {pg['name']}  [Gene ID: {pg['uid']}]")
            print(f"     {chr_info}{loc_info}")
            print(f"     {pg['description']}")
            print()

        print(f"共找到 {len(pseudogenes)} 个假基因。")

    print(f"\n{'='*60}")
    print(f"智能分析结果，仅供参考")


def main():
    if len(sys.argv) < 2:
        print("用法：")
        print("  python main.py same <基因A> <基因B> [基因C ...]  判断基因是否同一")
        print("  python main.py pseudo <基因名>                    查询假基因")
        sys.exit(1)

    command = sys.argv[1].strip().lower()

    if command == "same":
        if len(sys.argv) < 4:
            print("错误：same 命令需要至少2个基因名")
            print("用法：python main.py same <基因A> <基因B> [基因C ...]")
            sys.exit(1)
        cmd_same(sys.argv[2:])
    elif command == "pseudo":
        if len(sys.argv) < 3:
            print("错误：pseudo 命令需要1个基因名")
            print("用法：python main.py pseudo <基因名>")
            sys.exit(1)
        cmd_pseudo(sys.argv[2].strip())
    else:
        print(f"未知命令：{command}")
        print("可用命令：same, pseudo")
        sys.exit(1)


if __name__ == "__main__":
    main()
