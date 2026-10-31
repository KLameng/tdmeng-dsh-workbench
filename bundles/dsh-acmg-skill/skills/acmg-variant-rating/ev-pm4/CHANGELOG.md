# ev-pm4 CHANGELOG

2026-10-15 版本日志下沉：v1.1.0 变更记录从 SKILL.md frontmatter/正文移至本文件（正文/description 不再内联版本历史，防句子断裂）。

## v1.3.0（BP3 VCEP 适用性路由，2026-10-21）

- **全量探查**：134 个 VCEP 基因文件 **34 个含 `#### BP3` 档位判据**、99 个无段、1 个 NA（verification-evidence）。
- **关键形态结论**：多数基因的 BP3 是"框内 indel 位于重复区且不影响蛋白功能→Supporting"（标准型，SCN1A/PDHA1/POLG 等）；少数特定重复区限定（VHL 仅 8x GXEEX AA 重复基序 AA14-AA48、RPGR 仅 ORF15 重复区 AA585-1078）；CDH23/COCH/GJB2/KCNQ4/MYO6/MYO7A/OTOF/SLC26A4/TECTA/USH2A 重复区无已知功能→Supporting。
- 新增【BP3 VCEP 适用性路由协议】：查索引→读 BP3 段→判定形态（标准型/特定重复区限定/NA）→附加到通用 BP3 判定。通用 BP3 判定（三要素 + 重复区性质 + PM4 互斥）保留不动。
- 自检清单新增【BP3 VCEP 路由闸（v1.3.0）】：评 BP3 前必走路由。

## v1.2.0（PM4 VCEP 路由方案，2026-10-21）

- **全量探查（Windows 重建工作区）**：134 个 VCEP 基因文件 **103 个含 `#### PM4` 段**、15 个 NA、16 个无段。可数值化的 AA 长度切点在 **7 个基因**明确给出（ABCA4/AIPL1/CTLA4/GAA/GUCY2D/IDUA/RPE65：≥2 AA→Moderate、1 AA→Supporting）；另有 DICER1/RUNX1 为特定残基位置（RNase IIIb 域/RHD）。
- **关键形态结论**：PM4 特异规则以"框内 indel AA 数→档位"为主（可做计数引擎），前置条件（非重复区/进化保守/PhyloP）由执行者核验。
- 新增【PM4 VCEP 路由协议】第 4 步：查索引→读 PM4 段→判定形态→AA 计数档位喂引擎 `pm4_vcep_band`、特定残基位置按原文集合、SEMANTIC/纯通用用通用判定、NA 写不成立、纯通用回退。
- 引擎新增 `pm4_vcep_band(n_aa, gene, spec)`：复用 `_bs2_band_match`（code_prefix="PM4"），spec 形态 `{"type":"band","bands":{"moderate":2,"supporting":1},"unit":"amino_acid"}`，从高到低取最高达标档，返回 `PM4_Moderate/PM4_Supporting` 或 None；已注册 CLI。通用 PM4 判定（<1 外显子/终止密码子丧失）保留不动。
- **PM4 前置条件（写死）**：框内、非重复区、进化保守（VCEP 常附加 PhyloP 阈值如 ABCA4≥7.367、GUCY2D/AIPL1/RPE65>2.0）、indel<1 外显子或终止密码子丧失；引擎只做 AA 数档位比较，前置条件由执行者先查数据核验后再喂引擎。
- 自检清单新增【PM4 VCEP 路由闸（v1.2.0）】：评 PM4 前必走路由，VCEP 有 AA 档位则用 VCEP，特定残基按原文，SEMANTIC 用通用，NA 写不成立；禁止凭手抄漏查。

## v1.1.0

- 同技能补齐 BP3（良性 Supporting）判定段——框内 indel 位于重复/功能未知区域且进化非保守、预期不改变蛋白功能时使用，为 PM4 的良性镜像（变异解读查询路径 5.3.4.2）。
