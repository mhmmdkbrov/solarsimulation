"""Universal optics over a receiver: catalogue, geometric model, comparisons with a bare PV baseline.

Flow (same in ``simulator/uoptics.js``): choose an optic → enter its parameters → choose receiver and mounting →
compare with the bare PV baseline.

Level of the model ("ilkin həndəsi hesab")
-----------------------------------------
* Thin, paraxial optics, uniform spot (geometric optics), sun disk ±0.2665°. No surface profile is used.
* Linear Fresnel: focuses along one axis only. The strip width is |1 − h/(f·cos θ_l)|·a + blur, where θ_l is the
  incidence angle along the line (the focal line moves closer to the lens), its centre is shifted by h·tan θ_t, and
  along the line the light is shifted by h·tan θ_l (end losses).
* Point focus (Fresnel, convex lens, negative lens): 2-D spot |1 − h/f|·a + blur, rectangle or circle, shifted by
  h·tan θ. Negative lens: f < 0, the spot is larger than the aperture (spreading). Flat cover: m = 1.
* CPC (reflector, separate model): ideal 2-D CPC, light inside the acceptance half-angle reaches the receiver after
  ρ^n reflections, outside it is rejected; end losses along the trough.
* Transmission: τ0 is a nominal value at normal incidence. Unless a measured angle–transmission table is given, the
  angle dependence is assumed from two Fresnel surfaces (unpolarised) of index n — it is not presented as measured.
* Diffuse light on the receiver is bounded by étendue: ≤ E_d·τ_d·min(A_aperture, A_receiver) (isotropic radiance).
* Geometric concentration C_g = A_aperture / A_receiver (active). The optical power on the receiver is computed once
  from the aperture power; it is never multiplied by C_g again.

Every model returns the same quantities: incident power, optical transmission loss, share on the receiver, share
that misses it, mean (and, where defined, peak local) irradiance on the receiver.
"""
from __future__ import annotations

import copy
import math

import numpy as np

from . import optics as O

SUN_HALF_DEG = 0.2665
SAPM = (-3.47, -0.0594, 3.0)            # open rack, glass/glass (same as the module model)
MAX_LENSES = 400
T_CELL_LIMIT_C = 85.0                   # warning above this cell temperature (typical datasheet operating limit)
RASTER = 60                             # grid per receiver for the peak irradiance
STRIPS = 64                             # midpoint strips for circle ∩ rectangle
IST, OLC, FRZ = "istehsalçı məlumatı", "ölçülüb", "fərziyyə"
STATUSES = (IST, OLC, FRZ)
TYPES = {"linear_fresnel": "xətti Fresnel linzası", "point_fresnel": "nöqtə fokuslu Fresnel linzası",
         "convex": "qabarıq linza", "negative": "mənfi dioptriyalı (səpələyici) linza", "flat": "düz örtük",
         "cpc": "CPC reflektoru (birləşən parabolik konsentrator)"}
LEVEL_BASIC = "ilkin həndəsi hesab"
LEVEL_TABLE = "ölçülmüş bucaq–ötürmə cədvəli ilə həndəsi hesab"


def P(value, status=FRZ, note=""):
    return {"value": value, "status": status, "note": note}


# ------------------------------------------------------------------------------------------------------- catalogue
_COMMON = {
    "eta_cell": P(0.22, FRZ, "hüceyrənin STC səmərəliliyi"),
    "gamma_per_K": P(-0.0035, FRZ, "gücün temperatur əmsalı"),
    "k_el": P(0.98, FRZ, "elektrik əmsalı (naqil, uyğunsuzluq)"),
    "k_hs": P(1.0, FRZ, "istilik ötürən səth / qəbuledici sahəsi; 1 = adi modul kimi soyuma"),
    "k_th": P(0.95, FRZ, "analitik baza üçün sabit istilik əmsalı"),
    "track_err_deg": P(0.1, FRZ, "2 oxlu izləmədə sabit yönəltmə xətası (fokuslanan ox üzrə)"),
    "drive_W": P(4.0, FRZ, "izləmə mühərriki, gündüz, hər izləyici üçün"),
    "controller_W": P(0.5, FRZ, "idarəetmə, 24 saat"),
}

