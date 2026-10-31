# ev-variant-standardization CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此

## v1.1.0

- **新增变异身份归一化硬闸**（cDNA 进入后强制确认变异类型 / 框内框外 / 蛋白改变 p.HGVS / 基因内位置，全部来自真实注释结果）。
- `standardize_variant()` 返回新增身份字段：`identity_status`(annotated/blocked/data_gap)、`identity_reason`、`variant_class`、`is_frameshift`、`is_inframe`、`gene_region`、`protein_change`。
- 新增 `classify_variant_class()`：从 SO terms 判定变异大类与框内框外。
- **阻塞态（评级暂停，可恢复）**：变异类型无法判定、或蛋白改变类变异缺 p.HGVS 时，输出 blocked 并提示人工复核，禁止"按密码子推断/假设"填补身份要素后继续。
- **数据缺口（不阻塞为卡死）**：该转录本无注释数据时标 data_gap 待核，走"缺数据≠反对"规则。
- 修复：consequences 为空时不再 IndexError。

## v1.0.0

- 变异身份归一化唯一主入口：GeneBe 基础注释（转录本/cDNA/pHGVS/坐标）+ HGNC 基因名对齐；GeneBe 评级字段一律不取。

