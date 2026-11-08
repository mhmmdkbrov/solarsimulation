// Universal optics over a receiver — browser twin of solarsim/uoptics.py (same algorithms; parity-tested).
// Level: "ilkin həndəsi hesab" (thin paraxial optics, uniform spot, sun disk). See the Python module docstring.
const UOptics = (() => {
  const SUN_HALF_DEG = 0.2665, SAPM = [-3.47, -0.0594, 3.0], MAX_LENSES = 400, RASTER = 60, STRIPS = 64, T_CELL_LIMIT_C = 85;
  const IST = "istehsalçı məlumatı", OLC = "ölçülüb", FRZ = "fərziyyə", STATUSES = [IST, OLC, FRZ];
  const TYPES = { linear_fresnel: "xətti Fresnel linzası", point_fresnel: "nöqtə fokuslu Fresnel linzası", convex: "qabarıq linza",
                  negative: "mənfi dioptriyalı (səpələyici) linza", flat: "düz örtük", cpc: "CPC reflektoru (birləşən parabolik konsentrator)" };
  const LEVEL_BASIC = "ilkin həndəsi hesab", LEVEL_TABLE = "ölçülmüş bucaq–ötürmə cədvəli ilə həndəsi hesab";
  const PARAXIAL_WARN_DEG = 30;
  const rad = d => d * Math.PI / 180, deg = r => r * 180 / Math.PI;
  const P = (value, status = FRZ, note = "") => ({ value, status, note });
  const clone = o => JSON.parse(JSON.stringify(o));

  const COMMON = () => ({
    eta_cell: P(0.22, FRZ, "hüceyrənin STC səmərəliliyi"),
    gamma_per_K: P(-0.0035, FRZ, "gücün temperatur əmsalı"),
    k_el: P(0.98, FRZ, "elektrik əmsalı (naqil, uyğunsuzluq)"),
    k_hs: P(1.0, FRZ, "istilik ötürən səth / qəbuledici sahəsi; 1 = adi modul kimi soyuma"),
    k_th: P(0.95, FRZ, "analitik baza üçün sabit istilik əmsalı"),
    track_err_deg: P(0.1, FRZ, "2 oxlu izləmədə sabit yönəltmə xətası (fokuslanan ox üzrə)"),
    drive_W: P(4.0, FRZ, "izləmə mühərriki, gündüz, hər izləyici üçün"),
    controller_W: P(0.5, FRZ, "idarəetmə, 24 saat"),
  });

  const CATALOG = {
    lfs150150: {
      name: "LFS150150 xətti Fresnel (Knight Optical)", type: "linear_fresnel", shape: "rect", focus_axis: "y", layout: "each", mount: "fixed",
      source: "https://knightoptical.com/stock/default/lenses/fresnel-lenses/reverse-configuration-fresnel-lenses.html",
      source_note: "Kataloq: f = 150 mm (±5%), apertura 150 × 500 mm, faset eni 0,3 mm, qalınlıq 2 mm, PMMA, düz tərəf Günəşə. Ötürmə rəqəmi verilmir.",
      params: {
        ap_x_mm: P(500, IST, "uzunluq (xətt boyunca, yivlər bu oxa paraleldir)"), ap_y_mm: P(150, IST, "fokuslanan ox üzrə en"),
        f_mm: P(150, IST, "±5%"), thickness_mm: P(2, IST, ""),
        n_mat: P(1.49, FRZ, "PMMA üçün tipik sındırma əmsalı (material istehsalçıdan: PMMA)"),
        tau0: P(0.92, FRZ, "istehsalçı ötürmə vermir; PMMA üçün tipik normal düşmə dəyəri"),
        angle_table: P(null, FRZ, "ölçülmüş bucaq–ötürmə cədvəli yoxdur"),
        rec_x_mm: P(500, FRZ, "Rev B qəbuledicisi: 500 × 75 mm"), rec_y_mm: P(75, FRZ, "Rev B qəbuledicisi: 500 × 75 mm"),
        h_mm: P(75, FRZ, "zolaq eni = qəbuledici eni olan məsafə (fokusdan əvvəl)"),
        nx: P(1, FRZ, ""), ny: P(18, FRZ, "Rev B: 18 linza"), pitch_x_mm: P(500, FRZ, ""), pitch_y_mm: P(150, FRZ, "linzalar arası boşluq yoxdur"),
        eta_opt_eff: P(0.85, FRZ, "Rev B sadə hesabının effektiv optik payı"), ...COMMON() },
    },
    point_fresnel: {
      name: "Nöqtə fokuslu Fresnel (ümumi şablon)", type: "point_fresnel", shape: "rect", focus_axis: "y", layout: "each", mount: "2axis",
      source: null, source_note: "Şablon: bütün dəyərlər fərziyyədir.",
      params: {
        ap_x_mm: P(300), ap_y_mm: P(300), f_mm: P(300), thickness_mm: P(3), n_mat: P(1.49, FRZ, "PMMA"),
        tau0: P(0.85, FRZ, "Fresnel fasetlərinin itkisi daxil, tipik"), angle_table: P(null),
        rec_x_mm: P(30), rec_y_mm: P(30), h_mm: P(300, FRZ, "fokusda"),
        nx: P(2), ny: P(2), pitch_x_mm: P(300), pitch_y_mm: P(300), eta_opt_eff: P(0.85), ...COMMON() },
    },
    convex: {
      name: "Qabarıq linza (şablon, +5 D)", type: "convex", shape: "circle", focus_axis: "y", layout: "each", mount: "2axis",
      source: null, source_note: "Şablon: bütün dəyərlər fərziyyədir.",
      params: {
        ap_x_mm: P(100, FRZ, "diametr"), ap_y_mm: P(100, FRZ, "dairəvi apertura: diametr"), f_mm: P(200, FRZ, "+5 D"),
        thickness_mm: P(8), n_mat: P(1.5, FRZ, "şüşə"), tau0: P(0.92, FRZ, "iki səthdə əks olunma, örtüksüz"), angle_table: P(null),
        rec_x_mm: P(50), rec_y_mm: P(50), h_mm: P(100, FRZ, "fokusun yarısı"),
        nx: P(1), ny: P(1), pitch_x_mm: P(100), pitch_y_mm: P(100), eta_opt_eff: P(0.92), ...COMMON() },
    },
    negative: {
      name: "Mənfi linza (şablon, −5 D)", type: "negative", shape: "circle", focus_axis: "y", layout: "each", mount: "fixed",
      source: null, source_note: "Şablon: bütün dəyərlər fərziyyədir.",
      params: {
        ap_x_mm: P(100, FRZ, "diametr"), ap_y_mm: P(100, FRZ, "dairəvi apertura: diametr"), f_mm: P(-200, FRZ, "−5 D, xəyali fokus"),
        thickness_mm: P(4), n_mat: P(1.5), tau0: P(0.92), angle_table: P(null),
        rec_x_mm: P(100), rec_y_mm: P(100), h_mm: P(50),
        nx: P(1), ny: P(1), pitch_x_mm: P(100), pitch_y_mm: P(100), eta_opt_eff: P(0.92), ...COMMON() },
    },
    flat: {
      name: "Düz örtük (şablon)", type: "flat", shape: "rect", focus_axis: "y", layout: "each", mount: "fixed",
      source: null, source_note: "Şablon: bütün dəyərlər fərziyyədir.",
      params: {
        ap_x_mm: P(1000), ap_y_mm: P(1000), f_mm: P(null, FRZ, "fokus yoxdur"), thickness_mm: P(3), n_mat: P(1.5), tau0: P(0.92),
        angle_table: P(null), rec_x_mm: P(1000), rec_y_mm: P(1000), h_mm: P(5),
        nx: P(1), ny: P(1), pitch_x_mm: P(1000), pitch_y_mm: P(1000), eta_opt_eff: P(0.92), ...COMMON() },
    },
    cpc: {
      name: "CPC reflektoru (xətti, şablon)", type: "cpc", shape: "rect", focus_axis: "y", layout: "each", mount: "fixed",
      source: null, source_note: "Şablon: ideal 2D CPC, apertura qəbul bucağından və qəbuledicidən hesablanır.",
      params: {
        accept_deg: P(30, FRZ, "qəbul yarım-bucağı"), reflectivity: P(0.90), n_reflections: P(1.0, FRZ, "orta əks olunma sayı"),
        rec_x_mm: P(500, FRZ, "uzunluq"), rec_y_mm: P(50, FRZ, "fokuslanan ox üzrə en"),
        nx: P(1), ny: P(10), pitch_x_mm: P(500), pitch_y_mm: P(100), eta_opt_eff: P(0.81), ...COMMON() },
    },
  };
  for (const [k, hs, note] of [["lfs150150", 2.0, "istilik ötürən səth aperturaya bərabər (C = 2)"],
                               ["point_fresnel", 100.0, "passiv radiator aperturaya bərabər (C = 100)"],
                               ["convex", 3.0, "istilik ötürən səth təxminən aperturaya bərabər"],
                               ["cpc", 2.0, "istilik ötürən səth aperturaya bərabər (C = 2)"]]) CATALOG[k].params.k_hs = P(hs, FRZ, note);

  const REQUIRED = {
    linear_fresnel: ["ap_x_mm", "ap_y_mm", "f_mm", "tau0", "n_mat"], point_fresnel: ["ap_x_mm", "ap_y_mm", "f_mm", "tau0", "n_mat"],
    convex: ["ap_x_mm", "ap_y_mm", "f_mm", "tau0", "n_mat"], negative: ["ap_x_mm", "ap_y_mm", "f_mm", "tau0", "n_mat"],
    flat: ["ap_x_mm", "ap_y_mm", "tau0", "n_mat"], cpc: ["accept_deg", "reflectivity", "n_reflections"],
  };
  const REQUIRED_RX = ["rec_x_mm", "rec_y_mm", "nx", "ny", "pitch_x_mm", "pitch_y_mm", "eta_cell", "gamma_per_K", "k_el", "k_hs"];

  const preset = key => clone(CATALOG[key]);
  const v = (cfg, name, def = null) => { const p = cfg.params[name]; return p == null || p.value == null ? def : p.value; };
  const num = x => typeof x === "number" && isFinite(x);
  const layout = cfg => (cfg.type === "cpc" ? "each" : cfg.layout || "each");

  function aperture(cfg) {
    if (cfg.type === "cpc") {
      const s = Math.sin(rad(v(cfg, "accept_deg"))), rx = v(cfg, "rec_x_mm"), ry = v(cfg, "rec_y_mm");
      return (cfg.focus_axis || "y") === "x" ? [rx / s, ry] : [rx, ry / s];
    }
    return [v(cfg, "ap_x_mm"), v(cfg, "ap_y_mm")];
  }

  function validate(cfg) {
    const t = cfg.type;
    if (!(t in TYPES)) return { ok: false, missing: ["type"], errors: ["optika tipi seçilməyib"] };
    const need = [...new Set([...REQUIRED[t], ...REQUIRED_RX, ...(t === "cpc" ? [] : ["h_mm"])])];
    const missing = need.filter(k => !num(v(cfg, k))), err = [];
    if (!missing.length) {
      if (t !== "cpc") {
        if (v(cfg, "ap_x_mm") <= 0 || v(cfg, "ap_y_mm") <= 0) err.push("apertura ölçüləri müsbət olmalıdır");
        if (!(v(cfg, "tau0") > 0 && v(cfg, "tau0") <= 1)) err.push("ötürmə 0 ilə 1 arasında olmalıdır");
        if (v(cfg, "h_mm") <= 0) err.push("linza–qəbuledici məsafəsi müsbət olmalıdır");
      }
      if (["linear_fresnel", "point_fresnel", "convex"].includes(t) && v(cfg, "f_mm") <= 0) err.push("toplayıcı optikanın fokus məsafəsi müsbət olmalıdır");
      if (t === "negative" && v(cfg, "f_mm") >= 0) err.push("mənfi linzanın fokus məsafəsi mənfi olmalıdır");
      if (t === "cpc" && !(v(cfg, "accept_deg") > 0 && v(cfg, "accept_deg") < 90)) err.push("CPC qəbul bucağı 0° ilə 90° arasında olmalıdır");
      if (v(cfg, "rec_x_mm") <= 0 || v(cfg, "rec_y_mm") <= 0) err.push("qəbuledicinin ölçüləri müsbət olmalıdır");
      const nx = v(cfg, "nx"), ny = v(cfg, "ny");
      if (nx < 1 || ny < 1 || nx !== Math.trunc(nx) || ny !== Math.trunc(ny) || nx * ny > MAX_LENSES) err.push(`linza sayı tam ədəd olmalıdır, 1 … ${MAX_LENSES}`);
      const [ax, ay] = aperture(cfg);
      if (v(cfg, "pitch_x_mm") < ax - 1e-9 || v(cfg, "pitch_y_mm") < ay - 1e-9) err.push("addım aperturadan kiçik ola bilməz (linzalar üst-üstə düşür)");
      if (layout(cfg) === "each" && (v(cfg, "pitch_x_mm") < v(cfg, "rec_x_mm") - 1e-9 || v(cfg, "pitch_y_mm") < v(cfg, "rec_y_mm") - 1e-9))
        err.push("hər linzanın öz qəbuledicisi üçün addım qəbuledicidən kiçik ola bilməz");
      if (!(v(cfg, "eta_cell") > 0 && v(cfg, "eta_cell") < 1)) err.push("hüceyrə səmərəliliyi 0 ilə 1 arasında olmalıdır");
    }
    return { ok: !missing.length && !err.length, missing, errors: err };
  }

  function areas(cfg) {
    const [ax, ay] = aperture(cfg), n = v(cfg, "nx") * v(cfg, "ny");
    const a1 = (cfg.shape === "circle" && cfg.type !== "cpc" ? Math.PI / 4 * ax * ax : ax * ay) / 1e6;
    const r = (layout(cfg) === "shared" ? 1 : n) * v(cfg, "rec_x_mm") * v(cfg, "rec_y_mm") / 1e6;
    return { n, aperture_one_m2: a1, aperture_m2: n * a1, receiver_m2: r, C_g: n * a1 / r };
  }

  // ---------- transmission ----------
  function fresnelT(th, n) {
    th = Math.min(Math.max(th, 0), rad(89.999));
    if (th < 1e-9) return 1 - ((n - 1) / (n + 1)) ** 2;
    const tr = Math.asin(Math.sin(th) / n);
    const rs = (Math.sin(th - tr) / Math.sin(th + tr + 1e-300)) ** 2, rp = (Math.tan(th - tr) / Math.tan(th + tr + 1e-300)) ** 2;
    return 1 - 0.5 * (rs + rp);
  }
  function interp(x, xs, ys) {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
    let i = 1; while (xs[i] < x) i++;
    return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
  }
  function tau(cfg, theta) {
    const th = Math.abs(theta);
    if (cfg.type === "cpc") return v(cfg, "reflectivity") ** v(cfg, "n_reflections");
    const tab = v(cfg, "angle_table");
    if (tab && tab.length) {
      const s = [...tab].sort((a, b) => a[0] - b[0]);
      return interp(deg(th), s.map(r => r[0]), s.map(r => r[1]));
    }
    const n = v(cfg, "n_mat");
    return v(cfg, "tau0") * fresnelT(th, n) ** 2 / fresnelT(0, n) ** 2;
  }
  function tauDiffuse(cfg) {
    let s = 0, w = 0;
    for (let i = 0; i < 90; i++) { const th = rad(i + 0.5), wi = Math.sin(2 * th) * rad(1); s += tau(cfg, th) * wi; w += wi; }
    return s / w;
  }
  const modelLevel = cfg => (cfg.type !== "cpc" && v(cfg, "angle_table") && v(cfg, "angle_table").length ? LEVEL_TABLE : LEVEL_BASIC);

  // ---------- geometry ----------
  const ov1 = (a0, a1, b0, b1) => Math.max(0, Math.min(a1, b1) - Math.max(a0, b0));
  function ovCircleRect(cx, cy, r, x0, x1, y0, y1) {
    const lo = Math.max(cx - r, x0), hi = Math.min(cx + r, x1), dx = Math.max(0, hi - lo) / STRIPS;
    let tot = 0;
    for (let k = 0; k < STRIPS; k++) {
      const x = lo + (k + 0.5) * dx, half = Math.sqrt(Math.max(0, r * r - (x - cx) ** 2));
      tot += ov1(cy - half, cy + half, y0, y1) * dx;
    }
    return tot;
  }
  function spot(cfg, tx, ty) {
    const t = cfg.type, h = v(cfg, "h_mm"), [ax, ay] = aperture(cfg), b = 2 * h * Math.tan(rad(SUN_HALF_DEG)), f = v(cfg, "f_mm");
    let mx, my;
    if (t === "flat") { mx = my = 1; }
    else if (t === "linear_fresnel") {
      const fa = cfg.focus_axis || "y", tl = fa === "y" ? tx : ty, m = 1 - h / (f / Math.sqrt(1 + tl * tl));
      [mx, my] = fa === "y" ? [1, m] : [m, 1];
    } else { mx = my = 1 - h / f; }
    return { wx: Math.abs(mx) * ax + b, wy: Math.abs(my) * ay + b, sx: h * tx, sy: h * ty, circle: cfg.shape === "circle", blur: b, mx, my };
  }
  function overlap(sp, cx, cy, rx0, rx1, ry0, ry1) {
    const x = cx + sp.sx, y = cy + sp.sy;
    if (sp.circle) return ovCircleRect(x, y, sp.wx / 2, rx0, rx1, ry0, ry1);
    return ov1(x - sp.wx / 2, x + sp.wx / 2, rx0, rx1) * ov1(y - sp.wy / 2, y + sp.wy / 2, ry0, ry1);
  }
  const spotArea = sp => { if (!sp.circle) return sp.wx * sp.wy; const r = sp.wx / 2; return ovCircleRect(0, 0, r, -r, r, -r, r); };
  function lensCentres(cfg) {
    const nx = v(cfg, "nx"), ny = v(cfg, "ny"), px = v(cfg, "pitch_x_mm"), py = v(cfg, "pitch_y_mm"), out = [];
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) out.push([(i - (nx - 1) / 2) * px, (j - (ny - 1) / 2) * py]);
    return out;
  }
  function capture(cfg, tx, ty) {
    if (cfg.type === "cpc") {
      const thA = rad(v(cfg, "accept_deg")), fa = cfg.focus_axis || "y", [tt, tl] = fa === "y" ? [ty, tx] : [tx, ty];
      const a = (fa === "y" ? v(cfg, "rec_y_mm") : v(cfg, "rec_x_mm")) / 2, a2 = a / Math.sin(thA), H = (a + a2) / Math.tan(thA);
      const length = fa === "y" ? v(cfg, "rec_x_mm") : v(cfg, "rec_y_mm");
      return Math.abs(Math.atan(tt)) <= thA + 1e-12 ? Math.min(1, Math.max(0, 1 - H * Math.abs(tl) / length)) : 0;
    }
    const sp = spot(cfg, tx, ty), area = spotArea(sp), rx = v(cfg, "rec_x_mm"), ry = v(cfg, "rec_y_mm"), nx = v(cfg, "nx"), ny = v(cfg, "ny");
    let tot = 0;
    if (layout(cfg) === "shared") {
      for (const [cx, cy] of lensCentres(cfg)) tot += overlap(sp, cx, cy, -rx / 2, rx / 2, -ry / 2, ry / 2);
      return tot / (nx * ny * area);
    }
    const px = v(cfg, "pitch_x_mm"), py = v(cfg, "pitch_y_mm");
    const kxm = Math.min(nx - 1, Math.ceil(((sp.wx + rx) / 2 + Math.abs(sp.sx)) / px));
    const kym = Math.min(ny - 1, Math.ceil((((sp.circle ? sp.wx : sp.wy) + ry) / 2 + Math.abs(sp.sy)) / py));
    for (let kx = -kxm; kx <= kxm; kx++) for (let ky = -kym; ky <= kym; ky++) {
      const pairs = (nx - Math.abs(kx)) * (ny - Math.abs(ky)), ox = kx * px, oy = ky * py;
      tot += pairs * overlap(sp, 0, 0, ox - rx / 2, ox + rx / 2, oy - ry / 2, oy + ry / 2);
    }
    return tot / (nx * ny * area);
  }
  function peakBeamFactor(cfg, tx, ty) {
    if (cfg.type === "cpc") return null;
    const sp = spot(cfg, tx, ty), [ax, ay] = aperture(cfg), a1 = sp.circle ? Math.PI / 4 * ax * ax : ax * ay, dens = a1 / (sp.circle ? Math.PI / 4 * sp.wx ** 2 : sp.wx * sp.wy);
    const rx = v(cfg, "rec_x_mm"), ry = v(cfg, "rec_y_mm"), cen = lensCentres(cfg);
    let c0 = [0, 0];
    if (layout(cfg) === "each") c0 = cen.reduce((b, c) => {
      const kb = [Math.abs(b[0]) + Math.abs(b[1]), b[1], b[0]], kc = [Math.abs(c[0]) + Math.abs(c[1]), c[1], c[0]];
      for (let i = 0; i < 3; i++) { if (kc[i] < kb[i]) return c; if (kc[i] > kb[i]) return b; } return b;
    });
    let best = 0;
    for (let j = 0; j < RASTER; j++) for (let i = 0; i < RASTER; i++) {
      const X = c0[0] - rx / 2 + (i + 0.5) * rx / RASTER, Y = c0[1] - ry / 2 + (j + 0.5) * ry / RASTER;
      let acc = 0;
      for (const [cx, cy] of cen) {
        const x = cx + sp.sx, y = cy + sp.sy;
        const inside = sp.circle ? (X - x) ** 2 + (Y - y) ** 2 <= (sp.wx / 2) ** 2 : Math.abs(X - x) <= sp.wx / 2 && Math.abs(Y - y) <= sp.wy / 2;
        if (inside) acc += dens;
      }
      if (acc > best) best = acc;
    }
    return best;
  }

  // ---------- electrical / thermal ----------
  function tCell(e, ta, ws, kHs = 1) { const q = e / kHs; return ta + q * Math.exp(SAPM[0] + SAPM[1] * ws) + q / 1000 * SAPM[2]; }
  function iamGlass(theta) {
    const n = 1.526, K = 4, L = 0.002;
    const tr = t => { const r = Math.asin(Math.sin(t) / n), rs = (Math.sin(r - t) / Math.sin(r + t)) ** 2, rp = (Math.tan(r - t) / Math.tan(r + t)) ** 2;
                      return Math.exp(-K * L / Math.cos(r)) * (1 - 0.5 * (rs + rp)); };
    const th = Math.min(Math.max(Math.abs(theta), 1e-9), rad(89.999));
    return tr(th) / tr(1e-9);
  }
  let IAM_D = null;
  function iamGlassDiffuse() {
    if (IAM_D != null) return IAM_D;
    let s = 0, w = 0; for (let i = 0; i < 90; i++) { const th = rad(i + 0.5), wi = Math.sin(2 * th); s += iamGlass(th) * wi; w += wi; }
    return (IAM_D = s / w);
  }
  function pvDc(eOn, area, cfg, ta, ws, kHs = 1) {
    const tc = tCell(eOn, ta, ws, kHs);
    return [Math.max(0, eOn * area * v(cfg, "eta_cell") * (1 + v(cfg, "gamma_per_K") * (tc - 25)) * v(cfg, "k_el")), tc];
  }

  function optical(cfg, eb, ed, tx, ty, A = areas(cfg), td = cfg.type === "cpc" ? tau(cfg, 0) : tauDiffuse(cfg)) {
    const th = Math.atan(Math.hypot(tx, ty)), tb = tau(cfg, th), cap = capture(cfg, tx, ty);
    const pb = eb * A.aperture_m2, pd = ed * A.aperture_m2, dOn = ed * td * Math.min(A.aperture_m2, A.receiver_m2);
    const on = pb * tb * cap + dOn, trans = pb * tb + pd * td;
    return { P_in_W: pb + pd, P_beam_in_W: pb, optical_loss_W: pb * (1 - tb) + pd * (1 - td), on_receiver_W: on, off_receiver_W: trans - on,
             tau_beam: tb, tau_diffuse: td, capture_beam: cap, E_rec_mean_Wm2: on / A.receiver_m2 };
  }

  function lensGeometry(f, ax, ay, cylindrical = false) {   // = optics.lens_geometry
    const [axis, a] = cylindrical ? ["y", ay] : ay >= ax ? ["y", ay] : ["x", ax];
    const out = { axis, aperture_mm: a, aperture_x_mm: ax, aperture_y_mm: ay, cylindrical, f_mm: null, f_number: null, edge_angle_deg: 0, corner_angle_deg: null, diagonal_mm: null };
    if (!isFinite(f)) return out;
    const F = Math.abs(f);
    out.f_mm = f; out.f_number = F / a; out.edge_angle_deg = deg(Math.atan(a / 2 / F));
    if (!cylindrical) { const d = Math.hypot(ax, ay); out.diagonal_mm = d; out.corner_angle_deg = deg(Math.atan(d / 2 / F)); }
    return out;
  }
  const label = t => (t <= 10 ? "yaxşı" : t <= 20 ? "orta" : "aşağı");
  function validity(cfg, thetaInc = 0) {
    const t = cfg.type, inc = deg(Math.abs(thetaInc)), out = { incidence_deg: inc, incidence_label: label(inc) };
    if (t === "flat" || t === "cpc") return { ...out, edge: null, paraxial: null, above_warn_limit: false, reliability: null, coarse: false };
    const [ax, ay] = aperture(cfg), fa = cfg.focus_axis || "y";
    let g;
    if (t === "linear_fresnel") { g = lensGeometry(v(cfg, "f_mm"), fa === "x" ? ay : ax, fa === "x" ? ax : ay, true); g.axis = fa; }
    else { g = lensGeometry(v(cfg, "f_mm"), ax, ay); if (cfg.shape === "circle") Object.assign(g, { axis: "d", corner_angle_deg: null, diagonal_mm: null }); }
    const lab = label(g.edge_angle_deg), rank = { "yaxşı": 0, "orta": 1, "aşağı": 2 };
    const worst = rank[lab] >= rank[out.incidence_label] ? lab : out.incidence_label;
    const reliability = { "yaxşı": "yüksək", "orta": "orta", "aşağı": "aşağı" }[worst];
    return { ...out, edge: g, paraxial: lab, above_warn_limit: g.edge_angle_deg > PARAXIAL_WARN_DEG, reliability, coarse: reliability === "aşağı" };
  }

  function instant(cfg, { dni = 1000, diff = 0, theta_x_deg = 0, theta_y_deg = 0, ta = 25, ws = 1 } = {}) {
    const val = validate(cfg);
    if (!val.ok) return { ok: false, ...val };
    const tx = Math.tan(rad(theta_x_deg)), ty = Math.tan(rad(theta_y_deg)), cos = 1 / Math.sqrt(1 + tx * tx + ty * ty), eb = dni * cos;
    const A = areas(cfg), o = optical(cfg, eb, diff, tx, ty, A), pk = peakBeamFactor(cfg, tx, ty), td = o.tau_diffuse;
    const peak = pk == null ? null : eb * o.tau_beam * pk + diff * td * Math.min(A.aperture_m2, A.receiver_m2) / A.receiver_m2;
    const [dc, tc] = pvDc(o.E_rec_mean_Wm2, A.receiver_m2, cfg, ta, ws, v(cfg, "k_hs"));
    const th = Math.atan(Math.hypot(tx, ty)), ePlain = eb * iamGlass(th) + diff * iamGlassDiffuse();
    const [dcA, tA] = pvDc(ePlain, A.aperture_m2, cfg, ta, ws), [dcB, tB] = pvDc(ePlain, A.receiver_m2, cfg, ta, ws);
    const Pin = o.P_in_W, sh = k => (Pin > 0 ? o[k] / Pin : null);
    return { ok: true, level: modelLevel(cfg), areas: A, ...o, theta_inc_deg: deg(th), E_beam_plane_Wm2: eb,
      shares: { optical_loss_W: sh("optical_loss_W"), on_receiver_W: sh("on_receiver_W"), off_receiver_W: sh("off_receiver_W") },
      E_rec_peak_Wm2: peak, t_cell_C: tc, t_cell_warning: tc > T_CELL_LIMIT_C, dc_W: dc, system_eff: Pin > 0 ? dc / Pin : null,
      validity: validity(cfg, th),
      compare_A: { label: "eyni işıqtoplama sahəsi", area_optic_m2: A.aperture_m2, area_plain_m2: A.aperture_m2, plain_dc_W: dcA, optic_dc_W: dc,
                   delta_W: dc - dcA, ratio: dcA > 0 ? dc / dcA : null, plain_t_cell_C: tA, optic_W_per_m2: dc / A.aperture_m2, plain_W_per_m2: dcA / A.aperture_m2 },
      compare_B: { label: "eyni fotoelement sahəsi", cell_area_m2: A.receiver_m2, collect_optic_m2: A.aperture_m2, collect_plain_m2: A.receiver_m2,
                   plain_dc_W: dcB, optic_dc_W: dc, ratio: dcB > 0 ? dc / dcB : null, plain_t_cell_C: tB } };
  }

  function analytic(cfg, dni = 1000) {
    const A = areas(cfg), one = A.aperture_one_m2 * dni * v(cfg, "eta_opt_eff") * v(cfg, "eta_cell") * v(cfg, "k_th") * v(cfg, "k_el");
    return { per_unit_W: one, total_W: one * A.n, n: A.n, aperture_one_m2: A.aperture_one_m2, aperture_m2: A.aperture_m2, C_g: A.C_g };
  }

  const az = x => String(+x.toPrecision(6)).replace(".", ",").replace("-", "−");
  function assumptions(cfg, mount) {
    const out = [];
    if (cfg.type === "cpc") out.push(`qəbul bucağı və əks olunma: ${cfg.params.accept_deg.status} / ${cfg.params.reflectivity.status}`);
    else if (!(v(cfg, "angle_table") || []).length) out.push("ötürmənin bucaqdan asılılığı fərziyyədir (nominal τ0 + iki Fresnel səthi), ölçülmüş deyil");
    out.push(cfg.type !== "cpc" ? "qəbul bucağı ölçülməyib: həndəsi ləkə modelindən gəlir" : "CPC ideal fərz olunur (kəsilmə yoxdur)");
    out.push(`hüceyrə temperaturu: SAPM açıq dayaq modeli, istilik ötürən səth əmsalı k = ${az(v(cfg, "k_hs"))} (${cfg.params.k_hs.status})`);
    out.push("qəbulediciyə düşən səpələnmiş işıq étendue həddi ilə yuxarıdan qiymətləndirilir");
    if (mount === "2axis") out.push(`izləmə: yönəltmə xətası ${az(v(cfg, "track_err_deg"))}°, sərf ${az(v(cfg, "drive_W"))} W + ${az(v(cfg, "controller_W"))} W (${cfg.params.drive_W.status})`);
    return out;
  }

  function annual(cfg, h, mount = cfg.mount || "fixed") {
    const val = validate(cfg);
    if (!val.ok) return { ok: false, ...val };
    const A = areas(cfg), td = cfg.type === "cpc" ? tau(cfg, 0) : tauDiffuse(cfg), kHs = v(cfg, "k_hs"), step = h.step_h;
    const err = Math.tan(rad(v(cfg, "track_err_deg"))), fa = cfg.focus_axis || "y";
    const sum = { g: 0, a: 0, gA: 0, gB: 0, Pin: 0, loss: 0, on: 0, off: 0 };
    let tmax = -273, hot = 0;
    for (let i = 0; i < h.beam.length; i++) {
      const sun = h.sun[i] > 0;
      let eb, ed, tx, ty, ep, aux;
      if (mount === "2axis") {
        eb = h.t_dnicos[i]; ed = Math.max(0, h.t_glob[i] - h.t_dnicos[i]); tx = fa === "x" ? err : 0; ty = fa === "y" ? err : 0;
        ep = h.t_beam[i] + h.t_diff[i]; aux = v(cfg, "drive_W") * (sun ? 1 : 0) + v(cfg, "controller_W");
      } else { eb = h.beam[i]; ed = h.sky[i] + h.ground[i]; tx = h.tx[i]; ty = h.ty[i]; ep = h.f_beam[i] + h.f_diff[i]; aux = 0; }
      if (!sun) { eb = 0; ed = 0; }
      sum.a += aux;
      const [dA] = pvDc(ep, A.aperture_m2, cfg, h.ta[i], h.ws[i]), [dB] = pvDc(ep, A.receiver_m2, cfg, h.ta[i], h.ws[i]);
      sum.gA += dA; sum.gB += dB;
      if (eb === 0 && ed === 0) { const [d, tc] = pvDc(0, A.receiver_m2, cfg, h.ta[i], h.ws[i], kHs); sum.g += d; if (sun && tc > tmax) tmax = tc; continue; }
      const o = optical(cfg, eb, ed, tx, ty, A, td);
      const [d, tc] = pvDc(o.E_rec_mean_Wm2, A.receiver_m2, cfg, h.ta[i], h.ws[i], kHs);
      sum.g += d; sum.Pin += o.P_in_W; sum.loss += o.optical_loss_W; sum.on += o.on_receiver_W; sum.off += o.off_receiver_W;
      if (sun) { if (tc > tmax) tmax = tc; if (tc > T_CELL_LIMIT_C) hot++; }
    }
    const k = x => x * step / 1000, pct = (a, b) => (b > 0 ? 100 * (a / b - 1) : null), rat = (a, b) => (b > 0 ? a / b : null);
    const res = { gross_kWh: k(sum.g), aux_kWh: k(sum.a), net_kWh: k(sum.g) - k(sum.a) };
    const resA = { gross_kWh: k(sum.gA), aux_kWh: k(sum.a), net_kWh: k(sum.gA) - k(sum.a) };
    const resB = { gross_kWh: k(sum.gB), aux_kWh: k(sum.a), net_kWh: k(sum.gB) - k(sum.a) };
    return { ok: true, mount, level: modelLevel(cfg), areas: A, optic: res,
      optics_kWh: { P_in_W: k(sum.Pin), optical_loss_W: k(sum.loss), on_receiver_W: k(sum.on), off_receiver_W: k(sum.off) },
      max_t_cell_C: tmax, hours_above_limit: hot, t_limit_C: T_CELL_LIMIT_C,
      compare_A: { plain: resA, area_m2: A.aperture_m2, delta_gross_pct: pct(res.gross_kWh, resA.gross_kWh), delta_pct: pct(res.net_kWh, resA.net_kWh) },
      compare_B: { plain: resB, cell_area_m2: A.receiver_m2, collect_optic_m2: A.aperture_m2, collect_plain_m2: A.receiver_m2,
                   ratio_gross: rat(res.gross_kWh, resB.gross_kWh), ratio: rat(res.net_kWh, resB.net_kWh) },
      assumptions: assumptions(cfg, mount) };
  }

  return { SUN_HALF_DEG, MAX_LENSES, T_CELL_LIMIT_C, STATUSES, IST, OLC, FRZ, TYPES, LEVEL_BASIC, LEVEL_TABLE, CATALOG, preset, v, validate, layout,
           aperture, areas, tau, tauDiffuse, modelLevel, spot, capture, peakBeamFactor, lensCentres, optical, instant, analytic, validity, annual, assumptions };
})();
if (typeof module !== "undefined") module.exports = UOptics;
