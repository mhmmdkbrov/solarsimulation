"""Universal optics: catalogue numbers, Rev B analytic baseline, geometry edge cases, comparisons, JS = Python."""
import copy
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pytest

from solarsim import uoptics as U

ROOT = Path(__file__).resolve().parent.parent
BLUR = lambda h: 2 * h * math.tan(math.radians(U.SUN_HALF_DEG))


def setp(cfg, **kw):
    for k, val in kw.items():
        cfg["params"][k]["value"] = val
    return cfg


# ---------------------------------------------------------------------------------------- LFS150150 / Rev B
def test_lfs150150_areas_and_concentration():
    c = U.preset("lfs150150")
    A = U.areas(c)
    assert A["aperture_one_m2"] == pytest.approx(0.075, abs=1e-12)        # 150 × 500 mm
    assert A["C_g"] == pytest.approx(2.0, abs=1e-12)                       # 500 × 75 mm receiver
    assert A["n"] == 18 and A["aperture_m2"] == pytest.approx(1.35, abs=1e-12)
    assert c["params"]["f_mm"] == {"value": 150, "status": U.IST, "note": "±5%"}
    assert c["params"]["tau0"]["status"] == U.FRZ                          # no transmission figure published


def test_rev_b_analytic_baseline():
    """Normal incidence, DNI 1 000 W/m², η 22 %, effective optical share 85 %, thermal 0,95, electrical 0,98."""
    r = U.analytic(U.preset("lfs150150"), dni=1000.0)
    assert r["per_unit_W"] == pytest.approx(0.075 * 1000 * 0.85 * 0.22 * 0.95 * 0.98, rel=1e-12)
    assert round(r["per_unit_W"], 2) == 13.06 and round(r["total_W"], 2) == 235.03


def test_detailed_model_separates_material_transmission_from_intercept():
    """If 85 % is only the material transmission, light that misses the receiver is counted separately."""
    c = setp(U.preset("lfs150150"), tau0=0.85)
    r = U.instant(c, dni=1000.0)
    w_strip = abs(1 - 75 / 150) * 150 + BLUR(75)
    cap = (75 / w_strip) * (500 / (500 + BLUR(75)))                         # strip wider than the receiver by the sun blur
    assert r["capture_beam"] == pytest.approx(cap, rel=1e-12)
    assert r["on_receiver_W"] == pytest.approx(1350 * 0.85 * cap, rel=1e-12)
    assert r["off_receiver_W"] == pytest.approx(1350 * 0.85 * (1 - cap), rel=1e-12)
    assert r["optical_loss_W"] == pytest.approx(1350 * 0.15, rel=1e-12)
    assert sum(r["shares"].values()) == pytest.approx(1.0, abs=1e-12)


def test_concentration_is_not_applied_twice():
    c = U.preset("lfs150150")
    r = U.instant(c, dni=1000.0)
    assert r["on_receiver_W"] <= r["P_in_W"]
    assert r["E_rec_mean_Wm2"] == pytest.approx(1000 * r["tau_beam"] * r["capture_beam"] * U.areas(c)["C_g"], rel=1e-12)
    assert r["E_rec_mean_Wm2"] == pytest.approx(r["on_receiver_W"] / U.areas(c)["receiver_m2"], rel=1e-12)


# ---------------------------------------------------------------------------------------- angle behaviour
def test_light_leaves_receiver_as_transverse_angle_grows():
    c = U.preset("lfs150150")
    caps = [U.instant(c, theta_y_deg=t)["capture_beam"] for t in (0, 5, 10, 20, 30)]
    assert all(a > b for a, b in zip(caps, caps[1:]))
    # 10° across the focusing axis: strip shifted by h·tan θ
    w = 75 + BLUR(75)
    s = 75 * math.tan(math.radians(10))
    expect = (min(37.5, s + w / 2) - max(-37.5, s - w / 2)) / w * (500 / (500 + BLUR(75)))
    assert caps[2] == pytest.approx(expect, rel=1e-12)
    assert U.instant(c, theta_y_deg=10)["off_receiver_W"] > U.instant(c, theta_y_deg=0)["off_receiver_W"]


