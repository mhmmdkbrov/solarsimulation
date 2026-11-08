"""Flat-plate module: parameters with provenance status, front-glass IAM, cell temperature, PVWatts DC."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pvlib

ST_DS, ST_MEAS, ST_ASM = "pasport", "ölçülüb", "fərziyyə"
DATASHEET = ("Trina Solar Vertex S+ TSM-NEG9R.28, TSM_EN_2023_B (MEA) — "
             "https://pages.trinasolar.com/rs/567-KJK-096/images/NEG9R.28_EN_2023_MEA%20region.pdf")


@dataclass
class Param:
    value: float | str
    unit: str
    status: str            # pasport | ölçülüb | fərziyyə
    source: str = ""
    note: str = ""


def _p(v, u, s, src="", note=""):
    return Param(v, u, s, src, note)


@dataclass
class Module:
    """Trina TSM-450NEG9R.28. Geometry of the cells is an assumption chosen to give exactly 92 % active area."""
    p: dict = field(default_factory=lambda: {
        "pdc0_W": _p(450.0, "W", ST_DS, DATASHEET, "STC: 1000 W/m², 25 °C, AM1,5; tolerans 0…+5 W"),
        "length_mm": _p(1762.0, "mm", ST_DS, DATASHEET),
        "width_mm": _p(1134.0, "mm", ST_DS, DATASHEET),
        "n_cells": _p(144, "-", ST_DS, DATASHEET),
        "gamma_pdc": _p(-0.0030, "1/°C", ST_DS, DATASHEET, "−0.30 %/°C"),
        "beta_voc": _p(-0.0024, "1/°C", ST_DS, DATASHEET),
        "alpha_isc": _p(0.0004, "1/°C", ST_DS, DATASHEET),
        "vmpp_V": _p(44.6, "V", ST_DS, DATASHEET), "impp_A": _p(10.09, "A", ST_DS, DATASHEET),
        "voc_V": _p(52.9, "V", ST_DS, DATASHEET), "isc_A": _p(10.74, "A", ST_DS, DATASHEET),
        "noct_C": _p(43.0, "°C", ST_DS, DATASHEET, "±2 °C; 800 W/m², 20 °C hava, 1 m/s külək"),
        "p_noct_W": _p(343.0, "W", ST_DS, DATASHEET),
        "t_max_C": _p(85.0, "°C", ST_DS, DATASHEET, "işçi temperatur −40…+85 °C"),
        "front_glass": _p("1,6 mm, yüksək ötürməli, AR örtüklü, termik bərkidilmiş", "-", ST_DS, DATASHEET),
        "glass_n": _p(1.526, "-", ST_ASM, "De Soto və b. 2006 / pvlib standartı", "AR örtüyü ayrıca modelləşdirilmir"),
        "glass_K": _p(4.0, "1/m", ST_ASM, "pvlib standartı"), "glass_L": _p(0.002, "m", ST_ASM, "pvlib standartı"),
        "active_fraction": _p(0.92, "-", ST_ASM, "", "modul səthinin hüceyrələrlə örtülü payı; ölçülməlidir"),
        "cell_w_mm": _p(182.0, "mm", ST_ASM, "", "üçə kəsilmiş 210R tipli hüceyrə; pasportda yoxdur"),
        "layout": _p("6 sütun × 24 sıra (portret)", "-", ST_ASM, "", "1762 × 1134 mm və 144 hüceyrə ilə uyğundur"),
    })

    def v(self, k):
        return self.p[k].value

    @property
    def area_m2(self) -> float:
        return self.v("length_mm") * self.v("width_mm") / 1e6

    @property
    def active_fraction(self) -> float:
        return float(self.v("active_fraction"))

    @property
    def cell_h_mm(self) -> float:
        """Derived so that the 144-cell geometry has exactly the assumed active fraction (one value for all models)."""
        return self.active_fraction * self.v("length_mm") * self.v("width_mm") / (self.v("n_cells") * self.v("cell_w_mm"))

    @property
    def eta_stc(self) -> float:
        return self.v("pdc0_W") / (1000 * self.area_m2)


# ------------------------------------------------------------------------------------------------------ front glass IAM
def iam_front(aoi_deg, surface_tilt, n=1.526, K=4.0, L=0.002) -> pd.DataFrame:
    """Beam: pvlib.iam.physical. Sky/ground: Marion (2017) integration of the same model (0.5° tilt grid, interpolated)."""
    aoi = np.asarray(aoi_deg, float)
    beam = np.asarray(pvlib.iam.physical(aoi, n=n, K=K, L=L), float)
    tilt = np.broadcast_to(np.asarray(surface_tilt, float), aoi.shape)
    grid = np.unique(np.concatenate([np.arange(0.0, 90.01, 0.5), np.unique(tilt)[:50]]))
    d = pvlib.iam.marion_diffuse("physical", grid, n=n, K=K, L=L)
    return pd.DataFrame({"beam": beam, "sky": np.interp(tilt, grid, np.asarray(d["sky"], float)),
                         "ground": np.interp(tilt, grid, np.asarray(d["ground"], float))})


def effective_irradiance(poa: pd.DataFrame, iam: pd.DataFrame, spectral=1.0, soiling=0.0) -> pd.Series:
    e = poa["beam"].to_numpy() * iam["beam"].to_numpy() + poa["sky"].to_numpy() * iam["sky"].to_numpy() \
        + poa["ground"].to_numpy() * iam["ground"].to_numpy()
    return pd.Series(e * spectral * (1 - soiling), index=poa.index)


# --------------------------------------------------------------------------------------------------- cell temperature
SAPM_MOUNTS = {k: v for k, v in pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"].items()}
# open_rack_glass_glass: a=-3.47, b=-0.0594, ΔT=3 (King et al. 2004) — v1 default


def t_cell_sapm(poa_global, temp_air, wind_speed, mount="open_rack_glass_glass", a=None, b=None, dT=None):
    pr = SAPM_MOUNTS[mount]
    return pvlib.temperature.sapm_cell(poa_global, temp_air, wind_speed,
                                       pr["a"] if a is None else a, pr["b"] if b is None else b,
                                       pr["deltaT"] if dT is None else dT)


def noct_check(module: Module, mount="open_rack_glass_glass", a=None) -> dict:
    """Cell temperature and power at NOCT conditions (800 W/m², 20 °C, 1 m/s) vs. the datasheet."""
    t = float(t_cell_sapm(800.0, 20.0, 1.0, mount, a=a))
    p = pvwatts(800.0, t, module.v("pdc0_W"), module.v("gamma_pdc"))
    p_ds_t = pvwatts(800.0, module.v("noct_C"), module.v("pdc0_W"), module.v("gamma_pdc"))
    return {"t_cell_model_C": t, "t_noct_datasheet_C": module.v("noct_C"), "dT_C": t - module.v("noct_C"),
            "p_model_W": p, "p_at_datasheet_noct_W": p_ds_t, "p_noct_datasheet_W": module.v("p_noct_W")}


def calibrate_sapm_a_to_noct(module: Module, mount="open_rack_glass_glass") -> float:
    """Calibration *method*: solve SAPM 'a' so that the model reproduces the datasheet NOCT (b, ΔT kept).
    The result is calibrated to the datasheet, not measured on site — status stays 'fərziyyə' until a test is done."""
    pr = SAPM_MOUNTS[mount]
    # T = 800·exp(a + b·1) + 20 + 0.8·ΔT  ->  a = ln((NOCT − 20 − 0.8ΔT)/800) − b
    return float(np.log((module.v("noct_C") - 20 - 0.8 * pr["deltaT"]) / 800.0) - pr["b"])


def pvwatts(e_eff, t_cell, pdc0, gamma):
    return np.maximum(pvlib.pvsystem.pvwatts_dc(e_eff, t_cell, pdc0, gamma), 0.0)
