// Browser port of solarsim.scenarios (model v2). Pure functions, no DOM.
// Inputs: the "hourly" block of a docs/data/<dataset>.json file (POA components and sun geometry computed in Python
// with pvlib SPA, Perez and the front-glass IAM — the browser does not recompute the sun).
// Energy = Σ P·Δt with Δt = hourly.step_h. Gross DC − (tracker drive + controller + cooling) = net.
const SolarModel = (() => {
  const SCEN = ["A_fixed", "B_fixed", "A_2axis", "C_2axis"];
  const SAPM = { a: -3.47, b: -0.0594, dT: 3 };              // open_rack_glass_glass (King et al. 2004)

  const PRESETS = {
    base: { optics: true, tau_b: 0.92, tau_d: 0.84, gap_beam: 0.30, gap_diff: 0.10, nonunif: 0.02, heat: 2.0,
            f_act: 0.92, gamma_pdc: -0.0030, tau_c: 0.85, intercept: 0.95, accept: 1.0, track_sigma: 0.1,
            diff_accept: true, eta: 0.30, gamma_c: -0.0015, R: 4.0, fan: 0.0, trk: 4.0, ctrl: 0.5 },
    pess: { optics: true, tau_b: 0.88, tau_d: 0.78, gap_beam: 0.0, gap_diff: 0.0, nonunif: 0.06, heat: 5.0,
            f_act: 0.95, gamma_pdc: -0.0030, tau_c: 0.75, intercept: 0.88, accept: 0.6, track_sigma: 0.3,
            diff_accept: true, eta: 0.25, gamma_c: -0.0030, R: 8.0, fan: 2.0, trk: 8.0, ctrl: 1.5 },
    opt:  { optics: true, tau_b: 0.96, tau_d: 0.90, gap_beam: 0.7, gap_diff: 0.3, nonunif: 0.0, heat: 0.0,
            f_act: 0.88, gamma_pdc: -0.0030, tau_c: 0.92, intercept: 0.99, accept: 1.5, track_sigma: 0.05,
            diff_accept: true, eta: 0.38, gamma_c: -0.0005, R: 1.5, fan: 0.0, trk: 1.0, ctrl: 0.2 },
  };
  const AP_UNIT = 0.01, CELL = 1e-4;                         // m² per lens / per CPV cell (assumptions)
  const ETA_T_RANGE = [-20, 110], SUNS_RANGE = [1, 1000];

  const sapm = (E, ta, ws) => E * Math.exp(SAPM.a + SAPM.b * ws) + ta + (E / 1000) * SAPM.dT;

  // CPV: P_in = DNI·A_ap·max(cos AOI,0) (+ DHI·sin²θa inside the acceptance cone); P_cell = P_in·τ·intercept.
  // C = A_ap/A_cell only gives the cell intensity P_cell/A_cell — it never scales P_in.
  function cpvHour(dniCos, dhi, ta, A, p) {
    const nUnits = A / AP_UNIT, th = p.accept * Math.PI / 180, sg = p.track_sigma * Math.PI / 180;
    const trackF = sg > 0 ? 1 - Math.exp(-th * th / (2 * sg * sg)) : 1;
    const pin = dniCos * A + (p.diff_accept ? dhi * Math.sin(th) ** 2 * A : 0);
    const pc = pin * p.tau_c * p.intercept * trackF;
    const q = pc / nUnits, R = p.R, e0 = p.eta, g = p.gamma_c;
    const den = 1 + R * q * e0 * g;
    const T = (ta + R * q * (1 - e0) + R * q * e0 * g * 25) / den;
    const eta = Math.max(0, e0 * (1 + g * (T - 25)));
    const suns = pc / (nUnits * CELL) / 1000;
    return { pin, pc, T, eta, pel: pc * eta, suns,
             flags: { den_small: Math.abs(den) < 0.2, t_out_of_range: pc > 0 && (T < ETA_T_RANGE[0] || T > ETA_T_RANGE[1]),
                      suns_out_of_range: pc > 0 && (suns < SUNS_RANGE[0] || suns > SUNS_RANGE[1]),
                      eta_nonphysical: pc > 0 && (eta <= 0 || eta >= 0.5) } };
  }

  function simulate(D, p) {
    const h = D.hourly, n = h.n, A = D.areas.aperture_m2, pdc0 = 450, g = p.gamma_pdc;
    const ratio = (1 - p.f_act) / p.f_act;
    const gB = 1 + ratio * p.gap_beam, gD = 1 + ratio * p.gap_diff;
    const mism = p.optics ? 1 - p.nonunif : 1;
    const out = {};
    for (const s of SCEN) out[s] = { gross: new Float64Array(n), drive: new Float64Array(n), controller: new Float64Array(n), cooling: new Float64Array(n) };
    const flags = { den_small: 0, t_out_of_range: 0, suns_out_of_range: 0, eta_nonphysical: 0 };
    const tC = new Float64Array(n), sunsC = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const ta = h.ta[i], ws = h.ws[i], sun = h.sun[i];
      const tcF = sapm(h.f_glob[i], ta, ws), tcT = sapm(h.t_glob[i], ta, ws);
      const eA = h.f_beam[i] + h.f_diff[i];
      out.A_fixed.gross[i] = Math.max(0, pdc0 * eA / 1000 * (1 + g * (tcF - 25)));
      const eB = p.optics ? h.f_beam[i] * p.tau_b * h.f_layer[i] * gB + h.f_diff[i] * p.tau_d * gD : eA;
      out.B_fixed.gross[i] = Math.max(0, pdc0 * eB / 1000 * (1 + g * (tcF + p.heat * h.f_glob[i] / 1000 - 25)) * mism);
      out.A_2axis.gross[i] = Math.max(0, pdc0 * (h.t_beam[i] + h.t_diff[i]) / 1000 * (1 + g * (tcT - 25)));
      const c = cpvHour(h.t_dnicos[i], h.dhi[i], ta, A, p);
      out.C_2axis.gross[i] = c.pel; tC[i] = c.T; sunsC[i] = c.suns;
      for (const k in flags) if (c.flags[k]) flags[k]++;
      for (const s of ["A_2axis", "C_2axis"]) { out[s].drive[i] = p.trk * sun; out[s].controller[i] = p.ctrl; }
      out.C_2axis.cooling[i] = p.fan * sun;
    }
    return { series: out, flags, tC, sunsC };
  }

  function summarize(D, r) {
    const h = D.hourly, A = D.areas.aperture_m2, dt = h.step_h, out = {};
    for (const s of SCEN) {
      const t = { gross: 0, drive: 0, controller: 0, cooling: 0 }, mG = new Float64Array(12), mN = new Float64Array(12);
      const se = r.series[s];
      for (let i = 0; i < h.n; i++) {
        for (const k in t) t[k] += se[k][i];
        const net = se.gross[i] - se.drive[i] - se.controller[i] - se.cooling[i];
        mG[h.month[i] - 1] += se.gross[i]; mN[h.month[i] - 1] += net;
      }
      const kwh = v => v * dt / 1000, aux = kwh(t.drive + t.controller + t.cooling);
      out[s] = { gross_kWh_unit: kwh(t.gross), drive_kWh_unit: kwh(t.drive), controller_kWh_unit: kwh(t.controller),
                 cooling_kWh_unit: kwh(t.cooling), aux_kWh_unit: aux, net_kWh_unit: kwh(t.gross) - aux,
                 gross_kWh_m2_ap: kwh(t.gross) / A, net_kWh_m2_ap: (kwh(t.gross) - aux) / A,
                 monthly_gross_kWh_m2: Array.from(mG, v => v * dt / 1000 / A), monthly_net_kWh_m2: Array.from(mN, v => v * dt / 1000 / A) };
    }
    return out;
  }

  // sky classes by DHI/GHI, GHI > 10 W/m²; remaining hours reported separately so that the sum equals the year
  const CLASSES = [["clear", 0, 0.3], ["hazy", 0.3, 0.5], ["partly", 0.5, 0.9], ["overcast", 0.9, 1.0001]];
  function bySky(D, r) {
    const h = D.hourly, dt = h.step_h, keys = [...CLASSES.map(c => c[0]), "low_light", "kd_above_1"];
    const rows = Object.fromEntries(keys.map(k => [k, { hours: 0, ...Object.fromEntries(SCEN.map(s => [s, 0])) }]));
    for (let i = 0; i < h.n; i++) {
      let key = "low_light";
      if (h.ghi[i] > 10) {
        const kd = h.dhi[i] / h.ghi[i]; key = "kd_above_1";
        for (const [k, lo, hi] of CLASSES) if (kd >= lo && kd < hi) { key = k; break; }
      }
      rows[key].hours += dt;
      for (const s of SCEN) rows[key][s] += r.series[s].gross[i] * dt / 1000;
    }
    return rows;
  }

  // CPV net energy on a τ × η grid (other parameters from p); also returns a flag mask of non-trusted cells
  function cpvGrid(D, p, taus, etas) {
    const h = D.hourly, A = D.areas.aperture_m2, dt = h.step_h;
    let auxWh = 0;
    for (let i = 0; i < h.n; i++) auxWh += (p.trk + p.fan) * h.sun[i] + p.ctrl;
    // same equations as cpvHour, unrolled without allocations (2 501 grid cells × all lit hours)
    const nUnits = A / AP_UNIT, th = p.accept * Math.PI / 180, sg = p.track_sigma * Math.PI / 180;
    const trackF = sg > 0 ? 1 - Math.exp(-th * th / (2 * sg * sg)) : 1, s2 = Math.sin(th) ** 2;
    const pinA = [], taA = [];
    for (let i = 0; i < h.n; i++) {
      const pin = h.t_dnicos[i] * A + (p.diff_accept ? h.dhi[i] * s2 * A : 0);
      if (pin > 0) { pinA.push(pin * p.intercept * trackF); taA.push(h.ta[i]); }
    }
    const m = pinA.length, R = p.R, g = p.gamma_c, T0 = ETA_T_RANGE[0], T1 = ETA_T_RANGE[1];
    const Z = new Float64Array(etas.length * taus.length), bad = new Uint8Array(etas.length * taus.length);
    for (let ie = 0; ie < etas.length; ie++) {
      const e0 = etas[ie];
      for (let it = 0; it < taus.length; it++) {
        const tau = taus[it];
        let s = 0, flagged = 0;
        for (let k = 0; k < m; k++) {
          const pc = pinA[k] * tau, q = pc / nUnits, den = 1 + R * q * e0 * g;
          const T = (taA[k] + R * q * (1 - e0) + R * q * e0 * g * 25) / den;
          const eta = e0 * (1 + g * (T - 25));
          s += eta > 0 ? pc * eta : 0;
          if (Math.abs(den) < 0.2 || T < T0 || T > T1 || eta <= 0 || eta >= 0.5) flagged = 1;
        }
        Z[ie * taus.length + it] = (s - auxWh) * dt / 1000 / A;
        bad[ie * taus.length + it] = flagged;
      }
    }
    return { Z, bad };
  }

  return { SCEN, PRESETS, simulate, summarize, bySky, cpvGrid, cpvHour, sapm };
})();
if (typeof module !== "undefined") module.exports = SolarModel;
