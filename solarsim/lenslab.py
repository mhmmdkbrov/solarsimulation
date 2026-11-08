"""Annual evaluation of a lens over the fixed module (same weather, plane, temperature model as scenario A).

Every candidate (dioptre, distance, layout) is evaluated with the same function ``annual``; the search includes the
published test points, so the reported optimum is at least as good as each of them by construction (and tested).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import electrical as E
from . import geometry as G
from . import optics as O
from . import pv as PV
from .weather import Dataset, energy_Wh


def prepare(ds: Dataset, module: PV.Module | None = None, tilt=None, azimuth=None, albedo=None) -> dict:
    m = module or PV.Module()
    tilt = ds.site.tilt_deg if tilt is None else tilt
    azimuth = ds.site.azimuth_deg if azimuth is None else azimuth
    albedo = ds.site.albedo if albedo is None else albedo
    sp = G.solar_position(ds)
    poa = G.poa_components(ds, sp, tilt, azimuth, albedo)
    iam = PV.iam_front(poa["aoi"], tilt, n=m.v("glass_n"), K=m.v("glass_K"), L=m.v("glass_L"))
    fr = G.sun_in_panel_frame(sp, tilt, azimuth)
    tc = PV.t_cell_sapm(poa["global"], ds.df["temp_air"], ds.df["wind_speed"])
    e_a = PV.effective_irradiance(poa, iam.set_axis(ds.df.index))
    day = (poa["global"] > 0).to_numpy()
    beam_ok = (fr["cos"] > 0.02).to_numpy()
    return {
        "ds": ds, "module": m, "geom": O.Geometry(m), "tilt": tilt, "azimuth": azimuth, "albedo": albedo,
        "day": day, "beam": np.where(beam_ok, poa["beam"], 0.0)[day], "sky": poa["sky"].to_numpy()[day],
        "ground": poa["ground"].to_numpy()[day], "theta": np.radians(poa["aoi"].to_numpy())[day],
        "tx": fr["tx"].to_numpy()[day], "ty": fr["ty"].to_numpy()[day], "t_cell": tc.to_numpy()[day],
        "p_A": PV.pvwatts(e_a, tc, m.v("pdc0_W"), m.v("gamma_pdc")).to_numpy()[day],
        "index": ds.df.index[day], "step_h": ds.step_h,
    }


def fast_factor_vec(cells: np.ndarray, topology="T1") -> np.ndarray:
    """Vectorised weakest-cell rule for maps (H, 6, 24) -> factor relative to the mean irradiance."""
    H = cells.shape[0]
    caps = np.zeros((H, 3))
    for g, grp in enumerate(E.strings(topology)):
        for s in grp:
            c = np.array(s)
            caps[:, g] += cells[:, c[:, 0], c[:, 1]].min(axis=1) / 2.0
    mean = cells.mean(axis=(1, 2))
    best = np.zeros(H)
    for g in range(3):
        I = caps[:, g]
        best = np.maximum(best, I * (caps >= I[:, None] - 1e-12).sum(1) / 3.0)
    return np.where(mean > 0, best / np.where(mean > 0, mean, 1), 1.0)


NULL_LENS = O.LensConfig(0.0, O.T_GLASS, "array", tau=1.0, n=1.0, K=0.0)   # "no lens": same optical chain, no effect


def _chain_power(prep, cfg, method, topology, sl):
    m, geom = prep["module"], prep["geom"]
    lb = O.light_balance(cfg, geom, prep["beam"][sl], prep["sky"][sl], prep["ground"][sl],
                         prep["tx"][sl], prep["ty"][sl], prep["theta"][sl], prep["tilt"])
    cells = lb["cells_Wm2"]
    g_mean = cells.mean(axis=(1, 2))
    tc = prep["t_cell"][sl]
    if method == "fast":
        mf = fast_factor_vec(cells, topology)
    elif method == "iv":
        mf = np.array([E.mismatch_factor(cells[i], tc[i], topology) if g_mean[i] > 1 else 1.0 for i in range(len(g_mean))])
    else:
        raise ValueError(method)
    return PV.pvwatts(g_mean, tc, m.v("pdc0_W"), m.v("gamma_pdc")) * mf, mf, lb


def annual(prep: dict, cfg: O.LensConfig, method="fast", topology="T1", every=1) -> dict:
    """Annual DC energy of the lens module (kWh/m² aperture) and the light balance [kWh].

    Differential method: the lens and a null lens (n = 1, τ = 1, D = 0) go through the same optical chain; their
    energy ratio is applied to scenario A (pvlib baseline). The chain's own deviation from A (diffuse sampling,
    edge geometry) is reported as ``chain_vs_A_pct`` and does not enter the lens effect."""
    m, geom = prep["module"], prep["geom"]
    sl = slice(None, None, every)
    p_lens, mf, lb = _chain_power(prep, cfg, method, topology, sl)
    key = ("null", method, topology, every)          # the null-lens chain does not depend on the lens: cache it
    if key not in prep:
        prep[key] = _chain_power(prep, NULL_LENS, method, topology, sl)[0]
    p_null = prep[key]
    dt = prep["step_h"] * every
    A = m.area_m2
    kwh = lambda x: float(np.sum(x) * dt / 1000.0)
    a_kwh_m2 = kwh(prep["p_A"][sl]) / A
    ratio = float(np.sum(p_lens) / max(np.sum(p_null), 1e-9))
    bal = {k: kwh(lb[k]) for k in ("in", "refl_lens", "abs_lens", "refl_glass", "own", "neighbours", "gap", "off", "rs_loss")}
    res = {"A_kWh_m2": a_kwh_m2, "L_kWh_m2": a_kwh_m2 * ratio, "ratio_to_null_lens": ratio,
           "chain_vs_A_pct": 100 * (kwh(p_null) / A / a_kwh_m2 - 1),
           "balance_kWh": bal,
           "mismatch_energy_weighted": float(np.sum(p_lens) / max(np.sum(p_lens / np.where(mf > 0, mf, 1)), 1e-9)),
           "method": method, "topology": topology, "every": every,
           "validity": O.validity(cfg, geom, prep["theta"][sl], prep["beam"][sl])}
    res["delta_pct"] = 100 * (ratio - 1)
    return res


def test_points(P: float) -> list[tuple[str, float]]:
    pts = [("şüşənin üstündə 3 mm", 3.0), ("10 sm sınaq məsafəsi", 100.0)]
    if P > 0:
        pts.append(("fokusda h = f", 1000.0 / P))
    return pts


H_GRID = [2.6, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 250, 333.3, 400, 500, 750, 1000]


def best_h(prep, P, mode, tau, h_grid=H_GRID, method="fast") -> dict:
    """Best distance within the tested range (grid ∪ test points), all evaluated with the same annual function."""
    cand = sorted(set([round(h, 3) for h in h_grid] + [round(h, 3) for _, h in test_points(P)]))
    rows = [(h, annual(prep, O.LensConfig(P, h, mode, tau), method)) for h in cand]
    h_best, r_best = max(rows, key=lambda x: x[1]["L_kWh_m2"])
    return {"h": h_best, "result": r_best, "candidates": [(h, r["delta_pct"]) for h, r in rows],
            "search": {"h_min": cand[0], "h_max": cand[-1], "n": len(cand)}}
