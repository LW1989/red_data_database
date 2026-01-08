# Database Tables Documentation

This document provides an overview of the meaningful tables in the `red-data-db` database that are actively used for analysis.

**Generated:** 2026-01-05

---

## Schema: `zensus`

The zensus schema contains all German Census 2022 data including reference grids and fact tables.

### 📍 Reference Tables (Geometry)

#### `zensus.ref_lwu_properties`

- **Status:** ✅ (5,468 rows)
- **Description:** Properties owned by Berlin state-owned housing companies (LWU)
- **Usage:** Primary analysis target - calculate statistics for each LWU property

**Columns:**
- `property_id` (TEXT, PRIMARY KEY) - Cleaned property identifier (lwu_fls.{number})
- `original_id` (TEXT) - Original ID from source data with padding
- `geom` (GEOMETRY, MULTIPOLYGON, EPSG:3035) - Property boundaries
- `created_at` (TIMESTAMP) - Record creation timestamp

---

#### `zensus.ref_grid_10km`

- **Status:** ✅ (1,339 rows)
- **Description:** 10km × 10km reference grid (ETRS89-LAEA)
- **Usage:** Coarse-level spatial aggregation

**Columns:**
- `grid_id` (TEXT, PRIMARY KEY) - Grid cell identifier (CRS3035RES10000m...)
- `geom` (GEOMETRY, POLYGON, EPSG:3035) - Grid cell geometry

---

#### `zensus.ref_grid_1km`

- **Status:** ✅ (133,398 rows)
- **Description:** 1km × 1km reference grid (ETRS89-LAEA)
- **Usage:** Medium-level spatial aggregation

**Columns:**
- `grid_id` (TEXT, PRIMARY KEY) - Grid cell identifier (CRS3035RES1000m...)
- `geom` (GEOMETRY, POLYGON, EPSG:3035) - Grid cell geometry

---

#### `zensus.ref_grid_100m`

- **Status:** ✅ (38,287,676 rows)
- **Description:** 100m × 100m reference grid (ETRS89-LAEA)
- **Usage:** **Primary grid for detailed analysis** - intersect with LWU properties

**Columns:**
- `grid_id` (TEXT, PRIMARY KEY) - Grid cell identifier (CRS3035RES100m...)
- `geom` (GEOMETRY, POLYGON, EPSG:3035) - Grid cell geometry

---

### 📊 Fact Tables - 100m Grid (Primary Data Source)

#### `zensus.fact_zensus_100m_durchschnittliche_nettokaltmiete_und_anzahl_der_wohnungen`

- **Status:** ✅ (2,827,842 rows)
- **Description:** **Average rent per m² and number of flats**
- **Usage:** ✅ **ACTIVELY USED** - Calculate weighted average rent for LWU properties
- **Coverage:** 99.2% of LWU properties

**Columns:**
- `grid_id` (TEXT, PRIMARY KEY) - Links to ref_grid_100m
- `year` (INTEGER) - Census year (2022)
- `durchschnmieteqm` (DOUBLE PRECISION) - Average rent per m² (€/m²)
- `anzahlwohnungen` (INTEGER) - Number of flats
- `x_mp_100m`, `y_mp_100m` (DOUBLE PRECISION) - Grid cell center coordinates

---

#### `zensus.fact_zensus_100m_heizungsart`

- **Status:** ✅ (2,628,942 rows)
- **Description:** **Heating type distribution**
- **Usage:** ✅ **ACTIVELY USED** - Calculate heating type proportions for LWU properties
- **Coverage:** 55.4% of LWU properties

**Columns:**
- `grid_id` (TEXT, PRIMARY KEY)
- `year` (INTEGER) - Census year (2022)
- `insgesamt_heizungsart` (INTEGER) - Total count
- `fernheizung` (DOUBLE PRECISION) - District heating
- `etagenheizung` (DOUBLE PRECISION) - Floor heating
- `blockheizung` (DOUBLE PRECISION) - Block heating
- `zentralheizung` (DOUBLE PRECISION) - Central heating
- `einzel_mehrraumoefen` (DOUBLE PRECISION) - Single/multi-room stoves
- `keine_heizung` (DOUBLE PRECISION) - No heating
- `x_mp_100m`, `y_mp_100m` (DOUBLE PRECISION)

