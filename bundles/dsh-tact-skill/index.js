/*
 * TACT 三轴坐标定位 · DeepSeek Harness 工具插件（组合包入口）
 * ----------------------------------------------------------------------------
 * 把已在 Node/浏览器双端真实验证过的判定核 tact-core.js 注册成一个 dsh 工具：
 *   工具名      tact_locate
 *   干什么      喂入一条 AI 系统失败/错误现象，逐坐标 LLM 判定，跑三步法
 *               （前置排除闸 → L 轴 → M/P 先母后子过闸剪枝），产出五项报告。
 * 判定逻辑      100% 在 tact-core.js，与单文件 HTML 版、Python 管线逐字对齐；
 *               本文件只负责"接平台"：读底座、发 HTTP、把工具参数喂给判定核。
 * 模型/密钥     直连火山方舟 OpenAI 兼容端点；Key 不落盘、不进日志。读取优先级：
 *               ① 程序「设置」里托管的凭据 VOLC_ARK_API_KEY（在界面填，最高优先）
 *               ② 环境变量 TACT_ARK_API_KEY / ARK_API_KEY / VOLC_APIKEY（含 home/.env，兜底）。
 * 平台差异      与 HTML 版唯一相同的差异点就是 chatOnce（怎么发 HTTP）。
 */
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { credentialRef } from '@deepseek-ai/dsh-credentials';

const require = createRequire(import.meta.url);
// 用 .cjs 后缀强制 CommonJS 加载（本包 package.json 是 type:module，.js 会被当 ESM，
// 同步 require ESM 会让 UMD 的浏览器分支拿到 undefined 的 this）。判定核内容一字未改。
const TACT = require('./tact-core.cjs');

// 坐标底座（与 HTML 版 coord_snapshot 逐字节一致，v2.7.9：L4 / M9 / P8）
const SNAP = JSON.parse(readFileSync(new URL('./references/coordinate_data.json', import.meta.url), 'utf8'));

export const name = 'dsh-tact-skill';
export const inject = ['tools', 'credentials'];

// 由 apply 注入的凭据服务；拿不到时（极旧宿主）退回纯环境变量模式
let credentialsSvc = null;

// 取一次火山 Key：界面托管凭据优先，环境变量（含 home/.env）兜底。
// 凭据服务要求"每次操作现取、不要跨操作缓存"，这样用户改完 Key 下一次判定立即生效。
async function resolveArkKey() {
  if (credentialsSvc) {
    try {
      const r = await credentialsSvc.resolve(credentialRef('VOLC_ARK_API_KEY'));
      if (r && r.value) return r.value;
    } catch {
      // 凭据服务异常时静默落到环境变量，不阻断
    }
  }
  return process.env.TACT_ARK_API_KEY || process.env.ARK_API_KEY || process.env.VOLC_APIKEY || '';
}

const ARK_CHAT_URL =
  (process.env.TACT_ARK_BASE_URL || 'https://ark.cn-beijing.volces.com/api/v3') +
  '/chat/completions';
const DEFAULT_MODEL = process.env.TACT_MODEL || 'doubao-seed-2-1-pro-260628';

