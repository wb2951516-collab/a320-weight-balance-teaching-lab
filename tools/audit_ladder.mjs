/**
 * 拆解阶梯自检
 * ============
 * 复算视图侧 buildExplodeLadder() 的数学，验证核心不变式：
 *   **第 k 层的落位底边 = 第 k−1 层的落位顶边 + GAP**
 * 即竖向层与层绝不相交 —— 这是"逐层拆解能看见每一层"的数学条件。
 *
 * 背景（踩过的坑）：上一版手调层距 0.55 m，而上壳体自身高 4.22 m，
 * 爆炸后上壳体 [1.85,6.07] 把座椅 [3.78,4.74] 整个包住 → 座椅升上去却看不见，
 * 表现就是"先炸出来的被后炸出的遮挡"。
 *
 * 用法: node tools/audit_ladder.mjs <glb> [gap] [lift0]
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { readFileSync, writeFileSync } from 'node:fs';

const GLB = process.argv[2];
const GAP = Number(process.argv[3] ?? 0.55);
const LIFT0 = Number(process.argv[4] ?? 0.60);
const OUT = 'C:/Users/96258/AppData/Local/Temp/ladder.txt';

// 与 web/index.html 的 STACK_ORDER 必须一致
const STACK_ORDER = [1, 2, 3, 4, 5, 6, 7, 12, 8, 9, 10, 11];
const NAME = { 1: '起落架', 2: '腹板', 3: '货舱+行李', 4: '货舱地板', 5: '客舱地板',
  6: '座椅', 7: '上壳体', 8: '机翼', 9: '燃油', 10: '发动机', 11: '尾翼',
  12: '舱门/舷窗/标识' };

const buf = readFileSync(GLB);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const gltf = await new Promise((r, j) => new GLTFLoader().parse(ab, '', r, j));

// 按 (layer) 汇总世界 AABB（复刻视图侧算法）
const ext = new Map();
gltf.scene.updateWorldMatrix(true, true);
gltf.scene.traverse((o) => {
  if (!o.isMesh) return;
  const L = o.userData && o.userData.lb_layer;
  if (!L) return;                       // 0 / undefined = 不参与拆解
  if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
  const box = new THREE.Box3().copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld);
  let e = ext.get(L);
  if (!e) { e = { lo: Infinity, hi: -Infinity }; ext.set(L, e); }
  if (box.min.y < e.lo) e.lo = box.min.y;
  if (box.max.y > e.hi) e.hi = box.max.y;
});

const L = [];
const p = (s) => L.push(String(s));
p(`拆解阶梯自检   间隙 GAP=${GAP} m   起始底边 LIFT0=${LIFT0} m`);
p('='.repeat(112));
p('层  名称                原始Y底   原始Y顶   自身高   位移     落位底    落位顶   与前层间隙  向上?');
p('-'.repeat(112));

let cursor = LIFT0;
let prevHi = null;
let bad = [];
for (const lay of STACK_ORDER) {
  const e = ext.get(lay);
  if (!e) { p(`L${lay}  —— 数据中不存在，跳过`); continue; }
  const h = e.hi - e.lo;
  const amp = cursor - e.lo;
  const finLo = cursor, finHi = cursor + h;
  const gapToPrev = prevHi === null ? null : (finLo - prevHi);
  const up = amp > 0;
  if (!up) bad.push(`L${lay} 位移为负(${amp.toFixed(2)})，不是向上`);
  if (gapToPrev !== null && gapToPrev < GAP - 1e-6) bad.push(`L${lay} 与前层间隙 ${gapToPrev.toFixed(2)} < GAP`);
  p(`L${String(lay).padStart(2)} ${NAME[lay].padEnd(18)} ${e.lo.toFixed(2).padStart(8)} ${e.hi.toFixed(2).padStart(8)} ` +
    `${h.toFixed(2).padStart(7)} ${amp.toFixed(2).padStart(8)} ${finLo.toFixed(2).padStart(9)} ${finHi.toFixed(2).padStart(9)} ` +
    `${(gapToPrev === null ? '     -' : gapToPrev.toFixed(2).padStart(10))}      ${up ? '✔' : '★'}`);
  prevHi = finHi;
  cursor += h + GAP;
}
p('='.repeat(112));
p(`爆炸后总高：${(cursor - GAP).toFixed(2)} m（最上层顶边）`);
p('');
p('不变式检查（竖向层与层不得相交、且位移一律为正）：');
if (bad.length === 0) p('   PASS —— 所有层间隙 ≥ GAP，且位移全部为正');
else bad.forEach((b) => p('   ★ FAIL ' + b));

// 与组装态对比：组装态各层是互相嵌套的，所以"各层自身高之和"远大于机身高度
const sumH = [...ext.values()].reduce((a, e) => a + (e.hi - e.lo), 0);
const allLo = Math.min(...[...ext.values()].map((e) => e.lo));
const allHi = Math.max(...[...ext.values()].map((e) => e.hi));
p('');
p(`参考：组装态竖向跨度 ${(allHi - allLo).toFixed(2)} m；各层自身高之和 ${sumH.toFixed(2)} m`);
p(`      → 后者远大于前者，说明各层在组装态本就是**互相嵌套**的；`);
p(`        要让每层都露出来，拉开的总量必须接近"各层自身高之和 + 间隙"，这就是塔高的来源。`);

writeFileSync(OUT, L.join('\n'), 'utf-8');
console.log(L.join('\n'));
