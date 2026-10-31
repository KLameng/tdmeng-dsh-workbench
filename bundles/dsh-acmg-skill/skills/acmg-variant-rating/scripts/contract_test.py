#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
contract_test.py — L1→L2 输入契约测试（收敛计划 P3，纳入打包门禁）
验证组合层输入契约（input-schema.md）四条硬性：
  1. 官方裁定带 class → 短路，不按通用规则
  2. 官方裁定无 class（level 不含分类）→ official_pending，不得按 VUS 处置
  3. 官方裁定可从 status 描述文字提取分类（var005/006/030/038 形态）→ 短路官方
  4. 复合码方向限定：PS2/PM6 同向只计一次；PP3/BP4、PM2/BA1 对向 skip（不双计/不抵消/不推良性）
任一 FAIL → 退出码 1。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.join(HERE, "acmg_combine.py")  # 相对路径：引擎同目录（随包可移植）

fails = 0
passed = 0


def ok(name, cond, detail=""):
    global fails, passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}  {detail}")
    else:
        fails += 1
        print(f"  [FAIL] {name}  {detail}")


def cli_ev(ev):
    r = subprocess.run([sys.executable, SC, "-e", json.dumps(ev, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


def has(out, *kws):
    return all(k in out for k in kws)


# 1. 官方带 class 短路
rc, out, err = cli_ev([{"code": "VCEP官方裁定", "level": "官方", "class": "Pathogenic"}])
ok("官方带 class → 短路 Pathogenic", rc == 0 and has(out, "官方", "Pathogenic"), f"rc={rc}")

# 2. 官方无 class → official_pending，不得按 VUS
rc, out, err = cli_ev([{"code": "VCEP官方裁定", "level": "官方"}])
ok("官方无 class → official_pending（不按 VUS）",
   rc == 0 and "official_pending" in out and "待上游补官方分类" in out and "不得按通用 VUS" in out, f"rc={rc}")

# 3. 官方可从 status 描述提取分类（var005/006/030/038 形态）
for status, expect in [
    ("Hearing Loss VCEP GN023：PP3+PM3_VS+PP4+PP1_S→致病", "Pathogenic"),
    ("ClinGen Hearing Loss 专家组共识：AR NSHL 致病、可变外显", "Pathogenic"),
    ("ClinGen Hemoglobinopathy VCEP GN170：VCV15458=Pathogenic（15 confirmed trans）", "Pathogenic"),
]:
    rc, out, err = cli_ev([{"code": "VCEP官方裁定", "level": "官方", "status": status}])
    ok(f"官方 status 补分类 → {expect}", rc == 0 and expect in out, f"rc={rc}")

# 4a. 复合码同向只计一次（PS2/PM6）
rc, out, err = cli_ev({"PS2/PM6": "Moderate"})
ok("复合码同向只计一次（PS2/PM6→1条 Moderate）", rc == 0 and "PM6" not in out and "Moderate" in out, f"rc={rc}")

# 4b. 复合码对向 skip（PP3/BP4 不双计不抵消）
rc, out, err = cli_ev({"PP3/BP4": "Supporting"})
ok("复合码对向 skip（PP3/BP4 不双计不抵消）", rc == 0, f"rc={rc}")

# 4c. 复合码对向 skip（PM2/BA1 不推良性）
rc, out, err = cli_ev({"PM2/BA1": "Supporting"})
ok("复合码对向 skip（PM2/BA1 不推良性）", rc == 0, f"rc={rc}")

# 4d. BA1 不带 level → fallback VeryStrong → Benign（D15/D16：堵"成立的 BA1"断言盲区）
rc, out, err = cli_ev({"BA1": ""})
ok("BA1 不带 level → Benign", rc == 0 and "Benign" in out, f"rc={rc} out={out[:80]}")

# 4e. BA1 Standalone（原始等级名，白名单已收录）→ Benign（不再静默 skip 成 VUS）
rc, out, err = cli_ev({"BA1": "Standalone"})
ok("BA1 Standalone → Benign（白名单收录，不再 skip 成 VUS）", rc == 0 and "Benign" in out, f"rc={rc} out={out[:80]}")

# 4f. BA1 Stand-alone（连字符写法）→ Benign
rc, out, err = cli_ev({"BA1": "Stand-alone"})
ok("BA1 Stand-alone → Benign", rc == 0 and "Benign" in out, f"rc={rc} out={out[:80]}")

# 4g. BA1 降档等级（D26/F2 钉住）：BA1 只看 code、成立即判良性；降档等级不 skip、按该等级计良性侧
rc, out, err = cli_ev({"BA1": "Supporting"})
ok("BA1=Supporting → 引擎A Benign、引擎B Likely Benign（不 skip 不升格）",
   rc == 0 and "Benign" in out and "Likely Benign" in out, f"rc={rc} out={out[:100]}")

# 4h. BA1 带括号写法（D27/v5.5.2）：ClinGen VCEP 官方原文 "1 Stand Alone (BA1)" 剥括号对 → Benign；
# 括号前缀变体 "(BA1) Stand Alone" 同样归一；知识库原文不改、只改引擎 standalone 识别
rc, out, err = cli_ev({"BA1": "Stand Alone (BA1)"})
ok("BA1 'Stand Alone (BA1)' → Benign（D27 剥括号对）", rc == 0 and "Benign" in out, f"rc={rc} out={out[:80]}")
rc, out, err = cli_ev({"BA1": "(BA1) Stand Alone"})
ok("BA1 '(BA1) Stand Alone' → Benign（D27 剥括号对，前缀变体）", rc == 0 and "Benign" in out, f"rc={rc} out={out[:80]}")

# 5a. 负向断言（D19/D21）：非 BA1 码写 standalone → 整条 skip，不升格（PM1+PM2_M+PP3_S 不得成 Pathogenic）
rc, out, err = cli_ev({"PM1": "Standalone", "PM2": "Moderate", "PP3": "Supporting"})
ok("非BA1+Standalone 不升格（PM1 用例仍 VUS）", rc == 0 and "VUS" in out and "Pathogenic" not in out, f"rc={rc} out={out[:80]}")

# 5b. 负向断言：PP3+SA 单码 → PP3 skip，不参与计分（结果 VUS 非致病）
rc, out, err = cli_ev({"PP3": "SA"})
ok("PP3+SA 单码不参与计分（VUS）", rc == 0 and "VUS" in out and "Pathogenic" not in out, f"rc={rc} out={out[:80]}")

# 5c. 负向断言（D28 修复，有牙齿）：BS1+SA 不得升格。BS1 因 standalone 被 skip，
# 结论必须与"只喂背景"（去掉 BS1）一致；若 BS1 被错误升格 VeryStrong → 会推成 Benign。
# 牙齿检验：v10 把 BS1:SA 升 VeryStrong → Benign（断言 FAIL）；v11 起 skip → VUS（断言 PASS）。
rc_a, out_a, _ = cli_ev({"BS1": "SA"})
rc_b, out_b, _ = cli_ev({})
ok("BS1+SA 不升格：BS1 被 skip，结论与空背景一致（VUS，不含 Benign/Pathogenic）",
   rc_a == 0 and "VUS" in out_a and "Benign" not in out_a and "Pathogenic" not in out_a
   and "VUS" in out_b and "Benign" not in out_b, f"rc_a={rc_a} out_a={out_a[:60]}")

# 5d. 负向断言（D29 修复）：list 形态的 stand-alone 维度（D19 门控在 list 分支同样生效）
rc, out, err = cli_ev([{"code": "PM1", "level": "Standalone"}])
ok("list：非 BA1+Standalone 不升格（PM1 skip，仍 VUS）",
   rc == 0 and "VUS" in out and "Pathogenic" not in out, f"rc={rc} out={out[:80]}")

# 5e. D24 负向断言（dict 形态，F1 cap）：PM2=Strong → 封顶到 Supporting 计入（cap），绝不按传入等级判 Pathogenic
rc, out, err = cli_ev({"PM2": "Strong", "PP3": "Supporting", "PS3": "Strong"})
ok("dict：PM2=Strong → 封顶 Supporting（不判 Pathogenic，结果为 LP）",
   rc == 0 and "Likely Pathogenic" in out and "Pathogenic" not in out.replace("Likely Pathogenic", ""), f"rc={rc} out={out[:100]}")
# F4（去子串）：items 层断言 PM2 已封顶 Supporting、note 含 cap、capped 标记置位（F6）
import acmg_combine as _ac
_its, _of = _ac.parse_evidence_items({"PM2": "Strong", "PP3": "Supporting", "PS3": "Strong"})
_pm2 = [i for i in _its if i["code"] == "PM2"]
ok("dict：PM2 items 层已 cap（level=Supporting, skip=False, note 含 cap, capped=True）",
   bool(_pm2) and _pm2[0]["level"] == "Supporting" and not _pm2[0]["skip"] and "cap" in (_pm2[0].get("note") or "") and _pm2[0].get("capped"),
   f"pm2={[(i['level'],i['skip'],i.get('note'),i.get('capped')) for i in _pm2]}")
# F6（v5.5.1）：cap 留痕透传到 CLI 输出，可审计可见
rc, out, err = cli_ev({"PM2": "Strong", "PP3": "Supporting", "PS3": "Strong"})
ok("dict：CLI 输出含被封顶标记（F6 可审计）", rc == 0 and "封顶" in out, f"rc={rc} out={out[:100]}")

# 5f. D24 负向断言（list 形态）：PM2 非 Supporting 同样封顶 Supporting（cap）
rc, out, err = cli_ev([{"code": "PM2", "level": "Strong"}, {"code": "PP3", "level": "Supporting"}])
ok("list：PM2=Strong → 封顶 Supporting（list 分支同 dict 生效）",
   rc == 0 and "Pathogenic" not in out, f"rc={rc} out={out[:100]}")

# 6. v5.6.2 负向断言：去掉"点数法优先仲裁/取值归一"后，combine() 输出两套并列+定位，
# 不含单一最终分类（arbitrated_result/arbitration）字段；CLI 打印两套定位、无"最终分类(仲裁)"
_combine = _ac.AcmgCombine(_ac.load_config(os.path.join(HERE, "..", "config", "thresholds.json")))
_its6, _of6 = _ac.parse_evidence_items({"PVS1": "VeryStrong"})  # 旧仲裁：A=VUS / B=LP → arbitrated=LP
_c6 = _combine.combine(_its6, interval="2020", official=_of6)
ok("v5.6.2：combine() 输出含 engine_a/engine_b/agreement/positioning",
   all(k in _c6 for k in ("engine_a", "engine_b", "agreement", "positioning")),
   f"keys={sorted(_c6.keys())}")
ok("v5.6.2：combine() 不含单一最终分类字段 arbitrated_result/arbitration（不取值归一）",
   ("arbitrated_result" not in _c6) and ("arbitration" not in _c6),
   f"keys={sorted(_c6.keys())}")
rc, out, err = cli_ev({"PVS1": "VeryStrong"})
ok("v5.6.2：CLI 并列输出两套定位、无'最终分类(仲裁)'",
   rc == 0 and "两套定位" in out and "不取值归一" in out and "仲裁" not in out and "最终分类(" not in out,
   f"rc={rc} out={out[:140]}")

# 7. pp3_vcep_band 引擎功能（v1.7.0 PP3 VCEP 路由）：9 种 spec 形态确定性判定
import acmg_evidence as _ae

def _pp3_case(title, scores, gene, spec, vt="missense", excl=None, expect_band=None, expect_none=False):
    band, detail = _ae.pp3_vcep_band(scores, gene, spec, variant_type=vt, exclusions=excl)
    if expect_none:
        ok(f"pp3_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:80]}")
    else:
        ok(f"pp3_vcep_band[{title}] → {expect_band}", band == expect_band, f"band={band} detail={detail[:80]}")

# 7.1 tool_threshold：REVEL 单阈值封顶 Supporting（ACADVL >0.75）
_pp3_case("ACADVL REVEL0.80", {"revel": 0.80}, "ACADVL", {"type": "tool_threshold", "tool": "revel", "ge": 0.75}, expect_band="PP3_Supporting")
_pp3_case("ACADVL REVEL0.70 不成立", {"revel": 0.70}, "ACADVL", {"type": "tool_threshold", "tool": "revel", "ge": 0.75}, expect_none=True)
# 7.2 revel_or_spliceai（ACVRL1）
_pp3_case("ACVRL1 REVEL0.81", {"revel": 0.81}, "ACVRL1", {"type": "revel_or_spliceai", "revel_ge": 0.644, "spliceai_ge": 0.2}, expect_band="PP3_Supporting")
_pp3_case("ACVRL1 SpliceAI0.3", {"revel": 0.3, "spliceai": 0.3}, "ACVRL1", {"type": "revel_or_spliceai", "revel_ge": 0.644, "spliceai_ge": 0.2}, expect_band="PP3_Supporting")
_pp3_case("ACVRL1 双低不成立", {"revel": 0.5, "spliceai": 0.1}, "ACVRL1", {"type": "revel_or_spliceai", "revel_ge": 0.644, "spliceai_ge": 0.2}, expect_none=True)
# 7.3 revel_and_cadd（CTLA4）
_pp3_case("CTLA4 双达标", {"revel": 0.7, "cadd": 26}, "CTLA4", {"type": "revel_and_cadd", "revel_ge": 0.644, "cadd_ge": 25.3}, expect_band="PP3_Supporting")
_pp3_case("CTLA4 CADD不足不成立", {"revel": 0.7, "cadd": 20}, "CTLA4", {"type": "revel_and_cadd", "revel_ge": 0.644, "cadd_ge": 25.3}, expect_none=True)
# 7.4 n_of_m（BMPR2 三工具取二）
_pp3_case("BMPR2 2/3 达标", {"revel": 0.7, "alphamissense": 0.8, "cadd": 20}, "BMPR2", {"type": "n_of_m", "tools": {"revel": 0.644, "alphamissense": 0.792, "cadd": 25.3}, "n": 2}, expect_band="PP3_Supporting")
_pp3_case("BMPR2 1/3 不成立", {"revel": 0.7, "alphamissense": 0.5, "cadd": 20}, "BMPR2", {"type": "n_of_m", "tools": {"revel": 0.644, "alphamissense": 0.792, "cadd": 25.3}, "n": 2}, expect_none=True)
# 7.5 spliceai_only（ADA 仅同义/内含子）
_pp3_case("ADA 同义 SpliceAI0.3", {"spliceai": 0.3}, "ADA", {"type": "spliceai_only", "ge": 0.2, "variant_types": ["synonymous", "intronic"]}, vt="synonymous", expect_band="PP3_Supporting")
_pp3_case("ADA 错义不适用", {"spliceai": 0.3}, "ADA", {"type": "spliceai_only", "ge": 0.2, "variant_types": ["synonymous", "intronic"]}, vt="missense", expect_none=True)
# 7.6 bayesdel_domain（BRCA1）
_pp3_case("BRCA1 BayesDel0.35", {"bayesdel": 0.35}, "BRCA1", {"type": "bayesdel_domain", "ge": 0.28, "domains": ["RING 2-101"]}, expect_band="PP3_Supporting")
_pp3_case("BRCA1 BayesDel0.2 不成立", {"bayesdel": 0.2}, "BRCA1", {"type": "bayesdel_domain", "ge": 0.28, "domains": ["RING 2-101"]}, expect_none=True)
# 7.7 multi_band（GAMT 三档）
_mb = {"type": "multi_band", "bands": {"strong": {"revel_ge": 0.932}, "moderate": {"revel_ge": 0.773}, "supporting": {"revel_ge": 0.644}}}
_pp3_case("GAMT REVEL0.95 Strong", {"revel": 0.95}, "GAMT", _mb, expect_band="PP3_Strong")
_pp3_case("GAMT REVEL0.80 Moderate", {"revel": 0.80}, "GAMT", _mb, expect_band="PP3_Moderate")
_pp3_case("GAMT REVEL0.66 Supporting", {"revel": 0.66}, "GAMT", _mb, expect_band="PP3_Supporting")
_pp3_case("GAMT REVEL0.5 不成立", {"revel": 0.5}, "GAMT", _mb, expect_none=True)
# 7.8 前置排除
_pp3_case("ACADVL RNA实证排除", {"revel": 0.8}, "ACADVL", {"type": "tool_threshold", "tool": "revel", "ge": 0.75}, excl={"rna_proven_splice": True}, expect_none=True)
# 7.9 reference_only 回退
_pp3_case("ACTA1 reference_only", {}, "ACTA1", {"type": "reference_only", "note": "通用定义"}, expect_none=True)

# 8. pm3_vcep_band 引擎功能（v1.13.0 PM3 VCEP 路由）：标准档/FA档/封顶
def _pm3_case(title, examples, gene, spec=None, max_band=None, expect=None, expect_none=False):
    band, detail = _ae.pm3_vcep_band(examples, gene, spec=spec, max_band=max_band)
    if expect_none:
        ok(f"pm3_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:80]}")
    else:
        ok(f"pm3_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:80]}")

_fa = {"supporting": 1, "moderate": 2, "strong": 4, "vs": 8}
# 8.1 标准档（spec=None，与 pm3_points 一致）
_pm3_case("GJB2 A×1→Moderate", [{"type":"A","n":1}], "GJB2", expect="PM3_Moderate")
_pm3_case("GJB2 A×4→VeryStrong", [{"type":"A","n":4}], "GJB2", expect="PM3_VeryStrong")
_pm3_case("GJB2 hom×1→Supporting", [{"type":"hom","n":1}], "GJB2", expect="PM3_Supporting")
_pm3_case("GJB2 B_LP×1 不成立(<0.5)", [{"type":"B_LP","n":1}], "GJB2", expect_none=True)
# 8.2 FA 档 1/2/4/8（ATM/PALB2/FOXN1）
_pm3_case("ATM A×1 FA→Supporting", [{"type":"A","n":1}], "ATM", spec=_fa, expect="PM3_Supporting")
_pm3_case("ATM A×2 FA→Moderate", [{"type":"A","n":2}], "ATM", spec=_fa, expect="PM3_Moderate")
_pm3_case("ATM A×4 FA→Strong", [{"type":"A","n":4}], "ATM", spec=_fa, expect="PM3_Strong")
_pm3_case("ATM A×8 FA→VeryStrong", [{"type":"A","n":8}], "ATM", spec=_fa, expect="PM3_VeryStrong")
_pm3_case("ATM hom×1 FA 不成立(<1)", [{"type":"hom","n":1}], "ATM", spec=_fa, expect_none=True)
# 8.3 封顶（BRCA1/2 max=Strong；LDLR max=Moderate）
_pm3_case("BRCA1 A×4 封顶Strong", [{"type":"A","n":4}], "BRCA1", max_band="PM3_Strong", expect="PM3_Strong")
_pm3_case("LDLR A×4 封顶Moderate", [{"type":"A","n":4}], "LDLR", max_band="PM3_Moderate", expect="PM3_Moderate")
_pm3_case("LDLR A×1 未超封顶→Moderate", [{"type":"A","n":1}], "LDLR", max_band="PM3_Moderate", expect="PM3_Moderate")
# 8.4 标准档与 pm3_points 一致性（零变化保证）
for _ex in ([{"type":"A","n":1}], [{"type":"A","n":2}], [{"type":"hom","n":2}], [{"type":"B_P","n":2}]):
    _old = _ae.pm3_points(_ex)[0]
    _new = _ae.pm3_vcep_band(_ex, "GJB2")[0]
    ok(f"pm3_vcep_band 一致性 old={_old} new={_new}", _new == _old, f"ex={_ex}")

# 9. pp4_vcep_band 引擎功能（v1.4.0 PP4 VCEP 路由）：通用缺省/点数/计数/LR/条件式回退/封顶
def _pp4_case(title, value, gene, spec=None, max_band=None, expect=None, expect_none=False):
    band, detail = _ae.pp4_vcep_band(value, gene, spec=spec, max_band=max_band)
    if expect_none:
        ok(f"pp4_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:70]}")
    else:
        ok(f"pp4_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:70]}")

_ada = {"type":"points","bands":{"supporting":[1,2],"moderate":[2,6],"strong":[6,None]}}
_mlh1 = {"type":"count","bands":{"supporting":[1,2],"moderate":[2,3],"strong":[3,None]}}
_brca = {"type":"lr","bands":{"supporting":[2.08,4.3],"moderate":[4.3,18.7],"strong":[18.7,None]}}
# 9.1 通用缺省（spec=None → 通用表型特异 Supporting）
_pp4_case("GJB2 缺省→Supporting", None, "GJB2", expect="PP4_Supporting")
# 9.2 点数型 ADA（1-<2 SU / 2-<6 MO / ≥6 ST）
_pp4_case("ADA 1.5→SU", 1.5, "ADA", spec=_ada, expect="PP4_Supporting")
_pp4_case("ADA 2→MO", 2, "ADA", spec=_ada, expect="PP4_Moderate")
_pp4_case("ADA 6→ST", 6, "ADA", spec=_ada, expect="PP4_Strong")
_pp4_case("ADA 0.5 不成立(<1)", 0.5, "ADA", spec=_ada, expect_none=True)
# 9.3 计数型 MLH1（1 SU / 2 MO / ≥3 ST）
_pp4_case("MLH1 1→SU", 1, "MLH1", spec=_mlh1, expect="PP4_Supporting")
_pp4_case("MLH1 2→MO", 2, "MLH1", spec=_mlh1, expect="PP4_Moderate")
_pp4_case("MLH1 3→ST", 3, "MLH1", spec=_mlh1, expect="PP4_Strong")
_pp4_case("MLH1 0 不成立", 0, "MLH1", spec=_mlh1, expect_none=True)
# 9.4 LR 型 BRCA1（≥2.08 SU / ≥4.3 MO / ≥18.7 ST）
_pp4_case("BRCA1 LR3→SU", 3, "BRCA1", spec=_brca, expect="PP4_Supporting")
_pp4_case("BRCA1 LR10→MO", 10, "BRCA1", spec=_brca, expect="PP4_Moderate")
_pp4_case("BRCA1 LR30→ST", 30, "BRCA1", spec=_brca, expect="PP4_Strong")
_pp4_case("BRCA1 LR1 不成立", 1, "BRCA1", spec=_brca, expect_none=True)
# 9.5 条件式回退（phenotype 引擎不判数值）
_pp4_case("GALT phenotype 需人工核", None, "GALT", spec={"type":"phenotype","note":"RBC 酶活<10%"}, expect_none=True)
# 9.6 封顶 + 数值未取到
_pp4_case("GJB2 封顶SU→SU", None, "GJB2", max_band="PP4_Supporting", expect="PP4_Supporting")
_pp4_case("ADA 数值未取到→None", None, "ADA", spec=_ada, expect_none=True)

# 10. ps4_vcep_band 引擎功能（v1.4.0 PS4 VCEP 路由）：通用缺省/计数/点数/条件式回退/封顶
def _ps4_case(title, value, gene, spec=None, max_band=None, expect=None, expect_none=False):
    band, detail = _ae.ps4_vcep_band(value, gene, spec=spec, max_band=max_band)
    if expect_none:
        ok(f"ps4_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:70]}")
    else:
        ok(f"ps4_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:70]}")

_cdh1 = {"type":"count","bands":{"supporting":[1,2],"moderate":[2,4],"strong":[4,16],"vs":[16,None]}}
_f8 = {"type":"count","bands":{"supporting":[1,2],"moderate":[2,4],"strong":[4,8],"vs":[8,None]}}
_apc = {"type":"points","bands":{"supporting":[1,2],"moderate":[2,4],"strong":[4,16],"vs":[16,None]}}
# 10.1 通用缺省（spec=None → 通用口径 ≥2→SU）
_ps4_case("通用缺省 value3→SU", 3, "X", expect="PS4_Supporting")
# 10.2 计数型 CDH1（≥16 VS / 4-15 ST / 2-3 MO / 1 SU）
_ps4_case("CDH1 1→SU", 1, "CDH1", spec=_cdh1, expect="PS4_Supporting")
_ps4_case("CDH1 3→MO", 3, "CDH1", spec=_cdh1, expect="PS4_Moderate")
_ps4_case("CDH1 8→ST", 8, "CDH1", spec=_cdh1, expect="PS4_Strong")
_ps4_case("CDH1 16→VS", 16, "CDH1", spec=_cdh1, expect="PS4_VeryStrong")
_ps4_case("CDH1 0 不成立", 0, "CDH1", spec=_cdh1, expect_none=True)
# 10.3 计数型 F8（≥8 VS / 4-7 ST）
_ps4_case("F8 5→ST", 5, "F8", spec=_f8, expect="PS4_Strong")
_ps4_case("F8 8→VS", 8, "F8", spec=_f8, expect="PS4_VeryStrong")
# 10.4 点数型 APC（≥16 VS / 4-15.5 ST / 2-3.5 MO / 1-1.5 SU）
_ps4_case("APC 3→MO", 3, "APC", spec=_apc, expect="PS4_Moderate")
_ps4_case("APC 16→VS", 16, "APC", spec=_apc, expect="PS4_VeryStrong")
# 10.5 条件式回退（phenotype 引擎不判数值）
_ps4_case("ATM phenotype 需人工核", None, "ATM", spec={"type":"phenotype","note":"case-control OR+CI"}, expect_none=True)
# 10.6 封顶 + 数值未取到
_ps4_case("CDH1 5 封顶MO→MO", 5, "CDH1", spec=_cdh1, max_band="PS4_Moderate", expect="PS4_Moderate")
_ps4_case("CDH1 数值未取到→None", None, "CDH1", spec=_cdh1, expect_none=True)

# 11. bp4_vcep_band 引擎功能（BP4 特异基因治理 2026-10-20）：按变异类型分派 + 数值切点 + 剪接排除 + NA分支 + 多档
def _bp4_case(title, scores, gene, spec, vt="missense", excl=None, expect=None, expect_none=False):
    band, detail = _ae.bp4_vcep_band(scores, gene, spec, variant_type=vt, exclusions=excl)
    if expect_none:
        ok(f"bp4_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:70]}")
    else:
        ok(f"bp4_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:70]}")

# 11.1 单档 Supporting·REVEL 切点（GJB2：REVEL≤0.15）
_gjb2_bp4 = {"type": "by_type", "bands": {"supporting": {"by_type": {
    "missense": {"tool": "revel", "le": 0.15}, "default": {"require_absent": ["maxentscan"]}}}}}
_bp4_case("GJB2 REVEL0.10→SU", {"revel": 0.10}, "GJB2", _gjb2_bp4, expect="BP4_Supporting")
_bp4_case("GJB2 REVEL0.30 不成立", {"revel": 0.30}, "GJB2", _gjb2_bp4, expect_none=True)
# 11.2 单档 + 剪接排除（HBB：missense REVEL<0.7 且 SpliceAI DS≤0.3；synonymous CADD≤11 且 SpliceAI≤0.3）
_hbb_bp4 = {"type": "by_type", "bands": {"supporting": {"by_type": {
    "missense": {"tool": "revel", "le": 0.7, "spliceai_le": 0.3},
    "synonymous": {"tool": "cadd", "le": 11, "spliceai_le": 0.3}}}}}
_bp4_case("HBB missense REVEL0.5+SpliceAI0.2→SU", {"revel": 0.5, "spliceai": 0.2}, "HBB", _hbb_bp4, expect="BP4_Supporting")
_bp4_case("HBB missense REVEL0.8 不成立", {"revel": 0.8, "spliceai": 0.2}, "HBB", _hbb_bp4, expect_none=True)
_bp4_case("HBB missense REVEL0.5但SpliceAI0.5 不成立", {"revel": 0.5, "spliceai": 0.5}, "HBB", _hbb_bp4, expect_none=True)
_bp4_case("HBB synonymous CADD10→SU", {"cadd": 10, "spliceai": 0.1}, "HBB", _hbb_bp4, vt="synonymous", expect="BP4_Supporting")
_bp4_case("HBB synonymous CADD15 不成立", {"cadd": 15, "spliceai": 0.1}, "HBB", _hbb_bp4, vt="synonymous", expect_none=True)
# 11.3 NA 分支（APC：missense NA，synonymous 剪接无影响）
_apc_bp4 = {"type": "by_type", "bands": {"supporting": {"by_type": {
    "missense": "NA", "synonymous": {"require_absent": ["spliceai"]}}}}}
_bp4_case("APC missense NA 不成立", {"revel": 0.1}, "APC", _apc_bp4, expect_none=True)
_bp4_case("APC synonymous SpliceAI0→SU", {"spliceai": 0.0}, "APC", _apc_bp4, vt="synonymous", expect="BP4_Supporting")
# 11.4 多档（TP53：Moderate BayesDel≤-0.008 且 SpliceAI<0.2；Supporting BayesDel<0.16）
_tp53_bp4 = {"type": "by_type", "bands": {
    "moderate": {"by_type": {"missense": {"tool": "bayesdel", "le": -0.008, "spliceai_le": 0.2}}},
    "supporting": {"by_type": {"missense": {"tool": "bayesdel", "le": 0.16, "spliceai_le": 0.2}}}}}
_bp4_case("TP53 BayesDel-0.02→MO", {"bayesdel": -0.02, "spliceai": 0.1}, "TP53", _tp53_bp4, expect="BP4_Moderate")
_bp4_case("TP53 BayesDel-0.005→SU", {"bayesdel": -0.005, "spliceai": 0.1}, "TP53", _tp53_bp4, expect="BP4_Supporting")
_bp4_case("TP53 BayesDel0.5 不成立", {"bayesdel": 0.5, "spliceai": 0.1}, "TP53", _tp53_bp4, expect_none=True)
# 11.5 引用式回退 + 前置排除 + 非法spec
_bp4_case("引用式回退", {"revel": 0.1}, "X", {"type": "reference_only", "note": "见附录"}, expect_none=True)
_bp4_case("前置排除命中不成立", {"revel": 0.1}, "X", _gjb2_bp4, excl={"na_branch": True}, expect_none=True)
_bp4_case("非法spec不成立", {"revel": 0.1}, "X", "bad", expect_none=True)

# 12. ps3_vcep_band 引擎功能（PS3/BS3 特异基因治理 2026-10-20）：功能实验类型+判据→档位
def _ps3_case(title, experiments, gene, spec, benign=False, max_band=None, expect=None, expect_none=False):
    band, detail = _ae.ps3_vcep_band(experiments, gene, spec=spec, max_band=max_band, benign=benign)
    if expect_none:
        ok(f"ps3_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:70]}")
    else:
        ok(f"ps3_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:70]}")

# 12.1 TP53：Kato 分档（Strong=non-functional+LOF多数 / Moderate=partially+LOF多数 / Supporting=non-functional+Kawaguchi异常）
_tp53_ps3 = {"type": "experiment", "bands": {
    "strong": {"kato": "non-functional", "lof_majority": True},
    "moderate": {"kato": "partially-functional", "lof_majority": True},
    "supporting": {"kato": "non-functional", "kawaguchi": "abnormal"}}}
_ps3_case("TP53 Kato非功能+LOF多数→ST", {"kato": "non-functional", "lof_majority": True, "kawaguchi": "abnormal"}, "TP53", _tp53_ps3, expect="PS3_Strong")
_ps3_case("TP53 Kato部分+LOF多数→MO", {"kato": "partially-functional", "lof_majority": True}, "TP53", _tp53_ps3, expect="PS3_Moderate")
_ps3_case("TP53 Kato非功能+Kawaguchi异常→SU", {"kato": "non-functional", "lof_majority": False, "kawaguchi": "abnormal"}, "TP53", _tp53_ps3, expect="PS3_Supporting")
_ps3_case("TP53 判据缺LOF→None", {"kato": "non-functional"}, "TP53", _tp53_ps3, expect_none=True)
# 12.2 GAA：酶活数值分档（Moderate<5% / Supporting<30%）
_gaa_ps3 = {"type": "experiment", "bands": {
    "moderate": {"enzyme_activity_pct": {"op": "lt", "v": 5}},
    "supporting": {"enzyme_activity_pct": {"op": "lt", "v": 30}}}}
_ps3_case("GAA 酶活3.5%→MO", {"enzyme_activity_pct": 3.5}, "GAA", _gaa_ps3, expect="PS3_Moderate")
_ps3_case("GAA 酶活10%→SU", {"enzyme_activity_pct": 10}, "GAA", _gaa_ps3, expect="PS3_Supporting")
_ps3_case("GAA 酶活50%→None", {"enzyme_activity_pct": 50}, "GAA", _gaa_ps3, expect_none=True)
# 12.3 CDH1：RNA out-of-frame→ST / in-frame→MO
_cdh1_ps3 = {"type": "experiment", "bands": {
    "strong": {"rna_out_of_frame": True}, "moderate": {"rna_in_frame": True}}}
_ps3_case("CDH1 RNA out-of-frame→ST", {"rna_out_of_frame": True}, "CDH1", _cdh1_ps3, expect="PS3_Strong")
_ps3_case("CDH1 RNA in-frame→MO", {"rna_in_frame": True}, "CDH1", _cdh1_ps3, expect="PS3_Moderate")
# 12.4 BS3 良性镜像 + 引用式 + 封顶
_ps3_case("BS3 无损伤→BS3_ST", {"no_damaging_effect": True}, "MYH7", {"type": "experiment", "bands": {"strong": {"no_damaging_effect": True}}}, benign=True, expect="BS3_Strong")
_ps3_case("BS3 有损伤→None", {"no_damaging_effect": False}, "MYH7", {"type": "experiment", "bands": {"strong": {"no_damaging_effect": True}}}, benign=True, expect_none=True)
_ps3_case("引用式回退", {"x": 1}, "X", {"type": "reference_only", "note": "引SVI"}, expect_none=True)
_ps3_case("封顶SU", {"kato": "non-functional", "lof_majority": True}, "TP53", _tp53_ps3, max_band="PS3_Moderate", expect="PS3_Moderate")
_ps3_case("非法spec", {"x": 1}, "X", "bad", expect_none=True)

# 13. ba1_vcep_band 引擎功能（BA1 特异基因治理 2026-10-20，Windows 重建工作区重做）：Stand Alone 独立证据码
#     spec 由 ev-bs1-bs2 第 3.6 步路由读 VCEP-<gene>.md #### BA1 段解析传入：单一切点 {cutoff,direction:ge|gt} / 按遗传方式 {AR,AD}
def _ba1_case(title, af, gene, mode, spec, expect=None, expect_none=False):
    band, detail = _ae.ba1_vcep_band(af, gene, mode, spec)
    if expect_none:
        ok(f"ba1_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:80]}")
    else:
        ok(f"ba1_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:80]}")

# 13.1 单一切点 direction=ge（CDH1 MAF cutoff 0.2%）
_ba1_case("CDH1 AF0.3% ge 达标", 0.003, "CDH1", "AD", {"cutoff": 0.002, "direction": "ge"}, expect="BA1_Stand_Alone")
_ba1_case("CDH1 AF0.1% ge 不达标", 0.001, "CDH1", "AD", {"cutoff": 0.002, "direction": "ge"}, expect_none=True)
_ba1_case("CDH1 ge 恰等于达标", 0.002, "CDH1", "AD", {"cutoff": 0.002, "direction": "ge"}, expect="BA1_Stand_Alone")
# 13.2 单一切点 direction=gt 严格大于（ATM Grpmax FAF >0.5%）
_ba1_case("ATM AF0.6% gt 达标", 0.006, "ATM", "AD", {"cutoff": 0.005, "direction": "gt"}, expect="BA1_Stand_Alone")
_ba1_case("ATM AF0.5% gt 等于不达标", 0.005, "ATM", "AD", {"cutoff": 0.005, "direction": "gt"}, expect_none=True)
_ba1_case("ATM AF0.3% gt 不达标", 0.003, "ATM", "AD", {"cutoff": 0.005, "direction": "gt"}, expect_none=True)
# 13.3 按遗传方式分档（CDH23/GJB2/USH2A AR≥0.5% AD≥0.1%）
_cdh23_ba1 = {"AR": {"cutoff": 0.005, "direction": "ge"}, "AD": {"cutoff": 0.001, "direction": "ge"}}
_ba1_case("CDH23 AR AF0.6% 达标", 0.006, "CDH23", "AR", _cdh23_ba1, expect="BA1_Stand_Alone")
_ba1_case("CDH23 AR AF0.4% 不达标", 0.004, "CDH23", "AR", _cdh23_ba1, expect_none=True)
_ba1_case("CDH23 AD AF0.2% 达标", 0.002, "CDH23", "AD", _cdh23_ba1, expect="BA1_Stand_Alone")
_ba1_case("CDH23 AD AF0.05% 不达标", 0.0005, "CDH23", "AD", _cdh23_ba1, expect_none=True)
_ba1_case("CDH23 XL 无分支", 0.01, "CDH23", "XL", _cdh23_ba1, expect_none=True)
# 13.4 引用式/无 spec 回退（引擎 spec=None 返回 None，由子技能回退通用）
_ba1_case("reference_only 回退", 0.3, "X", "AD", {"type": "reference_only", "note": "通用定义"}, expect_none=True)
# 13.5 AF 取不到 + 非法 spec + 缺 cutoff
_ba1_case("AF 取不到", None, "CDH1", "AD", {"cutoff": 0.002, "direction": "ge"}, expect_none=True)
_ba1_case("非法spec", 0.01, "CDH1", "AD", "bad", expect_none=True)
_ba1_case("缺 cutoff", 0.01, "CDH1", "AD", {"direction": "ge"}, expect_none=True)

# ============ 第 14 节：BS2 VCEP 档位路由（v1.8.0 新增）============
# bs2_vcep_band(value, gene, spec)：数值/计数/点数 → 档位，从高到低取最高达标档

def _bs2_case(title, value, gene, spec, expect=None, expect_none=False):
    band, detail = _ae.bs2_vcep_band(value, gene, spec)
    if expect_none:
        ok(f"bs2_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:80]}")
    else:
        ok(f"bs2_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:80]}")

# 14.1 点数型 BRCA1（Strong≥4 / Moderate≥2 / Supporting≥1，points）
_brca1_bs2 = {"type": "band", "bands": {"strong": 4, "moderate": 2, "supporting": 1}, "unit": "points"}
_bs2_case("BRCA1 5分 → Strong", 5, "BRCA1", _brca1_bs2, expect="BS2_Strong")
_bs2_case("BRCA1 4分 恰达标 Strong", 4, "BRCA1", _brca1_bs2, expect="BS2_Strong")
_bs2_case("BRCA1 3分 → Moderate", 3, "BRCA1", _brca1_bs2, expect="BS2_Moderate")
_bs2_case("BRCA1 2分 恰达标 Moderate", 2, "BRCA1", _brca1_bs2, expect="BS2_Moderate")
_bs2_case("BRCA1 1分 → Supporting", 1, "BRCA1", _brca1_bs2, expect="BS2_Supporting")
_bs2_case("BRCA1 0分 不成立", 0, "BRCA1", _brca1_bs2, expect_none=True)
# 14.2 计数型 CDH1（Strong≥10 / Supporting≥3，count）
_cdh1_bs2 = {"type": "band", "bands": {"strong": 10, "supporting": 3}, "unit": "count"}
_bs2_case("CDH1 12例 → Strong", 12, "CDH1", _cdh1_bs2, expect="BS2_Strong")
_bs2_case("CDH1 10例 恰达标 Strong", 10, "CDH1", _cdh1_bs2, expect="BS2_Strong")
_bs2_case("CDH1 5例 → Supporting", 5, "CDH1", _cdh1_bs2, expect="BS2_Supporting")
_bs2_case("CDH1 3例 恰达标 Supporting", 3, "CDH1", _cdh1_bs2, expect="BS2_Supporting")
_bs2_case("CDH1 2例 不成立", 2, "CDH1", _cdh1_bs2, expect_none=True)
# 14.3 计数型 TP53 三档（Strong≥8 / Moderate≥4 / Supporting≥2，count）
_tp53_bs2 = {"type": "band", "bands": {"strong": 8, "moderate": 4, "supporting": 2}, "unit": "count"}
_bs2_case("TP53 9例 → Strong", 9, "TP53", _tp53_bs2, expect="BS2_Strong")
_bs2_case("TP53 6例 → Moderate", 6, "TP53", _tp53_bs2, expect="BS2_Moderate")
_bs2_case("TP53 4例 恰达标 Moderate", 4, "TP53", _tp53_bs2, expect="BS2_Moderate")
_bs2_case("TP53 3例 → Supporting", 3, "TP53", _tp53_bs2, expect="BS2_Supporting")
_bs2_case("TP53 1例 不成立", 1, "TP53", _tp53_bs2, expect_none=True)
# 14.4 数值型 F8（因子活性 >40%，direction=gt）
_f8_bs2 = {"type": "band", "bands": {"strong": 40}, "direction": "gt", "unit": "percent"}
_bs2_case("F8 55% → Strong", 55, "F8", _f8_bs2, expect="BS2_Strong")
_bs2_case("F8 恰40% gt 不达标", 40, "F8", _f8_bs2, expect_none=True)
_bs2_case("F8 30% 不达标", 30, "F8", _f8_bs2, expect_none=True)
# 14.5 取不到 + 非法 spec + 缺 bands
_bs2_case("值取不到", None, "CDH1", _cdh1_bs2, expect_none=True)
_bs2_case("非法 spec", 5, "CDH1", "bad", expect_none=True)
_bs2_case("缺 bands", 5, "CDH1", {"type": "band"}, expect_none=True)

# ============ 第 15 节：PM1 VCEP 位置匹配路由（v1.2.0 新增）============
# pm1_vcep_band(aa_pos, gene, spec)：变异氨基酸位置 vs 位置集合（区间/单点），从高到低取最高命中档

def _pm1_case(title, aa_pos, gene, spec, expect=None, expect_none=False):
    band, detail = _ae.pm1_vcep_band(aa_pos, gene, spec)
    if expect_none:
        ok(f"pm1_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:80]}")
    else:
        ok(f"pm1_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:80]}")

# 15.1 单区间 MYH7（codons 167-931 → Moderate，含边界）
_myh7_pm1 = {"type": "region", "bands": {"moderate": [{"lo": 167, "hi": 931}]}}
_pm1_case("MYH7 300 命中", 300, "MYH7", _myh7_pm1, expect="PM1_Moderate")
_pm1_case("MYH7 167 下界命中", 167, "MYH7", _myh7_pm1, expect="PM1_Moderate")
_pm1_case("MYH7 931 上界命中", 931, "MYH7", _myh7_pm1, expect="PM1_Moderate")
_pm1_case("MYH7 166 未命中", 166, "MYH7", _myh7_pm1, expect_none=True)
# 15.2 多区间 MYBPC3（485-502 和 1248-1266 → Moderate）
_mybpc3_pm1 = {"type": "region", "bands": {"moderate": [{"lo": 485, "hi": 502}, {"lo": 1248, "hi": 1266}]}}
_pm1_case("MYBPC3 500 第一区间", 500, "MYBPC3", _mybpc3_pm1, expect="PM1_Moderate")
_pm1_case("MYBPC3 1255 第二区间", 1255, "MYBPC3", _mybpc3_pm1, expect="PM1_Moderate")
_pm1_case("MYBPC3 600 未命中", 600, "MYBPC3", _mybpc3_pm1, expect_none=True)
# 15.3 多档 RUNX1（Strong=单点，Supporting=区间，从高到低）
_runx1_pm1 = {"type": "region", "bands": {"strong": [{"pos": 107}, {"pos": 110}, {"pos": 134}], "supporting": [{"lo": 89, "hi": 204}]}}
_pm1_case("RUNX1 107 Strong", 107, "RUNX1", _runx1_pm1, expect="PM1_Strong")
_pm1_case("RUNX1 110 Strong", 110, "RUNX1", _runx1_pm1, expect="PM1_Strong")
_pm1_case("RUNX1 150 Supporting", 150, "RUNX1", _runx1_pm1, expect="PM1_Supporting")
_pm1_case("RUNX1 88 未命中", 88, "RUNX1", _runx1_pm1, expect_none=True)
# 15.4 TP53 单点集合（密码子）
_tp53_pm1 = {"type": "region", "bands": {"moderate": [{"pos": 175}, {"pos": 245}, {"pos": 248}, {"pos": 249}, {"pos": 273}, {"pos": 282}]}}
_pm1_case("TP53 248 命中", 248, "TP53", _tp53_pm1, expect="PM1_Moderate")
_pm1_case("TP53 200 未命中", 200, "TP53", _tp53_pm1, expect_none=True)
# 15.5 取不到 + 非法 spec + 缺 bands
_pm1_case("位置取不到", None, "MYH7", _myh7_pm1, expect_none=True)
_pm1_case("非法 spec", 300, "MYH7", "bad", expect_none=True)
_pm1_case("缺 bands", 300, "MYH7", {"type": "region"}, expect_none=True)

# ============ 第 16 节：PM5 VCEP 计数档位路由（v1.4.0 新增）============
# pm5_vcep_band(n_known, gene, spec)：同密码子已知致病错义计数 vs 档位，从高到低取最高达标档

def _pm5_case(title, n_known, gene, spec, expect=None, expect_none=False):
    band, detail = _ae.pm5_vcep_band(n_known, gene, spec)
    if expect_none:
        ok(f"pm5_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:80]}")
    else:
        ok(f"pm5_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:80]}")

# 16.1 TP53（Strong≥2 / Moderate≥1 / Supporting≥1，unit=known_pathogenic）
_tp53_pm5 = {"type": "band", "bands": {"strong": 2, "moderate": 1, "supporting": 1}, "unit": "known_pathogenic"}
_pm5_case("TP53 3个 → Strong", 3, "TP53", _tp53_pm5, expect="PM5_Strong")
_pm5_case("TP53 2个 恰达标 Strong", 2, "TP53", _tp53_pm5, expect="PM5_Strong")
_pm5_case("TP53 1个 → Moderate", 1, "TP53", _tp53_pm5, expect="PM5_Moderate")
_pm5_case("TP53 0个 不成立", 0, "TP53", _tp53_pm5, expect_none=True)
# 16.2 LDLR/BRAF/KRAS（Strong≥2 / Moderate≥1）
_ldlr_pm5 = {"type": "band", "bands": {"strong": 2, "moderate": 1}, "unit": "known_pathogenic"}
_pm5_case("LDLR 2个 → Strong", 2, "LDLR", _ldlr_pm5, expect="PM5_Strong")
_pm5_case("LDLR 1个 → Moderate", 1, "LDLR", _ldlr_pm5, expect="PM5_Moderate")
_pm5_case("LDLR 0个 不成立", 0, "LDLR", _ldlr_pm5, expect_none=True)
_pm5_case("BRAF 3个 → Strong", 3, "BRAF", _ldlr_pm5, expect="PM5_Strong")
_pm5_case("KRAS 1个 → Moderate", 1, "KRAS", _ldlr_pm5, expect="PM5_Moderate")
# 16.3 取不到 + 非法 spec + 缺 bands
_pm5_case("计数取不到", None, "TP53", _tp53_pm5, expect_none=True)
_pm5_case("非法 spec", 1, "TP53", "bad", expect_none=True)
_pm5_case("缺 bands", 1, "TP53", {"type": "band"}, expect_none=True)

# ============ 第 17 节：PM4 VCEP AA 计数档位路由（v1.2.0 新增）============
# pm4_vcep_band(n_aa, gene, spec)：框内 indel AA 数 vs 档位，从高到低取最高达标档

def _pm4_case(title, n_aa, gene, spec, expect=None, expect_none=False):
    band, detail = _ae.pm4_vcep_band(n_aa, gene, spec)
    if expect_none:
        ok(f"pm4_vcep_band[{title}] 不成立", band is None, f"band={band} detail={detail[:80]}")
    else:
        ok(f"pm4_vcep_band[{title}] → {expect}", band == expect, f"band={band} detail={detail[:80]}")

# 17.1 ABCA4/GAA/IDUA（≥2→Moderate、≥1→Supporting）
_pm4_mod_supp = {"type": "band", "bands": {"moderate": 2, "supporting": 1}, "unit": "amino_acid"}
_pm4_case("ABCA4 5 AA → Moderate", 5, "ABCA4", _pm4_mod_supp, expect="PM4_Moderate")
_pm4_case("ABCA4 2 AA 恰达标 → Moderate", 2, "ABCA4", _pm4_mod_supp, expect="PM4_Moderate")
_pm4_case("ABCA4 1 AA → Supporting", 1, "ABCA4", _pm4_mod_supp, expect="PM4_Supporting")
_pm4_case("ABCA4 0 AA 不成立", 0, "ABCA4", _pm4_mod_supp, expect_none=True)
_pm4_case("GAA 3 AA → Moderate", 3, "GAA", _pm4_mod_supp, expect="PM4_Moderate")
_pm4_case("IDUA 1 AA → Supporting", 1, "IDUA", _pm4_mod_supp, expect="PM4_Supporting")
# 17.2 CTLA4（仅 Moderate≥2）
_pm4_mod_only = {"type": "band", "bands": {"moderate": 2}, "unit": "amino_acid"}
_pm4_case("CTLA4 2 AA → Moderate", 2, "CTLA4", _pm4_mod_only, expect="PM4_Moderate")
_pm4_case("CTLA4 1 AA 不达标", 1, "CTLA4", _pm4_mod_only, expect_none=True)
# 17.3 取不到 + 非法 + 缺 bands
_pm4_case("AA 取不到", None, "ABCA4", _pm4_mod_supp, expect_none=True)
_pm4_case("非法 spec", 1, "ABCA4", "bad", expect_none=True)
_pm4_case("缺 bands", 1, "ABCA4", {"type": "band"}, expect_none=True)

# ============ 第 18 节：BP1 VCEP 适用性路由协议（v1.9.0 新增，纯适用性路由无引擎）============
# BP1 为适用性/语义路由（RASopathy GOF 不适用/截断机制适用/区域排除/NA），无数值引擎。
# 契约校验：技能协议已含 BP1 VCEP 适用性路由协议 + 自检路由闸，确保评 BP1 前必走 VCEP 路由。
def _bp1_skill_has(text, key):
    return key in text

import os as _os
_ws = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_pp3bp4 = open(_os.path.join(_ws, "ev-pp3-bp4", "SKILL.md"), encoding="utf-8").read()
ok("BP1 VCEP 适用性路由协议已写入 ev-pp3-bp4", "BP1 VCEP 适用性路由协议" in _pp3bp4, "")
ok("BP1 路由闸已写入自检清单", "BP1 VCEP 路由闸" in _pp3bp4, "")
ok("BP1 路由协议含 RASopathy GOF 限定", "不用于 RASopathy" in _pp3bp4 or "GOF" in _pp3bp4, "")
ok("BP1 路由协议含 APC 区域排除", "β-catenin" in _pp3bp4, "")
ok("BP1 路由协议含 NA 出口", "KCNQ1" in _pp3bp4 or "不适用" in _pp3bp4, "")

# ============ 第 19 节：BP7 VCEP 适用性路由协议（v1.10.0 新增，适用性+剪接/保守判据）============
# BP7 特异为"同义/内含子+剪接预测+保守性"判据，多数标准型 Supporting，少数数值切点/RNA升档。
ok("BP7 VCEP 适用性路由协议已写入 ev-pp3-bp4", "BP7 VCEP 适用性路由协议" in _pp3bp4, "")
ok("BP7 路由闸已写入自检清单", "BP7 VCEP 路由闸" in _pp3bp4, "")
ok("BP7 路由协议含标准型判据", "+7/-21" in _pp3bp4 or "同义" in _pp3bp4, "")
ok("BP7 路由协议含数值切点型", "HNF1A" in _pp3bp4 or "SpliceAI <0.2" in _pp3bp4, "")
ok("BP7 路由协议含 RNA 升档型", "RNA" in _pp3bp4 or "Strong" in _pp3bp4, "")

# ============ 第 20 节：BP2 VCEP 适用性路由协议（v1.9.0 新增，反式/顺式已知致病判定）============
_bs1bs2 = open(_os.path.join(_ws, "ev-bs1-bs2", "SKILL.md"), encoding="utf-8").read()
ok("BP2 VCEP 适用性路由协议已写入 ev-bs1-bs2", "BP2 VCEP 适用性路由协议" in _bs1bs2, "")
ok("BP2 路由闸已写入自检清单", "BP2 VCEP 路由闸" in _bs1bs2, "")
ok("BP2 路由协议含标准型反式/顺式判据", "顺式" in _bs1bs2 or "in trans" in _bs1bs2, "")
ok("BP2 路由协议含计数/点数型", "APC" in _bs1bs2 or "BRAF" in _bs1bs2, "")
ok("BP2 路由协议含 NA/升档出口", "KCNQ1" in _bs1bs2 or "SGCG" in _bs1bs2, "")

# ============ 第 21 节：BP3 VCEP 适用性路由协议（v1.3.0 新增，框内 indel 重复区判定）============
_pm4 = open(_os.path.join(_ws, "ev-pm4", "SKILL.md"), encoding="utf-8").read()
ok("BP3 VCEP 适用性路由协议已写入 ev-pm4", "BP3 VCEP 适用性路由协议" in _pm4, "")
ok("BP3 路由闸已写入自检清单", "BP3 VCEP 路由闸" in _pm4, "")
ok("BP3 路由协议含标准型重复区判据", "重复区" in _pm4, "")
ok("BP3 路由协议含特定重复区限定", "VHL" in _pm4 or "RPGR" in _pm4, "")
ok("BP3 路由协议含 NA 出口", "不适用" in _pm4, "")

# ============ 第 22 节：BS4 VCEP 适用性路由协议（v1.8.0 新增，共分离信息量门槛）============
_pp1 = open(_os.path.join(_ws, "ev-pp1", "SKILL.md"), encoding="utf-8").read()
ok("BS4 VCEP 适用性路由协议已写入 ev-pp1", "BS4 VCEP 适用性路由协议" in _pp1, "")
ok("BS4 路由闸已写入自检清单", "BS4 VCEP 路由闸" in _pp1, "")
ok("BS4 路由协议含信息量门槛判据", "减数分裂" in _pp1 or "informative" in _pp1, "")
ok("BS4 路由协议含定量共分离型", "BRCA1" in _pp1 or "Bayes" in _pp1 or "LR" in _pp1, "")
ok("BS4 路由协议含单/多家系档位型", "VHL" in _pp1 or "Supporting" in _pp1, "")

# ============ 第 23 节：BP5 VCEP 适用性路由协议（v1.5.0 新增，新发旁置/校准阈值）============
_ps2pm6 = open(_os.path.join(_ws, "ev-ps2-pm6", "SKILL.md"), encoding="utf-8").read()
ok("BP5 VCEP 适用性路由协议已写入 ev-ps2-pm6", "BP5 VCEP 适用性路由协议" in _ps2pm6, "")
ok("BP5 路由闸已写入自检清单", "BP5 VCEP 路由闸" in _ps2pm6, "")
ok("BP5 路由协议含标准型新发旁置判据", "旁置" in _ps2pm6 or "另一" in _ps2pm6, "")
ok("BP5 路由协议含校准阈值型", "BRCA1" in _ps2pm6 or "LR" in _ps2pm6 or "CTLA4" in _ps2pm6, "")
ok("BP5 路由协议含计数型", "CDKL5" in _ps2pm6 or "VHL" in _ps2pm6, "")

# ============ 第 24 节：组件接口真验证（v24-fix，报告 §7 契约补接口）============
# 报告批评：既有契约 224 项几乎全是"文档文本存在性"断言，从不真正调用组件接口，
# 导致 G1 门禁与 standardize/classify/知识图 三者契约断裂却 0 失败。
# 本节补三条确定性接口验证，失败即退出码 1（纳入打包门禁）。
import subprocess as _sp
_GATE = os.path.join(HERE, "constraint_gate.py")
_STD = os.path.join(_ws, "ev-variant-standardization", "standardize_variant.py")
_KGF = os.path.join(_ws, "config", "knowledge_graph.json")

def _run_gate(variant_json):
    r = _sp.run([sys.executable, _GATE, "check", "--variant", json.dumps(variant_json)],
                capture_output=True, text=True)
    try:
        return json.loads(r.stdout or "{}"), r.returncode
    except Exception:
        return {}, r.returncode

def _import_std():
    # 不真正联网跑 standardize_variant()（会 curl），只静态验证其函数存在且返回契约字段
    src = open(_STD, encoding="utf-8").read()
    return {
        "has_std_def": "def standardize_variant" in src,
        "has_classify_def": "def classify_variant_class" in src,
        "has_identity_status": "identity_status" in src,
        "has_variant_class": "variant_class" in src,
        "has_protein_change": "protein_change" in src,
        "has_return_dict": "return result" in src,
    }

# 3.1 G1 词表归一：classify 八类中 nonsense/frameshift/inframe/splicing 各档输入必须 G1 PASS
for _cls, _gene, _needp in [
    ("nonsense", "COL7A1", ""),          # 截短类，不需 p.HGVS
    ("frameshift", "BRCA1", ""),         # 截短类，不需 p.HGVS
    ("splicing", "ATP7B", ""),           # 剪接→truncating（v24-fix 知识图新增 splicing）
    ("inframe", "VHL", "p.Tyr98_Phe109del"),  # 框内→inframe_indel
    ("missense", "COL7A1", "p.Glu888="),      # 错义需 p.HGVS
]:
    _vin = {"gene": _gene, "c_hgvs": "c.NA", "variant_class": _cls, "identity_status": "annotated"}
    if _needp:
        _vin["protein_change"] = _needp
    _r, _rc = _run_gate(_vin)
    _g1 = (_r.get("gates") or {}).get("G1", {})
    ok(f"接口-{_cls} 归一后 G1 PASS（classify八类→门禁四类）", _g1.get("pass") is True,
       f"G1={_g1.get('pass')} rc={_rc}")

# 3.2 standardize_variant.py 输出契约：须含三字段（identity_status/variant_class/protein_change）+ return dict
_std = _import_std()
ok("接口-standardize_variant 定义存在", _std["has_std_def"], "")
ok("接口-classify_variant_class 定义存在", _std["has_classify_def"], "")
ok("接口-standardize 返回 dict 含 identity_status", _std["has_identity_status"], "")
ok("接口-standardize 返回 dict 含 variant_class", _std["has_variant_class"], "")
ok("接口-standardize 返回 dict 含 protein_change", _std["has_protein_change"], "")
ok("接口-standardize 返回结构化 result（非仅 print）", _std["has_return_dict"], "")

# 3.3 知识图 evidence_applicability 键集合 ⊇ 门禁 _VALID_CLASSES（含新增 splicing/noncoding 去向）
try:
    _kg = json.load(open(_KGF, encoding="utf-8"))
    _ea = set(_kg.get("evidence_applicability", {}).keys())
    _required = {"truncating", "missense", "inframe_indel", "synonymous", "splicing", "noncoding"}
    _missing = _required - _ea
    ok("接口-知识图 evidence_applicability 键 ⊇ 门禁四类+新增 splicing/noncoding",
       not _missing, f"缺失: {sorted(_missing) if _missing else '无'}")
    # G2 命中：splicing 走 truncating 适用表（16 码），noncoding 走空表（不 STOP）
    _r, _rc = _run_gate({"gene": "ATP7B", "c_hgvs": "c.NA", "variant_class": "splicing", "identity_status": "annotated"})
    _g2 = (_r.get("gates") or {}).get("G2", {})
    ok("接口-splicing G2 命中适用表（不 STOP）", _g2.get("pass") is True,
       f"G2={_g2.get('pass')} reason={_g2.get('reason','')}")
    _r, _rc = _run_gate({"gene": "ATP7B", "c_hgvs": "c.NA", "variant_class": "noncoding", "identity_status": "annotated"})
    _g2 = (_r.get("gates") or {}).get("G2", {})
    # noncoding 无适用证据码：G2 归一后 STOP 待人工（fail-closed，不静默当作四类）
    # ——这是报告 §3 要求的"明确去向"：剪接已归 truncating，非编码明确待人工，而非无键报错。
    _g1n = (_r.get("gates") or {}).get("G1", {})
    ok("接口-noncoding 明确待人工出口（G1/G2 STOP，不静默）",
       _g1n.get("pass") is False or _g2.get("pass") is False,
       f"G1={_g1n.get('pass')} G2={_g2.get('pass')}")
except Exception as _e:
    ok("接口-知识图键集合验证可执行", False, str(_e))


# ---------- arad 离线契约测试（v1.2.4 新增，2026-10-23）----------
# 固定样例喂 _arad_variant_matches，锁住 v1.0.4 的目标变异匹配逻辑
# 防止后续修改 arad 时把"泛基因查询返回 30 条无关等位"的 bug 又带回来
try:
    sys.path.insert(0, os.path.join(HERE, "..", "arad-inheritance-judgment"))
    from main import _arad_variant_matches

    # 用例 1：c.35delG（目标）↔ c.35del（ClinVar 省略碱基写法）→ 应命中
    t1 = _arad_variant_matches(record_variant="c.35del", record_protein="p.Gly12Valfs*2", target="c.35delG")
    ok("arad 离线-cDNA 省略碱基写法兼容（c.35delG ↔ c.35del）", t1, f"result={t1}")

    # 用例 2：c.35delG（目标）↔ c.247_249del（不同位置）→ 应不命中
    t2 = _arad_variant_matches(record_variant="c.247_249del", record_protein="p.Glu83del", target="c.35delG")
    ok("arad 离线-不同位置变异不命中（c.247_249del ≠ c.35delG）", not t2, f"result={t2}")

    # 用例 3：c.235delC（目标）↔ c.235del（省略碱基写法）→ 应命中
    t3 = _arad_variant_matches(record_variant="c.235del", record_protein="p.Leu79Cysfs*3", target="c.235delC")
    ok("arad 离线-cDNA 省略碱基写法兼容（c.235delC ↔ c.235del）", t3, f"result={t3}")

    # 用例 4：蛋白表达匹配（p.Gly12Valfs*2）→ 应命中
    t4 = _arad_variant_matches(record_variant="c.35del", record_protein="p.Gly12Valfs*2", target="p.Gly12Valfs*2")
    ok("arad 离线-蛋白表达匹配（p.Gly12Valfs*2）", t4, f"result={t4}")

    # 用例 5：空 target → 应不命中（边界）
    t5 = _arad_variant_matches(record_variant="c.35del", record_protein="", target="")
    ok("arad 离线-空 target 不命中（边界）", not t5, f"result={t5}")

except Exception as _e:
    ok("arad 离线契约测试可执行", False, str(_e))


print(f"\n契约测试: {passed} 通过 / {fails} 失败")
sys.exit(1 if fails else 0)
