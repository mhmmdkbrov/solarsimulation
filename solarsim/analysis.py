"""Aggregations that must add up exactly to the annual totals (months, sky classes, years)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .weather import Dataset, energy_Wh

SKY_CLASSES = [  # by diffuse fraction DHI/GHI, only for hours with GHI > 10 W/m²
    ("clear", "Açıq, günəşli", 0.0, 0.3), ("hazy", "Dumanlı, tozlu", 0.3, 0.5),
    ("partly", "Qismən buludlu", 0.5, 0.9), ("overcast", "Tam buludlu", 0.9, 1.0001),
]
GHI_MIN = 10.0


def local_index(ds: Dataset, fixed_standard_offset: bool = True) -> pd.DatetimeIndex:
    """Local time for display/aggregation. TMY years are nominal, so the zone's *standard* offset is used
    (no DST; Baku has none since 2016, Almería shows CET winter time)."""
    if not fixed_standard_offset:
        return ds.df.index.tz_convert(ds.site.tz)
    import zoneinfo, datetime as dt
    z = zoneinfo.ZoneInfo(ds.site.tz)
    off = z.utcoffset(dt.datetime(2023, 1, 15)) or dt.timedelta(0)     # standard (winter) offset
    return (ds.df.index + off).tz_localize(None)


def monthly_kWh(ds: Dataset, power_W: pd.Series) -> pd.Series:
    li = local_index(ds)
    e = pd.Series(np.asarray(power_W, float) * ds.step_h / 1000.0, index=li)
    return e.groupby(li.month).sum().reindex(range(1, 13), fill_value=0.0)


def sky_class_index(ds: Dataset) -> pd.Series:
    g, d = ds.df["ghi"].to_numpy(), ds.df["dhi"].to_numpy()
    out = np.full(len(g), "low_light", dtype=object)
    lit = g > GHI_MIN
    kd = np.where(lit, d / np.where(lit, g, 1), np.nan)
    for key, _, lo, hi in SKY_CLASSES:
        out[lit & (kd >= lo) & (kd < hi)] = key
    out[lit & ~np.isin(out, [c[0] for c in SKY_CLASSES])] = "kd_above_1"   # DHI > GHI (data inconsistency)
    return pd.Series(out, index=ds.df.index)


def by_sky_class_kWh(ds: Dataset, power_W: pd.Series) -> pd.DataFrame:
    cls = sky_class_index(ds)
    e = pd.Series(np.asarray(power_W, float) * ds.step_h / 1000.0, index=ds.df.index)
    keys = [c[0] for c in SKY_CLASSES] + ["low_light", "kd_above_1"]
    return pd.DataFrame({"hours": cls.value_counts().reindex(keys, fill_value=0) * ds.step_h,
                         "kWh": e.groupby(cls).sum().reindex(keys, fill_value=0.0)})


def interannual(results_by_year: dict[int, pd.DataFrame], col="net_kWh_m2_ap") -> pd.DataFrame:
    tab = pd.DataFrame({y: r[col] for y, r in results_by_year.items()}).T.sort_index()
    stats = pd.DataFrame({"mean": tab.mean(), "std": tab.std(ddof=1), "min": tab.min(), "max": tab.max(),
                          "cv_percent": 100 * tab.std(ddof=1) / tab.mean()}).T
    return tab, stats
