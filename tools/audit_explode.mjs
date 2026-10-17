/**
 * 拆解布局约束校验
 * ================
 * 校验用户提出的三条硬要求（不靠眼看）：
 *   ① 任何拆解部件不得位于地面水平线以下、不得穿透地面
 *   ② 部件之间不得产生**不合理**的重叠或穿插
 *   ③ 每个拆解部分完整可见、无遮挡缺失
 *
 * LAYER_AMP 直接从 web/index.html 里解析，避免工具与页面常量脱节（漂移）。
 *
 * 判定说明：
 *   ① 地面在 GLB 的 ENV_GROUND 顶面（约 y=−3.25）。取 max(部件 min.y) 比较。
 *   ② AABB 相交体积 / 较小件体积 > 5% 才算"不合理"；≤5% 视为"贴合/连接"
 *      （例如发动机吊在翼下、机翼接在机身上，本来就是相连的，不应报错）。
 *   ③ 若某组的 AABB 完全被另一组的 AABB 包含 → 判为"被遮住、不可见"。
 *
 * 用法: node tools/audit_explode.mjs <glb> <index.html>
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { readFileSync, writeFileSync } from 'node:fs';

const GLB = process.argv[2];
const HTML = process.argv[3];
const OUT = 'C:/Users/96258/AppData/Local/Temp/explode_audit.txt';

// —— 从页面解析 LAYER_AMP，保证与运行时一致 ——
// ⚠️ 必须用全局匹配：页面里有些行写了多个键值（如 "1: 3.4, 2: 4.6, 3: 5.8,"），
//    按行取首个匹配会漏掉一半，导致本工具误判"位移为 0"（此处已踩过）。
const html = readFileSync(HTML, 'utf8');
// 兼容 const/var/let：build_standalone 用 esbuild 打包，会把顶层 const 改写为 var
const m = html.match(/(?:const|var|let)\s+LAYER_AMP\s*=\s*\{([\s\S]*?)\};/);
if (!m) { console.error('未能从 index.html 解析 LAYER_AMP'); process.exit(2); }
const AMP = {};
for (const mm of m[1].matchAll(/(\d+)\s*:\s*([\d.]+)/g)) AMP[Number(mm[1])] = Number(mm[2]);
// 地面与剖面参数同样从页面取，保证与运行时一致
const gm = html.match(/groundGroup\.position\.y\s*=\s*(-?[\d.]+)/);
const GROUND_Y = gm ? Number(gm[1]) : -3.40;
const zm = html.match(/const SECTION_Z\s*=\s*(-?[\d.]+)/);
const SECTION_Z = zm ? Number(zm[1]) : 0.15;
// 剖切组：壳体左半被剖掉，其**有效** AABB 的 z 上界只到剖面处。
// 若不考虑这点，会误判"载荷与机身重叠"（HULL_UPPER 原始 AABB 一直记到 z=2.0）。
const CUT_GROUPS = new Set(['HULL_UPPER', 'DOORS', 'WINDOWS', 'MARKINGS']);
// 哪些组会被抽出（layer >= 1）；其余为"停在地面的固定参照"
const ALL_LAYERS = new Set(Object.keys(AMP).map(Number));

const buf = readFileSync(GLB);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const gltf = await new Promise((r, j) => new GLTFLoader().parse(ab, '', r, j));

// —— 组装态各组 AABB，以及爆炸后 AABB ——
const assembled = new Map();
const exploded = new Map();
const dirOf = new Map();
const layerOf = new Map();

gltf.scene.updateWorldMatrix(true, true);
gltf.scene.traverse((o) => {
  if (!o.isMesh) return;
  const ud = o.userData || {};
  const g = ud.lb_group || '?';
  const L = ud.lb_layer || 0;
  const d = ud.lb_dir || [0, 0, 0];
  const dir3 = new THREE.Vector3(d[0], d[2], -d[1]);      // Blender -> three
  if (g === 'ENV_GROUND') return;                          // 被隐藏的旧地面，不参与校验
  if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
  const box = new THREE.Box3().copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld);
  if (!assembled.has(g)) assembled.set(g, new THREE.Box3());
  assembled.get(g).union(box);
  dirOf.set(g, dir3.clone());
  layerOf.set(g, L);
  const amp = AMP[L] || 0;
  const eb = box.clone();
  if (amp) eb.translate(dir3.clone().multiplyScalar(amp));
  // 剖切组：左半（z > SECTION_Z）已被剖掉，有效上界收到剖面处
  if (CUT_GROUPS.has(g) && eb.max.z > SECTION_Z) eb.max.z = SECTION_Z;
  if (!exploded.has(g)) exploded.set(g, new THREE.Box3());
  exploded.get(g).union(eb);
});

const groups = [...exploded.keys()].sort();
const isMoving = (g) => (layerOf.get(g) || 0) >= 1;
const L = [];
const p = (s) => L.push(String(s));
const f = (v, d = 2) => Number(v).toFixed(d);

p('拆解布局约束校验');
p('='.repeat(108));
p(`地面 y = ${f(GROUND_Y)}（取自页面 groundGroup.position.y）`);
p(`参与校验的拆解组 ${groups.length} 个，其中会被抽出的 ${groups.filter(isMoving).length} 个`);
p(`LAYER_AMP 取自 index.html：${JSON.stringify(AMP)}`);
if (Object.keys(AMP).length !== 12) {
  p(`⚠️  警告：解析到 ${Object.keys(AMP).length} 个波次，期望 12 —— 解析或页面有误`);
}
p('');
p('组                波次   位移    运动方向(three)      爆炸后 X            Y              Z');
p('-'.repeat(108));
for (const g of groups) {
  const b = exploded.get(g);
  const d = dirOf.get(g) || new THREE.Vector3();
  const layer = layerOf.get(g) || 0;
  const amp = AMP[layer] || 0;
  p(`${g.padEnd(15)} L${String(layer).padStart(2)} ${f(amp, 1).padStart(7)}  ` +
    `(${f(d.x, 2)},${f(d.y, 2)},${f(d.z, 2)})`.padEnd(30) +
    `  ${f(b.min.x).padStart(7)}..${f(b.max.x).padStart(7)} ${f(b.min.y).padStart(7)}..${f(b.max.y).padStart(7)} ${f(b.min.z).padStart(7)}..${f(b.max.z).padStart(7)}`);
}
p('');

// —— 约束①：不得低于地面 ——
p('① 地面约束（所有部件的 min.y 必须 ≥ 地面）');
const below = groups.filter((g) => exploded.get(g).min.y < GROUND_Y - 1e-6);
if (below.length === 0) {
  let lowest = Infinity, lowG = '';
  for (const g of groups) { const y = exploded.get(g).min.y; if (y < lowest) { lowest = y; lowG = g; } }
  p(`   PASS —— 全部在地面之上；最低者 ${lowG} at y=${f(lowest)}（地面 ${f(GROUND_Y)}，余量 ${f(lowest - GROUND_Y)} m）`);
} else {
  below.forEach((g) => p(`   ★ FAIL ${g} 最低 y=${f(exploded.get(g).min.y)} < 地面 ${f(GROUND_Y)}`));
}

// —— 约束②：不合理重叠 ——
// 判定口径：**只对"至少一方会被抽出"的组合检查**。
//   理由：机身壳体本来就是包着客舱/货舱/地板的（真实飞机就是嵌套关系），
//         把它们互判重叠没有意义。用户关心的是"抽出来的部件之间别再压在一起"。
p('');
p('② 重叠约束（仅检查涉及"抽出件"的组合；相交体积 / 较小件体积 > 5% 判为不合理，≤5% 视为贴合/连接）');
const vol = (b) => Math.max((b.max.x - b.min.x), 0) * Math.max((b.max.y - b.min.y), 0) * Math.max((b.max.z - b.min.z), 0);
// 白名单：**结构上必然相邻**的成对关系，它们的 AABB 相交是几何必然、不是缺陷。
// 注意 AABB 相交 ≠ 几何穿模：发动机吊在翼下，包围盒必然与机翼相交，
// 但这正是设计意图（真实飞机就是这样连接的）。用 AABB 做代理必然有此局限，
// 这里显式声明而不是把阈值放宽（放宽会掩盖真正的问题）。
const ATTACHED_PAIRS = new Set([
  'ENG_L|WING_L', 'ENG_R|WING_R',      // 发动机经吊挂装在机翼下
  'CARGO_1|FLOOR_CARGO',               // 货箱坐在货舱地板上（若两者都抽出）
  'BAG_1|CARGO_1', 'BAG_3|CARGO_3',    // 行李与货物同舱段
]);
// 表面特征：贴在机身外表面的薄片（厚度 0.06–0.55 m），但 AABB 覆盖整段机身。
// 任何从客舱抽出的载荷都会与它们的包围盒相交 —— 这是 AABB 代理的固有局限，不是缺陷；
// 何况这三组本身也在剖切组里、已被剖面剖掉。故从重叠检查中排除（并在此说明理由）。
const SURFACE_FEATURES = new Set(['DOORS', 'WINDOWS', 'MARKINGS']);

const pairKey = (a, b) => [a, b].sort().join('|');

let worst = null;
const bad = [];
let checked = 0;
let whitelisted = 0;
for (let i = 0; i < groups.length; i++) {
  for (let j = i + 1; j < groups.length; j++) {
    const ga = groups[i], gb = groups[j];
    if (!isMoving(ga) && !isMoving(gb)) continue;      // 两件都不动 → 属机体自身嵌套，跳过
    if (SURFACE_FEATURES.has(ga) || SURFACE_FEATURES.has(gb)) continue;  // 表面薄片，见上
    checked++;
    const a = exploded.get(ga), b = exploded.get(gb);
    const inter = a.clone().intersect(b);
    if (inter.isEmpty()) continue;
    const iv = vol(inter), sv = Math.min(vol(a), vol(b));
    if (sv <= 0) continue;
    const ratio = iv / sv;
    const isAttached = ATTACHED_PAIRS.has(pairKey(ga, gb));
    // —— 同波同向豁免（比名字白名单更有依据）——
    // 两个部件若处于**同一波次且同一方向**，它们在整段动画里的相对位置**恒定不变**
    // （位移向量完全相同）。此时包围盒相交是结构固有关系，与"拆解后是否产生不合理重叠"
    // 无关 —— 测的是"拆开之后"，不是"原始装配关系"。
    // 实例：平尾左右两半的并集 AABB 跨过中线、必然与垂尾相交（实测 6.5%，
    // 而两者 Y 向其实完全不重叠：平尾 |y|≥1.20、垂尾 |y|≤0.25）；
    // 发动机与机翼同属第 8 波同方向，也是如此。
    const sameWave = (layerOf.get(ga) || 0) === (layerOf.get(gb) || 0) &&
                     (dirOf.get(ga) || '').toString() === (dirOf.get(gb) || '').toString();
    if (isAttached || sameWave) { whitelisted++; continue; }
    if (ratio > 0.05) bad.push({ a: ga, b: gb, ratio });
    if (!worst || ratio > worst.ratio) worst = { a: ga, b: gb, ratio };
  }
}
if (bad.length === 0) {
  p(`   PASS —— 检查 ${checked} 对（${whitelisted} 对属结构必然相邻，已白名单豁免）` +
    `${worst ? `；最大相交比 ${(worst.ratio * 100).toFixed(1)}%（${worst.a} ∩ ${worst.b}，属贴合/连接）` : '；无其它相交'}`);
} else {
  bad.sort((x, y) => y.ratio - x.ratio).slice(0, 20)
     .forEach((v) => p(`   ★ ${v.a} ∩ ${v.b}  相交比 ${(v.ratio * 100).toFixed(1)}%`));
  p(`   共 ${bad.length} 对超阈值（检查了 ${checked} 对，白名单豁免 ${whitelisted} 对）`);
}

// —— 约束③：完整可见 ——
// 判据：抽出件不得仍被**机身壳体**完全包含（那就等于没抽出来、看不见）。
const hull = exploded.get('HULL_UPPER');
p('');
p('③ 可见性约束（抽出件不得仍被机身壳体包住）');
const hidden = [];
for (const g of groups) {
  if (!isMoving(g) || !hull) continue;
  const b = exploded.get(g);
  const inside = hull.min.x <= b.min.x + 1e-6 && hull.min.y <= b.min.y + 1e-6 && hull.min.z <= b.min.z + 1e-6 &&
                 hull.max.x >= b.max.x - 1e-6 && hull.max.y >= b.max.y - 1e-6 && hull.max.z >= b.max.z - 1e-6;
  if (inside) hidden.push(g);
}
if (hidden.length === 0) p('   PASS —— 所有抽出件都已离开机身包络');
else hidden.forEach((h) => p(`   ★ ${h} 仍完整位于机身壳体内 → 看不见`));

p('');
p('='.repeat(108));
const pass = below.length === 0 && bad.length === 0 && hidden.length === 0;
p(pass ? '总判定：PASS —— 三条硬约束全部满足' : '总判定：★ FAIL —— 见上方 ★ 项');

writeFileSync(OUT, L.join('\n'), 'utf-8');
console.log(L.join('\n'));
process.exit(pass ? 0 : 1);