CATALOG = {
    "lfs150150": {
        "name": "LFS150150 xətti Fresnel (Knight Optical)", "type": "linear_fresnel", "shape": "rect", "focus_axis": "y",
        "layout": "each", "mount": "fixed",
        "source": "https://knightoptical.com/stock/default/lenses/fresnel-lenses/reverse-configuration-fresnel-lenses.html",
        "source_note": "Kataloq: f = 150 mm (±5%), apertura 150 × 500 mm, faset eni 0,3 mm, qalınlıq 2 mm, PMMA, "
                       "düz tərəf Günəşə. Ötürmə rəqəmi verilmir.",
        "params": {
            "ap_x_mm": P(500, IST, "uzunluq (xətt boyunca, yivlər bu oxa paraleldir)"),
            "ap_y_mm": P(150, IST, "fokuslanan ox üzrə en"),
            "f_mm": P(150, IST, "±5%"),
            "thickness_mm": P(2, IST, ""),
            "n_mat": P(1.49, FRZ, "PMMA üçün tipik sındırma əmsalı (material istehsalçıdan: PMMA)"),
            "tau0": P(0.92, FRZ, "istehsalçı ötürmə vermir; PMMA üçün tipik normal düşmə dəyəri"),
            "angle_table": P(None, FRZ, "ölçülmüş bucaq–ötürmə cədvəli yoxdur"),
            "rec_x_mm": P(500, FRZ, "Rev B qəbuledicisi: 500 × 75 mm"),
            "rec_y_mm": P(75, FRZ, "Rev B qəbuledicisi: 500 × 75 mm"),
            "h_mm": P(75, FRZ, "zolaq eni = qəbuledici eni olan məsafə (fokusdan əvvəl)"),
            "nx": P(1, FRZ, ""), "ny": P(18, FRZ, "Rev B: 18 linza"),
            "pitch_x_mm": P(500, FRZ, ""), "pitch_y_mm": P(150, FRZ, "linzalar arası boşluq yoxdur"),
            "eta_opt_eff": P(0.85, FRZ, "Rev B sadə hesabının effektiv optik payı"),
            **copy.deepcopy(_COMMON)},
    },
    "point_fresnel": {
        "name": "Nöqtə fokuslu Fresnel (ümumi şablon)", "type": "point_fresnel", "shape": "rect", "focus_axis": "y",
        "layout": "each", "mount": "2axis", "source": None, "source_note": "Şablon: bütün dəyərlər fərziyyədir.",
        "params": {
            "ap_x_mm": P(300, FRZ, ""), "ap_y_mm": P(300, FRZ, ""), "f_mm": P(300, FRZ, ""),
            "thickness_mm": P(3, FRZ, ""), "n_mat": P(1.49, FRZ, "PMMA"),
            "tau0": P(0.85, FRZ, "Fresnel fasetlərinin itkisi daxil, tipik"),
            "angle_table": P(None, FRZ, ""),
            "rec_x_mm": P(30, FRZ, ""), "rec_y_mm": P(30, FRZ, ""), "h_mm": P(300, FRZ, "fokusda"),
            "nx": P(2, FRZ, ""), "ny": P(2, FRZ, ""), "pitch_x_mm": P(300, FRZ, ""), "pitch_y_mm": P(300, FRZ, ""),
            "eta_opt_eff": P(0.85, FRZ, ""), **copy.deepcopy(_COMMON)},
    },
    "convex": {
        "name": "Qabarıq linza (şablon, +5 D)", "type": "convex", "shape": "circle", "focus_axis": "y",
        "layout": "each", "mount": "2axis", "source": None, "source_note": "Şablon: bütün dəyərlər fərziyyədir.",
        "params": {
            "ap_x_mm": P(100, FRZ, "diametr"), "ap_y_mm": P(100, FRZ, "dairəvi apertura: diametr"),
            "f_mm": P(200, FRZ, "+5 D"), "thickness_mm": P(8, FRZ, ""), "n_mat": P(1.5, FRZ, "şüşə"),
            "tau0": P(0.92, FRZ, "iki səthdə əks olunma, örtüksüz"), "angle_table": P(None, FRZ, ""),
            "rec_x_mm": P(50, FRZ, ""), "rec_y_mm": P(50, FRZ, ""), "h_mm": P(100, FRZ, "fokusun yarısı"),
            "nx": P(1, FRZ, ""), "ny": P(1, FRZ, ""), "pitch_x_mm": P(100, FRZ, ""), "pitch_y_mm": P(100, FRZ, ""),
            "eta_opt_eff": P(0.92, FRZ, ""), **copy.deepcopy(_COMMON)},
    },
    "negative": {
        "name": "Mənfi linza (şablon, −5 D)", "type": "negative", "shape": "circle", "focus_axis": "y",
        "layout": "each", "mount": "fixed", "source": None, "source_note": "Şablon: bütün dəyərlər fərziyyədir.",
        "params": {
            "ap_x_mm": P(100, FRZ, "diametr"), "ap_y_mm": P(100, FRZ, "dairəvi apertura: diametr"),
            "f_mm": P(-200, FRZ, "−5 D, xəyali fokus"), "thickness_mm": P(4, FRZ, ""), "n_mat": P(1.5, FRZ, ""),
            "tau0": P(0.92, FRZ, ""), "angle_table": P(None, FRZ, ""),
            "rec_x_mm": P(100, FRZ, ""), "rec_y_mm": P(100, FRZ, ""), "h_mm": P(50, FRZ, ""),
            "nx": P(1, FRZ, ""), "ny": P(1, FRZ, ""), "pitch_x_mm": P(100, FRZ, ""), "pitch_y_mm": P(100, FRZ, ""),
            "eta_opt_eff": P(0.92, FRZ, ""), **copy.deepcopy(_COMMON)},
    },
    "flat": {
        "name": "Düz örtük (şablon)", "type": "flat", "shape": "rect", "focus_axis": "y",
        "layout": "each", "mount": "fixed", "source": None, "source_note": "Şablon: bütün dəyərlər fərziyyədir.",
        "params": {
            "ap_x_mm": P(1000, FRZ, ""), "ap_y_mm": P(1000, FRZ, ""), "f_mm": P(None, FRZ, "fokus yoxdur"),
            "thickness_mm": P(3, FRZ, ""), "n_mat": P(1.5, FRZ, ""), "tau0": P(0.92, FRZ, ""),
            "angle_table": P(None, FRZ, ""),
            "rec_x_mm": P(1000, FRZ, ""), "rec_y_mm": P(1000, FRZ, ""), "h_mm": P(5, FRZ, ""),
            "nx": P(1, FRZ, ""), "ny": P(1, FRZ, ""), "pitch_x_mm": P(1000, FRZ, ""), "pitch_y_mm": P(1000, FRZ, ""),
            "eta_opt_eff": P(0.92, FRZ, ""), **copy.deepcopy(_COMMON)},
    },
    "cpc": {
        "name": "CPC reflektoru (xətti, şablon)", "type": "cpc", "shape": "rect", "focus_axis": "y",
        "layout": "each", "mount": "fixed", "source": None,
        "source_note": "Şablon: ideal 2D CPC, apertura qəbul bucağından və qəbuledicidən hesablanır.",
        "params": {
            "accept_deg": P(30, FRZ, "qəbul yarım-bucağı"), "reflectivity": P(0.90, FRZ, ""),
            "n_reflections": P(1.0, FRZ, "orta əks olunma sayı"),
            "rec_x_mm": P(500, FRZ, "uzunluq"), "rec_y_mm": P(50, FRZ, "fokuslanan ox üzrə en"),
            "nx": P(1, FRZ, ""), "ny": P(10, FRZ, ""), "pitch_x_mm": P(500, FRZ, ""), "pitch_y_mm": P(100, FRZ, ""),
            "eta_opt_eff": P(0.81, FRZ, ""), **copy.deepcopy(_COMMON)},
    },
}