def test_linear_fresnel_longitudinal_angle_shortens_focus_and_loses_ends():
    c = U.preset("lfs150150")
    sp = U.spot(c, np.array([math.tan(math.radians(30))]), np.array([0.0]))
    assert sp["wy"][0] == pytest.approx(abs(1 - 75 / (150 * math.cos(math.radians(30)))) * 150 + BLUR(75), rel=1e-12)
    cap = U.capture(c, math.tan(math.radians(30)), 0.0)[0]
    lx = 500 + BLUR(75)
    sx = 75 * math.tan(math.radians(30))
    end = (min(250, sx + lx / 2) - max(-250, sx - lx / 2)) / lx
    assert cap == pytest.approx(end * min(1.0, 75 / sp["wy"][0]), rel=1e-12)


def test_array_edges_separate_receivers():
    """Shift of exactly one pitch: every lens lights its neighbour's receiver except the last one in the row."""
    c = U.preset("lfs150150")
    t = 150 / 75                                                           # h·tan θ = 150 mm = pitch
    cap = U.capture(c, 0.0, t)[0]
    w = 75 + BLUR(75)
    assert cap == pytest.approx(17 / 18 * 75 / w * 500 / (500 + BLUR(75)), rel=1e-12)


def test_array_edges_shared_receiver():
    """Flat-cover array over one shared receiver: at an angle, light of the edge row falls past the panel edge."""
    c = setp(U.preset("flat"), nx=4, ny=1, ap_x_mm=250.0, ap_y_mm=1000.0, pitch_x_mm=250.0, pitch_y_mm=1000.0,
             rec_x_mm=1000.0, rec_y_mm=1000.0, h_mm=100.0)
    c["layout"] = "shared"
    tx = 50 / 100                                                          # 50 mm shift
    cap = U.capture(c, tx, 0.0)[0]
    b = BLUR(100)
    wx, wy = 250 + b, 1000 + b
    per = [(min(500, cx + 50 + wx / 2) - max(-500, cx + 50 - wx / 2)) / wx for cx in (-375, -125, 125, 375)]
    assert cap == pytest.approx(np.mean(per) * 1000 / wy, rel=1e-12)
    assert cap < 0.96


# ---------------------------------------------------------------------------------------- other optics
def test_flat_cover():
    c = U.preset("flat")
    r = U.instant(c)
    assert r["areas"]["C_g"] == pytest.approx(1.0)
    assert r["capture_beam"] == pytest.approx(1000 / (1000 + BLUR(5)) ** 1 * 1000 / (1000 + BLUR(5)), rel=1e-12)
    assert r["tau_beam"] == pytest.approx(0.92, rel=1e-12)
    assert r["validity"]["reliability"] is None                           # no paraxial approximation needed
    # angle: transmission falls (two Fresnel surfaces), the shadow shifts by h·tan θ
    r60 = U.instant(c, theta_x_deg=60)
    th, n = math.radians(60), 1.5
    tr = math.asin(math.sin(th) / n)
    t60 = 1 - 0.5 * ((math.sin(th - tr) / math.sin(th + tr)) ** 2 + (math.tan(th - tr) / math.tan(th + tr)) ** 2)
    t0 = 1 - ((n - 1) / (n + 1)) ** 2
    assert r60["tau_beam"] == pytest.approx(0.92 * (t60 / t0) ** 2, rel=1e-12)
    assert r60["capture_beam"] < r["capture_beam"]


def test_flat_lossless_cover_equals_bare_baseline():
    c = setp(U.preset("flat"), tau0=1.0, n_mat=1.0, h_mm=1e-6)
    r = U.instant(c, dni=1000.0)
    assert r["compare_A"]["ratio"] == pytest.approx(1.0, abs=1e-6)
    assert r["compare_B"]["ratio"] == pytest.approx(1.0, abs=1e-6)        # same cells, same collecting area here


