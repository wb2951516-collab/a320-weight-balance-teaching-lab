/**
 * dump_group.mjs —— 列出指定组内每个网格的「名字 / 世界坐标 / 几何尺寸 / 世界 AABB」。
 *
 * 用途：定位"某个零件到底在哪"。graphics 层面（AABB 相交、位置对不对）靠肉眼从低分辨率
 * 截图判断极不可靠——本文件就是为此而生（风扇错位 13 m 那次，猜了四轮都没中，
 * 最后是读数据才定案的：位移没乘进度 progIn(T,...)）。
 *
 * 用法：node tools/dump_group.mjs <glb> ENG_L [ENG_R ...]
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
// 用裸模块名（与 audit_explode.mjs 同源）：three 装在 tools/node_modules，
// 会从本文件所在目录向上解析。**不要**自己拼 file:// URL 去 tools/gltf/node_modules
// ——那里没有 three（踩过：ERR_MODULE_NOT_FOUND）。
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

const GLB = process.argv[2];
const argv = process.argv.slice(3);
if (!GLB || argv.length === 0) {
  console.error('用法: node tools/dump_group.mjs <glb> <组名> [组名...] | --all');
  process.exit(2);
}

const buf = readFileSync(GLB);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const gltf = await new Promise((res, rej) => new GLTFLoader().parse(ab, '', res, rej));
gltf.scene.updateWorldMatrix(true, true);

// --all：列出所有组并按 X 中心排序 —— 用来判断"机头朝哪边"（最高 X 的那组就是机头端）
let WANT = argv;
if (argv[0] === '--all') {
  const seen = new Map();
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    const g = (o.userData || {}).lb_group || '?';
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    const b = new THREE.Box3().copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld);
    if (!seen.has(g)) seen.set(g, new THREE.Box3());
    seen.get(g).union(b);
  });
  const arr = [...seen.entries()].map(([g, b]) => ({
    g, c: b.getCenter(new THREE.Vector3()), b,
  })).sort((a, c) => c.c.x - a.c.x);
  const out = [];
  out.push('=== 全部组（按 X 中心降序）—— X 最大端即机头方向 ===');
  out.push('  组名              X中心     Y中心     Z中心      X范围');
  out.push('  ' + '-'.repeat(84));
  for (const r of arr) {
    out.push(`  ${r.g.padEnd(16)} ${r.c.x.toFixed(2).padStart(7)}  ${r.c.y.toFixed(2).padStart(7)}  ` +
             `${r.c.z.toFixed(2).padStart(7)}   [${r.b.min.x.toFixed(2)}, ${r.b.max.x.toFixed(2)}]`);
  }
  const p0 = join(process.env.TEMP || '.', 'dump_groups_all.txt');
  writeFileSync(p0, out.join('\n'), 'utf-8');
  console.log(out.join('\n'));
  console.log('\n已写入: ' + p0);
  process.exit(0);
}

const f = (v) => Number(v).toFixed(2).padStart(8);
const L = [];
const p = (s) => L.push(String(s));

for (const want of WANT) {
  const rows = [];
  const union = new THREE.Box3();
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    if ((o.userData || {}).lb_group !== want) return;
    if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
    const box = new THREE.Box3().copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld);
    union.union(box);
    const pos = new THREE.Vector3(), q = new THREE.Quaternion(), sc = new THREE.Vector3();
    o.matrixWorld.decompose(pos, q, sc);
    const gs = o.geometry.boundingBox.getSize(new THREE.Vector3());
    rows.push({ name: o.name, pos, gs, box, verts: o.geometry.attributes.position.count });
  });
  p('');
  p(`=== 组 ${want} —— ${rows.length} 个网格 ===`);
  p('  名字                    顶点   几何尺寸(XYZ)              世界AABB  X                Y                Z');
  p('  ' + '-'.repeat(112));
  rows.sort((a, b) => b.pos.x - a.pos.x);
  for (const r of rows) {
    p(`  ${(r.name || '(无名)').padEnd(22)} ${String(r.verts).padStart(6)}  ` +
      `${f(r.gs.x)},${f(r.gs.y)},${f(r.gs.z)}   ` +
      `[${f(r.box.min.x)},${f(r.box.max.x)}] [${f(r.box.min.y)},${f(r.box.max.y)}] [${f(r.box.min.z)},${f(r.box.max.z)}]`);
  }
  const c = union.getCenter(new THREE.Vector3()), s = union.getSize(new THREE.Vector3());
  p(`  ${'-'.repeat(112)}`);
  p(`  组并集 AABB：中心 (${c.x.toFixed(2)}, ${c.y.toFixed(2)}, ${c.z.toFixed(2)})  ` +
    `尺寸 (${s.x.toFixed(2)}, ${s.y.toFixed(2)}, ${s.z.toFixed(2)})`);
  p(`  组并集范围：X [${union.min.x.toFixed(2)}, ${union.max.x.toFixed(2)}]  ` +
    `Y [${union.min.y.toFixed(2)}, ${union.max.y.toFixed(2)}]  Z [${union.min.z.toFixed(2)}, ${union.max.z.toFixed(2)}]`);
}

const out = join(process.env.TEMP || '.', 'dump_group.txt');
writeFileSync(out, L.join('\n'), 'utf-8');
console.log(L.join('\n'));
console.log('\n已写入: ' + out);
