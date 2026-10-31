# dsh-acmg-skill — ACMG 变异评级技能群 · DeepSeek Harness 挂载包

把现有的《变异评级技能群 v1.2.4.4（22 个 SKILL + Python 取数脚本）》挂到
[DeepSeek Harness（dsh）](https://github.com/deepseek-ai/dsh) 上。装上之后，dsh 这个"总管"
会读到一份**身份说明书**，知道有一位"ACMG 变异评级专家群"、什么时候该找它、怎么按 22 个子技能
编排；另外给一个**环境自检工具** `acmg_env_check`，开跑前先确认 Python/依赖/文件/Key 就位。

> 这是"方法论编排型 + Python 取数型"技能包，和纯 JS 单工具的 TACT 包性质不同：
> 真正逐码评级的编排和取数脚本**原样保留在 `skills/acmg-variant-rating/` 里，一行没改**，
> dsh 负责读懂说明书、用自带的 bash/pwsh 工具去跑这些 Python 脚本。

---

## 0. 包里有什么

```
dsh-acmg-skill/
├─ package.json                 # 组合包清单（dsh.bundle.patch 指向补丁文件）
├─ cordis.patch.yml             # 挂载补丁（改两处绝对路径即可）
├─ skill.js                     # 插件一：把身份说明书注册为 bundled skill（调度模型可读/可触发）
├─ index.js                     # 插件二：注册 acmg_env_check 环境自检工具（纯 Node）
├─ README.md
└─ skills/
   └─ acmg-variant-rating/      # ★ 原始技能群整包，未改动
      ├─ SKILL.md               # ★ 身份说明书 + 22 子技能路由图（本包新增/重写的入口）
      ├─ README.md / CHANGELOG.md / LICENSE / requirements*.txt
      ├─ acmg-total-scheduler/  # 总调度（执行契约、三表、三开关、强制 27 字段）
      ├─ acmg-conflict-summary-output/
      ├─ arad-inheritance-judgment/
      ├─ ev-*/                  # 19 个证据/取数技能（各含 SKILL.md + Python 脚本）
      ├─ scripts/               # 共享确定性引擎（acmg_evidence/acmg_combine，727 单测）
      ├─ config/                # 知识图 + 四套阈值表
      └─ tests/ check_hashes.py check_skills.py
```

两个插件各干一件事：

| 插件文件 | 注册 | 作用 |
| --- | --- | --- |
| `skill.js` | 一条 bundled skill `acmg-variant-rating` | 让总管读到身份说明书，并能顺路径引用群里全部 22 个子技能、`scripts/`、`config/` |
| `index.js` | 一个工具 `acmg_env_check` | 评级前自检 Python、requests/pyliftover、群文件、环境变量，缺什么直接给补缺命令 |

> 没有把"跑 Python"再做成一个工具——dsh 自带 `bash`/`pwsh`/`fs` 等工具，总管读说明书后
> 直接用它们执行群内脚本即可。取数脚本走标准 OpenAI/HTTP，不依赖 Coze 平台。

---

## 1. 先满足两个运行前提

### ① Node ≥ v22.18（跑 dsh 本体）

dsh 的入口用了 `import.meta.main`（Node **v22.18** 才加入）。本机若是更早的 v22.x，
`dsh` 会双击后静默退出、无任何输出。请到 <https://nodejs.org> 升级到 **22 LTS 最新版**（≥22.18）。
自检：`node --version`。

### ② Python 3 + 两个 pip 依赖（跑取数脚本）

技能群的取数脚本是 Python。需要：

```powershell
# 装好 Python 3.13（安装时勾选 Add Python to PATH）后，在本包 skills/acmg-variant-rating 目录：
python -m pip install -r requirements.txt
```

依赖（见 `requirements.txt`）：

- `requests>=2.31` —— ClinVar / NCBI / 文献 / 基因身份 / 疾病 / 遗传方式等 HTTP 取数；
- `pyliftover>=0.4` —— 变异归一化的 hg19↔hg38 坐标转换。

> gnomAD 约束查询（PP2/BP1）用纯标准库，不装 requests 也能跑；其余取数需要。
> 不确定环境齐不齐？挂上后直接让 dsh 调 `acmg_env_check`，它会逐项报告并给出补缺命令。

---

## 2. 挂载（两种方式任选）

### 方式 A：组合包（推荐）

1. 解压本包；
2. 打开 `cordis.patch.yml`，把两处 `<绝对路径>` 改成本包解压目录的**绝对路径**（用正斜杠 `/`）。
   例如 Windows：`name: 'file:///C:/Users/me/dsh-acmg-skill/skill.js'`；
3. 在本包目录执行（dsh 会读 `package.json` 里的 `dsh.bundle.patch`）：

```bash
dsh plugin add .
dsh web
```

### 方式 B：直接用补丁文件

```bash
dsh web --patch cordis.patch.yml
```

### 方式 C：本地开发（不装包）

```bash
dsh web --patch /你的路径/dsh-acmg-skill/cordis.patch.yml
```

---

## 3. 配环境变量

- `NCBI_EMAIL`（强烈建议）：NCBI E-utilities 联系邮箱，未设则用中性占位邮箱、易被限流；
- `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`（可选）：文献证据码 LLM 精筛要用；未配置时该步骤
  会硬中断并给配置指引，**不阻塞其他证据码**；
- `HGMD_QUERY_DIR`（可选）：HGMD 商业库本地查询目录。不随包、不内置；没有就走 ClinVar/文献通道
  并在报告中标注；纯公开库验证可设 `HGMD_SKIP=1`。

> 这些变量只在运行时从环境读取，不写进包、不入库。

---

## 4. 怎么用

1. 先让总管做环境自检（或直接说"先检查评级环境"）：它会调用 `acmg_env_check`；
2. 环境就绪后，直接给一个具体变异，例如：
   > 帮我给 BRCA1 c.5266dupC（p.Gln1756ProfsTer74）做 ACMG 评级
3. 总管读身份说明书 → 进 `acmg-total-scheduler` 契约 → 按"身份归一化→遗传前置→圈码→逐码判定
   （用 bash/pwsh 跑对应 ev-* 的 Python 脚本）→ 互斥消解 → 收尾技能双套定级出报告"。

报告由 `acmg-conflict-summary-output` 输出，固定 27 字段、"表5 主结论 + Tavtigian 交叉核对"双套、
强制列"未达强度证据"，证据来源可回溯。**给证据不给最终临床结论**，结尾标注"智能分析结果，仅供参考"。

---

## 5. 与 TACT 包的关系（将来多技能并存）

- 本包 = **变异评级专家群**（给某个具体变异定致病性，P/LP/VUS/LB/B）；
- TACT 包 = **AI 系统错误定位专家**（给 AI 的翻车现象定三轴坐标）。
- 两者各自带"身份说明书"，触发边界互不重叠，可同时 `--patch` 挂给同一个 dsh。
  将来系统级调度说明书只需把各包 `SKILL.md` 开头的"何时用/何时别用"收编做组级路由。

---

## 6. 已知边界 / 别踩坑

- **clingen-vcep 是独立另包**，不在本包内（共 23 个 SKILL，本包含 22）。缺少它时，基因特异规则
  这一步必须在报告里显式标注"未查阅 VCEP 特异规则"，不能默默跳过。
- 本机实测：系统 PATH 若只有微软商店的 Python 占位符，`python` 会打开商店而非运行脚本；
  请装真正的 Python 并加入 PATH（或用 Coze 桌面运行时里的 Python，但要给它补装 requests/pyliftover）。
- `coze_workload_identity.py` 只是个 `requests` 转发垫片，不依赖 Coze 平台，普通命令行即可运行。
- 评级质量相关的已知限制（HGMD 商业库、部分站点不可达等）以技能群 `README.md` / `CHANGELOG.md` 为准。