def test_negative_lens_spreads_light():
    c = U.preset("negative")                                               # −5 D, h = 50 mm, Ø 100 mm, receiver 100 × 100
    sp = U.spot(c, np.array([0.0]), np.array([0.0]))
    assert sp["wx"][0] == pytest.approx(abs(1 - 50 / -200) * 100 + BLUR(50), rel=1e-12)   # 125 mm + blur > aperture
    r = U.instant(c)
    assert r["capture_beam"] < 1 and r["off_receiver_W"] > 0
    assert r["E_rec_peak_Wm2"] < 1000 * r["tau_beam"]                      # spreading lowers the local irradiance
    # circle ∩ square: compare with a fine numerical integration
    R = sp["wx"][0] / 2
    x = np.linspace(-R, R, 200001)
    chord = 2 * np.sqrt(np.clip(R * R - x * x, 0, None))
    inside = np.trapezoid(np.where(np.abs(x) <= 50, np.minimum(chord, 100), 0), x)
    assert r["capture_beam"] == pytest.approx(inside / (math.pi * R * R), rel=1e-3)   # 64-strip quadrature


def test_round_spot_fully_on_receiver_is_captured_exactly():
    c = setp(U.preset("convex"), ap_x_mm=120.0, ap_y_mm=120.0, f_mm=250.0, h_mm=170.0, rec_x_mm=40.0, rec_y_mm=40.0,
             nx=3, ny=2, pitch_x_mm=130.0, pitch_y_mm=130.0)
    r = U.instant(c)
    assert r["capture_beam"] == pytest.approx(1.0, abs=1e-12)
    assert r["off_receiver_W"] == pytest.approx(0.0, abs=1e-9)


def test_cpc_acceptance():
    c = U.preset("cpc")
    A = U.areas(c)
    assert A["C_g"] == pytest.approx(1 / math.sin(math.radians(30)), rel=1e-12)
    assert U.capture(c, 0.0, math.tan(math.radians(29.9)))[0] == pytest.approx(1.0)
    assert U.capture(c, 0.0, math.tan(math.radians(30.1)))[0] == 0.0
    assert U.instant(c)["E_rec_peak_Wm2"] is None                          # flux profile not modelled


def test_measured_angle_table_is_used():
    c = U.preset("convex")
    assert U.model_level(c) == U.LEVEL_BASIC
    c["params"]["angle_table"] = {"value": [[0, 0.9], [30, 0.8], [60, 0.5]], "status": U.OLC, "note": ""}
    assert U.model_level(c) == U.LEVEL_TABLE
    assert U.tau(c, math.radians(45)) == pytest.approx(0.65)


def test_incomplete_inputs():
    c = U.preset("convex")
    c["params"]["f_mm"]["value"] = None
    c["params"]["rec_x_mm"]["value"] = None
    val = U.validate(c)
    assert not val["ok"] and set(val["missing"]) == {"f_mm", "rec_x_mm"}
    assert U.instant(c)["ok"] is False and U.annual(c, {})["ok"] is False
    c2 = setp(U.preset("convex"), f_mm=-100.0)
    assert "toplayıcı optikanın fokus məsafəsi müsbət olmalıdır" in U.validate(c2)["errors"]
    c3 = setp(U.preset("lfs150150"), pitch_y_mm=100.0)
    assert not U.validate(c3)["ok"]
    assert U.validate({"type": "x", "params": {}})["ok"] is False


def test_compare_B_reports_both_collecting_areas():
    r = U.instant(U.preset("lfs150150"))
    B = r["compare_B"]
    assert B["collect_optic_m2"] == pytest.approx(1.35) and B["collect_plain_m2"] == pytest.approx(0.675)
    assert B["cell_area_m2"] == pytest.approx(0.675)
    assert r["compare_A"]["area_optic_m2"] == r["compare_A"]["area_plain_m2"]


# ---------------------------------------------------------------------------------------- annual, JS = Python
@pytest.fixture(scope="module")
def hourly():
    return json.loads((ROOT / "docs" / "data" / "baku_pvgis53_tmy.json").read_text(encoding="utf-8"))["hourly"]


