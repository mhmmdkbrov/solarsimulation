"""Python ↔ browser parity for the lens model (fast method, T1). Usage: python tests/parity_lens.py docs/data/<id>.json
Tolerance: 0.1 percentage point on the annual lens effect and 0.3 % on the light-balance terms (inputs rounded in the export)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from solarsim import lenslab as LL, optics as O, weather as W   # noqa: E402

CFGS = [(3, 3, "big"), (10, 100, "big"), (-3, 3, "array"), (-10, 100, "array"), (13.5, 8, "array"),
        (13.5, 8, "array_cyl"), (0, 3, "array"), (5, 30, "array")]


def main(path):
    D = json.loads(Path(path).read_text(encoding="utf-8"))
    site, src = D["dataset"]["id"].split("_", 1)
    ds = {"pvgis53_tmy": W.pvgis53_tmy, "pvgis6_tmy": W.pvgis6_tmy}[src](site)
    prep = LL.prepare(ds)
    js = r"""
const L = require(process.argv[1]); const D = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const cfgs = JSON.parse(process.argv[3]);
console.log(JSON.stringify(cfgs.map(([P, h, mode]) => L.annual(D, { P, h, mode, tau: 0.92 }))));
"""
    out = subprocess.run(["node", "-e", js, str(ROOT / "simulator" / "lensoptics.js"), path, json.dumps(CFGS)],
                         capture_output=True, text=True, check=True)
    res_js = json.loads(out.stdout)
    ok = True
    for (P, h, mode), rj in zip(CFGS, res_js):
        rp = LL.annual(prep, O.LensConfig(P, h, mode, 0.92))
        d = abs(rj["delta_pct"] - rp["delta_pct"])
        bal = max(abs(rj["balance_kWh"][k] - rp["balance_kWh"][k]) / max(rp["balance_kWh"]["in"], 1e-9)
                  for k in ("refl_lens", "abs_lens", "refl_glass", "own", "neighbours", "gap", "off"))
        good = d < 0.1 and bal < 0.003
        ok &= good
        print(f"{'OK  ' if good else 'FAIL'} P={P:+5.1f} h={h:6.1f} {mode:9s}: py {rp['delta_pct']:+8.3f}%  js {rj['delta_pct']:+8.3f}%  "
              f"|Δ| {d:.4f} pp  max balance diff {bal * 100:.4f} %")
    print("LENS PARITY OK" if ok else "LENS PARITY FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
