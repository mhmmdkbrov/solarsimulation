"""Assemble the three static pages for GitHub Pages (docs/).

Order of the pipeline (Python → export → static site):
    python -m solarsim.fetch_all            # raw PVGIS downloads (server side), stored with request metadata
    python -m solarsim.build                # docs/data/<dataset>.json + docs/data/index.json (all numbers)
    python simulator/build_simulator.py     # docs/index.html, docs/lab.html, docs/simulator.html (JS inlined)
The pages load the datasets at run time; no number is typed into a page by hand.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "docs"
SKELETON_HEAD = """<!doctype html>
<html lang="az">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>
"""


def to_site(page: str) -> str:
    """Wrap a page body (no <html>/<head>/<body>) into a full standalone HTML document."""
    cut = page.index('<div class="wrap"')
    return SKELETON_HEAD + page[:cut] + "</head>\n<body>\n" + page[cut:] + "\n</body>\n</html>\n"


def main():
    js = {name: (HERE / f"{name}.js").read_text(encoding="utf-8") for name in ("datastore", "model", "lensoptics")}
    pages = {"index.html": "lens_template.html", "lab.html": "lab_template.html", "simulator.html": "template.html"}
    SITE.mkdir(exist_ok=True)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    for out, tpl in pages.items():
        t = (HERE / tpl).read_text(encoding="utf-8")
        t = t.replace("__DATASTORE__", js["datastore"]).replace("__MODEL__", js["model"]).replace("__LENSOPTICS__", js["lensoptics"])
        for leftover in ("__DATASTORE__", "__MODEL__", "__LENSOPTICS__", "__DATA__", "__CASES__", "__LABDATA__"):
            assert leftover not in t, f"{tpl}: placeholder {leftover} left"
        (SITE / out).write_text(to_site(t), encoding="utf-8")
        print(f"docs/{out}: {(SITE / out).stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
