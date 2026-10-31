#!/usr/bin/env python3
"""LLM 提取校验层契约测试（v1.6.0，2026-10-22 新增）

验证 ev-variant-literature-patient/main.py 的提取校验层：
  V1 C1 枚举合法性：genotype 越界取值 → invalid
  V2 C2 内部一致性：纯合+反式第二变异 → conflict
  V3 C2 内部一致性：复合杂合无反式 → conflict
  V4 C2 内部一致性：de_novo=是 但 parental 未报告 → conflict
  V5 C1/C2 全通过（clean 字段）→ clean, confidence=high
  V6 仅 ClinVar 查不到（unverified）→ has_issue, confidence=medium（不判 invalid）
  V7 校验层不编答案：原字段值原样保留（validated 继承 fields）
  V8 缺字段默认"未报告"时 clean（不误伤）

运行：
  python scripts/test_extraction_validation.py
退出码：0 = 全部通过；1 = 有失败
"""
import os
import sys
import importlib.util

MAIN_PATH = os.path.join(os.path.dirname(__file__), "..",
                         "ev-variant-literature-patient", "main.py")
EV_LIT_DIR = os.path.dirname(MAIN_PATH)
if EV_LIT_DIR not in sys.path:
    sys.path.insert(0, EV_LIT_DIR)


def _load_main():
    spec = importlib.util.spec_from_file_location("ev_lit_main", MAIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clear_llm_env():
    for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY",
              "ARK_API_KEY", "COZE_ARK_API_KEY"):
        os.environ.pop(k, None)


def main():
    mod = _load_main()
    _clear_llm_env()  # 校验层本身不触发 LLM 闸门，仅确保环境干净
    fails = 0
    total = 0

    def check(name, cond, detail=""):
        nonlocal fails, total
        total += 1
        mark = "[PASS]" if cond else "[FAIL]"
        if not cond:
            fails += 1
        print(f"  {mark} {name}  {detail}")

    # V1: C1 枚举非法
    r = mod._validate_extraction({"genotype": "半合子"}, "GJB2")
    check("V1 C1 genotype越界→invalid",
          r["validation"]["status"] == "invalid"
          and any(i["level"] == "invalid" for i in r["validation"]["issues"]),
          f"status={r['validation']['status']}")

    # V2: C2 纯合+反式
    r = mod._validate_extraction({"genotype": "纯合", "trans_variant": "c.235delC"}, "GJB2")
    check("V2 C2 纯合+反式→conflict",
          r["validation"]["status"] == "invalid"
          and any(i["level"] == "conflict" for i in r["validation"]["issues"]),
          f"status={r['validation']['status']}")

    # V3: C2 复合杂合无反式
    r = mod._validate_extraction({"genotype": "复合杂合", "trans_variant": "未报告"}, "GJB2")
    check("V3 C2 复合杂合无反式→conflict",
          r["validation"]["status"] == "invalid"
          and any(i["level"] == "conflict" for i in r["validation"]["issues"]),
          f"status={r['validation']['status']}")

    # V4: C2 de novo 无双亲
    r = mod._validate_extraction({"genotype": "杂合", "de_novo": "是",
                                  "parental_genotype": "未报告"}, "MYH7")
    check("V4 C2 de_novo=是 但parental未报告→conflict",
          r["validation"]["status"] == "invalid"
          and any(i["level"] == "conflict" for i in r["validation"]["issues"]),
          f"status={r['validation']['status']}")

    # V5: 干净字段
    r = mod._validate_extraction({"genotype": "杂合", "de_novo": "否",
                                  "parental_genotype": "父携母未携带",
                                  "trans_variant": "未报告",
                                  "phenotype_consistency": "与已知疾病谱一致"}, "MYH7")
    check("V5 干净→clean high",
          r["validation"]["status"] == "clean"
          and r["validation"]["confidence"] == "high",
          f"status={r['validation']['status']} conf={r['validation']['confidence']}")

    # V6: 仅 unverified（ClinVar 查不到）→ has_issue medium，不判 invalid
    #   用一个几乎不可能存在于 ClinVar 的合成变异名触发 unverified
    r = mod._validate_extraction({"genotype": "复合杂合", "trans_variant": "c.9999_10000delGG",
                                  "de_novo": "否", "parental_genotype": "父携母未携带"}, "GJB2")
    st = r["validation"]["status"]
    lv = {i["level"] for i in r["validation"]["issues"]}
    check("V6 仅unverified→has_issue medium(非invalid)",
          st == "has_issue" and r["validation"]["confidence"] == "medium"
          and "unverified" in lv and "conflict" not in lv and "invalid" not in lv,
          f"status={st} levels={lv}")

    # V7: 不编答案，字段原样保留
    r = mod._validate_extraction({"genotype": "杂合"}, "GJB2")
    check("V7 校验不编答案，原字段保留",
          r.get("genotype") == "杂合" and "validation" in r,
          f"genotype={r.get('genotype')}")

    # V8: 缺字段默认未报告时 clean（不误伤未报告字段）
    r = mod._validate_extraction({"genotype": "杂合", "de_novo": "未报告",
                                  "parental_genotype": "未报告",
                                  "trans_variant": "未报告",
                                  "phenotype_consistency": "无法判断"}, "MYH7")
    check("V8 缺字段默认未报告→clean",
          r["validation"]["status"] == "clean"
          and r["validation"]["confidence"] == "high",
          f"status={r['validation']['status']}")

    print(f"\n结果: {total-fails}/{total} 通过")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
