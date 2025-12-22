# Bundestagswahlen Column Mapping Strategy

## Executive Summary

After analyzing the election CSV files (2017, 2021, 2025), the recommended approach is:

**Use BTW2021/2025 unified schema** (52 columns after date normalization) as the base schema. BTW2017 can be included with **86.5% column mapping** (45 out of 52 columns). Only 7 columns will be NULL for BTW2017 data.

**Note on BTW2013**: BTW2013 data structure is too different (only 13/52 columns match, 25% overlap) and is **not recommended** for inclusion in the unified schema. If needed, BTW2013 should be stored in a separate table.

## Column Structure Analysis

### BTW2021 vs BTW2025

**Status**: ✅ **IDENTICAL after removing date references**

- **Raw columns**: 52 each, but 16 columns differ
- **Difference**: Only date references in column names:
  - Unemployment: `arbeitslosenquote_februar_*` (2021) vs `arbeitslosenquote_november_*` (2025)
  - SGB II: `empf_nger_innen_von_leistungen_nach_sgb_ii_oktober_*` (2021) vs `empf_nger_innen_von_leistungen_nach_sgb_ii_august_*` (2025)
- **After normalization**: All 52 columns map to the same unified names

**Conclusion**: BTW2021 and BTW2025 can use the **same table schema** with unified column names.

### BTW2017 Compatibility

**Status**: ✅ **HIGHLY COMPATIBLE** (86.5% mappable)

- **Total columns**: 52 (same count as 2021/2025)
- **Exact matches**: 20 columns (38%)
- **Semantic matches**: 25 columns (48%)
- **Not mappable**: 7 columns (13.5%)
- **Total mappable**: 45 columns (86.5%)

**Key Differences**:
1. **Column naming**: 2017 uses different terminology (e.g., `bev_lkerung_ausl_nder` vs `bev_lkerung_ausl_nder_innen`, `Einwohner` vs `EW`)
2. **Missing categories in 2017**: 
   - Land use (`bodenfl_che_*`) - 2 columns
   - Housing area metrics (`wohnfl_che_*`) - 2 columns
   - Electric/hybrid vehicles (`pkw_elektro_hybrid_pct`) - 1 column
   - Childcare by age groups (different structure) - 2 columns
3. **Different structure**: Education columns use "Absolventen/Abgänger" vs "Schulabgänger/-innen"
4. **Unemployment data**: 2017 uses March 2017 (`arbeitslosenquote_m_rz_*`), 2021/2025 use different months
5. **Zensus 2011 data**: 2017 includes Zensus 2011 migration and religion data (not in 2021/2025, but these are not in the unified schema)

## Recommended Solution

### Unified Schema with BTW2017 Mapping (Recommended)

**Pros**:
- Single table for all three elections (2017, 2021, 2025)
- 86.5% of columns have data for all elections
- Only 7 columns will be NULL for BTW2017 (13.5%)
- BTW2021 and BTW2025 are identical (no NULLs)
- Queries can filter by `election_year` to avoid NULL issues

**Cons**:
- BTW2017 will have NULLs for 7 columns
- Requires column mapping logic during data loading

**Implementation**:
- Use BTW2021/2025 schema (52 columns)
- BTW2017 data: Map 45 compatible columns, set 7 to NULL
- Add `election_year` column to distinguish

## Complete Column Mapping Table

The following table shows all 52 unified columns and their mapping to BTW2017, BTW2021, and BTW2025:

