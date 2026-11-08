// Derive the data for the simple "lens vs. ordinary panel" explainer from the same model and Baku TMY data.
// Usage (project folder): node simulator/lens_cases.js simulator/lens_cases.json
const fs = require("fs");
const path = require("path");
const M = require("./model.js");
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "data.json"), "utf8"));

// Lens (retrofit B) quality levels. The panel itself (f_act) is the same in all levels.
const base = M.PRESETS.base;
const LEVELS = {
  weak:  { ...base, tau_b: 0.88, tau_d: 0.78, gap_beam: 0.0, gap_diff: 0.0, nonunif: 0.06, heat: 5.0 },
  base:  { ...base },
  good:  { ...base, tau_b: 0.96, tau_d: 0.90, gap_beam: 0.7, gap_diff: 0.3, nonunif: 0.0, heat: 0.0 },
  ideal: { ...base, tau_b: 1.0, tau_d: 1.0, gap_beam: 1.0, gap_diff: 1.0, nonunif: 0.0, heat: 0.0 },
};
// weather classes by diffuse fraction DHI/GHI (daytime hours, GHI > 10 W/m²)
const CLASSES = [
  { id: "clear", lo: 0, hi: 0.3 }, { id: "hazy", lo: 0.3, hi: 0.5 },
  { id: "partly", lo: 0.5, hi: 0.9 }, { id: "overcast", lo: 0.9, hi: 1.0001 },
];
const cls = i => { if (!(D.ghi[i] > 10)) return -1; const kd = D.dhi[i] / D.ghi[i]; return CLASSES.findIndex(c => kd >= c.lo && kd < c.hi); };

// representative hour per class: mean over Apr–Sep, 11–14 h Baku time
const keys = ["ghi", "dni", "dhi", "f_glob", "f_beam", "f_diff", "f_layer", "ta", "ws"];
const rep = CLASSES.map(() => ({ n: 0 }));
for (let i = 0; i < D.ghi.length; i++) {
  const k = cls(i);
  if (k < 0 || D.month[i] < 4 || D.month[i] > 9 || D.hour[i] < 11 || D.hour[i] > 14) continue;
  const r = rep[k]; r.n++;
  for (const key of keys) r[key] = (r[key] || 0) + D[key][i];
}
rep.forEach(r => keys.forEach(key => (r[key] = +(r[key] / r.n).toFixed(4))));

// annual results and per-class energy (whole year) per level
const annual = {}, perClass = {};
const hours = CLASSES.map(() => 0);
for (let i = 0; i < D.ghi.length; i++) { const k = cls(i); if (k >= 0) hours[k]++; }
for (const [name, p] of Object.entries(LEVELS)) {
  const r = M.simulate(D, p), s = M.summarize(D, r);
  annual[name] = { A: s.A_fixed.net_kWh_m2, B: s.B_fixed.net_kWh_m2 };
  const e = CLASSES.map(() => ({ A: 0, B: 0 }));
  for (let i = 0; i < D.ghi.length; i++) { const k = cls(i); if (k >= 0) { e[k].A += r.dc.A_fixed[i]; e[k].B += r.dc.B_fixed[i]; } }
  perClass[name] = e.map(v => ({ A_kWh_m2: v.A / 1000 / D.meta.area_m2, B_kWh_m2: v.B / 1000 / D.meta.area_m2 }));
}
const out = { meta: { ...D.meta, note: "Apr–Sep, 11–14 h Baku time means per weather class" }, classes: CLASSES, hours, rep, levels: LEVELS, annual, perClass };
fs.writeFileSync(process.argv[2], JSON.stringify(out));
console.log("rep hours per class:", rep.map(r => r.n), "| year daytime hours:", hours);
console.log("annual kWh/m²:", JSON.stringify(annual, (k, v) => (typeof v === "number" ? +v.toFixed(1) : v)));
console.log("rep:", JSON.stringify(rep.map(r => ({ n: r.n, dni: r.dni, dhi: r.dhi, f_beam: r.f_beam, f_diff: r.f_diff, ta: r.ta }))));
