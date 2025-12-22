# Implementation Note: Adding VG250 and Bundestagswahlen Tables

## Overview
This document outlines the implementation plan for adding administrative boundary tables (VG250) and federal election data tables (Bundestagswahlen) to the existing Zensus database.

## Tables to Implement

### VG250 Administrative Boundaries (Priority 1)

1. **`ref_municipality`** (from VG250_GEM)
   - 11,103 municipalities (Gemeinden)
   - Smallest administrative unit for joining with Zensus grid cells

2. **`ref_county`** (from VG250_KRS)
   - 433 counties (Kreise and kreisfreie Städte)
   - For aggregating Zensus data by county

3. **`ref_federal_state`** (from VG250_LAN)
   - 34 federal states (Länder)
   - For state-level aggregation of Zensus data

### Bundestagswahlen (Federal Elections)

4. **`ref_electoral_district`** (from shapefiles)
   - 299 electoral districts per election (2017, 2021, 2025)
   - Electoral district boundaries with geometry
   - **Note on BTW2013**: BTW2013 data structure is too different and is not recommended for inclusion

5. **`fact_election_structural_data`** (from CSV files)
   - Socioeconomic and demographic data per electoral district
   - 52 columns of structural indicators
   - **⚠️ IMPORTANT**: CSV files have poor design - see `BUNDESTAGSWAHLEN_CSV_ANALYSIS.md` for detailed parsing requirements
   - **Column Mapping**: See `BUNDESTAGSWAHLEN_COLUMN_MAPPING.md` for BTW2017/2021/2025 mapping strategy
   - **Note on BTW2013**: BTW2013 data structure is too different and is not recommended for inclusion

## Database Schema

### 1. ref_municipality

```sql
CREATE TABLE zensus.ref_municipality (
    ars TEXT PRIMARY KEY,  -- 12-digit Official Regional Key
    ags TEXT NOT NULL,     -- 8-digit Official Municipality Key
    name TEXT NOT NULL,    -- Municipality name (GEN)
    bez TEXT,              -- Type/Designation (BEZ) - e.g., "Stadt", "Gemeinde"
    land_nr TEXT NOT NULL, -- State number (LKZ)
    land_name TEXT NOT NULL, -- State name
    nuts TEXT,            -- NUTS code
    beginn DATE,          -- Validity start date
    geom GEOMETRY(POLYGON, 3035) NOT NULL,
    CONSTRAINT chk_municipality_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_municipality_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX idx_municipality_geom ON zensus.ref_municipality USING GIST (geom);
CREATE INDEX idx_municipality_ags ON zensus.ref_municipality (ags);
CREATE INDEX idx_municipality_land_nr ON zensus.ref_municipality (land_nr);
```

### 2. ref_county

```sql
CREATE TABLE zensus.ref_county (
    ars TEXT PRIMARY KEY,  -- 5-digit Official Regional Key (e.g., "01001")
    ags TEXT NOT NULL,     -- Same as ARS for counties
    name TEXT NOT NULL,    -- County name (GEN)
    bez TEXT,              -- Type (BEZ) - e.g., "Kreisfreie Stadt", "Landkreis"
    land_nr TEXT NOT NULL, -- State number
    land_name TEXT NOT NULL, -- State name
    nuts TEXT,            -- NUTS code
    beginn DATE,          -- Validity start date
    geom GEOMETRY(POLYGON, 3035) NOT NULL,
    CONSTRAINT chk_county_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_county_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX idx_county_geom ON zensus.ref_county USING GIST (geom);
CREATE INDEX idx_county_ags ON zensus.ref_county (ags);
CREATE INDEX idx_county_land_nr ON zensus.ref_county (land_nr);
```

### 3. ref_federal_state

```sql
CREATE TABLE zensus.ref_federal_state (
    ars TEXT PRIMARY KEY,  -- 2-digit Official Regional Key (e.g., "01")
    ags TEXT NOT NULL,     -- Same as ARS for states
    name TEXT NOT NULL,    -- State name (GEN) - e.g., "Schleswig-Holstein"
    bez TEXT,              -- Type (BEZ) - e.g., "Land", "Freistaat"
    nuts TEXT,            -- NUTS code (e.g., "DEF")
    beginn DATE,          -- Validity start date
    geom GEOMETRY(MULTIPOLYGON, 3035) NOT NULL,
    CONSTRAINT chk_federal_state_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_federal_state_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX idx_federal_state_geom ON zensus.ref_federal_state USING GIST (geom);
CREATE INDEX idx_federal_state_ags ON zensus.ref_federal_state (ags);
```

### 4. ref_electoral_district

