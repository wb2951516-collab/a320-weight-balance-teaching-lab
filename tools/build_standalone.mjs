/**
 * 打包「双击即开」的自包含单文件课件
 * =====================================
 * 为什么要做这个：
 *   web/ 目录那版依赖 ES 模块 + fetch，在 file:// 下会被浏览器整体拦截，
 *   必须先起本地 HTTP 服务（启动预览.cmd）。而教室/发给同事的场景里，
 *   "双击打开"才是最可靠的交付方式。
 *
 * 做法：
 *   1. 从 web/index.html 抽出 <script type="module"> 的代码体（保持单一真源）
 *   2. 把 GLB 编成 base64 data URI、labels.json 内联为对象，替换掉两处网络请求
 *   3. 用 esbuild 打包成 **IIFE（经典脚本）** —— 彻底不用 ES 模块，file:// 下也能跑
 *   4. 把打包结果内联回 HTML，去掉 importmap 与 file:// 诊断段
 *
 * 用法：
 *   node tools/build_standalone.mjs
 * 产出：
 *   output/stage1/配载教学三维拆解.html
 */
import { build } from 'esbuild';
import { readFileSync, writeFileSync, mkdtempSync, rmSync, existsSync, statSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJ = resolve(HERE, '..');
const WEB = join(PROJ, 'output', 'stage1', 'web');
// three 从 tools 的 npm 依赖解析（r186）。旧值 'D:/three.js' 指向的源码目录
// 已被清空（只剩一个 Legacy 文件），照旧会打包失败。
const THREE_DIR = join(PROJ, 'tools', 'node_modules', 'three');
const NM = join(WEB, 'vendor', 'npm', 'node_modules');
const SRC_HTML = join(WEB, 'index.html');
const GLB = join(WEB, 'teach_model.glb');
const LABELS = join(WEB, 'labels.json');
const GROUPS = join(PROJ, 'output', 'stage1', 'groups.json');
const OUT_HTML = join(PROJ, 'output', 'stage1', '配载教学三维拆解.html');

for (const [name, p] of [['index.html', SRC_HTML], ['teach_model.glb', GLB],
                         ['labels.json', LABELS], ['groups.json', GROUPS],
                         ['esbuild', join(PROJ, 'tools', 'gltf', 'node_modules', 'esbuild')]]) {
  if (!existsSync(p)) { console.error('缺少依赖:', name, '->', p); process.exit(2); }
}

let html = readFileSync(SRC_HTML, 'utf8');

// ---- 1. 抽出 module 脚本体 ----
// 注意：必须按「行首」锚定。诊断脚本的注释里出现过 "<script type="module">" 这几个字，
// 用 indexOf 会匹配到注释里，抽出一段垃圾代码（此处曾真实踩过）。
const MOD_RE = /\n<script type="module">([\s\S]*?)<\/script>/;
const modMatch = html.match(MOD_RE);
if (!modMatch) { console.error('index.html 中找不到行首的 <script type="module">'); process.exit(2); }
let appCode = modMatch[1];
if (!appCode.includes('loader.load(')) {
  console.error('抽出的 module 代码不像应用代码（未含 loader.load），中止以免产出坏文件');
  process.exit(2);
}

// ---- 2. 把两处网络请求换成内联数据 ----
const glbB64 = readFileSync(GLB).toString('base64');
const labelsObj = JSON.parse(readFileSync(LABELS, 'utf8'));
console.log('GLB  base64:', (glbB64.length / 1024 / 1024).toFixed(2), 'MB');
console.log('标注条数   :', labelsObj.count);

if (!appCode.includes("loader.load('./teach_model.glb'")) {
  console.error("未找到 loader.load('./teach_model.glb')，无法替换；index.html 可能被改过");
  process.exit(2);
}
appCode = appCode.replace("loader.load('./teach_model.glb'", 'loader.load(window.__GLB_DATA__');
appCode = appCode.replace(
  "await (await fetch('./labels.json')).json()",
  'window.__LABELS__');

// ---- 3. esbuild 打包成 IIFE ----
const tmp = mkdtempSync(join(tmpdir(), 'standalone-'));
const entry = join(tmp, 'entry.js');
writeFileSync(entry, appCode, 'utf8');

const aliasPlugin = {
  name: 'local-alias',
  setup(b) {
    const map = {
      'three': join(THREE_DIR, 'build', 'three.module.js'),
      'three-mesh-bvh': join(NM, 'three-mesh-bvh', 'src', 'index.js'),
      'camera-controls': join(NM, 'camera-controls', 'dist', 'camera-controls.module.js'),
      'troika-three-text': join(NM, 'troika-three-text', 'dist', 'troika-three-text.esm.js'),
      'troika-three-utils': join(NM, 'troika-three-utils', 'dist', 'troika-three-utils.esm.js'),
      'troika-worker-utils': join(NM, 'troika-worker-utils', 'dist', 'troika-worker-utils.esm.js'),
      'webgl-sdf-generator': join(NM, 'webgl-sdf-generator', 'dist', 'webgl-sdf-generator.mjs'),
      'bidi-js': join(NM, 'bidi-js', 'dist', 'bidi.mjs')
    };
    b.onResolve({ filter: /^three\/addons\// }, (a) => ({
      path: join(THREE_DIR, 'examples', 'jsm', a.path.slice('three/addons/'.length))
    }));
    b.onResolve({ filter: /.*/ }, (a) => {
      if (map[a.path]) return { path: map[a.path] };
      return null;
    });
  }
};