// 平台注入点：单次对话调用。关闭深度思考（该模型开思考单坐标 90s+ 必超时）。
async function chatOnce(messages, model, opts) {
  if (authFailed) { authFailed.noretry = true; throw authFailed; } // 已确认 Key 无效：直接失败，绝不退避重试
  const key = await resolveArkKey();
  if (!key) {
    const e = new Error(
      '未配置火山方舟 API Key。请在程序「设置 → 模型」里为火山方舟（volc-ark）填写 API Key 后重试。'
    );
    e.noretry = true; // 配置错误，立即失败、不退避
    throw e;
  }
  const payload = {
    model: model || DEFAULT_MODEL,
    messages,
    max_tokens: 2000,
    temperature: 0.0,
  };
  if (!opts || opts.disableThinking !== false) payload.thinking = { type: 'disabled' };

  const resp = await fetch(ARK_CHAT_URL, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (resp.status === 401) {
    authFailed = new Error('API Key 无效或无权限（401），请到「设置 → 模型」检查火山方舟 API Key；已熔断后续判定。');
    authFailed.noretry = true;
    throw authFailed;
  }
  if (resp.status === 429) throw new Error('触发限流（429），判定核会自动退避重试');
  if (!resp.ok) {
    const t = await resp.text().catch(() => '');
    throw new Error('火山接口返回 HTTP ' + resp.status + ' ' + t.slice(0, 160));
  }
  const j = await resp.json();
  const m = (j.choices && j.choices[0] && j.choices[0].message) || {};
  return m.content || m.reasoning_content || '';
}

// 认证熔断：一旦收到 401，说明 Key 全局无效，后续所有坐标立即失败、不再空耗退避重试。
let authFailed = null;

export function apply(ctx) {
  credentialsSvc = ctx.credentials || null;
  ctx.tools.register(
    defineTool({
      name: 'tact_locate',
      description: [
        '用 TACT 三轴坐标分类法，给一条「AI 系统 / 大模型 / 智能体的失败、错误、异常现象」定位坐标。',
        '适用：用户描述了某个 AI 行为出问题（答错、编造、拒答、流程跑偏、评估与生产不一致、多智能体协作失败等），',
        '想知道它"在哪一层犯(L轴)、怎么错的(M轴)、破坏了哪一面(P轴)"，需要逐坐标严谨判定并留痕时调用。',
        '输入是一条完整的现象原文；工具会自己跑完前置排除闸、L轴、M/P母→子剪枝，直接返回五项 Markdown 报告。',
        '不要用于：与 AI 失败无关的普通问题；E1数据治理/E2环境/E3纯预测/E4纯评测方法学四类（会被前置闸按闸排除）。',
      ].join(''),
      parameters: {
        phenomenon: {
          type: 'string',
          required: true,
          description: '待定位的 AI 失败/错误/异常现象原文，尽量保留具体表现、上下文和触发条件。',
        },
        model: {
          type: 'string',
          description:
            '可选，逐坐标判定使用的火山方舟模型 ID/接入点 ID。默认 ' + DEFAULT_MODEL + '。',
        },
        concurrency: {
          type: 'number',
          description: '可选，同组子坐标的并发判定数，默认 4（降低限流概率）。',
        },
      },
      output: {
        schema: { type: 'string' },
        render: (_args, value) => [{ type: 'text', text: String(value) }],
      },
      async execute(args, exec) {
        const text = String(args.phenomenon || '').trim();
        if (!text) throw new Error('phenomenon 不能为空，请提供待定位的 AI 失败现象原文。');

        // 前置查 Key：配置错误 0ms 秒败，不跑完整轮再给废报告（界面托管凭据优先）
        const preKey = await resolveArkKey();
        if (!preKey) {
          throw new Error(
            '未配置火山方舟 API Key。请在程序「设置 → 模型」里为火山方舟（volc-ark）填写 API Key 后重试。'
          );
        }

        // 致命错误熔断：401 等不可恢复错误一旦出现，立即中止整轮并向上抛（区别于用户主动取消）。
        let fatal = null;
        const guardedChat = async (messages, model, opts) => {
          try {
            return await chatOnce(messages, model, opts);
          } catch (e) {
            if (e && e.noretry) fatal = e;
            throw e;
          }
        };

        const state = await TACT.runJudge(SNAP, text, {
          chatOnce: guardedChat,
          model: args.model || DEFAULT_MODEL,
          concurrency: args.concurrency || 4,
          // 工具内调用：起手节奏从 2s 收到 0.5s，整轮更快；退避冷却保持
          baseSleep: 500,
          retries: 3,
          cooldown: [15000, 30000, 60000],
          disableThinking: true,
          // 致命配置错误或用户在 dsh 里点停止：都让判定核尽快收住
          shouldCancel: () =>
            !!fatal || !!(exec && exec.signal && exec.signal.aborted),
        });

        // 因致命错误中止：抛给用户明确的配置/鉴权原因，而不是返回"全判不了"的报告
        if (state.cancelled && fatal) throw fatal;

        const report = TACT.renderFive(
          state.hitCodes,
          SNAP,
          state.results,
          state.gateInfo,
          state.mothersHit
        );

        const gateLine = state.gateInfo.llm_excluded
          ? '前置语义闸：按闸排除（' + (state.gateInfo.llm_gate_class || '未归类') + '）'
          : '前置语义闸：过闸';
        const trace =
          '---\n' +
          '**运行留痕**：' +
          gateLine +
          '；实判 ' + state.judgedCount +
          ' · 剪枝 ' + state.pruned.length +
          ' · 判不了 ' + state.unreadable.length +
          (state.cancelled ? ' · （已被中途取消，结果不完整）' : '') +
          ' · 模型 `' + state.model + '`';

        // renderFive 末尾自带一次免责声明；把运行留痕插到免责之前，全文只在最后出现一次免责
        const body = report.replace(/\n*>\s*智能分析结果[，,]仅供参考。?\s*$/, '');
        return body.trimEnd() + '\n\n---\n' + trace + '\n\n> 智能分析结果，仅供参考。\n';
      },
    })
  );

  ctx.logger?.info?.('[dsh-tact-skill] tact_locate 工具已注册（坐标底座 ' + SNAP.version + '）');
}
