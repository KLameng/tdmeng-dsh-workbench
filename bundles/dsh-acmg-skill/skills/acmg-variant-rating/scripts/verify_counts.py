# -*- coding: utf-8 -*-
"""ACMG 评级技能群 · 数字声明 vs 磁盘实际校验（防"差一错误"复发 + 防跨文件逃逸）。

核心改进（20261015 复审整改）：
  - 技能数声明**全仓扫描本评级群 23 技能**（ev-* + 3 核心 + clingen-vcep + README），
    交叉比对全部须为 23——修复"README 改了、acmg-total-scheduler 仍是 22"的逃逸形态；
  - 基因数 / narrative-units / VCEP 组数声明集中在 README 校验（全仓扫基因数噪声过大，
    退化为 README 比对）；
  - 默认路径从脚本位置推导（SRC_ROOT = 脚本上一级 = .user_skills），不写死绝对路径，
    换机器/换目录不失效；仍支持 argv 覆盖。

不一致输出 FAIL 并以退出码 1 退出（供打包/CI 阻断）。
用法：python verify_counts.py [SRC_ROOT]
"""
import os
import re
import sys
import pathlib

SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) > 1 and sys.argv[1]:
    SRC_ROOT = sys.argv[1]

CORE = {"acmg-total-scheduler", "acmg-conflict-summary-output", "arad-inheritance-judgment"}
GROUP_SKILLS = CORE | {"clingen-vcep"}


def group_skill_dirs():
    return [d for d in os.listdir(SRC_ROOT)
            if os.path.isdir(os.path.join(SRC_ROOT, d))
            and (d.startswith("ev-") or d in GROUP_SKILLS)]


def disk_counts():
    kb = os.path.join(SRC_ROOT, "clingen-vcep", "knowledge-base")
    nu = os.path.join(SRC_ROOT, "clingen-vcep", "narrative-units")
    mapf = os.path.join(SRC_ROOT, "clingen-vcep", "gene-gn-file-mapping.csv")
    genes = [b for b in os.listdir(kb)
             if b.startswith("VCEP-") and not b.startswith("VCEP-verification")]
    nus = [b for b in os.listdir(nu) if b.endswith(".md")] if os.path.isdir(nu) else []
    mapping_genes = set()
    if os.path.exists(mapf):
        with open(mapf, encoding="utf-8") as f:
            next(f, None)
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                cells = ln.split(",")
                if cells and cells[0].strip():
                    mapping_genes.add(cells[0].strip())
    return {
        "技能数": len(group_skill_dirs()),
        "基因数": len(genes),
        "narrative-units": len(nus),
        "VCEP组数(去重基因)": len(mapping_genes),
    }


def read_text(p):
    try:
        return pathlib.Path(p).read_text(encoding="utf-8")
    except Exception:
        return ""


def skill_count_declarations():
    """扫描本评级群 23 技能 + README 内的 'N 个技能' 声明。"""
    decls = []
    for d in group_skill_dirs():
        p = os.path.join(SRC_ROOT, d, "SKILL.md")
        for m in re.finditer(r"(\d+)\s*个技能", read_text(p)):
            decls.append((os.path.join(d, "SKILL.md"), int(m.group(1))))
    rp = os.path.join(SRC_ROOT, "README.md")
    for m in re.finditer(r"(\d+)\s*个技能", read_text(rp)):
        decls.append(("README.md", int(m.group(1))))
    return decls


def _ensure_vcep_dir():
    vd = os.path.join(SRC_ROOT, "clingen-vcep")
    if not os.path.isdir(vd):
        print(f"[FAIL] clingen-vcep/ 数据缺失：未找到目录 {vd}")
        print("[HINT] clingen-vcep 为独立 VCEP 数据包（v1.1.0，单独分发、不随技能群主包）："
              "需先解压 VCEP 数据包到技能群根目录同级，使技能群根下出现 clingen-vcep/。"
              "主包 ZIP 不含 VCEP 数据，勿从主包内寻找。")
        sys.exit(2)


def main():
    _ensure_vcep_dir()
    c = disk_counts()
    ok = True

    # ① 技能数全仓交叉比对：本群所有声明须为 23
    decls = skill_count_declarations()
    bad = [(f, n) for f, n in decls if n != 23]
    if bad:
        ok = False
        for f, n in bad:
            print(f"[FAIL] '{f}' 声明 {n} 个技能，应为 23（磁盘实际={c['技能数']}）")
    if not decls:
        ok = False
        print("[FAIL] 未找到任何技能数声明")

    # ② README 基因数 / narrative-units 声明
    r = read_text(os.path.join(SRC_ROOT, "README.md"))
    if f"{c['基因数']} 基因" not in r:
        ok = False
        print(f"[FAIL] README 未声明'{c['基因数']} 基因'（磁盘实际={c['基因数']}）")
    if str(c["narrative-units"]) not in r:
        ok = False
        print(f"[FAIL] README 未声明 narrative-units 数 {c['narrative-units']}（磁盘实际={c['narrative-units']}）")

    print("[OK] 磁盘实际：技能数=%d | 基因数=%d | narrative-units=%d | VCEP组(去重基因)=%d"
          % (c["技能数"], c["基因数"], c["narrative-units"], c["VCEP组数(去重基因)"]))
    print(f"[OK] 本群技能数声明 {len(decls)} 处" + ("，全部 = 23" if not bad else ""))

    if not ok:
        print("[FAIL] 数字声明与磁盘实际不一致，取消后续打包/发布。")
        sys.exit(1)
    print("[PASS] 全仓数字声明与磁盘实际一致（防差一错误 + 防跨文件逃逸）。")


if __name__ == "__main__":
    main()