**⚠️ Data Quality Note:** Categories may not sum to total due to Zensus privacy protection (rounding/noise injection)

---

#### `zensus.fact_zensus_100m_energietraeger`

- **Status:** ✅ (2,628,942 rows)
- **Description:** **Energy source distribution**
- **Usage:** ✅ **ACTIVELY USED** - Calculate energy source proportions for LWU properties
- **Coverage:** 60.9% of LWU properties

**Columns:**
- `grid_id` (TEXT, PRIMARY KEY)
- `year` (INTEGER) - Census year (2022)
- `insgesamt_energietraeger` (INTEGER) - Total count
- `gas` (DOUBLE PRECISION) - Natural gas
- `heizoel` (DOUBLE PRECISION) - Heating oil
- `holz_holzpellets` (DOUBLE PRECISION) - Wood/pellets
- `biomasse_biogas` (DOUBLE PRECISION) - Biomass/biogas
- `solar_geothermie_waermepumpen` (DOUBLE PRECISION) - Solar/geothermal/heat pumps
- `strom` (DOUBLE PRECISION) - Electricity
- `kohle` (DOUBLE PRECISION) - Coal
- `fernwaerme` (DOUBLE PRECISION) - District heating
- `kein_energietraeger` (DOUBLE PRECISION) - No energy source
- `x_mp_100m`, `y_mp_100m` (DOUBLE PRECISION)

**⚠️ Data Quality Note:** Categories may not sum to total due to Zensus privacy protection

---

#### `zensus.fact_zensus_100m_gebaeude_nach_baujahr_in_mikrozensus_klassen`

- **Status:** ✅ (2,371,676 rows)
- **Description:** **Building construction year distribution**
- **Usage:** ✅ **ACTIVELY USED** - Calculate construction year proportions for LWU properties
- **Coverage:** 35.7% of LWU properties (⚠️ limited coverage)

**Columns:**
- `grid_id` (TEXT, PRIMARY KEY)
- `year` (INTEGER) - Census year (2022)
- `insgesamt_gebaeude` (INTEGER) - Total buildings
- `vor1919` (DOUBLE PRECISION) - Before 1919
- `a1919bis1948` (DOUBLE PRECISION) - 1919-1948
- `a1949bis1978` (DOUBLE PRECISION) - 1949-1978
- `a1979bis1990` (DOUBLE PRECISION) - 1979-1990
- `a1991bis2000` (DOUBLE PRECISION) - 1991-2000
- `a2001bis2010` (DOUBLE PRECISION) - 2001-2010
- `a2011bis2019` (DOUBLE PRECISION) - 2011-2019
- `a2020undspaeter` (DOUBLE PRECISION) - 2020 and later
- `x_mp_100m`, `y_mp_100m` (DOUBLE PRECISION)

**⚠️ Data Quality Note:** Categories may not sum to total due to Zensus privacy protection. Lower coverage compared to other metrics.

---

### 📊 Additional Fact Tables (100m Grid)

The following tables are available but not currently used in active analysis:

- `fact_zensus_100m_alter_5altersklassen` - Age distribution (5 classes)
- `fact_zensus_100m_alter_infr` - Age infrastructure groups
- `fact_zensus_100m_bevoelkerungszahl` - Population count
- `fact_zensus_100m_familienstand` - Marital status
- `fact_zensus_100m_gebaeude_nach_zahl_der_wohnungen` - Buildings by number of flats
- `fact_zensus_100m_geschlecht` - Gender distribution
- `fact_zensus_100m_haushaltstyp_nach_kindern` - Household types by children
- `fact_zensus_100m_staatsangehoerigkeit` - Nationality
- `fact_zensus_100m_typ_der_kernfamilie_nach_kindern` - Core family types
- `fact_zensus_100m_wohnungen_nach_anzahl_raeume` - Flats by number of rooms
- `fact_zensus_100m_wohnungen_nach_eigentumsverhaeltnisse` - Flats by ownership
- `fact_zensus_100m_wohnungen_nach_haushaltsgrösse` - Flats by household size
- And more...

These tables follow the same structure as the actively used tables and can be integrated into future analyses as needed.

---

### 📊 Fact Tables - 10km and 1km Grids

