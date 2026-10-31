# 组合层标准输入契约（L1→L2）

> 版本：v1.4.0（2026-10-16，F3 版本号修正 + D26 §2.3 BA1 等级契约改写：如实描述 `{"BA1":"Supporting"}`→Benign/LB 不 skip、明示调用方不得用降档等级削弱 BA1；前序 D20/D19/D11/D12/D15）
> 适用：`scripts/acmg_combine.py` 的 `--input / -e / --official`
> 铁律：组合层只接受「证据码+使用等级」与「官方裁定」，**不接受任何过程记录**（查询路径、文献列表、中间推理、可疑文献甄别过程）。过程记录属于 L1（证据判定层），由收尾技能或调用方在上游落盘，不进组合层输入。

## 1. 组合层输入 = 三部分，严格分开

| 通道 | 内容 | 禁止 |
|---|---|---|
| 证据码清单（items） | 仅 `{码: 等级}` 或 `[{"code":...,"level":...}]` | 不得含过程记录/查询路径/文献列表 |
| 官方裁定（official） | 仅一个官方分类结论 `{"class":...}` | 不得混入证据码清单 |
| interval | 分值区间 `2020 / 2023 / bmpR2_gn125_v2`；其中 `bmpR2_gn125_v2`（BMPR2/PAH 单基因，ClinGen CSpec GN125 v2.0.0）**须同时传 `--gene BMPR2`，否则引擎拒绝执行**（D11 强制，防评其他基因误用） | 不得省略（默认读 config） |

## 2. 证据码清单（items）合法形态

### 2.1 dict 形态
```json
{"PVS1": "VeryStrong", "PM3": "Moderate", "PP3": "Supporting"}
{"PVS1_Strong": 1, "PM2_Supporting": 2}
{"PP3/BP4": "均不成立"}        // 复合码自动拆分（PP3、BP4 各自判 skip）
```

### 2.2 list 形态
```json
[
  {"code": "PVS1", "level": "VeryStrong"},
  {"code": "PM3", "level": "Moderate", "count": 2, "verdict": "established"},
  {"code": "BP4", "level": "Supporting", "skip": true}
]
```
- `verdict` 非 `established/confirmed` → 该条拒收（skip），不计分。
- `not_found` / `pending` → 该码只降 confidence，不计分。
- 非标准等级（`未成立`/`互斥剔除` 等）→ 整条 skip，不抛错。

### 2.3 BA1 的 level 契约（D15 强制 / D20 修订，2026-10-15）

> **BA1 成立时不带 level**（引擎有 fallback 判 VeryStrong→Benign），或显式写 `Standalone` / `Stand-alone` / `Stand_alone` / `Stand Alone` / `SA` / `VeryStrong`——引擎对 **BA1** 做空白/连字符归一（stand-alone 系列归 VeryStrong，**含 ACMG/AMP 2015 原文 `"Stand Alone"` 带空格**，D20）。
> **stand-alone 系列写法仅对 BA1 生效（BA1 门控，D19）**：非 BA1 码写 `Standalone`/`SA` 等 → 整条 skip，**绝不升格为 VeryStrong**（引擎无全局白名单）。
> **正确示例**：`{"BA1": ""}` / `{"BA1": "Standalone"}` / `{"BA1": "Stand Alone"}` / `{"BA1": "SA"}`（→ VeryStrong → Benign）。
> **BA1 等级契约（D26 修正，2026-10-15）**：BA1 规则**只看 code、成立即判良性**，引擎**不因降档等级而 skip**——`{"BA1": "Supporting"}` 实测按 Supporting 计入良性侧 → **Likely Benign**（不是 skip，也不是 Benign，会静默削弱 BA1 的 VeryStrong 独立性）。**调用方不得用降档等级给 BA1**（会削弱为 LB）；BA1 成立一律按 VeryStrong（Benign）处理。
> `{"PM1": "Standalone"}`（非 BA1 用 stand-alone 写法）→ skip。

## 3. 官方裁定（official）—— 接口契约（Q5 修复）

官方裁定**必须带分类**才短路为 `official` 结论；不带分类标 `official_pending`（不得按通用 VUS 处置）。

### 3.1 数据内官方裁定（list 元素，推荐）
```json
[
  {"code": "VCEP官方裁定", "class": "Pathogenic",
   "source": "ClinGen VCEP GN170", "cspec_version": "v2.0.0", "effective_date": "2026-01-30"}
]
```
- `class` 字段直接提供分类 → 短路 Pathogenic。
- 兼容旧格式：无 `class` 时从 `level` 解析（`"level":"Pathogenic"` → Pathogenic）；`"level":"官方"` 无分类 → `official_pending`。

### 3.2 CLI 官方裁定（--official，兜底补分类）
```bash
--official '{"class":"Pathogenic","source":"ClinGen VCEP GN170","cspec_version":"v2.0.0"}'
```
- 合并优先级：**数据内 official（有 class）> CLI official（有 class）> pending（数据或 CLI 的任意非空）**。
- 即：数据内官方裁定为 pending 时，可由 `--official` 补上分类完成短路；两者都无 class 才回 pending。

### 3.3 判定规则
- `official.class` 命中 → 直接返回 `status=official`，跳过表5/分值通用规则（官方已定级优先）。
- `official.pending` → 返回 `status=official_pending`，标注"待上游补官方分类"，**不得判成普通 VUS**。
- 官方裁定与证据码清单互斥：官方裁定不进 items（`_extract_official` 提取后不再计分），避免双重计码。

## 4. 反例（禁止）
- ❌ `{"code":"VCEP官方裁定","level":"官方","evidence":"var005 表型5例"}` —— 过程信息混入，官方无 class → pending
- ❌ `--input 文件含查询路径/文献列表` —— 组合层只收证据码+官方裁定
- ❌ `{"PP3": 0.82, "evidence":["PMID..."]}` —— 证据码 value 只允许 count/等级，不允许过程字段

## 5. 调用方义务
- 收尾技能 / 调用方：上游已判定并落盘的证据码清单 + 官方裁定，按本契约组包后交给组合层；
- 官方分类缺失时：调用方须在 `--official` 补 class（从 ClinGen CSpec / 位点级裁定读取），不得静默丢给 pending；
- 组合层输出 `official_pending` 时：调用方须回查官方裁定并补 class 后重跑，不得直接采信 VUS。
