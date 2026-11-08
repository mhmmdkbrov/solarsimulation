// Check of the numerical claims in the shared presentation draft ("lens-boosted solar panel", C = 5x example)
// against physics and the project's model (same Baku PVGIS TMY data, same module, same temperature model).
// Usage (project folder): node simulator/claims_check.js simulator/claims_check.json
const fs = require("fs");
const path = require("path");
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "data.json"), "utf8"));

const PDC0 = D.meta.module.pdc0_W, GAMMA = D.meta.module.gamma_pdc_per_C, A_MOD = D.meta.area_m2;  // 450 W, -0.0030/°C, 1.998 m²
const { sapm_a: SA, sapm_b: SB, sapm_dT: SDT } = D.meta.sapm;
const ETA_STC = PDC0 / (1000 * A_MOD);       // 0.2252 module efficiency at STC
const T_MAX = 85;                            // °C, datasheet maximum operating temperature
const RS_K = 0.035;                          // assumption (same as lens lab): extra series-resistance loss per extra sun
const SI_LIMIT = 0.294;                      // theoretical limit of a single-junction silicon cell (Richter et al., IEEE J. Photovolt. 2013)
const sapm = (E, ta, ws) => E * Math.exp(SA + SB * ws) + ta + (E / 1000) * SDT;
const out = { inputs: { PDC0, GAMMA, A_MOD, ETA_STC, T_MAX, RS_K, SI_LIMIT } };

// ---- claim 1: magnifier +3 … +10 D -> f = 10 … 33 cm, magnification 2x … 4x
const mag = Dp => ({ D: Dp, f_cm: 100 / Dp, M_relaxed: Dp / 4, M_near: 1 + Dp / 4 });   // reference distance 25 cm
out.magnifier = [3, 10].map(mag);

// ---- claim "C = 5x, 20 % -> ~55 %": what concentration really does (instantaneous, DNI = 1000 W/m², normal incidence)
// Lens aperture = 5 × module area, all light homogenised onto one module (best case for the claim).
function concentrated(C, tau, Tcell) {
  const E = 1000 * C * tau;                                  // W/m² on the module
  const ideal = PDC0 * E / 1000;                             // linear, 25 °C, no resistance loss
  const rs = Math.max(0, 1 - RS_K * (E / 1000 - 1));
  const p = ideal * rs * (1 + GAMMA * (Tcell - 25));
  const aperture = C * A_MOD;
  return { C, tau, E_on_module_Wm2: E, T_cell_C: Tcell, P_W: p, eta_vs_aperture: p / (1000 * aperture), aperture_m2: aperture };
}
const C = 5, TAU = 0.90;                                     // 90 %: the draft's own "90 %+ transparency"
const Tpassive = sapm(1000 * C * TAU, 25, 1);                // no active cooling, 25 °C air, 1 m/s wind
out.c5 = {
  claim_eta: 0.55,
  passive: concentrated(C, TAU, Tpassive),
  cooled60: concentrated(C, TAU, 60),
  cooled25: concentrated(C, TAU, 25),
  five_plain_modules_W: 5 * PDC0,                            // same 9.99 m² covered with 5 ordinary modules (STC)
  plain_module_at_same_air: { T_cell_C: sapm(1000, 25, 1), P_W: PDC0 * (1 + GAMMA * (sapm(1000, 25, 1) - 25)) },
};

// ---- claim "+50 … 70 % more energy": annual Baku energy per m² of collecting area
// Ordinary module fixed (scenario A) and on a 2-axis tracker; lens C = 5 must track (imaging lens, beam only).
function annual() {
  let eA = 0, eT = 0, eLc = 0, eLp = 0, hotHours = 0;
  for (let i = 0; i < D.f_glob.length; i++) {
    const ta = D.ta[i], ws = D.ws[i];
    const fG = D.f_glob[i], tG = D.t_glob[i];
    if (fG > 0) eA += Math.max(0, PDC0 * (D.f_beam[i] + D.f_diff[i]) / 1000 * (1 + GAMMA * (sapm(fG, ta, ws) - 25)));
    if (tG > 0) eT += Math.max(0, PDC0 * (D.t_beam[i] + D.t_diff[i]) / 1000 * (1 + GAMMA * (sapm(tG, ta, ws) - 25)));
    const Eb = D.t_dnicos[i] * C * TAU;                       // only direct light is focused
    if (Eb > 0) {
      const rs = Math.max(0, 1 - RS_K * (Eb / 1000 - 1));
      const Tp = sapm(Eb, ta, ws);
      if (Tp > T_MAX) hotHours++;
      eLp += Math.max(0, PDC0 * Eb / 1000 * rs * (1 + GAMMA * (Tp - 25)));          // passive (would exceed T_MAX)
      eLc += Math.max(0, PDC0 * Eb / 1000 * rs * (1 + GAMMA * (ta + 10 - 25)));     // active cooling: cell = air + 10 K
    }
  }
  const per = (e, area) => e / 1000 / area;
  return {
    A_fixed_kWh_m2: per(eA, A_MOD), A_2axis_kWh_m2: per(eT, A_MOD),
    lens_C5_cooled_kWh_m2: per(eLc, C * A_MOD), lens_C5_passive_kWh_m2: per(eLp, C * A_MOD),
    lens_hours_above_Tmax: hotHours,
    beam_share_on_tracker: D.t_dnicos.reduce((s, v) => s + v, 0) / D.t_glob.reduce((s, v) => s + v, 0),
  };
}
out.annual = annual();

const a = out.annual, c = out.c5;
console.log("magnifier:", out.magnifier.map(m => `+${m.D} D: f=${m.f_cm.toFixed(1)} cm, M=${m.M_relaxed.toFixed(2)}…${m.M_near.toFixed(2)}x`).join(" | "));
console.log(`C=5, tau=0.90, DNI 1000: passive T=${c.passive.T_cell_C.toFixed(0)} °C P=${c.passive.P_W.toFixed(0)} W eta=${(100 * c.passive.eta_vs_aperture).toFixed(1)}% | cooled 60 °C P=${c.cooled60.P_W.toFixed(0)} W eta=${(100 * c.cooled60.eta_vs_aperture).toFixed(1)}% | cooled 25 °C eta=${(100 * c.cooled25.eta_vs_aperture).toFixed(1)}% | 5 plain modules ${c.five_plain_modules_W} W`);
console.log(`plain module same air: T=${c.plain_module_at_same_air.T_cell_C.toFixed(1)} °C P=${c.plain_module_at_same_air.P_W.toFixed(0)} W`);
console.log(`annual kWh/m²: A fixed ${a.A_fixed_kWh_m2.toFixed(1)}, A 2-axis ${a.A_2axis_kWh_m2.toFixed(1)}, lens C5 cooled ${a.lens_C5_cooled_kWh_m2.toFixed(1)}, passive ${a.lens_C5_passive_kWh_m2.toFixed(1)} (${a.lens_hours_above_Tmax} h above ${T_MAX} °C), beam share ${(100 * a.beam_share_on_tracker).toFixed(1)}%`);
// consistency with the notebook
const okA = Math.abs(a.A_fixed_kWh_m2 - 355.4006) < 0.01, okT = Math.abs(a.A_2axis_kWh_m2 - (895.1793179073231 / A_MOD)) < 0.01;
console.log(okA && okT ? "notebook consistency OK" : `notebook consistency FAILED ${a.A_2axis_kWh_m2} vs ${895.1793 / A_MOD}`);
if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(out));
process.exit(okA && okT ? 0 : 1);
