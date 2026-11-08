"""Command line: build a dataset for any coordinate (server-side PVGIS call or your own CSV) for the site.

  python -m solarsim.cli dataset --key seki --name "Şəki" --lat 41.19 --lon 47.17 --tz Asia/Baku --tilt 35 \
         --out seki.json [--source pvgis53|pvgis6] [--albedo 0.2] [--azimuth 180] [--add-to-site]
  python -m solarsim.cli dataset --key test --name "Test" --lat 40.4 --lon 49.9 --tz Asia/Baku --tilt 35 \
         --source csv --csv my_weather.csv --offset 0 --out test.json

Open the resulting JSON on any page with "Öz məlumat dəstini aç (JSON)". With --add-to-site it is also written to
docs/data/ and listed in docs/data/index.json. A dataset is written only if every step ran with real data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import build as B
from . import fetch_all as F
from . import pvgis
from . import weather as W
from .sites import PRESETS, Site


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m solarsim.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dataset")
    d.add_argument("--key", required=True); d.add_argument("--name", required=True)
    d.add_argument("--lat", type=float, required=True); d.add_argument("--lon", type=float, required=True)
    d.add_argument("--tz", required=True); d.add_argument("--tilt", type=float, required=True)
    d.add_argument("--azimuth", type=float, default=180.0); d.add_argument("--albedo", type=float, default=0.20)
    d.add_argument("--source", choices=["pvgis53", "pvgis6", "csv"], default="pvgis53")
    d.add_argument("--csv"); d.add_argument("--offset", type=float, default=0.0)
    d.add_argument("--elevation", type=float, default=0.0)
    d.add_argument("--out", required=True); d.add_argument("--add-to-site", action="store_true")
    a = ap.parse_args(argv)

    site = Site(a.key, a.name, a.lat, a.lon, a.tz, tilt_deg=a.tilt, azimuth_deg=a.azimuth, albedo=a.albedo,
                elevation_m=a.elevation, notes="CLI ilə yaradılıb")
    PRESETS[a.key] = site
    if a.source == "csv":
        if not a.csv:
            ap.error("--csv is required for --source csv")
        ds = W.user_csv(a.csv, site, a.offset, label=f"istifadəçi CSV ({Path(a.csv).name})")
    else:
        raw = F.RAW / a.key
        need = {"pvgis53_tmy.json.gz": lambda: pvgis.fetch_pvgis53_tmy(a.lat, a.lon)}      # also gives the elevation
        if a.source == "pvgis6":
            need["pvgis6_tmy.json.gz"] = lambda: pvgis.fetch_pvgis6_tmy(a.lat, a.lon)
            need["pvgis6_sources.json.gz"] = lambda: pvgis.fetch_pvgis6_sources(a.lat, a.lon)
        for name, job in need.items():
            if not (raw / name).exists():
                content, req = job()            # raises on HTTP errors: no dataset is written without real data
                pvgis.save_raw(raw / name, content, req)
        ds = (W.pvgis53_tmy if a.source == "pvgis53" else W.pvgis6_tmy)(a.key)
    data = B.build_dataset(ds, quick=True)
    out = Path(a.out)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{out} ({out.stat().st_size / 1e6:.2f} MB): {ds.label()}")
    if a.add_to_site:
        target = B.OUT / f"{ds.meta['id']}.json"
        target.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
        idx_path = B.OUT / "index.json"
        idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"datasets": []}
        idx["datasets"] = [x for x in idx["datasets"] if x["id"] != ds.meta["id"]] + [{
            "id": ds.meta["id"], "file": f"data/{target.name}", "site": a.key, "name": a.name, "label": ds.label(),
            "kind": ds.meta["kind"], "api_version": ds.meta.get("api_version") or "user",
            "size_kB": round(target.stat().st_size / 1e3)}]
        idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"added to {idx_path}")


if __name__ == "__main__":
    main()
