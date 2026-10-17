/**
 * GLB 优化管线（可复现）
 * =====================
 * 背景（2026-09-22 实测）：Blender 导出的 GLB 把同一份几何重复写了 697 次，
 * 未压缩 5067 KB；用 gltf-transform 的 dedup 后 **降到 550 KB（9.2 倍）**，
 * 且 Three.js 侧直接拿到共享的 BufferGeometry（唯一实例数 697 → 60），
 * extras（lb_group 等契约字段）零丢失。
 *
 * 因此本项目**不再需要 Draco**：dedup 后的文件比 Draco 版（1620 KB）更小，
 * 而且浏览器端不需要加载 ~250 KB 的解码器，也不需要 .wasm 支持。
 *
 * 用法：
 *   node tools/optimize_glb.mjs <输入.glb> [输出.glb] [--draco]
 * 例：
 *   node tools/optimize_glb.mjs output/stage1/teach_model_raw.glb output/stage1/teach_model.glb
 */
import { spawnSync } from 'node:child_process';
import { existsSync, statSync, renameSync, mkdtempSync, rmSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const CLI = join(HERE, 'gltf', 'node_modules', '@gltf-transform', 'cli', 'bin', 'cli.js');

const argv = process.argv.slice(2);
const wantDraco = argv.includes('--draco');
const pos = argv.filter((a) => !a.startsWith('--'));
const input = pos[0];
const output = pos[1] || input.replace(/\.glb$/i, '.opt.glb');

if (!input || !existsSync(input)) {
  console.error('用法: node optimize_glb.mjs <输入.glb> [输出.glb] [--draco]');
  console.error('输入不存在:', input);
  process.exit(2);
}
if (!existsSync(CLI)) {
  console.error('未找到 gltf-transform CLI：', CLI);
  console.error('请先安装：  cd tools/gltf && npm install @gltf-transform/cli@4.5.0 --legacy-peer-deps');
  process.exit(2);
}

const kb = (p) => (statSync(p).size / 1024).toFixed(0) + ' KB';
const run = (args) => {
  const r = spawnSync(process.execPath, [CLI, ...args], { encoding: 'utf8' });
  if (r.status !== 0) {
    console.error('步骤失败:', args.join(' '));
    console.error((r.stdout || '') + (r.stderr || ''));
    process.exit(1);
  }
  return r.stdout || '';
};

console.log('输入 :', input, '→', kb(input));
const tmp = mkdtempSync(join(tmpdir(), 'glbopt-'));
const step1 = join(tmp, 'step1.glb');
const step2 = join(tmp, 'step2.glb');

// 1) 几何去重：把重复的顶点缓冲合并成一份（本步骤解决 90% 的体积）
run(['dedup', resolve(input), step1]);
console.log('dedup:', kb(step1));

// 2) 清理未被引用的资源（删掉导出残留的孤立 accessor / 材质）
run(['prune', step1, step2]);
console.log('prune:', kb(step2));

// 3) 可选：Draco。默认不开 —— dedup 后文件已更小，且开 Draco 会强制浏览器加载解码器
let finalSrc = step2;
if (wantDraco) {
  const step3 = join(tmp, 'step3.glb');
  run(['draco', step2, step3]);
  console.log('draco:', kb(step3));
  finalSrc = step3;
}

// 4) 落盘
if (existsSync(output)) rmSync(output, { force: true });
try {
  renameSync(finalSrc, output);
} catch {
  // 跨卷时 rename 会失败，退回复制
  const { copyFileSync } = await import('node:fs');
  copyFileSync(finalSrc, output);
}
rmSync(tmp, { recursive: true, force: true });

console.log('输出 :', output, '→', kb(output));
console.log('压缩比:', (statSync(input).size / statSync(output).size).toFixed(1) + 'x');
