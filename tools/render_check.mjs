/**
 * 三维页面渲染自检器（CDP 直连，可靠版）
 * =====================================
 * 为什么不用 `chrome --screenshot --virtual-time-budget`：
 * 该模式用「虚拟时间」推进，GLB 这类真实网络 I/O 会被饿死，导致间歇性假超时
 * （2026-09-22 实测：同一页面、同一服务，有时成有时败）。本器改用 CDP，
 * 轮询页面真实状态位，只有真的加载完成才截图，并顺带抓 Console 报错。
 *
 * 用法：
 *   node tools/render_check.mjs <url> <输出png> [等待秒数]
 * 例：
 *   node tools/render_check.mjs "http://127.0.0.1:8777/index.html?t=100" out.png 60
 */
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CHROME = process.env.CHROME_PATH
  || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9333 + Math.floor(Math.random() * 400);

const url = process.argv[2];
const outPng = process.argv[3];
const waitSec = Number(process.argv[4] || 60);
if (!url || !outPng) {
  console.error('用法: node render_check.mjs <url> <out.png> [等待秒数]');
  process.exit(2);
}

const profile = mkdtempSync(join(tmpdir(), 'lbchk-'));
const chrome = spawn(CHROME, [
  '--headless=new',
  '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader',
  '--hide-scrollbars',
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-extensions',
  `--user-data-dir=${profile}`,
  '--window-size=1680,900',
  `--remote-debugging-port=${PORT}`,
  'about:blank'
], { stdio: ['ignore', 'ignore', 'pipe'] });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const page = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page;
    } catch { /* 还没起来 */ }
    await sleep(500);
  }
  throw new Error('未能连接到 Chrome 调试端口');
}

let ws, msgId = 0;
const pending = new Map();
const consoleLogs = [];
const exceptions = [];

function send(method, params = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((res, rej) => pending.set(id, { res, rej }));
}

function main() {
  return new Promise(async (resolve) => {
    try {
      const target = await findTarget();
      ws = new WebSocket(target.webSocketDebuggerUrl);
      await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

      ws.onmessage = (ev) => {
        const m = JSON.parse(ev.data);
        if (m.id && pending.has(m.id)) {
          const { res, rej } = pending.get(m.id);
          pending.delete(m.id);
          m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
          return;
        }
        if (m.method === 'Runtime.consoleAPICalled') {
          const txt = (m.params.args || []).map((a) =>
            a.value !== undefined ? a.value : (a.description || a.type)).join(' ');
          consoleLogs.push(`[${m.params.type}] ${txt}`);
        }
        if (m.method === 'Runtime.exceptionThrown') {
          const d = m.params.exceptionDetails;
          exceptions.push(d.exception?.description || d.text || 'unknown');
        }
      };

      await send('Runtime.enable');
      await send('Page.enable');
      await send('Page.navigate', { url });

      const deadline = Date.now() + waitSec * 1000;
      let state = null;
      while (Date.now() < deadline) {
        await sleep(700);
        try {
          const r = await send('Runtime.evaluate', {
            expression: `JSON.stringify({
              ok: !!window.__LB_OK,
              started: !!window.__LB_MODULE_STARTED,
              diag: (document.getElementById('h_diag')||{}).textContent || '',
              err: (document.getElementById('err')||{}).style ?
                   document.getElementById('err').style.display : '',
              errText: ((document.getElementById('err')||{}).firstElementChild||{}).textContent || '',
              calls: (document.getElementById('h_calls')||{}).textContent || '',
              fps: (document.getElementById('h_fps')||{}).textContent || '',
              probe: (typeof window.__LB_DEBUG__ === 'function') ? window.__LB_DEBUG__() : null
            })`,
            returnByValue: true
          });
          state = JSON.parse(r.result.value);
          if (state.ok) break;
          if (state.err === 'grid' && state.errText) break;   // 已给出明确错误，无需再等
        } catch { /* 页面导航中 */ }
      }

      // 让渲染循环跑几帧再截图
      await sleep(1200);
      const shot = await send('Page.captureScreenshot', { format: 'png' });
      writeFileSync(outPng, Buffer.from(shot.data, 'base64'));

      resolve({ state, consoleLogs, exceptions });
    } catch (e) {
      resolve({ error: String(e) });
    }
  });
}

const result = await main();
console.log('=== 渲染自检结果 ===');
if (result.error) {
  console.log('连接/执行失败:', result.error);
} else {
  const s = result.state || {};
  console.log('模块已启动 :', s.started);
  console.log('加载已完成 :', s.ok);
  console.log('自检读数   :', (s.diag || '').replace(/\s+/g, ' ').trim());
  console.log('draw call  :', s.calls, '| FPS:', s.fps);
  if (s.err === 'grid') console.log('页面给出的错误:', (s.errText || '').slice(0, 400));
  console.log('Console 输出 (' + result.consoleLogs.length + ' 条):');
  result.consoleLogs.slice(0, 20).forEach((l) => console.log('   ', l.slice(0, 200)));
  console.log('未捕获异常 (' + result.exceptions.length + ' 条):');
  result.exceptions.slice(0, 10).forEach((l) => console.log('   ', String(l).split('\n')[0].slice(0, 220)));
  console.log('截图已写入:', outPng);
}

// 同步落盘一份 UTF-8 日志：PowerShell 捕获 Node 输出时会把中文转成乱码，
// 只看终端会读不出诊断信息（已踩过）。日志放在截图同目录同名 .log。
try {
  const base = outPng.replace(/\.png$/i, '.log');
  const lines = [];
  lines.push('# 渲染自检 · ' + url);
  if (result.error) {
    lines.push('连接/执行失败: ' + result.error);
  } else {
    const s = result.state || {};
    lines.push('模块已启动: ' + s.started);
    lines.push('加载已完成: ' + s.ok);
    lines.push('自检读数  : ' + String(s.diag || '').replace(/\s+/g, ' ').trim());
    lines.push('draw call : ' + s.calls + ' | FPS: ' + s.fps);
    lines.push('probe     : ' + JSON.stringify(s.probe || null));
    if (s.err === 'grid') lines.push('页面错误  : ' + String(s.errText || '').slice(0, 800));
    lines.push('');
    lines.push('## Console（' + result.consoleLogs.length + ' 条）');
    result.consoleLogs.forEach((l) => lines.push(l));
    lines.push('');
    lines.push('## 未捕获异常（' + result.exceptions.length + ' 条）');
    result.exceptions.forEach((l) => lines.push(String(l).split('\n')[0]));
  }
  writeFileSync(base, lines.join('\n'), 'utf8');
  console.log('日志已写入:', base);
} catch (e) {
  console.log('日志落盘失败:', String(e));
}

try { ws && ws.close(); } catch {}
chrome.kill();
await sleep(400);
try { rmSync(profile, { recursive: true, force: true }); } catch {}
process.exit(result.state && result.state.ok ? 0 : 1);
