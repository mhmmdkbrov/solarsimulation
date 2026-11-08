# Model v2.0.0: yekun hesabat

Bu fayl `python -m solarsim.report` ilə yaradılıb. Rəqəmlər `docs/data/*.json`, `tests/baseline_v1.json` və testlərin faktiki icrasından gəlir.

## 1. Tapılan problemlər, düzəlişlər və dəyişən fayllar

| Problem (v1) | Düzəliş (v2) | Fayllar |
|---|---|---|
| Yalnız Bakı; PVGIS 5.3 keşi notebook-a bağlı | Məkan seçimləri (Bakı, Naxçıvan, Almería) və istənilən koordinat; PVGIS 5.3 TMY + 2005–2023 sırası + PVGIS 6 TMY ayrıca dəst kimi; tam sorğu metadatası | `solarsim/sites.py`, `pvgis.py`, `weather.py`, `fetch_all.py`, `cli.py`, `data/raw/` |
| Laboratoriyada sabit `0.1672 h` ofset və sadələşdirilmiş Günəş vektoru | Ofset mənbənin metadatasından bir dəfə tətbiq olunur; bütün səhifələr pvlib SPA vektorlarını məlumat dəstindən oxuyur | `weather.py`, `geometry.py`, `build.py`, `lensoptics.js` |
| Brüt və xalis enerji, sərfin bölgüsü qarışıq göstərilirdi | Hər ssenari üçün brüt DC, izləmə, idarəetmə, soyutma, xalis; kWh/qurğu, kWh/m² apertura, kWh/m² torpaq ayrıca | `scenarios.py`, `model.js`, `template.html` |
| Enerji yalnız saatlıq addımla hesablanırdı; çatışmayan sətirlər yoxlanmırdı | Σ(P·Δt), addım məlumatdan; çatışmayan sətirlər sayılır; yarım saat, sıçrayış ili, çatışmayan sətir testləri | `weather.py`, `tests/test_core.py` |
| Aktiv sahə payı iki modeldə fərqli (0,92 və 0,9195) | 0,92 giriş parametri; hüceyrə hündürlüyü ondan hesablanır | `pv.py`, `optics.py`, `lensoptics.js` |
| Linza massivində sonsuz periodik hüceyrə; paneldən kənara çıxan işıq yox idi | Sonlu panel: öz hüceyrə, qonşu, boşluq, kənar; modul şüşəsində sınma; birbaşa, səma və yer işığı ayrıca; işıq balansı testi | `optics.py`, `lenslab.py`, `lensoptics.js` |
| “Ən yaxşı məsafə” bəzi sınaq nöqtələrindən pis idi (−3 D, −10 D) | Axtarışa sınaq nöqtələri daxildir; bütün namizədlər eyni funksiya ilə; test: maksimum ≥ hər sınaq nöqtəsi | `lenslab.py`, `tests/test_optics.py` |
| Nazik linzanın etibarlılıq sərhədi göstərilmirdi | f-ədədi N = |f| / a və kənar şüanın optik oxla bucağı atan((a/2) / |f|) hesab oxu göstərilməklə, künc şüası ayrıca; ≤ 10° / ≤ 20° / daha böyük → yüksək / orta / aşağı, 30° simulyatorun paraksial model üçün xəbərdarlıq meyarıdır (istehsal hökmü deyil); aşağı etibarlılıqda “kobud yaxınlaşdırma” yarlığı; Snell/Fresnel 2D şüa izləməsi ilə yoxlama | `optics.py` (`validity`, `trace2d`) |
| Böyük linzada yalnız “ən zəif hüceyrə” qaydası | Hüceyrə → sıra → bypass qrupu → modul I–V modeli (De Soto, pasportdan); T1/T3 topologiya həssaslığı; bərabər, kölgəli hüceyrə və qrup testləri | `electrical.py`, `tests/test_optics.py` |
| CPV-də qəbul bucağı və izləmə xətası yox idi; istilik həllində xəbərdarlıq yox idi | Qəbul bucağı + Rayleigh izləmə xətası, konusdakı səpələnmiş işıq, η(T, C) etibarlılıq diapazonu, xəbərdarlıqlar və xəritədə ştrix | `scenarios.py`, `model.js` |
| C = 5-də soyutma sərfi və ekstrapolyasiya statusu göstərilmirdi | Eyni apertura ilə müqayisə; “soyutma sərfi daxil edilməyib”; 170 °C və 1043 saat model proqnozu kimi; 29,4% həddinin şərtləri | `studies.py`, `lab_template.html` |
| Səhifələrdə əl ilə yazılmış rəqəmlər və “mükəmməl linza” ifadəsi | Bütün rəqəmlər məlumat dəstindən; “sadə modelin ideal ssenarisi” şərtləri ilə; hava sinifləri GHI > 10 W/m² + qalan saatlar; versiya və dəst adı hər səhifədə | `lens_template.html`, `lab_template.html`, `template.html`, `datastore.js` |
| v1 nəticələri üçün reqressiya bazası yox idi | `tests/baseline_v1.json`; v2 v1 rejimində eyni nəticəni verir; v1 skriptləri `legacy/v1/` | `tests/make_baseline_v1.js`, `legacy/v1/` |

