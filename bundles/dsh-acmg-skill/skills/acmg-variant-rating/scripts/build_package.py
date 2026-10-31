# -*- coding: utf-8 -*-
"""ACMG 评级技能群打包脚本（正式版，随包发布）。

从权威源（本仓库根）打包技能群 zip。VCEP 数据层独立入仓（D2 定案：数据单独入仓），
**不**打进技能群包——运行时由独立 VCEP 数据仓库提供。

用法：
    python scripts/build_package.py                                  # 打包当前仓库根 → 变异评级技能群_<date>.zip
    python scripts/build_package.py --src <root> --out <zip路径>     # 显式指定源与输出

退出码：0=成功打包 / 1=任一校验失败（禁止打包）。可挂 CI / release 链。
"""
import argparse
import os
import re
import subprocess
import sys
import zipfile
import pathlib

# 技能与工程内容（clingen-vcep 数据层独立入仓，不在此列）
DIRS = [
    "acmg-total-scheduler", "acmg-conflict-summary-output", "arad-inheritance-judgment",
    "ev-bs1-bs2", "ev-disease-info", "ev-gene-identity", "ev-gnomad-constraint",
    "ev-pm1", "ev-pm2", "ev-pm3", "ev-pm4", "ev-pp1", "ev-pp2", "ev-pp3-bp4",
    "ev-pp4", "ev-ps1-pm5", "ev-ps2-pm6", "ev-ps3-bs3", "ev-ps4", "ev-pvs1",
    "ev-variant-literature-patient", "ev-variant-standardization",
    "config", "scripts", "docs",
]
EXTRA = ["LICENSE", "SECURITY.md", "CONTRIBUTING.md", "requirements.txt",
         "requirements-lock.txt", "README.md", "sync-manifest.md"]
EXCLUDE_DIRS = {"__pycache__", "_cache", ".gnomad_cache"}


def _run_py(script_rel, src):
    """在 src 根下运行一个 scripts 脚本；返回错误列表（空=通过）。"""
    p = os.path.join(src, script_rel)
    if not os.path.exists(p):
        return [f"{script_rel} 缺失"]
    try:
        r = subprocess.run([sys.executable, p], cwd=src,
                           capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return [f"{script_rel} 执行超时（600s）"]
    if r.returncode == 0:
        return []
    tail = (r.stdout or "").strip().splitlines()[-3:]
    return [f"{script_rel} 未通过（退出码 {r.returncode}），尾部输出: " + " | ".join(tail)]


def run_verify_counts(src):
    return _run_py("scripts/verify_counts.py", src)


def run_contract_test(src):
    return _run_py("scripts/contract_test.py", src)


def run_regression_gate(src):
    return _run_py("scripts/regression_gate.py", src)


def run_gene_specific_sync(src):
    return _run_py("scripts/check_gene_specific_sync.py", src)


def run_py_compile(src):
    """scripts/config 下所有 .py 语法编译。"""
    errs = []
    for sub in ("scripts", "config"):
        d = os.path.join(src, sub)
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(".py"):
                    p = os.path.join(root, f)
                    try:
                        import py_compile
                        py_compile.compile(p, doraise=True)
                    except py_compile.PyCompileError as ex:
                        errs.append(f"{os.path.relpath(p, src)}: {ex}")
    return errs


def check_embed_versions(src):
    """检查 SKILL.md 正文里嵌句版本日志断裂模式（** **vX）。"""
    errs = []
    pat = re.compile(r"\*\* *\*\* *v\d")
    for d in DIRS:
        p = os.path.join(src, d, "SKILL.md")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            body = f.read()
        parts = body.split("---", 2)
        body_text = parts[2] if len(parts) > 2 else body
        for i, ln in enumerate(body_text.splitlines(), 1):
            if pat.search(ln):
                errs.append(f"{d}/SKILL.md L{i}: {ln.strip()[:80]}")
    return errs


def build(src, out):
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d in DIRS:
            s = os.path.join(src, d)
            if not os.path.isdir(s):
                print(f"[SKIP] 目录不存在: {d}")
                continue
            for root, dirs_, files in os.walk(s):
                dirs_[:] = [x for x in dirs_ if x not in EXCLUDE_DIRS]
                for f in files:
                    if f.endswith(".pyc"):
                        continue
                    if f.startswith("_") and f.endswith(".txt"):
                        continue
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, src)
                    z.write(full, rel)
                    count += 1
        for e in EXTRA:
            p = os.path.join(src, e)
            if os.path.exists(p):
                z.write(p, e)
                count += 1
            else:
                print(f"[WARN] 缺失配套文件: {e}")
    size = os.path.getsize(out)
    print(f"打包完成: {out}")
    print(f"文件数: {count}  大小: {size / 1024 / 1024:.1f} MB")
    return count


def main():
    ap = argparse.ArgumentParser(description="ACMG 评级技能群打包（正式版，VCEP 数据独立入仓）")
    # 默认 src = 脚本文件所在目录的父目录（仓库根）
    default_src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--src", default=default_src, help="权威源仓库根")
    ap.add_argument("--out", default=None, help="输出 zip 路径（默认 变异评级技能群_<date>.zip）")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    if args.out:
        out = os.path.abspath(args.out)
    else:
        date = pathlib.Path(__file__).parent.name  # 兜底；用当前日期更稳
        import time
        out = os.path.join(os.getcwd(), f"变异评级技能群_{time.strftime('%Y%m%d')}.zip")

    checks = [
        ("README 数字声明（verify_counts.py）", lambda: run_verify_counts(src)),
        ("嵌句版本日志（** **vX 断裂模式）", lambda: check_embed_versions(src)),
        ("py_compile 语法编译（scripts/config 全 .py）", lambda: run_py_compile(src)),
        ("契约测试（contract_test.py）", lambda: run_contract_test(src)),
        ("回归门禁（regression_gate.py）", lambda: run_regression_gate(src)),
        ("注册表一致性（check_gene_specific_sync.py）", lambda: run_gene_specific_sync(src)),
    ]
    ok = True
    for name, fn in checks:
        errs = fn()
        if errs:
            ok = False
            print(f"[FAIL] {name}:")
            for e in errs:
                print("   -", e)
    if not ok:
        print("防复发校验未通过，取消打包。")
        return 1
    print("[PASS] 防复发校验通过（verify_counts + 嵌句检测 + py_compile + 契约测试 + 回归门禁 + 注册表一致性）。")

    build(src, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