```sql
CREATE TABLE zensus.ref_electoral_district (
    wahlkreis_nr INTEGER NOT NULL,
    wahlkreis_name TEXT NOT NULL,
    land_nr TEXT NOT NULL,
    land_name TEXT NOT NULL,
    election_year INTEGER NOT NULL,
    geom GEOMETRY(POLYGON, 3035) NOT NULL,
    CONSTRAINT pk_electoral_district PRIMARY KEY (wahlkreis_nr, election_year),
    CONSTRAINT chk_wahlkreis_nr CHECK (wahlkreis_nr BETWEEN 1 AND 299),
    CONSTRAINT chk_election_year CHECK (election_year IN (2017, 2021, 2025)),
    CONSTRAINT chk_electoral_district_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_electoral_district_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX idx_electoral_district_geom ON zensus.ref_electoral_district USING GIST (geom);
CREATE INDEX idx_electoral_district_wkr_nr ON zensus.ref_electoral_district (wahlkreis_nr);
CREATE INDEX idx_electoral_district_year ON zensus.ref_electoral_district (election_year);
CREATE INDEX idx_electoral_district_land_nr ON zensus.ref_electoral_district (land_nr);
```

### 5. fact_election_structural_data

**Important**: 
- Column names are normalized to remove date-specific parts (months, years). The original CSV column names contain dates (e.g., "am 31.12.2023", "Februar 2021", "November 2024") that differ between elections.
- **BTW2021 and BTW2025**: After normalization, these have **identical column structure** (52 columns). They can use the same schema.
- **BTW2017**: 45 out of 52 columns (86.5%) can be mapped to the unified schema. Only 7 columns will be NULL for 2017 data. See `BUNDESTAGSWAHLEN_COLUMN_MAPPING.md` for detailed mapping strategy.
- **BTW2013**: BTW2013 data structure is too different (only 13/52 columns match, 25% overlap) and is **not recommended** for inclusion. If needed, store BTW2013 in a separate table.
- **Always include `election_year` column** to distinguish between elections and handle NULLs appropriately.

```sql
CREATE TABLE zensus.fact_election_structural_data (
    wahlkreis_nr INTEGER NOT NULL,
    election_year INTEGER NOT NULL,
    
    -- Administrative
    gemeinden_anzahl INTEGER,
    flaeche_km2 NUMERIC,
    
    -- Demographics (reference dates differ by election)
    bevoelkerung_insgesamt_1000 NUMERIC,
    bevoelkerung_deutsche_1000 NUMERIC,
    bevoelkerung_auslaender_pct NUMERIC,
    bevoelkerungsdichte NUMERIC,
    bevoelkerung_geburten_saldo_je_1000ew NUMERIC,
    bevoelkerung_wanderung_saldo_je_1000ew NUMERIC,
    
    -- Age Structure
    alter_unter_18_pct NUMERIC,
    alter_18_24_pct NUMERIC,
    alter_25_34_pct NUMERIC,
    alter_35_59_pct NUMERIC,
    alter_60_74_pct NUMERIC,
    alter_75_plus_pct NUMERIC,
    
    -- Land Use (NULL for BTW2017)
    bodenflaeche_siedlung_verkehr_pct NUMERIC,
    bodenflaeche_vegetation_gewaesser_pct NUMERIC,
    
    -- Housing
    wohnungen_fertiggestellt_je_1000ew NUMERIC,
    wohnungen_bestand_je_1000ew NUMERIC,
    wohnflaeche_je_wohnung NUMERIC,  -- NULL for BTW2017
    wohnflaeche_je_ew NUMERIC,  -- NULL for BTW2017
    
    -- Transportation
    pkw_bestand_je_1000ew NUMERIC,
    pkw_elektro_hybrid_pct NUMERIC,  -- NULL for BTW2017
    
    -- Economy
    unternehmen_insgesamt_je_1000ew NUMERIC,
    unternehmen_handwerk_je_1000ew NUMERIC,
    einkommen_verfuegbar_eur_je_ew NUMERIC,
    bip_eur_je_ew NUMERIC,
    
    -- Education
    schulabgaenger_berufliche_schulen INTEGER,
    schulabgaenger_allgemeinbildend_je_1000ew NUMERIC,
    schulabgaenger_ohne_hauptschulabschluss_pct NUMERIC,
    schulabgaenger_hauptschulabschluss_pct NUMERIC,
    schulabgaenger_mittlerer_abschluss_pct NUMERIC,
    schulabgaenger_abitur_pct NUMERIC,
    kindertagesbetreuung_unter_3_pct NUMERIC,  -- NULL for BTW2017
    kindertagesbetreuung_3_6_pct NUMERIC,  -- NULL for BTW2017
    
    -- Employment
    beschaeftigte_insgesamt_je_1000ew NUMERIC,
    beschaeftigte_landwirtschaft_pct NUMERIC,
    beschaeftigte_produzierendes_gewerbe_pct NUMERIC,
    beschaeftigte_handel_gastgewerbe_verkehr_pct NUMERIC,
    beschaeftigte_oeffentliche_dienstleister_pct NUMERIC,
    beschaeftigte_uebrige_dienstleister_pct NUMERIC,
    sgb2_leistungsempfaenger_je_1000ew NUMERIC,
    sgb2_nicht_erwerbsfaehig_pct NUMERIC,
    sgb2_auslaender_pct NUMERIC,
    arbeitslosenquote_insgesamt_pct NUMERIC,
    arbeitslosenquote_maenner_pct NUMERIC,
    arbeitslosenquote_frauen_pct NUMERIC,
    arbeitslosenquote_15_24_pct NUMERIC,
    arbeitslosenquote_55_64_pct NUMERIC,
    
    -- Metadata
    fussnoten TEXT,  -- Footnotes column (may contain additional notes)
    
    -- Always include election_year to distinguish elections
    -- This is critical for handling NULLs (2013 has many NULL columns)
    CONSTRAINT pk_election_structural_data PRIMARY KEY (wahlkreis_nr, election_year),
    CONSTRAINT fk_election_structural_data_district 
        FOREIGN KEY (wahlkreis_nr, election_year) 
        REFERENCES zensus.ref_electoral_district(wahlkreis_nr, election_year),
    CONSTRAINT chk_wahlkreis_nr_range CHECK (wahlkreis_nr BETWEEN 1 AND 299)
);

CREATE INDEX idx_election_structural_data_wkr_nr ON zensus.fact_election_structural_data (wahlkreis_nr);
CREATE INDEX idx_election_structural_data_year ON zensus.fact_election_structural_data (election_year);
```