All fact tables are also available at 10km and 1km grid levels:
- `fact_zensus_10km_*` - Coarse-level data
- `fact_zensus_1km_*` - Medium-level data

These can be used for:
- Regional analysis
- Performance optimization (smaller datasets)
- Multi-scale analysis

---

## Data Quality & Limitations

### Known Issues with Zensus Data

1. **Categories Don't Sum to Totals**
   - **Cause:** Statistical disclosure control (privacy protection)
   - **Mechanism:** Independent rounding, noise injection, cell suppression
   - **Impact:** Proportions typically sum to 90-95% instead of 100%
   - **Affected:** ALL heating, energy, and construction year tables (100% of rows)

2. **Variable Data Coverage**
   - **Rent:** 99.2% coverage ✅
   - **Heating:** 55.4% coverage ⚠️
   - **Energy:** 60.9% coverage ⚠️
   - **Construction Year:** 35.7% coverage ⚠️⚠️

3. **Grid-Based Approximation**
   - LWU properties span multiple 100m grid cells
   - Characteristics assigned based on weighted overlap
   - Not precise building-level data

### Recommendations

- **Use rent data with confidence** - excellent coverage and quality
- **Treat heating/energy as directional indicators** - good for comparisons, not absolute values
- **Use construction year data carefully** - limited coverage
- **Focus on relative comparisons** - e.g., "Property A has more district heating than Property B"

---

## Usage Examples

### Load Tables into GeoPandas/Pandas

See: `notebooks/load_data.ipynb`

```python
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine

# Load LWU properties
lwu_properties = gpd.read_postgis(
    "SELECT * FROM zensus.ref_lwu_properties",
    engine, geom_col='geom'
)

# Load rent data for intersecting grids
rent_data = pd.read_sql("""
    SELECT r.*
    FROM zensus.fact_zensus_100m_durchschnittliche_nettokaltmiete_und_anzahl_der_wohnungen r
    WHERE EXISTS (
        SELECT 1 FROM zensus.ref_lwu_properties l
        INNER JOIN zensus.ref_grid_100m g ON ST_Intersects(l.geom, g.geom)
        WHERE r.grid_id = g.grid_id
    )
""", engine)
```

### Calculate Weighted Statistics

See: `notebooks/lwu_berlin_analysis.ipynb`

The analysis notebook calculates weighted averages for each LWU property by:
1. Finding intersecting 100m grid cells
2. Calculating overlap ratios
3. Using number of flats/buildings as weights
4. Computing weighted means/proportions

Results: `lwu_berlin_weighted_analysis.csv` (5,468 properties × 26 columns)

---

## Schema: `analytics`

The analytics schema contains derived data and calculated statistics. This separates raw census data (in `zensus`) from business-ready analytics.

### 📊 Fact Tables

#### `analytics.fact_lwu_weighted_stats`

- **Status:** ✅ (5,468 rows)
- **Description:** Weighted demographic statistics for LWU properties calculated from 100m grid intersections
- **Usage:** Analysis and reporting of LWU property characteristics

**Columns:**
- `property_id` (TEXT, PRIMARY KEY) - Links to zensus.ref_lwu_properties
- `weighted_avg_rent_per_sqm` (DOUBLE PRECISION) - Average rent (€/m²)
- `rent_total_flats` (DOUBLE PRECISION) - Weighted flat count for confidence assessment
- `heating_*_pct` (DOUBLE PRECISION) - Heating type proportions (6 types)
- `heating_total_buildings` (DOUBLE PRECISION) - Weighted building count
- `energy_*_pct` (DOUBLE PRECISION) - Energy source proportions (9 types)
- `energy_total_buildings` (DOUBLE PRECISION) - Weighted building count
- `baujahr_*_pct` (DOUBLE PRECISION) - Construction year proportions (8 periods)
- `baujahr_total_buildings` (DOUBLE PRECISION) - Weighted building count
- `created_at` (TIMESTAMP) - Calculation timestamp

**Key Notes:**
- Proportions stored as decimals (0.0 to 1.0, multiply by 100 for %)
- All proportions sum to 100% (by design)
- Higher `*_total_buildings` or `rent_total_flats` = more confident estimate

---

### 👁️ Views

#### `analytics.view_lwu_stats_geo`

