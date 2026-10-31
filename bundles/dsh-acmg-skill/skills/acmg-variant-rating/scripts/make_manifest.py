# -*- coding: utf-8 -*-
"""ACMG 评级技能群 MANIFEST 生成（SHA-256 哈希锁 + 版本关联）。

在 build_package.py 之后运行：对打包 zip 内所有文件算 SHA-256，生成 MANIFEST.json。
含技能群发布版本 ↔ VCEP 数据仓库版本关联（D2 定案：发版记版本关联、VCEP 库自记版本维护统计）。

用法：
    python scripts/make_manifest.py --zip <built.zip> --version <技能群发布版本> [--vcep-version <VCEP版本>] [--vcep-repo <owner/repo>] [--vcep-branch <分支>] [--vcep-commit <commit>] [--vcep-snapshot-date <YYYY-MM-DD>] [--out MANIFEST.json]

退出码：0=成功 / 2=输入 zip 缺失或损坏。可挂 CI / release 链。
"""
import argparse
import hashlib
import json
import os
import sys
import time
import zipfile


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description="ACMG 评级技能群 MANIFEST 生成（哈希锁 + 版本关联）")
    ap.add_argument("--zip", required=True, help="build_package.py 产出的 zip")
    ap.add_argument("--version", required=True, help="技能群发布版本（如 v1.2.0）")
    ap.add_argument("--vcep-version", default="", help="VCEP 数据仓库版本（可选，未提供记 unknown）")
    ap.add_argument("--vcep-repo", default="", help="VCEP 数据仓库 owner/repo（可选，未提供不写 vcep_data 块）")
    ap.add_argument("--vcep-branch", default="", help="VCEP 数据仓库分支（可选）")
    ap.add_argument("--vcep-commit", default="", help="VCEP 数据仓库 commit（可选）")
    ap.add_argument("--vcep-snapshot-date", default="", help="VCEP 数据快照日期 YYYY-MM-DD（可选）")
    ap.add_argument("--out", default="MANIFEST.json", help="输出 MANIFEST 路径")
    args = ap.parse_args()

    if not os.path.exists(args.zip):
        print(f"[FATAL] zip 不存在: {args.zip}", file=sys.stderr)
        return 2
    try:
        zf = zipfile.ZipFile(args.zip)
    except zipfile.BadZipFile:
        print(f"[FATAL] zip 损坏（非有效压缩包）: {args.zip}", file=sys.stderr)
        return 2

    files = {}
    with zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            data = zf.read(name)
            files[name] = {"sha256": sha256_bytes(data), "size": len(data)}

    manifest = {
        "asset": "ACMG-Variant-Evaluation 受控文件完整性清单（发布锁）",
        "manifest_version": "1.0",
        "skills_version": args.version,
        "vcep_data_version": args.vcep_version or "unknown",
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "file_count": len(files),
        "files": files,
    }
    if args.vcep_repo:
        manifest["vcep_data"] = {
            "repo": args.vcep_repo,
            "branch": args.vcep_branch,
            "commit": args.vcep_commit,
            "version": args.vcep_version or "unknown",
            "snapshot_date": args.vcep_snapshot_date,
        }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"MANIFEST 已生成: {args.out}（{len(files)} 个文件，skills_version={args.version}, "
          f"vcep_data_version={args.vcep_version or 'unknown'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
