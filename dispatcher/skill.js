/*
 * 总管调度说明书 · bundled skill provider
 * 注册 chief-dispatcher：系统级路由说明书，供 dsh 调度模型在分诊时优先参考。
 * 与两个专家包（tact / acmg）的身份说明书并列，不替代它们的业务说明书。
 */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { BUNDLED_SKILL_RANK } from '@deepseek-ai/dsh-skill';

const PROVIDER_NAME = 'dsh-chief-dispatcher';
const SKILL_BODY_URL = new URL('./skills/chief-dispatcher/SKILL.md', import.meta.url);
const RESOURCE_BASE = {
  kind: 'directory',
  path: fileURLToPath(new URL('./skills/chief-dispatcher/', import.meta.url)),
};
const SKILL_NAME = 'chief-dispatcher';
const SKILL_DESCRIPTION =
  '总管调度说明书（系统级路由宪法）：用户请求进入后先据此分诊——该交给 TACT 三轴坐标定位专家（AI 系统出错现象分类，工具 tact_locate）还是 ACMG 变异评级专家群（具体基因变异致病性，工具 acmg_env_check 自检后按总调度评级），或总管自答/声明未挂载。含两类任务判别表、路由决策树、跨专家仲裁、证据与免责纪律，以及将来新增专家的扩展规则。';

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
  async get() {
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

export const name = 'dsh-chief-dispatcher-skill';
export const inject = ['skills'];

export function apply(ctx) {
  ctx.skills.registerProvider(() => provider);
  ctx.logger?.info?.('[chief-dispatcher] 总管调度说明书已作为 bundled skill 注册');
}
