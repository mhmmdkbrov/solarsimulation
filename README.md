# Bakı üçün günəş qurğusu simulyasiyası (PV, optik retrofit, CPV)

Fiziki prototipdən əvvəl aparılan mühəndislik qiymətləndirməsi. Eyni xarici işıqtoplama sahəsində (1 modul, 1,998 m²)
dörd ssenarinin **illik xalis DC enerjisi** müqayisə olunur:

| Kod | Ssenari |
|---|---|
| `A_fixed` | Adi, sabit panel Trina Vertex S+ TSM-450NEG9R.28 (35°, cənub) |
| `B_fixed` | Eyni panel + zavod şüşəsinin üstündə əlavə optik qat (retrofit), eyni istiqamət |
| `A_2axis` | Eyni adi panel, 2 oxlu izləmə (CPV ilə eyni strategiya) |
| `C_2axis` | CPV: linza → kiçik fotoelement, 2 oxlu izləmə, yalnız birbaşa işıq |

Meteoroloji məlumat: **PVGIS 5.3 TMY** (Avropa Komissiyası JRC), 40,41° N, 49,87° E. Model: `pvlib` (PVWatts DC, SAPM temperaturu, Perez).
İzahlar Azərbaycan dilindədir, kod identifikatorları ingilis dilindədir.

## Onlayn baxmaq

* **Linza günəş panelini gücləndirirmi?** Sadə vizual izah, hava şəraitini seçmək olur:
  https://mhmmdkbrov.github.io/solarsimulation/
* **Linza laboratoriyası.** Linzanın gücünü (dioptriya), məsafəsini, düzülüşünü və materialını dəyişmək olur. Şüaların yolu və hüceyrə xəritəsi göstərilir:
  https://mhmmdkbrov.github.io/solarsimulation/lab.html
* **Bakı günəş simulyatoru.** Bütün fərziyyələri sürgülərlə dəyişmək olur:
  https://mhmmdkbrov.github.io/solarsimulation/simulator.html

Hər iki səhifə `docs/` qovluğundadır və GitHub Pages ilə yayımlanır. Quraşdırma tələb etmir.

**Əsas nəticə (baza fərziyyələr, Bakı, il ərzində):** adi panel 355 kWh/m². Orta keyfiyyətli linza qatı ilə 311 kWh/m² (−13%).
Mükəmməl linzanın nəzəri yuxarı həddi +8%-dir. CPV (2 oxlu izləmə) eyni izləməli adi panelin 0,69-u qədərdir.

**Linza gücü testləri (həndəsi optika, Bakının bütün ili, material 92% ötürür).** +3, −3, +10 və −10 dioptriyanın hamısı adi paneldən az verir:
hər hüceyrəyə kiçik linza ilə ən yaxşı halda −6%…−10%, bütün panelə bir böyük linza ilə −12%…−38%. Fokusda isə −100%-ə qədər.
Fiziki mümkün ən yaxşı variant hər hüceyrəyə ayrıca linzadır: +13,5 D, hüceyrədən 8 mm hündürlükdə. Onun nəticəsi adi materialla −4,9%,
əks olunmaya qarşı örtüklə −0,8%, itkisiz (nəzəri) materialla +3,3%-dir. Model və testlər: `simulator/lensoptics.js`, `simulator/lens_tests.js`.

**Təqdimat qaralamasındakı rəqəmlərin yoxlanması** (`simulator/claims_check.js`, nəticələr linza laboratoriyasının sonunda):

| Qaralamadakı iddia | Düzgün hesab | Nəticə |
|---|---|---|
| Lupa +3…+10 D, fokus 10–33 sm | f = 1/D: 33,3 sm və 10,0 sm | Düzdür |
| Belə lupalar 2–4 dəfə böyüdür | +3 D: 0,75–1,75×, +10 D: 2,5–3,5× | Qismən düzdür |
| Panellərin səmərəliliyi 20–22% | Trina: 22,5% (STC) | Düzdür |
| 20% panel + C = 5 → ~55% | Səmərəlilik konsentrasiya ilə artmır. Silikon üçün nəzəri hədd 29,4%-dir. C = 5 (DNI 1000 W/m², linza 90%): soyutma ilə 15,9%, soyutmasız 10,0% və hüceyrə 170 °C (pasportda maks. 85 °C). Eyni sahədə 5 adi panel: 20,3% | Səhvdir |
| Linzalar enerjini 50–70% artırır | Bakıda il ərzində: C = 5 linza sistemi 248 kWh/m², adi sabit panel 355, izləməli adi panel 448 kWh/m² (−30% və −45%) | Səhvdir |
| Kvars 1000 °C, borosilikat 500 °C, şəffaflıq 90%+ | Material üçün təxminən düzdür, amma silikon hüceyrə 85 °C-dən yuxarı işləyə bilməz | Qismən düzdür |
B və C üzrə optika və fotoelement parametrləri fərziyyədir, prototipdə ölçülməlidir.

