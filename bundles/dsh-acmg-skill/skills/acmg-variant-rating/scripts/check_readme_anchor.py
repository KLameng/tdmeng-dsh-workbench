#!/usr/bin/env python3
"""
check_readme_anchor.py — 校验 README 版本锚定行与各 SKILL frontmatter 一致性

用法：
    python scripts/check_readme_anchor.py

退出码：
    0 = 一致
    1 = 不一致（README 锚定行与实际 frontmatter 有差异）

原理：
    从 README.md 的 <!-- ANCHOR:BEGIN --> / <!-- ANCHOR:END --> 标记里
    解析声明的版本号，与各 SKILL.md frontmatter 的实际 version 对比。
    不一致说明改了技能版本但没跑 gen_readme_anchor.py 更新 README。
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

# 外部数据包（无 SKILL.md，手动维护版本，与 gen_readme_anchor.py 保持一致）
EXTERNAL_VERSIONS = {
    "clingen-vcep": "1.1.0",
}


def read_skill_version(skill_dir: str) -> str | None:
    """读 SKILL.md frontmatter 的 version 字段"""
    skill_md = os.path.join(ROOT, skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return None
    with open(skill_md, "r", encoding="utf-8") as f:
        content = f.read(500)
    m = re.search(r'^version:\s*([^\s\n]+)', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def get_actual_versions() -> dict[str, str]:
    """收集 ACMG 技能白名单内的实际版本（含外部数据包）"""
    versions = {}
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
    return versions


def get_readme_versions() -> dict[str, str]:
    """从 README.md ANCHOR 标记里解析声明的版本"""
    readme_path = os.path.join(ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()

    # 提取 ANCHOR 标记之间的内容
    m = re.search(r'<!-- ANCHOR:BEGIN -->\n(.*?)\n<!-- ANCHOR:END -->', readme, re.DOTALL)
    if not m:
        return {}

    anchor_text = m.group(1)
    # 解析 `skill-name=x.y.z` 格式
    versions = {}
    for match in re.finditer(r'`([^`=]+)=([^`]+)`', anchor_text):
        name = match.group(1).strip()
        version = match.group(2).strip()
        versions[name] = version
    return versions


def main():
    actual = get_actual_versions()
    declared = get_readme_versions()

    if not declared:
        print("[FAIL] README.md 未找到 ANCHOR 标记，或标记内无版本号")
        print("       请先运行 scripts/gen_readme_anchor.py --write 生成锚定行")
        return 1

    errors = []

    # 检查 1：数量是否一致
    if len(actual) != len(declared):
        errors.append(f"数量不一致：实际 {len(actual)} 个技能，README 声明 {len(declared)} 个")

    # 检查 2：逐技能对比
    all_names = sorted(set(list(actual.keys()) + list(declared.keys())))
    for name in all_names:
        a = actual.get(name)
        d = declared.get(name)
        if a is None:
            errors.append(f"  {name}: README 声明了但实际无 SKILL.md（多余）")
        elif d is None:
            errors.append(f"  {name}: 实际有 SKILL.md 但 README 未声明（遗漏）")
        elif a != d:
            errors.append(f"  {name}: 实际={a}, README={d}（不一致）")

    if errors:
        print(f"[FAIL] README 版本锚定不一致，共 {len(errors)} 处：")
        for e in errors:
            print(f"  {e}")
        print()
        print("修复方法：运行 python scripts/gen_readme_anchor.py --write")
        return 1

    print(f"[PASS] README 版本锚定一致（{len(actual)} 个技能）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
