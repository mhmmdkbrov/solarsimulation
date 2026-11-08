"""Build the interactive simulator page (single self-contained HTML).

Run from the project folder after the notebook has been executed:
    .venv/Scripts/python simulator/export_web.py simulator/data.json
    node simulator/verify.js            # JS model vs. notebook numbers
    .venv/Scripts/python simulator/build_simulator.py
"""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
html = (here / "template.html").read_text(encoding="utf-8")
model = (here / "model.js").read_text(encoding="utf-8")
data = (here / "data.json").read_text(encoding="utf-8").replace("</", "<\\/")
out = here / "baku_solar_simulator.html"
out.write_text(html.replace("__MODEL__", model).replace("__DATA__", data), encoding="utf-8")
print(f"{out.name}: {out.stat().st_size / 1e6:.2f} MB")

# simple explainer "lens vs. ordinary panel" (needs: node simulator/lens_cases.js simulator/lens_cases.json)
cases = here / "lens_cases.json"
if cases.exists():
    lens = (here / "lens_template.html").read_text(encoding="utf-8")
    out2 = here / "linza_vs_adi_panel.html"
    out2.write_text(lens.replace("__CASES__", cases.read_text(encoding="utf-8").replace("</", "<\\/")), encoding="utf-8")
    print(f"{out2.name}: {out2.stat().st_size / 1e3:.0f} kB")

# ---------- static website (GitHub Pages serves the docs/ folder) ----------
SITE = here.parent / "docs"
SKELETON_HEAD = """<!doctype html>
<html lang="az">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>
"""


def to_site(page: str) -> str:
    """Wrap an artifact page (no <html>/<head>/<body>) into a full standalone HTML document."""
    cut = page.index('<div class="wrap">')
    return SKELETON_HEAD + page[:cut] + "</head>\n<body>\n" + page[cut:] + "\n</body>\n</html>\n"


SITE.mkdir(exist_ok=True)

# lens lab (needs: node simulator/lens_cases.js ... and node simulator/lens_tests.js simulator/lens_tests.json)
tests = here / "lens_tests.json"
if cases.exists() and tests.exists():
    full = json.loads((here / "data.json").read_text(encoding="utf-8"))
    year = {"meta": full["meta"], **{k: full[k] for k in ("doy", "hour", "f_glob", "f_beam", "f_diff", "ta", "ws")}}
    labdata = {"rep": json.loads(cases.read_text(encoding="utf-8"))["rep"],
               "tests": json.loads(tests.read_text(encoding="utf-8")), "year": year}
    lab = (here / "lab_template.html").read_text(encoding="utf-8")
    lab = lab.replace("__LENSOPTICS__", (here / "lensoptics.js").read_text(encoding="utf-8"))
    lab = lab.replace("__LABDATA__", json.dumps(labdata, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/"))
    (here / "linza_laboratoriyasi.html").write_text(lab, encoding="utf-8")
    (SITE / "lab.html").write_text(to_site(lab), encoding="utf-8")
    print(f"lab.html: {(SITE / 'lab.html').stat().st_size / 1e3:.0f} kB")
(SITE / ".nojekyll").write_text("", encoding="utf-8")
(SITE / "simulator.html").write_text(to_site(out.read_text(encoding="utf-8")), encoding="utf-8")
if cases.exists():
    page = out2.read_text(encoding="utf-8").replace("https://claude.ai/artifact/S3NXogBuvnbRhZyb6kdH6g", "simulator.html")
    page = page.replace('target="_blank" rel="noopener">ətraflı simulyatorda', '>ətraflı simulyatorda')
    (SITE / "index.html").write_text(to_site(page), encoding="utf-8")
print("site:", sorted(p.name for p in SITE.iterdir()))