## Fayllar

| Fayl / qovluq | Məzmun |
|---|---|
| `solar_simulation.ipynb` | Əsas notebook. Parametrlər, məlumat, modellər, yoxlamalar, həssaslıq, 4 qrafik, nəticələr |
| `requirements.txt` | Python asılılıqları |
| `data/pvgis_tmy_<lat>N_<lon>E.csv`, `..._meta.json` | PVGIS API-dən yüklənmiş TMY-nin yerli keşi və metadata-sı |
| `data/pvgis_tmy_user.csv` | (istəyə bağlı) əl ilə yüklənmiş PVGIS TMY CSV |
| `sources/README.md` | Parametrlərin yoxlandığı rəsmi texniki pasportun linki (PDF müəllif hüququna görə depoya daxil edilməyib) |
| `results/hourly_results_baku.csv` | 8760 saatlıq nəticə (UTC və Bakı vaxtı, meteo, POA, hər ssenari üçün DC/sərf/xalis W, hüceyrə temperaturu, CPV optik gücləri) |
| `results/parameters.csv` | Hər parametrin dəyəri, vahidi, statusu və mənbəyi |
| `results/checks.csv` | Yoxlamaların nəticəsi |
| `results/annual_summary.csv`, `monthly_net_kWh_m2.csv`, `annual_net_ranges_kWh_m2.csv` | İllik və aylıq nəticələr |
| `results/sensitivity_one_at_a_time.csv`, `dc_by_diffuse_fraction_kWh_m2.csv` | Həssaslıq və səma şəraiti üzrə bölgü |
| `results/figures/fig1…fig4_*.png` | Dörd qrafik |

Saatlıq CSV-də addım 1 saatdır. Ona görə hər sətirdəki `W` dəyəri (saat ərzində orta güc) həmin saatın `Wh` enerjisinə bərabərdir.
Bakı vaxtında aylıq cəmlərdə 31 dekabrın son 4 UTC saatı (gecə) yanvara düşür.

## İşə salma (Windows, PowerShell)

```powershell
git clone https://github.com/mhmmdkbrov/solarsimulation.git
cd solarsimulation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m ipykernel install --sys-prefix --name sunlight --display-name "Python (sunlight .venv)"
```

İnteraktiv iş üçün JupyterLab açın və “Python (sunlight .venv)” kernelini seçin:

```powershell
python -m jupyterlab solar_simulation.ipynb
```

Notebook-u başdan sona brauzersiz icra etmək üçün (nəticələr notebook-un içinə yazılır):

```powershell
python -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=sunlight --ExecutePreprocessor.timeout=1200 solar_simulation.ipynb
```

`python -m jupyter ...` əvəzinə `python -m nbconvert` / `python -m jupyterlab` istifadə edin. Əks halda sistemdəki başqa
Jupyter quraşdırılması işə düşə və pvlib-i tapmaya bilər.

macOS/Linux üçün `.venv/bin/activate` istifadə edin, qalan əmrlər eynidir.

## İnteraktiv simulyator

`simulator/baku_solar_simulator.html` notebook-dakı modelin brauzer versiyasıdır. Sürgülərlə B, C və izləmə fərziyyələrini dəyişin;
illik, aylıq, gündəlik nəticələr və CPV hədd xəritəsi dərhal yenidən hesablanır. Fayl tək başına işləyir: brauzerdə açmaq kifayətdir.
“Notebook üçün kopyala” düyməsi seçilmiş parametrləri notebook-a yapışdırmaq üçün Python kodu kimi verir.

Notebook-u dəyişdikdən sonra (məsələn, koordinat və ya maililik) simulyatoru yeniləmək üçün:

```powershell
.\.venv\Scripts\python simulator\export_web.py simulator\data.json
node simulator\verify.js
.\.venv\Scripts\python simulator\build_simulator.py
```

`verify.js` JS modelinin notebook-un baza, pessimist və optimist nəticələrini tam təkrarladığını yoxlayır.

