# Günəş paneli, optik qat, linza və CPV: təkrarlana bilən mühəndislik modeli

Fiziki prototipdən əvvəl aparılan mühəndislik qiymətləndirməsi. Eyni işıqtoplama sahəsində (apertura, 1 modul = 1,998 m²)
adi panel, panel üstündə optik qat və linza, eləcə də CPV ssenarilərinin illik **brüt** və **xalis** DC enerjisi müqayisə olunur.
Linzanın qazanc və ya itki verməsini modelin girişləri və yoxlamaları müəyyən edir. Model istənilən məkana tətbiq olunur.
Hazır seçimlər: Bakı, Naxçıvan, Almería.

| Kod | Ssenari |
|---|---|
| `A_fixed` | Adi, sabit panel Trina Vertex S+ TSM-450NEG9R.28 |
| `B_fixed` | Eyni panel + zavod şüşəsinin üstündə əlavə optik qat (sadə model), eyni istiqamət |
| `A_2axis` | Eyni adi panel, 2 oxlu izləmə (C ilə eyni strategiya) |
| `C_2axis` | CPV: linza → kiçik fotoelement, 2 oxlu izləmə |
| Linza laboratoriyası | Dioptriya, məsafə, düzülüş və material ilə həndəsi linza modeli (sonlu panel, işıq balansı, I–V) |

İzahlar Azərbaycan dilindədir, kod identifikatorları ingilis dilindədir.

## Onlayn baxmaq

* Sadə izah: https://mhmmdkbrov.github.io/solarsimulation/
* Linza laboratoriyası: https://mhmmdkbrov.github.io/solarsimulation/lab.html
* Ətraflı simulyator: https://mhmmdkbrov.github.io/solarsimulation/simulator.html
* Linza enerji kalkulyatoru. Paylaşılan Streamlit kalkulyatorunun hesabı olduğu kimi təkrarlanır, yanında düzgün müqayisə və səhvlərin siyahısı verilir:
  https://mhmmdkbrov.github.io/solarsimulation/calculator.html (`simulator/calculator.js` = `solarsim/calculator.py`, testlər `tests/test_calculator.py`)

Hər səhifədə məkan və məlumat dəstini seçmək, yerli JSON faylını açmaq mümkündür. Hesab versiyası və məlumat dəstinin adı da göstərilir.

## Nəticələr

Nəticələr `docs/data/*.json` fayllarından gəlir və `results/*_v2.csv` cədvəllərində saxlanılır. Ən son icranın qısa xülasəsi
[`REPORT_v2.md`](REPORT_v2.md) faylındadır.

## Hesablama axını

```
PVGIS (server tərəfi)  →  data/raw/<məkan>/*.json.gz (+ sorğu metadatası)
        ↓  python -m solarsim.build
docs/data/<dəst>.json   (bütün rəqəmlər: illik, aylıq, hava sinifləri, linza cədvəlləri, C = 5, illərarası)
        ↓  python simulator/build_simulator.py
docs/index.html, docs/lab.html, docs/simulator.html   (statik sayt; JS modelləri Python ilə paritet testindən keçir)
```

| Qovluq / fayl | Məzmun |
|---|---|
| `solarsim/` | Python paketi: `sites`, `pvgis`, `weather`, `geometry`, `pv`, `scenarios`, `optics`, `electrical`, `lenslab`, `studies`, `analysis`, `build`, `cli` |
| `solar_simulation.ipynb` | Paketi işlədən notebook: reqressiya, məlumat dəstləri, modul, ssenarilər, illərarası, linza, CPV, nəticələr |
| `simulator/` | Səhifə şablonları və brauzer modelləri (`model.js`, `lensoptics.js`, `datastore.js`), `build_simulator.py` |
| `docs/` | GitHub Pages saytı və `docs/data/` məlumat dəstləri |
| `data/raw/` | PVGIS-in xam cavabları (gzip) və sorğu metadatası (URL, parametrlər, UTC tarix) |
| `tests/` | `pytest` testləri, brauzer paritet testləri, v1 reqressiya bazası (`baseline_v1.json`) |
| `results/` | v2 cədvəlləri və qrafikləri (v1 faylları müqayisə üçün saxlanılıb) |
| `legacy/v1/` | Əvvəlki modelin skriptləri və məlumatı: v1 bazası buradan təkrarlanır |

## İşə salma

```powershell
git clone https://github.com/mhmmdkbrov/solarsimulation.git
cd solarsimulation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m ipykernel install --sys-prefix --name sunlight --display-name "Python (sunlight .venv)"
```

Məlumatı yükləmək və saytı yenidən qurmaq:

```powershell
python -m solarsim.fetch_all              # PVGIS 5.3 TMY + 2005–2023 saatlıq sıra + üfüq + PVGIS 6 TMY (3 məkan)
python -m solarsim.build                  # bütün dəstlər və tədqiqatlar (bir neçə on dəqiqə); --quick ağır hissələri buraxır
python simulator\build_simulator.py       # docs\*.html
python -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=sunlight --ExecutePreprocessor.timeout=3600 solar_simulation.ipynb
```

