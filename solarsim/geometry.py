"""Sun position and plane-of-array (POA) components — one implementation for notebook, CLI, tests and the site export.

Where each optical step is applied (applied once, never twice)
-------------------------------------------------------------
1. Transposition (Perez 1990, pvlib.irradiance.get_total_irradiance): GHI/DNI/DHI -> POA components
   beam  = DNI·max(cos AOI, 0)                  (geometric, no reflection loss)
   sky   = Perez sky diffuse on the plane      (isotropic + circumsolar + horizon terms)
   ground= GHI·albedo·(1 − cos β)/2            (isotropic ground reflection)
2. Module front-glass IAM (pvlib.iam.physical for beam, Marion 2017 integration for sky and ground):
   applied in pv.effective_irradiance only.
3. Add-on optics (scenario B, lens lab) multiply on top of (2) or replace the front-surface term, see optics/scenarios.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib

from .weather import Dataset


def solar_position(ds: Dataset) -> pd.DataFrame:
    """pvlib SPA at label + solpos_offset_h (the offset is applied here and only here)."""
    t = ds.df.index + pd.Timedelta(hours=float(ds.meta["solpos_offset_h"]))
    sp = pvlib.solarposition.get_solarposition(t, ds.site.latitude, ds.site.longitude,
                                               altitude=ds.site.elevation_m or 0.0,
                                               temperature=ds.df["temp_air"].to_numpy())
    sp.index = ds.df.index
    out = sp[["apparent_zenith", "zenith", "apparent_elevation", "elevation", "azimuth"]].copy()
    out["dni_extra"] = pvlib.irradiance.get_extra_radiation(ds.df.index)      # v1: evaluated at the label (Δ < 0.01 %)
    out["airmass_rel"] = pvlib.atmosphere.get_relative_airmass(out["apparent_zenith"])
    out["sun_up"] = out["apparent_elevation"] > 0
    return out


def poa_components(ds: Dataset, sp: pd.DataFrame, surface_tilt, surface_azimuth, albedo: float,
                   sky_model: str = "perez") -> pd.DataFrame:
    irr = pvlib.irradiance.get_total_irradiance(
        surface_tilt=surface_tilt, surface_azimuth=surface_azimuth,
        solar_zenith=sp["apparent_zenith"], solar_azimuth=sp["azimuth"],
        dni=ds.df["dni"], ghi=ds.df["ghi"], dhi=ds.df["dhi"], dni_extra=sp["dni_extra"],
        airmass=sp["airmass_rel"], albedo=albedo, model=sky_model)
    out = pd.DataFrame({"beam": irr["poa_direct"], "sky": irr["poa_sky_diffuse"], "ground": irr["poa_ground_diffuse"]},
                       index=ds.df.index).fillna(0.0).clip(lower=0.0)
    out["global"] = out["beam"] + out["sky"] + out["ground"]
    out["aoi"] = pvlib.irradiance.aoi(surface_tilt, surface_azimuth, sp["apparent_zenith"], sp["azimuth"])
    out["surface_tilt"] = surface_tilt
    out["surface_azimuth"] = surface_azimuth
    return out


def tracker_2axis(sp: pd.DataFrame):
    """Ideal 2-axis tracking (no angle limits, no row shading): normal points at the sun while it is up."""
    tilt = sp["apparent_zenith"].clip(0, 90).where(sp["sun_up"], 0.0)
    azim = sp["azimuth"].where(sp["sun_up"], 180.0)
    return tilt, azim


def sun_in_panel_frame(sp: pd.DataFrame, tilt_deg, azimuth_deg) -> pd.DataFrame:
    """Sun unit vector in the module frame: x = along the module width (horizontal), y = up the slope, z = normal.
    Returned as tan components (tx, ty) for the lens optics and cos of incidence. Same vectors are exported to the site."""
    el = np.radians(sp["apparent_elevation"].to_numpy())
    az = np.radians(sp["azimuth"].to_numpy())
    E, N, U = np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)
    b = np.radians(np.broadcast_to(np.asarray(tilt_deg, float), E.shape))
    g = np.radians(np.broadcast_to(np.asarray(azimuth_deg, float), E.shape))
    # module frame: normal n, width axis ex (horizontal, to the right when facing the module), slope axis ey = n × ex
    n = np.stack([np.sin(b) * np.sin(g), np.sin(b) * np.cos(g), np.cos(b)])
    ex = np.stack([-np.cos(g), np.sin(g), np.zeros_like(g)])        # azimuth 180° (south) -> ex = east, ey = up-slope
    ey = np.cross(n.T, ex.T).T
    s = np.stack([E, N, U])
    sx, sy, sz = (s * ex).sum(0), (s * ey).sum(0), (s * n).sum(0)
    ok = sz > 0.02
    return pd.DataFrame({"cos": sz, "tx": np.where(ok, sx / np.where(ok, sz, 1), 0.0),
                         "ty": np.where(ok, sy / np.where(ok, sz, 1), 0.0)}, index=sp.index)