**Note on Column Name Normalization**: 
- Original CSV columns: `"Bevölkerung am 31.12.2023 - Insgesamt (in 1000)"`
- Normalized column: `bevoelkerung_insgesamt_1000`
- This allows the same schema to work across all election years despite different reference dates

## Implementation Steps

### Step 1: Create Database Schemas

1. Create SQL schema files for each table:
   - `docker/init/03_vg250_schema.sql` - VG250 tables
   - `docker/init/04_bundestagswahlen_schema.sql` - Election tables

2. Apply schemas to database:
   ```bash
   docker-compose exec -T postgres psql -U zensus_user -d zensus_db < docker/init/03_vg250_schema.sql
   docker-compose exec -T postgres psql -U zensus_user -d zensus_db < docker/init/04_bundestagswahlen_schema.sql
   ```

### Step 2: Create Load Scripts

#### 2.1 VG250 Load Script: `etl/load_vg250.py`

**Features**:
- Read shapefiles from VG250 dataset
- Reproject from EPSG:25832 to EPSG:3035
- Handle different geometry types (Polygon vs MultiPolygon)
- Load into appropriate reference tables
- Validate geometries and fix invalid ones

**Usage**:
```bash
# Load municipalities
python etl/load_vg250.py \
    --shapefile "/path/to/vg250_ebenen_0101/VG250_GEM.shp" \
    --table ref_municipality

# Load counties
python etl/load_vg250.py \
    --shapefile "/path/to/vg250_ebenen_0101/VG250_KRS.shp" \
    --table ref_county

# Load federal states
python etl/load_vg250.py \
    --shapefile "/path/to/vg250_ebenen_0101/VG250_LAN.shp" \
    --table ref_federal_state
```

#### 2.2 Bundestagswahlen Load Script: `etl/load_elections.py`

**Features**:
- Load shapefiles for electoral districts (multiple election years)
- Reproject from EPSG:25832 to EPSG:3035
- **Special CSV parsing** (see `BUNDESTAGSWAHLEN_CSV_ANALYSIS.md` for details):
  - Dynamic header row detection (finds row with "Land" and "Wahlkreis-Nr.")
  - Handles variable comment rows (8-9 rows depending on election)
  - Normalizes column names (removes date-specific parts)
  - Parses German number format (comma decimals, dot thousands)
  - Handles Wahlkreis-Nr. format differences (zero-padded vs plain integers)
  - Filters out summary rows
- Load structural data into fact table
- Handle multiple election years