## 2. Ssenarilər üzrə əvvəlki və yeni nəticələr (Bakı, PVGIS 5.3 TMY)

| Ssenari | v1 brüt | v2 brüt | v1 xalis | v2 xalis | köməkçi sərf v2, kWh/qurğu (izləmə + idarəetmə + soyutma) | fərqin səbəbi |
|---|---|---|---|---|---|---|
| A — sabit adi panel | 355,4006 | 355,4006 | 355,4006 | 355,4006 | 0,000 = 0,000 + 0,000 + 0,000 | dəyişməyib (v2 kodu v1 rejimində 0,0001 dəqiqliklə eynidir) |
| B — sabit panel + orta optik qat | 310,7364 | 310,7364 | 310,7364 | 310,7364 | 0,000 = 0,000 + 0,000 + 0,000 | dəyişməyib (v2 kodu v1 rejimində 0,0001 dəqiqliklə eynidir) |
| A-izləmə — iki oxlu adi panel | 448,0135 | 448,0135 | 436,9210 | 436,9210 | 22,164 = 17,784 + 4,380 + 0,000 | dəyişməyib (v2 kodu v1 rejimində 0,0001 dəqiqliklə eynidir) |
| C — iki oxlu CPV | 314,7325 | 314,7801 | 303,6400 | 303,6876 | 22,164 = 17,784 + 4,380 + 0,000 | CPV qəbul konusundakı səpələnmiş işıq (DHI·sin²1°) əlavə olunub, izləmə xətası (σ = 0,1°) nəzərə alınıb |

Vahid: kWh/m² apertura/il (apertura = 1,998 m²). A-izləmənin 448,01 dəyəri brüt, 436,92 isə xalisdir.

**Linza laboratoriyası (Bakı, material 92%, il üzrə adi panelə nisbətən).** v1 sonsuz periodik hüceyrə modeli ilə müqayisədə v2 sonlu paneldən istifadə edir: kənar hüceyrələr, paneldən kənara çıxan işıq, modul şüşəsində sınma və işıq balansı nəzərə alınır. Elektrik modeli: sürətli qayda, mötərizədə hüceyrə I–V modeli (T1).

