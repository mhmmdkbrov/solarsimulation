"""Export hourly model inputs (from the notebook's own code) for the interactive web simulator.
Run from the project dir: .venv/Scripts/python <this> <out.json>"""
import json
import sys

import nbformat
import numpy as np

nb = nbformat.read("solar_simulation.ipynb", 4)
g = {}
for i in (1, 3, 5, 6, 8, 10):
    exec(nb.cells[i].source, g)

pvlib, pd = g["pvlib"], g["pd"]
w, geo, R = g["weather"], g["geo"], g["RETROFIT"]
irr_f, iam_f, irr_t, iam_t = g["irr_fixed"], g["iam_fixed"], g["irr_trk"], g["iam_trk"]
loc = w.index.tz_convert(g["LOCAL_TZ"])

layer_iam = np.asarray(pvlib.iam.physical(irr_f["aoi"], n=R["n_layer"], K=R["K_layer"], L=R["L_layer"]), float)


def r(a, d=2):
    return [round(float(x), d) for x in np.asarray(a, float)]


data = {
    "meta": {
        "source": g["DATA_LABEL"], "is_sample": bool(g["IS_SAMPLE"]), "area_m2": g["A_COLLECT_M2"],
        "tilt": g["SYSTEM"]["tilt_deg"], "azimuth": g["SYSTEM"]["azimuth_deg"],
        "start_local": str(loc[0]), "tz": "UTC+4",
        "module": {k: g["MODULE"][k] for k in ("pdc0_W", "gamma_pdc_per_C", "active_area_fraction")},
        "sapm": {k: g["SYSTEM"][k] for k in ("sapm_a", "sapm_b", "sapm_dT")},
        "layer_n": R["n_layer"],
    },
    "month": [int(m) for m in loc.month], "doy": [int(d) for d in loc.dayofyear], "hour": [int(h) for h in loc.hour],
    "year_ok": [int(y == g["TMY_YEAR"]) for y in loc.year],
    "ghi": r(w["ghi"], 1), "dni": r(w["dni"], 1), "dhi": r(w["dhi"], 1),
    "ta": r(w["temp_air"], 2), "ws": r(w["wind_speed"], 2),
    "sun": [int(s) for s in geo["sun_up"]],
    # fixed plane
    "f_glob": r(irr_f["poa_global"]), "f_beam": r(irr_f["poa_direct"] * iam_f["beam"], 3),
    "f_diff": r(irr_f["poa_sky_diffuse"] * iam_f["sky"] + irr_f["poa_ground_diffuse"] * iam_f["ground"], 3),
    "f_layer": r(layer_iam, 5),
    # 2-axis plane
    "t_glob": r(irr_t["poa_global"]), "t_beam": r(irr_t["poa_direct"] * iam_t["beam"], 3),
    "t_diff": r(irr_t["poa_sky_diffuse"] * iam_t["sky"] + irr_t["poa_ground_diffuse"] * iam_t["ground"], 3),
    "t_dnicos": r(w["dni"] * np.cos(np.radians(irr_t["aoi"])).clip(lower=0), 3),
}

# reference results from the notebook code (base parameters) for verification of the JS port
res = g["run_scenarios"]()
data["reference_net_kWh"] = {s: float(res[s]["net_W"].sum() / 1000) for s in g["SCENARIOS"]}
json.dump(data, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("reference net kWh:", data["reference_net_kWh"])
