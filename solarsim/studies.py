"""Studies built on the scenario model: C = 5 concentration on a flat module, CPV break-even, interannual spread."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import geometry as G
from . import pv as PV
from . import scenarios as S
from .weather import Dataset, energy_Wh

SI_LIMIT = {"value": 0.294, "conditions": "1 günəş (AM1.5G, 1000 W/m²), 25 °C, ideal kristal silikon (yalnız Auger + şüalanma "
            "rekombinasiyası) — Richter, Hermle, Glunz, IEEE J. Photovolt. 3 (2013) 1184"}
RS_K = 0.035   # assumption shared with the lens model: extra series-resistance loss per extra sun


def c5_study(ds: Dataset, C=5.0, tau=0.90, t_cooled_above_air=10.0, module: PV.Module | None = None,
             params: dict | None = None) -> dict:
    """Lens of aperture C × module area focusing direct light onto ONE flat module (best case: uniform spot),
    on a 2-axis tracker, vs. C ordinary modules covering the same total aperture (fixed and on the same tracker)."""
    m = module or PV.Module()
    P = S.values(params or S.default_params())
    A = m.area_m2
    pdc0, gam, tmax = m.v("pdc0_W"), m.v("gamma_pdc"), m.v("t_max_C")
    res = S.run(ds, params)
    geo = res.hourly["_geometry"]
    sun = geo["sun_up"].astype(float).to_numpy()
    w = ds.df
    # --- instantaneous example (DNI 1000 W/m², normal incidence, 25 °C air, 1 m/s) ------------------------------
    def inst(t_cell):
        E = 1000 * C * tau
        p = pdc0 * E / 1000 * max(0.0, 1 - RS_K * (E / 1000 - 1)) * (1 + gam * (t_cell - 25))
        return {"t_cell_C": t_cell, "P_W": p, "eta_aperture": p / (1000 * C * A)}
    t_pass = float(PV.t_cell_sapm(1000 * C * tau, 25.0, 1.0))
    t_plain = float(PV.t_cell_sapm(1000.0, 25.0, 1.0))
    p_plain = pdc0 * (1 + gam * (t_plain - 25))
    instant = {"passive": inst(t_pass), "cooled_60C": inst(60.0), "cooled_25C": inst(25.0),
               "plain_array": {"t_cell_C": t_plain, "P_W": C * p_plain, "eta_aperture": p_plain / (1000 * A)},
               "plain_array_stc_W": C * pdc0}
    # --- annual, Baku-type dataset -------------------------------------------------------------------------------
    eb = (geo["dni_cos_2axis"].to_numpy() * C * tau)                       # W/m² on the module (direct light only)
    rs = np.clip(1 - RS_K * (eb / 1000 - 1), 0, 1)
    t_p = PV.t_cell_sapm(eb, w["temp_air"].to_numpy(), w["wind_speed"].to_numpy())
    t_c = w["temp_air"].to_numpy() + t_cooled_above_air
    p_pass = np.where(eb > 0, pdc0 * eb / 1000 * rs * (1 + gam * (t_p - 25)), 0).clip(min=0)
    p_cool = np.where(eb > 0, pdc0 * eb / 1000 * rs * (1 + gam * (t_c - 25)), 0).clip(min=0)
    drive = C * P["tracker"]["drive_W"] * sun                                 # tracker drive scales with aperture (assumption)
    ctrl = np.full_like(sun, P["tracker"]["controller_W"])
    ap = C * A
    kwh = lambda x: energy_Wh(x, ds.step_h) / 1000.0
    hot = (eb > 0) & (t_p > tmax)
    annual = {
        "aperture_m2": ap,
        "lens_cooled": {"gross_kWh": kwh(p_cool), "drive_kWh": kwh(drive), "controller_kWh": kwh(ctrl),
                        "cooling_kWh": None, "cooling_status": "soyutma sərfi daxil edilməyib (ölçülməlidir)"},
        "lens_passive": {"gross_kWh": kwh(p_pass), "drive_kWh": kwh(drive), "controller_kWh": kwh(ctrl),
                         "hours_above_tmax": int(hot.sum()), "max_t_cell_C": float(np.max(t_p)),
                         "status": "model ekstrapolyasiyası: SAPM yüksək konsentrasiya üçün kalibrlənməyib"},
        "plain_fixed": {"gross_kWh": C * res.annual.loc["A_fixed", "gross_kWh_unit"], "drive_kWh": 0.0, "controller_kWh": 0.0},
        "plain_2axis": {"gross_kWh": C * res.annual.loc["A_2axis", "gross_kWh_unit"],
                        "drive_kWh": kwh(drive), "controller_kWh": kwh(ctrl)},
    }
    for k, v in annual.items():
        if isinstance(v, dict):
            aux = (v.get("drive_kWh") or 0) + (v.get("controller_kWh") or 0) + (v.get("cooling_kWh") or 0)
            v["net_kWh"] = v["gross_kWh"] - aux
            v["gross_kWh_m2_ap"] = v["gross_kWh"] / ap
            v["net_kWh_m2_ap"] = v["net_kWh"] / ap
    beam_share = float(geo["dni_cos_2axis"].sum() / max(geo["poa_2axis_global"].sum(), 1e-9))
    return {"C": C, "tau": tau, "t_cooled_above_air_K": t_cooled_above_air, "instant": instant, "annual": annual,
            "beam_share_2axis": beam_share, "si_limit": SI_LIMIT, "t_max_C": tmax}


def cpv_breakeven(ds: Dataset, params: dict | None = None, etas=np.round(np.arange(0.15, 0.4501, 0.005), 4),
                  taus=None) -> dict:
    """Smallest cell efficiency (within the searched range) at which C reaches A-2axis / A (net, same aperture)."""
    base = params or S.default_params()
    r0 = S.run(ds, base)
    ref_t, ref_f = r0.annual.loc["A_2axis", "net_kWh_unit"], r0.annual.loc["A_fixed", "net_kWh_unit"]
    taus = [S.values(base)["cpv"]["tau_optical"]] if taus is None else taus
    out = {"eta_range": [float(etas[0]), float(etas[-1])], "step": float(etas[1] - etas[0]), "rows": []}
    m = PV.Module()
    geo = r0.hourly["_geometry"]
    c = S.values(base)["cpv"]
    aux = r0.annual.loc["C_2axis", "aux_kWh_unit"]
    for tau in taus:
        nets = []
        for e in etas:
            cp = S.cpv_model(geo["dni_cos_2axis"], ds.df["temp_air"], geo["sun_up"], ds.df["dhi"],
                             {**c, "tau_optical": float(tau), "eta_cell_ref": float(e)}, m.area_m2)
            nets.append(energy_Wh(cp["gross_W"], ds.step_h) / 1000.0 - aux)
        nets = np.array(nets)
        find = lambda ref: (float(etas[np.argmax(nets >= ref)]) if (nets >= ref).any() else None)
        out["rows"].append({"tau": float(tau), "eta_vs_A_2axis": find(ref_t), "eta_vs_A_fixed": find(ref_f)})
    return out


def interannual(series: dict[int, Dataset], params=None) -> pd.DataFrame:
    rows = {}
    for y, ds in sorted(series.items()):
        a = S.run(ds, params).annual
        rows[y] = {k: a.loc[k, "net_kWh_m2_ap"] for k in S.SCEN}
        rows[y]["ghi_kWh_m2"] = float(ds.df["ghi"].sum() * ds.step_h / 1000)
    return pd.DataFrame(rows).T
