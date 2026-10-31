# -*- coding: utf-8 -*-
"""
P1 修复：同步 knowledge_graph.json 的 thresholds_ref.pm2.af_genetic
与权威表 config/thresholds.json 一致（2026-10-20 路由方案收缩为 TMPRSS3/STRC/GJB6 三基因）。
原则：knowledge_graph 是规范层快照，应反映权威表当前状态；引擎读 thresholds.json，VCEP 路由读 clingen-vcep 原文，
本副本同步后消除"PTEN 已出表却仍留副本"的污染源。
"""
import json, io, sys, os

# ROOT 优先取命令行参数，否则取本脚本所在目录的父目录（技能群根）
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(p):
    with io.open(p, encoding="utf-8") as f:
        return json.load(f)

kg_path = ROOT + r"\config\knowledge_graph.json"
thr_path = ROOT + r"\config\thresholds.json"

kg = load(kg_path)
thr = load(thr_path)

src = thr["pm2"]["af_genetic"]
target = kg["thresholds_ref"]["pm2"]["af_genetic"]

# 提取权威表的纯基因键（int/float 值；排除 note/source/version 等元键）
src_genes = {k: v for k, v in src.items() if isinstance(v, (int, float))}
src_meta = {k: v for k, v in src.items() if not isinstance(v, (int, float))}

# 保留知识图原有 note/source/version 元键，但更新数值基因表
new_genes = dict(src_genes)
# 更新 note 为路由说明（从权威表 note 提炼，保持知识图语境）
new_note = (
    "PM2 基因/疾病特异阈值。2026-10-20 路由方案收缩：有 ClinGen VCEP 文件的基因（GJB2/SLC26A4/CDH23/MYO15A/OTOF/PTEN 等）"
    "其特异阈值以 clingen-vcep/VCEP-<gene>.md 原文为权威源、由 ev-pm2 路由读取，不入本表；"
    "本表 af_genetic 仅含 0.007%(=0.00007) 一个值，严格仅限 TMPRSS3/STRC/GJB6 三个无 VCEP 文件的常隐遗传性听力损失基因。"
    "其他 AR-HL 基因有 VCEP 文件，一律走 VCEP 路由读取，禁止套用此 0.007% 值。"
)
new_source = "AR-HL 疾病特异阈值 0.007%（《变异解读查询路径》表7 20200904 + 指南解读 slide 43），仅适用无 ClinGen VCEP 文件的 TMPRSS3/STRC/GJB6 三基因；其余 AR-HL 基因有 VCEP 文件、走 VCEP 路由读取（2026-10-20）"
new_version = "cspec 各版（仅无 VCEP 基因兜底）"

target["note"] = new_note
target["source"] = new_source
target["version"] = new_version
# 删除所有旧基因键
for k in list(target.keys()):
    if isinstance(target[k], (int, float)):
        del target[k]
# 写入权威表的 3 基因
target.update(new_genes)

# 更新知识图 meta.version 微调记录？不改大版本，仅 thresholds_ref 同步（保持 updated 日期原样，避免误改版本号）
# 落盘，保持 ensure_ascii=False + 缩进2
with io.open(kg_path, "w", encoding="utf-8") as f:
    json.dump(kg, f, ensure_ascii=False, indent=2)

# 校验
kg2 = load(kg_path)
final = kg2["thresholds_ref"]["pm2"]["af_genetic"]
final_genes = {k: v for k, v in final.items() if isinstance(v, (int, float))}
print("同步后 af_genetic 基因键:", sorted(final_genes.keys()))
print("与权威表基因集一致:", set(final_genes) == set(src_genes))
print("PTEN 已移除:", "PTEN" not in final)
for g in sorted(src_genes):
    assert final_genes[g] == src_genes[g], g
print("全部值一致。P1 修复完成。")
