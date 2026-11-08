const fs = require("fs");
const path = require("path");
const M = require("./model.js");
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "data.json"), "utf8"));
const A = D.meta.area_m2;
let ok = true;
const check = (name, got, exp, tolRel) => {
  const rel = Math.abs(got / exp - 1);
  const pass = rel <= tolRel;
  ok = ok && pass;
  console.log(`${pass ? "OK  " : "FAIL"} ${name}: js=${got.toFixed(3)} notebook=${exp.toFixed(3)} rel=${(rel * 100).toFixed(4)}%`);
};
const s0 = M.summarize(D, M.simulate(D, M.PRESETS.base));
for (const s of M.SCEN) check(`base ${s} net kWh`, s0[s].net_kWh, D.reference_net_kWh[s], 5e-4);
// notebook combined pessimistic / optimistic ranges (annual_net_ranges_kWh_m2.csv)
const ranges = { pess: { B_fixed: 274.70851260521016, A_2axis: 423.6364190060414, C_2axis: 176.14000488181233 },
                 opt: { B_fixed: 353.6665493348579, A_2axis: 444.9115452754923, C_2axis: 452.1830409790663 } };
for (const k of ["pess", "opt"]) {
  const s = M.summarize(D, M.simulate(D, M.PRESETS[k]));
  for (const sc of Object.keys(ranges[k])) check(`${k} ${sc} kWh/m²`, s[sc].net_kWh_m2, ranges[k][sc], 5e-4);
}
// optics off, no heating, no aux -> B == A
const off = M.summarize(D, M.simulate(D, { ...M.PRESETS.base, optics: false, heat: 0 }));
check("B(optics off, heat 0) == A", off.B_fixed.net_kWh, off.A_fixed.net_kWh, 1e-12);
// break-even map value at base (τ=0.85, η=0.30) equals scenario C
const t0 = performance.now();
const taus = Array.from({ length: 41 }, (_, i) => +(0.6 + i * 0.01).toFixed(4));
const etas = Array.from({ length: 61 }, (_, i) => +(0.15 + i * 0.005).toFixed(4));
const Z = M.cpvGrid(D, M.PRESETS.base, taus, etas);
const zi = etas.indexOf(0.3) * taus.length + taus.indexOf(0.85);
console.log(`grid time ${(performance.now() - t0).toFixed(0)} ms`);
check("map(τ=0.85, η=0.30) == C", Z[zi], s0.C_2axis.net_kWh_m2, 1e-9);
// break-even η vs A_2axis at τ = 0.85 (notebook: 0.430)
const col = etas.map((e, ie) => Z[ie * taus.length + taus.indexOf(0.85)]);
const be = etas[col.findIndex(v => v >= s0.A_2axis.net_kWh_m2)];
console.log(`break-even η vs A_2axis at τ=0.85: ${be} (notebook 0.430)`);
ok = ok && Math.abs(be - 0.43) < 1e-9;
console.log(ok ? "ALL OK" : "SOME FAILED");
process.exit(ok ? 0 : 1);