| Linza | Düzülüş | v1: 3 mm | v2: 3 mm | v1: ən yaxşı | v2: ən yaxşı h | v2: ən yaxşı nəticə | etibarlılıq |
|---|---|---|---|---|---|---|---|
| +3 D | array | −9,4% | −10,7% (−10,7%) | −9,2% | 4,0 mm | −10,6% (−10,4%) | orta |
| +3 D | array_cyl | — | −11,3% (−11,3%) | — | 3,0 mm | −11,3% (−11,3%) | yüksək |
| +3 D | big | −18,7% | −16,2% (−11,6%) | −16,8% | 2,6 mm | −14,7% (−11,2%) | aşağı |
| −3 D | array | −11,9% | −13,0% (−12,9%) | −10,3% | 2,6 mm | −12,8% (−12,7%) | orta |
| −3 D | array_cyl | — | −12,4% (−12,3%) | — | 2,6 mm | −12,3% (−12,3%) | yüksək |
| −3 D | big | −12,1% | −12,6% (−12,7%) | −11,8% | 2,6 mm | −12,4% (−12,4%) | aşağı |
| +10 D | array | −6,7% | −8,1% (−8,1%) | −6,0% | 5,0 mm | −7,5% (−7,3%) | aşağı |
| +10 D | array_cyl | — | −10,1% (−10,1%) | — | 4,0 mm | −10,0% (−9,9%) | aşağı |
| +10 D | big | −43,7% | −35,3% (−26,8%) | −37,7% | 2,6 mm | −30,6% (−22,3%) | aşağı |
| −10 D | array | −14,3% | −15,5% (−15,2%) | −10,4% | 2,6 mm | −14,9% (−14,8%) | aşağı |
| −10 D | array_cyl | — | −13,6% (−13,4%) | — | 2,6 mm | −13,3% (−13,3%) | aşağı |
| −10 D | big | −15,6% | −15,3% (−15,4%) | −14,7% | 2,6 mm | −14,6% (−14,7%) | aşağı |

+13,5 D / 8 mm (v1 nəticəsi saxlanılıb): v1 adi material −4,9%, başabaş ötürmə ≈ 96,8%. v2 sferik massiv: −6,5% / −2,4% / +1,6% (92 / 96 / 100%). v2 silindrik: −10,3% / −6,4% / −2,5%.

Etibarlı zonada ən yaxşı (array; yalnız paraksial etiketi “aşağı” olmayan dioptriyalar (kənar şüa bucağı ≤ 20°)): +3,5 D, h = 4,0 mm → −10,4% / −6,5% / −2,6%; başabaş ötürmə yoxdur; kənar şüanın optik oxla bucağı 18,3°, etibarlılıq orta.

Axtarışın ümumi maksimumu (array) aşağı etibarlılıq zonasındadır, **kobud yaxınlaşdırma**: +20 D (axtarış diapazonunun kənarı, ±20 D), h = 5,0 mm → −5,0% / −0,9% / +3,3%; başabaş ötürmə 96,8%; kənar şüanın optik oxla bucağı 62,1°, etibarlılıq aşağı. Təsdiqlənmiş prototip seçimi deyil.

Etibarlı zonada ən yaxşı (array_cyl; yalnız paraksial etiketi “aşağı” olmayan dioptriyalar (kənar şüa bucağı ≤ 20°)): +9,5 D, h = 4,0 mm → −10,1% / −6,2% / −2,3%; başabaş ötürmə yoxdur; kənar şüanın optik oxla bucağı 19,2°, etibarlılıq orta.

Axtarışın ümumi maksimumu (array_cyl) aşağı etibarlılıq zonasındadır, **kobud yaxınlaşdırma**: +20 D (axtarış diapazonunun kənarı, ±20 D), h = 4,0 mm → −8,6% / −4,6% / −0,7%; başabaş ötürmə yoxdur; kənar şüanın optik oxla bucağı 36,3°, etibarlılıq aşağı. Təsdiqlənmiş prototip seçimi deyil.

Sadə optik qat modelinin ideal ssenarisi: +7,84% (sadə modelin ideal ssenarisi: aktiv sahə 92 %, boşluq işığı tam qaytarılır, ötürmə 100 %, əlavə istilik və qeyri-bərabərlik itkisi sıfır).

**C = 5 sınağı (eyni ümumi apertura, Bakı).**

