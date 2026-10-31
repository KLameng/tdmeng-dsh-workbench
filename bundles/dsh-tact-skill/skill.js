/*
 * TACT 身份说明书 · bundled skill provider（官方 @deepseek-ai/dsh-skill-badge 同款范式）
 * ----------------------------------------------------------------------------
 * 把 skills/tact-three-axis-check/SKILL.md 作为一条 bundled 技能注册进 ctx.skills，
 * 调度大模型在系统提示阶段就能读到「何时调用 tact_locate / 何时别调用 / 坐标辨析」，
 * modelInvocable + userInvocable 全开，无需用户手动把技能目录复制到 $DSH_HOME/skills。
 * 工具的确定性编排见 index.js；本文件只负责"把说明书挂上去"。
 */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { BUNDLED_SKILL_RANK } from '@deepseek-ai/dsh-skill';

const PROVIDER_NAME = 'dsh-tact-skill';
const SKILL_BODY_URL = new URL(
  './skills/tact-three-axis-check/SKILL.md',
  import.meta.url
);
// resourceBase 指向技能目录，使 references/、docs/ 等资源相对链接有根
const RESOURCE_BASE = {
  kind: 'directory',
  path: fileURLToPath(new URL('./skills/tact-three-axis-check/', import.meta.url)),
};

const SKILL_NAME = 'tact-three-axis-check';
const SKILL_DESCRIPTION =
  '用 TACT 三轴坐标分类法（L轴=在哪一层犯 / M轴=怎么错的 / P轴=破坏了哪一面）给 AI 系统的失败、错误、异常现象定位坐标。' +
  '当用户描述一个 AI/大模型/智能体的具体翻车现象、异常输出或事故，想判断错误类型、定位 L/M/P 三维坐标、拿验证路径时，' +
  '直接调用 tact_locate 工具并把现象原文原样传入。触发词：定坐标、这是什么错误、TACT、三轴、L轴M轴P轴、错误归类、失败模式定位、验证路径。';

// 去掉文件里的 YAML frontmatter（bundled 技能的描述以本文件 CANDIDATE.description 为准）
function stripFrontmatter(md) {
  const m = /^---\r?\n[\s\S]*?\r?\n---\r?\n?/.exec(md);
  return m ? md.slice(m[0].length) : md;
}

const CANDIDATE = {
  name: SKILL_NAME,
  description: SKILL_DESCRIPTION,
  invocation: { modelInvocable: true, userInvocable: true },
  provider: PROVIDER_NAME,
  source: 'bundled',
  resourceBase: RESOURCE_BASE,
  rank: BUNDLED_SKILL_RANK,
  locator: SKILL_BODY_URL,
};

const provider = {
  name: PROVIDER_NAME,
  list: () => Promise.resolve([CANDIDATE]),
  async get(_candidate) {
    return {
      name: CANDIDATE.name,
      description: CANDIDATE.description,
      invocation: CANDIDATE.invocation,
      provider: CANDIDATE.provider,
      source: CANDIDATE.source,
      resourceBase: RESOURCE_BASE,
      content: stripFrontmatter(await readFile(SKILL_BODY_URL, 'utf8')),
    };
  },
};

export const name = 'dsh-tact-skill-skill';
export const inject = ['skills'];

export function apply(ctx) {
  ctx.skills.registerProvider(() => provider);
  ctx.logger?.info?.('[dsh-tact-skill] 身份说明书 tact-three-axis-check 已作为 bundled skill 注册');
}