- **Status:** ✅ (5,468 rows)
- **Description:** LWU statistics joined with property geometries for mapping
- **Usage:** GIS applications, map visualizations, spatial analysis

**Columns:**
- All columns from `fact_lwu_weighted_stats`
- `geom` (GEOMETRY, MULTIPOLYGON, EPSG:3035) - Property boundaries from zensus.ref_lwu_properties

**Usage Example:**
```python
import geopandas as gpd
gdf = gpd.read_postgis(
    "SELECT * FROM analytics.view_lwu_stats_geo",
    engine, geom_col='geom'
)
gdf.plot(column='weighted_avg_rent_per_sqm', legend=True)
```

---

## Schema: `housing`

The housing schema contains real estate rental listing data from external sources with geocoded locations. This provides market-level rental data complementing the census aggregated statistics.

### 🏠 Fact Tables

#### `housing.properties`

- **Status:** ✅ (~15,000 rows, updated daily)
- **Description:** **Real estate rental listings with geocoded locations**
- **Usage:** Market analysis, rental price tracking, property availability monitoring
- **Source:** External housing scraper database (daily sync)
- **Coverage:** Germany-wide rental properties (apartments and houses only, parking spaces excluded)

**Columns:**

**Property Identifiers:**
- `internal_id` (TEXT, PRIMARY KEY) - Unique property identifier from source
- `company` (TEXT) - Property management company/listing source

**Address Components:**
- `strasse_normalized` (TEXT) - Normalized street name
- `hausnummer` (TEXT) - House number
- `plz` (TEXT) - Postal code
- `ort` (TEXT) - City/municipality name

**Property Characteristics:**
- `preis` (NUMERIC) - Monthly rent in EUR
- `groesse` (NUMERIC) - Size in m²
- `anzahl_zimmer` (NUMERIC) - Number of rooms
- `eur_per_m2` (NUMERIC) - Rent per m² (EUR/m²)
- `immo_type_scraped` (TEXT) - Property type (wohnung, haus, etc.)

**Geocoding Data:**
- `latitude` (DOUBLE PRECISION) - Latitude (WGS84)
- `longitude` (DOUBLE PRECISION) - Longitude (WGS84)
- `geom` (GEOMETRY, POINT, EPSG:4326) - PostGIS point geometry for spatial queries
- `geocoding_status` (TEXT) - Status: 'success', 'failed', or 'pending'
- `geocoded_address` (TEXT) - Full address string used for geocoding
- `last_geocoded_at` (TIMESTAMP) - Last geocoding attempt timestamp

**Temporal Tracking:**
- `date_scraped` (TIMESTAMP) - When data was scraped from source
- `first_seen` (TIMESTAMP) - First time property appeared in source
- `last_seen` (TIMESTAMP) - Last time property was active in source
- `created_at` (TIMESTAMP) - Record creation in source database
- `updated_at` (TIMESTAMP) - Last update in source database
- `synced_at` (TIMESTAMP) - Last sync to local database

**Indexes:**
- PRIMARY KEY on `internal_id`
- GIST index on `geom` (spatial queries)
- B-tree index on `geocoding_status` (filter queries)

**Data Quality:**
- **Geocoding Success Rate:** 99.4% (14,910/15,000)
- **Failed Geocoding:** 90 properties (0.6%)
  - 32 have insufficient address data
  - 58 addresses not in OpenStreetMap database
- **Excluded:** Parking spaces (Stellplätze) and garages are automatically filtered out

**⚠️ Data Notes:**
- Properties are synced daily at 5:00 AM (incremental sync)
- Only apartments and houses are included (parking/garages excluded)
- Geocoding uses Nominatim API with German address optimization
- Failed geocoding may indicate data quality issues or very new streets

---

#### `housing.geocoding_cache`

- **Status:** ✅ (Auto-managed)
- **Description:** Cache for geocoding API results to reduce API calls
- **Usage:** Automatic - used by sync script to avoid redundant geocoding

**Columns:**
- `id` (SERIAL, PRIMARY KEY) - Auto-incrementing ID
- `address_hash` (TEXT, UNIQUE) - MD5 hash of normalized address
- `original_address` (TEXT) - Full address string
- `latitude` (DOUBLE PRECISION) - Cached latitude
- `longitude` (DOUBLE PRECISION) - Cached longitude
- `quality` (NUMERIC) - Quality score
- `display_name` (TEXT) - Full display name from geocoder
- `created_at` (TIMESTAMP) - Cache entry creation time
- `used_count` (INTEGER) - Number of times cache was hit