for _k, _hs, _note in (("lfs150150", 2.0, "istilik ötürən səth aperturaya bərabər (C = 2)"),
                       ("point_fresnel", 100.0, "passiv radiator aperturaya bərabər (C = 100)"),
                       ("convex", 3.0, "istilik ötürən səth təxminən aperturaya bərabər"),
                       ("cpc", 2.0, "istilik ötürən səth aperturaya bərabər (C = 2)")):
    CATALOG[_k]["params"]["k_hs"] = P(_hs, FRZ, _note)

REQUIRED = {
    "linear_fresnel": ("ap_x_mm", "ap_y_mm", "f_mm", "tau0", "n_mat"),
    "point_fresnel": ("ap_x_mm", "ap_y_mm", "f_mm", "tau0", "n_mat"),
    "convex": ("ap_x_mm", "ap_y_mm", "f_mm", "tau0", "n_mat"),
    "negative": ("ap_x_mm", "ap_y_mm", "f_mm", "tau0", "n_mat"),
    "flat": ("ap_x_mm", "ap_y_mm", "tau0", "n_mat"),
    "cpc": ("accept_deg", "reflectivity", "n_reflections"),
}
REQUIRED_RX = ("rec_x_mm", "rec_y_mm", "nx", "ny", "pitch_x_mm", "pitch_y_mm", "eta_cell", "gamma_per_K", "k_el", "k_hs")


def preset(key: str) -> dict:
    return copy.deepcopy(CATALOG[key])


def v(cfg, name, default=None):
    p = cfg["params"].get(name)
    return default if p is None or p.get("value") is None else p["value"]


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate(cfg) -> dict:
    """Missing and inconsistent inputs. A result is only computed when ``ok``."""
    t = cfg.get("type")
    if t not in TYPES:
        return {"ok": False, "missing": ["type"], "errors": ["optika tipi seçilməyib"]}
    need = list(REQUIRED[t]) + list(REQUIRED_RX) + ([] if t == "cpc" else ["h_mm"])
    missing = [k for k in dict.fromkeys(need) if not _num(v(cfg, k))]
    err = []
    if not missing:
        if t not in ("cpc",):
            if v(cfg, "ap_x_mm") <= 0 or v(cfg, "ap_y_mm") <= 0:
                err.append("apertura ölçüləri müsbət olmalıdır")
            if not 0 < v(cfg, "tau0") <= 1:
                err.append("ötürmə 0 ilə 1 arasında olmalıdır")
            if v(cfg, "h_mm") <= 0:
                err.append("linza–qəbuledici məsafəsi müsbət olmalıdır")
        if t in ("linear_fresnel", "point_fresnel", "convex") and v(cfg, "f_mm") <= 0:
            err.append("toplayıcı optikanın fokus məsafəsi müsbət olmalıdır")
        if t == "negative" and v(cfg, "f_mm") >= 0:
            err.append("mənfi linzanın fokus məsafəsi mənfi olmalıdır")
        if t == "cpc" and not 0 < v(cfg, "accept_deg") < 90:
            err.append("CPC qəbul bucağı 0° ilə 90° arasında olmalıdır")
        if v(cfg, "rec_x_mm") <= 0 or v(cfg, "rec_y_mm") <= 0:
            err.append("qəbuledicinin ölçüləri müsbət olmalıdır")
        nx, ny = v(cfg, "nx"), v(cfg, "ny")
        if nx < 1 or ny < 1 or nx != int(nx) or ny != int(ny) or nx * ny > MAX_LENSES:
            err.append(f"linza sayı tam ədəd olmalıdır, 1 … {MAX_LENSES}")
        ax, ay = aperture_mm(cfg)
        if v(cfg, "pitch_x_mm") < ax - 1e-9 or v(cfg, "pitch_y_mm") < ay - 1e-9:
            err.append("addım aperturadan kiçik ola bilməz (linzalar üst-üstə düşür)")
        if layout(cfg) == "each" and (v(cfg, "pitch_x_mm") < v(cfg, "rec_x_mm") - 1e-9 or v(cfg, "pitch_y_mm") < v(cfg, "rec_y_mm") - 1e-9):
            err.append("hər linzanın öz qəbuledicisi üçün addım qəbuledicidən kiçik ola bilməz")
        if not 0 < v(cfg, "eta_cell") < 1:
            err.append("hüceyrə səmərəliliyi 0 ilə 1 arasında olmalıdır")
    return {"ok": not missing and not err, "missing": missing, "errors": err}


