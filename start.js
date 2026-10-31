/*
 * Td.蒙 dsh 工作台 · 一键启动器
 * 双击「启动工作台.bat」即运行本脚本：
 *  1) 定位本目录（解压后任意位置均可，无需改路径）；
 *  2) 动态生成指向 总管 + TACT + ACMG 五个插件的 cordis 补丁（绝对 file:// 路径）；
 *  3) 设置 DSH_HOME 到工作台 home（会话/凭据不污染系统）；
 *  4) 调便携 Node 里的 dsh CLI 启动 web，dsh 会自动用默认浏览器打开带一次性 token 的页面。
 */
import { fileURLToPath } from 'node:url';
import { writeFileSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import net from 'node:net';

// 防止重复双击：3080 已在监听说明工作台已经开着
function portInUse(port) {
  return new Promise((resolve) => {
    const tester = net
      .connect(port, '127.0.0.1')
      .once('connect', () => {
        tester.destroy();
        resolve(true);
      })
      .once('error', () => resolve(false));
  });
}

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const HOME = path.join(ROOT, 'home');
const PATCH = path.join(ROOT, 'config', 'cordis.patch.yml');
mkdirSync(path.dirname(PATCH), { recursive: true });
mkdirSync(HOME, { recursive: true });

const p = (rel) => 'file:///' + path.join(ROOT, rel).replace(/\\/g, '/');

// 五个插件：总管说明书 1 + TACT（说明书+工具）2 + ACMG（说明书+工具）2
const entries = [
  ['chief-dispatcher-skill', 'dispatcher/skill.js'],
  ['dsh-tact-skill-skill', 'bundles/dsh-tact-skill/skill.js'],
  ['dsh-tact-skill-tool', 'bundles/dsh-tact-skill/index.js'],
  ['dsh-acmg-skill-skill', 'bundles/dsh-acmg-skill/skill.js'],
  ['dsh-acmg-skill-tool', 'bundles/dsh-acmg-skill/index.js'],
];

const missing = entries.filter(([, rel]) => !existsSync(path.join(ROOT, rel)));
if (missing.length) {
  console.error('缺少插件文件，无法启动：');
  missing.forEach(([id, rel]) => console.error('  - ' + rel + ' (' + id + ')'));
  console.error('\n请确认整包解压完整，不要只复制单个文件。');
  process.exit(1);
}

// 火山方舟路由：预置 OpenAI 兼容端点，模型与 TACT 判定核保持一致；
// Key 不写进本补丁：优先在网页「设置 → 模型」里为火山方舟填写（托管凭据，
// 凭据名固定为 VOLC_ARK_API_KEY，TACT 判定核读的也是同一把）；home/.env 仅作兜底。
const VOLC_PROVIDER = 'volc-ark';
const VOLC_MODEL = process.env.TACT_MODEL || 'doubao-seed-2-1-pro-260628';
const VOLC_BASE = process.env.TACT_ARK_BASE_URL || 'https://ark.cn-beijing.volces.com/api/v3';

const yaml =
  '# 本文件由 start.js 每次启动时自动生成（绝对路径），勿手改\n' +
  '- insert:\n' +
  entries.map(([id, rel]) => `    - id: ${id}\n      name: '${p(rel)}'`).join('\n') +
  '\n' +
  '# —— 预置火山方舟（豆包）模型路由；Key 在网页「设置 → 模型」填，home/.env 仅兜底 ——\n' +
  '- id: llm-pi-ai\n' +
  '  config:\n' +
  '    providers:\n' +
  `      ${VOLC_PROVIDER}:\n` +
  '        displayName: 火山方舟（豆包）\n' +
  "        api: openai-completions\n" +
  '        apiKeyEnv: VOLC_ARK_API_KEY\n' +
  `        baseURL: ${VOLC_BASE}\n` +
  '        models:\n' +
  `          - id: ${VOLC_MODEL}\n` +
  '            name: 豆包 Seed 2.1 Pro\n' +
  '            contextWindow: 256000\n' +
  '            maxTokens: 16384\n' +
  '            input:\n' +
  '              - text\n' +
  '- id: agent-default-model\n' +
  '  config:\n' +
  `    provider: ${VOLC_PROVIDER}\n` +
  `    model: ${VOLC_MODEL}\n`;
writeFileSync(PATCH, yaml, 'utf8');

const dshBin = path.join(ROOT, 'node_modules', '@deepseek-ai', 'dsh', 'lib', 'bin.js');
if (!existsSync(dshBin)) {
  console.error('未找到 dsh 运行时：' + dshBin);
  console.error('若你拿到的是"轻量包"，请先在工作台目录运行一次「首次安装依赖.bat」（需联网）。');
  process.exit(1);
}

// 读取 home/.env（dsh 自己也会读，这里额外注入给 TACT 工具进程，一处填 Key 两处生效）
const ENV_FILE = path.join(HOME, '.env');
if (existsSync(ENV_FILE)) {
  for (const rawLine of readFileSync(ENV_FILE, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 0) continue;
    const k = line.slice(0, eq).trim();
    let v = line.slice(eq + 1).trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    if (k && v && process.env[k] === undefined) process.env[k] = v;
  }
}

// 一个 Key 喂两处：dsh 火山路由认 VOLC_ARK_API_KEY，TACT 判定核认 TACT_ARK_API_KEY
if (process.env.VOLC_ARK_API_KEY && !process.env.TACT_ARK_API_KEY) {
  process.env.TACT_ARK_API_KEY = process.env.VOLC_ARK_API_KEY;
}

const env = { ...process.env, DSH_HOME: HOME };
const hasKey = !!(env.VOLC_ARK_API_KEY || env.TACT_ARK_API_KEY);

await (async () => {
  if (await portInUse(3080)) {
    console.log('检测到 3080 端口已被占用——工作台很可能已经在运行了。');
    console.log('请直接看浏览器里已经打开的 DeepSeek Harness 页面；若找不到标签页，');
    console.log('可在浏览器手动打开 http://127.0.0.1:3080/ ，或关掉之前的黑窗后重试。');
    console.log('');
    console.log('按任意键退出本窗口，不会影响已在运行的工作台。');
    process.stdin.resume();
    process.stdin.once('data', () => process.exit(0));
    return;
  }

  console.log('======================================================');
  console.log('  Td.蒙 · dsh 工作台启动中…');
  console.log('  专家：TACT 三轴坐标定位 · ACMG 变异评级 · 总管调度');
  if (hasKey) {
    console.log('  模型 Key：已从 home/.env 读到（兜底方式；界面「设置」里填的会优先）。');
  } else {
    console.log('  模型 Key：还没配置。浏览器打开后，点「设置 → 模型」，');
    console.log('           在「火山方舟（豆包）」这一栏粘贴 API Key 保存即可，无需重启。');
    console.log('           （习惯改文件的，也仍可在 home/.env 的 VOLC_ARK_API_KEY= 后填写作兜底。）');
  }
  console.log('  浏览器会自动打开；关闭这个黑窗即停止服务。');
  console.log('======================================================\n');

  const child = spawn(process.execPath, [dshBin, '--profile', 'web', '--patch', PATCH], {
    cwd: ROOT,
    env,
    stdio: 'inherit',
  });
  child.on('exit', (code) => process.exit(code ?? 0));
})();