**Important CSV Parsing Notes**:
- **BTW2013**: Not recommended due to encoding issues (ISO-8859-1 vs UTF-8)
- **BTW2021**: 8 comment rows, header at line 9, zero-padded Wahlkreis-Nr. (001, 002)
- **BTW2025**: 9 comment rows, header at line 10, plain Wahlkreis-Nr. (1, 2)
- Column names contain dates (e.g., "am 31.12.2023") that differ between elections
- All numeric values use German format: `2.124,3` = 2124.3

**Usage**:
```bash
# Load electoral district boundaries
python etl/load_elections.py \
    --shapefile "/path/to/btw2025/btw25_geometrie_wahlkreise_vg250_shp/btw25_geometrie_wahlkreise_vg250.shp" \
    --election-year 2025

# Load structural data (automatically detects header row)
python etl/load_elections.py \
    --csv "/path/to/btw2025/btw2025_strukturdaten.csv" \
    --election-year 2025
```

**CSV Parsing Implementation** (see `BUNDESTAGSWAHLEN_CSV_ANALYSIS.md` and `BUNDESTAGSWAHLEN_COLUMN_MAPPING.md` for full details):

**Key Points**:
- BTW2021 and BTW2025 have identical structure after normalization (52 columns) - no mapping needed
- BTW2017 has high compatibility (45/52 columns mappable, 86.5%)
  - 20 exact matches (same normalized name)
  - 25 semantic matches (same concept, different naming)
  - 7 columns not in BTW2017 (will be NULL)
- Use unified schema based on 2021/2025, with NULLs for 2017 missing columns (7 columns)
- BTW2013 is not recommended (only 13/52 columns match, 25% overlap)
- Always add `election_year` column when loading data
- See `BUNDESTAGSWAHLEN_COLUMN_MAPPING.md` for complete column mapping table and implementation details

```python
def find_header_row(csv_path):
    """Find the row containing column names (has 'Land' and 'Wahlkreis-Nr.')."""
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for i, line in enumerate(f):
            parts = line.split(';')
            if len(parts) > 2 and 'Land' in parts[0] and 'Wahlkreis' in parts[1]:
                return i  # Zero-indexed line number
    return None

def normalize_column_name(col_name):
    """Normalize column names by removing date-specific parts."""
    import re
    # Remove date patterns (am DD.MM.YYYY)
    col = re.sub(r'\s*am\s+\d{2}\.\d{2}\.\d{4}\s*', ' ', col_name)
    # Remove other date references
    col = re.sub(r'\s*\d{4}\s*', ' ', col)
    # Convert to lowercase and sanitize
    col = col.lower()
    col = re.sub(r'[^a-z0-9\s]', ' ', col)
    col = re.sub(r'\s+', '_', col)
    return col.strip('_')

def parse_german_number(value):
    """Convert German number format to float (2.124,3 -> 2124.3)."""
    if pd.isna(value) or value == '' or value == '–':
        return None
    value_str = str(value).strip().replace('.', '').replace(',', '.')
    try:
        return float(value_str)
    except ValueError:
        return None
```

### Column Mapping Strategy for BTW2017

**Important**: BTW2017 requires column mapping to the unified schema. See `BUNDESTAGSWAHLEN_COLUMN_MAPPING.md` for the complete mapping table.

**Summary**:
- **BTW2021/2025**: No mapping needed (identical after normalization)
- **BTW2017**: 45 out of 52 columns (86.5%) can be mapped
  - 20 exact matches (same normalized name)
  - 25 semantic matches (same concept, different naming)
  - 7 columns not in BTW2017 (will be NULL)

**Columns that will be NULL for BTW2017**:
1. `bodenflaeche_siedlung_verkehr_pct` - Land use: Settlement and traffic
2. `bodenflaeche_vegetation_gewaesser_pct` - Land use: Vegetation and water
3. `wohnflaeche_je_wohnung` - Living area per dwelling
4. `wohnflaeche_je_ew` - Living area per inhabitant
5. `pkw_elektro_hybrid_pct` - Electric/hybrid vehicles
6. `kindertagesbetreuung_unter_3_pct` - Childcare under 3 years
7. `kindertagesbetreuung_3_6_pct` - Childcare 3-6 years

**Column Mapping Dictionary**:

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

