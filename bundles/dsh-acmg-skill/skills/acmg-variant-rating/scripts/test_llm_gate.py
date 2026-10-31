#!/usr/bin/env python3
"""LLM 闸门契约测试（v1.5.0，2026-10-22 新增）

验证 ev-variant-literature-patient/main.py 的 LLM 闸门行为：
  G1 缺 KEY 时 _ensure_llm_env() 抛 LLMConfigError（含配置指引）
  G2 配齐通用兼容通道（LLM_BASE_URL/MODEL/API_KEY）时放行
  G3 配齐方舟通道（ARK_API_KEY）时放行
  G4 _call_llm_for_filter 在 LLM 全失败时抛 LLMConfigError（不再返回 "" 静默降级）
  G5 ≥50 篇关键词快速过滤分支不误伤（不调用 LLM 闸门）

运行：
  python scripts/test_llm_gate.py
退出码：0 = 全部通过；1 = 有失败
"""
import os
import sys
import importlib.util

MAIN_PATH = os.path.join(os.path.dirname(__file__), "..",
                         "ev-variant-literature-patient", "main.py")
# main.py 顶层 `from coze_workload_identity import requests`，coze_workload_identity.py
# 与 main.py 同目录。把该目录加入 sys.path，避免在 scripts/ 下运行时 ModuleNotFoundError。
EV_LIT_DIR = os.path.dirname(MAIN_PATH)
if EV_LIT_DIR not in sys.path:
    sys.path.insert(0, EV_LIT_DIR)


def _load_main():
    spec = importlib.util.spec_from_file_location("ev_lit_main", MAIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    # main.py 顶层 import requests（coze_workload_identity），需宿主注入，捕获导入失败
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001
        print(f"[SETUP] main.py 顶层导入失败: {e}")
        print("[SETUP] 继续尝试仅用可解析的闸门函数（若定义于模块顶层可独立测试）")
        raise
    return mod


def _clear_llm_env():
    for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY",
              "ARK_API_KEY", "COZE_ARK_API_KEY"):
        os.environ.pop(k, None)


def _has_guide(exc):
    t = str(exc)
    return ("LLM_BASE_URL" in t and "LLM_MODEL" in t
            and "LLM_API_KEY" in t and "console.volcengine.com" in t)


def main():
    mod = _load_main()
    LLMConfigError = mod.LLMConfigError
    ensure = mod._ensure_llm_env
    call = mod._call_llm_for_filter

    results = []
    def check(name, cond, detail=""):
        results.append((name, cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  -- {detail}" if detail else ""))

    # G1 缺 KEY -> 抛 LLMConfigError 且带指引
    _clear_llm_env()
    try:
        ensure()
        check("G1 缺KEY应抛LLMConfigError", False, "未抛错(放行了)")
    except LLMConfigError as e:
        check("G1 缺KEY应抛LLMConfigError", True)
        check("G1b 异常含完整配置指引", _has_guide(e))
    except Exception as e:  # noqa: BLE001
        check("G1 缺KEY应抛LLMConfigError", False, f"抛了{type(e).__name__}")

    # G2 配齐通用兼容通道 -> 放行
    _clear_llm_env()
    os.environ["LLM_BASE_URL"] = "https://api.deepseek.com/v1"
    os.environ["LLM_MODEL"] = "deepseek-chat"
    os.environ["LLM_API_KEY"] = "sk-test"
    try:
        ensure()
        check("G2 通用兼容通道配齐应放行", True)
    except Exception as e:  # noqa: BLE001
        check("G2 通用兼容通道配齐应放行", False, f"{type(e).__name__}: {e}")

    # G3 方舟通道 -> 放行
    _clear_llm_env()
    os.environ["ARK_API_KEY"] = "ark-test"
    try:
        ensure()
        check("G3 方舟通道配齐应放行", True)
    except Exception as e:  # noqa: BLE001
        check("G3 方舟通道配齐应放行", False, f"{type(e).__name__}: {e}")

    # G3b 通用通道缺 LLM_MODEL -> 抛 LLMConfigError
    _clear_llm_env()
    os.environ["LLM_BASE_URL"] = "https://api.deepseek.com/v1"
    os.environ["LLM_API_KEY"] = "sk-test"
    try:
        ensure()
        check("G3b 通用通道缺MODEL应抛", False, "放行了")
    except LLMConfigError:
        check("G3b 通用通道缺MODEL应抛", True)
    except Exception as e:  # noqa: BLE001
        check("G3b 通用通道缺MODEL应抛", False, f"{type(e).__name__}")

    # G4 _call_llm_for_filter 全失败 -> 抛 LLMConfigError（不再 return ""）
    # 模拟：无 sdk、无兼容通道、无方舟 key -> 应抛 LLMConfigError
    _clear_llm_env()
    try:
        r = call("test prompt")
        check("G4 LLM全失败应抛LLMConfigError", False, f"返回了 {r!r}")
    except LLMConfigError:
        check("G4 LLM全失败应抛LLMConfigError", True)
    except Exception as e:  # noqa: BLE001
        check("G4 LLM全失败应抛LLMConfigError", False, f"{type(e).__name__}: {e}")

    # G5 ≥50 篇关键词快速过滤：验证 _post_filter_results 在 >=50 时走关键词分支
    # 用 50 篇非核心文献 + 空核心，观察打印是否进入关键词模式（不调用 LLM 闸门）
    try:
        build = mod._build_variant_forms
        pf = mod._post_filter_results
        kw = mod._keyword_fast_filter
        papers = [
            {"pmid": str(i), "title": f"BRCA1 c.5266dupC variant {i}",
             "abstract": ""} for i in range(50)
        ]
        # 直接调用关键词过滤，应返回过滤结果而非抛 LLMConfigError
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            result = pf(papers, "c.5266dupC", "", "", "", "BRCA1", [])
        check("G5 >=50篇关键词分支不误伤", isinstance(result, tuple)
              and len(result[0]) >= 0)
    except Exception as e:  # noqa: BLE001
        check("G5 >=50篇关键词分支不误伤", False, f"{type(e).__name__}: {e}")

    failed = [n for n, c in results if not c]
    print(f"\n结果: {len(results)-len(failed)}/{len(results)} 通过")
    if failed:
        print("失败项:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
