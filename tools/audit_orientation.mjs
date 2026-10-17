/**
 * 机翼 / 尾翼朝向审计
 * ==================
 * "方向是反的"这种判断必须落到数值上，否则改完还是错。
 * 本脚本读 GLB，对每个部件组算出：
 *   - 展向（哪一端是翼尖）与根弦位置
 *   - 后掠方向：翼尖相对翼根是往后（X 变小，正确）还是往前（X 变大，反了）
 *   - 上反角（dihedral）
 *   - 法线朝向：面法线是否指向实体外侧（判断是否法线翻转 / 面片内外颠倒）
 *
 * 坐标系：机头朝 +X，左为 +Z（Blender y 负 → glTF z 正），上为 +Y
 *   因此"左翼"= Z 为正的一侧，"右翼"= Z 为负的一侧。
 *
 * 用法: node tools/audit_orientation.mjs <glb>
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { readFileSync, writeFileSync } from 'node:fs';

const GLB = process.argv[2];
const OUT = process.argv[3] || 'C:/Users/96258/AppData/Local/Temp/orient_audit.txt';

const buf = readFileSync(GLB);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const gltf = await new Promise((r, j) => new GLTFLoader().parse(ab, '', r, j));

// 按拆解组收集世界空间顶点
const groups = new Map();
gltf.scene.updateWorldMatrix(true, true);
gltf.scene.traverse((o) => {
  if (!o.isMesh) return;
  const g = (o.userData && o.userData.lb_group) || '?';
  if (!groups.has(g)) groups.set(g, []);
  const pos = o.geometry.attributes.position;
  const nor = o.geometry.attributes.normal;
  const v = new THREE.Vector3();
  const n = new THREE.Vector3();
  const nm = new THREE.Matrix3().getNormalMatrix(o.matrixWorld);
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
    if (nor) n.fromBufferAttribute(nor, i).applyMatrix3(nm).normalize();
    groups.get(g).push({ x: v.x, y: v.y, z: v.z, nx: n.x, ny: n.y, nz: n.z, name: o.name });
  }
});

const L = [];
const p = (...a) => L.push(a.map(String).join(' '));
const f = (x, d = 2) => Number(x).toFixed(d);

function stats(g) {
  const pts = groups.get(g) || [];
  if (!pts.length) return null;
  let mn = { x: 1e9, y: 1e9, z: 1e9 }, mx = { x: -1e9, y: -1e9, z: -1e9 };
  for (const q of pts) {
    mn.x = Math.min(mn.x, q.x); mx.x = Math.max(mx.x, q.x);
    mn.y = Math.min(mn.y, q.y); mx.y = Math.max(mx.y, q.y);
    mn.z = Math.min(mn.z, q.z); mx.z = Math.max(mx.z, q.z);
  }
  return { pts, mn, mx, n: pts.length };
}

/* ---------- 1. 机翼后掠 / 上反 ---------- */
function wing(g, sideSign) {
  const s = stats(g);
  if (!s) { p(`  ${g}: 无数据`); return; }
  const { pts, mn, mx } = s;
  // 翼尖 = |z| 最大的一批点；翼根 = z 最接近 0 的一批点
  const zAbsMax = Math.max(Math.abs(mn.z), Math.abs(mx.z));
  const tipZ = sideSign > 0 ? mx.z : mn.z;
  const tip = pts.filter((q) => Math.abs(q.z - tipZ) < zAbsMax * 0.06);
  const root = pts.filter((q) => Math.abs(q.z) < zAbsMax * 0.10);
  const avg = (arr, k) => arr.reduce((a, b) => a + b[k], 0) / (arr.length || 1);

  const tipX = avg(tip, 'x'), rootX = avg(root, 'x');
  const tipY = avg(tip, 'y'), rootY = avg(root, 'y');
  const tipN = tip.length, rootN = root.length;

  // 前缘(X 大) 与 后缘(X 小)
  const tipLE = tip.reduce((a, b) => Math.max(a, b.x), -1e9);
  const tipTE = tip.reduce((a, b) => Math.min(a, b.x), 1e9);
  const rootLE = root.reduce((a, b) => Math.max(a, b.x), -1e9);
  const rootTE = root.reduce((a, b) => Math.min(a, b.x), 1e9);

  const span = Math.abs(tipZ);
  const sweep = Math.atan2(rootLE - tipLE, span) * 180 / Math.PI;   // 前缘后掠角
  const dihedral = Math.atan2(tipY - rootY, span) * 180 / Math.PI;

  p(`  ${g}  (Z ${f(mn.z)} → ${f(mx.z)}, /|Z|max=${f(zAbsMax)})`);
  p(`     翼根 z≈${f(avg(root, 'z'))}  n=${rootN}   翼尖 z≈${f(tipZ)}  n=${tipN}`);
  p(`     翼根弦: LE x=${f(rootLE)}  TE x=${f(rootTE)}  弦长=${f(rootLE - rootTE)}`);
  p(`     翼尖弦: LE x=${f(tipLE)}  TE x=${f(tipTE)}  弦长=${f(tipLE - tipTE)}`);
  p(`     前缘后掠角 = ${f(sweep, 1)}°   ${sweep > 3 ? '（后掠，正确 ✔）' : sweep < -3 ? '（★前掠 —— 方向反了）' : '（近平直）'}`);
  p(`     上反角     = ${f(dihedral, 1)}°   ${dihedral > 1 ? '（上反，正确 ✔）' : dihedral < -1 ? '（★下反 —— 可疑）' : '（水平）'}`);
  p(`     翼根厚度(Y) = ${f(root.reduce((a, b) => Math.max(a, b.y), -1e9) - root.reduce((a, b) => Math.min(a, b.y), 1e9))}` +
    `   翼尖厚度(Y) = ${f(tip.reduce((a, b) => Math.max(a, b.y), -1e9) - tip.reduce((a, b) => Math.min(a, b.y), 1e9))}`);
}