def layout(cfg):
    return "each" if cfg["type"] == "cpc" else cfg.get("layout", "each")


def aperture_mm(cfg):
    """Aperture of one optic (x, y) in the mount frame. CPC: derived from the receiver and the acceptance angle."""
    if cfg["type"] == "cpc":
        s = math.sin(math.radians(v(cfg, "accept_deg")))
        rx, ry = v(cfg, "rec_x_mm"), v(cfg, "rec_y_mm")
        return (rx / s, ry) if cfg.get("focus_axis", "y") == "x" else (rx, ry / s)
    return v(cfg, "ap_x_mm"), v(cfg, "ap_y_mm")


def areas(cfg) -> dict:
    ax, ay = aperture_mm(cfg)
    n = int(v(cfg, "nx")) * int(v(cfg, "ny"))
    a1 = (math.pi / 4 * ax * ax if cfg.get("shape") == "circle" and cfg["type"] != "cpc" else ax * ay) / 1e6
    if layout(cfg) == "shared":
        r = v(cfg, "rec_x_mm") * v(cfg, "rec_y_mm") / 1e6
    else:
        r = n * v(cfg, "rec_x_mm") * v(cfg, "rec_y_mm") / 1e6
    return {"n": n, "aperture_one_m2": a1, "aperture_m2": n * a1, "receiver_m2": r, "C_g": n * a1 / r}


# ---------------------------------------------------------------------------------------------- transmission τ(θ)
def _fresnel_t(theta, n):
    """Unpolarised transmittance of one air → n surface."""
    th = np.clip(np.asarray(theta, float), 0, np.radians(89.999))
    tr = np.arcsin(np.sin(th) / n)
    rs = (np.sin(th - tr) / np.sin(th + tr + 1e-300)) ** 2
    rp = (np.tan(th - tr) / np.tan(th + tr + 1e-300)) ** 2
    r0 = ((n - 1) / (n + 1)) ** 2
    r = np.where(th < 1e-9, r0, 0.5 * (rs + rp))
    return 1 - r


def tau(cfg, theta):
    """Transmission at incidence θ [rad]. Measured table if given, else τ0 × (two Fresnel surfaces)/(same at 0)."""
    th = np.abs(np.asarray(theta, float))
    if cfg["type"] == "cpc":
        return np.full_like(th, v(cfg, "reflectivity") ** v(cfg, "n_reflections"))
    tab = v(cfg, "angle_table")
    if tab:
        a = np.array([r[0] for r in tab], float)
        t = np.array([r[1] for r in tab], float)
        o = np.argsort(a)
        return np.interp(np.degrees(th), a[o], t[o])
    n = v(cfg, "n_mat")
    t0 = _fresnel_t(0.0, n) ** 2
    return v(cfg, "tau0") * _fresnel_t(th, n) ** 2 / t0


def tau_diffuse(cfg):
    """Cosine-weighted hemispherical average of τ(θ) (isotropic radiance), midpoint rule, 90 bins."""
    th = np.radians(np.arange(90) + 0.5)
    w = np.sin(2 * th) * np.radians(1.0)
    return float((tau(cfg, th) * w).sum() / w.sum())


def model_level(cfg):
    return LEVEL_TABLE if (cfg["type"] != "cpc" and v(cfg, "angle_table")) else LEVEL_BASIC


# -------------------------------------------------------------------------------------------------- geometry
def _ov1(a0, a1, b0, b1):
    return np.clip(np.minimum(a1, b1) - np.maximum(a0, b0), 0, None)


def _ov_circle_rect(cx, cy, r, x0, x1, y0, y1):
    """Area of circle (cx, cy, r) ∩ rectangle: midpoint strips over the common x range. Arrays broadcast."""
    lo, hi = np.maximum(cx - r, x0), np.minimum(cx + r, x1)
    dx = np.clip(hi - lo, 0, None) / STRIPS
    tot = 0.0
    for k in range(STRIPS):
        x = lo + (k + 0.5) * dx
        half = np.sqrt(np.clip(r * r - (x - cx) ** 2, 0, None))
        tot = tot + _ov1(cy - half, cy + half, y0, y1) * dx
    return tot


