/**
 * 配载平衡核心算法校验
 * 公式：
 *   M = W * Arm
 *   CGx = Σ(W*Arm) / ΣW
 *   %MAC = (CGx - LEMAC) / MAC * 100
 *   CGy = Σ(W*y) / ΣW
 */
const MAC = 4.195;
const LEMAC = 13.0;
const OEW = 42500;
const OEW_ST = LEMAC + 0.25 * MAC; // 14.04875
const PAX_W = 84;
const BAG_W = 12;
const MAX_TOW = 78000;
const SAFE = [20, 34];

// 当前 HTML 站位（调参前）
const OLD = {
  Z: { FWD: 13.15, MID: 14.5, AFT: 16.1 },
  C: { FWD: 12.55, AFT: 16.55, BULK: 17.35 },
  F: { WING_L: 14.0, WING_R: 14.0, CTR: 14.8 },
};

// 修正后教学站位（加大前后跨度，保证极端预设能出包线）
const NEW = {
  Z: { FWD: 12.4, MID: 14.6, AFT: 17.2 },
  C: { FWD: 10.8, AFT: 18.2, BULK: 19.0 },
  F: { WING_L: 13.6, WING_R: 13.6, CTR: 15.6 },
};

const PRESETS = {
  ok: {
    pax: { FWD: 40, MID: 60, AFT: 35 },
    cargo: { FWD: 1800, AFT: 2200, BULK: 400 },
    fuel: { WING_L: 4200, WING_R: 4300, CTR: 3500 },
  },
  fwd: {
    pax: { FWD: 60, MID: 0, AFT: 0 },
    cargo: { FWD: 3500, AFT: 0, BULK: 0 },
    fuel: { WING_L: 9000, WING_R: 9000, CTR: 0 },
  },
  aft: {
    pax: { FWD: 0, MID: 0, AFT: 50 },
    cargo: { FWD: 0, AFT: 4500, BULK: 1500 },
    fuel: { WING_L: 0, WING_R: 0, CTR: 8000 },
  },
  empty: {
    pax: { FWD: 0, MID: 0, AFT: 0 },
    cargo: { FWD: 0, AFT: 0, BULK: 0 },
    fuel: { WING_L: 0, WING_R: 0, CTR: 0 },
  },
};

function calc(st, p) {
  const items = [{ w: OEW, arm: OEW_ST, y: 0 }];
  for (const z of Object.keys(p.pax)) {
    const n = p.pax[z];
    items.push({ w: n * PAX_W, arm: st.Z[z], y: 0 });
    const bagArm = z === "FWD" ? st.C.FWD : st.C.AFT;
    items.push({ w: n * BAG_W, arm: bagArm, y: 0 });
  }
  for (const c of Object.keys(p.cargo)) {
    items.push({ w: p.cargo[c], arm: st.C[c], y: 0 });
  }
  for (const f of Object.keys(p.fuel)) {
    items.push({ w: p.fuel[f], arm: st.F[f], y: f.includes("L") ? -5.5 : f.includes("R") ? 5.5 : 0 });
  }
  const W = items.reduce((s, i) => s + i.w, 0);
  const M = items.reduce((s, i) => s + i.w * i.arm, 0);
  const My = items.reduce((s, i) => s + i.w * i.y, 0);
  const cg = W ? M / W : 0;
  const cy = W ? My / W : 0;
  const mac = ((cg - LEMAC) / MAC) * 100;
  return {
    W,
    M,
    cg,
    cy,
    mac,
    okMac: mac >= SAFE[0] && mac <= SAFE[1],
    okTow: W <= MAX_TOW,
  };
}

// 手工公式抽查：OEW only
function manualOew() {
  const w = OEW;
  const m = OEW * OEW_ST;
  const cg = m / w;
  const mac = ((cg - LEMAC) / MAC) * 100;
  return { w, m, cg, mac };
}

console.log("=== 公式抽查：OEW only ===");
console.log(manualOew());
console.log("期望 mac≈25.0, cg≈", OEW_ST.toFixed(4));

console.log("\n=== 旧站位 OLD ===");
for (const [k, p] of Object.entries(PRESETS)) {
  const r = calc(OLD, p);
  console.log(
    k,
    "TOW",
    r.W.toFixed(0),
    "CG",
    r.cg.toFixed(3),
    "%MAC",
    r.mac.toFixed(2),
    r.okMac ? "IN" : "OUT",
    "y",
    r.cy.toFixed(3)
  );
}

console.log("\n=== 新站位 NEW ===");
for (const [k, p] of Object.entries(PRESETS)) {
  const r = calc(NEW, p);
  console.log(
    k,
    "TOW",
    r.W.toFixed(0),
    "CG",
    r.cg.toFixed(3),
    "%MAC",
    r.mac.toFixed(2),
    r.okMac ? "IN" : "OUT",
    "y",
    r.cy.toFixed(3)
  );
}

// 检查：fwd 应 OUT 前限，aft 应 OUT 后限，ok 应 IN
const okR = calc(NEW, PRESETS.ok);
const fwdR = calc(NEW, PRESETS.fwd);
const aftR = calc(NEW, PRESETS.aft);
console.log("\n=== 验收 ===");
console.log("ok IN?", okR.okMac, okR.mac.toFixed(2));
console.log("fwd OUT front?", !fwdR.okMac && fwdR.mac < SAFE[0], fwdR.mac.toFixed(2));
console.log("aft OUT aft?", !aftR.okMac && aftR.mac > SAFE[1], aftR.mac.toFixed(2));
