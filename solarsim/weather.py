"""Weather datasets: one container for every source, with full provenance metadata.

Time convention (applied everywhere)
-----------------------------------
* ``df.index`` is the time stamp *label* of the source, tz-aware UTC.
* ``meta["solpos_offset_h"]`` is the shift that must be added to the label to get the instant the irradiance refers to.
  It is applied exactly once, in ``geometry.solar_position``.
    - PVGIS 5.3 TMY: labels are HH:00, the offset is the response's ``inputs.location.irradiance_time_offset``.
    - PVGIS 5.3 seriescalc: labels already carry the minutes (e.g. HH:10) -> offset 0 (adding it again would double count).
    - PVGIS 6 TMY: no offset in the response -> offset estimated from clear-sky timing and labelled as an estimate.
* ``meta["step_h"]`` is the nominal time step; energy = Σ P·Δt with Δt = step_h for every present row.
  Missing rows are counted and reported, never filled silently.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

from .pvgis import load_raw
from .sites import PRESETS, Site

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
COLS = ["ghi", "dni", "dhi", "temp_air", "wind_speed"]
TMY_NOMINAL_YEAR = 1990   # v1 convention (PVGIS default coerce year); keeps the v1 regression exact


@dataclass
class Dataset:
    id: str
    site: Site
    df: pd.DataFrame
    meta: dict = field(default_factory=dict)

    @property
    def step_h(self) -> float:
        return float(self.meta["step_h"])

    def label(self) -> str:
        m = self.meta
        return f'{m["source_label"]} · {self.site.name} ({self.site.latitude:.4g}° N, {self.site.longitude:.4g}° E)'


# ---------------------------------------------------------------------------------------------------------------- utils
def infer_step_h(index: pd.DatetimeIndex) -> float:
    """Median spacing of the labels in hours (unit-safe: works for ns and us resolutions)."""
    d = (index[1:] - index[:-1]) / pd.Timedelta(hours=1)
    d = np.asarray(d, float)
    d = d[d > 0]
    return float(np.median(d)) if len(d) else 1.0


def completeness(index: pd.DatetimeIndex, step_h: float) -> dict:
    """Missing rows relative to a regular grid between the first and last label (same minute phase)."""
    if len(index) < 2:
        return {"n_rows": len(index), "n_expected": len(index), "n_missing": 0, "missing_hours": 0.0}
    full = pd.date_range(index[0], index[-1], freq=pd.Timedelta(hours=step_h))
    missing = full.difference(index)
    return {"n_rows": int(len(index)), "n_expected": int(len(full)), "n_missing": int(len(missing)),
            "missing_hours": float(len(missing) * step_h), "first_missing": [str(t) for t in missing[:5]]}


def energy_Wh(power_W: pd.Series | np.ndarray, step_h: float) -> float:
    """Σ P·Δt over the present rows (W × h = Wh)."""
    return float(np.nansum(np.asarray(power_W, float)) * step_h)


def _finish(ds_id, site, df, meta) -> Dataset:
    df = df.sort_index()
    if df.index.has_duplicates:
        raise ValueError(f"{ds_id}: duplicated time stamps")
    step = infer_step_h(df.index)
    meta = {**meta, "step_h": step, "completeness": completeness(df.index, step),
            "first_label_utc": str(df.index[0]), "last_label_utc": str(df.index[-1]),
            "timezone_calc": "UTC", "timezone_display": site.tz}
    for c in COLS:
        if c not in df:
            raise ValueError(f"{ds_id}: column {c} missing")
    df = df[COLS].astype(float)
    if df.isna().any().any():
        raise ValueError(f"{ds_id}: NaN values after loading — clean or report them in the loader")
    return Dataset(ds_id, site, df, meta)


def _pvgis_time(s: str) -> pd.Timestamp:
    return pd.Timestamp(dt.datetime.strptime(s, "%Y%m%d:%H%M"), tz="UTC")


def _site_with_elevation(key: str, elevation: float) -> Site:
    s = PRESETS[key]
    return Site(**{**s.to_dict(), "elevation_m": float(elevation)})


# ------------------------------------------------------------------------------------------------------- PVGIS 5.3 TMY
def pvgis53_tmy(key: str, year: int = TMY_NOMINAL_YEAR) -> Dataset:
    data, req = load_raw(RAW / key / "pvgis53_tmy.json.gz")
    loc, met = data["inputs"]["location"], data["inputs"]["meteo_data"]
    rows = data["outputs"]["tmy_hourly"]
    idx = pd.DatetimeIndex([_pvgis_time(r["time(UTC)"]).replace(year=year) for r in rows])
    df = pd.DataFrame({"ghi": [r["G(h)"] for r in rows], "dni": [r["Gb(n)"] for r in rows],
                       "dhi": [r["Gd(h)"] for r in rows], "temp_air": [r["T2m"] for r in rows],
                       "wind_speed": [r["WS10m"] for r in rows]}, index=idx)
    site = _site_with_elevation(key, loc["elevation"])
    meta = {
        "id": f"{key}_pvgis53_tmy", "kind": "TMY", "api": "PVGIS", "api_version": "5.3", "endpoint": req["endpoint"],
        "request_url": req["url"], "requested_utc": req["requested_utc"],
        "radiation_db": met["radiation_db"], "meteo_db": met["meteo_db"],
        "years": [met["year_min"], met["year_max"]],
        "months_selected": {m["month"]: m["year"] for m in data["outputs"]["months_selected"]},
        "use_horizon": met["use_horizon"], "horizon_db": met.get("horizon_db"),
        "horizon_applied_in_source": bool(met["use_horizon"]),
        "latitude": loc["latitude"], "longitude": loc["longitude"], "elevation_m": loc["elevation"],
        "irradiance_time_offset_h": float(loc["irradiance_time_offset"]),
        "solpos_offset_h": float(loc["irradiance_time_offset"]),
        "offset_rule": "vaxt nişanı HH:00 + irradiance_time_offset (cavabın metadatasından)",
        "nominal_year": year, "cleaning": [],
        "source_label": f'PVGIS 5.3 TMY ({met["radiation_db"]} + {met["meteo_db"]}, {met["year_min"]}–{met["year_max"]})',
    }
    return _finish(meta["id"], site, df, meta)


# ------------------------------------------------------------------------------------------- PVGIS 5.3 hourly series
def pvgis53_series(key: str, years=(2005, 2023)) -> dict[int, Dataset]:
    """Calendar years from seriescalc (angle 0 -> horizontal components). Returns {year: Dataset}."""
    data, req = load_raw(RAW / key / f"pvgis53_series_{years[0]}_{years[1]}.json.gz")
    loc, met = data["inputs"]["location"], data["inputs"]["meteo_data"]
    rows = data["outputs"]["hourly"]
    idx = pd.DatetimeIndex([_pvgis_time(r["time"]) for r in rows])
    gb_h = np.array([r["Gb(i)"] for r in rows], float)
    gd_h = np.array([r["Gd(i)"] for r in rows], float)
    h_sun = np.array([r["H_sun"] for r in rows], float)
    # DNI from the horizontal beam with PVGIS' own sun height for the same instant (consistent geometry)
    sin_h = np.sin(np.radians(h_sun))
    dni = np.where((gb_h > 0) & (sin_h > 0.02), gb_h / np.maximum(sin_h, 0.02), 0.0)
    dni_clipped = int(((gb_h > 0) & (sin_h <= 0.02)).sum())
    df = pd.DataFrame({"ghi": gb_h + gd_h, "dni": dni, "dhi": gd_h,
                       "temp_air": [r["T2m"] for r in rows], "wind_speed": [r["WS10m"] for r in rows],
                       "h_sun_pvgis": h_sun}, index=idx)
    site = _site_with_elevation(key, loc["elevation"])
    out = {}
    for y in range(years[0], years[1] + 1):
        part = df[df.index.year == y]
        meta = {
            "id": f"{key}_pvgis53_{y}", "kind": "calendar_year", "year": y, "api": "PVGIS", "api_version": "5.3",
            "endpoint": req["endpoint"], "request_url": req["url"], "requested_utc": req["requested_utc"],
            "radiation_db": met["radiation_db"], "meteo_db": met["meteo_db"], "years": [y, y],
            "use_horizon": met["use_horizon"], "horizon_db": met.get("horizon_db"),
            "horizon_applied_in_source": bool(met["use_horizon"]),
            "latitude": loc["latitude"], "longitude": loc["longitude"], "elevation_m": loc["elevation"],
            "irradiance_time_offset_h": None, "solpos_offset_h": 0.0,
            "offset_rule": "dəqiqələr vaxt nişanının içindədir (məs. HH:10); əlavə ofset yoxdur",
            "label_minute": int(part.index[0].minute),
            "cleaning": ([f"Günəşin hündürlüyü ≤ 1,15° olan {dni_clipped} sətirdə DNI = 0 götürülüb (bütün sıra üzrə)"]
                         if dni_clipped else []),
            "source_label": f'PVGIS 5.3 hourly {y} ({met["radiation_db"]} + {met["meteo_db"]})',
        }
        ds = _finish(meta["id"], site, part.drop(columns="h_sun_pvgis"), meta)
        ds.meta["h_sun_pvgis_deg"] = part["h_sun_pvgis"].to_numpy()   # kept for the timing test (not exported)
        out[y] = ds
    return out


# --------------------------------------------------------------------------------------------------------- PVGIS 6 TMY
def estimate_offset_h(df: pd.DataFrame, site: Site, candidates=np.arange(-0.75, 0.7501, 0.0833)) -> float:
    """Shift (h) that best aligns measured GHI with the clear-sky model on clear hours (least squares)."""
    loc = pvlib.location.Location(site.latitude, site.longitude, altitude=site.elevation_m or 0)
    best, best_err = 0.0, np.inf
    for s in candidates:
        t = df.index + pd.Timedelta(hours=float(s))
        cs = loc.get_clearsky(t, model="ineichen")["ghi"].to_numpy()
        g = df["ghi"].to_numpy()
        m = (cs > 200) & (g > 0.85 * cs) & (g < 1.15 * cs)     # clear hours under this shift
        if m.sum() < 200:
            continue
        err = float(np.mean((g[m] / cs[m] - 1) ** 2))          # mean squared relative deviation on clear hours
        if err < best_err:
            best, best_err = float(s), err
    return round(best, 4)


def pvgis6_tmy(key: str, year: int = TMY_NOMINAL_YEAR) -> Dataset:
    data, req = load_raw(RAW / key / "pvgis6_tmy.json.gz")
    t = data["typical_meteorological_year"]
    labels = pd.to_datetime(t["mean_global_horizontal_irradiance"]["time"])
    idx_src = pd.DatetimeIndex(labels).tz_localize("UTC")
    num = lambda k: pd.to_numeric(pd.Series(t[k]["values"]), errors="coerce").to_numpy(float)
    for k in ("mean_dry_bulb_temperature", "mean_wind_velocity", "mean_direct_normal_irradiance"):
        if list(t[k]["time"]) != list(t["mean_global_horizontal_irradiance"]["time"]):
            raise ValueError("PVGIS 6 TMY variables have different time axes")
    ghi, dni = num("mean_global_horizontal_irradiance"), num("mean_direct_normal_irradiance")
    ta, ws = num("mean_dry_bulb_temperature"), num("mean_wind_velocity")
    s0 = PRESETS[key]
    srcs = None
    try:
        srcs, _ = load_raw(RAW / key / "pvgis6_sources.json.gz")
    except FileNotFoundError:
        pass
    site = Site(**{**s0.to_dict()})
    try:   # elevation from the PVGIS 5.3 response of the same point (PVGIS 6 TMY does not return it)
        d53, _ = load_raw(RAW / key / "pvgis53_tmy.json.gz")
        site.elevation_m = float(d53["inputs"]["location"]["elevation"])
    except FileNotFoundError:
        site.elevation_m = 0.0
    cleaning = []
    # nominal year, chronological order (TMY months come from different years)
    idx = pd.DatetimeIndex([x.replace(year=year) for x in idx_src])
    df = pd.DataFrame({"ghi": ghi, "dni": dni, "temp_air": ta, "wind_speed": ws}, index=idx).sort_index()
    n_nan = {c: int(df[c].isna().sum()) for c in df}
    df = df.interpolate(limit=3, limit_direction="both")
    still = int(df.isna().sum().sum())
    df = df.fillna(0.0)
    names = {"ghi": "GHI", "dni": "DNI", "temp_air": "temperatur", "wind_speed": "külək"}
    cleaning.append("Boş (NaN) qiymətlər (" + ", ".join(f"{names[k]} {v}" for k, v in n_nan.items()) + f") xətti interpolyasiya ilə dolduruldu (≤ 3 saat); {still} qiymət 0 götürüldü")
    offset = estimate_offset_h(df, site)
    sp = pvlib.solarposition.get_solarposition(df.index + pd.Timedelta(hours=offset), site.latitude, site.longitude,
                                               altitude=site.elevation_m)
    elev = sp["apparent_elevation"].to_numpy()
    night = elev <= 0
    n_night = int(((df["ghi"].to_numpy() > 0) | (df["dni"].to_numpy() > 0))[night].sum())
    df.loc[night, ["ghi", "dni"]] = 0.0
    cleaning.append(f"Günəş üfüqün altında olduğu halda GHI/DNI > 0 olan {n_night} gecə sətri 0 götürüldü "
                    "(TMY ayları birləşən yerlərdə xətti keçidlər)")
    cz = np.clip(np.cos(np.radians(sp["zenith"].to_numpy())), 0, None)
    bh = df["dni"].to_numpy() * cz
    over = bh > df["ghi"].to_numpy()
    df["dni"] = np.where(over & (cz > 0.02), df["ghi"].to_numpy() / np.maximum(cz, 0.02), df["dni"].to_numpy())
    df["dhi"] = np.clip(df["ghi"].to_numpy() - df["dni"].to_numpy() * cz, 0, None)
    cleaning.append(f"DHI = GHI − DNI·cos(z) kimi hesablandı (API vermir); DNI·cos(z) GHI-dən böyük olan {int(over.sum())} sətirdə "
                    "DNI azaldıldı")
    years = sorted(set(int(v) for v in data["source_years"].values()))
    meta = {
        "id": f"{key}_pvgis6_tmy", "kind": "TMY", "api": "PVGIS", "api_version": "6 (v6; sənədlərə görə aktiv inkişaf mərhələsində)",
        "endpoint": req["endpoint"], "request_url": req["url"], "requested_utc": req["requested_utc"],
        "radiation_db": "SARAH-3 / ERA5 (PVGIS 6 əhatə sorğusu: " + ", ".join((srcs or {}).get("irradiance_sources", [])) + ")",
        "meteo_db": "ERA5-Land (PVGIS 6 sənədləri)", "years": [min(years), max(years)],
        "query_years": [req["params"]["start_time"][:4], req["params"]["end_time"][:4]],
        "months_selected": data["source_years"], "weighting_scheme": data.get("weighting_scheme"),
        "use_horizon": "PVGIS default horizon profile (not stated in the response)", "horizon_applied_in_source": None,
        "latitude": site.latitude, "longitude": site.longitude, "elevation_m": site.elevation_m,
        "irradiance_time_offset_h": None, "solpos_offset_h": offset,
        "offset_rule": f"API vermir; açıq səma vaxtlamasından {f"{offset:+.3f}".replace(".", ",")} saat kimi qiymətləndirildi (vaxt nişanları UTC)",
        "nominal_year": year, "cleaning": cleaning,
        "source_label": f"PVGIS 6 TMY (beta API, {min(years)}–{max(years)}, təmizlənib)",
    }
    return _finish(meta["id"], site, df, meta)


# --------------------------------------------------------------------------------------------------- user-supplied CSV
def user_csv(path: str | Path, site: Site, solpos_offset_h: float = 0.0, label: str = "istifadəçi CSV") -> Dataset:
    """Generic CSV: columns time (ISO, UTC), ghi, dni, dhi [W/m²], temp_air [°C], wind_speed [m/s]."""
    df = pd.read_csv(path)
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("time"), utc=True))
    meta = {"id": f"user_{Path(path).stem}", "kind": "user", "api": None, "solpos_offset_h": float(solpos_offset_h),
            "offset_rule": "istifadəçi tərəfindən verilib", "cleaning": [], "source_label": label,
            "latitude": site.latitude, "longitude": site.longitude, "elevation_m": site.elevation_m,
            "horizon_applied_in_source": None}
    return _finish(meta["id"], site, df, meta)


def sample_clear_sky(site: Site, year=2023, step_h=1.0) -> Dataset:
    """Clear-sky SAMPLE data (clearly labelled; never presented as a measured or PVGIS result)."""
    idx = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:59", freq=pd.Timedelta(hours=step_h), tz="UTC")
    loc = pvlib.location.Location(site.latitude, site.longitude, altitude=site.elevation_m or 0)
    cs = loc.get_clearsky(idx, model="ineichen")
    doy = idx.day_of_year.to_numpy()
    df = pd.DataFrame({"ghi": cs["ghi"], "dni": cs["dni"], "dhi": cs["dhi"],
                       "temp_air": 15 + 10 * np.sin(2 * np.pi * (doy - 110) / 365), "wind_speed": 3.0}, index=idx)
    meta = {"id": f"{site.key}_sample", "kind": "SAMPLE", "api": None, "solpos_offset_h": 0.0,
            "offset_rule": "sintetik məlumat", "cleaning": [], "source_label": "NÜMUNƏ MƏLUMAT (açıq səma modeli)",
            "horizon_applied_in_source": False}
    return _finish(meta["id"], site, df, meta)
