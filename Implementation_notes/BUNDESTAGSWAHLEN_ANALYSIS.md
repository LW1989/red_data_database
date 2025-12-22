# Bundestagswahlen (Federal Election) Data Analysis

## Overview
The `bundestagswahlen` folder contains data for multiple German federal elections (Bundestagswahlen). Each election includes:
- **Shapefiles**: Electoral district (Wahlkreis) boundaries
- **CSV files**: Structural and socioeconomic data per electoral district

## Available Elections

### 1. **BTW2013** (2013 Election - 18th Bundestag)
- **Shapefile**: `btw13_geometrie_wahlkreise_etrs89-vg1000_geo_shp/Geometrie_Wahlkreise_18DBT_VG1000.shp`
- **CSV**: `btw2013_strukturdaten.csv`
- **Note**: CSV encoding issues detected (may need special handling)

### 2. **BTW2021** (2021 Election - 20th Bundestag)
- **Shapefile**: `btw21_geometrie_wahlkreise_vg250_shp/Geometrie_Wahlkreise_20DBT_VG250.shp`
- **CSV**: `btw21_strukturdaten.csv`
- **Election Date**: September 26, 2021

### 3. **BTW2025** (2025 Election - 21st Bundestag)
- **Shapefile**: `btw25_geometrie_wahlkreise_vg250_shp/btw25_geometrie_wahlkreise_vg250.shp`
- **CSV**: `btw2025_strukturdaten.csv`
- **Election Date**: February 23, 2025

## Shapefile Structure

All shapefiles contain **299 electoral districts** (Wahlkreise), which is the standard number for German federal elections.

### Common Columns:
- **`WKR_NR`**: Electoral district number (1-299)
- **`WKR_NAME`**: Electoral district name (e.g., "Flensburg – Schleswig")
- **`LAND_NR`**: State number (e.g., "01" for Schleswig-Holstein)
- **`LAND_NAME`**: State name (e.g., "Schleswig-Holstein")
- **`geometry`**: Polygon geometry of the electoral district

### Coordinate Systems:
- **BTW2013**: EPSG:25832 (ETRS89 / UTM Zone 32N) - based on VG1000
- **BTW2021**: EPSG:25832 (ETRS89 / UTM Zone 32N) - based on VG250
- **BTW2025**: EPSG:25832 (ETRS89 / UTM Zone 32N) - based on VG250

**Note**: All need reprojection to **EPSG:3035** to match your database.

## CSV Structure (Structural Data)

The CSV files contain socioeconomic and demographic data for each electoral district. The files have:
- **Encoding**: UTF-8 with BOM (use `utf-8-sig` encoding when reading)
- **Delimiter**: Semicolon (`;`)
- **Header rows**: Multiple comment rows (copyright, license, data sources) - typically 7-8 rows
- **Column names**: The first data row contains the actual column names (not in the header)
- **Data rows**: One row per electoral district (299 rows + header row with column names)

**Reading the CSV**:
```python
# Skip first 7-8 comment rows, then use first data row as column names
df = pd.read_csv(
    csv_path,
    encoding='utf-8-sig',  # Handle BOM
    sep=';',
    skiprows=7,  # Skip comment rows
    header=0  # First row after skiprows contains column names
)
# Then rename columns from first row if needed
```

### CSV Column Categories (based on BTW2025):

1. **Identification**:
   - Land (State)
   - Wahlkreis-Nr. (Electoral district number)
   - Wahlkreis-Name (Electoral district name)

2. **Administrative Data**:
   - Gemeinden am 31.12.2023 (Anzahl) - Number of municipalities
   - Fläche am 31.12.2023 (km²) - Area in square kilometers

3. **Demographics** (as of 31.12.2023):
   - Bevölkerung insgesamt (in 1000) - Total population
   - Bevölkerung - Deutsche (in 1000) - German population
   - Bevölkerung - Ausländer/-innen (%) - Foreign population percentage
   - Bevölkerungsdichte (EW je km²) - Population density
   - Population change indicators (birth rate, migration)

4. **Age Structure**:
   - unter 18 (%)
   - 18-24 (%)
   - 25-34 (%)
   - 35-59 (%)
   - 60-74 (%)
   - 75 und mehr (%)

5. **Land Use** (as of 31.12.2022):
   - Siedlung und Verkehr (%) - Settlement and traffic
   - Vegetation und Gewässer (%) - Vegetation and water

6. **Housing**:
   - Fertiggestellte Wohnungen 2023 (je 1000 EW) - Completed housing units
   - Bestand an Wohnungen (je 1000 EW) - Housing stock
   - Wohnfläche (je Wohnung / je EW) - Living space

7. **Transportation**:
   - PKW-Bestand (je 1000 EW) - Car ownership
   - PKW mit Elektro- oder Hybrid-Antrieb (%) - Electric/hybrid cars

8. **Economy**:
   - Unternehmen insgesamt (je 1000 EW) - Total companies
   - Handwerksunternehmen (je 1000 EW) - Craft businesses
   - Verfügbares Einkommen (EUR je EW) - Disposable income
   - Bruttoinlandsprodukt (EUR je EW) - GDP per capita

9. **Education**:
   - Schulabgänger/-innen beruflicher Schulen - Vocational school graduates
   - Schulabgänger/-innen allgemeinbildender Schulen - General education graduates
   - Education levels (Hauptschulabschluss, mittlerer Abschluss, Abitur)
   - Kindertagesbetreuung - Childcare coverage

