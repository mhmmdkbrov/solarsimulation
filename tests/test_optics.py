"""Lens optics, light balance, electrical mismatch and search tests."""
import numpy as np
import pytest

from solarsim import electrical as E
from solarsim import lenslab as LL
from solarsim import optics as O
from solarsim import weather as W


@pytest.fixture(scope="module")
def prep():
    return LL.prepare(W.pvgis53_tmy("baku"))


@pytest.fixture(scope="module")
def geom():
    return O.Geometry()


# ------------------------------------------------------------------------------------------------- dioptre / focus
@pytest.mark.parametrize("P,f", [(3, 333.333), (10, 100.0), (-3, -333.333), (-10, -100.0), (13.5, 74.074)])
def test_focal_length_units(P, f):
    c = O.LensConfig(P, 10)
    assert c.f == pytest.approx(f, abs=1e-3)                       # f [mm] = 1000 / D [1/m]
    assert c.kind == ("converging" if P > 0 else "diverging")


def test_flat_sheet_mode():
    c = O.LensConfig(0.0, 3)
    assert c.kind == "flat" and np.isinf(c.f)


def test_negative_lens_virtual_focus_spreads(geom):
    s = O.spot_split(O.LensConfig(-10, 100, "array"), geom, np.array([0.0]), np.array([0.0]))
    assert s["m"] > 1                                               # m = 1 − h/f > 1 for f < 0: spot larger than the lens
    assert s["conc"][0] < 1


def test_13p5D_8mm_cell_plane_before_focus():
    c = O.LensConfig(13.5, 8.0)
    assert O._h_eff(c.h) < c.f                                      # ≈7.3 mm < 74.1 mm: cells are far above the focus
    assert c.f == pytest.approx(74.07, abs=0.01)


# ---------------------------------------------------------------------------------------------------- light balance
@pytest.mark.parametrize("cfg", [O.LensConfig(3, 3, "big"), O.LensConfig(10, 100, "big"), O.LensConfig(-10, 100, "array"),
                                 O.LensConfig(13.5, 8, "array"), O.LensConfig(13.5, 8, "array_cyl"), O.LensConfig(0, 3, "array")])
def test_light_balance_closes(prep, cfg):
    r = LL.annual(prep, cfg)
    b = r["balance_kWh"]
    parts = sum(b[k] for k in ("refl_lens", "abs_lens", "refl_glass", "own", "neighbours", "gap", "off"))
    assert parts == pytest.approx(b["in"], rel=1e-12)
    assert all(b[k] >= -1e-9 for k in b)


def test_null_lens_equals_bare_module(prep):
    """n = 1, no absorption, τ = 1, flat: the lens does nothing, so the result must equal scenario A exactly
    (differential method), and the optical chain itself must stay within 1 % of the pvlib baseline."""
    r = LL.annual(prep, LL.NULL_LENS)
    assert r["L_kWh_m2"] == pytest.approx(r["A_kWh_m2"], rel=1e-12)
    assert abs(r["chain_vs_A_pct"]) < 1.0


def test_edge_ray_leaves_the_module(geom):
    # big lens, large incidence along the slope: part of the spot leaves the module
    s = O.spot_split(O.LensConfig(0.0, 500, "big"), geom, np.array([0.0]), np.array([np.tan(np.radians(60))]))
    assert s["off"][0] > 0.4


def test_large_incidence_reduces_lens_transmission():
    T0, R0, A0 = O.lens_split(np.array([0.0]), O.LensConfig(3, 10))
    T7, R7, A7 = O.lens_split(np.array([np.radians(75)]), O.LensConfig(3, 10))
    assert T0[0] == pytest.approx(0.92, abs=1e-9) and T7[0] < T0[0]
    assert T0[0] + R0[0] + A0[0] == pytest.approx(1.0) and T7[0] + R7[0] + A7[0] == pytest.approx(1.0)