Linza laboratoriyası (`docs/lab.html`) üçün əvvəlcə `node simulator/lens_tests.js simulator/lens_tests.json` icra olunur.
Bu skript optika modelini yoxlayır və dioptriya testlərini hesablayır. Sadə izah səhifəsi (`docs/index.html`) üçün hava tipləri və illik nəticələr `node simulator/lens_cases.js simulator/lens_cases.json`
əmri ilə yenidən hesablanır. `build_simulator.py` hər iki səhifəni həm `simulator/`, həm də sayt üçün `docs/` qovluğuna yazır.

## Lisenziya

Kod [MIT](LICENSE) lisenziyası ilə açıqdır. PVGIS məlumatı Avropa Komissiyasının təkrar istifadə qaydası (CC BY 4.0) ilə işlədilir.

## Meteoroloji məlumat

Notebook məlumatı bu ardıcıllıqla axtarır: yerli keş → PVGIS API (`https://re.jrc.ec.europa.eu/api/v5_3/tmy`) →
`data/pvgis_tmy_user.csv` → **NÜMUNƏ MƏLUMAT** (açıq səma modeli). Nümunə məlumat işlədilərsə, cədvəllər, qrafiklər və CSV
faylının adı (`hourly_results_SAMPLE_DATA.csv`) bunu açıq göstərir. Bunu söndürmək üçün parametrlər xanasında
`ALLOW_SAMPLE_DATA = False` yazın.

**PVGIS CSV-ni əl ilə yükləmək:**
1. https://re.jrc.ec.europa.eu/pvg_tools/en/ açın və **TMY** bölməsini seçin.
2. Koordinatları daxil edin (40.41, 49.87) və standart radiasiya bazasını (PVGIS-SARAH3) saxlayın.
3. **CSV** formatında yükləyin, faylı `data/pvgis_tmy_user.csv` adı ilə saxlayın və notebook-u yenidən işə salın.

Koordinatları dəyişmək üçün parametrlər xanasında `SITE["latitude"]` və `SITE["longitude"]` dəyərlərini dəyişin. Hər koordinat cütü üçün ayrıca keş faylı yaradılır.

## Parametr statusları

`texniki pasport`, `meteoroloji məlumat`, `elmi mənbə`, `fərziyyə`, `ölçülməlidir`. Tam siyahı `results/parameters.csv` faylındadır.

**Texniki pasport qeydi:** Tapşırıqda verilən `Datasheet_Vertex S+_NEG9R.28_EN_2024_C_web.pdf` keçidi 2026-11-08 tarixində
`BlobNotFound` qaytardı. Parametrlər Trina-nın rəsmi serverindəki `TSM_EN_2023_B` (MEA) versiyası ilə yoxlanıb.
450 W, 1762×1134 mm, 22,5%, NOCT 43±2 °C və NOCT gücü 343 W təsdiqlənir. `Pmax` temperatur əmsalı bu versiyada **−0,30%/°C**-dir, tapşırıqda isə −0,29%/°C verilib.
Baza hesabda yoxlanmış dəyər işlədilir, −0,29%/°C-nin təsiri isə notebook-da ayrıca hesablanır.

## Məhdudiyyətlər (ilk versiya)

* B və C üzrə optik, istilik, fotoelement və köməkçi sərf rəqəmləri **fərziyyədir**. Linza, optik qat, fotoelement və soyutma hələ seçilməyib.
  Bu rəqəmlərdən kommersiya məhsulu barədə nəticə çıxarmaq olmaz.
* CPV-də səpələnmiş işığın elektrik töhfəsi sıfırdır. Fotoelement səmərəliliyinin intensivlikdən asılılığı nəzərə alınmır.
* Retrofitdə qeyri-bərabər işıqlanmanın təsiri sabit itki payı kimi verilib. Hüceyrə üzrə işıq xəritəsi əldə edildikdə,
  ardıcıl hüceyrələrdə cərəyan uyğunsuzluğu I–V modeli ilə ayrıca hesablanmalıdır.
* PVWatts I–V əyrisi vermir. pvlib-in CEC verilənlər bazasında TSM-450NEG9R.28 yoxdur, ona görə CEC/De Soto modeli əlavə edilməyib.
  Lazım olsa, pasport dəyərlərindən `pvlib.ivtools.sdm.fit_cec_sam` (NREL-PySAM tələb edir) ilə parametr çıxarıla bilər.
* İzləmə idealdır (məhdudiyyət, kölgə və külək rejimi yoxdur). Çirklənmə 0 qəbul edilir. Spektral təsir nəzərə alınmır.
