"""Cell-level I–V mismatch model (cell → string → bypass group → module).

Topology of the TSM-450NEG9R.28 (144 cut cells, 3 bypass diodes)
----------------------------------------------------------------
The datasheet gives no wiring diagram. It gives Voc = 52.9 V and 144 cells; a crystalline-Si cell has
Voc ≈ 0.70–0.74 V, so 52.9 V means ~72 cells in series, i.e. the 144 cells form two parallel paths. This is the
standard half-module layout: 3 bypass groups in series; each group = 2 parallel strings × 24 cells.
* T1 (default, assumption): the strings of group g are the upper and lower halves (rows 12–23 and 0–11) of
  columns 2g and 2g+1.
* T3 (sensitivity): the strings of group g are column 2g and column 2g+1 (24 rows each).
A 144-in-series layout is excluded by the datasheet Voc.

Cell parameters: De Soto single-diode model fitted to the datasheet (pvlib.ivtools.sdm.fit_desoto, 72 cells in series),
split per cell (2 parallel paths): I_L,c = I_L/2, I_0,c = I_0/2, R_s,c = 2R_s/72, R_sh,c = 2R_sh/72, nV_th,c = nN_sV_th/72.
Reverse bias through R_sh only (no breakdown); each bypass diode clamps its group at −0.6 V.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pvlib

NX, NY = 6, 24
V_BYPASS = -0.6


@lru_cache(maxsize=1)
def module_sdm():
    from pvlib.ivtools.sdm import fit_desoto
    Vmp, Imp, Voc, Isc = 44.6, 10.09, 52.9, 10.74
    alpha, beta = 0.0004 * Isc, -0.0024 * Voc
    vth = 1.380649e-23 * 298.15 / 1.602176634e-19
    a0 = 1.1 * 72 * vth
    p, _ = fit_desoto(v_mp=Vmp, i_mp=Imp, v_oc=Voc, i_sc=Isc, alpha_sc=alpha, beta_voc=beta, cells_in_series=72,
                      init_guess={"IL_0": Isc, "Io_0": Isc / (np.exp(Voc / a0) - 1), "a_0": a0, "Rs_0": 0.25, "Rsh_0": 500})
    return {k: float(v) for k, v in p.items() if k != "cells_in_series"}


def strings(topology: str = "T1"):
    """List of 3 groups; each group = list of 2 strings; each string = list of (col, row) cells."""
    groups = []
    for g in range(3):
        cols = (2 * g, 2 * g + 1)
        if topology == "T1":
            lower = [(c, r) for c in cols for r in range(0, 12)]
            upper = [(c, r) for c in cols for r in range(12, 24)]
            groups.append([lower, upper])
        elif topology == "T3":
            groups.append([[(cols[0], r) for r in range(24)], [(cols[1], r) for r in range(24)]])
        else:
            raise ValueError(topology)
    return groups


def cell_params(G_cells, T_cells):
    """Per-cell single-diode parameters at irradiance G (W/m², cell-equivalent) and temperature T (°C)."""
    p = module_sdm()
    G = np.clip(np.asarray(G_cells, float), 0, None)
    IL, I0, Rs, Rsh, nV = pvlib.pvsystem.calcparams_desoto(
        np.maximum(G, 1e-3), np.asarray(T_cells, float), p["alpha_sc"], p["a_ref"], p["I_L_ref"], p["I_o_ref"],
        p["R_sh_ref"], p["R_s"], EgRef=p["EgRef"], dEgdT=p["dEgdT"])
    IL = np.where(G > 0, IL, 0.0)
    return IL / 2, I0 / 2, 2 * Rs / 72, 2 * Rsh / 72, nV / 72


def module_pmax(G_map, T_cell, topology: str = "T1", n_i: int = 300) -> dict:
    """Maximum power of the module for a 6×24 cell irradiance map (W/m²) at one cell temperature (°C)."""
    G_map = np.asarray(G_map, float).reshape(NX, NY)
    IL, I0, Rs, Rsh, nV = cell_params(G_map, np.full((NX, NY), float(T_cell)))
    IL, I0, Rsh, nV = (np.broadcast_to(x, (NX, NY)) for x in (IL, I0, Rsh, nV))
    Rs = float(np.asarray(Rs).ravel()[0]) if np.ndim(Rs) else float(Rs)
    imax = float(IL.max()) * 2.05 + 1e-6
    i_mod = np.linspace(0, imax, n_i)
    v_mod = np.zeros_like(i_mod)
    group_v = []
    for grp in strings(topology):
        # string V(I) on a common string-current grid
        i_s = np.linspace(0, max(float(IL.max()) * 1.05, 1e-6), n_i)
        curves = []
        for s in grp:
            c = np.array(s)
            v = pvlib.pvsystem.v_from_i(i_s[:, None], IL[c[:, 0], c[:, 1]][None, :], I0[c[:, 0], c[:, 1]][None, :], Rs,
                                        Rsh[c[:, 0], c[:, 1]][None, :], nV[c[:, 0], c[:, 1]][None, :])
            curves.append(np.asarray(v, float).sum(axis=1))          # V_string(I), decreasing in I
        # parallel strings: I_group(V) = Σ I_string(V) on a common voltage grid
        vmin = min(c.min() for c in curves); vmax = max(c.max() for c in curves)
        vg = np.linspace(vmin, vmax, n_i)
        ig = sum(np.interp(vg, c[::-1], i_s[::-1], left=i_s[-1], right=0.0) for c in curves)
        # back to V_group(I) on the module current grid (I_group decreasing in V), then the bypass clamp
        v_of_i = np.interp(i_mod, ig[::-1], vg[::-1], left=vg[-1], right=vmin)
        v_of_i = np.maximum(v_of_i, V_BYPASS)
        group_v.append(v_of_i)
        v_mod += v_of_i
    p = i_mod * v_mod
    k = int(np.argmax(p))
    bypassed = [bool(gv[k] < 0) for gv in group_v]
    return {"p_mp": float(p[k]), "i_mp": float(i_mod[k]), "v_mp": float(v_mod[k]), "bypassed": bypassed}


def mismatch_factor(G_map, T_cell, topology="T1") -> float:
    """P_max(map) / P_max(uniform map with the same mean irradiance)."""
    G_map = np.asarray(G_map, float)
    mean = float(G_map.mean())
    if mean <= 0:
        return 1.0
    p_map = module_pmax(G_map, T_cell, topology)["p_mp"]
    p_uni = module_pmax(np.full((NX, NY), mean), T_cell, topology)["p_mp"]
    return p_map / p_uni if p_uni > 0 else 0.0


def weakest_cell_factor(G_map, topology="T1") -> float:
    """Fast first approximation (v1 idea, now topology-aware): each string carries the current of its weakest cell,
    parallel strings add, bypass groups that cannot carry the operating current are skipped."""
    G_map = np.asarray(G_map, float).reshape(NX, NY)
    caps = []
    for grp in strings(topology):
        caps.append(sum(min(G_map[c, r] for c, r in s) for s in grp) / 2.0)
    mean = float(G_map.mean())
    if mean <= 0:
        return 1.0
    best = max(I * sum(1 for c in caps if c >= I - 1e-12) / 3.0 for I in caps)
    return best / mean