const bundlePath = join(tmp, 'bundle.js');
await build({
  entryPoints: [entry],
  bundle: true,
  format: 'iife',            // 经典脚本：file:// 下不受 ES 模块限制
  target: ['chrome100'],
  minify: false,             // 不压缩，便于课堂排障时读代码
  legalComments: 'none',
  outfile: bundlePath,
  plugins: [aliasPlugin],
  logLevel: 'warning',
  // ★ IIFE 下 import.meta.url 为空，DRACOLoader 会执行
  //   new URL('../libs/draco/…', '') 并抛 TypeError: Invalid URL。
  //   内联脚本里 import.meta.url 的等价物就是 document.baseURI（同为该页面的 URL），
  //   替换后 URL 构造合法。本项目交付的 GLB 是 dedup 版不含 Draco，仅保证不抛错。
  define: { 'import.meta.url': 'document.baseURI' }
});
let bundle = readFileSync(bundlePath, 'utf8');

// 内联数据放在 bundle 之前
const dataScript =
  '<script>\n' +
  '/* 内联资源：GLB（base64）、标注清单、分组数据表。双击即可打开，无需本地服务。 */\n' +
  'window.__GLB_DATA__ = "data:model/gltf-binary;base64,' + glbB64 + '";\n' +
  'window.__LABELS__ = ' + JSON.stringify(labelsObj) + ';\n' +
  'window.__GROUPS__ = ' + JSON.stringify(JSON.parse(readFileSync(GROUPS, 'utf8'))) + ';\n' +
  '</script>\n';

// ---- 4. 组装 HTML ----
// 去掉 importmap（IIFE 不再需要）
html = html.replace(/<script type="importmap">[\s\S]*?<\/script>\s*/g, '');
// 去掉 file:// 诊断段（这一版正是要在 file:// 下跑，留着会误报）
const diagStart = html.indexOf('<script>\n/* ─');
const diagEnd = diagStart >= 0 ? html.indexOf('</script>', diagStart) + '</script>\n'.length : -1;
if (diagStart >= 0 && diagEnd > 0) html = html.slice(0, diagStart) + html.slice(diagEnd);
// 用内联数据 + 打包结果整体替换 module 脚本（同样按行首锚定）
// ★ 必须用「替换函数」而不是字符串：String.replace 的替换串里 `$` 有特殊含义
//   （$& $` $' $1 …），而应用代码里到处是 $('id') 与 ${...}，
//   用字符串会把整段 HTML 重复插入，产出体积暴涨（此处曾真实踩过：11.4 MB）。
html = html.replace(MOD_RE, () => '\n' + dataScript + '<script>\n' + bundle + '\n</script>');

const finalLen = Buffer.byteLength(html, 'utf8');
const expectMax = (bundle.length + glbB64.length + 400 * 1024);
if (finalLen > expectMax) {
  console.error('产出体积异常：', (finalLen / 1048576).toFixed(1), 'MB，超出预期上限',
                (expectMax / 1048576).toFixed(1), 'MB —— 大概率发生了内容重复插入');
  process.exit(2);
}
if (!html.includes('window.__GLB_DATA__')) {
  console.error('内联数据未注入，产出可能不完整');
  process.exit(2);
}
// 标题与提示
html = html.replace('<title>配载教学 · 三维拆解验证（Stage 1b）</title>',
                    '<title>配载教学 · 三维拆解（自包含单文件版）</title>');
html = html.replace('<h1>三维拆解验证</h1>', '<h1>三维拆解 · 单文件版</h1>');
html = html.replace(/<div class="sub">[\s\S]*?<\/div>/,
  '<div class="sub">自包含单文件：GLB 与标注已内联，<b>双击即可打开</b>，无需本地服务、无需联网。<br>' +
  '由 <code>tools/build_standalone.mjs</code> 从 <code>web/index.html</code> 自动生成，勿手工改本文件。</div>');

writeFileSync(OUT_HTML, html, 'utf8');
rmSync(tmp, { recursive: true, force: true });

const kb = (p) => (statSync(p).size / 1024).toFixed(0) + ' KB';
console.log('');
console.log('源 index.html :', kb(SRC_HTML));
console.log('bundle        :', (bundle.length / 1024).toFixed(0), 'KB');
console.log('产出           :', OUT_HTML, '->', kb(OUT_HTML));
// 校验：最终文件里不应再有真正的 ES import 语句（注释/字符串里的词不算）
const esImport = /(^|\n)\s*import\s+[\w{*'"]/.test(html) || /\n\s*import\s*\(/.test(html);
console.log('含 ES 模块 import 语句 :', esImport ? '是（异常！）' : '否 ✔');
console.log('含 type="module" 标签  :', /<script\s+type="module"/.test(html) ? '是（异常！）' : '否 ✔');
console.log('含 importmap           :', /type="importmap"/.test(html) ? '是（异常！）' : '否 ✔');
