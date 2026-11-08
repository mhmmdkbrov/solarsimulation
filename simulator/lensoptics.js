// Browser port of solarsim.optics + solarsim.lenslab (model v2, level 1: finite geometry, thin paraxial lens).
// Lengths mm, irradiance W/m², power W. Same equations as Python; parity is checked by tests/parity_lens.py.
const LensOptics = (() => {
  const LX = 1134, LY = 1762, NX = 6, NY = 24, PX = LX / NX, PY = LY / NY;
  const F_ACT = 0.92, CX = 182, CY = F_ACT * LX * LY / (144 * CX);
  const T_GLASS = 2.1, N_GLASS = 1.5, C_MAX = 46000, SUN_HALF_TAN = Math.tan(0.2665 * Math.PI / 180), RS_K = 0.035;
  // paraxial-model warning criteria (simulator conventions, not manufacturability limits); = solarsim/optics.py
  const PARAXIAL_GOOD_DEG = 10, PARAXIAL_FAIR_DEG = 20, PARAXIAL_WARN_DEG = 30;
  const cxs = Array.from({ length: NX }, (_, i) => -LX / 2 + (i + 0.5) * PX);
  const cys = Array.from({ length: NY }, (_, j) => -LY / 2 + (j + 0.5) * PY);
  const GLASS = { n: 1.526, K: 4, L: 0.002 };

  const focal = P => (Math.abs(P) < 1e-12 ? Infinity : 1000 / P);
  const kind = P => (Math.abs(P) < 1e-12 ? "flat" : P > 0 ? "converging" : "diverging");

  function fresnel(th, n) {
    const t = Math.min(Math.max(Math.abs(th), 1e-9), 89.9 * Math.PI / 180);
    const tr = Math.asin(Math.sin(t) / n);
    const rs = (Math.sin(tr - t) / Math.sin(tr + t)) ** 2, rp = (Math.tan(tr - t) / Math.tan(tr + t)) ** 2;
    return [0.5 * (rs + rp), tr];
  }
  // pvlib.iam.physical (normalised to 1 at normal incidence)
  function iamPhysical(th, n, K, L) {
    const tau = t => { const [R, tr] = fresnel(t, n); return (1 - R) * Math.exp(-K * L / Math.cos(tr)); };
    return Math.abs(th) >= Math.PI / 2 ? 0 : tau(th) / tau(1e-6);
  }
  const glassIam = th => iamPhysical(th, GLASS.n, GLASS.K, GLASS.L);

  // (transmitted, reflected, absorbed) by the lens; normal-incidence transmittance = cfg.tau
  function lensSplit(th, cfg) {
    const [R, tr] = fresnel(th, cfg.n), [R0] = fresnel(1e-6, cfg.n);
    const tBulk = Math.exp(-cfg.K * cfg.L / Math.cos(tr));
    const shape = ((1 - R) ** 2 * tBulk) / ((1 - R0) ** 2 * Math.exp(-cfg.K * cfg.L));
    const T = Math.min(1, Math.max(0, cfg.tau * shape));
    const A = Math.min(1 - T, Math.max(0, (1 - tBulk) * (1 - R)));
    return [T, 1 - T - A, A];
  }

  const hEff = h => Math.max(h - T_GLASS, 0) + T_GLASS / N_GLASS;
  function shift(h, t) {
    const th = Math.atan(t), tg = Math.tan(Math.asin(Math.sin(th) / N_GLASS));
    return -(Math.max(h - T_GLASS, 0) * t + T_GLASS * tg);
  }
  const ov = (a0, a1, b0, b1) => Math.max(0, Math.min(a1, b1) - Math.max(a0, b0));
  function tiles(mode) {
    return mode === "big" ? { tx: [0], ax: LX, ty: [0], ay: LY } : { tx: cxs, ax: PX, ty: cys, ay: PY };
  }

  // fractions of the power arriving at the cell plane: cells[NX*NY], own, neighbours, gap, off; conc; m
  function spotSplit(cfg, tx, ty, blurHalf = SUN_HALF_TAN, cellsOut) {
    const T = tiles(cfg.mode), f = focal(cfg.P), he = hEff(cfg.h);
    const m = isFinite(f) ? 1 - he / f : 1, mx = cfg.mode === "array_cyl" ? 1 : m;
    const blur = 2 * cfg.h * blurHalf;
    let wx = Math.abs(mx) * T.ax + blur, wy = Math.abs(m) * T.ay + blur;
    const k = Math.sqrt(Math.max(1, (T.ax * T.ay) / C_MAX / Math.max(wx * wy, 1e-12)));
    wx *= k; wy *= k;
    const sx = shift(cfg.h, tx), sy = shift(cfg.h, ty);
    const ntx = T.tx.length, nty = T.ty.length, share = 1 / (ntx * nty);
    const colX = new Float64Array(NX), colY = new Float64Array(NY);
    let ownX = 0, ownY = 0, inX = 0, inY = 0;
    for (let i = 0; i < ntx; i++) {
      const a0 = T.tx[i] + sx - wx / 2, a1 = a0 + wx;
      inX += ov(a0, a1, -LX / 2, LX / 2) / wx;
      for (let p = 0; p < NX; p++) { const o = ov(a0, a1, cxs[p] - CX / 2, cxs[p] + CX / 2) / wx; colX[p] += o; if (ntx === NX && p === i) ownX += o; }
    }
    for (let j = 0; j < nty; j++) {
      const a0 = T.ty[j] + sy - wy / 2, a1 = a0 + wy;
      inY += ov(a0, a1, -LY / 2, LY / 2) / wy;
      for (let q = 0; q < NY; q++) { const o = ov(a0, a1, cys[q] - CY / 2, cys[q] + CY / 2) / wy; colY[q] += o; if (nty === NY && q === j) ownY += o; }
    }
    const cells = cellsOut || new Float64Array(NX * NY);
    let on = 0;
    for (let p = 0; p < NX; p++) for (let q = 0; q < NY; q++) { const v = share * colX[p] * colY[q]; cells[p * NY + q] = v; on += v; }
    const own = cfg.mode === "big" ? 0 : share * ownX * ownY;
    const inside = share * inX * inY;
    return { cells, own, neighbours: on - own, gap: inside - on, off: 1 - inside, conc: (T.ax * T.ay) / (wx * wy), m };
  }

  function hemisphere(tiltDeg) {
    const d = [], b = tiltDeg * Math.PI / 180;
    for (let a = 2.5; a < 90; a += 5) for (let p = 0; p < 360; p += 15) {
      const th = a * Math.PI / 180, ph = p * Math.PI / 180;
      const up = Math.sin(th) * Math.sin(ph) * Math.sin(b) + Math.cos(th) * Math.cos(b);
      const blur = 0.5 * Math.max((5 * Math.PI / 180) / Math.cos(th) ** 2, Math.tan(th) * (15 * Math.PI / 180));
      d.push({ th, tx: Math.tan(th) * Math.cos(ph), ty: Math.tan(th) * Math.sin(ph), w: Math.cos(th) * Math.sin(th), sky: up > 0, blur });
    }
    return d;
  }
  function diffuseResponse(cfg, tiltDeg, part) {
    const dirs = hemisphere(tiltDeg).filter(o => (part === "sky" ? o.sky : !o.sky));
    const out = { cells: new Float64Array(NX * NY), own: 0, neighbours: 0, gap: 0, off: 0, refl_lens: 0, abs_lens: 0, refl_glass: 0, bare: 0 };
    if (!dirs.length) return out;
    const wsum = dirs.reduce((s, o) => s + o.w, 0), tmp = new Float64Array(NX * NY);
    for (const o of dirs) {
      const w = o.w / wsum, [T, R, A] = lensSplit(o.th, cfg), g = glassIam(o.th);
      const s = spotSplit(cfg, o.tx, o.ty, o.blur, tmp), reach = w * T * g;
      for (let k = 0; k < tmp.length; k++) out.cells[k] += reach * tmp[k];
      out.own += reach * s.own; out.neighbours += reach * s.neighbours; out.gap += reach * s.gap; out.off += reach * s.off;
      out.refl_lens += w * R; out.abs_lens += w * A; out.refl_glass += w * T * (1 - g); out.bare += w * g * F_ACT;
    }
    return out;
  }

  // one hour: cell-equivalent irradiance map (W/m²) and the power balance (W)
  function hour(cfg, beam, sky, ground, tx, ty, th, ds, dg, cellsW) {
    const A = LX * LY / 1e6, cellA = CX * CY / 1e6;
    const [T, R, Ab] = lensSplit(th, cfg), g = glassIam(th);
    const tmp = new Float64Array(NX * NY);
    const s = spotSplit(cfg, tx, ty, SUN_HALF_TAN, tmp);
    const pb = beam * A, ps = sky * A, pg = ground * A, reachB = pb * T * g;
    const iLoc = beam * T * g * s.conc, pen = Math.min(1, Math.max(0, 1 - RS_K * Math.max(0, iLoc / 1000 - 1)));
    const out = cellsW || new Float64Array(NX * NY);
    let rs = 0;
    for (let k = 0; k < out.length; k++) {
      const b = reachB * tmp[k];
      rs += b * (1 - pen);
      out[k] = (b * pen + ps * ds.cells[k] + pg * dg.cells[k]) / cellA;
    }
    return {
      cells: out, conc: s.conc, m: s.m, spot: s,
      balance: { in: pb + ps + pg, refl_lens: pb * R + ps * ds.refl_lens + pg * dg.refl_lens,
                 abs_lens: pb * Ab + ps * ds.abs_lens + pg * dg.abs_lens,
                 refl_glass: pb * T * (1 - g) + ps * ds.refl_glass + pg * dg.refl_glass,
                 own: reachB * s.own + ps * ds.own + pg * dg.own, neighbours: reachB * s.neighbours + ps * ds.neighbours + pg * dg.neighbours,
                 gap: reachB * s.gap + ps * ds.gap + pg * dg.gap, off: reachB * s.off + ps * ds.off + pg * dg.off, rs_loss: rs },
    };
  }

  // topology T1 (default) / T3: groups of 2 parallel strings × 24 cells (see solarsim/electrical.py)
  function strings(topology) {
    const groups = [];
    for (let g = 0; g < 3; g++) {
      const c0 = 2 * g, c1 = 2 * g + 1, s1 = [], s2 = [];
      if (topology === "T3") { for (let r = 0; r < 24; r++) { s1.push([c0, r]); s2.push([c1, r]); } }
      else { for (const c of [c0, c1]) for (let r = 0; r < 12; r++) { s1.push([c, r]); s2.push([c, r + 12]); } }
      groups.push([s1, s2]);
    }
    return groups;
  }
  const STR = { T1: strings("T1"), T3: strings("T3") };
  function fastFactor(cells, topology = "T1") {
    const caps = STR[topology].map(grp => grp.reduce((a, s) => a + Math.min(...s.map(([c, r]) => cells[c * NY + r])), 0) / 2);
    let mean = 0; for (const v of cells) mean += v; mean /= cells.length;
    if (mean <= 0) return { f: 1, caps };
    let best = 0;
    for (const I of caps) best = Math.max(best, I * caps.filter(c => c >= I - 1e-12).length / 3);
    return { f: best / mean, caps };
  }

  const NULL = { P: 0, h: T_GLASS, mode: "array", tau: 1, n: 1, K: 0, L: 0.003 };
  const SAPM = { a: -3.47, b: -0.0594, dT: 3 };

  function chain(D, cfg, topology) {
    const h = D.hourly, tilt = D.inputs.tilt, ds = diffuseResponse(cfg, tilt, "sky"), dg = diffuseResponse(cfg, tilt, "ground");
    const cells = new Float64Array(NX * NY), bal = { in: 0, refl_lens: 0, abs_lens: 0, refl_glass: 0, own: 0, neighbours: 0, gap: 0, off: 0, rs_loss: 0 };
    let e = 0;
    for (let i = 0; i < h.n; i++) {
      const fg = h.f_glob[i]; if (!(fg > 0)) continue;
      const beam = h.cos[i] > 0.02 ? h.beam[i] : 0, th = h.aoi[i] * Math.PI / 180;
      const r = hour(cfg, beam, h.sky[i], h.ground[i], h.tx[i], h.ty[i], th, ds, dg, cells);
      for (const k in bal) bal[k] += r.balance[k];
      let mean = 0; for (const v of cells) mean += v; mean /= cells.length;
      const tc = fg * Math.exp(SAPM.a + SAPM.b * h.ws[i]) + h.ta[i] + fg / 1000 * SAPM.dT;
      e += Math.max(0, 450 * mean / 1000 * (1 - 0.003 * (tc - 25))) * fastFactor(cells, topology).f;
    }
    return { e, bal };
  }

  // annual result (differential method: lens / null lens through the same chain, applied to scenario A)
  function annual(D, cfg, topology = "T1") {
    const L = chain(D, { n: 1.49, K: 4, L: 0.003, ...cfg }, topology), N = chain(D, NULL, topology);
    const A = D.annual.A_fixed.gross_kWh_m2_ap, ratio = L.e / N.e, dt = D.hourly.step_h;
    const bal = Object.fromEntries(Object.entries(L.bal).map(([k, v]) => [k, v * dt / 1000]));
    return { A_kWh_m2: A, L_kWh_m2: A * ratio, ratio, delta_pct: 100 * (ratio - 1), balance_kWh: bal };
  }

  const paraxialLabel = t => (t <= PARAXIAL_GOOD_DEG ? "yaxşı" : t <= PARAXIAL_FAIR_DEG ? "orta" : "aşağı");

  // f-number and ray angles of one lens tile (ax × ay mm), unrounded. Focusing axis: the larger of x, y for a
  // spherical tile, y only for a cylindrical one. N = |f|/a, edge-ray angle to the optical axis = atan((a/2)/|f|),
  // corner-ray angle = atan((diagonal/2)/|f|) for a spherical rectangular tile.
  function lensGeometry(f, ax, ay, cylindrical = false) {
    const [axis, a] = cylindrical ? ["y", ay] : ay >= ax ? ["y", ay] : ["x", ax];
    const out = { axis, aperture_mm: a, aperture_x_mm: ax, aperture_y_mm: ay, cylindrical, f_mm: null, f_number: null,
                  edge_angle_deg: 0, corner_angle_deg: null, diagonal_mm: null };
    if (!isFinite(f)) return out;
    const F = Math.abs(f);
    out.f_mm = f; out.f_number = F / a; out.edge_angle_deg = Math.atan(a / 2 / F) * 180 / Math.PI;
    if (!cylindrical) { const d = Math.hypot(ax, ay); out.diagonal_mm = d; out.corner_angle_deg = Math.atan(d / 2 / F) * 180 / Math.PI; }
    return out;
  }

  function validity(cfg) {
    const T = tiles(cfg.mode);
    const v = lensGeometry(focal(cfg.P), T.ax, T.ay, cfg.mode === "array_cyl");
    v.paraxial = paraxialLabel(v.edge_angle_deg);
    v.above_warn_limit = v.edge_angle_deg > PARAXIAL_WARN_DEG; v.warn_limit_deg = PARAXIAL_WARN_DEG;
    v.reliability = v.paraxial === "aşağı" ? "aşağı" : v.paraxial === "orta" ? "orta" : "yüksək";
    v.coarse = v.reliability === "aşağı";
    return v;
  }

  return { LX, LY, NX, NY, PX, PY, CX, CY, F_ACT, T_GLASS, C_MAX, RS_K, focal, kind, hEff, shift, lensSplit, glassIam,
           spotSplit, diffuseResponse, hour, fastFactor, annual, lensGeometry, validity, PARAXIAL_WARN_DEG, strings: STR };
})();
if (typeof module !== "undefined") module.exports = LensOptics;
