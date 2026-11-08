// Freeze the results of the previous model (v1, commit ad549b0) as a regression baseline.
// Usage (project folder): node tests/make_baseline_v1.js tests/baseline_v1.json
const fs = require("fs");
const path = require("path");
const M = require("../legacy/v1/model_v1.js");
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "legacy", "v1", "data.json"), "utf8"));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "legacy", "v1", "lens_cases.json"), "utf8"));
const lensTests = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "legacy", "v1", "lens_tests.json"), "utf8"));
const claims = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "legacy", "v1", "claims_check.json"), "utf8"));
const A = D.meta.area_m2;
const s = M.summarize(D, M.simulate(D, M.PRESETS.base));
const out = { model_version: "v1 (commit ad549b0)", dataset: D.meta.source, area_m2: A, annual: {} };
for (const k of M.SCEN) out.annual[k] = { gross_kWh_m2: s[k].dc_kWh / A, aux_kWh_unit: s[k].aux_kWh, net_kWh_m2: s[k].net_kWh_m2, gross_kWh_unit: s[k].dc_kWh, net_kWh_unit: s[k].net_kWh };
// clear-weather sample (Apr–Sep, 11–14 h means) as used on index.html
const r = cases.rep[0], p = cases.levels.base, F = D.meta.module.active_area_fraction, { sapm_a: a, sapm_b: b, sapm_dT: dT } = D.meta.sapm;
const tc = r.f_glob * Math.exp(a + b * r.ws) + r.ta + r.f_glob / 1000 * dT;
const pA = 450 * (r.f_beam + r.f_diff) / 1000 * (1 + p.gamma_pdc * (tc - 25));
const ratio = (1 - F) / F;
const eB = r.f_beam * p.tau_b * r.f_layer * (1 + ratio * p.gap_beam) + r.f_diff * p.tau_d * (1 + ratio * p.gap_diff);
const pB = 450 * eB / 1000 * (1 + p.gamma_pdc * (tc + p.heat * r.f_glob / 1000 - 25)) * (1 - p.nonunif);
out.clear_sample_W = { A: pA, B: pB };
out.index_annual_by_level = cases.annual;
out.lens_lab_tests = lensTests;
out.claims_check = claims;
fs.writeFileSync(process.argv[2], JSON.stringify(out, null, 1));
console.log(JSON.stringify({ annual: out.annual, clear_sample_W: out.clear_sample_W }, (k, v) => (typeof v === "number" ? +v.toFixed(4) : v), 1));
