#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regression_gate.py — ACMG 组合引擎回归门禁（v1.0.0，第五轮审计 P0 整改配套）

铁律：每次改动 scripts/acmg_combine.py / combination_eval.py / config 后，必须跑本门禁，
全过才允许打包交付。防止「修复引入新回归」反复发生（审计 §4.3：验收通路与修复通路不交叉）。

三项检查：
  1. 穷举对照（328 组合）：纯致病 256 + 纯良性 64 + 混合 10，引擎 engine_a vs Table5 参考实现，必须 0 不符
  2. 引擎/CLI 冒烟：list 输入不双计、官方 class 短路、official_pending 不崩、复合码方向限定
  3. 39 集组合层评测：combination_eval 口径（表5/分值/overall 一致率），无崩溃
  4. 版本/配置一致性：收尾 version == CHANGELOG 最高版本

返回码：0=全 PASS；1=存在 FAIL（禁止打包）
一致率是「报告项」不设阈值（金标准口径见审计 §7：Table5 vs 点值法不一致，一致率低不代表引擎错）。
"""
import argparse
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = HERE  # 相对路径：脚本自身所在目录（随包可移植）
CONF = os.path.join(HERE, "..", "config", "thresholds.json")
GOLDEN = os.path.join(HERE, "..", "config", "golden.json")

sys.path.insert(0, HERE)
from acmg_combine import AcmgCombine, load_config, parse_evidence_items, ALL_PREFIXES  # noqa: E402

fails = 0
checks = []


def check(name, ok, detail=""):
    global fails
    checks.append((name, ok, detail))
    if not ok:
        fails += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


# ---------- 1. Table5 参考实现（Richards 2015，审计确认口径；返回全称与引擎对齐） ----------
def table5_ref(c):
    benign = c["BA1"] >= 1 or c["BS"] >= 2
    patho = (c["VS"] >= 1 and (c["ST"] >= 1 or c["MO"] >= 2 or (c["MO"] >= 1 and c["SU"] >= 1) or c["SU"] >= 2)) \
        or (c["ST"] >= 2) or (c["ST"] >= 1 and (c["MO"] >= 3 or (c["MO"] >= 2 and c["SU"] >= 2) or (c["MO"] >= 1 and c["SU"] >= 4)))
    lp = (c["VS"] >= 1 and c["MO"] >= 1) or (c["VS"] >= 1 and c["SU"] >= 1) \
        or (c["ST"] >= 1 and 1 <= c["MO"] <= 2) \
        or (c["ST"] >= 1 and c["SU"] >= 2) or (c["MO"] >= 3) or (c["MO"] >= 2 and c["SU"] >= 2) or (c["MO"] >= 1 and c["SU"] >= 4)
    # P0-1 修复（2026-10-22 用户拍板，与引擎 v20261022a 对齐）：LP 在 Table5 (i)-(vi) 基础上恢复补充口径
    # 「1 VS + 1 SU → LP」。1VS+1SU → LP；1VS+1MO（lp (i)）/ 1VS+2SU（patho (i) SU≥2）由对应分支先行拦截（P）。
    lb = (c["BS"] >= 1 and c["BP"] >= 1) or (c["BP"] >= 2)
    if patho and benign:
        return "VUS"
    if patho:
        return "Pathogenic"
    if benign:
        return "Benign"
    if lp and lb:
        return "VUS"
    if lp:
        return "Likely Pathogenic"
    if lb:
        return "Likely Benign"
    return "VUS"


# 构造引擎输入：用代表码把计数翻译成 items（dict 形式）
PATHO_REP = {"VS": ("PVS1", "VeryStrong"), "ST": ("PS3", "Strong"), "MO": ("PM3", "Moderate"), "SU": ("PP3", "Supporting")}


def build_items(c):
    """把计数 dict 翻译成 items。P1-7 修复适配：同一证据码在任一评价中只计 1 次（ACMG Table3），
    因此「N 条同等级证据」必须用 N 个不同码表达，不得同码重复计数（否则被 _dedup_same_code 压成 1 条，
    使 (iv)(v)(vi) 等需多码叠加的表5规则误判 VUS）。
    代表码：VS→PVS1；ST→PS3/PS4；MO→PM3/PP3；SU→PP3/PP1；BS→BS1_Strong/BS2_Strong；BP→BP4_Moderate/BP6。"""
    PATHO_MO = [("PM3", "Moderate"), ("PP3", "Moderate"), ("PM4", "Moderate")]
    PATHO_SU = [("PP3", "Supporting"), ("PP1", "Supporting"), ("PP2", "Supporting"), ("PP4", "Supporting")]
    PATHO_ST = [("PS3", "Strong"), ("PS4", "Strong"), ("PS1", "Strong")]
    BS_REP = [("BS1", "Strong"), ("BS2", "Strong")]
    BP_REP = [("BP4", "Moderate"), ("BP7", "Supporting")]
    d = {}
    for k, n in c.items():
        n = int(n)
        if n <= 0:
            continue
        if k == "BA1":
            d["BA1"] = n
            continue
        if k == "BS":
            reps = BS_REP
        elif k == "BP":
            reps = BP_REP
        elif k == "MO":
            reps = PATHO_MO
        elif k == "SU":
            reps = PATHO_SU
        elif k == "ST":
            reps = PATHO_ST
        elif k == "VS":
            reps = [("PVS1", "VeryStrong")]
        else:
            continue
        for i in range(n):
            code, lvl = reps[i % len(reps)]
            d[f"{code}_{lvl}"] = d.get(f"{code}_{lvl}", 0) + 1
    return d


def engine_a_result(engine, c):
    items, _ = parse_evidence_items(build_items(c))
    out = engine.combine(items)
    return out["engine_a"]["result"]


def run_exhaustive(engine):
    # 纯致病 256（VS/ST/MO/SU ∈ 0-3）
    bad = []
    for vs, st, mo, su in itertools.product(range(4), repeat=4):
        c = {"VS": vs, "ST": st, "MO": mo, "SU": su, "BA1": 0, "BS": 0, "BP": 0}
        exp = table5_ref(c)
        got = engine_a_result(engine, c)
        if exp != got:
            bad.append((c, exp, got))
    # 纯良性 64（BA1/BS/BP ∈ 0-3，无致病码）
    for ba1, bs, bp in itertools.product(range(4), repeat=3):
        c = {"VS": 0, "ST": 0, "MO": 0, "SU": 0, "BA1": ba1, "BS": bs, "BP": bp}
        exp = table5_ref(c)
        got = engine_a_result(engine, c)
        if exp != got:
            bad.append((c, exp, got))
    # 混合 10 组（审计 §2.1 覆盖：PVS1×BS1、PVS1×PP1 等）
    mixed = [
        {"VS": 1, "ST": 0, "MO": 0, "SU": 0, "BA1": 0, "BS": 1, "BP": 0},  # PVS1+BS1
        {"VS": 1, "ST": 0, "MO": 0, "SU": 1, "BA1": 0, "BS": 0, "BP": 0},  # PVS1+PP1
        {"VS": 1, "ST": 0, "MO": 1, "SU": 0, "BA1": 0, "BS": 0, "BP": 0},  # PVS1+PM3
        {"ST": 2, "MO": 0, "SU": 0, "VS": 0, "BA1": 0, "BS": 1, "BP": 0},
        {"ST": 1, "MO": 1, "SU": 0, "VS": 0, "BA1": 0, "BS": 1, "BP": 0},
        {"VS": 1, "MO": 1, "SU": 0, "ST": 0, "BA1": 0, "BS": 0, "BP": 1},
        {"MO": 3, "SU": 0, "VS": 0, "ST": 0, "BA1": 0, "BS": 0, "BP": 1},
        {"ST": 1, "SU": 2, "MO": 0, "VS": 0, "BA1": 0, "BS": 0, "BP": 2},
        {"MO": 2, "SU": 2, "VS": 0, "ST": 0, "BA1": 0, "BS": 1, "BP": 1},
        {"MO": 1, "SU": 4, "VS": 0, "ST": 0, "BA1": 0, "BS": 0, "BP": 0},
    ]
    for c in mixed:
        exp = table5_ref(c)
        got = engine_a_result(engine, c)
        if exp != got:
            bad.append((c, exp, got))
    return bad


def run_pm_supporting(engine):
    """P2-D 盲区修复：穷举加『PM 类码 × Supporting』输入，验证 PM2/PM3@Supporting 按 Supporting 桶处理，
    与『真 PP 类码 × Supporting』对表5结果等价（领域拍板 2026-10-15：两套结算均以证据等级为统一量纲）。
    此前穷举 PATHO_REP 的 SU 只绑 PP3，未覆盖 PM2/PM3@Supporting，恰漏 var002 引擎 P vs 金标准 LP 一类盲区。"""
    cases = [
        ({"PVS1_VeryStrong": 1, "PM2_Supporting": 1}, "PVS1_VS + PM2_SU(1条)"),
        ({"PVS1_VeryStrong": 1, "PM2_Supporting": 1, "PM3_Supporting": 1}, "PVS1_VS + PM2/PM3_SU(2条·PM类)"),
        ({"PVS1_VeryStrong": 1, "PP3_Supporting": 1, "PP1_Supporting": 1}, "PVS1_VS + PP3/PP1_SU(2条·PP类·对照)"),
        ({"PVS1_VeryStrong": 1, "PM2_Supporting": 1, "PM3_Supporting": 1, "PP3_Supporting": 1, "PP1_Supporting": 1}, "PVS1_VS + SU×4(PM+PP混合)"),
        ({"PM2_Supporting": 1, "PP3_Supporting": 1}, "PM2_SU + PP3_SU(2条·无VS)"),
        ({"PVS1_VeryStrong": 1, "PM2_Supporting": 1, "PP3_Supporting": 1, "PP1_Supporting": 1}, "PVS1_VS + PM2+PP3+PP1(SU×3)"),
    ]
    bad = []
    for items, name in cases:
        its, _ = parse_evidence_items(items)
        out = engine.combine(its)
        got = out["engine_a"]["result"]
        c = {"VS": 0, "ST": 0, "MO": 0, "SU": 0, "BA1": 0, "BS": 0, "BP": 0}
        for it in its:
            if it.get("skip"):
                continue
            lvl = it.get("level")
            n = it.get("count", 1)
            if it["code"] == "BA1":
                c["BA1"] += n
            elif lvl == "VeryStrong":
                c["VS"] += n
            elif lvl == "Strong":
                c["ST"] += n
            elif lvl == "Moderate":
                c["MO"] += n
            elif lvl == "Supporting":
                c["SU"] += n
        exp = table5_ref(c)
        if got != exp:
            bad.append((name, exp, got))
    return bad


# ---------- 1b. 分值引擎（engine_b）穷举对照（P0-B 修复，独立参考实现） ----------
def class_by_total_ref(total, iv):
    """独立参考：Tavtigian 分值→五分类（与引擎 _class_by_total 同语义、独立推导，防手滑）。
    区间语义：P>=P_min | LP>=LP_min | VUS>=VUS_min | (B_min, VUS_min)=LB | <=B_min=B。"""
    if total >= iv["P_min"]:
        return "Pathogenic"
    if total >= iv["LP_min"]:
        return "Likely Pathogenic"
    if total >= iv["VUS_min"]:
        return "VUS"
    if total > iv["B_min"]:
        return "Likely Benign"
    return "Benign"


def run_exhaustive_score(engine, conf):
    """分值引擎穷举（B 项盲区：engine_b 区间映射此前只靠 39 集，未独立穷举）。
    ① 对全整数总分 [-24,24] × 三区间（2020/2023/bmpR2_gn125_v2）对照独立参考 class_by_total_ref——覆盖 P/LP/VUS/LB/B 全边界与 2023 VUS 分支；
    ② 端到端 total 计算对照（items→总分）；
    ③ PM1+PP3 合计封顶 Strong(+4) 对照。"""
    bad = []
    iv_cfg = conf.get("tavtigian_interval", {})
    score_tbl = conf.get("score", {})
    # ① 全整数总分 × 三区间
    for interval in ["2020", "2023", "bmpR2_gn125_v2"]:
        iv = iv_cfg.get(interval)
        if not iv:
            bad.append((interval, "MISSING_IV", "n/a", "n/a"))
            continue
        for total in range(-24, 25):
            exp = class_by_total_ref(total, iv)
            got = engine._class_by_total(total, iv)
            if exp != got:
                bad.append((f"{interval} total={total}", exp, got))
    # ② 端到端 total 计算对照（代表组合，覆盖正负方向与边界）
    e2e = [
        ({"PVS1": "VeryStrong"}, 8),
        ({"PVS1": "VeryStrong", "PM3": "Moderate"}, 10),     # 8+2 → P（2020/2023/bmpR2_gn125_v2 P_min=10）
        ({"BS1": "Strong"}, -4),
        ({"BA1": "VeryStrong"}, -8),
        ({"PVS1": "VeryStrong", "PM3": "Moderate", "PP3": "Supporting"}, 11),
    ]
    for items, exp_total in e2e:
        its, _ = parse_evidence_items(items)
        out = engine.engine_b_score(its, interval="2020")
        if out["total"] != exp_total:
            bad.append((f"e2e total {items}", exp_total, out["total"]))
    # ③ PM1+PP3 封顶（4+4=8 → 合计封顶 +4）
    its, _ = parse_evidence_items({"PM1": "Strong", "PP3": "Strong"})
    out = engine.engine_b_score(its, interval="2020")
    if out["total"] != 4:
        bad.append(("PM1+PP3 cap", 4, out["total"]))
    # 2023 特有 VUS 分支（0-5 内分 Low/Mid/High）
    its, _ = parse_evidence_items({"PM3": "Moderate"})  # total=2 → VUS-Mid
    out = engine.engine_b_score(its, interval="2023")
    if out.get("vus_bias") != "VUS-Mid":
        bad.append(("2023 VUS-Mid 分支", "VUS-Mid", out.get("vus_bias")))
    return bad


def run_smoke(engine):
    # list 输入不双计（P0-1）：1 条 Strong → 1 条，不得判成 Pathogenic
    items, _ = parse_evidence_items([{"code": "PS3", "level": "Strong"}])
    check("list 输入不双计（1条Strong→1条）", len(items) == 1 and items[0]["code"] == "PS3",
          f"items={[(x['code'], x['level']) for x in items]}")
    out = engine.combine(items)
    check("list 单条 Strong→VUS（不被双计成 P）", out["engine_a"]["result"] == "VUS",
          f"result={out['engine_a']['result']}")
    # 官方 class 短路
    items, official = parse_evidence_items([{"code": "VCEP官方裁定", "class": "Pathogenic"}])
    out = engine.combine(items, official=official)
    check("官方 class=Pathogenic 短路", out.get("status") == "official" and out.get("class") == "Pathogenic")
    # official_pending 不崩（P0-3 由 CLI 分支处理，这里确认返回状态）
    items, official = parse_evidence_items([{"code": "VCEP官方裁定", "level": "官方"}])
    out = engine.combine(items, official=official)
    check("官方无分类→official_pending", out.get("status") == "official_pending")
    # 复合码方向限定（P1-1）
    items, _ = parse_evidence_items({"PS2/PM6": "Moderate"})
    check("复合码同向只计一次（PS2/PM6→1条）", len(items) == 1 and not items[0].get("skip"),
          f"items={[(x['code'], x['level']) for x in items]}")
    items, _ = parse_evidence_items({"PP3/BP4": "Supporting"})
    check("复合码对向 skip（PP3/BP4→不双计不抵消）", len(items) == 1 and items[0].get("skip"),
          f"items={[(x['code'], x.get('skip')) for x in items]}")
    items, _ = parse_evidence_items({"PM2/BA1": "Supporting"})
    check("复合码对向 skip（PM2/BA1→不推良性）", len(items) == 1 and items[0].get("skip"))


def run_39(engine):
    """39 集双尺子组合层评测（读 golden.json，两套结算分口径：表5仅对 basis=Table5，点值法不参与表5）。
    SKIP 计数：解析/引擎崩溃归 SKIP，SKIP>0 视为失败（堵住静默跳过）。"""
    GP = GOLDEN
    if not os.path.exists(GP):
        check("golden.json 存在", False, f"缺失 {GP}（先跑 golden_builder.py）")
        return None
    cases = json.load(open(GP, encoding="utf-8")).get("cases", [])
    total = len(cases)
    skip = ma_t5 = mb = mo = 0
    na_t5 = nb = 0
    n_pt = 0
    official_n = official_follow = 0
    for r in cases:
        criteria = r.get("criteria", [])
        methodA = r.get("methodA")
        methodB = r.get("methodB")
        basis = r.get("basis")
        try:
            items, official = parse_evidence_items(criteria)
            out = engine.combine(items, official=official)
        except Exception as ex:  # noqa: BLE001
            skip += 1
            continue
        is_official = out.get("status") == "official"
        if is_official:
            a = b = out.get("class")
            ag = True
            official_n += 1
            official_follow += (a == methodA) if methodA is not None else (b == methodB)
        elif out.get("status") == "official_pending":
            a = b = out.get("result", "VUS")
            ag = True
        else:
            a = out["engine_a"]["result"]
            b = out["engine_b"]["result"]
            ag = out.get("agreement")
        if basis == "Table5" and methodA is not None:
            na_t5 += 1
            ma_t5 += (a == methodA)
        if basis == "点值法":
            n_pt += 1
        if methodB is not None and not is_official:
            nb += 1
            mb += (b == methodB)
        mo += 1 if ag else 0
    rate = lambda n, d: f"{n/d*100:.1f}%" if d else "n/a"
    print(f"  39 集双尺子一致率: 表5(仅Table5基准)={rate(ma_t5,na_t5)} ({ma_t5}/{na_t5})  分值(非官方)={rate(mb,nb)} ({mb}/{nb})  "
          f"agreement={rate(mo,total)} ({mo}/{total})  点值法衍生={n_pt}  "
          f"官方遵循率={rate(official_follow,official_n)} ({official_follow}/{official_n})  SKIP={skip}")
    check("39 集评测 SKIP=0（无崩溃）", skip == 0, f"SKIP={skip}（SKIP>0 视为失败，禁止静默跳过）")
    return None


# 等级写法变体（D21/P1-2 + D27 v5.5.2）：standalone 系列写法集合，含 ClinGen VCEP 原文带括号写法
STANDALONE_FORMS = ["Standalone", "Stand-alone", "Stand_alone", "SA", "Stand Alone",
                    "Stand Alone (BA1)", "(BA1) Stand Alone"]


def run_level_variants(engine):
    """D21/P1-2 + D29：等级写法变体独立维度（v10 教训：门禁输入空间缺这一维）。
    stand-alone 系列写法只对 BA1 生效（BA1 门控）；非 BA1 码写该写法必须 skip，绝不升格 VeryStrong。
    D29 修复：dict 与 list 两个输入形态都覆盖（此前只测 dict，list 分支的 standalone 维度零断言）。
    D27（v5.5.2）：forms 追加 ClinGen VCEP 原文带括号写法 "Stand Alone (BA1)" / "(BA1) Stand Alone"，
    验证剥括号对后 BA1 仍升格、非 BA1 仍 skip，知识库原文不改、只改引擎识别。"""
    bad = []
    for code in sorted(ALL_PREFIXES):
        for f in STANDALONE_FORMS:
            for shape in ("dict", "list"):
                try:
                    if shape == "dict":
                        items, _ = parse_evidence_items({code: f})
                    else:
                        items, _ = parse_evidence_items([{"code": code, "level": f}])
                    if code == "BA1":
                        if not items or items[0]["skip"] or items[0]["level"] != "VeryStrong":
                            bad.append(f"{shape}: {code}+{f} → 应 VeryStrong/Benign，实际 {[(i['code'],i['level'],i['skip']) for i in items]}")
                    else:
                        if items and not items[0]["skip"]:
                            bad.append(f"{shape}: {code}+{f} → 应 skip，实际升格 {items[0]['level']}")
                except Exception as ex:  # noqa: BLE001
                    bad.append(f"{shape}: {code}+{f} ERR {ex}")
    return bad


def run_pm2_fixed(engine):
    """D24（2026-10-15 用户拍板；v13 审计 F1 修正为 cap；v5.5.1 F1′ 扩到 VeryStrong）：PM2 永久固定 PM2_Supporting，
    合法升级等级（VeryStrong/Strong/Moderate）**封顶到 Supporting 计入（cap）**、不整条丢弃、note+capped 留痕，
    dict + list 双形态。牙齿检验：v11 审计实证 PM2=Strong+PP3_S+PS3_S 判 Pathogenic，cap 后 PM2 仅 +1、不得判 Pathogenic；
    F1′ 修复 VeryStrong 曾整条丢弃（54 组偏低）——现与 Moderate/Strong 对称 cap。"""
    bad = []
    combos = [
        {"PM2": "Strong", "PP3": "Supporting", "PS3": "Strong"},
        {"PM2": "VeryStrong", "PP3": "Supporting", "PS3": "Strong"},
        {"PM2": "Moderate", "PVS1": "VeryStrong"},
    ]
    for items in combos:
        for shape in ("dict", "list"):
            if shape == "dict":
                its, _ = parse_evidence_items(items)
            else:
                its, _ = parse_evidence_items([{"code": c, "level": lv} for c, lv in items.items()])
            pm2 = [it for it in its if it["code"] == "PM2"]
            # cap：PM2 合法升级等级 → 封顶 Supporting 计入（skip=False + level=Supporting + note 含 cap + capped 标记）
            if not pm2 or pm2[0].get("skip") or pm2[0].get("level") != "Supporting" \
               or "cap" not in (pm2[0].get("note") or "") or not pm2[0].get("capped"):
                bad.append(f"{shape}: PM2 未封顶到 Supporting（应计入 skip=False + level=Supporting + note cap + capped），实际 {[(i['code'],i['level'],i['skip'],i.get('note'),i.get('capped')) for i in its]}")
            out = engine.combine(its)
            if out["engine_a"]["result"] == "Pathogenic":
                bad.append(f"{shape}: PM2 未封顶，仍判 Pathogenic（{items}）")
    return bad


def main():
    ap = argparse.ArgumentParser(description="ACMG 组合引擎回归门禁")
    ap.add_argument("--39", dest="run39", action="store_true", help="跑 39 集组合层评测（默认开）")
    ap.set_defaults(run39=True)
    args = ap.parse_args()

    conf = load_config(CONF)
    engine = AcmgCombine(conf)

    print("=== 1. 穷举对照（Table5 参考） ===")
    bad = run_exhaustive(engine)
    check("328 穷举对照 0 不符", len(bad) == 0,
          f"不符 {len(bad)} 处（前3: {bad[:3]}）" if bad else "")
    bad_pm = run_pm_supporting(engine)
    check("PM类码×Supporting 专项穷举 0 不符（P2-D 盲区修复）", len(bad_pm) == 0,
          f"不符 {len(bad_pm)} 处（前3: {bad_pm[:3]}）" if bad_pm else "")

    print("\n=== 1b. 分值引擎穷举对照（engine_b，P0-B） ===")
    bad_score = run_exhaustive_score(engine, conf)
    check("分值引擎穷举 0 不符（147 项×3区间 + 端到端 + cap）", len(bad_score) == 0,
          f"不符 {len(bad_score)} 处（前3: {bad_score[:3]}）" if bad_score else "")

    print("\n=== 2. 引擎/CLI 冒烟 ===")
    run_smoke(engine)

    print("\n=== 2b. 等级写法变体维度（D21/P1-2） ===")
    bad_var = run_level_variants(engine)
    check("写法变体：stand-alone 系列仅 BA1 生效、非 BA1 不升格", len(bad_var) == 0,
          f"违规 {len(bad_var)} 处（前3: {bad_var[:3]}）" if bad_var else f"{len(ALL_PREFIXES)} 码 × {len(STANDALONE_FORMS)} 写法 × dict/list 全通过")

    print("\n=== 2c. PM2 永久固定 PM2_Supporting（D24，dict+list 双形态） ===")
    bad_pm2 = run_pm2_fixed(engine)
    check("PM2 固定：非 Supporting 等级封顶到 Supporting 计入（cap）、绝不判 Pathogenic（dict+list）", len(bad_pm2) == 0,
          f"违规 {len(bad_pm2)} 处（前3: {bad_pm2[:3]}）" if bad_pm2 else "PM2 门控 dict+list 双形态全通过（cap）")

    print("\n=== 3. 39 集组合层评测 ===")
    if args.run39:
        run_39(engine)

    # 版本一致性（v1.1.0，P2-A 修复）：遍历全部 SKILL，校验各自 version == 各自 CHANGELOG 最高版本
    # （此前写死只查收尾，遗漏 acmg-total-scheduler 4.12.0 vs CHANGELOG 4.10.0 漂移）
    import re
    root = os.path.dirname(SCRIPTS)
    bad_ver = []
    n_ver = 0
    for entry in sorted(os.listdir(root)):
        sk = os.path.join(root, entry, "SKILL.md")
        cl = os.path.join(root, entry, "CHANGELOG.md")
        if not (os.path.isfile(sk) and os.path.isfile(cl)):
            continue
        ver = None
        for line in open(sk, encoding="utf-8"):
            if line.startswith("version:"):
                ver = line.split(":", 1)[1].strip()
                break
        chg = re.findall(r"^## v([\d.]+)", open(cl, encoding="utf-8").read(), re.M)
        top = max(chg, key=lambda v: [int(x) for x in v.split(".")]) if chg else None
        n_ver += 1
        if not (bool(ver) and bool(top) and ver == top):
            bad_ver.append(f"{entry}(SKILL={ver},CHANGELOG_top=v{top})")
    check("版本一致性：全部 SKILL version == 各自 CHANGELOG 最高版本（遍历全量）", not bad_ver,
          f"检查 {n_ver} 个 SKILL；漂移 {len(bad_ver)} 处: {bad_ver[:3]}" if bad_ver else f"检查 {n_ver} 个 SKILL，全部一致")

    # README 版本锚定一致性（v1.2.4 新增）：校验 README ANCHOR 行与各 SKILL frontmatter 一致
    # 防止改了技能版本但忘了更新 README 锚定行（此前已错 3 次：66.7%、arad 1.0.3、收尾 5.6.6）
    import subprocess
    anchor_check = os.path.join(SCRIPTS, "check_readme_anchor.py")
    if os.path.isfile(anchor_check):
        r = subprocess.run([sys.executable, anchor_check], capture_output=True, text=True)
        anchor_ok = (r.returncode == 0)
        anchor_detail = r.stdout.strip().split("\n")[0] if r.stdout else ""
        check("README 版本锚定与 SKILL frontmatter 一致", anchor_ok,
              anchor_detail if not anchor_ok else "")

    print(f"\n=== 结果: {'PASS' if fails == 0 else 'FAIL'}（{fails} 项失败）===")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