# Unified schema column names (all 52 columns)
UNIFIED_SCHEMA_COLUMNS = [
    'land', 'wahlkreis_nr', 'wahlkreis_name',
    'gemeinden_anzahl', 'fl_che_km',
    'bev_lkerung_insgesamt_in', 'bev_lkerung_deutsche_in', 'bev_lkerung_ausl_nder_innen',
    'bev_lkerungsdichte_ew_je_km',
    'zu_bzw_abnahme_der_bev_lkerung_geburtensaldo_je_ew',
    'zu_bzw_abnahme_der_bev_lkerung_wanderungssaldo_je_ew',
    'alter_von_bis_jahren_unter_18', 'alter_von_bis_jahren_18_24',
    'alter_von_bis_jahren_25_34', 'alter_von_bis_jahren_35_59',
    'alter_von_bis_jahren_60_74', 'alter_von_bis_jahren_75_und_mehr',
    'bodenfl_che_nach_art_der_tats_chlichen_nutzung_siedlung_und_verkehr',
    'bodenfl_che_nach_art_der_tats_chlichen_nutzung_vegetation_und_gew_sser',
    'fertiggestellte_wohnungen_je_ew', 'bestand_an_wohnungen_insgesamt_je_ew',
    'wohnfl_che_je_wohnung', 'wohnfl_che_je_ew',
    'pkw_bestand_pkw_insgesamt_je_ew', 'pkw_bestand_pkw_mit_elektro_oder_hybrid_antrieb',
    'unternehmensregister_unternehmen_insgesamt_je_ew',
    'unternehmensregister_handwerksunternehmen_je_ew',
    'verf_gbares_einkommen_der_privaten_haushalte_eur_je_ew',
    'bruttoinlandsprodukt_eur_je_ew',
    'schulabg_nger_innen_beruflicher_schulen',
    'schulabg_nger_innen_allgemeinbildender_schulen_insgesamt_ohne_externe_je_ew',
    'schulabg_nger_innen_allgemeinbildender_schulen_ohne_hauptschulabschluss',
    'schulabg_nger_innen_allgemeinbildender_schulen_mit_hauptschulabschluss',
    'schulabg_nger_innen_allgemeinbildender_schulen_mit_mittlerem_schulabschluss',
    'schulabg_nger_innen_allgemeinblldender_schulen_mit_allgemeiner_und_fachhochschulreife',
    'kindertagesbetreuung_betreute_kinder_unter_3_jahre_betreuungsquote',
    'kindertagesbetreuung_betreute_kinder_3_bis_unter_6_jahre_betreuungsquote',
    'sozialversicherungspflichtig_besch_ftigte_insgesamt_je_ew',
    'sozialversicherungspflichtig_besch_ftigte_land_und_forstwirtschaft_fischerei',
    'sozialversicherungspflichtig_besch_ftigte_produzierendes_gewerbe',
    'sozialversicherungspflichtig_besch_ftigte_handel_gastgewerbe_verkehr',
    'sozialversicherungspflichtig_besch_ftigte_ffentliche_und_private_dienstleister',
    'sozialversicherungspflichtig_besch_ftigte_brige_dienstleister_und_ohne_angabe',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_insgesamt_je_ew',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_nicht_erwerbsf_hige_hilfebed_rftige',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_ausl_nder_innen',
    'arbeitslosenquote_insgesamt', 'arbeitslosenquote_m_nner', 'arbeitslosenquote_frauen',
    'arbeitslosenquote_15_bis_24_jahre', 'arbeitslosenquote_55_bis_64_jahre',
    'fu_noten',
]
```

**Complete Data Loading Function with Mapping**:

```python
def load_election_csv_unified(csv_path, election_year):
    """
    Load election CSV and map to unified schema.
    
    Args:
        csv_path: Path to CSV file
        election_year: Election year (2017, 2021, or 2025)
    
    Returns:
        DataFrame with unified schema columns and election_year
    """
    # Determine encoding based on election year
    if election_year == 2017:
        encoding = 'iso-8859-1'
        header_row = 8  # Line 9 (0-indexed: 8)
    elif election_year == 2021:
        encoding = 'utf-8-sig'
        header_row = 8  # Line 9 (0-indexed: 8)
    elif election_year == 2025:
        encoding = 'utf-8-sig'
        header_row = 9  # Line 10 (0-indexed: 9)
    else:
        raise ValueError(f"Unsupported election year: {election_year}")
    
    # Read CSV
    df = pd.read_csv(
        csv_path,
        encoding=encoding,
        sep=';',
        skiprows=header_row,
        low_memory=False
    )
    
    # Normalize column names (remove date references)
    df.columns = [normalize_column_name(col) for col in df.columns]
    
    # Map to unified schema
    if election_year == 2017:
        # Apply BTW2017 specific mapping
        df = apply_2017_mapping(df)
    # BTW2021 and BTW2025 don't need mapping (already match unified schema)
    
    # Ensure all unified schema columns exist (set missing to NULL)
    for col in UNIFIED_SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None
    
    # Select only unified schema columns in correct order
    df = df[UNIFIED_SCHEMA_COLUMNS]
    
    # Add election_year
    df['election_year'] = election_year
    
    # Normalize Wahlkreis-Nr. (handle zero-padding)
    df['wahlkreis_nr'] = df['wahlkreis_nr'].apply(
        lambda x: int(str(x).lstrip('0') or '0') if pd.notna(x) else None
    )
    
    # Filter out summary rows (Wahlkreis-Nr. should be 1-299)
    df = df[df['wahlkreis_nr'].notna() & (df['wahlkreis_nr'] >= 1) & (df['wahlkreis_nr'] <= 299)]
    
    return df

