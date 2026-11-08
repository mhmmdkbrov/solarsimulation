// JS port of the notebook model (solar_simulation.ipynb, section 4). Pure functions, no DOM.
const SolarModel = (() => {
  const SCEN = ["A_fixed", "B_fixed", "A_2axis", "C_2axis"];

  const PRESETS = {
    base: { optics: true, tau_b: 0.92, tau_d: 0.84, gap_beam: 0.30, gap_diff: 0.10, nonunif: 0.02, heat: 2.0,
            f_act: 0.92, gamma_pdc: -0.0030, tau_c: 0.85, intercept: 0.95, eta: 0.30, gamma_c: -0.0015, R: 4.0,
            fan: 0.0, trk: 4.0, ctrl: 0.5 },
    pess: { optics: true, tau_b: 0.88, tau_d: 0.78, gap_beam: 0.0, gap_diff: 0.0, nonunif: 0.06, heat: 5.0,
            f_act: 0.95, gamma_pdc: -0.0030, tau_c: 0.75, intercept: 0.88, eta: 0.25, gamma_c: -0.0030, R: 8.0,
            fan: 2.0, trk: 8.0, ctrl: 1.5 },
    opt:  { optics: true, tau_b: 0.96, tau_d: 0.90, gap_beam: 0.7, gap_diff: 0.3, nonunif: 0.0, heat: 0.0,
            f_act: 0.88, gamma_pdc: -0.0030, tau_c: 0.92, intercept: 0.99, eta: 0.38, gamma_c: -0.0005, R: 1.5,
            fan: 0.0, trk: 1.0, ctrl: 0.2 },
  };
  const AP_UNIT = 0.01;  // m² per lens (assumption; does not change annual energy in this model version)
  const CELL = 1e-4;     // m² per cell

  function cpvCell(pc, ta, nUnits, p) {
    // analytic solution of T = Ta + R*q*(1-eta(T)), eta(T) = eta0*(1+g*(T-25))
    const q = pc / nUnits, R = p.R, e0 = p.eta, g = p.gamma_c;
    const T = (ta + R * q * (1 - e0) + R * q * e0 * g * 25) / (1 + R * q * e0 * g);
    const eta = Math.max(0, e0 * (1 + g * (T - 25)));
    return [pc * eta, T];
  }

  function simulate(D, p) {
    const n = D.ghi.length, A = D.meta.area_m2;
    const { sapm_a: a, sapm_b: b, sapm_dT: dT } = D.meta.sapm;
    const pdc0 = D.meta.module.pdc0_W, g = p.gamma_pdc;
    const ratio = (1 - p.f_act) / p.f_act;
    const gB = 1 + ratio * p.gap_beam, gD = 1 + ratio * p.gap_diff;
    const mism = p.optics ? 1 - p.nonunif : 1;
    const nUnits = A / AP_UNIT;
    const dc = {}, aux = {};
    for (const s of SCEN) { dc[s] = new Float64Array(n); aux[s] = new Float64Array(n); }
    const tcellC = new Float64Array(n), icell = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const ta = D.ta[i], ws = D.ws[i], sun = D.sun[i];
      const fG = D.f_glob[i], tG = D.t_glob[i];
      const tcF = fG * Math.exp(a + b * ws) + ta + (fG / 1000) * dT;
      const tcT = tG * Math.exp(a + b * ws) + ta + (tG / 1000) * dT;
      // A fixed (PVWatts)
      const eA = D.f_beam[i] + D.f_diff[i];
      dc.A_fixed[i] = Math.max(0, (pdc0 * eA / 1000) * (1 + g * (tcF - 25)));
      // B retrofit
      const eB = p.optics ? D.f_beam[i] * p.tau_b * D.f_layer[i] * gB + D.f_diff[i] * p.tau_d * gD : eA;
      const tcB = tcF + p.heat * fG / 1000;
      dc.B_fixed[i] = Math.max(0, (pdc0 * eB / 1000) * (1 + g * (tcB - 25)) * mism);
      // A on 2-axis tracker
      const eT = D.t_beam[i] + D.t_diff[i];
      dc.A_2axis[i] = Math.max(0, (pdc0 * eT / 1000) * (1 + g * (tcT - 25)));
      // C CPV: P_in = DNI·max(cos AOI,0)·A_aperture; P_cell = P_in·τ·f; C is used only for the intensity
      const pin = D.t_dnicos[i] * A;
      const pc = pin * p.tau_c * p.intercept;
      const [pel, T] = cpvCell(pc, ta, nUnits, p);
      dc.C_2axis[i] = pel; tcellC[i] = T; icell[i] = pc / (nUnits * CELL);
      const trk = p.trk * sun + p.ctrl;
      aux.A_2axis[i] = trk; aux.C_2axis[i] = trk + p.fan * sun;
    }
    return { dc, aux, tcellC, icell };
  }

  function summarize(D, r) {
    const A = D.meta.area_m2, out = {};
    for (const s of SCEN) {
      let dcs = 0, auxs = 0;
      const m = new Float64Array(12);
      for (let i = 0; i < D.ghi.length; i++) {
        dcs += r.dc[s][i]; auxs += r.aux[s][i];
        m[D.month[i] - 1] += r.dc[s][i] - r.aux[s][i];
      }
      out[s] = { dc_kWh: dcs / 1000, aux_kWh: auxs / 1000, net_kWh: (dcs - auxs) / 1000,
                 net_kWh_m2: (dcs - auxs) / 1000 / A, monthly_kWh_m2: Array.from(m, v => v / 1000 / A) };
    }
    return out;
  }

  function bySky(D, r) {
    const edges = [0, 0.3, 0.5, 0.7, 0.9, 1.0001];
    const rows = edges.slice(0, -1).map(() => ({ hours: 0, A_fixed: 0, B_fixed: 0, A_2axis: 0, C_2axis: 0 }));
    for (let i = 0; i < D.ghi.length; i++) {
      if (!(D.ghi[i] > 10)) continue;
      const kd = D.dhi[i] / D.ghi[i];
      for (let k = 0; k < rows.length; k++) {
        if (kd >= edges[k] && kd < edges[k + 1]) {
          rows[k].hours++;
          for (const s of SCEN) rows[k][s] += r.dc[s][i];
          break;
        }
      }
    }
    return rows;
  }

  // annual CPV net kWh/m² on a τ × η grid (other parameters from p)
  function cpvGrid(D, p, taus, etas) {
    const A = D.meta.area_m2, nUnits = A / AP_UNIT;
    const idx = [];
    for (let i = 0; i < D.ghi.length; i++) if (D.t_dnicos[i] > 0) idx.push(i);
    const base = Float64Array.from(idx, i => D.t_dnicos[i] * A * p.intercept);
    const ta = Float64Array.from(idx, i => D.ta[i]);
    let auxWh = 0;
    for (let i = 0; i < D.ghi.length; i++) auxWh += p.trk * D.sun[i] + p.ctrl + p.fan * D.sun[i];
    const Z = new Float64Array(etas.length * taus.length);
    const q = { R: p.R, gamma_c: p.gamma_c, eta: 0 };
    for (let ie = 0; ie < etas.length; ie++) {
      q.eta = etas[ie];
      for (let it = 0; it < taus.length; it++) {
        let sum = 0;
        const t = taus[it];
        for (let k = 0; k < idx.length; k++) sum += cpvCell(base[k] * t, ta[k], nUnits, q)[0];
        Z[ie * taus.length + it] = (sum - auxWh) / 1000 / A;
      }
    }
    return Z;
  }

  return { SCEN, PRESETS, simulate, summarize, bySky, cpvGrid };
})();
if (typeof module !== "undefined") module.exports = SolarModel;
