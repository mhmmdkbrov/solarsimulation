// Python ↔ browser parity for the scenario model. Usage: node tests/parity_model.js docs/data/<dataset>.json [...]
// Tolerance: 0.05 % on annual energies (exported arrays are rounded to 3 decimals in W/m²).
const fs = require("fs");
const M = require("../simulator/model.js");
const TOL = 5e-4;
let ok = true;
for (const f of process.argv.slice(2)) {
  const D = JSON.parse(fs.readFileSync(f, "utf8"));
  const s = M.summarize(D, M.simulate(D, M.PRESETS.base));
  for (const k of M.SCEN) {
    for (const col of ["gross_kWh_unit", "drive_kWh_unit", "controller_kWh_unit", "cooling_kWh_unit", "net_kWh_unit"]) {
      const py = D.annual[k][col], js = s[k][col];
      const rel = Math.abs(js - py) / Math.max(Math.abs(py), 1e-6);
      const pass = rel <= TOL || Math.abs(js - py) < 1e-9;
      if (!pass) ok = false;
      if (!pass || col === "net_kWh_unit") console.log(`${pass ? "OK  " : "FAIL"} ${D.dataset.id} ${k} ${col}: js ${js.toFixed(4)} py ${py.toFixed(4)} rel ${(rel * 100).toFixed(4)}%`);
    }
    const mon = s[k].monthly_net_kWh_m2.reduce((a, b) => a + b, 0);
    if (Math.abs(mon - s[k].net_kWh_m2_ap) > 1e-9) { ok = false; console.log(`FAIL months ≠ annual ${k}`); }
  }
  const sky = M.bySky(D, M.simulate(D, M.PRESETS.base));
  const tot = Object.values(sky).reduce((a, r) => a + r.A_fixed, 0);
  if (Math.abs(tot - s.A_fixed.gross_kWh_unit) > 1e-6) { ok = false; console.log("FAIL sky classes + remainder ≠ annual"); }
}
console.log(ok ? "PARITY OK" : "PARITY FAILED");
process.exit(ok ? 0 : 1);
