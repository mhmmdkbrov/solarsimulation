// Lens energy calculator: the original Streamlit formulas ("Solar Lens Energy Calculator v1.0", shared ChatGPT code),
// reproduced exactly, and a corrected comparison. Pure functions, no DOM; mirrored in solarsim/calculator.py.
const LensCalc = (() => {
  const SUN_ANG = 0.0093;              // rad, angular diameter of the sun (same constant as the original code)

  const DEFAULTS = {
    diopter: 5.0, diameter_cm: 20.0, lens_count: 72, transmission: 0.95, optical_efficiency: 0.90,
    receiver_area: 1.5, pv_efficiency: 0.20, irradiance: 1000, sun_hours: 5.0, thermal_derating: 0.05,
    electricity_price: 0.10,
    // inputs added for the corrected comparison
    h_cm: null,                        // lens → cell distance; null = at the focal length (what the original implies)
    packing: "square",                 // footprint of round lenses: "square" or "hex"
  };

  // Exact port of the original calculation (same names, same order, same formulas).
  function original(p) {
    const focal_length_m = 1 / p.diopter, focal_length_cm = focal_length_m * 100;
    const diameter_m = p.diameter_cm / 100;
    const single_lens_area = Math.PI * (diameter_m / 2) ** 2;
    const total_aperture = single_lens_area * p.lens_count;
    const concentration = total_aperture / p.receiver_area;
    const focal_spot_mm = focal_length_m * SUN_ANG * 1000;
    const incident_power = p.irradiance * total_aperture;
    const transmitted_power = incident_power * p.transmission;
    const receiver_optical_power = transmitted_power * p.optical_efficiency;
    const raw_electrical_power = receiver_optical_power * p.pv_efficiency;
    const lens_output_w = raw_electrical_power * (1 - p.thermal_derating);
    const baseline_output_w = p.irradiance * p.receiver_area * p.pv_efficiency;
    const baseline_daily_kwh = baseline_output_w * p.sun_hours / 1000, lens_daily_kwh = lens_output_w * p.sun_hours / 1000;
    const baseline_annual_kwh = baseline_daily_kwh * 365, lens_annual_kwh = lens_daily_kwh * 365;
    const gain_percent = baseline_output_w > 0 ? (lens_output_w / baseline_output_w - 1) * 100 : 0;
    const unconverted_power = incident_power - receiver_optical_power;
    const receiver_power_density = receiver_optical_power / p.receiver_area;
    const baseline_value = baseline_annual_kwh * p.electricity_price, lens_value = lens_annual_kwh * p.electricity_price;
    return { focal_length_m, focal_length_cm, single_lens_area, total_aperture, concentration, focal_spot_mm, incident_power,
             transmitted_power, receiver_optical_power, raw_electrical_power, lens_output_w, baseline_output_w,
             baseline_daily_kwh, lens_daily_kwh, baseline_annual_kwh, lens_annual_kwh, gain_percent, unconverted_power,
             receiver_power_density, baseline_value, lens_value, additional_value: lens_value - baseline_value };
  }

  // Corrected comparison. H (optional): annual irradiation of a dataset in kWh/m² —
  // { beam_2axis: Σ DNI·cos(AOI) on a 2-axis tracker, glob_fixed: Σ POA global fixed, glob_2axis: Σ POA global tracked }.
  function corrected(p, H) {
    const o = original(p);
    const f = o.focal_length_m, d = p.diameter_cm / 100, A = o.total_aperture, a1 = o.single_lens_area;
    const h = (p.h_cm == null ? f * 100 : p.h_cm) / 100;
    // footprint occupied by N round lenses (they cannot tile a plane without gaps)
    const footprint = p.packing === "hex" ? p.lens_count * d * d * Math.sqrt(3) / 2 : p.lens_count * d * d;
    // the diopter only sets where the light goes: spot size on the cell plane at distance h (thin lens + sun disk)
    const spot_m = d * Math.abs(1 - h / f) + h * SUN_ANG;
    const spot_area = Math.PI * (spot_m / 2) ** 2;
    const local_suns = (a1 / spot_area) * p.transmission * p.optical_efficiency;     // intensity in the spot / 1 sun
    const lit_share = Math.min(1, p.lens_count * spot_area / p.receiver_area);
    // energy bookkeeping at the original's irradiance (everything after the lens counted once)
    const G = p.irradiance, eta = p.pv_efficiency;
    const optical_loss_w = o.incident_power - o.receiver_optical_power;
    const heat_in_receiver_w = o.receiver_optical_power - o.lens_output_w;
    const not_converted_w = o.incident_power - o.lens_output_w;
    // same-area references (plain panels, same cell efficiency, no lens)
    const plain_same_receiver_w = o.baseline_output_w;
    const plain_same_aperture_w = G * A * eta;
    const plain_same_footprint_w = G * footprint * eta;
    const out = {
      original: o, h_m: h, footprint_m2: footprint, spot_mm: spot_m * 1000, local_suns, lit_share,
      optical_loss_w, heat_in_receiver_w, not_converted_w, heat_in_receiver_w_m2: heat_in_receiver_w / p.receiver_area,
      lens_w: o.lens_output_w, plain_same_receiver_w, plain_same_aperture_w, plain_same_footprint_w,
      vs_receiver_pct: 100 * (o.lens_output_w / plain_same_receiver_w - 1),
      vs_aperture_pct: 100 * (o.lens_output_w / plain_same_aperture_w - 1),
      vs_footprint_pct: 100 * (o.lens_output_w / plain_same_footprint_w - 1),
      eff_per_aperture: o.lens_output_w / (G * A), eff_plain: eta,
    };
    if (H) {
      // annual energy with real weather: the lens focuses only direct light and must track the sun;
      // plain panels use all light (simple energy balance for both: no IAM, no temperature model)
      const k = p.transmission * p.optical_efficiency * eta * (1 - p.thermal_derating);
      out.annual = {
        lens_2axis_kwh: H.beam_2axis * A * k,
        plain_fixed_same_aperture_kwh: H.glob_fixed * A * eta,
        plain_2axis_same_aperture_kwh: H.glob_2axis * A * eta,
        original_lens_kwh: o.lens_annual_kwh, original_baseline_kwh: o.baseline_annual_kwh,
        psh_irradiation_kwh_m2: G * p.sun_hours * 365 / 1000, H,
      };
    }
    return out;
  }

  function irradiationFromDataset(D) {
    const h = D.hourly, s = a => a.reduce((x, v) => x + v, 0) * h.step_h / 1000;
    return { beam_2axis: s(h.t_dnicos), glob_fixed: s(h.f_glob), glob_2axis: s(h.t_glob) };
  }

  return { DEFAULTS, original, corrected, irradiationFromDataset, SUN_ANG };
})();
if (typeof module !== "undefined") module.exports = LensCalc;
