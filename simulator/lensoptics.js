// Geometric (thin-lens, paraxial) optics of a lens placed above a standard PV module.
// Used by the "lens lab" page and its node test. Lengths in mm, irradiance in W/m², power in W.
const LensOptics = (() => {
  // Module geometry (Trina Vertex S+ TSM-450NEG9R.28, portrait): 6 cell columns across the width (x),
  // 24 rows along the length/slope (y), 3 bypass-diode substrings = column pairs.
  const LX = 1134, LY = 1762, NX = 6, NY = 24;
  const PX = LX / NX, PY = LY / NY;          // cell pitch
  const CX = 182, CY = 70.1;                 // active cell size (assumption; gives ~0.92 active area)
  const F_ACT = (CX * CY) / (PX * PY);
  const SUN_HALF = 0.00465;                  // rad, angular radius of the sun (focal spot cannot be smaller)
  const RS_K = 0.035;                        // assumption: extra series-resistance loss per extra "sun" of local intensity
  const TILT = 35 * Math.PI / 180;
  const C_MAX = 46000;                       // thermodynamic limit of solar concentration (sun's angular size)
  // the focal spot cannot be smaller than aperture / C_MAX
  function limitSpot(wx, wy, area) {
    const amin = area / C_MAX;
    if (wx * wy >= amin) return [wx, wy];
    const k = Math.sqrt(amin / Math.max(wx * wy, 1e-12));
    return [wx * k, wy * k];
  }

  // Fresnel/absorption transmission vs. angle (pvlib.iam.physical), normalised to 1 at normal incidence
  function iamPhysical(theta, n, K, L) {
    const t = Math.min(Math.abs(theta), 89.9 * Math.PI / 180);
    const tau = th => {
      if (th < 1e-6) { const r = ((n - 1) / (n + 1)) ** 2; return (1 - r) * Math.exp(-K * L); }
      const tr = Math.asin(Math.sin(th) / n);
      const rs = (Math.sin(tr - th) / Math.sin(tr + th)) ** 2, rp = (Math.tan(tr - th) / Math.tan(tr + th)) ** 2;
      return (1 - 0.5 * (rs + rp)) * Math.exp(-K * L / Math.cos(tr));
    };
    return tau(t) / tau(0);
  }
  const iamLens = th => iamPhysical(th, 1.49, 4, 0.003);      // add-on lens (PMMA-like)
  const iamGlass = th => iamPhysical(th, 1.526, 4, 0.002);    // module's own glass

  // length of [a,b] covered by a periodic row of cells (pitch p, width c, centred on multiples of p)
  function covered(a, b, p, c) {
    const F = x => { const k = Math.floor(x / p), r = x - k * p; return k * c + Math.min(r, c / 2) + Math.max(0, r - (p - c / 2)); };
    return F(b) - F(a);
  }
  const overlap1 = (a0, a1, b0, b1) => Math.max(0, Math.min(a1, b1) - Math.max(a0, b0));

  function lensType(P) {
    if (Math.abs(P) < 1e-9) return { kind: "flat", f: Infinity };
    return { kind: P > 0 ? "converging" : "diverging", f: 1000 / P };
  }
  // magnification of the aperture at the cell plane: m = 1 - h/f
  const mag = (P, h) => (Math.abs(P) < 1e-9 ? 1 : 1 - h / (1000 / P));

  // ---- one lenslet per cell (lens array) ----
  // blurHalf: angular half-width (in tan units) of the light source: the sun disk, or a patch of sky for diffuse light
  function lensletCapture(P, h, tx, ty, blurHalf = SUN_HALF) {
    const m = mag(P, h), blur = 2 * h * blurHalf;
    const [wx, wy] = limitSpot(Math.abs(m) * PX + blur, Math.abs(m) * PY + blur, PX * PY);
    const sx = -h * tx, sy = -h * ty;   // light travels opposite to the sun vector
    const cx = covered(sx - wx / 2, sx + wx / 2, PX, CX) / wx;
    const cy = covered(sy - wy / 2, sy + wy / 2, PY, CY) / wy;
    return { cap: cx * cy, conc: (PX * PY) / (wx * wy) };
  }

  // ---- one big lens covering the whole module ----
  // returns per-cell beam fraction relative to the incoming beam irradiance and the local intensity factor
  function bigLensCells(P, h, tx, ty, out, blurHalf = SUN_HALF) {
    const m = mag(P, h), blur = 2 * h * blurHalf;
    const [wx, wy] = limitSpot(Math.abs(m) * LX + blur, Math.abs(m) * LY + blur, LX * LY);
    const sx = -h * tx, sy = -h * ty, conc = (LX * LY) / (wx * wy);
    const x0 = sx - wx / 2, x1 = sx + wx / 2, y0 = sy - wy / 2, y1 = sy + wy / 2;
    for (let i = 0; i < NX; i++) {
      const cxm = -LX / 2 + (i + 0.5) * PX;
      const ox = overlap1(x0, x1, cxm - CX / 2, cxm + CX / 2);
      for (let j = 0; j < NY; j++) {
        const cym = -LY / 2 + (j + 0.5) * PY;
        const oy = overlap1(y0, y1, cym - CY / 2, cym + CY / 2);
        out[i * NY + j] = (conc * ox * oy) / (CX * CY);   // cell beam irradiance / incoming beam irradiance
      }
    }
    return conc;
  }

  // cos-weighted hemisphere sampling for diffuse light
  const DIRS = (() => {
    const d = []; let wsum = 0;
    for (let a = 2.5; a < 88; a += 5) for (let p = 0; p < 360; p += 15) {
      const th = a * Math.PI / 180, ph = p * Math.PI / 180, w = Math.cos(th) * Math.sin(th);
      // each sample stands for a 5° × 15° patch of sky: its spot is smeared over that patch (no sampling gaps)
      const bh = 0.5 * Math.max((5 * Math.PI / 180) / Math.cos(th) ** 2, Math.tan(th) * (15 * Math.PI / 180));
      d.push({ th, tx: Math.tan(th) * Math.cos(ph), ty: Math.tan(th) * Math.sin(ph), w, bh }); wsum += w;
    }
    d.forEach(o => (o.w /= wsum));
    return d;
  })();
  const GLASS_DIFF = DIRS.reduce((s, o) => s + o.w * iamGlass(o.th), 0);

  // per-setting diffuse factors: lens array -> scalar, big lens -> per-cell array (relative to no-lens diffuse)
  function diffuseFactors(cfg) {
    if (cfg.mode === "array") {
      let s = 0;
      for (const o of DIRS) s += o.w * iamLens(o.th) * iamGlass(o.th) * lensletCapture(cfg.P, cfg.h, o.tx, o.ty, o.bh).cap;
      return { array: s / (GLASS_DIFF * F_ACT) };
    }
    const acc = new Float64Array(NX * NY), tmp = new Float64Array(NX * NY);
    for (const o of DIRS) {
      bigLensCells(cfg.P, cfg.h, o.tx, o.ty, tmp, o.bh);
      const w = o.w * iamLens(o.th) * iamGlass(o.th) / GLASS_DIFF;
      for (let k = 0; k < acc.length; k++) acc[k] += w * tmp[k];
    }
    return { cells: acc };
  }

  // equivalent module irradiance (W/m² that a uniformly lit module would need for the same power)
  // gb: beam irradiance on the plane after the module glass (W/m²), gd: diffuse after module glass,
  // tx, ty: tangent of the incidence angle components in the module plane, th: incidence angle (rad)
  function moduleIrradiance(cfg, df, gb, gd, tx, ty, th, cellsOut) {
    const tau = cfg.tau;
    if (cfg.mode === "array") {
      let gBeam = 0, conc = 1;
      if (gb > 0) {
        const r = lensletCapture(cfg.P, cfg.h, tx, ty); conc = r.conc;
        const iLoc = gb * tau * iamLens(th) * conc;                    // local intensity in the focal spot
        const pen = Math.max(0, 1 - RS_K * Math.max(0, iLoc / 1000 - 1));
        gBeam = gb * tau * iamLens(th) * r.cap / F_ACT * pen;
      }
      const g = gBeam + gd * tau * df.array;
      if (cellsOut) cellsOut.fill(g);
      return { g, conc, mismatch: 1 };
    }
    const cells = cellsOut || new Float64Array(NX * NY);
    let conc = 1;
    if (gb > 0) {
      conc = bigLensCells(cfg.P, cfg.h, tx, ty, cells);
      const iLoc = gb * tau * iamLens(th) * conc;
      const pen = Math.max(0, 1 - RS_K * Math.max(0, iLoc / 1000 - 1));
      for (let k = 0; k < cells.length; k++) cells[k] = cells[k] * gb * tau * iamLens(th) * pen;
    } else cells.fill(0);
    for (let k = 0; k < cells.length; k++) cells[k] += gd * tau * df.cells[k];
    // series string with 3 bypass diodes (column pairs): current limited by the weakest cell of each substring
    const mins = [0, 1, 2].map(s => { let mn = Infinity; for (let i = 2 * s; i < 2 * s + 2; i++) for (let j = 0; j < NY; j++) mn = Math.min(mn, cells[i * NY + j]); return mn; });
    let best = 0;
    for (const I of mins) { const n = mins.filter(v => v >= I - 1e-9).length; best = Math.max(best, I * n / 3); }
    let mean = 0; for (const v of cells) mean += v; mean /= cells.length;
    return { g: best, conc, mismatch: mean > 0 ? best / mean : 1, substringMins: mins };
  }

  // sun vector in the module frame (tilt 35°, facing south); doy and local hour (UTC+4)
  function sunInPanel(doy, hourLocal, lat = 40.41, lon = 49.87, offsetH = 0.1672) {
    const hUTC = hourLocal - 4 + offsetH;
    const g = 2 * Math.PI / 365 * (doy - 1 + (hUTC - 12) / 24);
    const eqt = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
    const dec = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
    const tst = hUTC * 60 + eqt + 4 * lon, H = (tst / 4 - 180) * Math.PI / 180, phi = lat * Math.PI / 180;
    const E = -Math.cos(dec) * Math.sin(H);
    const N = Math.sin(dec) * Math.cos(phi) - Math.cos(dec) * Math.sin(phi) * Math.cos(H);
    const U = Math.sin(dec) * Math.sin(phi) + Math.cos(dec) * Math.cos(phi) * Math.cos(H);
    const sx = E, sy = N * Math.cos(TILT) + U * Math.sin(TILT), sz = -N * Math.sin(TILT) + U * Math.cos(TILT);
    return { up: U > 0, cos: sz, tx: sz > 0.02 ? sx / sz : 0, ty: sz > 0.02 ? sy / sz : 0, th: Math.acos(Math.max(-1, Math.min(1, sz))), elev: Math.asin(U) * 180 / Math.PI };
  }

  // annual net DC energy (kWh/m²) for the plain module and the lens configuration (same notebook inputs)
  function annual(D, cfg, step = 1) {
    const { sapm_a: a, sapm_b: b, sapm_dT: dT } = D.meta.sapm;
    const pdc0 = D.meta.module.pdc0_W, g = D.meta.module.gamma_pdc_per_C, A = D.meta.area_m2;
    const df = diffuseFactors(cfg), cells = new Float64Array(NX * NY);
    let eA = 0, eL = 0;
    for (let i = 0; i < D.f_glob.length; i += step) {
      const fG = D.f_glob[i]; if (fG <= 0) continue;
      const tc = fG * Math.exp(a + b * D.ws[i]) + D.ta[i] + (fG / 1000) * dT, tf = 1 + g * (tc - 25);
      eA += Math.max(0, pdc0 * (D.f_beam[i] + D.f_diff[i]) / 1000 * tf);
      const s = sunInPanel(D.doy[i], D.hour[i]);
      const r = moduleIrradiance(cfg, df, s.cos > 0.02 ? D.f_beam[i] : 0, D.f_diff[i], s.tx, s.ty, s.th, cells);
      eL += Math.max(0, pdc0 * r.g / 1000 * tf);
    }
    return { A: eA * step / 1000 / A, L: eL * step / 1000 / A };
  }

  return { LX, LY, NX, NY, PX, PY, CX, CY, F_ACT, SUN_HALF, RS_K, C_MAX, lensType, mag, iamLens, iamGlass, lensletCapture,
           bigLensCells, diffuseFactors, moduleIrradiance, sunInPanel, annual, DIRS };
})();
if (typeof module !== "undefined") module.exports = LensOptics;
