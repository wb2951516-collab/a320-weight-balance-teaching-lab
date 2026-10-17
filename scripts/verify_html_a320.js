/**
 * 与 a320_data.py / 当前 HTML 一致的验收脚本
 */
const MAC = 4.1935;
const LEMAC = 16.92;
const OEW = 42500;
const OEW_ST = LEMAC + 0.25 * MAC;
const PAX_W = 84, BAG_W = 12;
const SAFE = [18, 36];
const Z = { FWD: 11.2, MID: 18.5, AFT: 25.8 };
const C = { FWD: 12.8, AFT: 24.6, BULK: 28.8 };
const F = { WING_L: 18.2, WING_R: 18.2, CTR: 18.5 };

function calc(pax, cargo, fuel) {
  const items = [{ w: OEW, a: OEW_ST, y: 0 }];
  for (const z of Object.keys(pax)) {
    items.push({ w: pax[z] * PAX_W, a: Z[z], y: 0 });
    items.push({ w: pax[z] * BAG_W, a: z === "FWD" ? C.FWD : C.AFT, y: 0 });
  }
  for (const c of Object.keys(cargo)) items.push({ w: cargo[c], a: C[c], y: 0 });
  for (const f of Object.keys(fuel))
    items.push({ w: fuel[f], a: F[f], y: f.includes("L") ? -5.5 : f.includes("R") ? 5.5 : 0 });
  const W = items.reduce((s, i) => s + i.w, 0);
  const M = items.reduce((s, i) => s + i.w * i.a, 0);
  const My = items.reduce((s, i) => s + i.w * i.y, 0);
  const cg = W ? M / W : 0;
  const mac = ((cg - LEMAC) / MAC) * 100;
  const cy = W ? My / W : 0;
  return { W, cg, mac, cy, ok: mac >= SAFE[0] && mac <= SAFE[1] };
}

const cases = {
  empty: [{}, {}, {}],
  ok: [{ FWD: 40, MID: 60, AFT: 35 }, { FWD: 1800, AFT: 2200, BULK: 400 },
       { WING_L: 4200, WING_R: 4300, CTR: 3500 }],
  fwd: [{ FWD: 60, MID: 0, AFT: 0 }, { FWD: 3175, AFT: 0, BULK: 0 },
        { WING_L: 7500, WING_R: 7500, CTR: 0 }],
  aft: [{ FWD: 0, MID: 0, AFT: 50 }, { FWD: 0, AFT: 4480, BULK: 1495 },
        { WING_L: 0, WING_R: 0, CTR: 6145 }],
};

console.log("公式: M=W·Arm  CG=ΣM/ΣW  %MAC=(CG-LEMAC)/MAC·100");
console.log("包线", SAFE.join("-"), "MAC", MAC, "LEMAC", LEMAC);
for (const [k, args] of Object.entries(cases)) {
  const r = calc(...args);
  console.log(k, "TOW", r.W.toFixed(0), "CG", r.cg.toFixed(3), "%MAC", r.mac.toFixed(2), r.ok ? "IN" : "OUT", "y", r.cy.toFixed(3));
}
const fwd = calc(...cases.fwd), aft = calc(...cases.aft), ok = calc(...cases.ok);
console.log("PASS fwd OUT?", !fwd.ok && fwd.mac < SAFE[0]);
console.log("PASS aft OUT?", !aft.ok && aft.mac > SAFE[1]);
console.log("PASS ok IN?", ok.ok);