def spot(cfg, tx, ty):
    """Spot of one optic on the receiver plane for incidence slopes (tx, ty): size and centre shift [mm]."""
    t = cfg["type"]
    tx, ty = np.asarray(tx, float), np.asarray(ty, float)
    h = v(cfg, "h_mm")
    ax, ay = aperture_mm(cfg)
    b = 2 * h * math.tan(math.radians(SUN_HALF_DEG))
    f = v(cfg, "f_mm")
    if t == "flat":
        mx = my = np.ones_like(tx)
    elif t == "linear_fresnel":
        fa = cfg.get("focus_axis", "y")
        tl = tx if fa == "y" else ty
        m = 1 - h / (f / np.sqrt(1 + tl * tl))            # focal line closer at longitudinal incidence: f·cos θ_l
        mx, my = (np.ones_like(tx), m) if fa == "y" else (m, np.ones_like(tx))
    else:
        mx = my = np.full_like(tx, 1 - h / f)
    wx, wy = np.abs(mx) * ax + b, np.abs(my) * ay + b
    return {"wx": wx, "wy": wy, "sx": h * tx, "sy": h * ty, "circle": cfg.get("shape") == "circle", "blur": b}


def _overlap(sp, cx, cy, rx0, rx1, ry0, ry1):
    """Area of the spot centred at (cx + sx, cy + sy) inside a receiver rectangle [mm²]."""
    x, y = cx + sp["sx"], cy + sp["sy"]
    if sp["circle"]:
        return _ov_circle_rect(x, y, sp["wx"] / 2, rx0, rx1, ry0, ry1)
    return _ov1(x - sp["wx"] / 2, x + sp["wx"] / 2, rx0, rx1) * _ov1(y - sp["wy"] / 2, y + sp["wy"] / 2, ry0, ry1)


def _spot_area(sp):
    """Spot area with the same quadrature as the overlap (a spot fully on the receiver gives exactly 1)."""
    if sp["circle"]:
        r = sp["wx"] / 2
        return _ov_circle_rect(0.0, 0.0, r, -r, r, -r, r)
    return sp["wx"] * sp["wy"]


def lens_centres(cfg):
    nx, ny = int(v(cfg, "nx")), int(v(cfg, "ny"))
    px, py = v(cfg, "pitch_x_mm"), v(cfg, "pitch_y_mm")
    return [((i - (nx - 1) / 2) * px, (j - (ny - 1) / 2) * py) for j in range(ny) for i in range(nx)]


def capture(cfg, tx, ty):
    """Fraction of the transmitted beam that lands on the receivers (whole array, finite number of lenses, real
    array edges). Separate receivers: light of one lens may also land on a neighbour's receiver."""
    tx, ty = np.atleast_1d(np.asarray(tx, float)), np.atleast_1d(np.asarray(ty, float))
    if cfg["type"] == "cpc":
        th_a = math.radians(v(cfg, "accept_deg"))
        fa = cfg.get("focus_axis", "y")
        tt, tl = (ty, tx) if fa == "y" else (tx, ty)
        a = (v(cfg, "rec_y_mm") if fa == "y" else v(cfg, "rec_x_mm")) / 2
        a2 = a / math.sin(th_a)
        H = (a + a2) / math.tan(th_a)                       # full CPC height
        length = v(cfg, "rec_x_mm") if fa == "y" else v(cfg, "rec_y_mm")
        inside = np.abs(np.arctan(tt)) <= th_a + 1e-12
        return np.where(inside, np.clip(1 - H * np.abs(tl) / length, 0, 1), 0.0)
    sp = spot(cfg, tx, ty)
    area = _spot_area(sp)
    rx, ry = v(cfg, "rec_x_mm"), v(cfg, "rec_y_mm")
    nx, ny = int(v(cfg, "nx")), int(v(cfg, "ny"))
    if layout(cfg) == "shared":
        tot = 0.0
        for cx, cy in lens_centres(cfg):
            tot = tot + _overlap(sp, cx, cy, -rx / 2, rx / 2, -ry / 2, ry / 2)
        return tot / (nx * ny * area)
    px, py = v(cfg, "pitch_x_mm"), v(cfg, "pitch_y_mm")
    reach_x = (np.max(sp["wx"]) + rx) / 2 + np.max(np.abs(sp["sx"]))
    reach_y = (np.max(sp["wy"] if not sp["circle"] else sp["wx"]) + ry) / 2 + np.max(np.abs(sp["sy"]))
    kx_max = min(nx - 1, int(math.ceil(reach_x / px)))
    ky_max = min(ny - 1, int(math.ceil(reach_y / py)))
    tot = 0.0
    for kx in range(-kx_max, kx_max + 1):
        for ky in range(-ky_max, ky_max + 1):
            pairs = (nx - abs(kx)) * (ny - abs(ky))   # lens i → receiver of lens i + k exists for this many lenses
            ox, oy = kx * px, ky * py
            tot = tot + pairs * _overlap(sp, 0.0, 0.0, ox - rx / 2, ox + rx / 2, oy - ry / 2, oy + ry / 2)
    return tot / (nx * ny * area)