/* ---------- 2. 尾翼 ---------- */
function tailHS(g) {
  const s = stats(g);
  if (!s) { p(`  ${g}: 无数据`); return; }
  const { pts, mn, mx } = s;
  const zAbsMax = Math.max(Math.abs(mn.z), Math.abs(mx.z));
  p(`  ${g}  X ${f(mn.x)} → ${f(mx.x)}   |Z|max=${f(zAbsMax)}   Y ${f(mn.y)} → ${f(mx.y)}`);
  const left = pts.filter((q) => q.z > zAbsMax * 0.9);
  const root = pts.filter((q) => Math.abs(q.z) < zAbsMax * 0.15);
  if (left.length && root.length) {
    const avg = (arr, k) => arr.reduce((a, b) => a + b[k], 0) / arr.length;
    const span = avg(left, 'z');
    const sweep = Math.atan2(avg(root, 'x') - avg(left, 'x'), span) * 180 / Math.PI;
    p(`     左端 z≈${f(span)}  前缘后掠 = ${f(sweep, 1)}°   ${sweep > 3 ? '（后掠 ✔）' : sweep < -3 ? '（★前掠 —— 反了）' : '（平直）'}`);
  }
}

function tailVS(g) {
  const s = stats(g);
  if (!s) { p(`  ${g}: 无数据`); return; }
  const { pts, mn, mx } = s;
  const yTop = mx.y;
  const top = pts.filter((q) => q.y > mn.y + (mx.y - mn.y) * 0.9);
  const bot = pts.filter((q) => q.y < mn.y + (mx.y - mn.y) * 0.1);
  const avg = (arr, k) => arr.reduce((a, b) => a + b[k], 0) / (arr.length || 1);
  p(`  ${g}  Y ${f(mn.y)} → ${f(mx.y)}   X ${f(mn.x)} → ${f(mx.x)}`);
  p(`     顶部前缘 x=${f(top.reduce((a, b) => Math.max(a, b.x), -1e9))}  底部前缘 x=${f(bot.reduce((a, b) => Math.max(a, b.x), -1e9))}`);
  const lean = avg(top, 'x') - avg(bot, 'x');
  p(`     后倾量 = ${f(lean)}   ${lean < -0.2 ? '（后倾，正确 ✔）' : lean > 0.2 ? '（★前倾 —— 反了）' : '（近垂直）'}`);
}

/* ---------- 3. 法线朝向 ---------- */
function normals(g) {
  const s = stats(g);
  if (!s) return;
  const { pts, mn, mx } = s;
  const c = { x: (mn.x + mx.x) / 2, y: (mn.y + mx.y) / 2, z: (mn.z + mx.z) / 2 };
  let out = 0, inn = 0;
  for (const q of pts) {
    const dx = q.x - c.x, dy = q.y - c.y, dz = q.z - c.z;
    const d = dx * q.nx + dy * q.ny + dz * q.nz;
    if (d > 0) out++; else inn++;
  }
  const pct = 100 * inn / (out + inn || 1);
  p(`  ${g.padEnd(14)} 朝外 ${out} / 朝内 ${inn}  → 朝内占比 ${f(pct, 1)}%  ` +
    `${pct > 55 ? '★ 法线可能整体翻转' : '（朝向合理）'}`);
}

p('════════ 机翼 ════════');
p('约定：机头 +X，左 = +Z，上 = +Y');
for (const g of ['WING_L', 'WING_R', 'WING_FENCE']) {
  wing(g, g === 'WING_R' ? -1 : 1);
  p('');
}
p('════════ 尾翼 ════════');
tailHS('TAIL_HS');
p('');
tailVS('TAIL_VS');
p('');
p('════════ 法线朝向抽查 ════════');
for (const g of ['WING_L', 'WING_R', 'TAIL_HS', 'TAIL_VS', 'HULL_UPPER',
                 'ENG_L', 'ENG_R', 'CARGO_1', 'PAX_0A', 'BELLY_FAIRING', 'DOORS', 'WINDOWS',
                 'GEAR_N', 'FUEL_WING_L']) {
  normals(g);
}
p('');
p('════════ 全部组一览（尺寸与中心）════════');
for (const g of [...groups.keys()].sort()) {
  const s = stats(g);
  if (!s) continue;
  const { mn, mx, n } = s;
  p(`  ${g.padEnd(14)} n=${String(n).padStart(6)}  中心(${f((mn.x + mx.x) / 2)},${f((mn.y + mx.y) / 2)},${f((mn.z + mx.z) / 2)})  尺寸(${f(mx.x - mn.x)},${f(mx.y - mn.y)},${f(mx.z - mn.z)})`);
}

writeFileSync(OUT, L.join('\n'), 'utf-8');
console.log(L.join('\n'));