# ------------------------------------------------------------------------------------------------------- electrical
def test_iv_uniform_matches_datasheet():
    r = E.module_pmax(np.full((6, 24), 1000.0), 25.0)
    assert r["p_mp"] == pytest.approx(450.0, rel=0.002) and not any(r["bypassed"])


def test_iv_uniform_mismatch_is_one():
    assert E.mismatch_factor(np.full((6, 24), 700.0), 40.0) == pytest.approx(1.0, abs=1e-9)


def test_iv_one_shaded_cell_bypasses_one_group():
    g = np.full((6, 24), 1000.0); g[0, 5] = 0.0
    r = E.module_pmax(g, 25.0)
    assert sum(r["bypassed"]) == 1 and 0.6 < r["p_mp"] / 450.0 < 0.72


def test_iv_one_group_shaded():
    g = np.full((6, 24), 1000.0); g[2:4, :] = 0.0
    r = E.module_pmax(g, 25.0)
    assert r["bypassed"] == [False, True, False] and 0.6 < r["p_mp"] / 450.0 < 0.68


def test_topology_sensitivity_half_shade():
    g = np.full((6, 24), 1000.0); g[:, :12] = 500.0
    assert E.mismatch_factor(g, 25, "T1") > 0.98 and E.mismatch_factor(g, 25, "T3") < 0.75


def test_fast_rule_matches_iv_for_uniform_and_close_for_shading():
    g = np.full((6, 24), 1000.0)
    assert E.weakest_cell_factor(g) == pytest.approx(1.0)
    g[0, 5] = 0.0
    assert abs(E.weakest_cell_factor(g) - E.mismatch_factor(g, 25)) < 0.03


# ------------------------------------------------------------------------------------------------------------ search
def test_best_distance_beats_every_test_point(prep):
    for P, mode in [(-3, "array"), (-10, "array"), (3, "big")]:
        b = LL.best_h(prep, P, mode, 0.92)
        best = b["result"]["L_kWh_m2"]
        for name, h in LL.test_points(P):
            r = LL.annual(prep, O.LensConfig(P, h, mode, 0.92))
            assert best >= r["L_kWh_m2"] - 1e-9, (P, mode, name)


# -------------------------------------------------------------------------------------------- level 2 ray tracing
@pytest.mark.parametrize("P,h,theta", [(3, 3, 0.0), (3, 3, 20.0), (3, 20, 0.0), (5, 30, 10.0)])
def test_trace2d_agrees_with_paraxial_for_weak_lens(geom, P, h, theta):
    """Level 2 (Snell/Fresnel, sun disk) vs. level 1 (paraxial) along the slope y, where the spherical profile fits."""
    t = O.trace2d(O.LensConfig(P, h, "array"), geom, theta)
    cyl = O.LensConfig(P, h, "array_cyl", tau=1.0, n=1.0, K=0.0)     # focusing only along y, no x effect
    s = O.spot_split(cyl, geom, np.array([0.0]), np.array([np.tan(np.radians(theta))]))
    y_capture = (s["own"][0] + s["neighbours"][0]) / (1 - s["off"][0]) / (geom.CX / geom.PX)
    assert t["traced"]
    # tolerance follows the validity label: 'yaxşı' (edge-ray angle ≤ 10°) 1 point, 'orta' (≤ 20°) 2 points
    tol = {"yaxşı": 0.01, "orta": 0.02}[O.validity(O.LensConfig(P, h, "array_cyl"), geom)["paraxial"]]
    assert abs(t["on_cells"] - y_capture) < tol


def test_trace2d_reports_profile_that_does_not_fit(geom):
    t = O.trace2d(O.LensConfig(13.5, 8, "array"), geom, 0.0)                 # R = 36.3 mm < 36.7 mm
    assert t["traced"] is False and t["R_mm"] < t["half_aperture_mm"]


