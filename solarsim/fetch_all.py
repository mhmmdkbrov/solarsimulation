"""Download all raw PVGIS data for the location presets.  Usage: python -m solarsim.fetch_all [site ...]"""
import sys
import time
from pathlib import Path

from . import pvgis
from .sites import PRESETS

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_site(key: str, years=(2005, 2023), force=False):
    s = PRESETS[key]
    jobs = {
        "pvgis53_tmy.json.gz": lambda: pvgis.fetch_pvgis53_tmy(s.latitude, s.longitude),
        "pvgis53_horizon.json.gz": lambda: pvgis.fetch_pvgis53_horizon(s.latitude, s.longitude),
        "pvgis53_optimal.json.gz": lambda: pvgis.fetch_pvgis53_optimal(s.latitude, s.longitude),
        f"pvgis53_series_{years[0]}_{years[1]}.json.gz": lambda: pvgis.fetch_pvgis53_series(s.latitude, s.longitude, *years),
        "pvgis6_sources.json.gz": lambda: pvgis.fetch_pvgis6_sources(s.latitude, s.longitude),
        "pvgis6_tmy.json.gz": lambda: pvgis.fetch_pvgis6_tmy(s.latitude, s.longitude),
    }
    for name, job in jobs.items():
        path = RAW / key / name
        if path.exists() and not force:
            print(f"{key}/{name}: cached")
            continue
        t0 = time.time()
        try:
            content, req = job()
        except Exception as exc:  # noqa: BLE001 — report and continue with the other files
            print(f"{key}/{name}: FAILED {exc!r}")
            continue
        pvgis.save_raw(path, content, req)
        print(f"{key}/{name}: {len(content) / 1e6:.2f} MB in {time.time() - t0:.0f} s")
        time.sleep(1.0)


if __name__ == "__main__":
    for k in (sys.argv[1:] or list(PRESETS)):
        fetch_site(k)