| Variant | brüt kWh/m² | xalis kWh/m² | qeyd |
|---|---|---|---|
| linza C = 5, aktiv soyutma | 247,5 | 238,2 | soyutma sərfi daxil edilməyib (ölçülməlidir) |
| linza C = 5, soyutmasız | 206,1 | 196,8 | model ekstrapolyasiyası: SAPM yüksək konsentrasiya üçün kalibrlənməyib; 1043 saat > 85 °C (model proqnozu) |
| 5 adi panel, sabit | 355,4 | 355,4 |  |
| 5 adi panel, 2 oxlu | 448,0 | 438,7 |  |

## 3. İcra olunmuş testlər

`pytest`: **63 passed in 172.78s (0:02:52)**

| Modul | Test | Nəticə |
|---|---|---|
| test_calculator | `test_original_reproduces_shared_results` | keçdi |
| test_calculator | `test_diopter_does_not_change_original_output` | keçdi |
| test_calculator | `test_energy_balance_closes` | keçdi |
| test_calculator | `test_same_area_comparisons` | keçdi |
| test_calculator | `test_focus_spot_and_local_concentration` | keçdi |
| test_calculator | `test_js_matches_python` | keçdi |
| test_cli | `test_cli_csv_dataset` | keçdi |
| test_core | `test_stc_450W_and_efficiency` | keçdi |
| test_core | `test_zero_irradiance_gives_zero_power` | keçdi |
| test_core | `test_noct_check_and_calibration` | keçdi |
| test_core | `test_active_fraction_consistent` | keçdi |
| test_core | `test_half_hour_step_matches_hourly_energy` | keçdi |
| test_core | `test_leap_year_rows_and_energy` | keçdi |
| test_core | `test_missing_rows_are_reported_not_filled` | keçdi |
| test_core | `test_energy_integration_formula` | keçdi |
| test_core | `test_regression_v1_exact` | keçdi |
| test_core | `test_v2_default_differs_only_by_documented_cpv_changes` | keçdi |
| test_core | `test_gross_minus_aux_equals_net` | keçdi |
| test_core | `test_months_sum_to_annual` | keçdi |
| test_core | `test_sky_classes_plus_remainder_sum_to_annual` | keçdi |
| test_core | `test_optics_off_B_equals_A` | keçdi |
| test_core | `test_same_aperture_for_all_scenarios` | keçdi |
| test_core | `test_cpv_power_chain` | keçdi |
| test_core | `test_cpv_zero_dni_zero_power` | keçdi |
| test_core | `test_control_sample_225_and_204` | keçdi |
| test_core | `test_second_site_changes_sun_and_irradiance` | keçdi |
| test_core | `test_series_offset_applied_once` | keçdi |
| test_optics | `test_focal_length_units[3-333.333]` | keçdi |
| test_optics | `test_focal_length_units[10-100.0]` | keçdi |
| test_optics | `test_focal_length_units[-3--333.333]` | keçdi |
| test_optics | `test_focal_length_units[-10--100.0]` | keçdi |
| test_optics | `test_focal_length_units[13.5-74.074]` | keçdi |
| test_optics | `test_flat_sheet_mode` | keçdi |
| test_optics | `test_negative_lens_virtual_focus_spreads` | keçdi |
| test_optics | `test_13p5D_8mm_cell_plane_before_focus` | keçdi |
| test_optics | `test_light_balance_closes[cfg0]` | keçdi |
| test_optics | `test_light_balance_closes[cfg1]` | keçdi |
| test_optics | `test_light_balance_closes[cfg2]` | keçdi |
| test_optics | `test_light_balance_closes[cfg3]` | keçdi |
| test_optics | `test_light_balance_closes[cfg4]` | keçdi |
| test_optics | `test_light_balance_closes[cfg5]` | keçdi |
| test_optics | `test_null_lens_equals_bare_module` | keçdi |
| test_optics | `test_edge_ray_leaves_the_module` | keçdi |
| test_optics | `test_large_incidence_reduces_lens_transmission` | keçdi |
| test_optics | `test_iv_uniform_matches_datasheet` | keçdi |
| test_optics | `test_iv_uniform_mismatch_is_one` | keçdi |
| test_optics | `test_iv_one_shaded_cell_bypasses_one_group` | keçdi |
| test_optics | `test_iv_one_group_shaded` | keçdi |
| test_optics | `test_topology_sensitivity_half_shade` | keçdi |
| test_optics | `test_fast_rule_matches_iv_for_uniform_and_close_for_shading` | keçdi |
| test_optics | `test_best_distance_beats_every_test_point` | keçdi |
| test_optics | `test_trace2d_agrees_with_paraxial_for_weak_lens[3-3-0.0]` | keçdi |
| test_optics | `test_trace2d_agrees_with_paraxial_for_weak_lens[3-3-20.0]` | keçdi |
| test_optics | `test_trace2d_agrees_with_paraxial_for_weak_lens[3-20-0.0]` | keçdi |
| test_optics | `test_trace2d_agrees_with_paraxial_for_weak_lens[5-30-10.0]` | keçdi |
| test_optics | `test_trace2d_reports_profile_that_does_not_fit` | keçdi |
| test_optics | `test_validity_176cm_aperture_20cm_focus` | keçdi |
| test_optics | `test_validity_axis_and_cylinder` | keçdi |
| test_optics | `test_paraxial_label_limits[10.00deg]` | keçdi |
| test_optics | `test_paraxial_label_limits[10.01deg]` | keçdi |
| test_optics | `test_paraxial_label_limits[20.00deg]` | keçdi |
| test_optics | `test_paraxial_label_limits[20.01deg]` | keçdi |
| test_optics | `test_validity_js_matches_python` | keçdi |

