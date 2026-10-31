#!/usr/bin/env python3
"""
gen_readme_anchor.py — 从各 SKILL.md frontmatter 生成 README 版本锚定行

用法：
    python scripts/gen_readme_anchor.py          # 打印生成结果（dry-run）
    python scripts/gen_readme_anchor.py --write  # 实际写入 README.md

原理：
    遍历工作区根下所有 */SKILL.md，读 frontmatter 的 version 字段，
    按固定顺序生成锚定文本，替换 README.md 中
    <!-- ANCHOR:BEGIN --> 和 <!-- ANCHOR:END --> 之间的内容。

    改任何技能版本后跑一次本脚本即可，无需手抄。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ACMG 技能白名单（只检查这些，不扫整个目录——正式部署目录里有其他技能群）
ACMG_SKILLS = [
    "acmg-total-scheduler",
    "acmg-conflict-summary-output",
    "arad-inheritance-judgment",
    "clingen-vcep",  # 独立数据包，无 SKILL.md，手动维护
    "ev-bs1-bs2",
    "ev-disease-info",
    "ev-gene-identity",
    "ev-gnomad-constraint",
    "ev-pm1",
    "ev-pm2",
    "ev-pm3",
    "ev-pm4",
    "ev-pp1",
    "ev-pp2",
    "ev-pp3-bp4",
    "ev-pp4",
    "ev-ps1-pm5",
    "ev-ps2-pm6",
    "ev-ps3-bs3",
    "ev-ps4",
    "ev-pvs1",
    "ev-variant-literature-patient",
    "ev-variant-standardization",
]

# 独立数据包版本（clingen-vcep 不在主包，无 SKILL.md，手动维护）
EXTERNAL_VERSIONS = {
    "clingen-vcep": "1.1.0",
}


def read_skill_version(skill_dir: str) -> str | None:
    """读 SKILL.md frontmatter 的 version 字段"""
    skill_md = os.path.join(ROOT, skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return None
    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read(500)  # 只读前 500 字符足够覆盖 frontmatter
    # frontmatter 格式：---\nversion: x.y.z\n---
    m = re.search(r'^version:\s*([^\s\n]+)', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def collect_versions() -> list[tuple[str, str]]:
    """收集所有 ACMG 技能版本，按白名单固定顺序排列"""
    versions: dict[str, str] = {}

    # 只遍历白名单里的 ACMG 技能（正式目录里还有其他技能群，不能全扫）
    for skill_name in ACMG_SKILLS:
        # clingen-vcep 是外部数据包，无 SKILL.md，从 EXTERNAL_VERSIONS 取
        if skill_name in EXTERNAL_VERSIONS:
            versions[skill_name] = EXTERNAL_VERSIONS[skill_name]
            continue
        # 检查是否有 SKILL.md
        skill_dir = os.path.join(ROOT, skill_name)
        if os.path.isdir(skill_dir) and os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
            v = read_skill_version(skill_name)
            if v:
                versions[skill_name] = v

    # 按白名单固定顺序排列
    ordered: list[tuple[str, str]] = []
    for name in ACMG_SKILLS:
        if name in versions:
            ordered.append((name, versions[name]))
            del versions[name]
    # 剩余 ev-* 按字母序
    for name in sorted(versions.keys()):
        ordered.append((name, versions[name]))

    return ordered


def format_anchor_line(versions: list[tuple[str, str]]) -> str:
    """生成锚定行文本"""
    parts = [f"`{name}={v}`" for name, v in versions]
    return "> " + "、".join(parts) + "。"


def main():
    write_mode = "--write" in sys.argv

    versions = collect_versions()
    anchor_line = format_anchor_line(versions)

    print(f"收集到 {len(versions)} 个技能版本：")
    for name, v in versions:
        print(f"  {name} = {v}")
    print()
    print("生成的锚定行：")
    print(anchor_line)
    print()

    if not write_mode:
        print("[dry-run] 加 --write 实际写入 README.md")
        return 0

    # 读 README
    readme_path = os.path.join(ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    # 替换 ANCHOR 标记之间的内容
    pattern = r'(<!-- ANCHOR:BEGIN -->\n)>.*?\n(<!-- ANCHOR:END -->)'
    replacement = r'\1' + anchor_line + r'\n\2'
    new_readme = re.sub(pattern, replacement, readme, flags=re.DOTALL)

    if new_readme == readme:
        print("⚠️  README 未变化（锚定行已一致？）")
        return 0

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_readme)

    print(f"✅ 已写入 {readme_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
