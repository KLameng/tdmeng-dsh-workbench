/*
 * ACMG 变异评级技能群 · bundled skill provider（官方 @deepseek-ai/dsh-skill-badge 同款范式）
 * ----------------------------------------------------------------------------
 * 把 skills/acmg-variant-rating/SKILL.md（身份说明书 + 22 子技能路由图）注册为一条
 * bundled 技能；resourceBase 指向整个技能群根，使调度模型能顺引用全部 ev-* 子技能、
 * scripts/ 引擎、config/ 知识图与阈值表。取数脚本由 dsh 自带 bash/pwsh 工具执行，
 * 本插件只负责"把整套说明书挂上、把环境讲清"，不重复造执行工具。
 */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { BUNDLED_SKILL_RANK } from '@deepseek-ai/dsh-skill';

const PROVIDER_NAME = 'dsh-acmg-skill';
const SKILL_BODY_URL = new URL(
  './skills/acmg-variant-rating/SKILL.md',
  import.meta.url
);
// resourceBase 指向技能群根：身份说明书里的 acmg-total-scheduler/、ev-*/、scripts/、config/ 相对它解析
const RESOURCE_BASE = {
  kind: 'directory',
  path: fileURLToPath(new URL('./skills/acmg-variant-rating/', import.meta.url)),
};

const SKILL_NAME = 'acmg-variant-rating';
const SKILL_DESCRIPTION =
  '孟德尔疾病基因序列变异的 ACMG/AMP 2015 致病性分类技能群（22 个 SKILL：总调度 acmg-total-scheduler + 收尾 acmg-conflict-summary-output + 遗传方式前置 arad-inheritance-judgment + 19 个 ev-* 证据/取数技能）。' +
  '给定基因名+cDNA/蛋白改变（或 rsID/ClinGen CA ID/坐标），按 身份归一化→AD/AR遗传前置→按变异类型圈证据码→逐码判定(PVS1/PS/PM/PP/BS/BP/BA1)→互斥消解→表5+Tavtigian双套定级 出 P/LP/VUS/LB/B。' +
  '当用户要给某个具体变异做 ACMG 评级、判致病性、列证据码、查频率/计算预测/功能/文献证据时调用。触发词：ACMG评级、变异评级、致病性分类、证据码、这个变异致不致病、PVS1/PS1/PM2/PP3/BS1。' +
  '不含 SF 次要发现报出/WES 报出/PGT-M 决策（属另一个携筛咨询群），也不是给 AI 系统错误分类（那是 TACT）。';

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

export const name = 'dsh-acmg-skill-skill';
export const inject = ['skills'];

export function apply(ctx) {
  ctx.skills.registerProvider(() => provider);
  ctx.logger?.info?.('[dsh-acmg-skill] ACMG 变异评级技能群身份说明书已作为 bundled skill 注册（resourceBase=技能群根）');
}