Brauzer ↔ Python, ssenarilər (bütün TMY dəstləri, tolerans 0,05%): **PARITY OK**

Brauzer ↔ Python, linza (Bakı, tolerans 0,1 faiz bəndi):

```
OK   P= +3.0 h=   3.0 big      : py  -16.159%  js  -16.159%  |Î”| 0.0000 pp  max balance diff 0.0000 %
OK   P=+10.0 h= 100.0 big      : py  -99.956%  js  -99.956%  |Î”| 0.0000 pp  max balance diff 0.0000 %
OK   P= -3.0 h=   3.0 array    : py  -12.997%  js  -12.997%  |Î”| 0.0000 pp  max balance diff 0.0000 %
OK   P=-10.0 h= 100.0 array    : py  -58.678%  js  -58.678%  |Î”| 0.0000 pp  max balance diff 0.0000 %
OK   P=+13.5 h=   8.0 array    : py   -6.486%  js   -6.486%  |Î”| 0.0000 pp  max balance diff 0.0000 %
OK   P=+13.5 h=   8.0 array_cyl: py  -10.257%  js  -10.257%  |Î”| 0.0000 pp  max balance diff 0.0000 %
OK   P= +0.0 h=   3.0 array    : py  -11.861%  js  -11.861%  |Î”| 0.0000 pp  max balance diff 0.0000 %
OK   P= +5.0 h=  30.0 array    : py  -17.774%  js  -17.774%  |Î”| 0.0000 pp  max balance diff 0.0000 %
LENS PARITY OK
```

## 4. Aktual PVGIS məlumatı ilə yenidən hesablanan məkanlar

