/* TACT 三轴坐标检查 · 平台无关判定核心
 * 同一份逻辑在 Node 对拍与浏览器 UI 中运行，逐字复刻 tact_pipeline（Python 最新版）：
 *   - SYSTEM_PROMPT / GATE_PROMPT、判定上下文拼装、三行解析（judge_one_worker.py）
 *   - build_checklist 固定顺序（tact_pipeline.py）
 *   - 第0步前置排除闸、母→子剪枝、保守开闸、母码只开闸不入定位（tact_llm_judge.py）
 *   - render_five 五项输出（含反问+剪枝双留痕、过闸空组、按闸排除）（tact_pipeline.py）
 * 平台差异只在 chatOnce（如何发 HTTP 请求），由调用方注入。
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.TACT = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ---------- 提示词（与 judge_one_worker.py 一致）----------
  var SYSTEM_PROMPT = [
    '你是 TACT 三轴坐标分类法的判定器。你收到一条 AI 系统错误现象，以及一个具体坐标。',
    '请只对该坐标判定“命中(是)”或“不命中(否)”，不要擅自跳到别的坐标，不要提前给最终结论。',
    '',
    '判定规则（必须严格遵守）：',
    '1. 只看“该错误本质是不是这个坐标”，不看表面沾边。支持性证据廉价，要找机制层面的硬反例。',
    '2. 判定“是”前，先反问：有没有一条一票否决级的硬反例能证明它本质不是这条？攻不死才保留。',
    '3. 判定“否”前，先反问：它的机制其实是不是落在这里？是不是因为只看表面后果、没看机制才误判为否？',
    '4. 你只对一个坐标作答，输出格式严格如下（不要其他内容）：',
    '',
    '命中:<是|否>',
    '理由:<一句话机制判断>',
    '反问:<一句反问结论>'
  ].join('\n');

  var GATE_PROMPT = [
    '你是 TACT 三轴坐标分类法的「第 0 步 前置排除闸」判定器。',
    '你收到一条 AI 系统错误现象。请判定它是否属于下列四类“不占码”情形之一，',
    '且不适用任何分流细则（人类诱导+智能体自主执行、系统自身也有错误成分、',
    '已产出可观察的违规输出、机制已出现两条互不相干真实案例）。',
    '',
    'E1 治理域：错误的**主体是人**——人类把 AI 当工具实施犯罪/攻击（深度伪造诈骗、换脸盗刷等）。',
    '    智能体**自主**发起的对抗/作恶**不属于**本闸（应继续过闸）。',
    'E2 环境/基础设施故障：**环境本身坏了**（网络/配额/隔离边界/配置缺陷），模型本身未犯错。',
    '    系统没适配环境（属 M1-3/P3-6）、环境被攻击（机制归 M6 族）**不属于**本闸。',
    'E3 预测格：机制**仅 1 例真实案例**且在预测格名单（传感欺骗/输入媒介替换、安全紧急停机/熔断失效）。',
    'E4 评测风险信号：只是**倾向/信号**、尚未构成已发生的错误事件（欺骗性升高、对齐倒退、越权倾向）。',
    '',
    '判定规则（必须严格遵守）：',
    '1. 只有明确落入上述四类之一、且无分流细则适用时，才判“是”。',
    '2. 拿不准时判“否”——宁可过闸，不可漏判。',
    '3. 只输出下面三行，不要任何其他内容：',
    '',
    '命中:<是|否>',
    '闸类:<E1|E2|E3|E4|无>',
    '理由:<一句话判断>'
  ].join('\n');

  var GATE_ITEM = {
    code: 'E-GATE', name: '第0步前置排除闸', axis: 'G', kind: 'gate',
    desc: '四类不占码情形：E1 治理域 / E2 环境故障 / E3 预测格 / E4 评测风险信号',
    criterion: 'E1 治理域（主体是人，人类把 AI 当工具实施犯罪/攻击）、' +
      'E2 环境/基础设施故障（环境本身坏了、模型未犯错）、' +
      'E3 预测格（仅 1 例真实案例的机制）、' +
      'E4 评测风险信号（仅倾向/信号、未构成已发生的错误事件）',
    question: '该现象是否属于上述四类之一，且不适用任何分流细则（人类诱导+智能体自主执行、' +
      '系统自身也有错误成分、已产出可观察的违规输出、机制已出现两条互不相干真实案例）？'
  };

  // ---------- 判定清单（build_checklist 固定顺序）----------
  function buildChecklist(snap) {
    var list = [];
    var seq = 0;
    function push(o) { o.seq = ++seq; list.push(o); }
    snap.L.forEach(function (x) {
      push({ axis: 'L', code: x.code, name: x.name, kind: 'layer',
        criterion: x.criterion || '',
        question: '这个错误是否发生在' + x.name + '（' + (x.criterion || '') + '）？本质是不是这一层？',
        requires_recheck: true });
    });
    snap.M_groups.forEach(function (g) {
      push({ axis: 'M', code: g.code, name: g.name, kind: 'mother',
        criterion: g.criterion || '',
        question: '这个错误的机制是否属于「' + g.name + '」母坐标（' + (g.criterion || '') + '）？',
        requires_recheck: true });
      g.opts.forEach(function (o) {
        push({ axis: 'M', code: o.code, name: o.name, kind: 'child',
          desc: o.desc || '', criterion: g.criterion || '',
          question: '是否命中子坐标「' + o.code + '」：' + o.name + '（' + (o.desc || '') + '）？',
          requires_recheck: true });
      });
    });
    snap.P_groups.forEach(function (g) {
      push({ axis: 'P', code: g.code, name: g.name, kind: 'mother',
        criterion: g.criterion || '',
        question: '这个错误破坏的方面是否属于「' + g.name + '」母坐标（' + (g.criterion || '') + '）？',
        requires_recheck: true });
      g.opts.forEach(function (o) {
        push({ axis: 'P', code: o.code, name: o.name, kind: 'child',
          desc: o.desc || '', criterion: g.criterion || '',
          question: '是否命中子坐标「' + o.code + '」：' + o.name + '（' + (o.desc || '') + '）？',
          requires_recheck: true });
      });
    });
    return list;
  }

  // ---------- 第0步前置排除闸（规则近似，仅提示）----------
  var E_GATES = [
    ['E1 治理域', '主体是人、人类把AI当工具实施犯罪/攻击', ['深度伪造', '换脸盗刷', '人类诈骗', '人利用AI', '冒充他人实施']],
    ['E2 环境/基础设施故障', '环境坏了、模型没犯错', ['网络抖动', '配额耗尽', '隔离边界故障', '资源配额', '基础设施', '网络故障', '服务器宕机']],
    ['E3 预测格', '仅1例真实案例的机制', ['传感欺骗', '输入媒介替换', '熔断失效', '紧急停机失效']],
    ['E4 评测风险信号', '仅倾向/信号、未构成已发生错误', ['评测中倾向', '对齐倒退倾向', '欺骗性升高', '越权倾向']]
  ];
  function checkPreGates(text) {
    var t = String(text || '').toLowerCase(), hits = [];
    E_GATES.forEach(function (g) {
      for (var i = 0; i < g[2].length; i++) {
        if (t.indexOf(g[2][i].toLowerCase()) >= 0) {
          hits.push({ gate: g[0], desc: g[1], hit_keyword: g[2][i] });
          break;
        }
      }
    });
    return hits;
  }

  // ---------- 单次判定上下文拼装（worker main）----------
  function buildMessages(text, item) {
    var ctx = '坐标：' + item.code + ' ' + item.name + '（' + (item.desc || item.criterion || '') + '）\n' +
      '判据：' + (item.criterion || '') + '\n';
    var user = '待判现象：' + text + '\n\n' + ctx + (item.question || '');
    var sys = item.kind === 'gate' ? GATE_PROMPT : SYSTEM_PROMPT;
    return [{ role: 'system', content: sys }, { role: 'user', content: user }];
  }

  // ---------- 三行解析（worker 正则，逐行收集、命中不 break）----------
  var LABEL_RE = /^[-\s*·•#>]*\s*(命中|理由|反问|闸类)[-*\s·•#>]*[：:]\s*(.*)$/;
  function parseVerdict(out) {
    var hit = false, parsed = false, reason = '', challenge = '', gateClass = '';
    String(out || '').split(/\r?\n/).forEach(function (rawLine) {
      var line = rawLine.trim();
      if (!line) return;
      var m = line.match(LABEL_RE), label = '', val = '';
      if (m) { label = m[1]; val = m[2].trim(); }
      else {
        var lbs = ['命中', '理由', '反问', '闸类'];
        for (var i = 0; i < lbs.length; i++) {
          if (line.indexOf(lbs[i]) === 0) {
            label = lbs[i];
            val = line.slice(lbs[i].length).replace(/^[ 　：:]+/, '').trim();
            break;
          }
        }
      }
      if (label === '命中' && !parsed) {
        if (val === '是' || val === '否') hit = (val === '是');
        else hit = val.indexOf('是') >= 0 || /yes|true/i.test(val);
        parsed = true;
      } else if (label === '理由' && !reason) reason = val;
      else if (label === '反问' && !challenge) challenge = val;
      else if (label === '闸类' && !gateClass) gateClass = val;
    });
    return { hit: hit, readable: parsed, reason: reason, challenge: challenge,
      gate_class: gateClass, raw: String(out || '').slice(0, 300) };
  }

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  // judgeOne：对单个坐标判定，2s 节奏 + 递增冷却重试（与 tact_llm_judge 一致）
  // chatOnce(messages, model, opts) -> Promise<String>，平台注入
  function judgeOne(chatOnce, text, item, model, opts) {
    opts = opts || {};
    var retries = opts.retries == null ? 3 : opts.retries;
    var baseSleep = opts.baseSleep == null ? 2000 : opts.baseSleep;
    var cooldown = opts.cooldown || [15000, 30000, 60000];
    var messages = buildMessages(text, item);
    var lastErr = null;
    function attempt(n) {
      var wait = n === 0 ? baseSleep : baseSleep + (cooldown[n - 1] || cooldown[cooldown.length - 1]);
      return sleep(wait).then(function () {
        return chatOnce(messages, model, { disableThinking: opts.disableThinking !== false });
      }).then(function (out) {
        var v = parseVerdict(out);
        return { code: item.code, name: item.name, axis: item.axis, kind: item.kind,
          hit: v.hit, readable: v.readable, reason: v.reason, challenge: v.challenge,
          gate_class: v.gate_class, raw: v.raw };
      }).catch(function (e) {
        lastErr = e;
        // 平台可对不可恢复错误（如 401 缺/错 Key）打 noretry 标记，立即失败、不空耗退避
        if (e && e.noretry) throw e;
        if (n + 1 < retries) return attempt(n + 1);
        var err = new Error('坐标 ' + item.code + ' 判定失败（重试' + retries + '次）: ' + (e && e.message));
        err.code = item.code;
        throw err;
      });
    }
    return attempt(0);
  }

  // 第0步 LLM 语义闸；解析不出按“不排除”（宁可过闸）
  function judgeGate(chatOnce, text, model, opts) {
    return judgeOne(chatOnce, text, GATE_ITEM, model, opts).then(function (r) {
      if (!r.readable) return { excluded: false, gateClass: '', reason: 'gate 判定输出无法解析，按“不排除”处理（宁可过闸）' };
      return { excluded: !!r.hit, gateClass: (r.gate_class || '').trim(), reason: r.reason };
    });
  }

  // ---------- 编排：L → gate → M/P（母→子剪枝），返回结构与 Python out 对齐 ----------
  // options: { chatOnce, model, concurrency(组内子坐标并发,默认4), onProgress, shouldCancel,
  //            skip:Set, maxN, disableThinking }
  function runJudge(snap, text, options) {
    options = options || {};
    var checklist = buildChecklist(snap);
    var ruleGates = checkPreGates(text);
    var all = checklist;
    if (options.skip && options.skip.size) {
      all = all.filter(function (i) { return !options.skip.has(i.code); });
    }
    var state = {
      total: all.length, doneCount: 0, judgedCount: 0,
      results: [], hitCodes: { L: [], M: [], P: [] },
      mothersHit: [], unreadable: [], pruned: [],
      gateInfo: { rule_hits: ruleGates.map(function (g) { return g.gate; }),
        llm_excluded: false, llm_gate_class: '', llm_reason: '' },
      gate: null, startedAt: Date.now(), finishedAt: null, model: options.model || ''
    };
    function emit(phase, item, extra) {
      if (options.onProgress) options.onProgress(Object.assign({ phase: phase, item: item,
        done: state.doneCount, total: state.total, pruned: state.pruned.length }, extra || {}));
    }
    function cancelled() { return options.shouldCancel && options.shouldCancel(); }

    // 并发池：同一时刻在飞请求受限（默认 4），降低火山风控概率
    var sem = (function () {
      var n = options.concurrency == null ? 4 : options.concurrency, active = 0, q = [];
      function pump() { while (active < n && q.length) { active++; q.shift()().then(done, done); } }
      function done() { active--; pump(); }
      return function (task) { return new Promise(function (res, rej) {
        q.push(function () { return Promise.resolve().then(task).then(res, rej); }); pump();
      }); };
    })();

    function judge(item) {
      if (cancelled()) return Promise.resolve(null);
      return sem(function () {
        return judgeOne(options.chatOnce, text, item, state.model, options);
      });
    }

    // 处理一个判定结果（与 Python 主循环同语义）
    function adopt(r, item) {
      state.results.push(r);
      state.doneCount++;
      state.judgedCount++;
      if (!r.readable) {
        state.unreadable.push(r.code);
        emit('unreadable', r);
      } else if (r.hit) {
        if (item.kind === 'mother') { state.mothersHit.push(r.code); emit('mother-hit', r); }
        else { state.hitCodes[r.axis].push(r.code); emit('hit', r); }
      } else {
        emit('no', r);
      }
    }
    function adoptError(err, item) {
      state.results.push({ code: item.code, name: item.name, axis: item.axis,
        kind: item.kind, hit: false, readable: false, error: String(err && err.message || err) });
      state.doneCount++;
      state.judgedCount++;
      state.unreadable.push(item.code);
      emit('error', { code: item.code }, { error: String(err && err.message || err) });
    }
    function markPruned(item, motherCode) {
      state.pruned.push(item.code);
      state.results.push({ code: item.code, name: item.name, axis: item.axis,
        kind: 'child', hit: false, readable: true, pruned: true, pruned_by: motherCode,
        reason: '母坐标 ' + motherCode + ' 判否，按 SKILL.md 未进入该组子坐标',
        challenge: '', gate_class: '', raw: '' });
      state.doneCount++;
      emit('pruned', item, { by: motherCode });
    }

    function step() {
      if (cancelled()) { state.finishedAt = Date.now(); state.cancelled = true; return Promise.resolve(state); }

      // 1) L 轴（无母/子闸，并发）
      var L = all.filter(function (i) { return i.axis === 'L'; });
      if (L.length) {
        emit('stage', { code: 'L', name: 'L 轴' });
        return Promise.all(L.map(function (item) {
          return judge(item).then(function (r) { if (r) adopt(r, item); },
            function (e) { adoptError(e, item); });
        })).then(function () { all = all.filter(function (i) { return i.axis !== 'L'; }); return step(); });
      }

      // 2) 第0步前置排除闸（只判一次）
      if (state.gate === null) {
        state.gate = 'pending';
        emit('stage', { code: 'GATE', name: '第0步前置排除闸' });
        return judgeGate(options.chatOnce, text, state.model, options).then(function (g) {
          state.gate = g;
          state.gateInfo.llm_excluded = g.excluded;
          state.gateInfo.llm_gate_class = g.gateClass;
          state.gateInfo.llm_reason = g.reason;
          emit('gate', GATE_ITEM, g);
          if (g.excluded) all = all.filter(function (i) { return i.axis === 'L'; });
          return step();
        }, function (e) {
          // gate 判定整体失败：按“不排除”继续（与单坐标不可解析同取向）
          state.gate = { excluded: false, gateClass: '', reason: 'gate 调用失败：' + (e && e.message) };
          state.gateInfo.llm_reason = state.gate.reason;
          emit('gate-error', GATE_ITEM, { error: String(e && e.message || e) });
          return step();
        });
      }

      // 3) M/P 轴：逐组过母闸，母否剪整组，母是组内子坐标并发
      var groups = [];
      var pushGroup = function (axis, g) {
        var mother = all.filter(function (i) { return i.axis === axis && i.code === g.code; })[0];
        var childItems = g.opts.map(function (o) {
          return all.filter(function (i) { return i.axis === axis && i.code === o.code; })[0];
        }).filter(Boolean);
        if (mother) groups.push({ axis: axis, mother: mother, children: childItems });
      };
      if (all.some(function (i) { return i.axis === 'M'; })) snap.M_groups.forEach(function (g) { pushGroup('M', g); });
      if (all.some(function (i) { return i.axis === 'P'; })) snap.P_groups.forEach(function (g) { pushGroup('P', g); });

      function nextGroup(idx) {
        if (idx >= groups.length) { state.finishedAt = Date.now(); return Promise.resolve(state); }
        var grp = groups[idx];
        emit('stage', { code: grp.axis, name: grp.mother.code + ' ' + grp.mother.name + ' 母闸' });
        return judge(grp.mother).then(function (r) {
          var gateOpen;
          if (!r) { state.finishedAt = Date.now(); state.cancelled = true; return state; }
          adopt(r, grp.mother);
          if (!r.readable) gateOpen = true;            // 不可解析：保守开闸
          else gateOpen = !!r.hit;
          if (!gateOpen) grp.children.forEach(function (ch) { markPruned(ch, grp.mother.code); });
          if (cancelled()) { state.finishedAt = Date.now(); state.cancelled = true; return state; }
          if (!gateOpen) return nextGroup(idx + 1);
          // 母是：组内子坐标并发判定
          return Promise.all(grp.children.map(function (ch) {
            return judge(ch).then(function (rr) { if (rr) adopt(rr, ch); },
              function (e) { adoptError(e, ch); });
          })).then(function () { return nextGroup(idx + 1); });
        }, function (e) {
          // 母坐标判定抛错：宁可过闸、不可漏判——继续判该组子坐标
          adoptError(e, grp.mother);
          emit('gate-open-fallback', grp.mother);
          return Promise.all(grp.children.map(function (ch) {
            return judge(ch).then(function (rr) { if (rr) adopt(rr, ch); },
              function (e2) { adoptError(e2, ch); });
          })).then(function () { return nextGroup(idx + 1); });
        });
      }
      return nextGroup(0);
    }
    return step();
  }

  // ---------- 五项输出渲染（render_five，Markdown）----------
  function renderFive(coords, snap, details, gateInfo, mothers) {
    details = details || [];
    gateInfo = gateInfo || null;
    var det = {};
    details.forEach(function (d) { if (d.code) det[d.code] = d; });
    var lname = {}, mname = {}, mparent = {}, pname = {}, pparent = {};
    snap.L.forEach(function (x) { lname[x.code] = x.name; });
    snap.M_groups.forEach(function (g) {
      mname[g.code] = g.name;
      g.opts.forEach(function (o) { mname[o.code] = o.name; mparent[o.code] = g.name; });
    });
    snap.P_groups.forEach(function (g) {
      pname[g.code] = g.name;
      g.opts.forEach(function (o) { pname[o.code] = o.name; pparent[o.code] = g.name; });
    });
    var findOpt = function (axis, code) {
      var gs = axis === 'M' ? snap.M_groups : snap.P_groups;
      for (var i = 0; i < gs.length; i++)
        for (var j = 0; j < gs[i].opts.length; j++)
          if (gs[i].opts[j].code === code) return gs[i].opts[j];
      return null;
    };
    var L = [];
    L.push('### 1. 三维坐标名称');
    L.push('- 完整坐标：' + [coords.L.join(',') || '-', coords.M.join(',') || '-', coords.P.join(',') || '-'].join('/'));
    var motherNames = [];
    if (mothers) {
      if (coords.L.length) motherNames.push(lname[coords.L[0]] || '');
      mothers.forEach(function (code) {
        var nm = mname[code] || pname[code] || '';
        if (nm && motherNames.indexOf(nm) < 0) motherNames.push(nm);
      });
      motherNames = motherNames.filter(Boolean);
    } else {
      if (coords.L.length) motherNames.push(lname[coords.L[0]] || '');
      [[coords.M, mparent, mname], [coords.P, pparent, pname]].forEach(function (t) {
        t[0].forEach(function (c) {
          var nm = t[1][c] || t[2][c] || '';
          if (nm && motherNames.indexOf(nm) < 0) motherNames.push(nm);
        });
      });
    }
    L.push('- 三个母坐标名：' + (motherNames.length ? motherNames.join(' · ') : '（无命中）'));
    L.push('');

    L.push('### 2. 命中的 L 轴坐标');
    if (coords.L.length) {
      coords.L.forEach(function (c) {
        var x = snap.L.filter(function (y) { return y.code === c; })[0];
        if (x) {
          L.push('- **%s %s**'.replace('%s', c).replace('%s', x.name));
          L.push('  - 为什么是这一层：%s'.replace('%s', x.criterion));
          var d = det[c];
          if (d && d.reason) L.push('  - 机制判断：' + d.reason);
        } else L.push('- ' + c + '（坐标底座中未找到该码）');
      });
    } else L.push('- （L 轴未命中或按闸不占码）');
    L.push('');

    L.push('### 3. 所有命中的子坐标');
    var anyChild = false;
    [['M', mname], ['P', pname]].forEach(function (t) {
      var axis = t[0];
      coords[axis].forEach(function (c) {
        var o = findOpt(axis, c);
        anyChild = true;
        if (!o) { L.push('- **%s**：坐标底座中未找到该码（疑似造码）'.replace('%s', c)); return; }
        var parentName = (axis === 'M' ? mparent : pparent)[c] || '';
        L.push('- **%s %s**（所属母坐标：%s）'.replace('%s', c).replace('%s', o.name).replace('%s', parentName));
        L.push('  - 含义：' + (o.desc || ''));
        var d = det[c];
        if (d && d.reason) L.push('  - 机制判断：' + d.reason);
        (o.pairs || []).slice(0, 3).forEach(function (p) {
          if (p.length >= 3) {
            L.push('  - 可能表现：' + p[0]);
            L.push('    发生位置：' + p[1]);
            L.push('    验证路径：' + p[2]);
          }
        });
      });
    });
    if (!anyChild) L.push('- （M/P 轴未命中）');
    L.push('');

    // 第 4 项：反问留痕 + 剪枝留痕
    var prunedCodes = details.filter(function (d) { return d.pruned && d.code; }).map(function (d) { return d.code; });
    var codes6 = function (cs, n) { n = n || 6; var s = cs.slice(0, n).join(', '); return cs.length > n ? s + '…' : s; };
    L.push('### 4. 反问留痕');
    var traced = coords.L.concat(coords.M).concat(coords.P).filter(function (c) { return det[c] && det[c].challenge; });
    traced.forEach(function (c) {
      var d = det[c];
      L.push('- **' + c + '**：反问 → ' + d.challenge);
      if (d.reason) L.push('  机制判断 → ' + d.reason);
    });
    if (mothers) {
      mothers.forEach(function (c) {
        if (coords.M.indexOf(c) >= 0 || coords.P.indexOf(c) >= 0) return;
        var d = det[c];
        if (d && d.challenge) {
          var nm = mname[c] || pname[c] || '';
          L.push('- **母坐标闸 ' + c + ' ' + nm + '**（判是开闸）：反问 → ' + d.challenge);
          if (d.reason) L.push('  机制判断 → ' + d.reason);
        }
      });
    }
    // 剪枝留痕：每个判否母坐标逐个给机制层面排除理由
    var deniedMothers = details.filter(function (d) {
      return d.kind === 'mother' && !d.hit && d.readable !== false && !d.pruned;
    });
    if (deniedMothers.length) {
      L.push('- **剪枝留痕（母坐标判否、整组未进子闸）**：');
      deniedMothers.forEach(function (d) {
        var nm = mname[d.code] || pname[d.code] || d.name || '';
        var why = d.reason || d.challenge || '（模型未给出机制层面排除理由，建议重判该母闸）';
        L.push('  - **' + d.code + ' ' + nm + '**：排除——' + why);
      });
    }
    if (!traced.length && !(mothers || []).some(function (c) { return det[c] && det[c].challenge; })) {
      if (details.length) L.push('- 本次判定未返回可解析的反问记录（模型输出格式跑偏时会发生）；命中结论仍可用，但唯一性论证缺失，建议重跑相关坐标。');
      else L.push('- 本次为纯规则基线判定（关键词匹配），无 LLM 反问记录；需要反问留痕请改用 LLM 判定后端。');
    }
    if (prunedCodes.length)
      L.push('- 另有 ' + prunedCodes.length + ' 个子坐标随上述母坐标判否被剪枝、未进入判定，故无反问记录：' + codes6(prunedCodes));
    L.push('');

    // 第 5 项：判不了说明
    L.push('### 5. 判不了说明');
    var excluded = {};
    if (gateInfo && gateInfo.llm_excluded) {
      excluded = { M: 1, P: 1 };
      L.push('- 第 0 步前置排除闸命中 ' + (gateInfo.llm_gate_class || '未给出闸类') + '（' + gateInfo.llm_reason + '）→ M/P 轴按“不占码”排除，不属于“判不了”。');
    }
    var openedButEmpty = function (axis) {
      var out = [];
      (mothers || []).forEach(function (mc) {
        if (mc.indexOf(axis) !== 0) return;
        var gs = axis === 'M' ? snap.M_groups : snap.P_groups;
        var group = gs.filter(function (g) { return g.code === mc; })[0];
        if (!group) return;
        var childSet = {};
        group.opts.forEach(function (o) { childSet[o.code] = 1; });
        var hitHere = coords[axis].some(function (c) { return childSet[c]; });
        if (!hitHere) out.push([mc, group.name, group.opts.length]);
      });
      return out;
    };
    var emptyAxes = ['L', 'M', 'P'].filter(function (ax) { return !coords[ax].length && !excluded[ax]; });
    emptyAxes.forEach(function (ax) {
      var axPruned = prunedCodes.filter(function (c) { return c.indexOf(ax) === 0; });
      var oe = openedButEmpty(ax);
      if (oe.length) {
        oe.forEach(function (t) {
          L.push('- ' + ax + ' 轴另有母坐标 ' + t[0] + ' ' + t[1] + ' 判“是”开闸，但该组 ' + t[2] +
            ' 个精细子坐标无一通过反问；本轴最终命中落在其他族，该母坐标为粗粒度泛化判断，建议复核是否开闸过宽。');
        });
      } else if (axPruned.length) {
        L.push('- ' + ax + ' 轴：' + axPruned.length + ' 个子坐标因所属母坐标判否被剪枝而未判定；若漏报应先复核对应母坐标闸的判定质量。');
      } else {
        L.push('- ' + ax + ' 轴：走完全程无坐标通过反问（现有 117 个精细坐标未覆盖该机制）。是否应新增层，须按“是否一个独立且唯一机制、是否有两条互不相干错误同属此机制”判断，交用户决定，不自行造码。');
      }
    });
    if (!emptyAxes.length && !Object.keys(excluded).length) L.push('- 三轴均有命中，无需说明。');
    L.push('');
    L.push('> 智能分析结果，仅供参考。');
    return L.join('\n');
  }

  return {
    GATE_ITEM: GATE_ITEM,
    buildChecklist: buildChecklist,
    checkPreGates: checkPreGates,
    buildMessages: buildMessages,
    parseVerdict: parseVerdict,
    judgeOne: judgeOne,
    judgeGate: judgeGate,
    runJudge: runJudge,
    renderFive: renderFive
  };
});