**Performance:**
- Reduces API calls by ~90% after initial sync
- Speeds up daily incremental syncs significantly
- Automatically populated during geocoding

---

### 📊 Usage Examples

#### Query Properties with Spatial Filters

```sql
-- Find properties within 1km of a specific location
SELECT 
    internal_id,
    strasse_normalized || ' ' || hausnummer AS address,
    plz || ' ' || ort AS city,
    preis,
    eur_per_m2,
    groesse,
    anzahl_zimmer
FROM housing.properties
WHERE geocoding_status = 'success'
  AND ST_DWithin(
      geom::geography,
      ST_SetSRID(ST_MakePoint(13.4050, 52.5200), 4326)::geography,  -- Berlin center
      1000  -- 1000 meters
  )
ORDER BY eur_per_m2;
```

#### Average Rent Analysis by City

```sql
-- Calculate average rent statistics by city
SELECT 
    ort AS city,
    COUNT(*) AS property_count,
    ROUND(AVG(preis)::numeric, 2) AS avg_rent_total,
    ROUND(AVG(eur_per_m2)::numeric, 2) AS avg_rent_per_sqm,
    ROUND(AVG(groesse)::numeric, 2) AS avg_size_sqm,
    ROUND(AVG(anzahl_zimmer)::numeric, 2) AS avg_rooms
FROM housing.properties
WHERE geocoding_status = 'success'
  AND preis IS NOT NULL
  AND groesse IS NOT NULL
GROUP BY ort
HAVING COUNT(*) >= 10  -- Only cities with 10+ properties
ORDER BY property_count DESC;
```

#### Load into GeoPandas

```python
import geopandas as gpd
from sqlalchemy import create_engine

engine = create_engine('postgresql://user:pass@host:port/red-data-db')

# Load all geocoded properties
properties = gpd.read_postgis(
    """
    SELECT 
        internal_id,
        strasse_normalized || ' ' || hausnummer AS address,
        ort AS city,
        plz,
        preis,
        eur_per_m2,
        groesse,
        anzahl_zimmer,
        geom
    FROM housing.properties
    WHERE geocoding_status = 'success'
    """,
    engine,
    geom_col='geom'
)

# Plot rent per m²
properties.plot(column='eur_per_m2', legend=True, cmap='YlOrRd')
```

#### Geocoding Success Rate

```sql
-- Check geocoding quality
SELECT 
    geocoding_status,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM housing.properties
GROUP BY geocoding_status
ORDER BY count DESC;
```

---

## Maintenance & Updates

### Housing Data Sync

- **Automation:** Daily at 5:00 AM (cron job)
- **Mode:** Incremental (only new/updated records)
- **Script:** `etl/sync_housing_data.py`
- **Logs:** `/app/red_data_database/logs/housing_sync.log`

**Manual Operations:**
```bash
# Daily incremental sync
python etl/sync_housing_data.py

# Full re-sync (all records)
python etl/sync_housing_data.py --full

# Retry failed geocoding
python scripts/retry_failed_geocoding.py

# Run tests
python scripts/test_housing_sync.py

# Quality checks
psql -f tests/sql/housing_quality_checks.sql
```

**Documentation:**
- **User Guide:** `HOUSING_DATA_SYNC_GUIDE.md` - Setup and usage
- **Implementation:** `IMPLEMENTATION_SUMMARY_HOUSING_SYNC.md` - Technical details
- **Schema:** `docker/init/07_housing_data_schema.sql` - Database schema

---

## Files & Resources

- **Connection:** `notebooks/database_connection.ipynb` - Database connection examples
- **Calculation:** `analysis/lwu_statistics/calculate_lwu_weighted_stats.py` - Calculate LWU statistics
- **Guide:** `analysis/lwu_statistics/LWU_STATISTICS_GUIDE.md` - Detailed documentation
- **Housing Sync:** `HOUSING_DATA_SYNC_GUIDE.md` - Housing data synchronization guide

---

*For questions or issues, refer to the project README or analysis guides.*
