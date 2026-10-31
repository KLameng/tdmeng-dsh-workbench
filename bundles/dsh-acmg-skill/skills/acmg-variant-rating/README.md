# ACMG 单病变异评级技能群

对孟德尔疾病相关基因序列变异进行 ACMG/AMP 2015 致病性分类的成套技能（23 个技能 = 1 总调度 + 1 收尾 + 1 遗传方式前置 + 19 证据码子技能 + 1 个 VCEP 数据载体 `clingen-vcep`）。

> **版本锚定**：本分发包为各技能当前版本的**集合快照**，并非与任何单一版本号相等。各技能版本以各自 `SKILL.md`/`CHANGELOG.md` 为准（以下由 `scripts/gen_readme_anchor.py` 自动生成，请勿手抄）：
<!-- ANCHOR:BEGIN -->
> `acmg-total-scheduler=4.15.0`、`acmg-conflict-summary-output=5.6.7`、`arad-inheritance-judgment=1.0.4`、`clingen-vcep=1.1.0`、`ev-bs1-bs2=1.9.0`、`ev-disease-info=1.0.0`、`ev-gene-identity=1.0.0`、`ev-gnomad-constraint=1.0.0`、`ev-pm1=1.2.0`、`ev-pm2=1.5.0`、`ev-pm3=1.13.0`、`ev-pm4=1.3.0`、`ev-pp1=1.8.0`、`ev-pp2=1.2.3`、`ev-pp3-bp4=1.10.0`、`ev-pp4=1.4.0`、`ev-ps1-pm5=1.6.0`、`ev-ps2-pm6=1.5.0`、`ev-ps3-bs3=1.7.0`、`ev-ps4=1.5.0`、`ev-pvs1=1.13.0`、`ev-variant-literature-patient=1.7.0`、`ev-variant-standardization=1.1.0`。
<!-- ANCHOR:END -->
>
> **部署形态（P2-7 澄清）**：本技能群为**整包部署（workspace 整体）**，不是可逐个独立导入的单技能包——`ev-*` 证据技能依赖工作区根的 `scripts/acmg_evidence.py`、`config/thresholds.json` 等共享引擎/配置。**部署单元是整个解压目录**，勿单独导入某个 `ev-` 目录，否则找不到引擎。
>
> **数据卫生**：本分发包**不含** HGMD 商业数据库（`hgmd_pro_2024.1...xlsx` 不随包分发）。HGMD 取数通过 `ev-variant-literature-patient` 的 `HGMD_QUERY_DIR` 环境变量指向**用户自备授权**的桌面专用目录（详见该技能 README）；未配置时提示「HGMD 数据缺失」+ 前往配置指引，可设 `HGMD_SKIP=1` 显式跳过（状态 `missing_config`/`skipped_user_opted_out`，走 ClinVar/文献通道、不静默）。文献检索 LLM 精筛走通用 OpenAI 兼容通道（`LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY`），可接方舟/DeepSeek/智谱/Kimi/通义/OpenAI 等任意兼容平台。**未配置/调用失败时 LLM 闸门硬中断并引导配置 KEY，不静默降级（v1.5.0）。**

## 技能构成

| 层级 | 技能 | 职责 |
|---|---|---|
| 总调度（唯一入口） | `acmg-total-scheduler` | 变异身份归一化 → 遗传方式前置 → 按变异类型圈定证据码池 |
| 遗传方式前置 | `arad-inheritance-judgment` | AD/AR/多模式/LOF 机制判定（依赖遗传模式的证据码须先调用） |
| 收尾（互斥汇总） | `acmg-conflict-summary-output` | 互斥消解、赋分累加、经典联合规则 + Tavtigian 双套定级 |
| 证据码子技能 | `ev-*`（PVS1/PS1-PM5/PM1-PM4/PP1-PP4/PS2-PM6/PS3-BS3/PS4/BS1-BS2/PP3-BP4/PM4/文献等 19 个） | 逐码判定，输出证据码+等级/数据+规则/查询路径 |
| VCEP 载体 | `clingen-vcep` | 已装载基因按基因特异性规则判定（仅辅助，须联网核实 ClinGen cspec 最新版；**独立数据包，另包分发，主包 ZIP 不含**） |

## 安装与依赖

```bash
pip install -r requirements.txt   # 核心：requests>=2.28
```

涉及 `requests` 的技能：`ev-gene-identity` / `ev-disease-info` / `ev-variant-literature-patient` / `arad-inheritance-judgment`。建议在隔离 venv 中安装。

`ev-gnomad-constraint` / `ev-pp2` 的 `query_constraint.py` 仅依赖 Python 标准库（gnomAD GCS 公共存储桶，无需 API 认证）。

## 环境变量（可选）