def peak_beam_factor(cfg, tx, ty):
    """Peak local beam irradiance on a receiver divided by the beam irradiance on the aperture plane, per unit
    transmission (uniform spots summed on a RASTER × RASTER grid). None for the CPC (flux profile not modelled)."""
    if cfg["type"] == "cpc":
        return None
    sp = spot(cfg, np.atleast_1d(float(tx)), np.atleast_1d(float(ty)))
    wx, wy, sx, sy = float(sp["wx"][0]), float(sp["wy"][0]), float(sp["sx"][0]), float(sp["sy"][0])
    a1 = aperture_mm(cfg)
    a1 = math.pi / 4 * a1[0] ** 2 if sp["circle"] else a1[0] * a1[1]
    dens = a1 / (math.pi / 4 * wx * wx if sp["circle"] else wx * wy)   # spot irradiance / aperture irradiance
    rx, ry = v(cfg, "rec_x_mm"), v(cfg, "rec_y_mm")
    cen = lens_centres(cfg)
    if layout(cfg) == "each":                               # receiver of the lens nearest the array centre
        c0 = min(cen, key=lambda c: (abs(c[0]) + abs(c[1]), c[1], c[0]))
    else:
        c0 = (0.0, 0.0)
    gx = c0[0] - rx / 2 + (np.arange(RASTER) + 0.5) * rx / RASTER
    gy = c0[1] - ry / 2 + (np.arange(RASTER) + 0.5) * ry / RASTER
    X, Y = np.meshgrid(gx, gy)
    acc = np.zeros_like(X)
    for cx, cy in cen:
        x, y = cx + sx, cy + sy
        if sp["circle"]:
            inside = (X - x) ** 2 + (Y - y) ** 2 <= (wx / 2) ** 2
        else:
            inside = (np.abs(X - x) <= wx / 2) & (np.abs(Y - y) <= wy / 2)
        acc += inside * dens
    return float(acc.max())


# ---------------------------------------------------------------------------------------------- one evaluation
def _t_cell(e, ta, ws, k_hs=1.0):
    """SAPM cell temperature with the receiver heat flux spread over k_hs × the receiver area (k_hs = 1: the plain
    module model of this repository). Assumption for concentrated light; no active cooling."""
    a, b, dT = SAPM
    q = np.asarray(e, float) / k_hs
    return ta + q * np.exp(a + b * np.asarray(ws, float)) + q / 1000 * dT


def iam_glass(theta):
    """pvlib.iam.physical (n = 1.526, K = 4, L = 0.002), normalised to 1 at normal incidence — plain PV baseline."""
    n, K, L = 1.526, 4.0, 0.002
    th = np.clip(np.abs(np.asarray(theta, float)), 1e-9, np.radians(89.999))

    def tr(t):
        tr_ = np.arcsin(np.sin(t) / n)
        rs = (np.sin(tr_ - t) / np.sin(tr_ + t)) ** 2
        rp = (np.tan(tr_ - t) / np.tan(tr_ + t)) ** 2
        return np.exp(-K * L / np.cos(tr_)) * (1 - 0.5 * (rs + rp))

    return tr(th) / tr(np.asarray(1e-9))


def iam_glass_diffuse():
    th = np.radians(np.arange(90) + 0.5)
    w = np.sin(2 * th)
    return float((iam_glass(th) * w).sum() / w.sum())


def _pv_dc(e_on, area_m2, cfg, ta, ws, k_hs=1.0):
    """DC power [W] of cells receiving the irradiance e_on [W/m², mean over the cell area]."""
    tc = _t_cell(e_on, ta, ws, k_hs)
    p = e_on * area_m2 * v(cfg, "eta_cell") * (1 + v(cfg, "gamma_per_K") * (tc - 25)) * v(cfg, "k_el")
    return np.clip(p, 0, None), tc


def optical(cfg, e_beam, e_diff, tx, ty):
    """Optical power balance [W] for the whole array. e_beam: beam irradiance on the aperture plane (already ×cos θ),
    e_diff: diffuse irradiance on the aperture plane [W/m²]."""
    A = areas(cfg)
    th = np.arctan(np.hypot(tx, ty))
    tb, td = tau(cfg, th), (tau(cfg, 0.0) if cfg["type"] == "cpc" else tau_diffuse(cfg))
    cap = capture(cfg, tx, ty)
    pb, pd = np.asarray(e_beam, float) * A["aperture_m2"], np.asarray(e_diff, float) * A["aperture_m2"]
    d_on = np.asarray(e_diff, float) * td * min(A["aperture_m2"], A["receiver_m2"])     # étendue bound
    loss = pb * (1 - tb) + pd * (1 - td)
    on = pb * tb * cap + d_on
    trans = pb * tb + pd * td
    return {"P_in_W": pb + pd, "P_beam_in_W": pb, "optical_loss_W": loss, "on_receiver_W": on,
            "off_receiver_W": trans - on, "tau_beam": tb, "tau_diffuse": td, "capture_beam": cap,
            "E_rec_mean_Wm2": on / A["receiver_m2"]}