def apply_2017_mapping(df):
    """
    Map BTW2017 columns to unified schema.
    
    Args:
        df: DataFrame with BTW2017 normalized column names
    
    Returns:
        DataFrame with unified schema column names
    """
    unified_df = pd.DataFrame()
    
    # Map columns that exist in BTW2017
    for btw2017_col, unified_col in BTW2017_TO_UNIFIED_MAPPING.items():
        if btw2017_col in df.columns:
            unified_df[unified_col] = df[btw2017_col]
        else:
            # Column not found (shouldn't happen if mapping is correct)
            unified_df[unified_col] = None
    
    # Keep any other columns that might be in the dataframe
    for col in df.columns:
        if col not in BTW2017_TO_UNIFIED_MAPPING:
            # This column is not mappable (e.g., Zensus 2011 data)
            # It will be dropped when we select only UNIFIED_SCHEMA_COLUMNS
            pass
    
    return unified_df
```

**Note**: For the complete mapping table showing all 52 columns with their original names from each election, see `BUNDESTAGSWAHLEN_COLUMN_MAPPING.md`.

### Step 3: Data Loading Workflow

1. **Load VG250 data** (in hierarchical order):
   ```bash
   # 1. Federal states (top level)
   python etl/load_vg250.py --shapefile "VG250_LAN.shp" --table ref_federal_state
   
   # 2. Counties
   python etl/load_vg250.py --shapefile "VG250_KRS.shp" --table ref_county
   
   # 3. Municipalities (most detailed)
   python etl/load_vg250.py --shapefile "VG250_GEM.shp" --table ref_municipality
   ```

2. **Load Bundestagswahlen data**:
   ```bash
   # For each election year (2017, 2021, 2025):
   
   # 2017 Election (requires ISO-8859-1 encoding, column mapping)
   python etl/load_elections.py --shapefile "btw17_geometrie_wahlkreise_vg250_shp/btw17_geometrie_wahlkreise_vg250.shp" --election-year 2017
   python etl/load_elections.py --csv "btw2017/btw2017_strukturdaten.csv" --election-year 2017
   
   # 2021 Election
   python etl/load_elections.py --shapefile "btw21_geometrie_wahlkreise_vg250_shp/Geometrie_Wahlkreise_20DBT_VG250.shp" --election-year 2021
   python etl/load_elections.py --csv "btw2021/btw21_strukturdaten.csv" --election-year 2021
   
   # 2025 Election
   python etl/load_elections.py --shapefile "btw25_geometrie_wahlkreise_vg250_shp/btw25_geometrie_wahlkreise_vg250.shp" --election-year 2025
   python etl/load_elections.py --csv "btw2025/btw2025_strukturdaten.csv" --election-year 2025
   ```
   
   **Note**: BTW2017 requires special handling:
   - ISO-8859-1 encoding (not UTF-8)
   - Column mapping to unified schema (45/52 columns mappable, 86.5%)
   - 7 columns will be NULL:
     - `bodenflaeche_siedlung_verkehr_pct`, `bodenflaeche_vegetation_gewaesser_pct` (land use)
     - `wohnflaeche_je_wohnung`, `wohnflaeche_je_ew` (housing area)
     - `pkw_elektro_hybrid_pct` (electric vehicles)
     - `kindertagesbetreuung_unter_3_pct`, `kindertagesbetreuung_3_6_pct` (childcare by age)
   - See `BUNDESTAGSWAHLEN_COLUMN_MAPPING.md` for complete mapping table
   
   **Note on BTW2013**: BTW2013 is not recommended due to low compatibility (only 13/52 columns match, 25% overlap). If needed, implement separately.

### Step 4: Verification Queries

After loading, verify data integrity:

```sql
-- Check row counts
SELECT 'ref_municipality' as table_name, COUNT(*) as row_count FROM zensus.ref_municipality
UNION ALL
SELECT 'ref_county', COUNT(*) FROM zensus.ref_county
UNION ALL
SELECT 'ref_federal_state', COUNT(*) FROM zensus.ref_federal_state
UNION ALL
SELECT 'ref_electoral_district', COUNT(*) FROM zensus.ref_electoral_district
UNION ALL
SELECT 'fact_election_structural_data', COUNT(*) FROM zensus.fact_election_structural_data;

