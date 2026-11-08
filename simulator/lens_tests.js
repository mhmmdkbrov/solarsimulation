// Lens optics: sanity checks + the requested diopter tests (+3, −3, +10, −10 D) + best-case search.
// Usage (project folder): node simulator/lens_tests.js [out.json]
const fs = require("fs");
const path = require("path");
const L = require("./lensoptics.js");
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "data.json"), "utf8"));
let ok = true;
const check = (name, cond, info) => { ok = ok && cond; console.log(`${cond ? "OK  " : "FAIL"} ${name} ${info || ""}`); };

// 1) geometry: plain module (no lens, tau=1, P=0, h≈0) must reproduce scenario A exactly-ish
const base = L.annual(D, { mode: "array", P: 0, h: 0.001, tau: 1 });
check("A annual = notebook 355.40 kWh/m²", Math.abs(base.A - 355.4006) < 0.01, base.A.toFixed(3));
check("flat sheet tau=1, h≈0 -> lens ≈ A (within IAM differences)", Math.abs(base.L / base.A - 1) < 0.03, (base.L / base.A).toFixed(4));
check("active area fraction ≈ 0.92", Math.abs(L.F_ACT - 0.92) < 0.002, L.F_ACT.toFixed(4));
// 2) energy conservation of the lens array capture (never > 1)
let maxCap = 0; for (const P of [-10, -3, 3, 10, 30]) for (const h of [1, 5, 30, 100, 333]) for (const t of [0, 0.3, 1]) maxCap = Math.max(maxCap, L.lensletCapture(P, h, t, t).cap);
check("lenslet capture ≤ 1", maxCap <= 1 + 1e-12, maxCap.toFixed(4));
// 3) big lens: total light on cells ≤ incoming (sum over cells × cell area ≤ module area)
const cells = new Float64Array(144); let maxSum = 0;
for (const P of [-10, -3, 3, 10]) for (const h of [3, 100, 333, 1000]) { L.bigLensCells(P, h, 0.2, 0.3, cells); const s = cells.reduce((a, v) => a + v, 0) * L.CX * L.CY / (L.LX * L.LY); maxSum = Math.max(maxSum, s); }
check("big lens: light on cells ≤ light on lens", maxSum <= 1 + 1e-9, maxSum.toFixed(4));
// 4) cosine of incidence from the simple solar position agrees with the notebook plane (f_beam ≈ DNI·cos·IAM)
let n = 0, err = 0;
for (let i = 0; i < D.dni.length; i++) if (D.dni[i] > 300 && D.f_beam[i] > 100) { const s = L.sunInPanel(D.doy[i], D.hour[i]); const est = D.dni[i] * Math.max(0, s.cos) * L.iamGlass(s.th); err += Math.abs(est - D.f_beam[i]) / D.f_beam[i]; n++; }
check("sun geometry vs. pvlib (mean rel. error of beam on plane < 2%)", err / n < 0.02, (100 * err / n).toFixed(2) + "%");

// requested tests
const TAU = 0.92;
const hGrid = [2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 250, 333, 400, 500, 750, 1000];
const tests = [];
for (const P of [3, -3, 10, -10]) {
  const f = 1000 / P;
  for (const mode of ["array", "big"]) {
    const glued = L.annual(D, { mode, P, h: 3, tau: TAU });
    const hFocus = P > 0 ? f : 100;
    const atF = L.annual(D, { mode, P, h: hFocus, tau: TAU });
    let best = { h: null, L: -1 };
    for (const h of hGrid) { const r = L.annual(D, { mode, P, h, tau: TAU }, 3); if (r.L > best.L) best = { h, L: r.L }; }
    const bestExact = L.annual(D, { mode, P, h: best.h, tau: TAU });
    tests.push({ P, mode, glued_pct: 100 * (glued.L / glued.A - 1), hFocus, atF_pct: 100 * (atF.L / atF.A - 1), best_h: best.h, best_pct: 100 * (bestExact.L / bestExact.A - 1) });
  }
}
console.table(tests.map(t => ({ P: t.P, mode: t.mode, "h=3mm %": t.glued_pct.toFixed(1), [`h=f/100mm %`]: t.atF_pct.toFixed(1), "best h mm": t.best_h, "best %": t.best_pct.toFixed(1) })));

// global best search for the lens array (P −40..+40 D, h grid), with tau 0.92 and tau 1.0
const search = tau => {
  let best = { L: -1 };
  // physical limits: cells lie under ~1.6 mm glass + encapsulant -> h ≥ 2.5 mm;
  // a lenslet over a 73 mm cell needs f ≥ its width (f-number ≥ 1) -> P ≤ 13.5 D
  const hs = [2.5, 3, 4, 5, 6, 8, 10, 15, 20, 30, 50, 100, 200, 333, 500];
  for (let P = -40; P <= 13.5; P += 0.5) for (const h of hs) { const r = L.annual(D, { mode: "array", P, h, tau }, 4); if (r.L > best.L) best = { P, h, L: r.L, A: r.A }; }
  const ex = L.annual(D, { mode: "array", P: best.P, h: best.h, tau });
  return { tau, P: best.P, h: best.h, pct: 100 * (ex.L / ex.A - 1), L: ex.L, A: ex.A };
};
const best92 = search(0.92), best96 = search(0.96), best100 = search(1.0);
console.log("best lens array:", [best92, best96, best100].map(b => `tau ${b.tau}: P=${b.P} D, h=${b.h} mm -> ${b.pct.toFixed(1)}%`).join(" | "));
if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify({ tau: TAU, tests, best: [best92, best96, best100] }));
console.log(ok ? "ALL CHECKS OK" : "SOME CHECKS FAILED");
process.exit(ok ? 0 : 1);