| 变量 | 用途 | 默认 |
|---|---|---|
| `NCBI_EMAIL` | NCBI E-utilities 联系邮箱（建议设真实邮箱规避限流） | `variant-rating-skill@example.com` |
| `GNOMAD_INSECURE=1` | 仅证书错位时临时降级 SSL 校验 | 严格校验证书（安全优先） |

## 数据与缓存

- gnomAD 约束数据（v4 ≈82MB / v2 ≈13MB）：首次查询落盘到各脚本同目录 `_cache/`，后续直接读缓存；`python query_constraint.py <gene> --refresh` 强制更新。
- VCEP 载体：`clingen-vcep/gene-gn-file-mapping.csv`（131 基因，132 行含表头）+ `narrative-units/`（1721 单元）。⚠ 该载体仅为快速检阅通道，**非最终依据**；每次用到 VCEP 规则必须联网核实 ClinGen cspec 最新版，以数据库最新更新为准。

## 外部依赖与断链说明

- **HGMD**（`hgmd-variant-query`）：商业数据库，未随包提供；需自行采购授权后接入。取数脚本路径由环境变量 `HGMD_QUERY_DIR` 指定（含 `search.py` 的目录）；**未配置时**提示「HGMD 数据缺失」+ 前往配置指引（状态 `missing_config`），**用户确认不配置**可设 `HGMD_SKIP=1` 显式跳过（状态 `skipped_user_opted_out`），均走 ClinVar/文献检索通道并标注、不静默；其余检索通道不受影响。
- **LLM 文献精筛通道**（`ev-variant-literature-patient` 的 `_call_compat_llm`）：文献全文本/摘要的结构化提取（基因型/表型/家系/反式等）依赖一次 LLM 调用。**默认走通用 OpenAI 兼容通道**，通过以下 3 个环境变量配置（任一兼容平台通用：火山方舟 / DeepSeek / 智谱 / Kimi / 通义 / OpenAI 等）：

  | 环境变量 | 说明 | 方舟示例 |
  |---|---|---|
  | `LLM_BASE_URL` | 平台 OpenAI 兼容 base_url | `https://ark.cn-beijing.volces.com/api/v3` |
  | `LLM_MODEL` | 模型名 / 接入点 ID | `deepseek-v4-1-flash-261017`（或 `doubao-seed-2-1-pro-260628`） |
  | `LLM_API_KEY` | 平台 API Key | `ark-<你的Key>` |

  **模型选择建议**：文献精筛属**长文本 + 结构化 JSON 输出**任务，推荐——
  - 轻量快 / 省：`deepseek-v4-1-flash` 系列（flash 档，性价比高，默认首选）；
  - 更强提取：`doubao-seed-2-1-pro` / `deepseek-v4-pro`（豆包 pro / DeepSeek pro，提取更稳、token 成本更高）；
  - 按实际输出质量与预算在 `LLM_MODEL` 处切换即可，无需改代码。

  **方舟 Key 获取**：登录 [火山引擎控制台](https://console.volcengine.com/ark) → 开通方舟 → 左侧「API Key 管理」→ 创建 API Key（`ark-` 开头，仅显示一次）；方舟按 token 用量单独计费，不包含在豆包会员套餐。

  **⚠ 红线**：
  - **本技能包不内置任何 API Key，密钥一律走环境变量，禁止随包分发**（代码 v1.4.0 起已移除内置兜底 key）；
  - 旧默认端点 `ep-20260106113130-tj2pt` 为私有付费端点，非通用可用；使用前必须替换为自有可用 endpoint，否则按"查不到"出口处理，不得静默用默认值；
  - **LLM 闸门（v1.5.0，不静默出口的强制实现）**：LLM 未配置或调用失败时，**禁止静默降级为关键词过滤**——技能会**硬中断**（`LLMConfigError`，退出码 2），在错误信息中携带完整配置指引（3 个环境变量、方舟/DeepSeek 获取路径、配置命令），由承载平台（AI 助手/宿主）读取后引导用户配置 KEY，配置完成后重跑即正常使用。**任何平台安装均适用**（引导信息随异常文本走，不依赖豆包专有能力）。
  - 例外：文献量 ≥50 篇时走**关键词快速过滤**（`_post_filter_results`），该分支不依赖 LLM，不受闸门影响。

## 目录结构

```
acmg-total-scheduler/           总调度
acmg-conflict-summary-output/   收尾
arad-inheritance-judgment/      遗传方式前置
clingen-vcep/                   VCEP 载体（映射表 + narrative-units + knowledge-base；**另包**：独立 VCEP 数据包 v1.1.0，主包 ZIP 不含，需单独部署到技能群根同级后方可跑 VCEP 相关门禁/评级）
ev-*/                           证据码子技能（各含 SKILL.md [+ 脚本 + CHANGELOG.md]）
requirements.txt / README.md    依赖与说明（随包分发）
```

## 随包门禁与自检（v5.2.0 起随包交付）

以下回归/评测/契约工具**随包分发**，解压即可在包内自检（相对路径，不依赖构建环境）：

| 文件 | 作用 | 运行 |
|---|---|---|
| `config/golden.json` | 双尺子金标准（39 条，methodA 经典联合 / methodB 分值；暂用版，随金标准更新重建） | 评测输入快照 |
| `scripts/combination_eval.py` | 组合层分口径评测（同尺子对同尺子：engine_a vs methodA / engine_b vs methodB） | `python scripts/combination_eval.py`（默认读 config/golden.json） |
| `scripts/regression_gate.py` | 回归门禁：穷举 328 对照 + 引擎/CLI 冒烟 + 39 集双尺子评测（SKIP>0 视为失败）+ 版本一致性 | `python scripts/regression_gate.py` |
| `scripts/contract_test.py` | L1→L2 输入契约测试（官方裁定形态 / 复合码方向） | `python scripts/contract_test.py` |
| `scripts/test_llm_gate.py` | LLM 闸门契约测试（G1-G5：缺 KEY 抛 `LLMConfigError` 含指引 / 通用+方舟双通道放行 / LLM 全失败中断 / ≥50 篇关键词分支不误伤） | `python scripts/test_llm_gate.py` |
| `scripts/test_extraction_validation.py` | LLM 提取校验层契约测试（V1-V8：C1 枚举合法性 / C2 内部一致性 / C3 ClinVar 基线核对，只标注不编答案） | `python scripts/test_extraction_validation.py` |
| `scripts/check_vcep_structure.py` | clingen-vcep 全量结构化校验（C1 四段完整性 / C2 主文件骨架 / C3 三方基因对齐 / C4 声明一致性），产出 `reviews/vcep_structure_<date>.md/.json` | `python scripts/check_vcep_structure.py` |
| `reviews/` | 结构化校验产物（`vcep_structure_*.md/.json`；群级复审报告未随包） | 随包检视资产 |
| `scripts/golden_builder.py` | golden.json 生成说明（输入 39 变异集仅在构建环境，重建时指明输入路径） | 构建侧工具 |
| `sync-manifest.md` | **变更同步载体清单**：改任何"口径/枚举/识别串/契约"前先读它（confidence 边界 / interval 枚举 / 官方识别串 / BA1 门控 / 版本号 / 可疑文献 / 提交门禁 七组），防"改了数据层漏了文档层"连续复发 | **随包治理资产，改前必读** |

- 一致率声明以随包 `config/golden.json` 为基准，解压后运行 `scripts/combination_eval.py` 即可复现。
- **一致率双分母（口径诚实，v5.5.6）**：39 集暂用金标准实测——**表5一致率 93.8%（15/16，仅 basis=Table5 精选子集）/ 全量不筛 basis 51.3%（20/39）**；**分值一致率 97.1%（34/35，剔除 VCEP 官方 4 条）/ 官方遵循率 100%（4/4）**；两套引擎 agreement **97.4%（38/39）**。并列"精选/全量"与"含官方/剔除官方"分母，不写单一高值；官方裁定条目按最高真值层单独统计（只验证"技能群是否优先采官方"），不混入引擎一致率。**（注：`1VS+1SU → LP` 为 v5.5.6 起用户拍板采纳的补充口径（(i′)，属 ACMG Table 5 之外的工程化补充、非官方 Table 5 条目），引擎已采纳（`acmg_combine.py` `_classic_likely_pathogenic`(i′)），agreement 97.4%（38/39）；此前 P0-4 曾按"无 Table 5 出处"删除致 agreement 回落 66.7%（26/39），经用户拍板重新采纳保留。）**
- **口径声明（agreement=自洽率，非准确率，技能群整体评估 W2，2026-10-16）**：上表全部"一致率"是**两套引擎（表5 vs Tavtigian 分值）之间的自洽率**，即"双引擎对同一输入的结论是否一致"，**不是与 ClinGen/权威裁定的符合率（准确率）**；两套引擎同时偏离正确答案时自洽率仍会偏高。技能群当前**尚无"与权威裁定对比"的 hold-out 基准集**（W2，待用户自备数据集后建立）。**对外引用一律表述为"双引擎自洽率"，不得称"准确率"**；官方遵循率（4/4）是"是否优先采官方裁定"的流程遵循率，同样不是变异分类准确率。
- 打包门禁（`build_package` 五闸：README 数字 + 嵌句检测 + py_compile + 契约测试 + 回归门禁）**仅在构建环境**运行，不随包（构建产物不含构建脚本）。

## 整改记录（2026-10-15）

- 各技能 version 变更日志已从 SKILL.md frontmatter 下沉至各技能目录 `CHANGELOG.md`，description 精简为职责+触发（≤300 字符）。
- 可疑文献 L1/L2/L3 判定标准唯一收敛至 `ev-variant-literature-patient`，其余子技能仅单点引用。
- gnomAD 查询恢复 SSL 证书校验 + 落盘缓存；NCBI 联系邮箱改为环境变量。
