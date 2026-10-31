---
name: ev-gene-identity
version: 1.0.0
description: 核实两个或多个基因名称是否指向同一个基因，以及查询某基因有哪些假基因。通过NCBI Gene数据库实时查询Gene ID和别名进行比对，支持别名识别；假基因查询通过Gene Name+P通配符搜索并筛选pseudogene标记。当用户需要判断基因是否同名、基因别名比对、查假基因、pseudogene查询、确认基因是否为同一基因、基因符号比对时使用。
---

# 基因身份核实_jb

两个核心功能：
1. **判断两个/多个基因是否为同一个基因** — 基于NCBI Gene ID和别名
2. **查询某基因的假基因列表** — 基于NCBI Gene数据库pseudogene标记

## 数据源

- **NCBI Gene (E-utilities)**：免费公开数据库，无需API Key
- 使用 `esearch` + `esummary` 组合查询

## 功能一：判断基因是否为同一基因

### 工作流程

1. 对每个基因名分别调用esearch搜索NCBI Gene（Homo sapiens），获取Gene UID
2. 用esummary获取每个基因的 `name`（官方符号）和 `otheraliases`（别名列表）
3. 判断逻辑：
   - **Gene ID相同** → 同一基因 ✅
   - **基因A的官方名出现在基因B的别名中** → 同一基因（B是官方名，A是别名）
   - **基因B的官方名出现在基因A的别名中** → 同一基因（A是官方名，B是别名）
   - **以上都不满足** → 不同基因 ❌

### 用法

```bash
python main.py same <基因A> <基因B> [基因C ...]
```

### 输出

- 每个基因的：Gene ID、官方符号、别名列表
- 两两比对结果
- 最终结论

## 功能二：查询假基因

### 工作流程

1. 用 `{基因名}P*[Gene Name] AND Homo sapiens[Organism]` 搜索NCBI Gene
2. esummary批量获取结果详情
3. 筛选 `description` 字段中包含 "pseudogene" 的记录
4. 输出假基因名称、Gene ID、染色体位置、描述

### 用法

```bash
python main.py pseudo <基因名>
```

### 输出

- 匹配的假基因列表（基因符号、Gene ID、染色体位置、描述）
- 总数统计

### 局限性

- 不是所有基因的假基因都在NCBI Gene中有记录
- 搜不到时应说明"NCBI Gene库中无假基因记录"，不代表该基因确实无假基因

## 注意事项

- 数据实时查询NCBI，以查询时结果为准
- 仅查询人类（Homo sapiens）基因
- API限速3次/秒，批量查询时自动间隔
- 输出标注：智能分析结果，仅供参考
