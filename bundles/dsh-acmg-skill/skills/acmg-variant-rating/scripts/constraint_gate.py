"""
constraint_gate.py — 前置规范层 · 五道约束门禁的确定性校验器

用途（遵守"不要把裁定权交给模型"）：
  把调度层「前置规范层与约束门禁」固化为可执行脚本。评级模型在每个变异上依次过
  G1 范式输入闸 / G2 知识图查询闸 / G3 阈值来源闸 / G4 取数留痕闸，收尾层过 G5 双套并列闸。
  脚本是【确定性校验器】：只判定"过/不过 + 出口"，不裁决证据成立性、不做最终分类——
  最终分类永远由收尾引擎（acmg_combine.py）决定。

用法：
  python scripts/constraint_gate.py check --variant '{"gene":"COL7A1","c_hgvs":"c.2664G>A","variant_class":"missense","identity_status":"annotated"}'
  python scripts/constraint_gate.py gate --gate G1 --variant '{"identity_status":"annotated","variant_class":"missense"}'
  python scripts/constraint_gate.py selftest     # 内置自检（回归门禁用）

输出：JSON，含每道门的 pass/action/出口。退出码：全过 0；G1 不过 2；其余不过 1。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
KG = os.path.join(CONFIG, "knowledge_graph.json")
THRESH = os.path.join(CONFIG, "thresholds.json")

# 变异类型 → 规范化四类（G1）
_VALID_CLASSES = ("truncating", "missense", "inframe_indel", "synonymous")
# 蛋白改变类变异须有 p.HGVS（G1 硬阻塞；仅真正落在蛋白改变的四类保留）
_PROTEIN_CLASSES = ("missense",)
# classify_variant_class（八类）→ G1 门禁四类 的归一映射（可配置、可审计）
# nonsense/frameshift/splicing → truncating（截短/LOF 归类）；inframe → inframe_indel
_CLASS_ALIAS = {
    "nonsense": "truncating", "frameshift": "truncating", "splicing": "truncating",
    "inframe": "inframe_indel", "stop_gained": "truncating",
}
# 明确拒评/需知识图新增去向的类型（不静默当作四类）
_NONCODING_CLASSES = ("noncoding", "other_protein")


def _normalize_class(raw):
    """把上游 classify 八类词表归一为 G1 门禁四类；无法归一返回 None。
    noncoding/other_protein 无适用表，返回 None（G2 会 STOP 待人工，不静默）。"""
    if not raw:
        return ""
    c = str(raw).strip().lower()
    if c in _VALID_CLASSES:
        return c
    if c in _CLASS_ALIAS:
        return _CLASS_ALIAS[c]
    return ""

# G3 阈值来源闸：必须由阈值表提供、模型不得自报的切点键（唯一来源白名单）
_THRESHOLD_KEYS = ("revel", "spliceai", "pm2", "pp1_lod", "pp1_lod_cmp_ep", "hl_vcep_pp1", "pm3_score", "tavtigian_interval", "lof", "score")

# G5 双套并列闸：禁止输出"最终分类仲裁/取值归一"的字段名（若出现在输入/输出即违例）
_FORBIDDEN_ARBITRATED_FIELDS = ("arbitrated_result", "final_class_normalized", "取一", "归一", "arbitrated")


def _load_kg():
    if not os.path.exists(KG):
        return None
    with open(KG, encoding="utf-8") as f:
        return json.load(f)


def _load_thresh():
    if not os.path.exists(THRESH):
        return None
    with open(THRESH, encoding="utf-8") as f:
        return json.load(f)


def gate_g1(v):
    """G1 范式输入闸：未规范化/变异类型缺失 → 暂停"""
    v = v or {}
    identity = v.get("identity_status", "")
    vclass = _normalize_class(v.get("variant_class"))
    hgvs_p = v.get("protein_change", "")
    protein_required = vclass in _PROTEIN_CLASSES

    if identity == "blocked":
        return {"gate": "G1", "pass": False, "action": "STOP",
                "exit": "变异身份未确认，评级中止，待人工复核",
                "reason": "identity_status=blocked"}
    if identity == "data_gap":
        return {"gate": "G1", "pass": True, "action": "CONTINUE_WITH_TAG",
                "exit": "缺数据≠反对，继续但标待核",
                "reason": "identity_status=data_gap，身份要素待核，不阻塞"}
    if vclass not in _VALID_CLASSES:
        return {"gate": "G1", "pass": False, "action": "STOP",
                "exit": "变异类型未判明，评级中止，禁止按密码子推断填补",
                "reason": f"variant_class={vclass!r} 不在四类 {_VALID_CLASSES}"}
    if protein_required and not hgvs_p:
        return {"gate": "G1", "pass": False, "action": "STOP",
                "exit": "蛋白改变类变异未取得 p.HGVS，评级中止，禁止推断蛋白改变",
                "reason": f"{vclass} 缺 protein_change"}
    return {"gate": "G1", "pass": True, "action": "PROCEED",
            "exit": "", "reason": "范式输入通过"}


def gate_g2(v, kg):
    """G2 知识图查询闸：圈定证据码只从知识图 evidence_applicability 取"""
    if kg is None:
        return {"gate": "G2", "pass": False, "action": "WARN",
                "exit": "知识图缺失，退回阈值表+证据适用表原文，不静默",
                "reason": "knowledge_graph.json 未找到"}
    app = kg.get("evidence_applicability", {})
    vclass = _normalize_class(v.get("variant_class"))
    if vclass not in app:
        return {"gate": "G2", "pass": False, "action": "STOP",
                "exit": "知识图无此变异类型适用表，评级中止待人工",
                "reason": f"evidence_applicability 无 {vclass}"}
    return {"gate": "G2", "pass": True, "action": "PROCEED",
            "exit": "", "reason": f"知识图命中 {vclass} 适用表 {len(app[vclass])} 码"}


def gate_g3(v, th):
    """G3 阈值来源闸：外部切点必须来自阈值表"""
    if th is None:
        return {"gate": "G3", "pass": False, "action": "WARN",
                "exit": "阈值表缺失，所有该码证据不足，禁止用训练记忆数值",
                "reason": "thresholds.json 未找到"}
    missing = [k for k in _THRESHOLD_KEYS if k not in th]
    if missing:
        return {"gate": "G3", "pass": False, "action": "WARN",
                "exit": f"阈值表缺键 {missing}，涉及证据码证据不足，不得自报数值",
                "reason": f"thresholds.json 缺 {missing}"}
    return {"gate": "G3", "pass": True, "action": "PROCEED",
            "exit": "", "reason": "阈值来源就绪（阈值表完整）"}


def gate_g4(v):
    """G4 取数留痕闸：查不到必须落"查不到+N路尝试"，禁止"假设极低频/假定罕见"式填补"""
    v = v or {}
    trace = v.get("fetch_trace", {}) or {}
    if v.get("query_trace_complete") is False:
        return {"gate": "G4", "pass": False, "action": "STOP",
                "exit": "取数未完成留痕，回补查后再判",
                "reason": "query_trace_complete=False"}
    # 检测"假定罕见/假设极低频"式填补
    for code, rec in (v.get("evidence", {}) or {}).items():
        if isinstance(rec, dict):
            note = str(rec.get("note", ""))
            if any(k in note for k in ("假定罕见", "假设极低频", "假定极低频", "假设罕见", "按默认值")):
                return {"gate": "G4", "pass": False, "action": "STOP",
                        "exit": f"{code} 用'假定罕见/假设极低频'式填补，禁止；必须真实查询频率并留痕",
                        "reason": f"{code} note 含禁止填补词"}
    return {"gate": "G4", "pass": True, "action": "PROCEED",
            "exit": "", "reason": "取数留痕通过"}


def gate_g5(v):
    """G5 双套并列闸：收尾层禁止取值归一/输出单一仲裁分类"""
    v = v or {}
    violates = []
    for k in _FORBIDDEN_ARBITRATED_FIELDS:
        if k in v:
            violates.append(k)
    if violates:
        return {"gate": "G5", "pass": False, "action": "STOP",
                "exit": f"出现取值归一字段 {violates}，恢复双套并列输出，不得做取舍",
                "reason": f"含禁止字段 {violates}"}
    return {"gate": "G5", "pass": True, "action": "PROCEED",
            "exit": "", "reason": "双套并列，无取值归一"}


GATES = {"G1": gate_g1, "G2": gate_g2, "G3": gate_g3, "G4": gate_g4, "G5": gate_g5}


def check_all(v):
    """依序过 G1→G2→G3→G4→G5，返回每道门结果 + 总判定"""
    kg = _load_kg()
    th = _load_thresh()
    results = {
        "G1": gate_g1(v),
        "G2": gate_g2(v, kg),
        "G3": gate_g3(v, th),
        "G4": gate_g4(v),
        "G5": gate_g5(v),
    }
    stop = [g for g, r in results.items() if r.get("pass") is False and r.get("action") == "STOP"]
    all_pass = all(r.get("pass") for r in results.values())
    return {
        "variant": v.get("gene", "?") + " " + v.get("c_hgvs", "?"),
        "gates": results,
        "all_pass": all_pass,
        "stop_gates": stop,
        "exit_code": 2 if stop else (0 if all_pass else 1),
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    mode = sys.argv[1]
    if mode == "selftest":
        return selftest()
    if mode == "check":
        if "--variant" not in sys.argv:
            print("缺 --variant", file=sys.stderr); return 2
        idx = sys.argv.index("--variant") + 1
        v = json.loads(sys.argv[idx])
        res = check_all(v)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return res["exit_code"]
    if mode == "gate":
        if len(sys.argv) < 4 or sys.argv[2] != "--gate":
            print("用法 gate --gate G1 --variant '...'", file=sys.stderr); return 2
        g = sys.argv[3]
        idx = sys.argv.index("--variant") + 1
        v = json.loads(sys.argv[idx])
        fn = GATES.get(g.upper())
        if not fn:
            print(f"未知门禁 {g}", file=sys.stderr); return 2
        kg, th = _load_kg(), _load_thresh()
        res = fn(v) if g.upper() in ("G1","G4","G5") else (fn(v, kg) if g.upper()=="G2" else fn(v, th))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("pass") else (2 if res.get("action")=="STOP" else 1)
    print(f"未知模式 {mode}", file=sys.stderr)
    return 2


def selftest():
    """内置自检：五道门各有过/不过样例（G1 前置字段补齐，模拟真实评级对象）"""
    # 基础：真实评级对象必备字段（G1 通过）
    def base(**kw):
        b = {"identity_status": "annotated", "variant_class": "missense", "protein_change": "p.Arg403Gln",
             "gene": "COL7A1", "c_hgvs": "c.2664G>A", "query_trace_complete": True, "evidence": {}}
        b.update(kw)
        return b
    cases = [
        ("G1 通过", base(), True),
        ("G1 blocked", base(identity_status="blocked", variant_class=None), False),
        ("G1 无类型", base(variant_class=None), False),
        ("G1 蛋白缺p", base(protein_change=""), False),
        ("G2 通过", base(), True),
        ("G2 未知类型", base(variant_class="translocation"), False),
        ("G4 假定罕见填补", base(evidence={"PM2": {"note": "假定罕见，未查询"}}), False),
        ("G5 通过", base(), True),
        ("G5 取值归一", base(arbitrated_result="LP"), False),
    ]
    ok = 0
    for name, v, expect in cases:
        r = check_all(v)
        got = r["all_pass"]
        mark = "PASS" if got == expect else "FAIL"
        if got == expect:
            ok += 1
        print(f"[{mark}] {name}: all_pass={got} (期望 {expect}) stop={r['stop_gates']}")
    print(f"\n自检 {ok}/{len(cases)} 通过")
    return 0 if ok == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