Yeni koordinat üçün məlumat dəsti. PVGIS brauzerdən çağırıla bilmir: 5.x versiyası AJAX-ı qadağan edir, 6-cı versiyada isə sərt CORS siyasəti var. Ona görə dəst server tərəfində yaradılır və saytda “Öz məlumat dəstini aç” ilə açılır:

```powershell
python -m solarsim.cli dataset --key seki --name "Şəki" --lat 41.19 --lon 47.17 --tz Asia/Baku --tilt 35 --out seki.json
python -m solarsim.cli dataset --key my --name "Mənim məlumatım" --lat 40.4 --lon 49.9 --tz Asia/Baku --tilt 35 --source csv --csv my.csv --offset 0 --out my.json
```

CSV sütunları: `time` (UTC, ISO), `ghi`, `dni`, `dhi` [W/m²], `temp_air` [°C], `wind_speed` [m/s]. `--add-to-site` dəsti `docs/data/` siyahısına əlavə edir.

## Testlər

```powershell
python -m pytest -q tests                                   # model, vaxt, enerji, optika, I–V, CLI
node tests\parity_model.js docs\data\baku_pvgis53_tmy.json  # brauzer ↔ Python: ssenarilər (tolerans 0,05%)
python tests\parity_lens.py docs\data\baku_pvgis53_tmy.json # brauzer ↔ Python: linza (tolerans 0,1 faiz bəndi)
```

## Linza modelinin etibarlılığı

Linza laboratoriyası nazik paraksial linza modelindən istifadə edir. Etibarlılıq `solarsim/optics.py` və `simulator/lensoptics.js` faylındakı `validity` funksiyası ilə hesablanır:

* f-ədədi N = |f| / a, burada a fokuslayan aperturadır.
* Kənar şüanın optik oxla bucağı θ = atan((a/2) / |f|). Dəyərlər tam dəqiqliklə saxlanılır, yalnız ekranda yuvarlaqlaşdırılır.
* Hesab oxu: sferik linzada aperturası böyük olan ox, silindrik linzada yalnız maililik oxu y. Düzbucaqlı sferik linzanın künc şüasının bucağı atan((diaqonal/2) / |f|) ayrıca hesablanır və ayrıca göstərilir.
* Kənar şüa bucağı ≤ 10° olduqda etibarlılıq yüksək, ≤ 20° orta, daha böyük olduqda aşağıdır.
* 30° simulyatorun paraksial model üçün **xəbərdarlıq meyarıdır**. Bu, linzanın düzəldilə bilib-bilməməsi haqqında hökm deyil.
* Aşağı etibarlılıqda fokus və enerji nəticəsinin yanında “kobud yaxınlaşdırma” yazılır.
* Axtarışın maksimumu aşağı etibarlılıq zonasına düşərsə, ayrıca göstərilir və prototip seçimi kimi təqdim olunmur. Onun yanında etibarlı zonada (θ ≤ 20°) tapılan ən yaxşı nəticə verilir.

Misal: 176 sm apertura və 20 sm fokus üçün f/0,11 və 77,2° alınır (`tests/test_optics.py`).

Saxlanmış məlumat dəstlərindəki etibarlılıq sahələrini enerjini yenidən hesablamadan yeniləmək üçün:

```powershell
python -m solarsim.build --refresh-validity
```

## Vaxt və məlumat qaydaları

* Hesab UTC-də aparılır. Qrafiklər və aylar məkanın yerli **standart** vaxtı ilə verilir (TMY nominal ildir, yay saatı tətbiq olunmur).
* Günəş mövqeyi pvlib SPA ilə `vaxt nişanı + ofset` anında hesablanır. Ofset bir dəfə tətbiq olunur:
  PVGIS 5.3 TMY-də cavabın `irradiance_time_offset` sahəsindən gəlir (Bakı 0,1672 saat). Saatlıq sırada dəqiqələr vaxt nişanının içindədir, əlavə ofset yoxdur.
  PVGIS 6 TMY ofset vermir: ofset açıq səma vaxtlamasından qiymətləndirilir və metadatada belə qeyd olunur.
* Enerji `Σ(P × Δt)` ilə hesablanır, Δt məlumatın addımıdır. Çatışmayan sətirlər doldurulmur, sayı göstərilir.
* PVGIS 6 TMY təmizləmə qaydası (gecə dəyərləri, boş qiymətlər, DHI-nin hesablanması) dəstin metadatasında yazılır.

## Lisenziya

Kod [MIT](LICENSE) lisenziyası ilə açıqdır. PVGIS məlumatı Avropa Komissiyasının təkrar istifadə qaydası (CC BY 4.0) ilə işlədilir.
Trina texniki pasportu müəllif hüququna görə depoya daxil edilməyib, linki [`sources/README.md`](sources/README.md) faylındadır.