-- Check for invalid geometries
SELECT 'ref_municipality' as table_name, COUNT(*) as invalid_geoms 
FROM zensus.ref_municipality WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT 'ref_county', COUNT(*) FROM zensus.ref_county WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT 'ref_federal_state', COUNT(*) FROM zensus.ref_federal_state WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT 'ref_electoral_district', COUNT(*) FROM zensus.ref_electoral_district WHERE NOT ST_IsValid(geom);

-- Check SRID
SELECT 'ref_municipality' as table_name, COUNT(*) as wrong_srid 
FROM zensus.ref_municipality WHERE ST_SRID(geom) != 3035
UNION ALL
SELECT 'ref_county', COUNT(*) FROM zensus.ref_county WHERE ST_SRID(geom) != 3035
UNION ALL
SELECT 'ref_federal_state', COUNT(*) FROM zensus.ref_federal_state WHERE ST_SRID(geom) != 3035
UNION ALL
SELECT 'ref_electoral_district', COUNT(*) FROM zensus.ref_electoral_district WHERE ST_SRID(geom) != 3035;
```

## Integration with Existing Zensus Data

### Spatial Joins

Join Zensus grid data with administrative boundaries:

```sql
-- Aggregate Zensus data by municipality
SELECT 
    m.name as municipality,
    m.land_name as state,
    COUNT(g.grid_id) as grid_cells,
    SUM(f.einwohner) as total_population
FROM zensus.ref_municipality m
JOIN zensus.ref_grid_1km g ON ST_Intersects(m.geom, g.geom)
JOIN zensus.fact_zensus_1km_bevoelkerungszahl f ON g.grid_id = f.grid_id
GROUP BY m.name, m.land_name
ORDER BY total_population DESC;

-- Aggregate Zensus data by county
SELECT 
    c.name as county,
    c.land_name as state,
    COUNT(g.grid_id) as grid_cells,
    SUM(f.einwohner) as total_population
FROM zensus.ref_county c
JOIN zensus.ref_grid_1km g ON ST_Intersects(c.geom, g.geom)
JOIN zensus.fact_zensus_1km_bevoelkerungszahl f ON g.grid_id = f.grid_id
GROUP BY c.name, c.land_name;

-- Aggregate Zensus data by electoral district
SELECT 
    ed.wahlkreis_nr,
    ed.wahlkreis_name,
    ed.election_year,
    COUNT(g.grid_id) as grid_cells,
    SUM(f.einwohner) as total_population
FROM zensus.ref_electoral_district ed
JOIN zensus.ref_grid_1km g ON ST_Intersects(ed.geom, g.geom)
JOIN zensus.fact_zensus_1km_bevoelkerungszahl f ON g.grid_id = f.grid_id
WHERE ed.election_year = 2025
GROUP BY ed.wahlkreis_nr, ed.wahlkreis_name, ed.election_year;
```

### Combining Zensus and Election Data

```sql
-- Compare Zensus demographics with election structural data
SELECT 
    ed.wahlkreis_nr,
    ed.wahlkreis_name,
    -- Zensus data (aggregated)
    SUM(f.einwohner) as zensus_population,
    -- Election structural data
    esd.bevoelkerung_insgesamt_1000 * 1000 as structural_population,
    esd.alter_unter_18_pct as structural_age_under_18_pct,
    esd.arbeitslosenquote_insgesamt_pct
FROM zensus.ref_electoral_district ed
JOIN zensus.ref_grid_1km g ON ST_Intersects(ed.geom, g.geom)
JOIN zensus.fact_zensus_1km_bevoelkerungszahl f ON g.grid_id = f.grid_id
LEFT JOIN zensus.fact_election_structural_data esd 
    ON ed.wahlkreis_nr = esd.wahlkreis_nr 
    AND ed.election_year = esd.election_year
WHERE ed.election_year = 2025
GROUP BY ed.wahlkreis_nr, ed.wahlkreis_name, esd.bevoelkerung_insgesamt_1000, 
         esd.alter_unter_18_pct, esd.arbeitslosenquote_insgesamt_pct;
```

## Technical Considerations

### Coordinate System Reprojection

All shapefiles are in **EPSG:25832** (ETRS89 / UTM Zone 32N) and must be reprojected to **EPSG:3035** (ETRS89-LAEA) to match existing Zensus grid data.

**Implementation**:
```python
# In load scripts
if gdf.crs is None or gdf.crs.to_epsg() != 3035:
    if gdf.crs is None:
        gdf.set_crs(epsg=25832, inplace=True)
    gdf = gdf.to_crs(epsg=3035)