10. **Employment** (as of 30.06.2023):
    - Sozialversicherungspflichtig Beschäftigte - Social security employees
    - Employment by sector (Agriculture, Manufacturing, Trade, Services)
    - Arbeitslosenquote - Unemployment rate (by gender, age groups)
    - SGB II Leistungsempfänger - Social benefit recipients

## Recommended Database Tables

### Priority 1: Core Tables

1. **`ref_electoral_district`** (from shapefiles)
   - Primary key: `wahlkreis_nr` (1-299)
   - Columns: `wahlkreis_nr`, `wahlkreis_name`, `land_nr`, `land_name`, `election_year`, `geom`
   - Geometry: Polygon (SRID 3035)
   - Indexes: Spatial index on `geom`, index on `wahlkreis_nr`, `election_year`

2. **`fact_election_structural_data`** (from CSV files)
   - Primary key: `(wahlkreis_nr, election_year)`
   - Columns: All socioeconomic indicators from CSV
   - Foreign key: `wahlkreis_nr` → `ref_electoral_district.wahlkreis_nr`

### Table Schema Example

```sql
-- Electoral districts reference table
CREATE TABLE zensus.ref_electoral_district (
    wahlkreis_nr INTEGER NOT NULL,
    wahlkreis_name TEXT NOT NULL,
    land_nr TEXT NOT NULL,
    land_name TEXT NOT NULL,
    election_year INTEGER NOT NULL,
    geom GEOMETRY(POLYGON, 3035) NOT NULL,
    CONSTRAINT pk_electoral_district PRIMARY KEY (wahlkreis_nr, election_year),
    CONSTRAINT chk_wahlkreis_nr CHECK (wahlkreis_nr BETWEEN 1 AND 299),
    CONSTRAINT chk_election_year CHECK (election_year IN (2013, 2021, 2025))
);

CREATE INDEX idx_electoral_district_geom ON zensus.ref_electoral_district USING GIST (geom);
CREATE INDEX idx_electoral_district_wkr_nr ON zensus.ref_electoral_district (wahlkreis_nr);
CREATE INDEX idx_electoral_district_year ON zensus.ref_electoral_district (election_year);

-- Structural data fact table
CREATE TABLE zensus.fact_election_structural_data (
    wahlkreis_nr INTEGER NOT NULL,
    election_year INTEGER NOT NULL,
    -- Demographics
    gemeinden_anzahl INTEGER,
    flaeche_km2 NUMERIC,
    bevoelkerung_insgesamt_1000 NUMERIC,
    bevoelkerung_deutsche_1000 NUMERIC,
    bevoelkerung_auslaender_pct NUMERIC,
    bevoelkerungsdichte NUMERIC,
    -- Age structure
    alter_unter_18_pct NUMERIC,
    alter_18_24_pct NUMERIC,
    alter_25_34_pct NUMERIC,
    alter_35_59_pct NUMERIC,
    alter_60_74_pct NUMERIC,
    alter_75_plus_pct NUMERIC,
    -- Housing
    wohnungen_fertiggestellt_je_1000ew NUMERIC,
    wohnungen_bestand_je_1000ew NUMERIC,
    wohnflaeche_je_wohnung NUMERIC,
    wohnflaeche_je_ew NUMERIC,
    -- Economy
    einkommen_verfuegbar_eur_je_ew NUMERIC,
    bip_eur_je_ew NUMERIC,
    -- Employment
    beschaeftigte_insgesamt_je_1000ew NUMERIC,
    arbeitslosenquote_pct NUMERIC,
    -- ... (add all other columns from CSV)
    CONSTRAINT pk_election_structural_data PRIMARY KEY (wahlkreis_nr, election_year),
    CONSTRAINT fk_election_structural_data_district 
        FOREIGN KEY (wahlkreis_nr, election_year) 
        REFERENCES zensus.ref_electoral_district(wahlkreis_nr, election_year)
);
```

## Integration with Zensus Data

You can join electoral district data with Zensus grid data using:

1. **Spatial Join**: 
   ```sql
   SELECT 
       ed.wahlkreis_nr,
       ed.wahlkreis_name,
       COUNT(*) as grid_cells,
       SUM(f.einwohner) as total_population
   FROM zensus.ref_electoral_district ed
   JOIN zensus.ref_grid_1km g ON ST_Intersects(ed.geom, g.geom)
   JOIN zensus.fact_zensus_1km_bevoelkerungszahl f ON g.grid_id = f.grid_id
   WHERE ed.election_year = 2025
   GROUP BY ed.wahlkreis_nr, ed.wahlkreis_name
   ```

2. **Aggregation**: Aggregate Zensus statistics by electoral district for analysis

3. **Comparison**: Compare Zensus data with election structural data to identify correlations

## Data Quality Notes

- **Electoral District Boundaries**: Boundaries may change between elections due to population shifts
- **Data Sources**: CSV data comes from various sources (Bundesagentur für Arbeit, statistical offices)
- **Temporal Alignment**: CSV data dates vary (e.g., 2023 population data for 2025 election)
- **Coordinate System**: All shapefiles need reprojection from EPSG:25832 to EPSG:3035
- **CSV Encoding**: Files use UTF-8 with BOM, require `utf-8-sig` encoding when reading

## Next Steps

1. Create load script similar to `etl/load_grids.py` for electoral district shapefiles
2. Create CSV parser that handles multi-row headers and BOM encoding
3. Define database schemas for both reference and fact tables
4. Load data with automatic CRS reprojection (25832 → 3035)
5. Create spatial indexes for efficient joins with Zensus grid data
6. Add foreign key relationships between tables

