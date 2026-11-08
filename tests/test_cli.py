"""CLI: a dataset for any coordinate from a user CSV (no network), valid for the site."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from solarsim import weather as W
from solarsim.sites import Site


def test_cli_csv_dataset(tmp_path):
    site = Site("t", "Test", 40.6, 47.1, "Asia/Baku", tilt_deg=30.0, elevation_m=100.0)
    ds = W.sample_clear_sky(site, year=2023, step_h=1.0)
    csv = tmp_path / "weather.csv"
    df = ds.df.copy()
    df.insert(0, "time", df.index.strftime("%Y-%m-%dT%H:%M:%SZ"))
    df.to_csv(csv, index=False)
    out = tmp_path / "test.json"
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, "-m", "solarsim.cli", "dataset", "--key", "clitest", "--name", "Test",
                        "--lat", "40.6", "--lon", "47.1", "--tz", "Asia/Baku", "--tilt", "30", "--elevation", "100",
                        "--source", "csv", "--csv", str(csv), "--out", str(out)], capture_output=True, text=True, cwd=root,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 0, r.stderr[-800:]
    D = json.loads(out.read_text(encoding="utf-8"))
    for k in ("version", "dataset", "site", "inputs", "areas", "annual", "hourly"):
        assert k in D
    assert D["hourly"]["n"] == 8760 and len(D["hourly"]["ghi"]) == 8760
    assert D["version"]["model"].startswith("2.")
    assert D["dataset"]["source_label"].startswith("istifadəçi CSV")
    a = D["annual"]
    assert np.isclose(a["A_fixed"]["gross_kWh_unit"] - a["A_fixed"]["aux_kWh_unit"], a["A_fixed"]["net_kWh_unit"])