```

### Geometry Validation

- Validate all geometries before insertion
- Fix invalid geometries using `geom.buffer(0)` if needed
- Handle MultiPolygon to Polygon conversion if required

### CSV Parsing - Critical Implementation Details

**Bundestagswahlen CSV files are poorly designed and require special handling**. See `BUNDESTAGSWAHLEN_CSV_ANALYSIS.md` for complete details.

**Key Issues**:
1. **Variable comment rows**: 8-9 rows depending on election year
2. **No proper header**: Column names are in first data row, not separate header
3. **Date-specific column names**: Names contain dates that differ between elections
4. **German number format**: Comma decimals (`2.124,3` = 2124.3)
5. **Encoding issues**: BTW2013 uses non-UTF-8 encoding (not recommended)

**Required Parsing Steps**:

1. **Dynamic header detection**:
   ```python
   def find_header_row(csv_path):
       with open(csv_path, 'r', encoding='utf-8-sig') as f:
           for i, line in enumerate(f):
               parts = line.split(';')
               if len(parts) > 2 and 'Land' in parts[0] and 'Wahlkreis' in parts[1]:
                   return i
       return None
   ```

2. **Read with detected header**:
   ```python
   header_row = find_header_row(csv_path)
   df = pd.read_csv(csv_path, encoding='utf-8-sig', sep=';', skiprows=header_row)
   ```

3. **Normalize column names** (remove date-specific parts):
   ```python
   def normalize_column_name(col_name):
       import re
       col = re.sub(r'\s*am\s+\d{2}\.\d{2}\.\d{4}\s*', ' ', col_name)
       col = re.sub(r'\s*\d{4}\s*', ' ', col)
       col = col.lower().replace(' ', '_').replace('-', '_')
       return re.sub(r'[^a-z0-9_]', '', col)
   ```

4. **Parse German numbers**:
   ```python
   def parse_german_number(value):
       if pd.isna(value) or value == '' or value == '–':
           return None
       value_str = str(value).strip().replace('.', '').replace(',', '.')
       return float(value_str)
   ```

5. **Normalize Wahlkreis-Nr.** (handle zero-padding):
   ```python
   df['wahlkreis_nr'] = df['wahlkreis_nr'].apply(lambda x: int(str(x).lstrip('0') or '0'))
   ```

6. **Filter summary rows**:
   ```python
   df = df[df['wahlkreis_nr'].notna() & (df['wahlkreis_nr'] <= 299)]
   ```

**Election-Specific Notes**:
- **BTW2017**: ISO-8859-1 encoding, 8 comment rows, header at line 9, 52 columns (45 mappable to unified schema) - **requires column mapping**
- **BTW2021**: UTF-8-sig encoding, 8 comment rows, header at line 9, zero-padded Wahlkreis-Nr. (001, 002), 52 columns
- **BTW2025**: UTF-8-sig encoding, 9 comment rows, header at line 10, plain Wahlkreis-Nr. (1, 2), 52 columns
- **BTW2013**: Not recommended - too different structure (43 columns, only 13 match unified schema)

## File Structure

After implementation, the project structure should include:

```
etl/
  ├── load_vg250.py          # VG250 shapefile loader
  ├── load_elections.py       # Election data loader
  ├── load_grids.py          # Existing grid loader
  └── load_zensus.py         # Existing Zensus CSV loader

docker/init/
  ├── 01_init.sql            # Existing initialization
  ├── 02_schema.sql          # Existing Zensus schema
  ├── 03_vg250_schema.sql    # NEW: VG250 tables
  └── 04_bundestagswahlen_schema.sql  # NEW: Election tables
```

## Testing Checklist

- [ ] All schemas created successfully
- [ ] VG250 shapefiles load correctly (municipalities, counties, states)
- [ ] All geometries reprojected to EPSG:3035
- [ ] All geometries valid
- [ ] Electoral district shapefiles load for all election years
- [ ] CSV structural data loads correctly
- [ ] Foreign key constraints work
- [ ] Spatial indexes created and functional
- [ ] Spatial joins with Zensus grid data work correctly
- [ ] Row counts match expected values

## Next Steps After Implementation

1. Create views for common aggregations (e.g., `v_zensus_by_municipality`)
2. Add materialized views for performance-critical queries
3. Document API endpoints if building a REST API
4. Create data quality monitoring queries
5. Set up automated data refresh procedures

