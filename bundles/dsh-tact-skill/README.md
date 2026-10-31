# TACT 三轴坐标定位 · DeepSeek Harness 技能包

> 一个标准 dsh **组合包（bundle）**：挂上之后，dsh 同时得到一个「会动手的专家」和一份「身份说明书」。
>
> - **会动手的专家**：工具 `tact_locate`——你给它一段 AI 翻车现象，它逐坐标调大模型判定，输出 TACT 三轴定位五项报告。
> - **身份说明书**：技能 `tact-three-axis-check`——告诉 dsh 的调度大模型「我是谁、什么时候该叫我、什么时候别叫我、坐标怎么辨析」。

智能分析结果，仅供参考。

---

## 0. 一句话理解这个包

你之前设想的架构是：**dsh 当总管，很多技能包当专家，每个专家配一份身份说明书**。
这个包就是按这个规范做出的第一个样板——一个目录、装一次，「说明书」和「动手工具」一起挂上，总管该用时会自动叫工具。

## 1. 包里有什么

```
dsh-tact-skill/
├── package.json                       # 组合包清单（声明 dsh.bundle.patch）
├── cordis.patch.yml                   # 挂载补丁（说明书 + 工具 两个入口）
├── index.js                           # 工具插件：注册 tact_locate（会动手）
├── skill.js                           # 说明书插件：把 SKILL.md 注册为 bundled skill
├── tact-core.cjs                      # 判定核（与 HTML 版/Python 版同一份逻辑）
├── README.md                          # 本文件
├── references/
│   ├── coordinate_data.json           # 坐标底座 v2.7.9（L4/M9/P8，117 精细坐标）
│   └── coord_snapshot.md
└── skills/
    └── tact-three-axis-check/         # 完整 TACT 技能（说明书本体 + 全套参考）
        ├── SKILL.md                   # 身份说明书（方法论全文，v1.1.5）
        ├── guard/MANIFEST.json        # 哈希自验
        └── references/、docs/         # 三轴细则、坐标表、校准用例 CAL-01~29 等
```

## 2. 运行前提

- **Node.js ≥ 22.18.0（必须）**
  dsh 0.2.1 用了 `import.meta.main`，它在 Node **v22.18.0 才加入**。用更老的 Node（例如 22.13）直接跑 `dsh` 会**静默退出、什么都不显示**。已在便携 Node v22.20.0 上真机验证通过。
  检查版本：`node --version`；版本低就到 nodejs.org 升级到 22 LTS 最新版。
- 已安装 dsh：`npm i -g @deepseek-ai/dsh@0.2.1-rc.2`（或用 `npx @deepseek-ai/dsh`）。
- 一个火山方舟（豆包）大模型 API Key（OpenAI 兼容接口）。

## 3. 挂载（两种方式，二选一）

### 方式 A：补丁挂载（开发 / 本地目录，最简单）

1. 把本包解压到一个固定位置，复制其**绝对路径**。
2. 编辑本包根目录的 `cordis.patch.yml`，把两个 `<绝对路径>` 都替换成真实路径（注意用正斜杠 `/`）：

   ```yaml
   - insert:
       - id: dsh-tact-skill-skill
         name: 'file:///D:/my-skills/dsh-tact-skill/skill.js'
       - id: dsh-tact-skill-tool
         name: 'file:///D:/my-skills/dsh-tact-skill/index.js'
   ```

3. 启动时带上补丁：

   ```bash
   dsh web --patch "D:/my-skills/dsh-tact-skill/cordis.patch.yml"
   # 无界面跑一次也可以：
   dsh headless --patch "D:/my-skills/dsh-tact-skill/cordis.patch.yml" "帮我给这个 AI 错误定个 TACT 坐标：……"
   ```

### 方式 B：作为插件安装（发布到本地/私有 registry 后）

`package.json` 已声明 `dsh.bundle.patch`，安装后 dsh 自动读组合包补丁，无需手动改路径：

```bash
dsh plugin add dsh-tact-skill      # 发布后；本地目录也可试 dsh plugin add ./dsh-tact-skill
```

## 4. 配 Key（工具直连火山方舟）

