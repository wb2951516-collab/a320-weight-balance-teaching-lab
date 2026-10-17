import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { readFileSync, writeFileSync } from 'node:fs';

const GLB = process.argv[2];
const OUT = 'C:/Users/96258/AppData/Local/Temp/panels.txt';
const buf = readFileSync(GLB);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const gltf = await new Promise((r, j) => new GLTFLoader().parse(ab, '', r, j));

const f = (v, d = 2) => Number(v).toFixed(d).padStart(8);
const rows = [];
gltf.scene.updateWorldMatrix(true, true);
gltf.scene.traverse((o) => {
  if (!o.isMesh) return;
  const box = new THREE.Box3().setFromObject(o);
  const s = box.getSize(new THREE.Vector3());
  const c = box.getCenter(new THREE.Vector3());
  rows.push({ name: o.name, group: (o.userData && o.userData.lb_group) || '?',
    layer: (o.userData && o.userData.lb_layer) ?? -1,
    sx: s.x, sy: s.y, sz: s.z, cx: c.x, cy: c.y, cz: c.z,
    verts: o.geometry.attributes.position.count });
});

const L = [];
const p = (s) => L.push(String(s));

p('=== 疑似"平板/屏幕"：面积大且很薄，或体积很大 ===');
p('判据：最大两边之积 > 8 m² 且最薄边 < 0.6 m；或体积 > 20 m³');
p('');
p('物件名                    拆解组          波次        X        Y        Z    中心(x, y, z)                顶点');
p('-'.repeat(118));
const flat = rows.filter((r) => {
  const d = [r.sx, r.sy, r.sz].sort((a, b) => b - a);
  return (d[0] * d[1] > 8 && d[2] < 0.6) || (r.sx * r.sy * r.sz > 20);
}).sort((a, b) => (b.sx * b.sy * b.sz) - (a.sx * a.sy * a.sz));
for (const r of flat) {
  p(`${r.name.slice(0, 24).padEnd(25)}${r.group.padEnd(16)}L${String(r.layer).padStart(2)} ` +
    `${f(r.sx)} ${f(r.sy)} ${f(r.sz)}   (${r.cx.toFixed(2)}, ${r.cy.toFixed(2)}, ${r.cz.toFixed(2)})`.padEnd(74) +
    ` ${String(r.verts).padStart(5)}`);
}
p(`（共 ${flat.length} 个）`);

p('');
p('=== 尺寸最长边 > 5 m 的物件 ===');
const big = rows.filter((r) => Math.max(r.sx, r.sy, r.sz) > 5)
  .sort((a, b) => Math.max(b.sx, b.sy, b.sz) - Math.max(a.sx, a.sy, a.sz));
for (const r of big) {
  p(`  ${r.name.slice(0, 24).padEnd(25)}${r.group.padEnd(16)}L${String(r.layer).padStart(2)} ` +
    `尺寸(${r.sx.toFixed(2)}, ${r.sy.toFixed(2)}, ${r.sz.toFixed(2)})  中心(${r.cx.toFixed(2)}, ${r.cy.toFixed(2)}, ${r.cz.toFixed(2)})`);
}
p(`  （共 ${big.length} 个）`);

p('');
p('=== ANNO_* / ENV_* 全部物件 ===');
for (const r of rows.filter((r) => /^(ANNO_|ENV_)/.test(r.group))) {
  p(`  ${r.name.slice(0, 24).padEnd(25)}${r.group.padEnd(16)}` +
    `尺寸(${r.sx.toFixed(2)}, ${r.sy.toFixed(2)}, ${r.sz.toFixed(2)})  中心(${r.cx.toFixed(2)}, ${r.cy.toFixed(2)}, ${r.cz.toFixed(2)})  顶点${r.verts}`);
}

writeFileSync(OUT, L.join('\n'), 'utf-8');
console.log('WROTE ' + OUT + '  ' + L.length + ' lines');
