import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { readFileSync, writeFileSync } from 'node:fs';

const GLB = process.argv[2];
const OUT = process.argv[3] || 'C:/Users/96258/AppData/Local/Temp/waves.txt';
const buf = readFileSync(GLB);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const gltf = await new Promise((r, j) => new GLTFLoader().parse(ab, '', r, j));

const L = [];
const p = (...a) => L.push(a.map(String).join(' '));
const byLayer = new Map();
const dirs = new Map();

gltf.scene.traverse((o) => {
  if (!o.isMesh) return;
  const ud = o.userData || {};
  const g = ud.lb_group || '?';
  const L2 = ud.lb_layer ?? -1;
  if (!byLayer.has(L2)) byLayer.set(L2, new Map());
  const m = byLayer.get(L2);
  m.set(g, (m.get(g) || 0) + 1);
  const d = (ud.lb_dir || [0, 0, 0]).map((v) => Number(v).toFixed(2)).join(',');
  dirs.set(g, d);
});

const NAME = { 0: '不拆解（标注/环境）', 1: '起落架', 2: '腹板/下壳', 3: '货舱+行李',
  4: '货舱地板', 5: '客舱地板', 6: '客舱座椅', 7: '上壳体', 8: '机翼',
  9: '燃油', 10: '发动机', 11: '尾翼', 12: '舱门/舷窗/标识' };

p('契约 v2 波次自检（机头 +X，Blender 系方向：−Z=下，−Y=左，+Z=上）');
p('='.repeat(84));
let total = 0, layerSum = 0;
for (const k of [...byLayer.keys()].sort((a, b) => a - b)) {
  const m = byLayer.get(k);
  const n = [...m.values()].reduce((a, b) => a + b, 0);
  total += n;
  if (k > 0) layerSum += n;
  p('');
  p(`layer ${String(k).padStart(2)}  ${NAME[k] || ''}   共 ${n} 个物件`);
  for (const [g, c] of [...m.entries()].sort()) {
    p(`      ${g.padEnd(14)} ${String(c).padStart(4)}   方向(${dirs.get(g)})`);
  }
}
p('');
p('='.repeat(84));
p(`渲染节点合计 ${total}；参与拆解（layer>=1）${layerSum}；不拆解 ${total - layerSum}`);
const waves = [...byLayer.keys()].filter((k) => k > 0).sort((a, b) => a - b);
p(`波次：${waves.join(', ')}  （共 ${waves.length} 波，期望 12）`);
p(waves.length === 12 ? 'PASS：12 波齐备' : '★ FAIL：波次数不为 12');

writeFileSync(OUT, L.join('\n'), 'utf-8');
console.log(L.join('\n'));