工具本身是确定性的「逐坐标调用 + 汇总」，每次判定要请一个大模型投票，因此需要 Key。设一个环境变量即可（不写进代码、不进包）：

- Windows PowerShell（当前会话）：
  ```powershell
  $env:TACT_ARK_API_KEY = "你的火山方舟 API Key"
  ```
  永久生效：`[Environment]::SetEnvironmentVariable("TACT_ARK_API_KEY","你的Key","User")`
- macOS / Linux：
  ```bash
  export TACT_ARK_API_KEY="你的火山方舟 API Key"
  ```

可选环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TACT_ARK_API_KEY` | 无（必填） | 火山方舟 API Key |
| `TACT_ARK_BASE_URL` | `https://ark.cn-beijing.volces.com/api/v3` | OpenAI 兼容端点 |
| `TACT_ARK_MODEL` | `doubao-seed-2-1-pro-260628` | 判定用模型 |
| `TACT_CONCURRENCY` | `4` | 并发判定数 |

> 工具默认对豆包深度思考模型发 `thinking:{type:"disabled"}`，把单坐标判定从约 100 秒压到约 3 秒，结论一致。Key 没配 / 401 会**立刻报错提示**，不会傻等。

## 5. 怎么用

挂上、配好 Key 后，直接用大白话对 dsh 说，比如：

> 「帮我用 TACT 给这个现象定坐标：模型把我的反问当成新指令去执行了。」

总管（调度大模型）读到说明书后会自己调用 `tact_locate`，工具对原文跑完整流程：**前置排除闸（E1-E4）→ L 轴 → M/P 轴先判母后判子（母否剪整组、母是开闸判子）**，最后给出五项报告：①完整坐标+三母名 ②L轴理由 ③命中子坐标（含义/表现/位置/验证）④反问+剪枝双留痕 ⑤判不了/按闸排除/过闸空组。

一次约 2 分钟（实判约 50 个坐标、母闸剪掉约 80 个）。

## 6. 给将来「系统级调度 skill」的路由提示

这个包的身份说明书（`SKILL.md` 开头）已经写清了**触发条件**和**互斥边界**：

- 该叫我：一段**已发生的具体 AI 失败/错误现象**，要判类型、定 L/M/P 坐标、拿验证路径。
- 别叫我：空泛感想 / 怎么把系统做好（找规范） / 人类决策（找报告解读） / 事实问答（找检索） / 通用编程问题（找编程技能）。
- 前置排除闸：**E1 治理 / E2 环境 / E3 预测 / E4 评测**四类不占坐标，命中直接按闸排除。

将来做总管的系统级调度宪法时，把每个技能包说明书里的这两段收进去做组级路由即可。

## 7. 验证情况（真机）

- Node v22.20.0 便携版 + `@deepseek-ai/dsh@0.2.1-rc.2`，官方入口 `dsh headless/web` 正常加载，本包两个插件均成功激活、无报错。
- 工具 `tact_locate` 真实注册（参数 JSON Schema 校验生效，缺 `phenomenon` 被拦截）。
- 身份说明书真实注册为 bundled skill（modelInvocable + userInvocable），正文为 v1.1.5 方法论全文。
- 真实火山 Key 端到端跑通校准用例 **CAL-01**：golden 坐标 **M6-8、P1-8 全中、L 轴为空正确**，前置闸过闸，母→子剪枝与五项留痕齐全。
- 已知模型层现象（非本包缺陷）：该模型偏宽，会**多报 M6-1、M6-4、P8-8**，与此前 HTML 版/Python 版结果完全一致，属后续提示词调优项，需攒判例、跑全量 29 条校准。

## 8. 安全 / 隐私

- Key 只从环境变量读，不写进代码、不写进包、不进日志；数据只在你本机和火山端点之间传输。
- 工具只对你提供的文本做只读判定，不执行任何写操作。
- 坐标底座与方法论为内部研究工具，输出带「智能分析结果，仅供参考」；不直接给医疗 / 生产事故的最终结论。

## 9. 版本

- 组合包：v1.1.5
- 身份说明书逻辑版本：v1.1.5（坐标底座 coordinate_data.json / 校准用例 calibration_cases.json 哈希与 v1.1.4 相同，未改动）
- 坐标底座：coord_snapshot v2.7.9
