"""Lens energy calculator: the original code is reproduced exactly; the corrected comparison is checked; JS = Python."""
import json
import math
import subprocess
from pathlib import Path

import pytest

from solarsim import calculator as LC

ROOT = Path(__file__).resolve().parent.parent
P = dict(LC.DEFAULTS)


def test_original_reproduces_shared_results():
    o = LC.original(P)
    # values printed by the shared calculator (ChatGPT): 20 cm, 1.86 mm, 2.262 m², 1.51×, 1 934 W, 300 W, 367.5 W, +22.5 %
    assert o["focal_length_cm"] == pytest.approx(20.0)
    assert o["focal_spot_mm"] == pytest.approx(1.86)
    assert o["total_aperture"] == pytest.approx(2.2619, abs=1e-4)
    assert o["concentration"] == pytest.approx(1.508, abs=1e-3)
    assert o["receiver_optical_power"] == pytest.approx(1933.96, abs=0.01)
    assert o["baseline_output_w"] == pytest.approx(300.0)
    assert o["lens_output_w"] == pytest.approx(367.45, abs=0.01)
    assert o["gain_percent"] == pytest.approx(22.48, abs=0.01)
    assert o["unconverted_power"] == pytest.approx(328.0, abs=0.1)        # what the code calls "optical/thermal"


def test_diopter_does_not_change_original_output():
    outs = {D: LC.original({**P, "diopter": D})["lens_output_w"] for D in (1, 3, 5, 10, 20, 50)}
    assert max(outs.values()) - min(outs.values()) < 1e-9


def test_energy_balance_closes():
    c = LC.corrected(P)
    o = c["original"]
    assert c["optical_loss_w"] + c["heat_in_receiver_w"] + c["lens_w"] == pytest.approx(o["incident_power"])
    assert c["heat_in_receiver_w"] == pytest.approx(1566.5, abs=0.1)   # heat deposited in the cells (not in the code)


def test_same_area_comparisons():
    c = LC.corrected(P)
    assert c["vs_receiver_pct"] == pytest.approx(22.48, abs=0.01)      # original headline (unequal areas)
    assert c["vs_aperture_pct"] == pytest.approx(-18.78, abs=0.01)     # same collecting area
    assert c["vs_footprint_pct"] == pytest.approx(-36.20, abs=0.01)    # same footprint, square packing
    assert LC.corrected({**P, "packing": "hex"})["vs_footprint_pct"] == pytest.approx(-26.33, abs=0.01)
    # with lossless optics and no derating, the lens can at best equal a plain panel of the same aperture
    ideal = LC.corrected({**P, "transmission": 1.0, "optical_efficiency": 1.0, "thermal_derating": 0.0})
    assert ideal["vs_aperture_pct"] == pytest.approx(0.0, abs=1e-9)


def test_focus_spot_and_local_concentration():
    c = LC.corrected(P)                                                # at h = f: sun image only
    assert c["spot_mm"] == pytest.approx(1.86)
    assert c["local_suns"] == pytest.approx((0.2 / 0.00186) ** 2 * 0.95 * 0.9, rel=1e-9)
    defocus = LC.corrected({**P, "h_cm": 10.0})                        # half-way: spot = d/2 + h·θ
    assert defocus["spot_mm"] == pytest.approx(100 + 0.93, abs=1e-6)


def test_js_matches_python():
    js = r"""
const C = require(process.argv[1]); const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map(p => { const r = C.corrected({ ...C.DEFAULTS, ...p }, { beam_2axis: 1315, glob_fixed: 1679, glob_2axis: 2112 });
  return { lens: r.lens_w, ap: r.vs_aperture_pct, fp: r.vs_footprint_pct, heat: r.heat_in_receiver_w, suns: r.local_suns, ann: r.annual.lens_2axis_kwh }; })));
"""
    cases = [{}, {"diopter": 10, "h_cm": 7, "packing": "hex"}, {"lens_count": 10, "diameter_cm": 50, "receiver_area": 0.5}]
    r = subprocess.run(["node", "-e", js, str(ROOT / "simulator" / "calculator.js"), json.dumps(cases)], capture_output=True, text=True, check=True)
    for c, j in zip(cases, json.loads(r.stdout)):
        py = LC.corrected({**P, **c}, {"beam_2axis": 1315, "glob_fixed": 1679, "glob_2axis": 2112})
        assert j["lens"] == pytest.approx(py["lens_w"], rel=1e-12)
        assert j["ap"] == pytest.approx(py["vs_aperture_pct"], rel=1e-12)
        assert j["fp"] == pytest.approx(py["vs_footprint_pct"], rel=1e-12)
        assert j["heat"] == pytest.approx(py["heat_in_receiver_w"], rel=1e-12)
        assert j["suns"] == pytest.approx(py["local_suns"], rel=1e-12)
        assert j["ann"] == pytest.approx(py["annual"]["lens_2axis_kwh"], rel=1e-12)
