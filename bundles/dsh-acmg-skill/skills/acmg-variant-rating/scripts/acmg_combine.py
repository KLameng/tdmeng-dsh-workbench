#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
acmg_combine.py — ACMG 评级技能群「组合层」确定性可执行引擎（修正版 v20261022a）

把收尾 SKILL `acmg-conflict-summary-output` §2.1 经典联合规则（Richards 2015 Table 5）
+ §2.2 Tavtigian 分值双套，从"LLM 文字执行"固化为确定性可执行脚本。

⚠️ 表5 规则来源（正确口径）：
  Pathogenic 只有 3 条主规则——
    (i)   1 VeryStrong AND [ (a) ≥1 Strong | (b) ≥2 Moderate | (c) 1 Moderate + 1 Supporting | (d) ≥2 Supporting ]
    (ii)  ≥2 Strong
    (iii) 1 Strong  AND [ (a) ≥3 Moderate | (b) 2 Moderate + ≥2 Supporting | (c) 1 Moderate + ≥4 Supporting ]
  Likely pathogenic——
    (i) 1 VeryStrong + 1 Moderate
    (i′) 1 VeryStrong + 1 Supporting → LP（用户拍板补充口径 v5.5.6，非 Richards 2015 原表，
        2026-10-22 用户再次确认采纳；仅当无更强组合落到此，1VS+≥2SU / 1VS+1MO / 1VS+1MO+1SU / 1VS+1ST 已判 P）
    (ii) 1 Strong + 1~2 Moderate
    (iii) 1 Strong + ≥2 Supporting
    (iv) ≥3 Moderate
    (v)  2 Moderate AND ≥2 Supporting      ← (v) 在 LP 侧，不在致病侧
    (vi) 1 Moderate AND ≥4 Supporting
  良性与可能良性：BA1→B；≥2 BS→B；1 BS+1 BP 或 ≥2 BP→LB。
  本引擎按证据码「最终使用等级」分桶（VeryStrong/Strong/Moderate/Supporting），
  而非按码前缀基线——PVS1@Strong 计入 Strong 桶、PP3@Moderate 计入 Moderate 桶、
  PM2@Supporting 计入 Supporting 桶，与 ClinGen/SVI/VCEP 的强度改写一致。

特性：
  1. 双套独立定级（引擎A 表5 等级组合 / 引擎B Tavtigian 分值），并列输出、不强制一致；
     两套定位（用户拍板 2026-10-16，不取值归一）：方案A=现行报告方法（报告结论采用方案A）；
     方案B=未来方法布局（比表5 更准确，但用于报告是在未来，现仅并列输出作布局/前瞻，不参与现行报告结论）；
     两种是不同的计算方法，不横向对比、不取值归一。
  2. 完整正确表5（(v) 在 LP 侧 = 2 Moderate + ≥2 Supporting）；
  3. 分值/区间从集中配置表 config/thresholds.json 读取；
  4. confidence 标签（high/medium/low）；
  5. 全程审计留痕；
  6. 双路径交叉验证（表5 计数式 vs 分值累加式）；
  7. MIT 化、独立可跑、仅依赖 Python 标准库；对上游非等级标注（官方/未成立/互斥剔除等）安全跳过，不崩溃。

用法：
  python acmg_combine.py --input evid.json [--interval 2023|2020|bmpR2_gn125_v2] [--gene BMPR2] [--conf ../config/thresholds.json]
  python acmg_combine.py -e '{"PVS1_Strong":1,"PM3_Moderate":1}'

输入 evid.json 格式（证据码 + 使用等级，消解后的最终可用证据码集合）：
  方式一 dict：  {"PVS1_Strong":1, "PM3_Moderate":1, "PP4_Supporting":1}
  方式二 list：  [{"code":"PVS1","level":"Strong"}, {"code":"PM3","level":"Moderate"}]
  每条可选标注：{"not_found":true} 或 {"pending":true}（影响 confidence）

证据码前缀：PVS1 / PS1-4 / PM1-5 / PP1-5 / BA1 / BS1-4 / BP1-7
等级：VeryStrong|Strong|Moderate|Supporting（接受 _VS/_ST/_MO/_SU 简写）
非标准等级（官方/未成立/互斥剔除/未计/未达阈值/均不成立/待全文核验等）→ 标记 skip 跳过，不计分不计桶。