# ------------------------------------------------------------------------------------- validity: f-number, angles
def test_validity_176cm_aperture_20cm_focus(geom):
    """One big lens over the module: a = 1762 mm on the long side (y), f = 200 mm → f/0,11 and 77,2°."""
    v = O.validity(O.LensConfig(5.0, 200.0, "big"), geom)
    assert v["axis"] == "y" and v["aperture_mm"] == 1762.0 and v["f_mm"] == 200.0
    assert v["f_number"] == 200.0 / 1762.0                                   # N = f / aperture, unrounded
    assert v["edge_angle_deg"] == np.degrees(np.arctan((1762.0 / 2) / 200.0))  # atan((a/2)/f), unrounded
    assert f"{v['f_number']:.2f}" == "0.11" and f"{v['edge_angle_deg']:.1f}" == "77.2"
    assert v["corner_angle_deg"] == np.degrees(np.arctan(np.hypot(1134.0, 1762.0) / 2 / 200.0))
    assert v["corner_angle_deg"] > v["edge_angle_deg"]
    assert v["above_warn_limit"] and v["paraxial"] == "aşağı" and v["reliability"] == "aşağı" and v["coarse"]
    g = O.lens_geometry(200.0, 1760.0, 1760.0)                                # 176 cm square aperture
    assert f"{g['f_number']:.2f}" == "0.11" and f"{g['edge_angle_deg']:.1f}" == "77.2"


def test_validity_axis_and_cylinder(geom):
    v = O.validity(O.LensConfig(3.0, 10.0, "array"), geom)                    # tile 189 × 73,4 mm: larger side x
    assert v["axis"] == "x" and v["aperture_mm"] == geom.PX and v["corner_angle_deg"] is not None
    c = O.validity(O.LensConfig(3.0, 10.0, "array_cyl"), geom)                # cylinder: y only, no corner ray
    assert c["axis"] == "y" and c["aperture_mm"] == geom.PY and c["corner_angle_deg"] is None
    f = O.validity(O.LensConfig(0.0, 10.0, "array"), geom)
    assert f["f_number"] is None and f["edge_angle_deg"] == 0.0 and f["reliability"] == "yüksək"


@pytest.mark.parametrize("angle,label", [(10.0, "yaxşı"), (10.01, "orta"), (20.0, "orta"), (20.01, "aşağı")],
                         ids=["10.00deg", "10.01deg", "20.00deg", "20.01deg"])
def test_paraxial_label_limits(angle, label):
    assert O.paraxial_label(angle) == label


def test_validity_js_matches_python(geom):
    import json
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    cases = [(5.0, "big"), (3.0, "array"), (-10.0, "array"), (10.0, "array_cyl"), (0.0, "big"), (20.0, "array_cyl")]
    js = "const L=require(process.argv[1]); const D=require(process.argv[2]);"          "const c=JSON.parse(process.argv[3]); console.log(JSON.stringify({v:c.map(([P,m])=>L.validity({P,h:10,mode:m})),"          "fmt:[D.fmt(200/1762,2),D.fmt(Math.atan(881/200)*180/Math.PI,1)]}))"
    r = subprocess.run(["node", "-e", js, str(root / "simulator" / "lensoptics.js"), str(root / "simulator" / "datastore.js"),
                        json.dumps(cases)], capture_output=True, text=True, encoding="utf-8", check=True)
    out = json.loads(r.stdout)
    assert out["fmt"] == ["0,11", "77,2"]                                     # what the page shows
    for (P, mode), j in zip(cases, out["v"]):
        py = O.validity(O.LensConfig(P, 10.0, mode), geom)
        for k in ("axis", "paraxial", "above_warn_limit", "reliability", "coarse", "cylindrical"):
            assert j[k] == py[k], (P, mode, k)
        for k in ("aperture_mm", "f_number", "edge_angle_deg", "corner_angle_deg"):
            assert (j[k] is None and py[k] is None) or j[k] == pytest.approx(py[k], rel=1e-12), (P, mode, k)
