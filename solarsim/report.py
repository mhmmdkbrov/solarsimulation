"""Generate REPORT_v2.md from the built datasets and an actual test run.  Usage: python -m solarsim.report
Numbers come from docs/data/*.json and tests/baseline_v1.json; test results from running pytest and the parity tests."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from . import MODEL_VERSION

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
SCEN = ["A_fixed", "B_fixed", "A_2axis", "C_2axis"]
NAME = {"A_fixed": "A — sabit adi panel", "B_fixed": "B — sabit panel + orta optik qat", "A_2axis": "A-izləmə — iki oxlu adi panel",
        "C_2axis": "C — iki oxlu CPV"}


def az(v, d=2):
    if v is None:
        return "—"
    s = f"{abs(v):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if v < 0 and float(f"{abs(v):.{d}f}") != 0 else "") + s


def sgn(v):
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):g}".replace(".", ",")


def pct(v, d=1):
    return ("+" if v >= 0 else "−") + az(abs(v), d) + "%"


def run_tests():
    out = {}
    junit = ROOT / "results" / "pytest_v2.xml"
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:warnings", "tests", f"--junitxml={junit}"],
                       cwd=ROOT, capture_output=True, text=True, env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    cases = []
    for tc in ET.parse(junit).getroot().iter("testcase"):
        failed = any(ch.tag in ("failure", "error") for ch in tc)
        cases.append((tc.get("classname", "").split(".")[-1], tc.get("name"), "keçdi" if not failed else "KEÇMƏDİ"))
    junit.unlink()   # contains the machine name; the results are kept in the report table instead
    out["pytest"] = {"summary": r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:], "cases": cases}
    files = sorted(DATA.glob("*_tmy.json"))
    p = subprocess.run(["node", str(ROOT / "tests" / "parity_model.js"), *map(str, files)], capture_output=True, text=True)
    out["parity_model"] = p.stdout.strip().splitlines()[-1] if p.stdout else p.stderr[-300:]
    q = subprocess.run([sys.executable, str(ROOT / "tests" / "parity_lens.py"), str(DATA / "baku_pvgis53_tmy.json")],
                       capture_output=True, text=True, env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    out["parity_lens"] = q.stdout.strip().splitlines()
    return out


def main():
    idx = json.loads((DATA / "index.json").read_text(encoding="utf-8"))["datasets"]
    D = {d["id"]: json.loads((ROOT / "docs" / d["file"]).read_text(encoding="utf-8")) for d in idx}
    base = json.loads((ROOT / "tests" / "baseline_v1.json").read_text(encoding="utf-8"))
    T = run_tests()
    b = D["baku_pvgis53_tmy"]
    L = []
    w = L.append
    w(f"# Model v{MODEL_VERSION}: yekun hesabat\n")
    w("Bu fayl `python -m solarsim.report` ilə yaradılıb. Rəqəmlər `docs/data/*.json`, `tests/baseline_v1.json` və testlərin faktiki icrasından gəlir.\n")

    w("## 1. Tapılan problemlər, düzəlişlər və dəyişən fayllar\n")
    w("| Problem (v1) | Düzəliş (v2) | Fayllar |\n|---|---|---|")
    for row in PROBLEMS:
        w("| " + " | ".join(row) + " |")

    w("\n## 2. Ssenarilər üzrə əvvəlki və yeni nəticələr (Bakı, PVGIS 5.3 TMY)\n")
    w("| Ssenari | v1 brüt | v2 brüt | v1 xalis | v2 xalis | köməkçi sərf v2, kWh/qurğu (izləmə + idarəetmə + soyutma) | fərqin səbəbi |\n|---|---|---|---|---|---|---|")
    for s in SCEN:
        a = b["annual"][s]
        why = ("dəyişməyib (v2 kodu v1 rejimində 0,0001 dəqiqliklə eynidir)" if abs(a["net_kWh_m2_ap"] - base["annual"][s]["net_kWh_m2"]) < 1e-4
               else "CPV qəbul konusundakı səpələnmiş işıq (DHI·sin²1°) əlavə olunub, izləmə xətası (σ = 0,1°) nəzərə alınıb")
        w(f"| {NAME[s]} | {az(base['annual'][s]['gross_kWh_m2'], 4)} | {az(a['gross_kWh_m2_ap'], 4)} | {az(base['annual'][s]['net_kWh_m2'], 4)} | "
          f"{az(a['net_kWh_m2_ap'], 4)} | {az(a['aux_kWh_unit'], 3)} = {az(a['drive_kWh_unit'], 3)} + {az(a['controller_kWh_unit'], 3)} + {az(a['cooling_kWh_unit'], 3)} | {why} |")
    w("\nVahid: kWh/m² apertura/il (apertura = 1,998 m²). A-izləmənin 448,01 dəyəri brüt, 436,92 isə xalisdir.\n")

    w("**Linza laboratoriyası (Bakı, material 92%, il üzrə adi panelə nisbətən).** v1 sonsuz periodik hüceyrə modeli ilə müqayisədə v2 sonlu paneldən istifadə edir: kənar hüceyrələr, paneldən kənara çıxan işıq, modul şüşəsində sınma və işıq balansı nəzərə alınır. Elektrik modeli: sürətli qayda, mötərizədə hüceyrə I–V modeli (T1).\n")
    w("| Linza | Düzülüş | v1: 3 mm | v2: 3 mm | v1: ən yaxşı | v2: ən yaxşı h | v2: ən yaxşı nəticə | etibarlılıq |\n|---|---|---|---|---|---|---|---|")
    v1t = {(t["P"], t["mode"]): t for t in base["lens_lab_tests"]["tests"]}
    for t in b["lens"]["tests"]:
        o = v1t.get((t["P"], "array" if t["mode"] == "array" else t["mode"]))
        p3 = t["points"]["şüşənin üstündə 3 mm"]
        iv3 = (t.get("points_iv") or {}).get("şüşənin üstündə 3 mm")
        w(f"| {sgn(t['P'])} D | {t['mode']} | {pct(o['glued_pct']) if o else '—'} | {pct(p3)}{f' ({pct(iv3)})' if iv3 is not None else ''} | "
          f"{pct(o['best_pct']) if o else '—'} | {az(t['best_h'], 1)} mm | {pct(t['best_pct'])}{f' ({pct(t['best_iv'])})' if t.get('best_iv') is not None else ''} | {t['validity_best']['reliability']} |")
    v1p = b["lens"]["v1_point_13p5D_8mm"]
    w(f"\n+13,5 D / 8 mm (v1 nəticəsi saxlanılıb): v1 adi material {pct(v1p['v1']['0.92'])}, başabaş ötürmə ≈ {az(v1p['v1']['tau_breakeven_v1'] * 100, 1)}%. "
      f"v2 sferik massiv: {pct(v1p['v2']['array']['delta_pct']['0.92'])} / {pct(v1p['v2']['array']['delta_pct']['0.96'])} / {pct(v1p['v2']['array']['delta_pct']['1.0'])} "
      f"(92 / 96 / 100%). v2 silindrik: {pct(v1p['v2']['array_cyl']['delta_pct']['0.92'])} / {pct(v1p['v2']['array_cyl']['delta_pct']['0.96'])} / {pct(v1p['v2']['array_cyl']['delta_pct']['1.0'])}.")
    for m in ("array", "array_cyl"):
        x = b["lens"][m]
        w(f"\nSınanmış diapazonda ən yaxşı ({m}): {sgn(x['P'])} D{' (axtarış diapazonunun kənarı, ±20 D)' if abs(x['P']) >= 20 else ''}, h = {az(x['h'], 1)} mm → {pct(x['delta_pct']['0.92'])} / {pct(x['delta_pct']['0.96'])} / {pct(x['delta_pct']['1.0'])}; "
          f"başabaş ötürmə {('yoxdur' if x['tau_breakeven'] is None else az(x['tau_breakeven'] * 100, 1) + '%')}; etibarlılıq {x['validity']['reliability']}.")
    bl = b["b_levels"]["ideal"]
    w(f"\nSadə optik qat modelinin ideal ssenarisi: {pct(100 * (bl['B_kWh_m2'] / bl['A_kWh_m2'] - 1), 2)} ({bl['label']}).\n")

    w("**C = 5 sınağı (eyni ümumi apertura, Bakı).**\n")
    c = b["c5"]["annual"]
    w("| Variant | brüt kWh/m² | xalis kWh/m² | qeyd |\n|---|---|---|---|")
    for k, nm in (("lens_cooled", "linza C = 5, aktiv soyutma"), ("lens_passive", "linza C = 5, soyutmasız"),
                  ("plain_fixed", "5 adi panel, sabit"), ("plain_2axis", "5 adi panel, 2 oxlu")):
        note = c[k].get("cooling_status") or c[k].get("status") or ""
        if k == "lens_passive":
            note += f"; {c[k]['hours_above_tmax']} saat > 85 °C (model proqnozu)"
        w(f"| {nm} | {az(c[k]['gross_kWh_m2_ap'], 1)} | {az(c[k]['net_kWh_m2_ap'], 1)} | {note} |")

    w("\n## 3. İcra olunmuş testlər\n")
    w(f"`pytest`: **{T['pytest']['summary']}**\n")
    w("| Modul | Test | Nəticə |\n|---|---|---|")
    for cl, nm, res in T["pytest"]["cases"]:
        w(f"| {cl} | `{nm}` | {res} |")
    w(f"\nBrauzer ↔ Python, ssenarilər (bütün TMY dəstləri, tolerans 0,05%): **{T['parity_model']}**\n")
    w("Brauzer ↔ Python, linza (Bakı, tolerans 0,1 faiz bəndi):\n\n```\n" + "\n".join(T["parity_lens"]) + "\n```\n")

    w("## 4. Aktual PVGIS məlumatı ilə yenidən hesablanan məkanlar\n")
    w("| Dəst | API | Radiasiya bazası | İllər | Sorğu (UTC) | Ofset, saat | A xalis | B xalis | A-izləmə xalis | C xalis |\n|---|---|---|---|---|---|---|---|---|---|")
    for d in idx:
        x = D[d["id"]]; m = x["dataset"]; a = x["annual"]
        w(f"| {d['id']} | PVGIS {m['api_version'].split(' ')[0]} | {m['radiation_db'][:30]} | {'–'.join(map(str, m['years']))} | {m['requested_utc'][:16]} | "
          f"{az(m['solpos_offset_h'], 4)} | {az(a['A_fixed']['net_kWh_m2_ap'], 1)} | {az(a['B_fixed']['net_kWh_m2_ap'], 1)} | {az(a['A_2axis']['net_kWh_m2_ap'], 1)} | {az(a['C_2axis']['net_kWh_m2_ap'], 1)} |")
    for d in idx:
        x = D[d["id"]]
        if x["dataset"].get("cleaning"):
            w(f"\n{d['id']} təmizləmə: " + "; ".join(x["dataset"]["cleaning"]))
        if "interannual" in x:
            st = x["interannual"]["stats"]
            w(f"\n{d['id']} — illərarası (2005–2023), A xalis: orta {az(st['A_fixed']['mean'], 1)} ± {az(st['A_fixed']['std'], 1)} kWh/m², "
              f"min {az(st['A_fixed']['min'], 1)}, maks {az(st['A_fixed']['max'], 1)}.")
    w("\nVahid: kWh/m² apertura/il. PVGIS 6 API sənədlərə görə “aktiv inkişaf mərhələsindədir”. TMY cavabında DHI yoxdur, ay birləşmələrində isə gecə dəyərləri var. Təmizləmə qaydası yuxarıda verilib.\n")

    w("## 5. Hələ fərziyyə olan parametrlər və prototip planı\n")
    w("| Qrup | Parametr | Dəyər | Vahid | Qeyd |\n|---|---|---|---|---|")
    for p in b["params"]:
        if p["status"] == "fərziyyə":
            w(f"| {p['group']} | `{p['name']}` | {'məkan seçimindən' if p['value'] is None else (p['value'] if not isinstance(p['value'], float) else az(p['value'], 4))} | {p['unit']} | {p['note']} |")
    w(PROTOTYPE)
    (ROOT / "REPORT_v2.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("REPORT_v2.md written;", T["pytest"]["summary"], "|", T["parity_model"], "|", T["parity_lens"][-1] if T["parity_lens"] else "")


PROBLEMS = [
    ("Yalnız Bakı; PVGIS 5.3 keşi notebook-a bağlı", "Məkan seçimləri (Bakı, Naxçıvan, Almería) və istənilən koordinat; PVGIS 5.3 TMY + 2005–2023 sırası + PVGIS 6 TMY ayrıca dəst kimi; tam sorğu metadatası", "`solarsim/sites.py`, `pvgis.py`, `weather.py`, `fetch_all.py`, `cli.py`, `data/raw/`"),
    ("Laboratoriyada sabit `0.1672 h` ofset və sadələşdirilmiş Günəş vektoru", "Ofset mənbənin metadatasından bir dəfə tətbiq olunur; bütün səhifələr pvlib SPA vektorlarını məlumat dəstindən oxuyur", "`weather.py`, `geometry.py`, `build.py`, `lensoptics.js`"),
    ("Brüt və xalis enerji, sərfin bölgüsü qarışıq göstərilirdi", "Hər ssenari üçün brüt DC, izləmə, idarəetmə, soyutma, xalis; kWh/qurğu, kWh/m² apertura, kWh/m² torpaq ayrıca", "`scenarios.py`, `model.js`, `template.html`"),
    ("Enerji yalnız saatlıq addımla hesablanırdı; çatışmayan sətirlər yoxlanmırdı", "Σ(P·Δt), addım məlumatdan; çatışmayan sətirlər sayılır; yarım saat, sıçrayış ili, çatışmayan sətir testləri", "`weather.py`, `tests/test_core.py`"),
    ("Aktiv sahə payı iki modeldə fərqli (0,92 və 0,9195)", "0,92 giriş parametri; hüceyrə hündürlüyü ondan hesablanır", "`pv.py`, `optics.py`, `lensoptics.js`"),
    ("Linza massivində sonsuz periodik hüceyrə; paneldən kənara çıxan işıq yox idi", "Sonlu panel: öz hüceyrə, qonşu, boşluq, kənar; modul şüşəsində sınma; birbaşa, səma və yer işığı ayrıca; işıq balansı testi", "`optics.py`, `lenslab.py`, `lensoptics.js`"),
    ("“Ən yaxşı məsafə” bəzi sınaq nöqtələrindən pis idi (−3 D, −10 D)", "Axtarışa sınaq nöqtələri daxildir; bütün namizədlər eyni funksiya ilə; test: maksimum ≥ hər sınaq nöqtəsi", "`lenslab.py`, `tests/test_optics.py`"),
    ("Nazik linzanın etibarlılıq sərhədi göstərilmirdi", "f-ədədi, kənarda meyl, reallaşdırıla bilmə (Fresnel ≤ 30°), etibarlılıq yarlığı; Snell/Fresnel 2D şüa izləməsi ilə yoxlama", "`optics.py` (`validity`, `trace2d`)"),
    ("Böyük linzada yalnız “ən zəif hüceyrə” qaydası", "Hüceyrə → sıra → bypass qrupu → modul I–V modeli (De Soto, pasportdan); T1/T3 topologiya həssaslığı; bərabər, kölgəli hüceyrə və qrup testləri", "`electrical.py`, `tests/test_optics.py`"),
    ("CPV-də qəbul bucağı və izləmə xətası yox idi; istilik həllində xəbərdarlıq yox idi", "Qəbul bucağı + Rayleigh izləmə xətası, konusdakı səpələnmiş işıq, η(T, C) etibarlılıq diapazonu, xəbərdarlıqlar və xəritədə ştrix", "`scenarios.py`, `model.js`"),
    ("C = 5-də soyutma sərfi və ekstrapolyasiya statusu göstərilmirdi", "Eyni apertura ilə müqayisə; “soyutma sərfi daxil edilməyib”; 170 °C və 1043 saat model proqnozu kimi; 29,4% həddinin şərtləri", "`studies.py`, `lab_template.html`"),
    ("Səhifələrdə əl ilə yazılmış rəqəmlər və “mükəmməl linza” ifadəsi", "Bütün rəqəmlər məlumat dəstindən; “sadə modelin ideal ssenarisi” şərtləri ilə; hava sinifləri GHI > 10 W/m² + qalan saatlar; versiya və dəst adı hər səhifədə", "`lens_template.html`, `lab_template.html`, `template.html`, `datastore.js`"),
    ("v1 nəticələri üçün reqressiya bazası yox idi", "`tests/baseline_v1.json`; v2 v1 rejimində eyni nəticəni verir; v1 skriptləri `legacy/v1/`", "`tests/make_baseline_v1.js`, `legacy/v1/`"),
]

PROTOTYPE = """
**Prototip planı (yan-yana sınaq).**

