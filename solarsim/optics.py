"""Lens over a flat module — finite-geometry, thin-lens (paraxial) model with a full light balance.

Model level 1 (this module, used for annual results)
----------------------------------------------------
* Thin lens of power D [dioptre], focal length f = 1000/D mm (D = 0: flat sheet, D < 0: virtual focus, rays diverge).
* Lens tiles: ``array`` = one lenslet per cell (spherical, focusing in x and y), ``array_cyl`` = one cylindrical lenslet
  per cell row (focusing only along the slope y), ``big`` = one lens covering the whole module.
* Every tile images its aperture onto the cell plane: scale m = 1 − h_eff/f, shifted by the incidence angle
  (air path h − t_g plus t_g inside the module glass, Snell refraction). The spot is uniformly lit (geometric optics),
  never smaller than the sun-disk image and never more concentrated than C_max = 46 000.
* The light reaching the cell plane is split, without double counting, into: own cell, neighbouring cells,
  gaps between cells, outside the module. Upstream losses: reflected and absorbed in the lens, reflected by the
  module glass (angular part only — the normal-incidence glass loss is already inside the 450 W rating).
* Direct, sky-diffuse and ground-reflected light are redistributed separately (diffuse: isotropic radiance over the
  sky / ground part of the module's hemisphere).

Validity labels (``validity``) state where this level is a low-reliability approximation (large aperture, short
focus, large incidence angle). f-number N = |f| / a and the edge-ray angle to the optical axis θ = atan((a/2) / |f|)
are computed on the focusing axis that has the larger aperture a (cylindrical lenslets: the slope axis y only); for a
rectangular spherical lens the corner-ray angle atan((d/2) / |f|), d = diagonal, is reported separately. The 30° limit
is the simulator's warning criterion for the paraxial model; it is not a statement about whether such a lens can be
manufactured. Level 2 (``trace2d``) checks level 1 with exact Snell/Fresnel ray tracing.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .pv import Module

C_MAX = 46000.0                 # thermodynamic limit of solar concentration
SUN_HALF = np.radians(0.2665)   # angular radius of the sun
T_GLASS = 2.1                   # mm: 1.6 mm front glass (datasheet) + ~0.5 mm encapsulant (assumption)
N_GLASS = 1.5
RS_K = 0.035                    # assumption: extra series-resistance loss per extra sun of local intensity
# Warning criteria of the thin paraxial model (simulator conventions, not manufacturability limits):
# edge-ray angle to the optical axis ≤ 10° 'yaxşı', ≤ 20° 'orta', above 'aşağı'; above 30° an extra warning is shown.
PARAXIAL_GOOD_DEG, PARAXIAL_FAIR_DEG = 10.0, 20.0
PARAXIAL_WARN_DEG = 30.0


@dataclass
class LensConfig:
    P: float                    # dioptre
    h: float                    # mm, lens principal plane above the cell plane
    mode: str = "array"         # array | array_cyl | big
    tau: float = 0.92           # transmittance at normal incidence (both surfaces + bulk)
    n: float = 1.49
    K: float = 4.0
    L: float = 0.003

    @property
    def f(self) -> float:
        return np.inf if abs(self.P) < 1e-12 else 1000.0 / self.P

    @property
    def kind(self) -> str:
        return "flat" if abs(self.P) < 1e-12 else ("converging" if self.P > 0 else "diverging")


class Geometry:
    def __init__(self, module: Module | None = None):
        m = module or Module()
        self.LX, self.LY = m.v("width_mm"), m.v("length_mm")
        self.NX, self.NY = 6, 24
        self.PX, self.PY = self.LX / self.NX, self.LY / self.NY
        self.CX, self.CY = m.v("cell_w_mm"), m.cell_h_mm
        self.f_act = self.CX * self.CY / (self.PX * self.PY)
        self.cx = -self.LX / 2 + (np.arange(self.NX) + 0.5) * self.PX
        self.cy = -self.LY / 2 + (np.arange(self.NY) + 0.5) * self.PY
        self.glass = dict(n=m.v("glass_n"), K=m.v("glass_K"), L=m.v("glass_L"))


# ------------------------------------------------------------------------------------------ angle-dependent surfaces
def _fresnel_unpolarised(theta, n):
    th = np.clip(np.abs(theta), 1e-9, np.radians(89.9))
    tr = np.arcsin(np.sin(th) / n)
    rs = (np.sin(tr - th) / np.sin(tr + th)) ** 2
    rp = (np.tan(tr - th) / np.tan(tr + th)) ** 2
    return 0.5 * (rs + rp), tr


def lens_split(theta, cfg: LensConfig):
    """(transmitted, reflected, absorbed) fractions of the light hitting the lens; sum = 1.
    Normal-incidence transmittance equals cfg.tau; the angular shape follows Fresnel (2 surfaces) + bulk absorption."""
    R, tr = _fresnel_unpolarised(theta, cfg.n)
    R0, _ = _fresnel_unpolarised(np.array(1e-6), cfg.n)
    t_surf = (1 - R) ** 2
    t_bulk = np.exp(-cfg.K * cfg.L / np.cos(tr))
    shape = (t_surf * t_bulk) / ((1 - R0) ** 2 * np.exp(-cfg.K * cfg.L))
    T = np.clip(cfg.tau * shape, 0, 1)
    A = np.clip((1 - t_bulk) * (1 - R), 0, 1 - T)
    return T, 1 - T - A, A


def glass_iam(theta, geom: Geometry):
    import pvlib
    return np.asarray(pvlib.iam.physical(np.degrees(np.abs(theta)), **geom.glass), float)


# ----------------------------------------------------------------------------------------------------- spot geometry
def _h_eff(h):
    """Air-equivalent distance for focusing through the glass slab (paraxial): h − t_g + t_g/n."""
    return max(h - T_GLASS, 0.0) + T_GLASS / N_GLASS


def _shift(h, t):
    """Lateral displacement at the cell plane for incidence tan t (air part + refracted part in the glass)."""
    th = np.arctan(t)
    tg = np.tan(np.arcsin(np.sin(th) / N_GLASS))
    return -(max(h - T_GLASS, 0.0) * t + T_GLASS * tg)


def _tiles(geom: Geometry, mode: str):
    if mode == "big":
        return np.array([0.0]), np.array([geom.LX]), np.array([0.0]), np.array([geom.LY])
    return geom.cx, np.full(geom.NX, geom.PX), geom.cy, np.full(geom.NY, geom.PY)


def _overlap(a0, a1, b0, b1):
    return np.clip(np.minimum(a1, b1) - np.maximum(a0, b0), 0, None)


def spot_split(cfg: LensConfig, geom: Geometry, tx, ty, blur_half_tan=np.tan(SUN_HALF)):
    """For incidence (tx, ty) arrays of shape (H,), return per unit of power arriving at the cell plane:
    cells (H, NX, NY) fractions, own, neighbours, gap, off, and local concentration (H,)."""
    tx, ty = np.atleast_1d(tx).astype(float), np.atleast_1d(ty).astype(float)
    H = len(tx)
    tcx, awx, tcy, awy = _tiles(geom, cfg.mode)
    he = _h_eff(cfg.h)
    m = 1.0 if not np.isfinite(cfg.f) else 1.0 - he / cfg.f
    mx = 1.0 if cfg.mode == "array_cyl" else m
    blur = 2 * cfg.h * np.asarray(blur_half_tan, float)
    wx = np.abs(mx) * awx[None, :] + np.broadcast_to(blur, (H,))[:, None]      # (H, ntx)
    wy = np.abs(m) * awy[None, :] + np.broadcast_to(blur, (H,))[:, None]
    # concentration limit
    area_ap = awx[0] * awy[0]
    k = np.sqrt(np.maximum(1.0, area_ap / C_MAX / np.maximum(wx[:, :1] * wy[:, :1], 1e-12)))
    wx, wy = wx * k, wy * k
    sx = np.array([_shift(cfg.h, t) for t in tx])[:, None]
    sy = np.array([_shift(cfg.h, t) for t in ty])[:, None]
    x0, x1 = tcx[None, :] + sx - wx / 2, tcx[None, :] + sx + wx / 2
    y0, y1 = tcy[None, :] + sy - wy / 2, tcy[None, :] + sy + wy / 2
    # overlaps with cells along each axis: (H, n_tiles, n_cells)
    ox = _overlap(x0[:, :, None], x1[:, :, None], (geom.cx - geom.CX / 2)[None, None, :], (geom.cx + geom.CX / 2)[None, None, :])
    oy = _overlap(y0[:, :, None], y1[:, :, None], (geom.cy - geom.CY / 2)[None, None, :], (geom.cy + geom.CY / 2)[None, None, :])
    inx = _overlap(x0, x1, -geom.LX / 2, geom.LX / 2)            # (H, ntx)
    iny = _overlap(y0, y1, -geom.LY / 2, geom.LY / 2)
    # each tile carries the same power share (uniform irradiance on the module plane)
    ntx, nty = len(tcx), len(tcy)
    share = 1.0 / (ntx * nty)
    fx = ox / wx[:, :, None]                                      # fraction of a tile's spot (x) on cell column p
    fy = oy / wy[:, :, None]
    cells = share * np.einsum("hip,hjq->hpq", fx, fy)             # (H, NX, NY), fraction of total power
    if cfg.mode == "big":
        own = np.zeros(H)
    else:
        own = share * np.einsum("hii->h", fx) * np.einsum("hjj->h", fy)
    on_cells = cells.sum(axis=(1, 2))
    inside = share * (inx / wx).sum(1) * (iny / wy).sum(1)
    conc = (awx[0] * awy[0]) / (wx[:, 0] * wy[:, 0])
    return {"cells": cells, "own": own, "neighbours": on_cells - own, "gap": inside - on_cells,
            "off": 1.0 - inside, "conc": conc, "m": m}


# --------------------------------------------------------------------------------------------- diffuse directions
def hemisphere_dirs(tilt_deg: float, d_theta=5.0, d_phi=15.0):
    """Cos-weighted directions in the module frame, split into sky (world elevation > 0) and ground."""
    th = np.radians(np.arange(d_theta / 2, 90, d_theta))
    ph = np.radians(np.arange(0, 360, d_phi))
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    TH, PH = TH.ravel(), PH.ravel()
    w = np.cos(TH) * np.sin(TH)
    b = np.radians(tilt_deg)
    # direction towards the sky element in module frame -> world up component: d·U, U = (0, sin b, cos b) in (x,y,z)
    up = np.sin(TH) * np.sin(PH) * np.sin(b) + np.cos(TH) * np.cos(b)
    blur = 0.5 * np.maximum(np.radians(d_theta) / np.cos(TH) ** 2, np.tan(TH) * np.radians(d_phi))
    return {"theta": TH, "tx": np.tan(TH) * np.cos(PH), "ty": np.tan(TH) * np.sin(PH), "w": w,
            "sky": up > 0, "blur": blur}


def diffuse_response(cfg: LensConfig, geom: Geometry, tilt_deg: float, part: str):
    """Response of the lens to unit isotropic irradiance from the sky (or ground) part of the hemisphere.
    Returned fractions refer to the irradiance that would reach a bare module plane from that part."""
    d = hemisphere_dirs(tilt_deg)
    sel = d["sky"] if part == "sky" else ~d["sky"]
    if not sel.any():
        z = np.zeros((geom.NX, geom.NY))
        return {"cells": z, "own": 0.0, "neighbours": 0.0, "gap": 0.0, "off": 0.0, "refl_lens": 0.0,
                "abs_lens": 0.0, "refl_glass": 0.0, "bare_cells": 0.0}
    w = d["w"][sel] / d["w"][sel].sum()
    th = d["theta"][sel]
    T, R, A = lens_split(th, cfg)
    g = glass_iam(th, geom)
    s = spot_split(cfg, geom, d["tx"][sel], d["ty"][sel], d["blur"][sel])
    reach = w * T * g
    out = {"cells": np.einsum("h,hpq->pq", reach, s["cells"])}
    for k in ("own", "neighbours", "gap", "off"):
        out[k] = float((reach * s[k]).sum())
    out["refl_lens"] = float((w * R).sum()); out["abs_lens"] = float((w * A).sum())
    out["refl_glass"] = float((w * T * (1 - g)).sum())
    # bare module (no lens) reference: glass IAM over the same directions, then active-area fraction
    out["bare_cells"] = float((w * g).sum()) * geom.f_act
    return out


# --------------------------------------------------------------------------------------------- hourly light balance
def light_balance(cfg: LensConfig, geom: Geometry, beam, sky, ground, tx, ty, theta, tilt_deg: float):
    """Power balance [W] per hour for the module aperture. beam/sky/ground: POA irradiance components (W/m², before
    any glass loss). Returns dict of arrays and the cell map (H, NX, NY) in W/m² cell-equivalent irradiance."""
    A = geom.LX * geom.LY / 1e6
    beam, sky, ground = (np.asarray(v, float) for v in (beam, sky, ground))
    T, R, Ab = lens_split(np.asarray(theta, float), cfg)
    g = glass_iam(np.asarray(theta, float), geom)
    s = spot_split(cfg, geom, tx, ty)
    pb = beam * A
    reach_b = pb * T * g
    ds, dg = diffuse_response(cfg, geom, tilt_deg, "sky"), diffuse_response(cfg, geom, tilt_deg, "ground")
    ps, pg = sky * A, ground * A
    out = {"in": pb + ps + pg,
           "refl_lens": pb * R + ps * ds["refl_lens"] + pg * dg["refl_lens"],
           "abs_lens": pb * Ab + ps * ds["abs_lens"] + pg * dg["abs_lens"],
           "refl_glass": pb * T * (1 - g) + ps * ds["refl_glass"] + pg * dg["refl_glass"]}
    for k in ("own", "neighbours", "gap", "off"):
        out[k] = reach_b * s[k] + ps * ds[k] + pg * dg[k]
    cell_area = geom.CX * geom.CY / 1e6
    cellsW = reach_b[:, None, None] * s["cells"] + ps[:, None, None] * ds["cells"][None] + pg[:, None, None] * dg["cells"][None]
    # local concentration penalty (series resistance) on the beam part only
    i_loc = beam * T * g * s["conc"]
    pen = np.clip(1 - RS_K * np.clip(i_loc / 1000 - 1, 0, None), 0, 1)
    beam_cells = reach_b[:, None, None] * s["cells"]
    out["rs_loss"] = (beam_cells * (1 - pen)[:, None, None]).sum(axis=(1, 2))
    cellsW = cellsW - beam_cells * (1 - pen)[:, None, None]
    out["cells_Wm2"] = cellsW / cell_area                       # W/m² on each cell (cell-equivalent irradiance)
    out["conc"] = s["conc"]
    out["bare_Wm2"] = (beam * g + sky * (ds["bare_cells"] / geom.f_act) + ground * (dg["bare_cells"] / geom.f_act))
    return out


# --------------------------------------------------------------------------------------------------------- validity
def paraxial_label(edge_angle_deg: float) -> str:
    return "yaxşı" if edge_angle_deg <= PARAXIAL_GOOD_DEG else ("orta" if edge_angle_deg <= PARAXIAL_FAIR_DEG else "aşağı")


def lens_geometry(f_mm: float, ax_mm: float, ay_mm: float, cylindrical: bool = False) -> dict:
    """f-number and ray angles of one lens tile (ax × ay mm), unrounded.

    Focusing axis: the larger of x, y for a spherical tile; y only for a cylindrical one.
    N = |f| / a,  edge-ray angle to the optical axis = atan((a/2) / |f|);
    corner-ray angle = atan((√(ax² + ay²)/2) / |f|) for a spherical rectangular tile (None otherwise)."""
    if cylindrical:
        axis, a = "y", ay_mm
    else:
        axis, a = ("y", ay_mm) if ay_mm >= ax_mm else ("x", ax_mm)
    out = {"axis": axis, "aperture_mm": float(a), "aperture_x_mm": float(ax_mm), "aperture_y_mm": float(ay_mm),
           "cylindrical": bool(cylindrical), "f_mm": None, "f_number": None, "edge_angle_deg": 0.0,
           "corner_angle_deg": None, "diagonal_mm": None}
    if not np.isfinite(f_mm):
        return out
    F = abs(f_mm)
    out.update(f_mm=float(f_mm), f_number=float(F / a), edge_angle_deg=float(np.degrees(np.arctan(a / 2 / F))))
    if not cylindrical:
        d = float(np.hypot(ax_mm, ay_mm))
        out.update(diagonal_mm=d, corner_angle_deg=float(np.degrees(np.arctan(d / 2 / F))))
    return out


def reliability(v: dict) -> str:
    if v["paraxial"] == "aşağı":
        return "aşağı"
    if v["paraxial"] == "orta" or v.get("beam_share_aoi_gt_30", 0) > 0.5:
        return "orta"
    return "yüksək"


def validity(cfg: LensConfig, geom: Geometry, theta_beam=None, weights=None) -> dict:
    """Where the thin, paraxial level-1 model is trustworthy (see the module docstring for the definitions)."""
    tcx, awx, tcy, awy = _tiles(geom, cfg.mode)
    out = lens_geometry(cfg.f if cfg.kind != "flat" else np.inf, float(awx[0]), float(awy[0]), cfg.mode == "array_cyl")
    out["paraxial"] = paraxial_label(out["edge_angle_deg"])
    out["above_warn_limit"] = bool(out["edge_angle_deg"] > PARAXIAL_WARN_DEG)
    out["warn_limit_deg"] = PARAXIAL_WARN_DEG
    if theta_beam is not None:
        th = np.degrees(np.asarray(theta_beam, float))
        w = np.ones_like(th) if weights is None else np.asarray(weights, float)
        out["beam_share_aoi_gt_30"] = float(w[th > 30].sum() / max(w.sum(), 1e-12))
    out["reliability"] = reliability(out)
    out["coarse"] = out["reliability"] == "aşağı"      # results shown with the label "kobud yaxınlaşdırma"
    return out


# ------------------------------------------------------------------------------------------------- level 2: ray trace
def trace2d(cfg: LensConfig, geom: Geometry, theta_y_deg: float, n_rays=4001, n_sun=7, t_min=1.0):
    """Exact 2-D ray trace along the slope (y) through a spherical plano-convex (D>0) or plano-concave (D<0) lenslet,
    curved side towards the sun, R = (n−1)·|f|, flat side down at height h above the cells, minimum thickness
    t_min; then the module glass slab. Snell at every surface, unpolarised Fresnel transmission per surface,
    sun disk sampled. Returns the share of transmitted power on cells / in gaps / outside the module."""
    a = geom.PY if cfg.mode in ("array", "array_cyl") else geom.LY
    if cfg.kind == "flat":
        return {"traced": True, "note": "düz təbəqə: paraksial modellə eynidir"}
    R = (cfg.n - 1) * abs(cfg.f)
    if R < a / 2:
        return {"traced": False, "R_mm": float(R), "half_aperture_mm": float(a / 2),
                "note": "fərz olunan sferik profil bu aperturaya sığmır (R < a/2); izləmə aparılmadı"}
    sag = R - np.sqrt(R ** 2 - (a / 2) ** 2)
    zb = cfg.h                                            # flat bottom of the lens
    y0 = np.linspace(-a / 2, a / 2, n_rays)
    root = np.sqrt(R ** 2 - y0 ** 2)
    if cfg.P > 0:                                         # convex top, edge thickness t_min
        zc = zb + t_min - np.sqrt(R ** 2 - (a / 2) ** 2)
        zs = zc + root
        nrm = np.stack([y0, zs - zc]) / R
    else:                                                 # concave top, centre thickness t_min
        zc = zb + t_min + R
        zs = zc - root
        nrm = np.stack([-y0, zc - zs]) / R
    if cfg.mode == "big":
        centres, edge = geom.cy, geom.LY / 2
    else:
        centres, edge = np.arange(-30, 31) * geom.PY, np.inf
    on = gap = off = tot = 0.0
    for dsun in np.linspace(-SUN_HALF, SUN_HALF, n_sun):
        th = np.radians(theta_y_deg) + dsun
        d = np.stack([np.full_like(y0, np.sin(th)), np.full_like(y0, -np.cos(th))])
        cos_i = -(nrm * d).sum(0)
        eta = 1.0 / cfg.n
        k = 1 - eta ** 2 * (1 - cos_i ** 2)
        ok = (k > 0) & (cos_i > 0)
        tdir = eta * d + (eta * cos_i - np.sqrt(np.where(ok, k, 0.0))) * nrm
        R1, _ = _fresnel_unpolarised(np.arccos(np.clip(cos_i, -1, 1)), cfg.n)
        w = (1 - R1) * ok
        s = (zs - zb) / np.maximum(-tdir[1], 1e-9)
        yb = y0 + s * tdir[0]
        sin_out = cfg.n * tdir[0]
        ok2 = np.abs(sin_out) < 1
        R2, _ = _fresnel_unpolarised(np.arcsin(np.clip(np.abs(tdir[0]), 0, 1)), cfg.n)
        w = w * (1 - R2) * ok2
        ang = np.arcsin(np.clip(sin_out, -1, 1))
        yg = yb + max(zb - T_GLASS, 0.0) * np.tan(ang)
        yc = yg + T_GLASS * np.tan(np.arcsin(np.sin(ang) / N_GLASS))
        inside = np.abs(yc) <= edge
        local = np.min(np.abs(yc[:, None] - centres[None, :]), axis=1)
        hit = inside & (local <= geom.CY / 2)
        on += float((w * hit).sum()); gap += float((w * (inside & ~hit)).sum()); off += float((w * ~inside).sum())
        tot += float(w.sum())
    return {"traced": True, "on_cells": on / tot, "gap": gap / tot, "off": off / tot,
            "sag_mm": float(sag), "R_mm": float(R)}