| Unified Column | BTW2017 Original | BTW2021 Original | BTW2025 Original | Match Type |
|----------------|-----------------|-----------------|------------------|------------|
| `land` | Land | Land | Land | exact |
| `wahlkreis_nr` | Wahlkreis-Nr. | Wahlkreis-Nr. | Wahlkreis-Nr. | exact |
| `wahlkreis_name` | Wahlkreis-Name | Wahlkreis-Name | Wahlkreis-Name | exact |
| `gemeinden_anzahl` | Gemeinden am 31.12.2015 (Anzahl) | Gemeinden am 31.12.2019 (Anzahl) | Gemeinden am 31.12.2023 (Anzahl) | exact |
| `fl_che_km` | Fläche am 31.12.2015 (km²) | Fläche am 31.12.2019 (km²) | Fläche am 31.12.2023 (km²) | exact |
| `bev_lkerung_insgesamt_in` | Bevölkerung am 31.12.2015 - Insgesamt (in 1000) | Bevölkerung am 31.12.2019 - Insgesamt (in 1000) | Bevölkerung am 31.12.2023 - Insgesamt (in 1000) | exact |
| `bev_lkerung_deutsche_in` | Bevölkerung am 31.12.2015 - Deutsche (in 1000) | Bevölkerung am 31.12.2019 - Deutsche (in 1000) | Bevölkerung am 31.12.2023 - Deutsche (in 1000) | exact |
| `bev_lkerung_ausl_nder_innen` | Bevölkerung am 31.12.2015 - Ausländer (%) | Bevölkerung am 31.12.2019 - Ausländer/-innen (%) | Bevölkerung am 31.12.2023 - Ausländer/-innen (%) | semantic |
| `bev_lkerungsdichte_ew_je_km` | Bevölkerungsdichte am 31.12.2015 (Einwohner je km²) | Bevölkerungsdichte am 31.12.2019 (EW je km²) | Bevölkerungsdichte am 31.12.2023 (EW je km²) | semantic |
| `zu_bzw_abnahme_der_bev_lkerung_geburtensaldo_je_ew` | Zu- (+) bzw. Abnahme (-) der Bevölkerung 2015 - Geburtensaldo (je 1000 Einwohner) | Zu- (+) bzw. Abnahme (-) der Bevölkerung 2019 - Geburtensaldo (je 1000 EW) | Zu- (+) bzw. Abnahme (-) der Bevölkerung 2023 - Geburtensaldo (je 1000 EW) | semantic |
| `zu_bzw_abnahme_der_bev_lkerung_wanderungssaldo_je_ew` | Zu- (+) bzw. Abnahme (-) der Bevölkerung 2015 - Wanderungssaldo (je 1000 Einwohner) | Zu- (+) bzw. Abnahme (-) der Bevölkerung 2019 - Wanderungssaldo (je 1000 EW) | Zu- (+) bzw. Abnahme (-) der Bevölkerung 2022 - Wanderungssaldo (je 1000 EW) | semantic |
| `alter_von_bis_jahren_unter_18` | Alter von ... bis ... Jahren am 31.12.2015 - unter 18 (%) | Alter von ... bis ... Jahren am 31.12.2019 - unter 18 (%) | Alter von ... bis ... Jahren am 31.12.2023 - unter 18 (%) | exact |
| `alter_von_bis_jahren_18_24` | Alter von ... bis ... Jahren am 31.12.2015 - 18-24 (%) | Alter von ... bis ... Jahren am 31.12.2019 - 18-24 (%) | Alter von ... bis ... Jahren am 31.12.2023 - 18-24 (%) | exact |
| `alter_von_bis_jahren_25_34` | Alter von ... bis ... Jahren am 31.12.2015 - 25-34 (%) | Alter von ... bis ... Jahren am 31.12.2019 - 25-34 (%) | Alter von ... bis ... Jahren am 31.12.2023 - 25-34 (%) | exact |
| `alter_von_bis_jahren_35_59` | Alter von ... bis ... Jahren am 31.12.2015 - 35-59 (%) | Alter von ... bis ... Jahren am 31.12.2019 - 35-59 (%) | Alter von ... bis ... Jahren am 31.12.2023 - 35-59 (%) | exact |
| `alter_von_bis_jahren_60_74` | Alter von ... bis ... Jahren am 31.12.2015 - 60-74 (%) | Alter von ... bis ... Jahren am 31.12.2019 - 60-74 (%) | Alter von ... bis ... Jahren am 31.12.2023 - 60-74 (%) | exact |
| `alter_von_bis_jahren_75_und_mehr` | Alter von ... bis ... Jahren am 31.12.2015 - 75 und mehr (%) | Alter von ... bis ... Jahren am 31.12.2019 - 75 und mehr (%) | Alter von ... bis ... Jahren am 31.12.2023 - 75 und mehr (%) | exact |
| `bodenfl_che_nach_art_der_tats_chlichen_nutzung_siedlung_und_verkehr` | NULL | Bodenfläche nach Art der tatsächlichen Nutzung am 31.12.2019 - Siedlung und Verkehr (%) | Bodenfläche nach Art der tatsächlichen Nutzung am 31.12.2023 - Siedlung und Verkehr (%) | not_in_2017 |
| `bodenfl_che_nach_art_der_tats_chlichen_nutzung_vegetation_und_gew_sser` | NULL | Bodenfläche nach Art der tatsächlichen Nutzung am 31.12.2019 - Vegetation und Gewässer (%) | Bodenfläche nach Art der tatsächlichen Nutzung am 31.12.2023 - Vegetation und Gewässer (%) | not_in_2017 |
| `fertiggestellte_wohnungen_je_ew` | Bautätigkeit und Wohnungswesen - Fertiggestellte Wohnungen 2014 (je 1000 Einwohner) | Fertiggestellte Wohnungen 2019 (je 1000 EW) | Fertiggestellte Wohnungen 2023 (je 1000 EW) | semantic |
| `bestand_an_wohnungen_insgesamt_je_ew` | Bautätigkeit und Wohnungswesen - Bestand an Wohnungen am 31.12.2015 (je 1000 Einwohner) | Bestand an Wohnungen am 31.12.2019 - insgesamt (je 1000 EW) | Bestand an Wohnungen am 31.12.2023 - insgesamt (je 1000 EW) | semantic |
| `wohnfl_che_je_wohnung` | NULL | Wohnfläche am 31.12.2019 (je Wohnung) | Wohnfläche am 31.12.2023 (je Wohnung) | not_in_2017 |
| `wohnfl_che_je_ew` | NULL | Wohnfläche am 31.12.2019 (je EW) | Wohnfläche am 31.12.2023 (je EW) | not_in_2017 |
| `pkw_bestand_pkw_insgesamt_je_ew` | Kraftfahrzeugbestand am 01.01.2016 (je 1000 Einwohner) | PKW-Bestand am 01.01.2020 - PKW insgesamt (je 1000 EW) | PKW-Bestand am 01.01.2024 - PKW insgesamt (je 1000 EW) | semantic |
| `pkw_bestand_pkw_mit_elektro_oder_hybrid_antrieb` | NULL | PKW-Bestand am 01.01.2020 - PKW mit Elektro- oder Hybrid-Antrieb (%) | PKW-Bestand am 01.01.2024 - PKW mit Elektro- oder Hybrid-Antrieb (%) | not_in_2017 |
| `unternehmensregister_unternehmen_insgesamt_je_ew` | Unternehmensregister 2014 - Unternehmen insgesamt (je 1000 Einwohner) | Unternehmensregister 2018 - Unternehmen insgesamt (je 1000 EW) | Unternehmensregister 2022 - Unternehmen insgesamt (je 1000 EW) | semantic |
| `unternehmensregister_handwerksunternehmen_je_ew` | Unternehmensregister 2014 - Handwerksunternehmen (je 1000 Einwohner) | Unternehmensregister 2018 - Handwerksunternehmen (je 1000 EW) | Unternehmensregister 2022 - Handwerksunternehmen (je 1000 EW) | semantic |
| `verf_gbares_einkommen_der_privaten_haushalte_eur_je_ew` | Verfügbares Einkommen der privaten Haushalte 2014 (€ je Einwohner) | Verfügbares Einkommen der privaten Haushalte 2018 (EUR je EW) | Verfügbares Einkommen der privaten Haushalte 2021 (EUR je EW) | semantic |
| `bruttoinlandsprodukt_eur_je_ew` | Bruttoinlandsprodukt 2014 (€ je Einwohner) | Bruttoinlandsprodukt 2018 (EUR je EW) | Bruttoinlandsprodukt 2021 (EUR je EW) | semantic |
| `schulabg_nger_innen_beruflicher_schulen` | Absolventen/Abgänger beruflicher Schulen 2015 | Schulabgänger/-innen beruflicher Schulen 2019 | Schulabgänger/-innen beruflicher Schulen 2022 | semantic |
| `schulabg_nger_innen_allgemeinbildender_schulen_insgesamt_ohne_externe_je_ew` | Absolventen/Abgänger allgemeinbildender Schulen 2015 - insgesamt ohne Externe (je 1000 Einwohner) | Schulabgänger/-innen allgemeinbildender Schulen 2019 - insgesamt ohne Externe (je 1000 EW) | Schulabgänger/-innen allgemeinbildender Schulen 2022 - insgesamt ohne Externe (je 1000 EW) | semantic |
| `schulabg_nger_innen_allgemeinbildender_schulen_ohne_hauptschulabschluss` | Absolventen/Abgänger allgemeinbildender Schulen 2015 - ohne Hauptschulabschluss (%) | Schulabgänger/-innen allgemeinbildender Schulen 2019 - ohne Hauptschulabschluss (%) | Schulabgänger/-innen allgemeinbildender Schulen 2022 - ohne Hauptschulabschluss (%) | semantic |
| `schulabg_nger_innen_allgemeinbildender_schulen_mit_hauptschulabschluss` | Absolventen/Abgänger allgemeinbildender Schulen 2015 - mit Hauptschulabschluss (%) | Schulabgänger/-innen allgemeinbildender Schulen 2019 - mit Hauptschulabschluss (%) | Schulabgänger/-innen allgemeinbildender Schulen 2022 - mit Hauptschulabschluss (%) | semantic |
| `schulabg_nger_innen_allgemeinbildender_schulen_mit_mittlerem_schulabschluss` | Absolventen/Abgänger allgemeinbildender Schulen 2015 - mit mittlerem Schulabschluss (%) | Schulabgänger/-innen allgemeinbildender Schulen 2019 - mit mittlerem Schulabschluss (%) | Schulabgänger/-innen allgemeinbildender Schulen 2022 - mit mittlerem Schulabschluss (%) | semantic |
| `schulabg_nger_innen_allgemeinblldender_schulen_mit_allgemeiner_und_fachhochschulreife` | Absolventen/Abgänger allgemeinbildender Schulen 2015 - mit allgemeiner und Fachhochschulreife (%) | Schulabgänger/-innen allgemeinblldender Schulen 2019 - mit allgemeiner und Fachhochschulreife (%) | Schulabgänger/-innen allgemeinblldender Schulen 2022 - mit allgemeiner und Fachhochschulreife (%) | semantic |
| `kindertagesbetreuung_betreute_kinder_unter_3_jahre_betreuungsquote` | NULL | Kindertagesbetreuung am 01.03.2020 - Betreute Kinder unter 3 Jahre - Betreuungsquote (%) | Kindertagesbetreuung am 01.03.2023 - Betreute Kinder unter 3 Jahre - Betreuungsquote (%) | not_in_2017 |
| `kindertagesbetreuung_betreute_kinder_3_bis_unter_6_jahre_betreuungsquote` | NULL | Kindertagesbetreuung am 01.03.2020 - Betreute Kinder 3 bis unter 6 Jahre - Betreuungsquote (%) | Kindertagesbetreuung am 01.03.2023 - Betreute Kinder 3 bis unter 6 Jahre - Betreuungsquote (%) | not_in_2017 |
| `sozialversicherungspflichtig_besch_ftigte_insgesamt_je_ew` | Sozialversicherungspflichtig Beschäftigte am 30.06.2016 - insgesamt (je 1000 Einwohner) | Sozialversicherungspflichtig Beschäftigte am 30.06.2020 - insgesamt (je 1000 EW) | Sozialversicherungspflichtig Beschäftigte am 30.06.2023 - insgesamt (je 1000 EW) | semantic |
| `sozialversicherungspflichtig_besch_ftigte_land_und_forstwirtschaft_fischerei` | Sozialversicherungspflichtig Beschäftigte am 30.06.2016 - Land- und Forstwirtschaft, Fischerei (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2020 - Land- und Forstwirtschaft, Fischerei (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2023 - Land- und Forstwirtschaft, Fischerei (%) | exact |
| `sozialversicherungspflichtig_besch_ftigte_produzierendes_gewerbe` | Sozialversicherungspflichtig Beschäftigte am 30.06.2016 - Produzierendes Gewerbe (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2020 - Produzierendes Gewerbe (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2023 - Produzierendes Gewerbe (%) | exact |
| `sozialversicherungspflichtig_besch_ftigte_handel_gastgewerbe_verkehr` | Sozialversicherungspflichtig Beschäftigte am 30.06.2016 - Handel, Gastgewerbe, Verkehr (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2020 - Handel, Gastgewerbe, Verkehr (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2023 - Handel, Gastgewerbe, Verkehr (%) | exact |
| `sozialversicherungspflichtig_besch_ftigte_ffentliche_und_private_dienstleister` | Sozialversicherungspflichtig Beschäftigte am 30.06.2016 - Öffentliche und private Dienstleister (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2020 - Öffentliche und private Dienstleister (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2023 - Öffentliche und private Dienstleister (%) | exact |
| `sozialversicherungspflichtig_besch_ftigte_brige_dienstleister_und_ohne_angabe` | Sozialversicherungspflichtig Beschäftigte am 30.06.2016 - Übrige Dienstleister und 'ohne Angabe' (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2020 - Übrige Dienstleister und 'ohne Angabe' (%) | Sozialversicherungspflichtig Beschäftigte am 30.06.2023 - Übrige Dienstleister und 'ohne Angabe' (%) | exact |
| `empf_nger_innen_von_leistungen_nach_sgb_ii_insgesamt_je_ew` | Empfänger(innen) von Leistungen nach SGB II am 31.12.2016 - insgesamt (je 1000 Einwohner) | Empfänger/-innen von Leistungen nach SGB II Oktober 2020 - insgesamt (je 1000 EW) | Empfänger/-innen von Leistungen nach SGB II August 2024 - insgesamt (je 1000 EW) | semantic |
| `empf_nger_innen_von_leistungen_nach_sgb_ii_nicht_erwerbsf_hige_hilfebed_rftige` | Empfänger(innen) von Leistungen nach SGB II am 31.12.2016 - nicht erwerbsfähige Hilfebedürftige (%) | Empfänger/-innen von Leistungen nach SGB II Oktober 2020 - nicht erwerbsfähige Hilfebedürftige (%) | Empfänger/-innen von Leistungen nach SGB II August 2024 - nicht erwerbsfähige Hilfebedürftige (%) | exact |
| `empf_nger_innen_von_leistungen_nach_sgb_ii_ausl_nder_innen` | Empfänger(innen) von Leistungen nach SGB II am 31.12.2016 - Ausländer (%) | Empfänger/-innen von Leistungen nach SGB II Oktober 2020 - Ausländer/-innen (%) | Empfänger/-innen von Leistungen nach SGB II August 2024 - Ausländer/-innen (%) | semantic |
| `arbeitslosenquote_insgesamt` | Arbeitslosenquote März 2017 - insgesamt | Arbeitslosenquote Februar 2021 - insgesamt | Arbeitslosenquote November 2024 - insgesamt | semantic |
| `arbeitslosenquote_m_nner` | Arbeitslosenquote März 2017 - Männer | Arbeitslosenquote Februar 2021 - Männer | Arbeitslosenquote November 2024 - Männer | semantic |
| `arbeitslosenquote_frauen` | Arbeitslosenquote März 2017 - Frauen | Arbeitslosenquote Februar 2021 - Frauen | Arbeitslosenquote November 2024 - Frauen | semantic |
| `arbeitslosenquote_15_bis_24_jahre` | Arbeitslosenquote März 2017 - 15 bis unter 20 Jahre | Arbeitslosenquote Februar 2021 - 15 bis 24 Jahre | Arbeitslosenquote November 2024 - 15 bis 24 Jahre | semantic |
| `arbeitslosenquote_55_bis_64_jahre` | Arbeitslosenquote März 2017 - 55 bis unter 65 Jahre | Arbeitslosenquote Februar 2021 - 55 bis 64 Jahre | Arbeitslosenquote November 2024 - 55 bis 64 Jahre | semantic |
| `fu_noten` | Fußnoten | Fußnoten | Fußnoten | exact |

## Column Mapping Summary

### Match Types

- **exact**: Column name matches exactly after normalization (20 columns)
- **semantic**: Column represents the same concept but with different naming (25 columns)
- **not_in_2017**: Column does not exist in BTW2017, will be NULL (7 columns)

### Columns Not in BTW2017 (7 columns)

These columns will be NULL for BTW2017 data:

1. `bodenfl_che_nach_art_der_tats_chlichen_nutzung_siedlung_und_verkehr` - Land use: Settlement and traffic
2. `bodenfl_che_nach_art_der_tats_chlichen_nutzung_vegetation_und_gew_sser` - Land use: Vegetation and water
3. `wohnfl_che_je_wohnung` - Living area per dwelling
4. `wohnfl_che_je_ew` - Living area per inhabitant
5. `pkw_bestand_pkw_mit_elektro_oder_hybrid_antrieb` - Electric/hybrid vehicles
6. `kindertagesbetreuung_betreute_kinder_unter_3_jahre_betreuungsquote` - Childcare under 3 years
7. `kindertagesbetreuung_betreute_kinder_3_bis_unter_6_jahre_betreuungsquote` - Childcare 3-6 years

## Implementation Strategy

### Column Mapping Dictionary

```python
# Mapping from BTW2017 normalized column names to unified schema
BTW2017_TO_UNIFIED_MAPPING = {
    # Exact matches (same normalized name)
    'land': 'land',
    'wahlkreis_nr': 'wahlkreis_nr',
    'wahlkreis_name': 'wahlkreis_name',
    'gemeinden_anzahl': 'gemeinden_anzahl',
    'fl_che_km': 'fl_che_km',
    'bev_lkerung_insgesamt_in': 'bev_lkerung_insgesamt_in',
    'bev_lkerung_deutsche_in': 'bev_lkerung_deutsche_in',
    'alter_von_bis_jahren_unter_18': 'alter_von_bis_jahren_unter_18',
    'alter_von_bis_jahren_18_24': 'alter_von_bis_jahren_18_24',
    'alter_von_bis_jahren_25_34': 'alter_von_bis_jahren_25_34',
    'alter_von_bis_jahren_35_59': 'alter_von_bis_jahren_35_59',
    'alter_von_bis_jahren_60_74': 'alter_von_bis_jahren_60_74',
    'alter_von_bis_jahren_75_und_mehr': 'alter_von_bis_jahren_75_und_mehr',
    'sozialversicherungspflichtig_besch_ftigte_land_und_forstwirtschaft_fischerei': 'sozialversicherungspflichtig_besch_ftigte_land_und_forstwirtschaft_fischerei',
    'sozialversicherungspflichtig_besch_ftigte_produzierendes_gewerbe': 'sozialversicherungspflichtig_besch_ftigte_produzierendes_gewerbe',
    'sozialversicherungspflichtig_besch_ftigte_handel_gastgewerbe_verkehr': 'sozialversicherungspflichtig_besch_ftigte_handel_gastgewerbe_verkehr',
    'sozialversicherungspflichtig_besch_ftigte_ffentliche_und_private_dienstleister': 'sozialversicherungspflichtig_besch_ftigte_ffentliche_und_private_dienstleister',
    'sozialversicherungspflichtig_besch_ftigte_brige_dienstleister_und_ohne_angabe': 'sozialversicherungspflichtig_besch_ftigte_brige_dienstleister_und_ohne_angabe',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_nicht_erwerbsf_hige_hilfebed_rftige': 'empf_nger_innen_von_leistungen_nach_sgb_ii_nicht_erwerbsf_hige_hilfebed_rftige',
    'fu_noten': 'fu_noten',
    
    # Semantic matches (different naming, same concept)
    'bev_lkerung_ausl_nder': 'bev_lkerung_ausl_nder_innen',
    'bev_lkerungsdichte_einwohner_je_km': 'bev_lkerungsdichte_ew_je_km',
    'zu_bzw_abnahme_der_bev_lkerung_geburtensaldo_je_einwohner': 'zu_bzw_abnahme_der_bev_lkerung_geburtensaldo_je_ew',
    'zu_bzw_abnahme_der_bev_lkerung_wanderungssaldo_je_einwohner': 'zu_bzw_abnahme_der_bev_lkerung_wanderungssaldo_je_ew',
    'baut_tigkeit_und_wohnungswesen_fertiggestellte_wohnungen_je_einwohner': 'fertiggestellte_wohnungen_je_ew',
    'baut_tigkeit_und_wohnungswesen_bestand_an_wohnungen_je_einwohner': 'bestand_an_wohnungen_insgesamt_je_ew',
    'verf_gbares_einkommen_der_privaten_haushalte_je_einwohner': 'verf_gbares_einkommen_der_privaten_haushalte_eur_je_ew',
    'bruttoinlandsprodukt_je_einwohner': 'bruttoinlandsprodukt_eur_je_ew',
    'unternehmensregister_unternehmen_insgesamt_je_einwohner': 'unternehmensregister_unternehmen_insgesamt_je_ew',
    'unternehmensregister_handwerksunternehmen_je_einwohner': 'unternehmensregister_handwerksunternehmen_je_ew',
    'sozialversicherungspflichtig_besch_ftigte_insgesamt_je_einwohner': 'sozialversicherungspflichtig_besch_ftigte_insgesamt_je_ew',
    'absolventen_abg_nger_beruflicher_schulen': 'schulabg_nger_innen_beruflicher_schulen',
    'absolventen_abg_nger_allgemeinbildender_schulen_insgesamt_ohne_externe_je_einwohner': 'schulabg_nger_innen_allgemeinbildender_schulen_insgesamt_ohne_externe_je_ew',
    'absolventen_abg_nger_allgemeinbildender_schulen_ohne_hauptschulabschluss': 'schulabg_nger_innen_allgemeinbildender_schulen_ohne_hauptschulabschluss',
    'absolventen_abg_nger_allgemeinbildender_schulen_mit_hauptschulabschluss': 'schulabg_nger_innen_allgemeinbildender_schulen_mit_hauptschulabschluss',
    'absolventen_abg_nger_allgemeinbildender_schulen_mit_mittlerem_schulabschluss': 'schulabg_nger_innen_allgemeinbildender_schulen_mit_mittlerem_schulabschluss',
    'absolventen_abg_nger_allgemeinbildender_schulen_mit_allgemeiner_und_fachhochschulreife': 'schulabg_nger_innen_allgemeinblldender_schulen_mit_allgemeiner_und_fachhochschulreife',
    'kraftfahrzeugbestand_je_einwohner': 'pkw_bestand_pkw_insgesamt_je_ew',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_insgesamt_je_einwohner': 'empf_nger_innen_von_leistungen_nach_sgb_ii_insgesamt_je_ew',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_ausl_nder': 'empf_nger_innen_von_leistungen_nach_sgb_ii_ausl_nder_innen',
    'arbeitslosenquote_m_rz_insgesamt': 'arbeitslosenquote_insgesamt',
    'arbeitslosenquote_m_rz_m_nner': 'arbeitslosenquote_m_nner',
    'arbeitslosenquote_m_rz_frauen': 'arbeitslosenquote_frauen',
    'arbeitslosenquote_m_rz_15_bis_unter_20_jahre': 'arbeitslosenquote_15_bis_24_jahre',  # Note: age range differs slightly
    'arbeitslosenquote_m_rz_55_bis_unter_65_jahre': 'arbeitslosenquote_55_bis_64_jahre',  # Note: age range differs slightly
}
```

### Data Loading Function

```python
def load_election_csv_unified(csv_path, election_year):
    """
    Load election CSV and map to unified schema.
    """
    # Read CSV (with election-specific parsing)
    df = load_election_structural_data(csv_path, election_year)
    
    # Normalize column names (remove date references)
    df.columns = [normalize_column_name_unified(col) for col in df.columns]
    
    # Map to unified schema
    if election_year == 2017:
        # Apply BTW2017 specific mapping
        df = apply_2017_mapping(df)
    # BTW2021 and BTW2025 don't need mapping (already match unified schema)
    
    # Ensure all unified schema columns exist
    for col in UNIFIED_SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None
    
    # Select only unified schema columns
    df = df[UNIFIED_SCHEMA_COLUMNS]
    
    # Add election_year
    df['election_year'] = election_year
    
    return df

def apply_2017_mapping(df):
    """Map BTW2017 columns to unified schema."""
    # Create new dataframe with unified column names
    unified_df = pd.DataFrame()
    
    for btw2017_col, unified_col in BTW2017_TO_UNIFIED_MAPPING.items():
        if btw2017_col in df.columns:
            unified_df[unified_col] = df[btw2017_col]
        else:
            unified_df[unified_col] = None
    
    return unified_df
```

## Summary

| Election | Total Columns | Exact Matches | Semantic Matches | Not Mappable | Total Mappable | Compatibility |
|----------|---------------|---------------|------------------|--------------|---------------|---------------|
| BTW2017  | 52            | 20 (38%)      | 25 (48%)         | 7 (13.5%)    | 45 (86.5%)    | High          |
| BTW2021  | 52            | 52 (100%)     | 0                | 0            | 52 (100%)     | Perfect       |
| BTW2025  | 52            | 52 (100%)     | 0                | 0            | 52 (100%)     | Perfect       |

**Recommendation**: Use unified schema based on BTW2021/2025. BTW2017 can be included with 86.5% column mapping (45/52 columns). Only 7 columns will be NULL for BTW2017 data.

**Note on BTW2013**: BTW2013 is too different (only 13/52 columns match, 25% overlap) and is **not recommended** for inclusion. If needed, store BTW2013 in a separate table.