| Dəst | API | Radiasiya bazası | İllər | Sorğu (UTC) | Ofset, saat | A xalis | B xalis | A-izləmə xalis | C xalis |
|---|---|---|---|---|---|---|---|---|---|
| baku_pvgis53_tmy | PVGIS 5.3 | PVGIS-SARAH3 | 2005–2023 | 2026-11-08T15:18 | 0,1672 | 355,4 | 310,7 | 436,9 | 303,7 |
| baku_pvgis6_tmy | PVGIS 6 | SARAH-3 / ERA5 (PVGIS 6 əhatə  | 2015–2024 | 2026-11-08T15:18 | 0,1663 | 360,5 | 315,4 | 446,6 | 314,1 |
| naxcivan_pvgis53_tmy | PVGIS 5.3 | PVGIS-SARAH3 | 2005–2023 | 2026-11-08T15:18 | 0,1661 | 416,9 | 366,5 | 523,3 | 407,6 |
| naxcivan_pvgis6_tmy | PVGIS 6 | SARAH-3 / ERA5 (PVGIS 6 əhatə  | 2014–2024 | 2026-11-08T15:19 | 0,1663 | 418,3 | 368,1 | 531,8 | 417,2 |
| almeria_pvgis53_tmy | PVGIS 5.3 | PVGIS-SARAH3 | 2005–2023 | 2026-11-08T15:19 | 0,1657 | 464,8 | 410,3 | 626,6 | 521,9 |
| almeria_pvgis6_tmy | PVGIS 6 | SARAH-3 / ERA5 (PVGIS 6 əhatə  | 2014–2024 | 2026-11-08T15:19 | 0,1663 | 459,4 | 405,1 | 621,9 | 514,7 |

baku_pvgis53_tmy — illərarası (2005–2023), A xalis: orta 357,4 ± 8,9 kWh/m², min 342,0, maks 373,2.

baku_pvgis6_tmy təmizləmə: Boş (NaN) qiymətlər (GHI 13, DNI 12, temperatur 0, külək 0) xətti interpolyasiya ilə dolduruldu (≤ 3 saat); 0 qiymət 0 götürüldü; Günəş üfüqün altında olduğu halda GHI/DNI > 0 olan 73 gecə sətri 0 götürüldü (TMY ayları birləşən yerlərdə xətti keçidlər); DHI = GHI − DNI·cos(z) kimi hesablandı (API vermir); DNI·cos(z) GHI-dən böyük olan 2 sətirdə DNI azaldıldı

naxcivan_pvgis53_tmy — illərarası (2005–2023), A xalis: orta 411,3 ± 11,1 kWh/m², min 393,3, maks 431,3.

naxcivan_pvgis6_tmy təmizləmə: Boş (NaN) qiymətlər (GHI 17, DNI 11, temperatur 0, külək 0) xətti interpolyasiya ilə dolduruldu (≤ 3 saat); 0 qiymət 0 götürüldü; Günəş üfüqün altında olduğu halda GHI/DNI > 0 olan 81 gecə sətri 0 götürüldü (TMY ayları birləşən yerlərdə xətti keçidlər); DHI = GHI − DNI·cos(z) kimi hesablandı (API vermir); DNI·cos(z) GHI-dən böyük olan 3 sətirdə DNI azaldıldı

almeria_pvgis53_tmy — illərarası (2005–2023), A xalis: orta 459,6 ± 9,6 kWh/m², min 444,1, maks 474,3.

almeria_pvgis6_tmy təmizləmə: Boş (NaN) qiymətlər (GHI 25, DNI 13, temperatur 0, külək 0) xətti interpolyasiya ilə dolduruldu (≤ 3 saat); 0 qiymət 0 götürüldü; Günəş üfüqün altında olduğu halda GHI/DNI > 0 olan 123 gecə sətri 0 götürüldü (TMY ayları birləşən yerlərdə xətti keçidlər); DHI = GHI − DNI·cos(z) kimi hesablandı (API vermir); DNI·cos(z) GHI-dən böyük olan 22 sətirdə DNI azaldıldı

Vahid: kWh/m² apertura/il. PVGIS 6 API sənədlərə görə “aktiv inkişaf mərhələsindədir”. TMY cavabında DHI yoxdur, ay birləşmələrində isə gecə dəyərləri var. Təmizləmə qaydası yuxarıda verilib.

## 5. Hələ fərziyyə olan parametrlər və prototip planı

| Qrup | Parametr | Dəyər | Vahid | Qeyd |
|---|---|---|---|---|
| modul | `glass_n` | 1,5260 | - | AR örtüyü ayrıca modelləşdirilmir |
| modul | `glass_K` | 4,0000 | 1/m |  |
| modul | `glass_L` | 0,0020 | m |  |
| modul | `active_fraction` | 0,9200 | - | modul səthinin hüceyrələrlə örtülü payı; ölçülməlidir |
| modul | `cell_w_mm` | 182,0000 | mm | üçə kəsilmiş 210R tipli hüceyrə; pasportda yoxdur |
| modul | `layout` | 6 sütun × 24 sıra (portret) | - | 1762 × 1134 mm və 144 hüceyrə ilə uyğundur |
| system | `albedo` | məkan seçimindən | - | məkan seçimindən (0,20) |
| system | `tilt_deg` | məkan seçimindən | ° | məkan seçimindən |
| system | `azimuth_deg` | məkan seçimindən | ° | məkan seçimindən (180 = cənub) |
| system | `spectral` | 1,0000 | - |  |
| system | `soiling` | 0,0000 | - |  |
| system | `ground_coverage_ratio_fixed` | 0,4000 | - | yalnız torpaq sahəsi göstəriciləri üçün sıra məsafəsi |
| system | `ground_coverage_ratio_2axis` | 0,2500 | - | 2 oxlu izləyicilər daha geniş məsafə tələb edir |
| retrofit | `optics_enabled` | True | - |  |
| retrofit | `coupling` | air_gap | - | air_gap: qatın IAM-ı × modul şüşəsinin IAM-ı; bonded: qat modulun ön səthini əvəz edir |
| retrofit | `tau_beam_normal` | 0,9200 | - |  |
| retrofit | `tau_diffuse` | 0,8400 | - |  |
| retrofit | `K_layer` | 4,0000 | 1/m |  |
| retrofit | `L_layer` | 0,0030 | m |  |
| retrofit | `gap_recovery_beam` | 0,3000 | - |  |
| retrofit | `gap_recovery_diffuse` | 0,1000 | - |  |
| retrofit | `nonuniformity_loss` | 0,0200 | - |  |
| retrofit | `extra_heating_K_per_kWm2` | 2,0000 | K/(kW/m²) |  |
| retrofit | `aux_W` | 0,0000 | W |  |
| cpv | `aperture_unit_m2` | 0,0100 | m² | 10 × 10 sm linza |
| cpv | `cell_area_m2` | 0,0001 | m² | 1 × 1 sm fotoelement |
| cpv | `tau_optical` | 0,8500 | - |  |
| cpv | `intercept_optical` | 0,9500 | - | ideal izləmədə fokuslanan işığın fotoelementə düşən payı |
| cpv | `acceptance_half_angle_deg` | 1,0000 | ° | optikanın qəbul bucağı (90% nöqtəsi) |
| cpv | `tracking_error_sigma_deg` | 0,1000 | ° | hər ox üzrə 1σ yönəltmə xətası |
| cpv | `diffuse_in_acceptance` | True | - | qəbul konusunun içindəki izotrop səma işığı: DHI·sin²θa (v1-də 0) |
| cpv | `eta_cell_ref` | 0,3000 | - | 25 °C-də; kommersiya məhsulu deyil |
| cpv | `gamma_cell` | −0,0015 | 1/°C |  |
| cpv | `eta_valid_T_C` | [-20.0, 110.0] | °C | η(T) modelinin etibarlı temperatur diapazonu |
| cpv | `eta_valid_suns` | [1.0, 1000.0] | suns | η_ref-in etibarlı konsentrasiya diapazonu |
| cpv | `r_th_K_per_W` | 4,0000 | K/W | hər linza üçün hüceyrə → ətraf, passiv radiator |
| cpv | `fan_W` | 0,0000 | W | aktiv soyutma, gündüz |
| tracker | `drive_W` | 4,0000 | W | gündüz |
| tracker | `controller_W` | 0,5000 | W | 24 saat |

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

