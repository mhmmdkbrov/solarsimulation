"""Scenarios A (fixed PV), B (fixed PV + add-on optical layer, simple model), A-2axis and C (2-axis CPV).

Bookkeeping per scenario and hour: gross DC [W] − auxiliary [W] (tracker drive, controller, cooling) = net [W].
Annual energy = Σ P·Δt. Area concepts are kept apart (module surface, active cell area, aperture, ground).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pvlib

from . import geometry as G
from . import pv as PV
from .weather import Dataset, energy_Wh

SCEN = ["A_fixed", "B_fixed", "A_2axis", "C_2axis"]


def default_params() -> dict:
    """Baseline parameters (v1 values). Every entry: value, unit, status, note."""
    return {
        "system": {
            "albedo": (None, "-", "fərziyyə", "məkan seçimindən (0,20)"),
            "tilt_deg": (None, "°", "fərziyyə", "məkan seçimindən"),
            "azimuth_deg": (None, "°", "fərziyyə", "məkan seçimindən (180 = cənub)"),
            "sky_model": ("perez", "-", "elmi mənbə", "Perez və b. 1990"),
            "mount": ("open_rack_glass_glass", "-", "elmi mənbə", "SAPM, King və b. 2004"),
            "spectral": (1.0, "-", "fərziyyə", ""), "soiling": (0.0, "-", "fərziyyə", ""),
            "ground_coverage_ratio_fixed": (0.40, "-", "fərziyyə", "yalnız torpaq sahəsi göstəriciləri üçün sıra məsafəsi"),
            "ground_coverage_ratio_2axis": (0.25, "-", "fərziyyə", "2 oxlu izləyicilər daha geniş məsafə tələb edir"),
        },
        "retrofit": {
            "optics_enabled": (True, "-", "fərziyyə", ""),
            "coupling": ("air_gap", "-", "fərziyyə",
                         "air_gap: qatın IAM-ı × modul şüşəsinin IAM-ı; bonded: qat modulun ön səthini əvəz edir"),
            "tau_beam_normal": (0.92, "-", "fərziyyə", ""), "tau_diffuse": (0.84, "-", "fərziyyə", ""),
            "n_layer": (1.49, "-", "elmi mənbə", "PMMA"), "K_layer": (4.0, "1/m", "fərziyyə", ""),
            "L_layer": (0.003, "m", "fərziyyə", ""),
            "gap_recovery_beam": (0.30, "-", "fərziyyə", ""), "gap_recovery_diffuse": (0.10, "-", "fərziyyə", ""),
            "nonuniformity_loss": (0.02, "-", "fərziyyə", ""),
            "extra_heating_K_per_kWm2": (2.0, "K/(kW/m²)", "fərziyyə", ""),
            "aux_W": (0.0, "W", "fərziyyə", ""),
        },
        "cpv": {
            "aperture_unit_m2": (0.01, "m²", "fərziyyə", "10 × 10 sm linza"),
            "cell_area_m2": (1.0e-4, "m²", "fərziyyə", "1 × 1 sm fotoelement"),
            "tau_optical": (0.85, "-", "fərziyyə", ""),
            "intercept_optical": (0.95, "-", "fərziyyə", "ideal izləmədə fokuslanan işığın fotoelementə düşən payı"),
            "acceptance_half_angle_deg": (1.0, "°", "fərziyyə", "optikanın qəbul bucağı (90% nöqtəsi)"),
            "tracking_error_sigma_deg": (0.1, "°", "fərziyyə", "hər ox üzrə 1σ yönəltmə xətası"),
            "diffuse_in_acceptance": (True, "-", "fərziyyə",
                                      "qəbul konusunun içindəki izotrop səma işığı: DHI·sin²θa (v1-də 0)"),
            "eta_cell_ref": (0.30, "-", "fərziyyə", "25 °C-də; kommersiya məhsulu deyil"),
            "gamma_cell": (-0.0015, "1/°C", "fərziyyə", ""),
            "eta_valid_T_C": ((-20.0, 110.0), "°C", "fərziyyə", "η(T) modelinin etibarlı temperatur diapazonu"),
            "eta_valid_suns": ((1.0, 1000.0), "suns", "fərziyyə", "η_ref-in etibarlı konsentrasiya diapazonu"),
            "r_th_K_per_W": (4.0, "K/W", "fərziyyə", "hər linza üçün hüceyrə → ətraf, passiv radiator"),
            "fan_W": (0.0, "W", "fərziyyə", "aktiv soyutma, gündüz"),
        },
        "tracker": {
            "drive_W": (4.0, "W", "fərziyyə", "gündüz"), "controller_W": (0.5, "W", "fərziyyə", "24 saat"),
        },
    }


def values(params: dict) -> dict:
    return {g: {k: v[0] for k, v in d.items()} for g, d in params.items()}


def override(params: dict, changes: dict) -> dict:
    p = copy.deepcopy(params)
    for (g, k), val in changes.items():
        v = p[g][k]
        p[g][k] = (val, *v[1:])
    return p


@dataclass
class Result:
    hourly: dict                       # scenario -> DataFrame(gross_W, drive_W, controller_W, cooling_W, net_W, ...)
    annual: pd.DataFrame
    areas: dict
    warnings: dict
    inputs: dict = field(default_factory=dict)


# --------------------------------------------------------------------------------------------------- B: optical layer
def layer_effective(poa, iam, r, f_act):
    """Simple add-on optical layer (B). Returns effective irradiance on the cells [W/m² module-equivalent]."""
    ratio = (1 - f_act) / f_act
    if not r["optics_enabled"]:
        return poa["beam"] * iam["beam"].to_numpy() + poa["sky"] * iam["sky"].to_numpy() + poa["ground"] * iam["ground"].to_numpy()
    lay_beam = np.asarray(pvlib.iam.physical(poa["aoi"], n=r["n_layer"], K=r["K_layer"], L=r["L_layer"]), float)
    if r["coupling"] == "air_gap":       # layer surface + module glass surface both reflect
        fb, fs, fg = iam["beam"].to_numpy(), iam["sky"].to_numpy(), iam["ground"].to_numpy()
    elif r["coupling"] == "bonded":      # optically bonded: the module's air/glass interface disappears
        fb = fs = fg = 1.0
    else:
        raise ValueError(r["coupling"])
    beam = poa["beam"] * fb * r["tau_beam_normal"] * lay_beam * (1 + ratio * r["gap_recovery_beam"])
    # tau_diffuse is the hemispherical transmittance of the layer (it already contains the layer's angular loss)
    dfac = r["tau_diffuse"] * (1 + ratio * r["gap_recovery_diffuse"])
    return beam + poa["sky"] * fs * dfac + poa["ground"] * fg * dfac


# ------------------------------------------------------------------------------------------------------------- C: CPV
def cpv_model(dni_cos, temp_air, sun_up, dhi, c: dict, aperture_total_m2: float) -> pd.DataFrame:
    """P_in = DNI·A_ap·max(cos AOI,0) (+ diffuse inside the acceptance cone); P_cell = P_in·τ·intercept.
    Geometric concentration C = A_ap/A_cell is used only for the cell intensity P_cell/A_cell — never to scale P_in."""
    n_units = aperture_total_m2 / c["aperture_unit_m2"]
    C_geo = c["aperture_unit_m2"] / c["cell_area_m2"]
    th_a, sig = np.radians(c["acceptance_half_angle_deg"]), np.radians(c["tracking_error_sigma_deg"])
    # radial pointing error of a 2-axis tracker with independent Gaussian errors per axis -> Rayleigh distribution
    track_factor = 1.0 - np.exp(-th_a ** 2 / (2 * sig ** 2)) if sig > 0 else 1.0
    intercept = c["intercept_optical"] * track_factor
    p_in_beam = dni_cos * aperture_total_m2
    p_in_diff = (dhi * np.sin(th_a) ** 2 * aperture_total_m2) if c["diffuse_in_acceptance"] else 0.0 * dni_cos
    p_in = p_in_beam + p_in_diff
    p_cell = p_in * c["tau_optical"] * intercept
    q = p_cell / n_units                                   # W absorbed per cell (all non-electric power -> heat)
    R, e0, g = c["r_th_K_per_W"], c["eta_cell_ref"], c["gamma_cell"]
    den = 1 + R * q * e0 * g
    t = (temp_air + R * q * (1 - e0) + R * q * e0 * g * 25.0) / den
    eta = np.clip(e0 * (1 + g * (t - 25.0)), 0, None)
    p_el = p_cell * eta
    suns = p_cell / (n_units * c["cell_area_m2"]) / 1000.0
    lo, hi = c["eta_valid_T_C"]
    slo, shi = c["eta_valid_suns"]
    flags = pd.DataFrame({
        "den_small": np.abs(den) < 0.2,
        "t_out_of_range": (p_cell > 0) & ((t < lo) | (t > hi)),
        "suns_out_of_range": (p_cell > 0) & ((suns < slo) | (suns > shi)),
        "eta_nonphysical": (p_cell > 0) & ((eta <= 0) | (eta >= 0.5)),
    })
    return pd.DataFrame({"p_in_W": p_in, "p_in_diffuse_W": p_in_diff, "p_cell_W": p_cell, "t_cell_C": t, "eta": eta,
                         "gross_W": p_el, "heat_W": p_cell - p_el, "suns": suns, "intercept": intercept,
                         "C_geo": C_geo}).join(flags)


# ----------------------------------------------------------------------------------------------------------- run all
def run(ds: Dataset, params: dict | None = None, module: PV.Module | None = None) -> Result:
    params = params or default_params()
    P = values(params)
    m = module or PV.Module()
    s, r, c, tr = P["system"], P["retrofit"], P["cpv"], P["tracker"]
    tilt = ds.site.tilt_deg if s["tilt_deg"] is None else s["tilt_deg"]
    azim = ds.site.azimuth_deg if s["azimuth_deg"] is None else s["azimuth_deg"]
    albedo = ds.site.albedo if s["albedo"] is None else s["albedo"]
    pdc0, gam = m.v("pdc0_W"), m.v("gamma_pdc")
    gl = dict(n=m.v("glass_n"), K=m.v("glass_K"), L=m.v("glass_L"))

    sp = G.solar_position(ds)
    poa_f = G.poa_components(ds, sp, tilt, azim, albedo, s["sky_model"])
    iam_f = PV.iam_front(poa_f["aoi"], tilt, **gl); iam_f.index = ds.df.index
    tt, ta = G.tracker_2axis(sp)
    poa_t = G.poa_components(ds, sp, tt, ta, albedo, s["sky_model"])
    iam_t = PV.iam_front(poa_t["aoi"], tt, **gl); iam_t.index = ds.df.index

    w = ds.df
    tc_f = PV.t_cell_sapm(poa_f["global"], w["temp_air"], w["wind_speed"], s["mount"])
    tc_t = PV.t_cell_sapm(poa_t["global"], w["temp_air"], w["wind_speed"], s["mount"])
    e_a = PV.effective_irradiance(poa_f, iam_f, s["spectral"], s["soiling"])
    e_t = PV.effective_irradiance(poa_t, iam_t, s["spectral"], s["soiling"])
    e_b = layer_effective(poa_f, iam_f, r, m.active_fraction) * s["spectral"] * (1 - s["soiling"])
    tc_b = tc_f + r["extra_heating_K_per_kWm2"] * poa_f["global"] / 1000.0
    mism_b = (1 - r["nonuniformity_loss"]) if r["optics_enabled"] else 1.0

    zero = pd.Series(0.0, index=w.index)
    sun = sp["sun_up"].astype(float)
    hourly = {}
    hourly["A_fixed"] = pd.DataFrame({"gross_W": PV.pvwatts(e_a, tc_f, pdc0, gam), "drive_W": zero,
                                      "controller_W": zero, "cooling_W": zero, "t_cell_C": tc_f, "e_eff_Wm2": e_a})
    hourly["B_fixed"] = pd.DataFrame({"gross_W": PV.pvwatts(e_b, tc_b, pdc0, gam) * mism_b,
                                      "drive_W": zero, "controller_W": zero + r["aux_W"], "cooling_W": zero,
                                      "t_cell_C": tc_b, "e_eff_Wm2": e_b})
    hourly["A_2axis"] = pd.DataFrame({"gross_W": PV.pvwatts(e_t, tc_t, pdc0, gam), "drive_W": tr["drive_W"] * sun,
                                      "controller_W": zero + tr["controller_W"], "cooling_W": zero,
                                      "t_cell_C": tc_t, "e_eff_Wm2": e_t})
    dni_cos = w["dni"] * np.cos(np.radians(poa_t["aoi"])).clip(lower=0)
    cp = cpv_model(dni_cos, w["temp_air"], sp["sun_up"], w["dhi"], c, m.area_m2)
    hourly["C_2axis"] = cp.assign(drive_W=tr["drive_W"] * sun, controller_W=zero + tr["controller_W"],
                                  cooling_W=c["fan_W"] * sun)
    for k, h in hourly.items():
        h["aux_W"] = h["drive_W"] + h["controller_W"] + h["cooling_W"]
        h["net_W"] = h["gross_W"] - h["aux_W"]

    A = m.area_m2
    areas = {
        "module_surface_m2": A, "aperture_m2": A,
        "cell_area_flat_m2": A * m.active_fraction,
        "cell_area_cpv_m2": (A / c["aperture_unit_m2"]) * c["cell_area_m2"],
        "ground_fixed_m2": A / s["ground_coverage_ratio_fixed"], "ground_2axis_m2": A / s["ground_coverage_ratio_2axis"],
    }
    rows = {}
    for k in SCEN:
        h = hourly[k]
        e = {col: energy_Wh(h[col], ds.step_h) / 1000.0 for col in ("gross_W", "drive_W", "controller_W", "cooling_W", "aux_W", "net_W")}
        ground = areas["ground_2axis_m2"] if "2axis" in k else areas["ground_fixed_m2"]
        rows[k] = {"gross_kWh_unit": e["gross_W"], "drive_kWh_unit": e["drive_W"], "controller_kWh_unit": e["controller_W"],
                   "cooling_kWh_unit": e["cooling_W"], "aux_kWh_unit": e["aux_W"], "net_kWh_unit": e["net_W"],
                   "gross_kWh_m2_ap": e["gross_W"] / A, "net_kWh_m2_ap": e["net_W"] / A,
                   "net_kWh_m2_ground": e["net_W"] / ground}
    annual = pd.DataFrame(rows).T
    flags = cp[["den_small", "t_out_of_range", "suns_out_of_range", "eta_nonphysical"]]
    tot = max(energy_Wh(cp["gross_W"], ds.step_h), 1e-9)
    warnings = {"C_2axis": {k: {"hours": int(v), "energy_share": energy_Wh(cp["gross_W"][flags[k]], ds.step_h) / tot}
                            for k, v in flags.sum().items()},
                "dataset_completeness": ds.meta.get("completeness")}
    hourly["_geometry"] = pd.DataFrame({"sun_up": sp["sun_up"], "aoi_fixed": poa_f["aoi"], "aoi_2axis": poa_t["aoi"],
                                        "poa_fixed_beam": poa_f["beam"], "poa_fixed_sky": poa_f["sky"],
                                        "poa_fixed_ground": poa_f["ground"], "poa_fixed_global": poa_f["global"],
                                        "poa_2axis_global": poa_t["global"], "dni_cos_2axis": dni_cos,
                                        "iam_beam_fixed": iam_f["beam"].to_numpy(), "iam_sky_fixed": iam_f["sky"].to_numpy(),
                                        "iam_ground_fixed": iam_f["ground"].to_numpy(),
                                        "elevation": sp["apparent_elevation"], "azimuth": sp["azimuth"]})
    return Result(hourly, annual, areas, warnings, {"tilt": tilt, "azimuth": azim, "albedo": albedo, "params": params})