def instant(cfg, dni=1000.0, diff=0.0, theta_x_deg=0.0, theta_y_deg=0.0, ta=25.0, ws=1.0) -> dict:
    """Instant result. Angles: projected incidence angles in the mount frame (x, y)."""
    val = validate(cfg)
    if not val["ok"]:
        return {"ok": False, **val}
    tx, ty = math.tan(math.radians(theta_x_deg)), math.tan(math.radians(theta_y_deg))
    cos = 1 / math.sqrt(1 + tx * tx + ty * ty)
    eb = dni * cos
    A = areas(cfg)
    o = {k: (float(np.asarray(x).ravel()[0]) if not isinstance(x, float) else x)
         for k, x in optical(cfg, np.array([eb]), np.array([diff]), np.array([tx]), np.array([ty])).items()}
    pk = peak_beam_factor(cfg, tx, ty)
    td = o["tau_diffuse"]
    peak = None if pk is None else eb * o["tau_beam"] * pk + diff * td * min(A["aperture_m2"], A["receiver_m2"]) / A["receiver_m2"]
    dc, tc = _pv_dc(np.array([o["E_rec_mean_Wm2"]]), A["receiver_m2"], cfg, ta, ws, v(cfg, "k_hs"))
    dc, tc = float(dc[0]), float(tc[0])
    th = math.atan(math.hypot(tx, ty))
    e_plain = eb * float(iam_glass(th)) + diff * iam_glass_diffuse()
    dcA, tA = _pv_dc(np.array([e_plain]), A["aperture_m2"], cfg, ta, ws)
    dcB, tB = _pv_dc(np.array([e_plain]), A["receiver_m2"], cfg, ta, ws)
    dcA, dcB = float(dcA[0]), float(dcB[0])
    P_in = o["P_in_W"]
    shares = {k: (o[k] / P_in if P_in > 0 else None) for k in ("optical_loss_W", "on_receiver_W", "off_receiver_W")}
    return {"ok": True, "level": model_level(cfg), "areas": A, **o, "shares": shares, "E_rec_peak_Wm2": peak,
            "t_cell_C": tc, "t_cell_warning": tc > T_CELL_LIMIT_C, "dc_W": dc, "system_eff": dc / P_in if P_in > 0 else None,
            "validity": validity(cfg, th),
            "compare_A": {"label": "eyni işıqtoplama sahəsi", "area_optic_m2": A["aperture_m2"], "area_plain_m2": A["aperture_m2"],
                          "plain_dc_W": dcA, "optic_dc_W": dc, "delta_W": dc - dcA,
                          "ratio": dc / dcA if dcA > 0 else None, "plain_t_cell_C": float(tA[0]),
                          "optic_W_per_m2": dc / A["aperture_m2"], "plain_W_per_m2": dcA / A["aperture_m2"]},
            "compare_B": {"label": "eyni fotoelement sahəsi", "cell_area_m2": A["receiver_m2"],
                          "collect_optic_m2": A["aperture_m2"], "collect_plain_m2": A["receiver_m2"],
                          "plain_dc_W": dcB, "optic_dc_W": dc, "ratio": dc / dcB if dcB > 0 else None,
                          "plain_t_cell_C": float(tB[0])}}


def analytic(cfg, dni=1000.0) -> dict:
    """Simple analytic baseline (Rev B): N · A_aperture · DNI · η_opt,eff · η_cell · k_th · k_el at normal incidence.
    η_opt,eff is an effective optical share that already contains the receiver intercept."""
    A = areas(cfg)
    one = A["aperture_one_m2"] * dni * v(cfg, "eta_opt_eff") * v(cfg, "eta_cell") * v(cfg, "k_th") * v(cfg, "k_el")
    return {"per_unit_W": one, "total_W": one * A["n"], "n": A["n"], "aperture_one_m2": A["aperture_one_m2"],
            "aperture_m2": A["aperture_m2"], "C_g": A["C_g"]}


def validity(cfg, theta_inc=0.0) -> dict:
    """Paraxial validity: lens f-number and edge-ray angle (optics.lens_geometry) and, separately, the incidence."""
    t = cfg["type"]
    inc = math.degrees(abs(theta_inc))
    out = {"incidence_deg": inc, "incidence_label": O.paraxial_label(inc)}
    if t in ("flat", "cpc"):
        out.update(edge=None, paraxial=None, above_warn_limit=False, reliability=None, coarse=False)
        return out
    ax, ay = aperture_mm(cfg)
    fa = cfg.get("focus_axis", "y")
    if t == "linear_fresnel":
        g = O.lens_geometry(v(cfg, "f_mm"), ay if fa == "x" else ax, ax if fa == "x" else ay, cylindrical=True)
        g["axis"] = fa
    else:
        g = O.lens_geometry(v(cfg, "f_mm"), ax, ay)
        if cfg.get("shape") == "circle":                    # round aperture: diameter, no corner ray
            g.update(axis="d", corner_angle_deg=None, diagonal_mm=None)
    lab = O.paraxial_label(g["edge_angle_deg"])
    rank = {"yaxşı": 0, "orta": 1, "aşağı": 2}
    worst = max(lab, out["incidence_label"], key=rank.get)
    out.update(edge=g, paraxial=lab, above_warn_limit=g["edge_angle_deg"] > O.PARAXIAL_WARN_DEG,
               reliability={"yaxşı": "yüksək", "orta": "orta", "aşağı": "aşağı"}[worst])
    out["coarse"] = out["reliability"] == "aşağı"
    return out


