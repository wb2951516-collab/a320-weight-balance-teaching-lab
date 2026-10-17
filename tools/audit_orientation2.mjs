/**
 * 朝向审计 v2 —— 分带测量（修正 v1 的采样缺陷）
 * ==============================================
 * v1 的问题：用"最高/最低角点"代表尾翼顶/底，样本落在单个角上，
 * 对旋转过的长方体给出的结论是错的（已确认 v1 的垂尾判定不可信）。
 *
 * v2 做法：沿展向（|Z|）或高度（Y）分 N 个带，每带内取
 *   前缘 = max(X)、后缘 = min(X)、弦长 = 前缘 − 后缘
 * 然后看这些量随带宽的变化趋势。趋势用线性拟合的斜率判定，抗单点噪声。
 *
 * 判据（机头 +X）：
 *   后掠(正确) → 前缘 X 随 |Z| 增大而减小（斜率 < 0）
 *   前掠(反了) → 斜率 > 0
 *   后倾(正确) → 垂尾前缘 X 随 Y 增大而减小
 *
 * 用法: node tools/audit_orientation2.mjs <glb>
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { readFileSync, writeFileSync } from 'node:fs';

const GLB = process.argv[2];
const OUT = process.argv[3] || 'C:/Users/96258/AppData/Local/Temp/orient2.txt';

const buf = readFileSync(GLB);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const gltf = await new Promise((r, j) => new GLTFLoader().parse(ab, '', r, j));

const groups = new Map();
gltf.scene.updateWorldMatrix(true, true);
gltf.scene.traverse((o) => {
  if (!o.isMesh) return;
  const g = (o.userData && o.userData.lb_group) || '?';
  if (!groups.has(g)) groups.set(g, []);
  const pos = o.geometry.attributes.position;
  const v = new THREE.Vector3();
  const arr = groups.get(g);
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
    arr.push(v.clone());
  }
});

const L = [];
const p = (...a) => L.push(a.map(String).join(' '));
const f = (x, d = 2) => Number(x).toFixed(d);

function bbox(pts) {
  const mn = new THREE.Vector3(1e9, 1e9, 1e9), mx = new THREE.Vector3(-1e9, -1e9, -1e9);
  for (const q of pts) { mn.min(q); mx.max(q); }
  return { mn, mx };
}

/** 线性拟合 y = a + b·x，返回斜率 b */
function slope(xs, ys) {
  const n = xs.length;
  if (n < 3) return NaN;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) { num += (xs[i] - mx) * (ys[i] - my); den += (xs[i] - mx) ** 2; }
  return den === 0 ? NaN : num / den;
}

/** 沿 axis 分带，返回 [{t, front, rear, chord, n}] */
function bandStats(pts, axis, bands = 10) {
  const key = axis === 'zabs' ? (q) => Math.abs(q.z) : (q) => q[axis];
  const vals = pts.map(key);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const w = (hi - lo) / bands || 1;
  const out = [];
  for (let b = 0; b < bands; b++) {
    const a0 = lo + b * w, a1 = a0 + w;
    const sel = pts.filter((q) => { const k = key(q); return k >= a0 && (b === bands - 1 ? k <= a1 : k < a1); });
    if (!sel.length) continue;
    let front = -1e9, rear = 1e9;
    for (const q of sel) { front = Math.max(front, q.x); rear = Math.min(rear, q.x); }
    out.push({ t: (a0 + a1) / 2, front, rear, chord: front - rear, n: sel.length });
  }
  return out;
}

