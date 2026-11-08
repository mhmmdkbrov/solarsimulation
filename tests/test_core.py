"""Core tests: datasets, time handling, energy integration, flat-plate model, bookkeeping, regression to v1."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from solarsim import analysis as AN
from solarsim import pv as PV
from solarsim import scenarios as S
from solarsim import weather as W
from solarsim.sites import PRESETS

ROOT = Path(__file__).resolve().parent.parent
BASE = json.loads((ROOT / "tests" / "baseline_v1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def baku():
    return W.pvgis53_tmy("baku")


@pytest.fixture(scope="module")
def baku_run_v1(baku):
    return S.run(baku, S.override(S.default_params(), {("cpv", "diffuse_in_acceptance"): False}))


@pytest.fixture(scope="module")
def baku_run(baku):
    return S.run(baku)


# ----------------------------------------------------------------------------------------------- module / STC / NOCT
def test_stc_450W_and_efficiency():
    m = PV.Module()
    assert PV.pvwatts(1000.0, 25.0, m.v("pdc0_W"), m.v("gamma_pdc")) == pytest.approx(450.0, abs=1e-9)
    assert m.eta_stc == pytest.approx(0.2252, abs=5e-5)          # 450 / (1000 × 1.998108 m²)


def test_zero_irradiance_gives_zero_power():
    assert PV.pvwatts(0.0, 30.0, 450.0, -0.003) == 0.0


def test_noct_check_and_calibration():
    m = PV.Module()
    n = PV.noct_check(m)
    assert n["t_cell_model_C"] == pytest.approx(45.86, abs=0.01)  # v1 value; datasheet 43 ± 2 °C
    a_cal = PV.calibrate_sapm_a_to_noct(m)
    assert PV.noct_check(m, a=a_cal)["t_cell_model_C"] == pytest.approx(43.0, abs=1e-9)


def test_active_fraction_consistent():
    m = PV.Module()
    assert 144 * m.v("cell_w_mm") * m.cell_h_mm / (m.v("length_mm") * m.v("width_mm")) == pytest.approx(0.92, abs=1e-12)


# ----------------------------------------------------------------------------------------------------- time handling
def _synthetic(step_h, start="2024-01-01", end="2024-12-31 23:59", drop=None):
    s = PRESETS["baku"]
    ds = W.sample_clear_sky(W.Site(**{**s.to_dict(), "elevation_m": 22.0}), year=2024, step_h=step_h)
    if drop is not None:
        ds = W._finish("t", ds.site, ds.df.drop(ds.df.index[drop]), dict(ds.meta))
    return ds


def test_half_hour_step_matches_hourly_energy():
    d1, d05 = _synthetic(1.0), _synthetic(0.5)
    assert d05.step_h == 0.5 and d1.step_h == 1.0
    p1, p05 = S.run(d1).annual, S.run(d05).annual
    # same physics sampled twice as often: annual energies agree within sampling error (< 1 %)
    for k in S.SCEN:
        assert p05.loc[k, "gross_kWh_unit"] == pytest.approx(p1.loc[k, "gross_kWh_unit"], rel=0.01)


def test_leap_year_rows_and_energy():
    d = _synthetic(1.0)                      # 2024 is a leap year
    assert len(d.df) == 8784 and d.meta["completeness"]["n_missing"] == 0
    assert ((d.df.index.month == 2) & (d.df.index.day == 29)).sum() == 24


def test_missing_rows_are_reported_not_filled():
    d = _synthetic(1.0, drop=[4000, 4001, 4002])
    c = d.meta["completeness"]
    assert c["n_missing"] == 3 and c["missing_hours"] == 3.0
    full = _synthetic(1.0)
    e_full = S.run(full).annual.loc["A_fixed", "gross_kWh_unit"]
    e_miss = S.run(d).annual.loc["A_fixed", "gross_kWh_unit"]
    assert e_miss <= e_full                  # energy of the missing hours is not invented


def test_energy_integration_formula():
    assert W.energy_Wh(np.array([100.0, 200.0, 0.0]), 0.5) == 150.0


# ----------------------------------------------------------------------------------------------- regression to v1
def test_regression_v1_exact(baku_run_v1):
    for k in S.SCEN:
        b = BASE["annual"][k]
        assert baku_run_v1.annual.loc[k, "gross_kWh_m2_ap"] == pytest.approx(b["gross_kWh_m2"], abs=1e-4)
        assert baku_run_v1.annual.loc[k, "net_kWh_m2_ap"] == pytest.approx(b["net_kWh_m2"], abs=1e-4)
        assert baku_run_v1.annual.loc[k, "aux_kWh_unit"] == pytest.approx(b["aux_kWh_unit"], abs=1e-6)


def test_v2_default_differs_only_by_documented_cpv_changes(baku_run, baku_run_v1):
    for k in ("A_fixed", "B_fixed", "A_2axis"):
        assert baku_run.annual.loc[k, "net_kWh_unit"] == pytest.approx(baku_run_v1.annual.loc[k, "net_kWh_unit"], abs=1e-9)
    d = baku_run.annual.loc["C_2axis", "net_kWh_m2_ap"] - baku_run_v1.annual.loc["C_2axis", "net_kWh_m2_ap"]
    assert 0 < d < 0.2        # diffuse inside the 1° acceptance cone adds a little; tracking σ=0.1° removes ~0


# ------------------------------------------------------------------------------------------------------ bookkeeping
def test_gross_minus_aux_equals_net(baku_run):
    a = baku_run.annual
    assert np.allclose(a["gross_kWh_unit"] - a["aux_kWh_unit"], a["net_kWh_unit"], atol=1e-9)
    assert np.allclose(a["drive_kWh_unit"] + a["controller_kWh_unit"] + a["cooling_kWh_unit"], a["aux_kWh_unit"], atol=1e-9)


def test_months_sum_to_annual(baku, baku_run):
    for k in S.SCEN:
        m = AN.monthly_kWh(baku, baku_run.hourly[k]["net_W"])
        assert m.sum() == pytest.approx(baku_run.annual.loc[k, "net_kWh_unit"], abs=1e-9)


def test_sky_classes_plus_remainder_sum_to_annual(baku, baku_run):
    for k in S.SCEN:
        t = AN.by_sky_class_kWh(baku, baku_run.hourly[k]["gross_W"])
        assert t["kWh"].sum() == pytest.approx(baku_run.annual.loc[k, "gross_kWh_unit"], abs=1e-9)
        assert t["hours"].sum() == pytest.approx(len(baku.df) * baku.step_h)


def test_optics_off_B_equals_A(baku):
    p = S.override(S.default_params(), {("retrofit", "optics_enabled"): False,
                                        ("retrofit", "extra_heating_K_per_kWm2"): 0.0, ("retrofit", "aux_W"): 0.0})
    r = S.run(baku, p)
    assert np.allclose(r.hourly["B_fixed"]["net_W"], r.hourly["A_fixed"]["net_W"], atol=1e-9)


def test_same_aperture_for_all_scenarios(baku_run):
    assert baku_run.areas["aperture_m2"] == pytest.approx(baku_run.areas["module_surface_m2"])


# ------------------------------------------------------------------------------------------------------------- CPV
def test_cpv_power_chain(baku_run):
    c = baku_run.hourly["C_2axis"]
    assert (c["p_cell_W"] <= c["p_in_W"] + 1e-9).all()
    assert (c["gross_W"] <= c["p_cell_W"] + 1e-9).all()
    m = PV.Module()
    # C is not used to scale the input power: intensity on the cell = P_cell / A_cell
    cells = m.area_m2 / 0.01 * 1e-4
    lit = c["p_cell_W"] > 0
    assert np.allclose(c.loc[lit, "suns"] * 1000 * cells, c.loc[lit, "p_cell_W"], rtol=1e-12)


def test_cpv_zero_dni_zero_power(baku):
    df = baku.df.copy(); df["dni"] = 0.0; df["dhi"] = 0.0
    d0 = W.Dataset("z", baku.site, df, dict(baku.meta))
    assert S.run(d0).hourly["C_2axis"]["gross_W"].abs().max() == 0.0


def test_control_sample_225_and_204():
    c = {"aperture_unit_m2": 0.01, "cell_area_m2": 1e-4, "tau_optical": 0.85, "intercept_optical": 1.0,
         "acceptance_half_angle_deg": 1.0, "tracking_error_sigma_deg": 0.0, "diffuse_in_acceptance": False,
         "eta_cell_ref": 0.30, "gamma_cell": 0.0, "eta_valid_T_C": (-20, 110), "eta_valid_suns": (1, 1000),
         "r_th_K_per_W": 0.0, "fan_W": 0.0}
    one = pd.Series([800.0]); ta = pd.Series([25.0])
    assert S.cpv_model(one, ta, pd.Series([True]), pd.Series([200.0]), c, 1.0)["gross_W"].iloc[0] == pytest.approx(204.0)
    assert PV.pvwatts(1000.0, 25.0, 225.0, -0.003) == pytest.approx(225.0)


# ------------------------------------------------------------------------------------------------- sites / timing
def test_second_site_changes_sun_and_irradiance():
    b, n = W.pvgis53_tmy("baku"), W.pvgis53_tmy("almeria")
    from solarsim import geometry as G
    sb, sn = G.solar_position(b), G.solar_position(n)
    assert abs(sb["azimuth"].iloc[4000] - sn["azimuth"].iloc[4000]) > 5     # same label, different sky position
    assert abs(b.df["ghi"].sum() - n.df["ghi"].sum()) / b.df["ghi"].sum() > 0.1


def test_series_offset_applied_once():
    from solarsim import geometry as G
    y = W.pvgis53_series("baku")[2020]
    assert y.meta["solpos_offset_h"] == 0.0 and y.meta["label_minute"] == 10
    sp = G.solar_position(y)
    hs = y.meta["h_sun_pvgis_deg"]
    m = hs > 5
    assert np.mean(np.abs(hs[m] - sp["elevation"].to_numpy()[m])) < 0.2     # PVGIS sun height = SPA at the label
