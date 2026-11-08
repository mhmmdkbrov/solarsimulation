"""Lens energy calculator — Python mirror of simulator/calculator.js.

``original`` reproduces the shared Streamlit code ("Solar Lens Energy Calculator v1.0") exactly;
``corrected`` adds the comparisons that code leaves out (same aperture, same footprint, where the diopter acts,
heat actually deposited in the cells, direct light only with real weather data).
"""
from __future__ import annotations

import math

SUN_ANG = 0.0093
DEFAULTS = dict(diopter=5.0, diameter_cm=20.0, lens_count=72, transmission=0.95, optical_efficiency=0.90,
                receiver_area=1.5, pv_efficiency=0.20, irradiance=1000, sun_hours=5.0, thermal_derating=0.05,
                electricity_price=0.10, h_cm=None, packing="square")


def original(p: dict) -> dict:
    focal_length_m = 1 / p["diopter"]
    diameter_m = p["diameter_cm"] / 100
    single_lens_area = math.pi * (diameter_m / 2) ** 2
    total_aperture = single_lens_area * p["lens_count"]
    incident_power = p["irradiance"] * total_aperture
    transmitted_power = incident_power * p["transmission"]
    receiver_optical_power = transmitted_power * p["optical_efficiency"]
    raw_electrical_power = receiver_optical_power * p["pv_efficiency"]
    lens_output_w = raw_electrical_power * (1 - p["thermal_derating"])
    baseline_output_w = p["irradiance"] * p["receiver_area"] * p["pv_efficiency"]
    baseline_annual_kwh = baseline_output_w * p["sun_hours"] / 1000 * 365
    lens_annual_kwh = lens_output_w * p["sun_hours"] / 1000 * 365
    return dict(focal_length_m=focal_length_m, focal_length_cm=focal_length_m * 100, single_lens_area=single_lens_area,
                total_aperture=total_aperture, concentration=total_aperture / p["receiver_area"],
                focal_spot_mm=focal_length_m * SUN_ANG * 1000, incident_power=incident_power,
                transmitted_power=transmitted_power, receiver_optical_power=receiver_optical_power,
                raw_electrical_power=raw_electrical_power, lens_output_w=lens_output_w, baseline_output_w=baseline_output_w,
                baseline_annual_kwh=baseline_annual_kwh, lens_annual_kwh=lens_annual_kwh,
                gain_percent=(lens_output_w / baseline_output_w - 1) * 100 if baseline_output_w > 0 else 0,
                unconverted_power=incident_power - receiver_optical_power,
                receiver_power_density=receiver_optical_power / p["receiver_area"])


def corrected(p: dict, H: dict | None = None) -> dict:
    o = original(p)
    f, d, A, a1 = o["focal_length_m"], p["diameter_cm"] / 100, o["total_aperture"], o["single_lens_area"]
    h = (f * 100 if p.get("h_cm") is None else p["h_cm"]) / 100
    footprint = p["lens_count"] * d * d * (math.sqrt(3) / 2 if p.get("packing") == "hex" else 1.0)
    spot = d * abs(1 - h / f) + h * SUN_ANG
    spot_area = math.pi * (spot / 2) ** 2
    G, eta = p["irradiance"], p["pv_efficiency"]
    out = dict(original=o, h_m=h, footprint_m2=footprint, spot_mm=spot * 1000,
               local_suns=a1 / spot_area * p["transmission"] * p["optical_efficiency"],
               lit_share=min(1.0, p["lens_count"] * spot_area / p["receiver_area"]),
               optical_loss_w=o["incident_power"] - o["receiver_optical_power"],
               heat_in_receiver_w=o["receiver_optical_power"] - o["lens_output_w"],
               not_converted_w=o["incident_power"] - o["lens_output_w"],
               lens_w=o["lens_output_w"], plain_same_receiver_w=o["baseline_output_w"],
               plain_same_aperture_w=G * A * eta, plain_same_footprint_w=G * footprint * eta)
    out["vs_receiver_pct"] = 100 * (out["lens_w"] / out["plain_same_receiver_w"] - 1)
    out["vs_aperture_pct"] = 100 * (out["lens_w"] / out["plain_same_aperture_w"] - 1)
    out["vs_footprint_pct"] = 100 * (out["lens_w"] / out["plain_same_footprint_w"] - 1)
    if H:
        k = p["transmission"] * p["optical_efficiency"] * eta * (1 - p["thermal_derating"])
        out["annual"] = dict(lens_2axis_kwh=H["beam_2axis"] * A * k, plain_fixed_same_aperture_kwh=H["glob_fixed"] * A * eta,
                             plain_2axis_same_aperture_kwh=H["glob_2axis"] * A * eta)
    return out