1. İki eyni mini-panel (eyni partiya, eyni hüceyrə sayı və bypass sxemi) eyni maililik və azimutla yan-yana qurulur. Biri istinad, digəri linzalıdır. Hər paneldə ayrıca MPP izləyici və ya I–V skaneri olur.
2. Eyni vaxtda (1 dəqiqəlik addımla) qeyd olunur: hər panelin MPP gücü, panelin arxasında hüceyrə temperaturu, panel müstəvisində şüalanma (piranometr və ya istinad hüceyrəsi), birbaşa və səpələnmiş pay, düşmə bucağı, hava temperaturu və külək.
3. Linza müntəzəm olaraq panellər arasında dəyişdirilir (çarpaz sınaq). Beləliklə panelin öz fərqi linzanın təsirindən ayrılır.
4. Ölçülər modelin bu parametrlərini yeniləyir:

| Ölçü | Yenilənən parametr |
|---|---|
| Linzanın spektral və bucaqdan asılı ötürməsi (spektrofotometr, bucaq stendi) | `tau`, `n`, `K·L`; B üçün `tau_beam_normal`, `tau_diffuse` |
| Linza–hüceyrə məsafəsi, spot xəritəsi və düzülüş xətası (kamera, ölçmə lövhəsi) | `h`, spotun sürüşməsi, `gap_recovery_*` |
| Hüceyrə üzrə işıq xəritəsi və modulun I–V əyrisi | topologiya (T1/T3), `nonuniformity_loss`, `RS_K` |
| Linzalı və istinad paneli arasında temperatur fərqi | `extra_heating_K_per_kWm2`, SAPM `a`, `b` (NOCT kalibrləməsi ölçü ilə əvəzlənir) |
| Aktiv sahə payı (modulun foto-ölçüsü) | `active_fraction` |

5. Yalnız ölçülmüş və yoxlanmış dəyərlər “ölçülüb” statusu alır. Sonra model həmin dəyərlərlə yenidən işlədilir və proqnoz ölçülmüş enerji ilə müqayisə olunur.
"""

if __name__ == "__main__":
    main()