function report(name, pts, axis, bands = 10) {
  if (!pts || !pts.length) { p(`  ${name}: 无数据`); return; }
  const bb = bbox(pts);
  p(`  ${name}  点=${pts.length}`);
  p(`     包围盒 X ${f(bb.mn.x)}→${f(bb.mx.x)}   Y ${f(bb.mn.y)}→${f(bb.mx.y)}   Z ${f(bb.mn.z)}→${f(bb.mx.z)}`);
  const bs = bandStats(pts, axis, bands);
  p(`     ${axis === 'zabs' ? '|Z|' : 'Y'} 带  前缘X    后缘X    弦长   点数`);
  for (const b of bs) {
    p(`     ${f(b.t, 2).padStart(6)}  ${f(b.front).padStart(8)} ${f(b.rear).padStart(8)} ${f(b.chord).padStart(8)}  ${String(b.n).padStart(5)}`);
  }
  const sl = slope(bs.map((b) => b.t), bs.map((b) => b.front));
  const chordSlope = slope(bs.map((b) => b.t), bs.map((b) => b.chord));
  p(`     前缘X 对 ${axis === 'zabs' ? '|Z|' : 'Y'} 的斜率 = ${f(sl, 4)}`);
  p(`     弦长   对 ${axis === 'zabs' ? '|Z|' : 'Y'} 的斜率 = ${f(chordSlope, 4)}`);
  if (axis === 'zabs') {
    p(`     后掠判定: ${sl < -0.005 ? '后掠 ✔ 正确' : sl > 0.005 ? '★ 前掠 —— 反了' : '近平直'}`);
    const c0 = bs[0].chord, cN = bs[bs.length - 1].chord;
    p(`     锥度判定: 内端弦长 ${f(c0)} → 外端弦长 ${f(cN)}   ` +
      `${c0 > cN * 1.15 ? '根粗尖细 ✔ 正常' : cN > c0 * 1.15 ? '★ 尖粗根细 —— 倒锥，不正常' : '（近似等弦）'}`);
  } else {
    // 垂尾这类"竖直平板"：不能用"最高角点 vs 最低角点"比 X ——
    // 对旋转过的长方体，最高点恰好是前角、最低点恰好是后角，比出来必然相反（踩过）。
    // 正确做法：比较顶面与底面的**中点**（等价于中弦线），它才代表翼面的倾斜方向。
    const ys = pts.map((q) => q.y);
    const ylo = Math.min(...ys), yhi = Math.max(...ys), yr = yhi - ylo || 1;
    const slice = (a, b) => pts.filter((q) => q.y >= a && q.y <= b);
    const topS = slice(yhi - yr * 0.08, yhi);
    const botS = slice(ylo, ylo + yr * 0.08);
    const midX = (arr) => arr.reduce((s, q) => s + q.x, 0) / (arr.length || 1);
    const tm = midX(topS), bm = midX(botS);
    const d = tm - bm;
    p(`     顶面中点 x=${f(tm)}（${topS.length} 点）  底面中点 x=${f(bm)}（${botS.length} 点）  差值=${f(d)}`);
    p(`     后倾判定（中弦线）: ${d < -0.01 ? '后倾 ✔ 正确' : d > 0.01 ? '★ 前倾 —— 反了' : '近垂直'}`);
    p(`     注：若上一行与本仓库 stage1_export.py 的"朝向断言"矛盾，以那边的角点法为准。`);
  }
  p('');
}

p('════════ 机翼（按 |Z| 分带，机头 +X）════════');
report('WING_L（左，+Z）', groups.get('WING_L'), 'zabs', 10);
report('WING_R（右，−Z）', groups.get('WING_R'), 'zabs', 10);
p('════════ 平尾 ════════');
report('TAIL_HS（整体，跨左右）', groups.get('TAIL_HS'), 'zabs', 8);
p('════════ 垂尾（按 Y 分带）════════');
report('TAIL_VS', groups.get('TAIL_VS'), 'y', 10);

p('════════ 参照：机身与发动机 ════════');
report('HULL_UPPER', groups.get('HULL_UPPER'), 'zabs', 6);
report('ENG_L', groups.get('ENG_L'), 'zabs', 6);

writeFileSync(OUT, L.join('\n'), 'utf-8');
console.log(L.join('\n'));