注意：本引擎只做「组合层」定级；证据判定（查库/文献/功能/家系）与互斥消解、
官方两级优先由调度层与各子 SKILL 完成，本引擎输入即为消解后的证据码集合。
"""

import argparse
import json
import os
import re
import sys

# ---- 常量（默认路径） ----
DEFAULT_CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "thresholds.json")
DEFAULT_KG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "knowledge_graph.json")

# P0-1 修复（证据码核对报告）：模块级加载 knowledge_graph.code_base_strength，
# 用于「裸码无等级时」的默认等级兜底（如 {"PVS1":1} → PVS1 默认 VeryStrong）。
# 此前该表存在于 knowledge_graph.json 但 acmg_combine 从未读取（零命中），
# 导致裸码一律按"无等级"跳过、PVS1 等被静默丢弃（评级偏低根因）。
_CODE_BASE_STRENGTH = {}
try:
    with open(DEFAULT_KG, "r", encoding="utf-8") as _f:
        _KG = json.load(_f)
    _CODE_BASE_STRENGTH = _KG.get("code_base_strength", {}) or {}
except Exception:
    _CODE_BASE_STRENGTH = {}

# 证据码前缀 → 方向（致病 + / 良性 -）
# 注：按 ACMG/AMP 2015 官方 28 码（Richards 2015 Table 1/2）。PP5/BP6 已于 2018 起废弃，
# 不再列入；PM6（新发、父母未验证）为标准中等致病码，必须登记。
PATHOGENIC_PREFIXES = ("PVS1", "PS1", "PS2", "PS3", "PS4", "PM1", "PM2", "PM3", "PM4", "PM5", "PM6",
                       "PP1", "PP2", "PP3", "PP4")
BENIGN_PREFIXES = ("BA1", "BS1", "BS2", "BS3", "BS4", "BP1", "BP2", "BP3", "BP4", "BP5", "BP7")
ALL_PREFIXES = PATHOGENIC_PREFIXES + BENIGN_PREFIXES

LEVEL_SCORE = {"VeryStrong": "VS", "Strong": "ST", "Moderate": "MO", "Supporting": "SU"}

# D24（2026-10-15，用户拍板，manifest §8 / ev-pm2 v1.4.1 / 收尾 §0.4）：PM2 永久固定为 PM2_Supporting。
# 引擎是通用组合器，必须对违反该裁定的输入显式跳过（不静默归一、不按传入等级计分），
# 否则会把一个支持性证据静默变成强证据、直接推高到 Pathogenic（v11 审计实证：PM2=Strong → Pathogenic）。
# 这是"文档声明必须有代码执行者"的落地——manifest §8 只写文档不设执行者 = 无约束。
PM2_FIXED_LEVEL = "Supporting"

CLASS_LABELS = {0: "Pathogenic", 1: "Likely Pathogenic", 2: "VUS", 3: "Likely Benign", 4: "Benign"}
CLASS_ZH = {"Pathogenic": "致病", "Likely Pathogenic": "可能致病", "VUS": "意义不明确",
            "Likely Benign": "可能良性", "Benign": "良性"}

# 上游技能天然会输出的「非等级标注」：不计分、不计桶、不崩溃，标记 skip
NON_LEVEL_MARKERS = ("官方", "未成立", "互斥剔除", "未计", "未达阈值", "均不成立",
                     "待全文核验", "待核验", "pending", "not_found", "不适用", "弃用", "待人工")


class ACMGCombineError(Exception):
    pass


def load_config(path):
    if not os.path.exists(path):
        raise ACMGCombineError(f"配置表不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_level(lvl_raw):
    """把等级字符串归一化为 VeryStrong/Strong/Moderate/Supporting；非标准返回 None。
    v24-fix：遇 [状态标记] / (注) 先剥括号对（含内容），只对等级本体归一——
    如 'VeryStrong[certain]' → 'VeryStrong'、'Strong(RNA)' → 'Strong'。
    不再因尾随状态标记把整条等级判为非标准而丢弃。"""
    if not lvl_raw:
        return None
    lvl_raw = lvl_raw.strip()
    while "[" in lvl_raw and "]" in lvl_raw:
        i, j = lvl_raw.find("["), lvl_raw.find("]")
        lvl_raw = lvl_raw[:i] + " " + lvl_raw[j + 1:]
    while "(" in lvl_raw and ")" in lvl_raw:
        i, j = lvl_raw.find("("), lvl_raw.find(")")
        lvl_raw = lvl_raw[:i] + " " + lvl_raw[j + 1:]
    lvl_raw = " ".join(lvl_raw.split())
    up = lvl_raw.upper()
    if up in ("VS", "VERYSTRONG", "V", "VERY_STRONG"):
        return "VeryStrong"
    if up in ("ST", "STRONG", "S"):
        return "Strong"
    if up in ("MO", "MODERATE", "M"):
        return "Moderate"
    if up in ("SU", "SUPPORTING"):
        return "Supporting"
    # D19（2026-10-15）：stand-alone 系列写法移除出全局白名单——它们只对 BA1 生效（在调用点门控），
    # 非 BA1 码写该写法必须 skip，绝不可升格为 VeryStrong（v10 实测 100 组偏移）。
    return None


def _is_standalone_form(lvl_raw):
    """BA1 的规范等级写法识别（空白/连字符/下划线/括号对归一到 STANDALONE）：
    Standalone / Stand-alone / Stand_alone / Stand Alone / Stand Alone (BA1) / (BA1) Stand Alone / SA / SA (BA1) → True。
    （D20 接受 ACMG/AMP 2015 原文 "Stand Alone"；v5.5.2 D27 剥括号对，兼容 ClinGen VCEP 官方原文
     "1 Stand Alone (BA1)" 等带尾随括号写法，知识库原文不改。剥括号只作用于 standalone 判断、不影响其他路径；
     仅当括号成对出现才剥，防误伤非括号写法；剥后再归一比较 STANDALONE/SA。）"""
    if not lvl_raw:
        return False
    s = str(lvl_raw).upper().replace("-", " ").replace("_", " ")
    # 剥括号对（含内容）：兼容 VCEP 原文 "Stand Alone (BA1)" / "(BA1) Stand Alone" / "SA (BA1)"
    while "(" in s and ")" in s:
        i, j = s.find("("), s.find(")")
        s = s[:i] + " " + s[j + 1:]
    s = "".join(s.split())
    return s == "STANDALONE" or s == "SA"


def _is_non_level(s):
    return any(m in s for m in NON_LEVEL_MARKERS)


def _extract_official(code, level, class_val=None):
    """识别官方裁定条目（code/level 含"官方"或 level=official），提取官方分类。
    返回 {class, source, pending}；非官方条目返回 None。
    class 优先级：显式 class 字段 > level 中解析（含 Pathogenic/LP/B/LB 或中文明）；无 → pending（待上游补分类）。"""
    lv = str(level or "")
    if ("官方" in str(code)) or ("官方" in lv) or (lv.lower() in ("official", "官方裁定", "vcep官方裁定")):
        cls = class_val if class_val else None
        if not cls:
            for c in ("Pathogenic", "Likely Pathogenic", "Benign", "Likely Benign",
                      "致病", "可能致病", "良性", "可能良性", "VUS", "意义不明确"):
                if c in lv:
                    cls = c
                    break
        return {"class": cls, "source": code, "pending": cls is None, "evidence": None}
    return None


def _class_from_status(s):
    """从官方裁定的状态/描述文字中提取分类值（Pathogenic/LP/B/LB）；无则 None。"""
    if not s:
        return None
    s = str(s)
    for kw, cls in (("Likely Pathogenic", "Likely Pathogenic"), ("可能致病", "Likely Pathogenic"),
                    ("Pathogenic", "Pathogenic"), ("致病", "Pathogenic"),
                    ("Likely Benign", "Likely Benign"), ("可能良性", "Likely Benign"),
                    ("Benign", "Benign"), ("良性", "Benign")):
        if kw in s:
            return cls
    return None


def _split_complex_items(key, value):
    """复合码（PS2/PM6、PP3/BP4、PM2/BA1）拆分：方向限定，只计一次，杜绝双计/抵消/推良性。
    两侧同向 → 取第一侧计一次；两侧对向或含未知 → 方向未定，整条 skip（不计两侧）；
    value 显式 direction（pathogenic/benign）→ 取对应侧。"""
    subs = [s.strip() for s in key.split("/") if s.strip()]
    if not subs:
        return []
    count, level, direction, skip, verdict, not_found, pending = 1, None, None, False, None, False, False
    if isinstance(value, dict):
        count = int(value.get("count", 1)); level = value.get("level")
        direction = value.get("direction"); skip = bool(value.get("skip"))
        verdict = value.get("verdict"); not_found = bool(value.get("not_found")); pending = bool(value.get("pending"))
    elif isinstance(value, str):
        level = value
    elif isinstance(value, (int, float)):
        count = int(value)
    verdict_skip = verdict is not None and verdict not in ("established", "confirmed")

    def mk(code):
        it = _parse_key(code + (("_" + str(level)) if level else ""), value)
        if it:
            it["count"] = count; it["verdict"] = verdict
            it["not_found"] = not_found; it["pending"] = pending
            it["skip"] = it.get("skip") or skip or verdict_skip
        return it

    if direction:
        w = str(direction).lower()
        want = "P" if w in ("pathogenic", "致病", "p") else ("B" if w in ("benign", "良性", "b") else None)
        if want:
            pool = PATHOGENIC_PREFIXES if want == "P" else BENIGN_PREFIXES
            pick = [s for s in subs if s in pool]
            if pick:
                it = mk(pick[0])
                return [it] if it else []
        return []  # direction 未识别 → 不落码
    sides = [("P" if s in PATHOGENIC_PREFIXES else ("B" if s in BENIGN_PREFIXES else "?")) for s in subs]
    uniq = set(sides)
    if len(uniq) == 1 and "?" not in uniq:
        it = mk(subs[0])  # 同向（PS2/PM6）：取第一侧计一次
        return [it] if it else []
    it = mk(subs[0])  # 对向/未知：方向未定，整条 skip（禁止双计/抵消/推良性）
    if it:
        it["skip"] = True; it["code"] = key; it["note"] = "复合码方向未定，禁止双计/抵消"
    return [it] if it else []


def parse_evidence_items(data):
    """把 dict / list 输入统一解析为 (items, official)。
    - items: [{code, level, count, not_found, pending, skip}]；非标准等级 → skip=True
    - official: 官方裁定条目提取（{class,...} 或 pending）；官方条目不进 items
    P0-1 修复：list 分支不再双重 append（普通/复合码只计一次）。
    P1-1 修复：复合码拆分方向限定，杜绝双计/抵消/推良性。
    P1-2 修复：官方裁定无 class 时，从 status/strength 描述文字提取分类。"""
    items = []
    official = None

    def handle_key(k, v, cls=None):
        nonlocal official
        lv = v.get("level") if isinstance(v, dict) else (v if isinstance(v, str) else "")
        vcls = v.get("class") if isinstance(v, dict) else None
        o = _extract_official(k, lv, cls or vcls or _class_from_status(v.get("status") if isinstance(v, dict) else None))
        if o:
            official = o
            return True
        if "/" in k:  # 复合码：方向限定拆分（P1-1）
            for it in _split_complex_items(k, v):
                items.append(it)
        else:
            it = _parse_key(k, v)
            if it:
                items.append(it)
        return False

    if isinstance(data, dict):
        for k, v in data.items():
            handle_key(k, v)
    elif isinstance(data, list):
        for e in data:
            if isinstance(e, dict):
                if "code" in e:
                    # 先判官方裁定（class 字段 / status/strength 文字分类），不进 items
                    o = _extract_official(e["code"], e.get("level", ""),
                                          e.get("class") or _class_from_status(e.get("status")) or _class_from_status(e.get("strength")))
                    if o:
                        official = o
                        continue
                    if "/" in e["code"]:
                        for it in _split_complex_items(e["code"], e):
                            items.append(it)
                        continue
                    # 普通单码：只 append 一次（P0-1：不再双重计入）
                    _cl = e["code"].upper() if isinstance(e["code"], str) else e["code"]
                    _lv = e.get("level", "")
                    if _cl == "BA1" and (_lv in ("", None) or _is_standalone_form(_lv)):
                        lvl = "VeryStrong"  # D19/D20：BA1 不带 level 或 standalone 写法 → VeryStrong
                    else:
                        lvl = _normalize_level(_lv if _lv else "Supporting")
                    # D24（v13 审计 F1 修正为 cap；v5.5.1 F1′ 扩到 VeryStrong）：PM2 合法升级等级
                    # （VeryStrong/Strong/Moderate）→ 封顶到 Supporting 计入（不整条丢弃，note+capped 留痕）；
                    # standalone 等非合法等级写法 → 保持 skip（D19 非 BA1 不升格）
                    pm2_note = None
                    pm2_capped = False
                    if _cl == "PM2" and lvl != PM2_FIXED_LEVEL:
                        if lvl in ("VeryStrong", "Strong", "Moderate"):
                            pm2_note = f"PM2 永久固定 PM2_Supporting（manifest §8/ev-pm2 1.4.1）：收到 {_lv or '非Supporting'}，按永久 Supporting 封顶计入（cap），不取更高档"
                            lvl = PM2_FIXED_LEVEL
                            pm2_capped = True
                        else:
                            pm2_note = f"PM2 永久固定 PM2_Supporting（manifest §8/ev-pm2 1.4.1）：收到 {_lv or '非Supporting'} 非合法等级/standalone，不采信（skip）"
                    verdict = e.get("verdict")
                    verdict_skip = verdict is not None and verdict not in ("established", "confirmed")
                    skip = bool(e.get("skip")) or (lvl is None and _is_non_level(str(e.get("level", "")))) or (lvl is None) or verdict_skip
                    if _cl == "PM2" and lvl != PM2_FIXED_LEVEL:
                        skip = True  # standalone 等非合法等级 PM2 → skip（不 cap 不升格）
                    items.append({
                        "code": e["code"], "level": lvl or "Supporting", "count": int(e.get("count", 1)),
                        "not_found": bool(e.get("not_found")), "pending": bool(e.get("pending")),
                        "skip": skip, "verdict": verdict, "note": pm2_note, "capped": pm2_capped,
                    })
                elif len(e) == 1:
                    for k, v in e.items():
                        handle_key(k, v)
                else:
                    raise ACMGCombineError(f"无法识别的证据条目: {e}")
            else:
                raise ACMGCombineError(f"证据条目须为 dict，收到: {e}")
    else:
        raise ACMGCombineError("输入须为 dict 或 list")
    return items, official


def _parse_key(key, value):
    """解析 "CODE_LEVEL" 或 "CODE_LEVEL: count"。value 为 count / {level,...} / 等级字符串。
    P0-2 修复：支持 {"PM2":"Supporting"} 这类 value 即等级的输入（key 无后缀时用 value 的等级）；
    P0-3 修复：value 命中非等级标记（未成立/官方/互斥剔除等）→ 整条 skip，含 BA1（不再短路成 VeryStrong）。"""
    key = key.strip()
    meta = {"not_found": False, "pending": False}
    count = 1
    value_lvl = None
    if isinstance(value, dict):
        count = int(value.get("count", 1))
        meta["not_found"] = bool(value.get("not_found"))
        meta["pending"] = bool(value.get("pending"))
        value_lvl = value.get("level")
    elif isinstance(value, str):
        value_lvl = value  # {"PM2": "Supporting"} / {"BA1": "未成立"}
    elif isinstance(value, (int, float)):
        count = int(value)

    m = re.match(r"^([A-Za-z0-9]+)(?:_(.+))?$", key)
    if not m:
        raise ACMGCombineError(f"证据码名须为 'CODE_LEVEL'，收到: {key}")
    code = m.group(1).upper()
    key_lvl = m.group(2).strip() if m.group(2) else None
    # 等级优先取 key 后缀；无后缀时才用 value 的等级字符串（P0-2）
    lvl_raw = key_lvl or value_lvl

    # P0-3：等级串命中非等级标记 → skip（对 BA1 同样生效，不再 fallback VeryStrong）
    if lvl_raw and _is_non_level(str(lvl_raw)):
        return {"code": code, "level": "Supporting", "count": count, "not_found": meta["not_found"],
                "pending": meta["pending"], "skip": True}

    if code not in ALL_PREFIXES:
        raise ACMGCombineError(f"未知证据码前缀: {code}")
    else:
        if lvl_raw:
            if code == "BA1" and _is_standalone_form(str(lvl_raw)):
                lvl = "VeryStrong"  # D19/D20：stand-alone 写法归 BA1 门控（含带空格 "Stand Alone"）
            else:
                lvl = _normalize_level(lvl_raw)
        else:
            # P0-1 修复（证据码核对报告）：裸码无等级时，读 knowledge_graph.code_base_strength 的默认等级。
            # BA1 特例仍归 VeryStrong（stand-alone 门控）；其余码从 code_base_strength 查默认等级，
            # 查不到才视为无等级（→ 下方 skip 非等级标注，但那是真实缺等级，不再误伤有默认等级的码）。
            if code == "BA1":
                lvl = "VeryStrong"
            else:
                lvl = _CODE_BASE_STRENGTH.get(code) or None
    # D24（2026-10-15 用户拍板；v13 审计 F1 修正为 cap）：
    # PM2 永久固定 PM2_Supporting。**合法升级等级（VeryStrong/Strong/Moderate）→ 封顶到 Supporting 计入（cap）**，
    # 保留 PM2 成立该有的 +1 分（skip 会整条丢掉致 162 组系统性低估），note 留痕 + capped 标记可审计（F6）；
    # **standalone 等非合法等级写法 → 仍 skip**（D19：非 BA1 码写 standalone 不升格）。
    if code == "PM2" and lvl != PM2_FIXED_LEVEL:
        if lvl in ("VeryStrong", "Strong", "Moderate"):
            return {"code": code, "level": PM2_FIXED_LEVEL, "count": count, "not_found": meta["not_found"],
                    "pending": meta["pending"], "skip": False, "capped": True,
                    "note": f"PM2 永久固定 PM2_Supporting（manifest §8/ev-pm2 1.4.1）：收到 {lvl_raw or value_lvl or '非Supporting'}，按永久 Supporting 封顶计入（cap），不取更高档"}
        return {"code": code, "level": "Supporting", "count": count, "not_found": meta["not_found"],
                "pending": meta["pending"], "skip": True,
                "note": f"PM2 永久固定 PM2_Supporting（manifest §8/ev-pm2 1.4.1）：收到 {lvl_raw or value_lvl or '非Supporting'} 非合法等级/standalone，不采信（skip）"}
    if lvl is None:
        # 非标准等级（官方/未成立/互斥剔除/待核验等）→ skip
        return {"code": code, "level": "Supporting", "count": count, "not_found": meta["not_found"],
                "pending": meta["pending"], "skip": True}
    return {"code": code, "level": lvl, "count": count, "not_found": meta["not_found"],
            "pending": meta["pending"], "skip": False}


class AcmgCombine:
    def __init__(self, conf):
        self.conf = conf
        self.score = conf.get("score", {})
        self.interval_cfg = conf.get("tavtigian_interval", {})

    # ---------- 引擎A：经典联合规则（Richards 2015 Table 5，正确口径） ----------
    @staticmethod
    def _dedup_same_code(items):
        """P1-7 修复（证据码核对报告）：同一证据码在**同一等级**下只计 1 次。
        ACMG 2015 Table 3 明确 PP3 等"can be used only once in any evaluation"；
        同码同级多例（{BP4_Supporting:2} 或两条同码同级）不得重复计数推结论。
        ⚠ 修正（20261021 回归）：去重键是 (code, level)，**不是** code——同一码 PP3 以 Moderate 与
        Supporting 两级出现时是两条独立证据（不同数据/变异），必须都保留；
        仅当 code 与 level 完全相同才去重（保留 count=1）。否则会把 2MO+2SU 组合
        （PM3_M+PP3_M+PP3_S+PP1_S）误压成 3 条，使表5 (v) 2MO+≥2SU 漏判。"""
        best = {}
        for it in items:
            if it.get("skip") or it.get("not_found") or it.get("pending"):
                # 非计分条目：用 (code,level) 作键保留首个，不参与去重
                best.setdefault((it["code"], it.get("level", "Supporting")), dict(it))
                continue
            key = (it["code"], it.get("level", "Supporting"))
            if key not in best:
                best[key] = dict(it, count=1)
            # 已存在同码同级：count 强制为 1，不再累加（P1-7 同码只计 1 次）
        return list(best.values())

    def _counts(self, items):
        """按「最终使用等级」分桶（VeryStrong/Strong/Moderate/Supporting）。
        与码前缀基线解耦：PVS1@Strong→Strong 桶、PP3@Moderate→Moderate 桶、PM2@Supporting→Supporting 桶。
        P1-7 修复：先同码去重（PP3 等只能计 1 次），杜绝 {PP3:2} 重复推高。"""
        items = self._dedup_same_code(items)
        c = {"VS": 0, "ST": 0, "MO": 0, "SU": 0, "BA1": 0}
        for it in items:
            if it.get("skip") or it.get("not_found") or it.get("pending"):
                continue  # 非等级标注/查不到/待人工：不计桶
            n = it.get("count", 1)
            lvl = it.get("level", "Supporting")
            if it["code"] == "BA1":
                c["BA1"] += n
            # 方向过滤（P0-1 修复）：只有致病码进致病桶，良性码（BS/BP）不得反向推动致病。
            # 良侧由 engine_a_classic 的良性前缀计数单独判定。
            if it["code"] in PATHOGENIC_PREFIXES:
                if lvl == "VeryStrong":
                    c["VS"] += n
                elif lvl == "Strong":
                    c["ST"] += n
                elif lvl == "Moderate":
                    c["MO"] += n
                else:
                    c["SU"] += n
        return c

    def _classic_pathogenic(self, c):
        """致病强规则（P）——只有 Richards 2015 的 (i)(ii)(iii)，不含 (v)。"""
        # (i) 1 VS AND (≥1 ST | ≥2 MO | 1MO+1SU | ≥2 SU)
        if c["VS"] >= 1 and (c["ST"] >= 1 or c["MO"] >= 2 or (c["MO"] >= 1 and c["SU"] >= 1) or c["SU"] >= 2):
            return True
        # (ii) ≥2 ST
        if c["ST"] >= 2:
            return True
        # (iii) 1 ST AND (≥3 MO | 2MO+≥2SU | 1MO+≥4SU)
        if c["ST"] >= 1 and (c["MO"] >= 3 or (c["MO"] >= 2 and c["SU"] >= 2) or (c["MO"] >= 1 and c["SU"] >= 4)):
            return True
        return False

    def _classic_likely_pathogenic(self, c):
        """可能致病（LP）——Richards 2015 的 (i)-(vi) + 用户拍板补充口径 (i′)。"""
        # (i) 1 VS + 1 MO
        if c["VS"] >= 1 and c["MO"] >= 1:
            return True
        # (i′) 用户拍板补充口径（v5.5.6，2026-10-16 用户拍板；2026-10-22 用户再次确认采纳）：
        # 1 VS + 1 SU → LP。精确触发：仅当无更强组合落到此（1VS+1SU、SU=1、无 MO/ST）；
        # 1VS+≥2SU / 1VS+1MO / 1VS+1MO+1SU / 1VS+1ST 已由 _classic_pathogenic 判 P，不受影响。
        # （P0-4 曾以"非表5"从引擎删除；收尾 SKILL §2.1 文档一直保留该条，现引擎与文档对齐。）
        if c["VS"] >= 1 and c["SU"] >= 1:
            return True
        # (ii) 1 ST + 1~2 MO
        if c["ST"] >= 1 and 1 <= c["MO"] <= 2:
            return True
        # (iii) 1 ST + ≥2 SU
        if c["ST"] >= 1 and c["SU"] >= 2:
            return True
        # (iv) ≥3 MO
        if c["MO"] >= 3:
            return True
        # (v) 2 MO + ≥2 SU
        if c["MO"] >= 2 and c["SU"] >= 2:
            return True
        # (vi) 1 MO + ≥4 SU
        if c["MO"] >= 1 and c["SU"] >= 4:
            return True
        return False

    def _classic_benign(self, c):
        return c["BA1"] >= 1  # BA1 → B（BS≥2 单独由良性桶判定，见 _counts/引擎A）
        # 注：BS/BP 也按等级入桶，BS≥2 的判定保留在良性规则里（见 engine_a_classic）

    def engine_a_classic(self, items):
        c = self._counts(items)
        # P0-2 修复（证据码核对报告）：良侧表5 规则必须按「等级」分桶计数，不得按码前缀只数数量。
        # ACMG Table5：B = BA1 或 ≥2 BS(Strong)；LB = 1 BS(Strong)+1 BP(Supporting) 或 ≥2 BP(Supporting)。
        # 之前按码前缀数（{BS1_Supporting, BS2_Supporting} 被当 2 BS → 错判 Benign，实际需 2 Strong）；
        # 现改为只统计达到 Strong 的 BS 数 / 达到 Supporting 的 BP 数，并先同码去重（P1-7）。
        dedup = self._dedup_same_code(items)
        bs_strong = 0  # 达到 Strong(含) 的 BS 码数
        bp_support = 0  # 达到 Supporting 的 BP 码数
        for it in dedup:
            if it.get("skip") or it.get("not_found") or it.get("pending"):
                continue
            n = it.get("count", 1)
            code = it["code"]
            lvl = it.get("level", "Supporting")
            if code.startswith("BS"):
                if lvl in ("Strong", "VeryStrong"):
                    bs_strong += n
            elif code.startswith("BP"):
                if lvl in ("Supporting", "Moderate", "Strong", "VeryStrong"):
                    bp_support += n

        patho = self._classic_pathogenic(c)
        benign = (c["BA1"] >= 1) or (bs_strong >= 2)
        lp = self._classic_likely_pathogenic(c)
        lb = (bs_strong >= 1 and bp_support >= 1) or (bp_support >= 2)

        # 矛盾优先：致病强 & 良性强 → VUS
        if patho and benign:
            return {"result": "VUS", "rules_hit": ["致病强规则与良性强规则并存 → 矛盾 VUS"], "counts": c}
        if patho:
            return {"result": "Pathogenic", "rules_hit": self._patho_rules(c), "counts": c}
        if benign:
            rule = "BA1→B" if c["BA1"] else f"≥2BS_Strong→B ({bs_strong} BS_Strong)"
            return {"result": "Benign", "rules_hit": [rule], "counts": c}
        if lp and lb:
            return {"result": "VUS", "rules_hit": ["LP 与 LB 并存 → 矛盾 VUS"], "counts": c}
        if lp:
            return {"result": "Likely Pathogenic", "rules_hit": self._lp_rules(c), "counts": c}
        if lb:
            rule = f"≥2BP→LB ({bp_support} BP)" if bp_support >= 2 else f"1BS_Strong+1BP→LB ({bs_strong} BS_Strong + {bp_support} BP)"
            return {"result": "Likely Benign", "rules_hit": [rule], "counts": c}
        return {"result": "VUS", "rules_hit": ["无任何表5 组合命中"], "counts": c}

    def _patho_rules(self, c):
        out = []
        if c["VS"] >= 1:
            if c["ST"] >= 1:
                out.append("(i) 1VS + ≥1ST → P")
            elif c["MO"] >= 2:
                out.append("(i) 1VS + ≥2MO → P")
            elif c["MO"] >= 1 and c["SU"] >= 1:
                out.append("(i) 1VS + 1MO + 1SU → P")
            elif c["SU"] >= 2:
                out.append("(i) 1VS + ≥2SU → P")
        if c["ST"] >= 2:
            out.append("(ii) ≥2ST → P")
        if c["ST"] >= 1:
            if c["MO"] >= 3:
                out.append("(iii) 1ST + ≥3MO → P")
            elif c["MO"] >= 2 and c["SU"] >= 2:
                out.append("(iii) 1ST + 2MO + ≥2SU → P")
            elif c["MO"] >= 1 and c["SU"] >= 4:
                out.append("(iii) 1ST + 1MO + ≥4SU → P")
        return out

    def _lp_rules(self, c):
        out = []
        if c["VS"] >= 1 and c["MO"] >= 1:
            out.append("(i) 1VS + 1MO → LP")
        if c["VS"] >= 1 and c["SU"] >= 1:
            out.append("(i′) 1VS + 1SU → LP（用户拍板补充口径 v5.5.6）")
        if c["ST"] >= 1 and 1 <= c["MO"] <= 2:
            out.append("(ii) 1ST + 1~2MO → LP")
        if c["ST"] >= 1 and c["SU"] >= 2:
            out.append("(iii) 1ST + ≥2SU → LP")
        if c["MO"] >= 3:
            out.append("(iv) ≥3MO → LP")
        if c["MO"] >= 2 and c["SU"] >= 2:
            out.append("(v) 2MO + ≥2SU → LP")
        if c["MO"] >= 1 and c["SU"] >= 4:
            out.append("(vi) 1MO + ≥4SU → LP")
        return out

    # ---------- 引擎B：Tavtigian 分值 ----------
    def _score_one(self, code, level):
        key = LEVEL_SCORE.get(level)
        if key is None:
            return 0  # 非标准等级已由 parse 标记 skip，此处防御
        s = self.score.get(key, None)
        if s is None:
            raise ACMGCombineError(f"分值表缺等级 {level}")
        # 精确方向判定（不用 startswith，避免 PS/PM 基码误判方向）
        if code in PATHOGENIC_PREFIXES:
            return s
        if code in BENIGN_PREFIXES:
            return -s
        raise ACMGCombineError(f"未知证据码方向: {code}")

    def engine_b_score(self, items, interval=None):
        total = 0
        detail = []
        for it in items:
            if it.get("skip") or it.get("not_found") or it.get("pending"):
                continue  # 查不到/待人工/非等级标注不赋分
            n = it.get("count", 1)
            pts = self._score_one(it["code"], it["level"]) * n
            total += pts
            detail.append({"code": it["code"], "level": it["level"], "count": n, "pts": pts})
        # PM1 + PP3 合计封顶 Strong(+4)（ClinGen SVI Pejaver 2022 官方建议，官网核对 Q8）
        # 二者同时成立时合计分值不得 > 4，超出部分剔除并留痕。
        pm1_pts = sum(d["pts"] for d in detail if d["code"] == "PM1")
        pp3_pts = sum(d["pts"] for d in detail if d["code"] == "PP3")
        if pm1_pts and pp3_pts and (pm1_pts + pp3_pts) > 4:
            overflow = (pm1_pts + pp3_pts) - 4
            total -= overflow
            detail.append({"code": "PM1+PP3", "level": "cap", "count": 1, "pts": -overflow,
                           "note": "合计封顶 Strong(+4)，超出已剔除（Pejaver 2022）"})
        if interval is None:
            interval = self.interval_cfg.get("default", "2020")
        iv = self.interval_cfg.get(interval, self.interval_cfg.get("2020"))
        if not iv:
            raise ACMGCombineError(f"未知 Tavtigian 区间: {interval}")
        result = self._class_by_total(total, iv)
        vus_bias = None
        if 0 <= total <= 5 and interval == "2023":
            if 0 <= total <= 1:
                vus_bias = "VUS-Low"
            elif 2 <= total <= 3:
                vus_bias = "VUS-Mid"
            else:
                vus_bias = "VUS-High"
        return {"total": total, "interval": interval, "interval_cfg": iv, "result": result,
                "detail": detail, "vus_bias": vus_bias}

    def _class_by_total(self, total, iv):
        """Tavtigian 分值→五分类（完整五段，B_min 真实参与分类）。
        区间语义：P>=P_min | LP>=LP_min | VUS>=VUS_min | (B_min, VUS_min)=LB | <=B_min=B。
        修复点：良性侧不再用 `>=LB_min`（LB_min 是区间上界，会漏掉 LB 档），改消费 B_min。"""
        if total >= iv["P_min"]:
            return "Pathogenic"
        if total >= iv["LP_min"]:
            return "Likely Pathogenic"
        if total >= iv["VUS_min"]:
            return "VUS"
        if total > iv["B_min"]:
            return "Likely Benign"
        return "Benign"

    def _boundary_flags(self, total, iv):
        bounds = [iv["P_min"], iv["LP_min"], iv["VUS_min"], iv["LB_min"], iv["B_min"]]
        return [b for b in bounds if total == b]

    # ---------- 汇总 ----------
    def combine(self, items, interval=None, official=None, gene=None):
        """官方短路优先：若传入 official 裁定（ClinGen VCEP/EP 对具体变异的裁定），
        直接返回该结论并记录 cspec 版本/生效日，不再走通用规则加权。
        否则走 引擎A(表5)+引擎B(Tavtigian) 双套定级。
        gene：基因名（HGNC 大写）；当 interval=bmpR2_gn125_v2 时必须为 BMPR2，否则拒绝（D11 强制，2026-10-15）。"""
        # D11：BMPR2 专用区间强制基因校验（防评其他基因误用）
        if interval == "bmpR2_gn125_v2" and (gene is None or str(gene).upper() != "BMPR2"):
            raise ACMGCombineError(
                f"interval=bmpR2_gn125_v2 仅适用于 BMPR2 / 肺动脉高压(PAH) 单基因"
                f"（ClinGen CSpec GN125 v2.0.0），当前 gene={gene or '未提供'} 不匹配，拒绝执行；"
                f"评 BMPR2 必须传 --gene BMPR2，评其他基因禁止使用该区间")
        if official:
            if official.get("class"):
                return {
                    "status": "official",
                    "class": official.get("class"),
                    "cspec_version": official.get("cspec_version"),
                    "effective_date": official.get("effective_date"),
                    "evidence": official.get("evidence"),
                    "note": "官方（ClinGen VCEP/EP 或权威专家组共识）已定级优先，短路通用规则",
                    "official_source": official.get("source"),
                }
            # 4.2：官方裁定存在但分类未解析 → 标 pending（非普通 VUS），待上游补官方分类
            return {
                "status": "official_pending",
                "result": "VUS",
                "note": "官方裁定存在但分类未解析（level 未含 Pathogenic/LP/B/LB 分类值）→ 待上游补官方分类，不得按通用 VUS 处置",
                "official": official,
                "official_source": official.get("source"),
            }
        # P2 修复（全修，2026-10-23）：引擎 A/B 共用同一份去重后的 items——
        # 同一证据码同一等级只计 1 次（ACMG Table 3：PP3 等"can be used only once"），
        # 消除同码重复输入下"引擎A去重(_counts)/引擎B累加(engine_b_score)"的分歧
        # （如 PVS1_Strong + PP3_Supporting×2：修前 A=VUS / B=LP）。
        # 去重键为 (code, level)：同码不同等级（PP3_Moderate+PP3_Supporting）是独立证据仍保留，不误伤表5 (v) 2MO+2SU 组合。
        _raw_total = sum(it.get("count", 1) for it in items if not it.get("skip"))
        items = self._dedup_same_code(items)
        _aft_total = sum(it.get("count", 1) for it in items if not it.get("skip"))
        _dedupe = (f"同码同级去重：有效计分计数 {_raw_total}→{_aft_total}（ACMG Table3：同码同级只计1次）"
                   if _aft_total < _raw_total else None)
        a = self.engine_a_classic(items)
        b = self.engine_b_score(items, interval)
        iv = b["interval_cfg"]
        boundaries = self._boundary_flags(b["total"], iv)

        not_found = [it["code"] for it in items if it["not_found"] and not it.get("skip")]
        pending = [it["code"] for it in items if it["pending"] and not it.get("skip")]
        skipped = [f"{it['code']}={it.get('level','?')}" + (f"({it['note']})" if it.get("note") else "")
                   for it in items if it.get("skip")]
        # F6（v5.5.1）：cap 留痕透传到输出——PM2 被封顶到 Supporting 的条目，可审计可见
        capped = [f"{it['code']}={it.get('level','?')}" + (f"({it['note']})" if it.get("note") else "")
                  for it in items if it.get("capped")]

        # 两套定位（用户拍板 2026-10-16，不取值归一）：
        # 方案A（表5）=现行报告方法，报告结论采用方案A（官方/共识已定级时由上游按 §0 官方优先采用官方分类）；
        # 方案B（Tavtigian 分值）=未来方法布局，比表5 更准确但用于报告是在未来，现仅并列输出作布局/前瞻，
        #   不参与现行报告结论；两种是不同的计算方法，不横向对比、不取值归一。
        agreement = a["result"] == b["result"]
        # table5_gap（v20261019a，v20 审计 N5）：表5 无任何组合规则命中（引擎A=VUS）而方案B 落在明确结论
        # （P/LP/B/LB）时置 true，提示"表5 未覆盖此证据组合，请人工复核"——防 VUS 冒充结论。
        # 判据=引擎A 无明确结论（VUS）且引擎B 非 VUS；不误伤表5 有规则命中的正常案例（引擎A 非 VUS）。
        table5_gap = a["result"] == "VUS" and b["result"] not in ("VUS",)
        positioning = {
            "scheme_a": {"method": "经典联合规则(表5)", "role": "现行报告方法",
                         "note": "报告结论采用方案A（表5）；官方/共识已定级时按上游官方优先采用官方分类"},
            "scheme_b": {"method": "Tavtigian 分值", "role": "未来方法布局",
                         "note": "比表5 更准确，但用于报告是在未来；现仅并列输出作布局/前瞻，不参与现行报告结论"},
            "comparability": "两种是不同的计算方法，不横向对比、不取值归一",
        }

        # v24-fix：skipped（含三态括号被丢弃/非等级标记跳过）非空时 confidence 不得为 high——
        # 存在被丢弃的证据码即说明结论不完整，降级防"丢证据仍标高可信"。
        if skipped:
            confidence = "low"
        elif not_found or pending:
            confidence = "low"
        elif boundaries or not agreement:
            confidence = "low" if boundaries else "medium"
        else:
            confidence = "high"

        return {
            "input_count": len(items),
            "dedupe": _dedupe,
            "skipped": skipped,
            "capped": capped,
            "engine_a": {"name": "经典联合规则(表5)", "result": a["result"], "rules_hit": a["rules_hit"]},
            "engine_b": {"name": "Tavtigian 分值", "result": b["result"], "total": b["total"],
                         "interval": b["interval"], "detail": b["detail"], "vus_bias": b["vus_bias"]},
            "agreement": agreement,
            "table5_gap": table5_gap,
            "positioning": positioning,
            "confidence": confidence,
            "boundary": boundaries,
            "not_found": not_found,
            "pending": pending,
            "audit": {
                "score_table": self.score,
                "tavtigian_interval": iv,
                "classic_zh": CLASS_ZH.get(a["result"], a["result"]),
                "score_zh": CLASS_ZH.get(b["result"], b["result"]),
            },
        }


def main():
    ap = argparse.ArgumentParser(description="ACMG 组合层确定性引擎（表5 + Tavtigian 双套）")
    ap.add_argument("--input", help="输入 JSON 文件（证据码+等级 清单）")
    ap.add_argument("-e", "--evidence", help="内联证据码 JSON，如 '{\"PVS1_Strong\":1,\"PM3_Moderate\":1}'")
    ap.add_argument("--interval", choices=["2023", "2020", "bmpR2_gn125_v2"], default=None,
                    help="Tavtigian 分值区间（默认读 config/tavtigian_interval.default；bmpR2_gn125_v2=BMPR2/PAH 单基因 VCEP（GN125 v2.0.0）专用，须 --gene BMPR2 否则拒绝，默认不启用）")
    ap.add_argument("--gene", help="基因名（HGNC 大写，如 BMPR2）；当 --interval=bmpR2_gn125_v2 时必传且须为 BMPR2，否则拒绝执行")
    ap.add_argument("--official", help="官方裁定 JSON：{\"class\":\"Pathogenic\",\"cspec_version\":\"...\",\"effective_date\":\"...\",\"evidence\":\"...\"}（命中即短路通用规则）")
    ap.add_argument("--conf", default=DEFAULT_CONF, help=f"集中阈值配置表（默认 {DEFAULT_CONF}）")
    ap.add_argument("--zh", action="store_true", help="中文输出分类名")
    args = ap.parse_args()

    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif args.evidence:
            data = json.loads(args.evidence)
        else:
            ap.error("必须提供 --input 或 -e")

        conf = load_config(args.conf)
        cli_official = json.loads(args.official) if args.official else None
        items, data_official = parse_evidence_items(data)
    except json.JSONDecodeError as e:
        print(f"[错误] 输入 JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)
    except ACMGCombineError as e:
        # P2 修复（全修）：证据输入不合法（如 -e 传 list 形态 ["PVS1_Strong"]）→ 干净 JSON 错误退出，不抛 Traceback
        print(f"[错误] 证据输入不合法: {e}", file=sys.stderr)
        print('{"error":"' + str(e).replace('"', '\\"') + '"}', file=sys.stderr)
        sys.exit(1)
    # 数据内官方裁定优先（4.2：识别 {"code":"VCEP官方裁定",...} 为官方短路，不再被当证据码 skip）；
    # 数据官方为 pending（无 class）时，若 CLI --official 带分类则用其补上（标准输入契约：官方分类可由 --official 供给）
    if data_official and data_official.get("class"):
        official = data_official
    elif cli_official and cli_official.get("class"):
        official = cli_official
    else:
        official = data_official or cli_official
    engine = AcmgCombine(conf)
    out = engine.combine(items, interval=args.interval, official=official, gene=args.gene)

    if out.get("status") == "official":
        print("=== ACMG 组合层定级结果（官方短路） ===")
        print(f"分类: {out['class']}")
        if out.get("cspec_version"):
            print(f"cspec 版本: {out['cspec_version']}   生效日: {out.get('effective_date')}")
        print(out.get("note", ""))
        if out.get("evidence"):
            print(f"证据: {out['evidence']}")
        print("\n--- JSON ---")
        print(json.dumps(out, ensure_ascii=False))
        return

    if out.get("status") == "official_pending":
        # P0-3 修复：official_pending 无 engine_a/engine_b，单独分支输出（不抛 KeyError）
        print("=== ACMG 组合层定级结果（官方裁定待补分类） ===")
        print("官方裁定已识别但缺少分类（class），未短路通用规则；请补官方分类（--official 或数据 class 字段）后重跑，不得按通用 VUS 处置")
        print(out.get("note", ""))
        print("\n--- JSON ---")
        print(json.dumps(out, ensure_ascii=False))
        return

    a, b = out["engine_a"], out["engine_b"]
    zh = CLASS_ZH
    print("=== ACMG 组合层定级结果 ===")
    print(f"证据码条数: {out['input_count']}" + (f"（跳过非等级标注: {out['skipped']}）" if out["skipped"] else ""))
    if out.get("capped"):
        print(f"含被引擎封顶的码(cap): {out['capped']}")
    print(f"[引擎A 经典联合规则(表5)] {a['result']} ({zh.get(a['result'], a['result'])})")
    for r in a["rules_hit"]:
        print(f"   命中: {r}")
    print(f"[引擎B Tavtigian 分值] {b['result']} ({zh.get(b['result'], b['result'])})  总分={b['total']}  区间={b['interval']}")
    for d in b["detail"]:
        print(f"   {d['code']}_{d['level']} ×{d['count']} = {d['pts']:+d}")
    if b.get("vus_bias"):
        print(f"  VUS 偏性: {b['vus_bias']}")
    print(f"两套结论一致: {out['agreement']}")
    if out.get("table5_gap"):
        print(f"⚠ 表5 未覆盖此证据组合（引擎A=VUS），方案B 为 {b['result']}，请人工复核（报告以方案A 表5 为结论，此组合表5 无规则命中）")
    pos = out.get("positioning", {})
    print(f"两套定位: 方案A(表5)={pos.get('scheme_a', {}).get('role')}；方案B(点数法)={pos.get('scheme_b', {}).get('role')}；不取值归一")
    if not out['agreement']:
        print("两套不一致：如实并列输出、标注两代方法差异；报告以方案A（表5，现行）为结论（官方已定级除外）")
    print(f"confidence: {out['confidence']}")
    if out["boundary"]:
        print(f"处于阈值边界(切点值): {out['boundary']}")
    if out["not_found"]:
        print(f"含'查不到'码(不计分): {out['not_found']}")
    if out["pending"]:
        print(f"含'待人工'码: {out['pending']}")

    print("\n--- JSON ---")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
