#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
combination_eval.py — ACMG 组合层分口径评测（双尺子版，v20261015b）

同尺子对同尺子：金标准自带 methodA（经典联合规则 Table5）与 methodB（Tavtigian 分值）两把尺子，
评测时：
  - 引擎 engine_a（表5） vs 金标准 methodA   → 表5一致率
  - 引擎 engine_b（分值） vs 金标准 methodB   → 分值一致率
官方裁定条目（basis=VCEP官方）验证引擎是否官方短路（class 与官方分类一致）。

不再拿单一金标准 final 去同时衡量两套引擎（那会混尺子，指标失真，见第五轮审计 §7）。

用法：
  python combination_eval.py --golden golden.json [--conf ../config/thresholds.json] [--interval bmpR2_gn125_v2]

golden.json（由 golden_builder.py 生成）：
  { "ruler_A": "...", "ruler_B": "...", "cases": [
      {"id":"var001","gene":"SURF1","criteria":[{"code":"PVS1","level":"VeryStrong"},...],
       "methodA":"Likely Pathogenic","methodB":"Likely Pathogenic","basis":"Table5","official":false}
  ]}

输出：
  - 表5一致率 / 分值一致率 / 两套一致率（agreement）
  - 逐变异明细（两列各自命中）
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acmg_combine import AcmgCombine, load_config, parse_evidence_items, ACMGCombineError  # noqa: E402

DEFAULT_CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "thresholds.json")
DEFAULT_GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "golden.json")


