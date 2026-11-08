"""Build the site datasets (docs/data/*.json) from raw PVGIS downloads. Usage:
    python -m solarsim.build                 # all presets, PVGIS 5.3 + PVGIS 6 TMY, full studies
    python -m solarsim.build --quick         # skip the slow studies (lens search, I–V validation, interannual)
Every number shown on the site comes from these files (nothing is typed by hand into the pages).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

from . import MODEL_VERSION
from . import analysis as AN
from . import geometry as G
from . import lenslab as LL
from . import optics as O
from . import pv as PV
from . import scenarios as S
from . import studies as ST
from . import weather as W
from .sites import PRESETS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data"
BASELINE_V1 = json.loads((ROOT / "tests" / "baseline_v1.json").read_text(encoding="utf-8"))


def _r(a, d):
    return [round(float(x), d) for x in np.asarray(a, float)]


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


def params_table(params, module):
    rows = []
    for k, p in module.p.items():
        rows.append({"group": "modul", "name": k, "value": p.value, "unit": p.unit, "status": p.status,
                     "source": p.source, "note": p.note})
    for g, d in params.items():
        for k, v in d.items():
            rows.append({"group": g, "name": k, "value": v[0], "unit": v[1], "status": v[2], "source": "", "note": v[3]})
    return rows


def hourly_export(ds, res, module):
    geo = res.hourly["_geometry"]
    li = AN.local_index(ds)
    gl = dict(n=module.v("glass_n"), K=module.v("glass_K"), L=module.v("glass_L"))
    P = S.values(res.inputs["params"])["retrofit"]
    lay = np.asarray(pvlib.iam.physical(geo["aoi_fixed"], n=P["n_layer"], K=P["K_layer"], L=P["L_layer"]), float)
    sp = pd.DataFrame({"apparent_elevation": geo["elevation"], "azimuth": geo["azimuth"]})
    fr = G.sun_in_panel_frame(sp, res.inputs["tilt"], res.inputs["azimuth"])
    # 2-axis POA components with front-glass IAM (for the browser A_2axis model)
    spf = G.solar_position(ds)
    tt, ta = G.tracker_2axis(spf)
    poa_t = G.poa_components(ds, spf, tt, ta, res.inputs["albedo"])
    iam_t = PV.iam_front(poa_t["aoi"], tt, **gl)
    f_beam = geo["poa_fixed_beam"] * geo["iam_beam_fixed"]
    f_diff = geo["poa_fixed_sky"] * geo["iam_sky_fixed"] + geo["poa_fixed_ground"] * geo["iam_ground_fixed"]
    return {
        "n": len(ds.df), "step_h": ds.step_h,
        "month": [int(x) for x in li.month], "doy": [int(x) for x in li.day_of_year], "hour": _r(li.hour + li.minute / 60, 3),
        "year_ok": [int(y == li.year[len(li) // 2]) for y in li.year],
        "ghi": _r(ds.df["ghi"], 1), "dni": _r(ds.df["dni"], 1), "dhi": _r(ds.df["dhi"], 1),
        "ta": _r(ds.df["temp_air"], 2), "ws": _r(ds.df["wind_speed"], 2), "sun": [int(x) for x in geo["sun_up"]],
        "elev": _r(geo["elevation"], 2), "azim": _r(geo["azimuth"], 2),
        "f_beam": _r(f_beam, 3), "f_diff": _r(f_diff, 3), "f_glob": _r(geo["poa_fixed_global"], 3), "f_layer": _r(lay, 5),
        "beam": _r(geo["poa_fixed_beam"], 2), "sky": _r(geo["poa_fixed_sky"], 2), "ground": _r(geo["poa_fixed_ground"], 2),
        "aoi": _r(geo["aoi_fixed"], 3), "tx": _r(fr["tx"], 5), "ty": _r(fr["ty"], 5), "cos": _r(fr["cos"], 5),
        "t_beam": _r(poa_t["beam"] * iam_t["beam"].to_numpy(), 3),
        "t_diff": _r(poa_t["sky"] * iam_t["sky"].to_numpy() + poa_t["ground"] * iam_t["ground"].to_numpy(), 3),
        "t_glob": _r(poa_t["global"], 3), "t_dnicos": _r(geo["dni_cos_2axis"], 3),
    }


def lens_tables(prep, iv=False, log=print):
    """Requested dioptre tests. Fast rule for the whole distance search; with iv=True the test points and the best
    distance are re-evaluated with the cell-level I–V model (every 6th daytime hour, topology T1)."""
    out = {"tests": [], "search": {"h_grid_mm": LL.H_GRID, "h_min_mm": LL.H_GRID[0], "electrical": "sürətli qayda (ən zəif hüceyrə, T1)",
                                   "iv": "hüceyrə I–V modeli, T1, hər 6-cı gündüz saatı" if iv else None,
                                   "note": "h ≥ 2,6 mm: hüceyrələr 1,6 mm şüşə + ~0,5 mm laminat altındadır"}}
    for P in (3, -3, 10, -10):
        for mode in ("array", "array_cyl", "big"):
            b = LL.best_h(prep, P, mode, 0.92)
            cand = dict(b["candidates"])
            pts = {name: cand[round(h, 3)] for name, h in LL.test_points(P)}
            r = b["result"]
            row = {"P": P, "mode": mode, "points": pts, "best_h": b["h"], "best_pct": r["delta_pct"],
                   "validity_best": r["validity"], "candidates": b["candidates"]}
            if iv:
                row["points_iv"] = {name: LL.annual(prep, O.LensConfig(P, h, mode, 0.92), "iv", "T1", every=6)["delta_pct"]
                                    for name, h in LL.test_points(P)}
                row["best_iv"] = LL.annual(prep, O.LensConfig(P, b["h"], mode, 0.92), "iv", "T1", every=6)["delta_pct"]
                log(f"    P={P:+} {mode}: best h {b['h']} fast {r['delta_pct']:+.2f}% iv {row['best_iv']:+.2f}%")
            out["tests"].append(row)
    return out


def lens_best_and_iv(prep):
    """Best lenslet geometry within physical limits (h ≥ 2.6 mm) for array and array_cyl; break-even transmittance."""
    out = {}
    for mode in ("array", "array_cyl"):
        best = None
        for P in np.arange(-20, 20.01, 0.5):
            for h in LL.H_GRID:
                r = LL.annual(prep, O.LensConfig(float(P), h, mode, 0.92), every=3)
                if best is None or r["ratio_to_null_lens"] > best[2]:
                    best = (float(P), h, r["ratio_to_null_lens"])
        P, h, _ = best
        exact = {tau: LL.annual(prep, O.LensConfig(P, h, mode, tau)) for tau in (0.92, 0.96, 1.0)}
        # break-even transmittance by bisection on the full annual function
        lo, hi = 0.80, 1.0
        if exact[1.0]["ratio_to_null_lens"] < 1:
            tau_be = None
        else:
            for _ in range(20):
                mid = 0.5 * (lo + hi)
                (lo, hi) = (mid, hi) if LL.annual(prep, O.LensConfig(P, h, mode, mid))["ratio_to_null_lens"] < 1 else (lo, mid)
            tau_be = 0.5 * (lo + hi)
        out[mode] = {"P": P, "h": h, "delta_pct": {str(t): exact[t]["delta_pct"] for t in exact},
                     "tau_breakeven": tau_be, "validity": exact[0.92]["validity"],
                     "search": {"P_range": [-20, 20], "P_step": 0.5, "h_grid_mm": LL.H_GRID, "tau": 0.92,
                                "note": "sınanmış diapazonda ən yaxşı; axtarış hər 3-cü gündüz saatı ilə, nəticə bütün saatlarla"}}
    # previous-model point (+13.5 D / 8 mm) recomputed with the new geometry
    v1pt = {}
    for mode in ("array", "array_cyl"):
        e = {tau: LL.annual(prep, O.LensConfig(13.5, 8.0, mode, tau)) for tau in (0.92, 0.96, 1.0)}
        v1pt[mode] = {"delta_pct": {str(t): e[t]["delta_pct"] for t in e}, "validity": e[0.92]["validity"]}
    out["v1_point_13p5D_8mm"] = {"v1": {"0.92": -4.9, "0.96": -0.8, "1.0": 3.3, "tau_breakeven_v1": 0.968}, "v2": v1pt}
    # I–V validation of the fast rule and topology sensitivity (every 6th daytime hour)
    iv = []
    for P, h, mode in [(3, 3, "big"), (10, 2.6, "big"), (-10, 100, "array"), (13.5, 8, "array"), (13.5, 8, "array_cyl"),
                       (out["array"]["P"], out["array"]["h"], "array")]:
        cfg = O.LensConfig(P, h, mode, 0.92)
        f = LL.annual(prep, cfg, "fast", every=6)
        t1 = LL.annual(prep, cfg, "iv", "T1", every=6)
        t3 = LL.annual(prep, cfg, "iv", "T3", every=6)
        iv.append({"P": P, "h": h, "mode": mode, "fast_T1_pct": f["delta_pct"], "iv_T1_pct": t1["delta_pct"],
                   "iv_T3_pct": t3["delta_pct"]})
    out["iv_validation"] = {"rows": iv, "note": "hər 6-cı gündüz saatı; T1 — yarım-modul topologiyası (əsas fərziyyə), T3 — sütun topologiyası (həssaslıq)"}
    # level-2 ray tracing vs paraxial (slope direction)
    geom = prep["geom"]
    tr = []
    for P, h, mode in [(3, 3, "array"), (3, 20, "array"), (5, 30, "array"), (10, 8, "array"), (13.5, 8, "array"),
                       (-3, 3, "array"), (-10, 100, "array"), (3, 3, "big")]:
        for th in (0.0, 20.0, 40.0):
            t = O.trace2d(O.LensConfig(P, h, mode), geom, th)
            par = None
            if mode != "big":   # paraxial share on cells along y (cylindrical equivalent, no x effect, no losses)
                s = O.spot_split(O.LensConfig(P, h, "array_cyl", tau=1.0, n=1.0, K=0.0), geom,
                                 np.array([0.0]), np.array([np.tan(np.radians(th))]))
                par = float((s["own"][0] + s["neighbours"][0]) / max(1 - s["off"][0], 1e-12) / (geom.CX / geom.PX))
            tr.append({"P": P, "h": h, "mode": mode, "theta": th, "trace": t, "paraxial_y_on_cells": par})
    out["trace2d"] = tr
    return out


def index_cases(ds, res, prep):
    """Representative hours per sky class (Apr–Sep, 11–14 h local) and the whole-year split incl. low-light hours."""
    li = AN.local_index(ds)
    cls = AN.sky_class_index(ds).to_numpy()
    geo = res.hourly["_geometry"]
    m = (li.month >= 4) & (li.month <= 9) & (li.hour >= 11) & (li.hour <= 14)
    reps = []
    for key, name, lo, hi in AN.SKY_CLASSES:
        sel = m & (cls == key)
        if sel.sum() == 0:
            reps.append({"key": key, "name": name, "n": 0}); continue
        f_beam = (geo["poa_fixed_beam"] * geo["iam_beam_fixed"]).to_numpy()[sel]
        f_diff = (geo["poa_fixed_sky"] * geo["iam_sky_fixed"] + geo["poa_fixed_ground"] * geo["iam_ground_fixed"]).to_numpy()[sel]
        P = S.values(res.inputs["params"])["retrofit"]
        lay = np.asarray(pvlib.iam.physical(geo["aoi_fixed"].to_numpy()[sel], n=P["n_layer"], K=P["K_layer"], L=P["L_layer"]), float)
        reps.append({"key": key, "name": name, "n": int(sel.sum()), "dni": float(ds.df["dni"].to_numpy()[sel].mean()),
                     "dhi": float(ds.df["dhi"].to_numpy()[sel].mean()), "ghi": float(ds.df["ghi"].to_numpy()[sel].mean()),
                     "f_beam": float(f_beam.mean()), "f_diff": float(f_diff.mean()), "f_layer": float(lay.mean()),
                     "f_glob": float(geo["poa_fixed_global"].to_numpy()[sel].mean()),
                     "ta": float(ds.df["temp_air"].to_numpy()[sel].mean()), "ws": float(ds.df["wind_speed"].to_numpy()[sel].mean())})
    return {"rep": reps, "rule": "DHI/GHI sinifləri yalnız GHI > 10 W/m² olan saatlar üçün; nümunə: aprel–sentyabr, 11–14 yerli saat ortası"}


def b_levels(ds):
    """Simple optical-layer model (B) at four quality levels, plus its ideal scenario."""
    lv = {
        "weak": {"tau_beam_normal": 0.88, "tau_diffuse": 0.78, "gap_recovery_beam": 0.0, "gap_recovery_diffuse": 0.0,
                 "nonuniformity_loss": 0.06, "extra_heating_K_per_kWm2": 5.0},
        "base": {},
        "good": {"tau_beam_normal": 0.96, "tau_diffuse": 0.90, "gap_recovery_beam": 0.7, "gap_recovery_diffuse": 0.3,
                 "nonuniformity_loss": 0.0, "extra_heating_K_per_kWm2": 0.0},
        "ideal": {"tau_beam_normal": 1.0, "tau_diffuse": 1.0, "gap_recovery_beam": 1.0, "gap_recovery_diffuse": 1.0,
                  "nonuniformity_loss": 0.0, "extra_heating_K_per_kWm2": 0.0},
    }
    out = {}
    for k, ch in lv.items():
        p = S.override(S.default_params(), {("retrofit", kk): v for kk, v in ch.items()})
        r = S.run(ds, p)
        out[k] = {"params": {**S.values(p)["retrofit"]}, "A_kWh_m2": float(r.annual.loc["A_fixed", "net_kWh_m2_ap"]),
                  "B_kWh_m2": float(r.annual.loc["B_fixed", "net_kWh_m2_ap"]),
                  "by_class_kWh_m2": {
                      "A": (AN.by_sky_class_kWh(ds, r.hourly["A_fixed"]["gross_W"])["kWh"] / r.areas["aperture_m2"]).to_dict(),
                      "B": (AN.by_sky_class_kWh(ds, r.hourly["B_fixed"]["gross_W"])["kWh"] / r.areas["aperture_m2"]).to_dict()},
                  "hours": AN.by_sky_class_kWh(ds, r.hourly["A_fixed"]["gross_W"])["hours"].to_dict()}
    out["ideal"]["label"] = ("sadə modelin ideal ssenarisi: aktiv sahə 92 %, boşluq işığı tam qaytarılır, ötürmə 100 %, "
                             "əlavə istilik və qeyri-bərabərlik itkisi sıfır")
    return out


def build_dataset(ds, quick=False, series=None, log=print):
    t0 = time.time()
    m = PV.Module()
    params = S.default_params()
    res = S.run(ds, params, m)
    log(f"  scenarios {time.time() - t0:.0f} s")
    A = m.area_m2
    monthly = {k: {"gross": (AN.monthly_kWh(ds, res.hourly[k]["gross_W"]) / A).tolist(),
                   "net": (AN.monthly_kWh(ds, res.hourly[k]["net_W"]) / A).tolist()} for k in S.SCEN}
    sky = {k: AN.by_sky_class_kWh(ds, res.hourly[k]["gross_W"]).assign(kWh_m2=lambda t: t["kWh"] / A).to_dict()
           for k in S.SCEN}
    out = {
        "version": {"model": MODEL_VERSION, "built_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()},
        "dataset": {**{k: v for k, v in ds.meta.items() if k not in ("h_sun_pvgis_deg",)}, "label": ds.label()},
        "site": ds.site.to_dict(), "inputs": {k: res.inputs[k] for k in ("tilt", "azimuth", "albedo")},
        "params": params_table(params, m), "areas": res.areas,
        "annual": res.annual.to_dict(orient="index"), "monthly": monthly, "sky_classes": sky,
        "warnings": res.warnings, "noct": PV.noct_check(m),
        "noct_calibrated_a": PV.calibrate_sapm_a_to_noct(m),
        "hourly": hourly_export(ds, res, m),
        "b_levels": b_levels(ds),
        "c5": ST.c5_study(ds),
        "cpv_breakeven": ST.cpv_breakeven(ds),
    }
    log(f"  base studies {time.time() - t0:.0f} s")
    prep = LL.prepare(ds, m)
    out["index_cases"] = index_cases(ds, res, prep)
    if not quick:
        out["lens"] = lens_tables(prep, iv=ds.meta["id"] == "baku_pvgis53_tmy", log=log)
        log(f"  lens tables {time.time() - t0:.0f} s")
    if ds.meta["id"] == "baku_pvgis53_tmy":
        v1p = S.override(params, {("cpv", "diffuse_in_acceptance"): False})
        r1 = S.run(ds, v1p, m)
        out["regression_v1"] = {"baseline": BASELINE_V1["annual"], "v2_compat": r1.annual.to_dict(orient="index"),
                                "v2_default": res.annual.to_dict(orient="index"),
                                "clear_sample_W_v1": BASELINE_V1["clear_sample_W"],
                                "lens_lab_v1": BASELINE_V1["lens_lab_tests"], "claims_v1": BASELINE_V1["claims_check"]["annual"]}
        if not quick:
            out["lens"].update(lens_best_and_iv(prep))
            log(f"  lens best + I–V {time.time() - t0:.0f} s")
    if series and not quick:
        tab = ST.interannual(series)
        out["interannual"] = {"table": tab.to_dict(orient="index"),
                              "stats": tab.agg(["mean", "std", "min", "max"]).to_dict(),
                              "source": next(iter(series.values())).meta["source_label"].rsplit(" ", 1)[0] + " 2005–2023"}
        log(f"  interannual {time.time() - t0:.0f} s")
    return _clean(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--sites", nargs="*", default=list(PRESETS))
    ap.add_argument("--sources", nargs="*", default=["pvgis53", "pvgis6"])
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for key in a.sites:
        series = None
        if "pvgis53" in a.sources:
            try:
                series = W.pvgis53_series(key)
            except FileNotFoundError:
                series = None
        for src in a.sources:
            loader = {"pvgis53": W.pvgis53_tmy, "pvgis6": W.pvgis6_tmy}[src]
            try:
                ds = loader(key)
            except FileNotFoundError as e:
                print(f"{key}/{src}: no raw data ({e}); skipped")
                continue
            print(f"{ds.meta['id']}:")
            data = build_dataset(ds, a.quick, series if src == "pvgis53" else None)
            f = OUT / f"{ds.meta['id']}.json"
            f.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            index.append({"id": ds.meta["id"], "file": f"data/{f.name}", "site": key, "name": ds.site.name,
                          "label": ds.label(), "kind": ds.meta["kind"], "api_version": ds.meta["api_version"],
                          "size_kB": round(f.stat().st_size / 1e3)})
            print(f"  -> {f.relative_to(ROOT)} ({f.stat().st_size / 1e6:.2f} MB)")
    old = OUT / "index.json"
    if old.exists():   # keep entries of datasets not rebuilt in this run
        prev = [d for d in json.loads(old.read_text(encoding="utf-8"))["datasets"] if d["id"] not in {i["id"] for i in index}]
        index = prev + index
    order = {k: i for i, k in enumerate(PRESETS)}
    index.sort(key=lambda d: (order.get(d["site"], 99), d["id"]))
    old.write_text(json.dumps({"model": MODEL_VERSION, "datasets": index}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
