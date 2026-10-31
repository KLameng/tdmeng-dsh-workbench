/*
 * ACMG 变异评级技能群 · 环境自检工具 acmg_env_check
 * ----------------------------------------------------------------------------
 * 这个技能群的取数脚本是 Python（requests / pyliftover），评级前最好先确认本机环境。
 * 本工具纯 Node 实现（不依赖 Python 即可运行）：探测可用 Python、关键 pip 依赖、
 * 技能群关键文件、取数相关环境变量，返回一份"能不能开跑/缺什么/怎么补"的报告。
 * 真正的逐码评级由调度模型读 acmg-total-scheduler 后用 dsh 自带 bash/pwsh 执行 Python 脚本完成。
 */
import { execFile } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineTool } from '@deepseek-ai/dsh-tools';

const here = path.dirname(fileURLToPath(import.meta.url));
const GROUP_ROOT = path.join(here, 'skills', 'acmg-variant-rating');

// 候选解释器：PATH 上的 python/python3/py，以及 Windows 常见 Coze 桌面运行时
function candidates() {
  const list = [
    { cmd: 'python', args: ['--version'] },
    { cmd: 'python3', args: ['--version'] },
    { cmd: 'py', args: ['-3', '--version'] },
  ];
  const home = process.env.USERPROFILE || process.env.HOME;
  if (home && process.platform === 'win32') {
    list.push({
      cmd: path.join(home, '.coze', 'runtimes', 'desktop-runtime', 'current', 'bin', 'python.cmd'),
      args: ['--version'],
    });
  }
  return list;
}

