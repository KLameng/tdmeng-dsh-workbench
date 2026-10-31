# Tdmeng dsh 工作台（Td蒙-dsh 工作台）

一个开箱即用的 **DeepSeek Harness (dsh) 本地 AI 工作台**，内置三位专家：**总调度（chief-dispatcher）**、**TACT 三轴坐标定位专家**、**ACMG 变异评级专家**。

双击启动即可在浏览器里用大白话对话，总调度自动把任务派给对应专家。

## 内置专家

| 专家 | 定位 | 工具 |
|---|---|---|
| **总调度 chief-dispatcher** | 系统级路由，判定任务归谁 | 路由决策树 / 跨专家会诊 |
| **TACT 三轴坐标定位** | 给 AI 出错现象定位坐标（L 在哪一层 / M 怎么错 / P 破坏哪一面） | `tact_locate` |
| **ACMG 变异评级** | 给基因变异做致病性证据评级（PVS1/PS/PM/PP 等证据码） | `acmg_env_check` 等 |

## 快速开始

```bash
# 1. 首次安装依赖（需联网）
首次安装依赖.bat
# 或命令行：npm install

# 2. 启动工作台
启动工作台.bat
# 或命令行：node start.js
```

启动后浏览器会自动打开 `http://127.0.0.1:3080`。

> ⚠️ 本仓库不随包内置任何 API Key。请在网页「设置 → 模型」里为「火山方舟（豆包）」粘贴你的 API Key（`sk-` 开头），保存即生效。也可在 `home/.env` 填 `VOLC_ARK_API_KEY=...` 作为备用方式。

## 目录结构

```
tdmeng-dsh-workbench/
├── start.js              一键启动逻辑（动态生成 patch，相对路径，任意位置可运行）
├── dispatcher/           总调度 skill
├── bundles/
│   ├── dsh-tact-skill/   TACT 三轴坐标定位专家
│   └── dsh-acmg-skill/   ACMG 变异评级专家
├── config/               启动时自动生成（可忽略）
├── home/                 本地运行数据（API Key / 会话，不进仓库）
└── node_modules/         运行时依赖（npm install 生成，不进仓库）
```

## 数据与隐私说明

- **不包含 HGMD 商业数据库**。ACMG 专家运行时可走 ClinVar/文献通道并标注来源；若你本地配置了 HGMD，可设 `HGMD_SKIP=1` 跳过。HGMD Professional 为商业授权数据，请遵守其使用条款。
- API Key 仅保存在本机 `home/.credentials.yaml` 或 `home/.env`，不经第三方服务器转发，模型请求直连火山方舟官方接口。分享代码时请勿携带 `home/` 目录。

## License

Apache License 2.0