def main():
    ap = argparse.ArgumentParser(description="ACMG 组合层分口径评测（双尺子：金标准 methodA/methodB）")
    ap.add_argument("--golden", default=DEFAULT_GOLDEN, help="金标准 JSON（默认随包 config/golden.json；含 criteria/methodA/methodB/basis/official）")
    ap.add_argument("--conf", default=DEFAULT_CONF, help="集中阈值配置表")
    ap.add_argument("--d1", type=float, default=None, help="外部全链路 D1（百分比），用于误差拆解")
    ap.add_argument("--interval", choices=["2023", "2020", "bmpR2_gn125_v2"], default=None,
                    help="Tavtigian 分值区间（默认 None→读 config/tavtigian_interval.default，与引擎/门禁一致；不传时不得静默用 2023 草案；bmpR2_gn125_v2 须 --gene BMPR2 否则拒绝）")
    ap.add_argument("--gene", help="基因名（HGNC 大写，如 BMPR2）；仅当 --interval=bmpR2_gn125_v2 时必传且须为 BMPR2（评测金标准默认 2020，不涉及）")
    args = ap.parse_args()

    golden = json.load(open(args.golden, encoding="utf-8")).get("cases", [])
    if not golden:
        print("golden.json 无 cases")
        return 1
    conf = load_config(args.conf)
    engine = AcmgCombine(conf)

    rows = []
    ma_t5 = mb = mo = 0
    na_t5 = nb = 0
    n_pt = 0
    official_n = official_follow = 0
    skip = 0
    total = len(golden)
    for r in golden:
        gid = r.get("id", "?")
        criteria = r.get("criteria", [])
        methodA = r.get("methodA")
        methodB = r.get("methodB")
        basis = r.get("basis")
        try:
            items, official = parse_evidence_items(criteria)
            out = engine.combine(items, interval=args.interval, official=official, gene=args.gene)
        except ACMGCombineError as ex:
            # D17（P5-8）：契约/参数错误单独捕获，exit≠0，不与"数据 skip"混同
            print(f"[FATAL] 组合层参数/契约错误（非数据问题，禁止当 SKIP 跳过）：{ex}")
            return 2
        except Exception as ex:  # noqa: BLE001
            skip += 1
            rows.append({"id": gid, "goldenA": methodA, "goldenB": methodB,
                         "table5": "SKIP", "score": "SKIP", "agreement": None,
                         "confidence": None, "total": None, "skip": str(ex)[:80]})
            continue
        is_official = out.get("status") == "official"
        if is_official:
            a = b = out.get("class")
            ag = True
            # 官方短路条目单独统计（官方遵循率），不混入引擎一致率（否则结构性虚高：
            # 金标准 methodA/B 即抄官方，官方条目必然命中）
            official_n += 1
            official_follow += (a == methodA) if methodA is not None else (b == methodB)
        elif out.get("status") == "official_pending":
            a = b = out.get("result", "VUS")
            ag = True
        else:
            a = out["engine_a"]["result"]
            b = out["engine_b"]["result"]
            ag = out.get("agreement")
        # 两套结算分口径：表5一致率仅对 basis=Table5 条目（methodA 确由经典联合规则推）；
        # basis=点值法 条目的 methodA 由点值法推，不参与表5（否则混尺子、表5一致率假性偏低）；
        # methodB（Tavtigian 分值）参与分值一致率，但官方短路条目除外（单独统计）。
        if basis == "Table5" and methodA is not None:
            na_t5 += 1
            ma_t5 += (a == methodA)
        if basis == "点值法":
            n_pt += 1
        if methodB is not None and not is_official:
            nb += 1
            mb += (b == methodB)
        mo += 1 if ag else 0
        rows.append({
            "id": gid, "goldenA": methodA, "goldenB": methodB, "table5": a, "score": b,
            "agreement": ag, "confidence": out.get("confidence"), "total": out.get("engine_b", {}).get("total"),
            "basis": basis, "m_table5": (a == methodA) if basis == "Table5" else None,
            "m_score": (b == methodB) if (methodB and not is_official) else None,
            "official": is_official,
        })

    rate = lambda n, d: f"{n/d*100:.1f}%" if d else "n/a"
    lines = ["=== ACMG 组合层分口径评测（双尺子同尺子对同尺子） ===",
             f"变异数: {total}   SKIP: {skip}   basis 分布: Table5={na_t5} 点值法={n_pt} VCEP官方={official_n}",
             f"表5一致率（engine_a vs methodA，仅 Table5 基准）: {rate(ma_t5, na_t5)} ({ma_t5}/{na_t5})",
             f"分值一致率（engine_b vs methodB，非官方条目）: {rate(mb, nb)} ({mb}/{nb})",
             f"官方遵循率（VCEP官方短路，单独统计，不混入引擎一致率）: {rate(official_follow, official_n)} ({official_follow}/{official_n})",
             f"两套引擎一致率（agreement）: {rate(mo, total)} ({mo}/{total})",
             f"点值法衍生条目（methodA 非表5推，不参与表5一致率）: {n_pt}",
             ""]
    lines.append("== 逐变异明细 ==")
    for r in rows:
        flag = "S" if r.get("skip") else ("官方✓" if (r.get("basis") == "VCEP官方" and r.get("m_score")) else ("✓" if (r.get("m_table5") and r.get("m_score")) else ("△" if not r.get("agreement") else "✗")))
        lines.append(
            f"{r['id']} [basis={r.get('basis')}] | 金标准A={r['goldenA']} B={r['goldenB']} | 表5={r['table5']} 分值={r['score']} "
            f"两套={'一致' if r.get('agreement') else '分歧'} {flag}")
    if args.d1 is not None and na_t5:
        combo = ma_t5 / na_t5 * 100
        lines += ["", "== 误差拆解（基于表5口径） ==",
                  f"全链路 D1 (外部): {args.d1:.1f}%",
                  f"组合层一致率 (表5): {combo:.1f}%",
                  f"→ 组合层贡献偏差: {(100-combo):.1f}pp；证据判定层贡献偏差: {(combo-args.d1):.1f}pp"]
    out_txt = "\n".join(lines)
    print(out_txt)
    summary = {
        "total": total, "skip": skip, "na_t5": na_t5, "n_pt": n_pt, "nb": nb,
        "match_table5": ma_t5, "match_score": mb, "match_agreement": mo,
        "rate_table5": round(ma_t5 / na_t5 * 100, 1) if na_t5 else None,
        "rate_score": round(mb / nb * 100, 1) if nb else None,
        "rate_agreement": round(mo / total * 100, 1) if total else None,
        "rows": rows,
    }
    print("\n--- JSON ---")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