def test_annual_lists_assumptions_and_tracking_cost(hourly):
    fx = U.annual(U.preset("lfs150150"), hourly, "fixed")
    tr = U.annual(U.preset("lfs150150"), hourly, "2axis")
    assert fx["optic"]["aux_kWh"] == 0 and tr["optic"]["aux_kWh"] > 0
    assert any("fərziyyə" in a for a in fx["assumptions"])
    assert any("izləmə" in a for a in tr["assumptions"])
    o = fx["optics_kWh"]
    assert o["optical_loss_W"] + o["on_receiver_W"] + o["off_receiver_W"] == pytest.approx(o["P_in_W"], rel=1e-9)


CASES = [("lfs150150", {}), ("point_fresnel", {}), ("convex", {}), ("negative", {}), ("flat", {}), ("cpc", {}),
         ("convex", {"layout": "shared", "nx": 3, "ny": 2, "rec_x_mm": 300.0, "rec_y_mm": 200.0})]


def _cfg(key, over):
    c = U.preset(key)
    for k, val in over.items():
        if k == "layout":
            c["layout"] = val
        else:
            c["params"][k]["value"] = val
    return c


def test_js_matches_python(hourly):
    js = r"""
const U = require(process.argv[1]); const cases = JSON.parse(process.argv[2]); const fs = require("fs");
const H = JSON.parse(fs.readFileSync(process.argv[3], "utf8")).hourly;
const out = cases.map(([key, over]) => { const c = U.preset(key);
  for (const [k, val] of Object.entries(over)) { if (k === "layout") c.layout = val; else c.params[k].value = val; }
  const inst = [[0, 0], [7, -4], [25, 12]].map(([a, b]) => U.instant(c, { dni: 900, diff: 120, theta_x_deg: a, theta_y_deg: b, ta: 30, ws: 2 }));
  return { inst: inst.map(r => [r.on_receiver_W, r.off_receiver_W, r.optical_loss_W, r.E_rec_peak_Wm2, r.dc_W, r.compare_A.plain_dc_W, r.compare_B.plain_dc_W]),
           fx: U.annual(c, H, "fixed"), tr: U.annual(c, H, "2axis"), an: U.analytic(c).total_W }; });
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", js, str(ROOT / "simulator" / "uoptics.js"), json.dumps(CASES),
                        str(ROOT / "docs" / "data" / "baku_pvgis53_tmy.json")],
                       capture_output=True, text=True, encoding="utf-8", check=True)
    out = json.loads(r.stdout)
    for (key, over), j in zip(CASES, out):
        c = _cfg(key, over)
        for (a, b), ji in zip([(0, 0), (7, -4), (25, 12)], j["inst"]):
            p = U.instant(c, 900, 120, a, b, 30, 2)
            py = [p["on_receiver_W"], p["off_receiver_W"], p["optical_loss_W"], p["E_rec_peak_Wm2"], p["dc_W"],
                  p["compare_A"]["plain_dc_W"], p["compare_B"]["plain_dc_W"]]
            for x, y in zip(ji, py):
                assert (x is None and y is None) or x == pytest.approx(y, rel=1e-9, abs=1e-9), (key, a, b)
        for m in ("fixed", "2axis"):
            pa, ja = U.annual(c, hourly, m), j["fx" if m == "fixed" else "tr"]
            for part in ("optic",):
                for k in ("gross_kWh", "aux_kWh", "net_kWh"):
                    assert ja[part][k] == pytest.approx(pa[part][k], rel=1e-9, abs=1e-9), (key, m, k)
            for k in ("gross_kWh", "net_kWh"):
                assert ja["compare_A"]["plain"][k] == pytest.approx(pa["compare_A"]["plain"][k], rel=1e-9, abs=1e-9)
                assert ja["compare_B"]["plain"][k] == pytest.approx(pa["compare_B"]["plain"][k], rel=1e-9, abs=1e-9)
            for k in ("P_in_W", "on_receiver_W", "off_receiver_W"):
                assert ja["optics_kWh"][k] == pytest.approx(pa["optics_kWh"][k], rel=1e-9, abs=1e-9)
            assert ja["hours_above_limit"] == pa["hours_above_limit"]
        assert j["an"] == pytest.approx(U.analytic(c)["total_W"], rel=1e-12)