function run(cmd, args, timeoutMs = 20000) {
  // Windows 上 .cmd / 商店 python 别名必须经 shell，否则 spawn EINVAL
  const useShell = process.platform === 'win32';
  const q = (a) => (useShell && /[\s"&|<>^()]/.test(a) ? `"${String(a).replace(/"/g, '\\"')}"` : a);
  return new Promise((resolve) => {
    execFile(cmd, args.map(q), { timeout: timeoutMs, windowsHide: true, shell: useShell }, (err, stdout, stderr) => {
      resolve({ ok: !err, stdout: String(stdout || ''), stderr: String(stderr || '') });
    });
  });
}

async function findPython() {
  for (const c of candidates()) {
    const r = await run(c.cmd, c.args);
    const m = (r.stdout + r.stderr).match(/Python\s+(\d+\.\d+\.\d+)/);
    if (m) {
      // 取真实 exe（python.cmd 是包一层）
      let exe = c.cmd;
      const which = await run(c.cmd, ['-c', "import sys;print(sys.executable)"]);
      if (which.ok && which.stdout.trim()) exe = which.stdout.trim();
      return { found: true, cmd: c.cmd, exe, version: m[1] };
    }
  }
  return { found: false };
}

// 直接 spawn 真实 python.exe（不经 shell/.cmd）：多行 -c 作为单个 argv，无引号转义问题
function runFile(exe, args, timeoutMs = 20000) {
  return new Promise((resolve) => {
    execFile(exe, args, { timeout: timeoutMs, windowsHide: true }, (err, stdout, stderr) => {
      resolve({ ok: !err, stdout: String(stdout || ''), stderr: String(stderr || '') });
    });
  });
}

async function pyProbe(pyExe, code) {
  // 优先真实 exe 直跑；仅当只拿到 .cmd 时才退回 shell 模式（且只支持单行）
  const isCmd = /\.cmd$/i.test(pyExe);
  const r = isCmd ? await run(pyExe, ['-c', code.replace(/\s+/g, ' ')], 20000)
                 : await runFile(pyExe, ['-c', code], 20000);
  return r.ok ? r.stdout.trim() : (r.stderr.trim() || r.stdout.trim() || '');
}

// 注意：经 shell 传 -c，整段代码只用单引号，避免和命令行双引号包裹冲突
const PROBE_CODE = [
  'import sys, json',
  "out={'ver':sys.version.split()[0]}",
  "for m in ['requests','pyliftover']:",
  '    try:',
  "        mod=__import__(m); out[m]=getattr(mod,'__version__','installed')",
  '    except Exception:',
  '        out[m]=None',
  'print(json.dumps(out))',
].join('\n');

export const name = 'dsh-acmg-skill-tool';
export const inject = ['tools'];

export function apply(ctx) {
  ctx.tools.register(
    defineTool({
      name: 'acmg_env_check',
      description:
        '在运行 ACMG 变异评级技能群的 Python 取数脚本前，自检本机环境：是否有可用 Python 3、' +
        '是否装了 requests/pyliftover、技能群关键文件（scripts/config/22 个 SKILL）是否就位、' +
        '以及取数相关环境变量（NCBI_EMAIL / LLM_API_KEY / HGMD_*）是否配置。返回就绪状态与补缺步骤。' +
        '用户第一次要评级、或脚本报缺依赖/找不到 Python 时先调用本工具。',
      parameters: {
        detail: {
          type: 'string',
          description: '可选：传 "full" 则额外尝试 pip 版本等较慢探测；默认快速自检。',
        },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            ready: { type: 'boolean', description: '核心评级链路是否就绪（Python + requests + 群文件）' },
            report: { type: 'string', description: '给用户/模型看的中文自检报告（Markdown）' },
          },
        },
        render: (_args, v) => [{ type: 'text', text: v.report }],
      },
      async execute(args) {
        const lines = [];
        lines.push('## ACMG 评级环境自检');

        // 1) Python
        const py = await findPython();
        let pyReady = false;
        let pyCmd = null;
        if (py.found) {
          // 后续探测优先用真实 exe（findPython 已通过 sys.executable 解析）
          pyCmd = /\.cmd$/i.test(py.exe) ? py.cmd : py.exe;
          lines.push(`- Python：✅ ${py.version}（${py.exe}）`);
          pyReady = true;
        } else {
          lines.push('- Python：❌ 未在 PATH 找到可用的 Python 3');
          lines.push('  - 补缺：安装 Python 3.13（勾选 Add to PATH），或把 Coze 桌面运行时 Python 加入 PATH；');
          lines.push('    然后在技能群根目录执行 `python -m pip install -r requirements.txt`。');
        }

        // 2) pip 依赖
        let requestsOk = false;
        let pyliftoverOk = false;
        if (pyReady) {
          const raw = await pyProbe(pyCmd, PROBE_CODE);
          let info = null;
          try { info = JSON.parse(raw); } catch { info = null; }
          if (info) {
            requestsOk = !!info.requests;
            pyliftoverOk = !!info.pyliftover;
            lines.push(`- requests：${requestsOk ? '✅ ' + info.requests : '❌ 未安装（基因身份/疾病/文献/遗传方式取数需要）'}`);
            lines.push(`- pyliftover：${pyliftoverOk ? '✅ ' + info.pyliftover : '❌ 未安装（变异归一化 hg19↔hg38 坐标转换需要）'}`);
            if (!requestsOk || !pyliftoverOk) {
              lines.push('  - 补缺：在技能群根目录执行 `python -m pip install -r requirements.txt`');
            }
          } else {
            lines.push('- 依赖探测：⚠️ 未能执行探测脚本（输出：' + raw.slice(0, 80) + '）');
          }
        } else {
          lines.push('- requests / pyliftover：⏸️ 因无 Python 未检测');
        }

        // 3) 技能群关键文件
        const need = [
          'acmg-total-scheduler/SKILL.md',
          'acmg-conflict-summary-output/SKILL.md',
          'arad-inheritance-judgment/SKILL.md',
          'scripts/acmg_evidence.py',
          'scripts/acmg_combine.py',
          'config/knowledge_graph.json',
          'config/thresholds.json',
          'requirements.txt',
        ];
        let filesOk = true;
        lines.push('- 技能群关键文件：');
        for (const rel of need) {
          const ok = existsSync(path.join(GROUP_ROOT, rel));
          if (!ok) filesOk = false;
          lines.push(`  - ${ok ? '✅' : '❌'} ${rel}`);
        }
        let skillCount = 0;
        try {
          // 只数各原子技能目录（acmg-*/arad-*/ev-*/clingen-*）下的 SKILL.md，
          // 不计群根本包入口 SKILL.md（那是给 dsh 的身份说明书，不是原子子技能）
          for (const e of readdirSync(GROUP_ROOT, { withFileTypes: true })) {
            if (e.isDirectory() && /^(acmg-|arad-|ev-|clingen-)/.test(e.name)) {
              if (existsSync(path.join(GROUP_ROOT, e.name, 'SKILL.md'))) skillCount++;
            }
          }
        } catch { skillCount = -1; }
        lines.push(`  - 原子子技能 SKILL.md 数量：${skillCount >= 0 ? skillCount : '⚠️ 统计失败'}（预期 22；另有 clingen-vcep 为独立另包，缺失属正常但须在评级中标注）`);

        // 4) 环境变量（只报是否设置，绝不打印值）
        const envs = ['NCBI_EMAIL', 'LLM_BASE_URL', 'LLM_MODEL', 'LLM_API_KEY', 'HGMD_QUERY_DIR', 'HGMD_SKIP'];
        lines.push('- 取数相关环境变量：');
        for (const k of envs) {
          const set = process.env[k] && process.env[k].trim() !== '';
          let note = '';
          if (k === 'NCBI_EMAIL' && !set) note = '（未设则用中性占位邮箱，建议设真实邮箱防 NCBI 限流）';
          if (k === 'LLM_API_KEY' && !set) note = '（未设则文献 LLM 精筛会硬中断并给配置指引，非阻塞其他证据码）';
          if (k === 'HGMD_QUERY_DIR' && !set) note = '（HGMD 商业库不随包；走 ClinVar/文献通道并标注，或设 HGMD_SKIP=1）';
          lines.push(`  - ${set ? '✅' : '⬜'} ${k}${note}`);
        }

        const coreReady = pyReady && requestsOk && pyliftoverOk && filesOk;
        lines.unshift(coreReady
          ? '**结论：核心评级链路就绪，可以开始评级。**'
          : '**结论：环境尚未完全就绪，按上方"补缺"处理后再评级（纯标准库的 gnomAD 约束查询不受 requests 影响）。**');

        const report = lines.join('\n') + '\n\n> 智能分析结果，仅供参考。\n';
        return { ready: coreReady, report };
      },
    })
  );

  ctx.logger?.info?.('[dsh-acmg-skill] acmg_env_check 环境自检工具已注册');
}
