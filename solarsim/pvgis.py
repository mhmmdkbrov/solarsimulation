"""PVGIS clients (server side / CLI only — PVGIS forbids browser AJAX calls, PVGIS 6 applies a strict CORS policy).

Every download is stored verbatim (gzip) together with the request URL, parameters and UTC request time, so a dataset
can be rebuilt offline and audited. Nothing here invents data: if a request fails, the error is raised to the caller.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
from pathlib import Path

import requests

PVGIS53 = "https://re.jrc.ec.europa.eu/api/v5_3/"
PVGIS6 = "https://photovoltaic-geographic-information-system.ec.europa.eu/api/v6/"
UA = {"User-Agent": "solarsim (github.com/mhmmdkbrov/solarsimulation)"}


def _get(url: str, params: dict, timeout: int = 180) -> tuple[bytes, dict]:
    r = requests.get(url, params=params, timeout=timeout, headers=UA)
    r.raise_for_status()
    req = {"url": r.url, "endpoint": url, "params": params, "http_status": r.status_code,
           "requested_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
    return r.content, req


def save_raw(path: Path, content: bytes, request: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as f:
        f.write(content)
    path.with_suffix("").with_suffix(".request.json").write_text(json.dumps(request, indent=1), encoding="utf-8")


def load_raw(path: Path) -> tuple[dict, dict]:
    with gzip.open(path, "rb") as f:
        data = json.loads(f.read().decode("utf-8"))
    req = json.loads(path.with_suffix("").with_suffix(".request.json").read_text(encoding="utf-8"))
    return data, req


def fetch_pvgis53_tmy(lat, lon, usehorizon=1):
    return _get(PVGIS53 + "tmy", dict(lat=lat, lon=lon, outputformat="json", usehorizon=usehorizon))


def fetch_pvgis53_series(lat, lon, startyear, endyear, usehorizon=1):
    """Hourly horizontal components (angle=0): Gb(i)=beam horizontal, Gd(i)=diffuse horizontal, Gr(i)=0."""
    return _get(PVGIS53 + "seriescalc", dict(lat=lat, lon=lon, startyear=startyear, endyear=endyear, components=1,
                                             angle=0, aspect=0, outputformat="json", usehorizon=usehorizon), timeout=300)


def fetch_pvgis53_horizon(lat, lon):
    return _get(PVGIS53 + "printhorizon", dict(lat=lat, lon=lon, outputformat="json"))


def fetch_pvgis53_optimal(lat, lon):
    """PVcalc with optimalangles=1 (crystalline Si, free-standing, 1 kWp, loss 0) — used for the preset tilt only."""
    return _get(PVGIS53 + "PVcalc", dict(lat=lat, lon=lon, peakpower=1, loss=0, optimalangles=1, mountingplace="free",
                                         pvtechchoice="crystSi", outputformat="json"))


def fetch_pvgis6_tmy(lat, lon, start="2014-01-01T00:00:00", end="2024-12-31T23:59:59"):
    return _get(PVGIS6 + "meteorological/typical-meteorological-year",
                dict(longitude=lon, latitude=lat, start_time=start, end_time=end, metadata="true"), timeout=300)


def fetch_pvgis6_sources(lat, lon):
    return _get(PVGIS6 + "coverage/available-sources-in-selected-location", dict(longitude=lon, latitude=lat))