# ------------------------------------------------------------------------------------------------------- annual
def annual(cfg, hourly: dict, mount: str | None = None) -> dict:
    """Annual energy over a dataset's hourly export (docs/data/<id>.json → "hourly"). Mount: 'fixed' (site tilt and
    azimuth of the dataset) or '2axis' (two-axis tracking, constant pointing error)."""
    val = validate(cfg)
    if not val["ok"]:
        return {"ok": False, **val}
    mount = mount or cfg.get("mount", "fixed")
    h = {k: np.asarray(hourly[k], float) for k in ("beam", "sky", "ground", "tx", "ty", "f_beam", "f_diff", "ta", "ws",
                                                     "t_beam", "t_diff", "t_glob", "t_dnicos", "sun")}
    step = float(hourly["step_h"])
    sun = h["sun"] > 0
    if mount == "2axis":
        e_b, e_d = h["t_dnicos"], np.clip(h["t_glob"] - h["t_dnicos"], 0, None)
        err = math.tan(math.radians(v(cfg, "track_err_deg")))
        fa = cfg.get("focus_axis", "y")
        tx = np.full_like(e_b, err if fa == "x" else 0.0)
        ty = np.full_like(e_b, err if fa == "y" else 0.0)
        e_plain = h["t_beam"] + h["t_diff"]
        aux = v(cfg, "drive_W") * sun + v(cfg, "controller_W")
    else:
        e_b, e_d, tx, ty = h["beam"], h["sky"] + h["ground"], h["tx"], h["ty"]
        e_plain = h["f_beam"] + h["f_diff"]
        aux = np.zeros_like(e_b)
    e_b, e_d = np.where(sun, e_b, 0.0), np.where(sun, e_d, 0.0)
    A = areas(cfg)
    o = optical(cfg, e_b, e_d, tx, ty)
    dc, tc = _pv_dc(o["E_rec_mean_Wm2"], A["receiver_m2"], cfg, h["ta"], h["ws"], v(cfg, "k_hs"))
    dcA, _ = _pv_dc(e_plain, A["aperture_m2"], cfg, h["ta"], h["ws"])
    dcB, _ = _pv_dc(e_plain, A["receiver_m2"], cfg, h["ta"], h["ws"])
    kwh = lambda x: float(np.sum(x) * step / 1000)
    res = {"gross_kWh": kwh(dc), "aux_kWh": kwh(aux), "net_kWh": kwh(dc) - kwh(aux)}
    resA = {"gross_kWh": kwh(dcA), "aux_kWh": kwh(aux), "net_kWh": kwh(dcA) - kwh(aux)}
    resB = {"gross_kWh": kwh(dcB), "aux_kWh": kwh(aux), "net_kWh": kwh(dcB) - kwh(aux)}
    optics_kWh = {k: kwh(o[k]) for k in ("P_in_W", "optical_loss_W", "on_receiver_W", "off_receiver_W")}
    pct = lambda a, b: 100 * (a / b - 1) if b > 0 else None
    rat = lambda a, b: a / b if b > 0 else None
    hot = (tc > T_CELL_LIMIT_C) & sun
    return {"ok": True, "mount": mount, "level": model_level(cfg), "areas": A, "optic": res, "optics_kWh": optics_kWh,
            "max_t_cell_C": float(np.max(np.where(sun, tc, -273))), "hours_above_limit": int(hot.sum()),
            "t_limit_C": T_CELL_LIMIT_C,
            "compare_A": {"plain": resA, "area_m2": A["aperture_m2"],
                          "delta_gross_pct": pct(res["gross_kWh"], resA["gross_kWh"]),
                          "delta_pct": pct(res["net_kWh"], resA["net_kWh"])},
            "compare_B": {"plain": resB, "cell_area_m2": A["receiver_m2"], "collect_optic_m2": A["aperture_m2"],
                          "collect_plain_m2": A["receiver_m2"],
                          "ratio_gross": rat(res["gross_kWh"], resB["gross_kWh"]),
                          "ratio": rat(res["net_kWh"], resB["net_kWh"])},
            "assumptions": assumptions(cfg, mount)}


def _az(x):
    return f"{x:g}".replace(".", ",").replace("-", "−")


def assumptions(cfg, mount):
    """Which inputs of the annual result are assumptions (shown with the result)."""
    out = []
    if cfg["type"] == "cpc":
        out.append("qəbul bucağı və əks olunma: " + cfg["params"]["accept_deg"]["status"] + " / " + cfg["params"]["reflectivity"]["status"])
    elif not v(cfg, "angle_table"):
        out.append("ötürmənin bucaqdan asılılığı fərziyyədir (nominal τ0 + iki Fresnel səthi), ölçülmüş deyil")
    out.append("qəbul bucağı ölçülməyib: həndəsi ləkə modelindən gəlir" if cfg["type"] != "cpc" else "CPC ideal fərz olunur (kəsilmə yoxdur)")
    out.append(f"hüceyrə temperaturu: SAPM açıq dayaq modeli, istilik ötürən səth əmsalı k = {_az(v(cfg, 'k_hs'))} ({cfg['params']['k_hs']['status']})")
    out.append("qəbulediciyə düşən səpələnmiş işıq étendue həddi ilə yuxarıdan qiymətləndirilir")
    if mount == "2axis":
        out.append(f"izləmə: yönəltmə xətası {_az(v(cfg, 'track_err_deg'))}°, sərf {_az(v(cfg, 'drive_W'))} W + {_az(v(cfg, 'controller_W'))} W ({cfg['params']['drive_W']['status']})")
    return out
