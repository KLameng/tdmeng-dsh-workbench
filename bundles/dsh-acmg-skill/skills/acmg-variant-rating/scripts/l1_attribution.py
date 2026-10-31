# -*- coding: utf-8 -*-
"""ACMG 技能群 L1 收敛跟踪工具（根因7 诊断）。
每次改版后，用同一份金标准+评级结果重跑本工具，看判据层(L1)误差是否收敛。
误差分层：
  L0 事实层  = 文献搬运/坐标/转录本 错误（data 段事实，脚本标注需人工抽查）
  L1 判据层  = 证据码判定错误（漏用/滥用/档位错；该用没用、不该用用了、用了但档位不对）
  L2 组合层  = 证据码正确但最终定级错（组合算术；现引擎 acmg_combine 差分零差异，此类应≈0，
               若>0 多为 PVS1 档位两可等判据边界，非算术）
用法：
  python l1_attribution.py                          # 默认读 acmg-evaluation-framework/tests/golden_47.json + result_47_v20.json
  python l1_attribution.py --golden <g> --result <r>
  python l1_attribution.py --prev-l1 <N>            # 对比上一轮 L1 变异数，输出收敛方向
"""
import json, sys, os, io, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_G = os.path.normpath(os.path.join(HERE, "..", "acmg-evaluation-framework", "tests", "golden_47.json"))
DEFAULT_R = os.path.normpath(os.path.join(HERE, "..", "acmg-evaluation-framework", "tests", "result_47_v20.json"))

STRENGTHS = ("VeryStrong", "Strong", "Moderate", "Supporting")

def parse_golden_codes(ev_list):
    """golden authoritative_evidence -> {code: strength|None}。None=未标注强度，只判用/不用。"""
    out = {}
    for e in ev_list:
        e = e.strip()
        if not e:
            continue
        p = e.split("_")
        out[p[0]] = p[1] if len(p) >= 2 and p[1] in STRENGTHS else None
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default=DEFAULT_G)
    ap.add_argument("--result", default=DEFAULT_R)
    ap.add_argument("--prev-l1", type=int, default=None, help="上一轮 L1 变异数，用于收敛对比")
    args = ap.parse_args()

    with open(args.golden, encoding="utf-8") as f:
        golden = json.load(f)
    with open(args.result, encoding="utf-8") as f:
        result = json.load(f)

    gv = {v["id"]: v for v in golden["dataset"]["variants"]}
    rv = {r["variant_id"]: r for r in result["evaluation_run"]["results"]}

    layers = {"L0事实": [], "L1判据": [], "L2组合/定级": [], "正确": []}
    l1 = {"漏用": 0, "滥用": 0, "档位错": 0}
    tot = 0
    for vid, g in gv.items():
        if vid not in rv:
            layers["L1判据"].append(vid); continue
        r = rv[vid]
        tot += 1
        gcodes = parse_golden_codes(g["authoritative_evidence"])
        ai = {e["code"]: (e.get("strength") if e.get("strength") in STRENGTHS else None) for e in r.get("evidence_codes", [])}
        missed = [c for c in gcodes if c not in ai]
        overused = [c for c in ai if c not in gcodes]
        wrong = [f"{c}(应{gcodes[c]}/实{ai[c]})" for c in gcodes if c in ai and gcodes[c] and ai[c] and gcodes[c] != ai[c]]
        final_ok = (r.get("final_class") == g["authoritative_class"])
        if not (missed or overused or wrong) and final_ok:
            layers["正确"].append(vid)
        elif missed or overused or wrong:
            layers["L1判据"].append(vid)
            l1["漏用"] += len(missed); l1["滥用"] += len(overused); l1["档位错"] += len(wrong)
            print(f"[L1] {vid} {g.get('gene','')} {g.get('hgvs_c','')} 金={g['authoritative_class']} AI={r.get('final_class')} "
                  f"漏用{missed} 滥用{overused} 档位{wrong}")
        else:
            layers["L2组合/定级"].append(vid)
            print(f"[L2] {vid} {g.get('gene','')} {g.get('hgvs_c','')} 金={g['authoritative_class']} AI={r.get('final_class')}（证据码与金一致但定级不同）")

    err = tot - len(layers["正确"])
    print("\n===== L1 收敛跟踪（%d 变异） =====" % tot)
    for k in ("L0事实", "L1判据", "L2组合/定级", "正确"):
        print(f"  {k}: {len(layers[k])}  ({len(layers[k])/tot*100:.1f}%)")
    print(f"  L1 细分: 漏用{l1['漏用']} 滥用{l1['滥用']} 档位错{l1['档位错']}")
    if err:
        print(f"  误差 {err} 中 L1 {len(layers['L1判据'])/err*100:.1f}%、L2 {len(layers['L2组合/定级'])/err*100:.1f}%、L0 {len(layers['L0事实'])/err*100:.1f}%")
    if args.prev_l1 is not None:
        d = args.prev_l1 - len(layers["L1判据"])
        arrow = "↓ 收敛" if d > 0 else ("↑ 发散" if d < 0 else "=")
        print(f"  与上一轮 L1={args.prev_l1} 对比: 本轮 L1={len(layers['L1判据'])} ({d:+d} {arrow})")

if __name__ == "__main__":
    main()
