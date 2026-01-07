# LWU Property Statistics - Guide

This guide explains how to calculate and use weighted demographic statistics for LWU (Landeseigene Wohnungen) properties in Berlin.

---

## Overview

The `calculate_lwu_weighted_stats.py` script calculates weighted demographic statistics for 5,468 LWU properties by spatially intersecting them with 100m zensus grid cells. Each property may span multiple grid cells, so we use weighted averages to properly combine the data.

### Calculated Metrics

1. **Durchschnittsmiete** (Average rent per m²)
2. **Heizungsart** (Heating types: Fernheizung, Etagenheizung, etc.)
3. **Energieträger** (Energy sources: Gas, Öl, etc.)
4. **Baujahr** (Construction year distributions)

---

## How Weighted Averages Work

### Example: Property Spanning 2 Grid Cells

A property intersects with two 100m × 100m grid cells:

**Grid A:**
- Overlap: 3% of grid (33 m²)
- Flats: 94
- Rent: €9.64/m²

**Grid B:**
- Overlap: 5% of grid (501 m²)
- Flats: 111
- Rent: €9.11/m²

### Calculation Steps

1. **Calculate weight for each grid:**
   - Weight_A = 0.03 × 94 = 2.82 (equivalent flats)
   - Weight_B = 0.05 × 111 = 5.55 (equivalent flats)

2. **Calculate weighted rent:**
   - Weighted_rent_A = 2.82 × €9.64 = €27.18
   - Weighted_rent_B = 5.55 × €9.11 = €50.56

3. **Calculate final average:**
   - Total weighted rent = €27.18 + €50.56 = €77.74
   - Total weight = 2.82 + 5.55 = 8.37
   - **Average = €77.74 / 8.37 = €9.29/m²**

This gives more weight to Grid B (larger overlap + more flats), which is correct.

### Formula

```
weighted_avg = Σ(overlap_ratio × density × value) / Σ(overlap_ratio × density)
```

Where:
- `overlap_ratio` = how much of the property overlaps with grid cell
- `density` = number of flats/buildings in grid cell
- `value` = rent or category proportion

---

## Usage

### Run the Calculation

```bash
python etl/calculate_lwu_weighted_stats.py
```

**Outputs:**
- `lwu_weighted_stats_YYYY-MM-DD.csv` (5,468 properties × 30 columns)
- 9 intermediate CSV files for inspection/debugging

### Insert into Database

```bash
python analysis/lwu_statistics/insert_lwu_weighted_stats_to_db.py lwu_weighted_stats_YYYY-MM-DD.csv
```

Creates table: `analytics.fact_lwu_weighted_stats`

### Query the Data

```sql
-- Get properties with high rent
SELECT property_id, weighted_avg_rent_per_sqm
FROM analytics.fact_lwu_weighted_stats
WHERE weighted_avg_rent_per_sqm > 10.0
ORDER BY weighted_avg_rent_per_sqm DESC;

-- Average heating type distribution
SELECT 
    ROUND(AVG(heating_fernheizung_pct) * 100, 1) as fernheizung_pct,
    ROUND(AVG(heating_zentralheizung_pct) * 100, 1) as zentralheizung_pct
FROM analytics.fact_lwu_weighted_stats
WHERE heating_total_buildings > 0;

-- Query with geometry for mapping
SELECT property_id, weighted_avg_rent_per_sqm, geom
FROM analytics.view_lwu_stats_geo
WHERE weighted_avg_rent_per_sqm > 8;
```

### For Mapping (GeoPandas)

```python
import geopandas as gpd
from sqlalchemy import create_engine

engine = create_engine('postgresql://...')

# Load data with geometry
gdf = gpd.read_postgis(
    """SELECT * FROM analytics.view_lwu_stats_geo 
       WHERE weighted_avg_rent_per_sqm IS NOT NULL""",
    engine,
    geom_col='geom'
)

# Create a map
gdf.plot(column='weighted_avg_rent_per_sqm', legend=True)
```

---

## Intermediate Files

The script saves 9 intermediate CSV files showing the calculation steps:

1. `intermediate_spatial_intersections_*.csv` - Property-grid overlaps
2. `intermediate_rent_data_*.csv` - Raw zensus rent data
3. `intermediate_rent_merged_*.csv` - Rent with weights calculated
4. `intermediate_heating_data_*.csv` - Raw heating data
5. `intermediate_heating_merged_*.csv` - Heating with weights
6. `intermediate_energy_data_*.csv` - Raw energy data
7. `intermediate_energy_merged_*.csv` - Energy with weights
8. `intermediate_baujahr_data_*.csv` - Raw construction year data
9. `intermediate_baujahr_merged_*.csv` - Construction year with weights

### Disable Intermediate Files

```python
from etl.calculate_lwu_weighted_stats import LWUWeightedStatsCalculator

calculator = LWUWeightedStatsCalculator(save_intermediates=False)
calculator.calculate_all_statistics()
calculator.export_to_csv()
```

---

## Output Schema

### Database Structure

**Schema:** `analytics` (for derived/calculated data)  
**Table:** `analytics.fact_lwu_weighted_stats` (statistics without geometry)  
**View:** `analytics.view_lwu_stats_geo` (statistics WITH geometry for mapping)

### Columns

**Rent:**
- `weighted_avg_rent_per_sqm` - Average rent (€/m²)
- `rent_total_flats` - Total weighted flats (for confidence assessment)

**Heating (6 types):**
- `heating_fernheizung_pct` - District heating proportion
- `heating_etagenheizung_pct` - Floor heating
- `heating_blockheizung_pct` - Block heating
- `heating_zentralheizung_pct` - Central heating
- `heating_einzel_mehrraumoefen_pct` - Stoves
- `heating_keine_heizung_pct` - No heating
- `heating_total_buildings` - Total weighted buildings

**Energy (9 sources):**
- `energy_gas_pct`, `energy_heizoel_pct`, `energy_holz_holzpellets_pct`, etc.
- `energy_total_buildings` - Total weighted buildings

**Construction Year (8 periods):**
- `baujahr_vor1919_pct`, `baujahr_1919bis1948_pct`, etc.
- `baujahr_total_buildings` - Total weighted buildings

**Metadata:**
- `created_at` - Calculation timestamp

### Data Types
- Proportions are stored as decimals (0.0 to 1.0)
- Multiply by 100 to get percentages

---

## Data Quality Notes

### Coverage
- Rent: 99.2% (5,423/5,468 properties)
- Heating: 99.8% (5,457/5,468 properties)
- Energy: 99.7% (5,454/5,468 properties)
- Construction Year: 97.8% (5,345/5,468 properties)

### Proportion Sums
All category proportions sum to exactly 100% because we calculate our own totals from non-NULL categories rather than using the official `insgesamt_*` columns (which contain privacy protection noise).

### Low Weights
Properties with `rent_total_flats < 1.0` have unreliable estimates due to:
- Very small overlap with grid cells
- Few flats in the overlapping areas
- Consider these less confident

---

## Key Implementation Details

### Why Calculate Own Totals?

The zensus `insgesamt_*` columns contain privacy protection noise (rounding, noise injection). By calculating our own totals from category values, we ensure:
- Internal consistency (proportions sum to 100%)
- No artificial gaps from privacy noise
- More accurate proportions

### Weighted Average Formula

For rent:
```python
weight = overlap_ratio × anzahlwohnungen
weighted_rent = weight × durchschnmieteqm
final_rent = Σ(weighted_rent) / Σ(weight)
```

For proportions:
```python
weight = overlap_ratio × calculated_total
weighted_category = overlap_ratio × category_value
category_pct = Σ(weighted_category) / Σ(weight)
```

Both are mathematically equivalent to standard weighted averages.

---

## Troubleshooting

### Properties with NULL values
- Property doesn't intersect any grid cells with data
- Check `intermediate_spatial_intersections_*.csv` to see if property has any grid overlaps

### Proportions don't sum to 100%
- This would only happen if there are NULL categories in the source data
- Our calculation method guarantees 100% sums when all categories are included

### Verifying calculations
1. Open `intermediate_rent_merged_*.csv`
2. Filter for a property_id
3. Sum the `weighted_rent` and `weight` columns
4. Divide: `sum(weighted_rent) / sum(weight)`
5. Compare with final CSV

---

## References

- **Source data:** Zensus 2022 (100m grid cells)
- **Property data:** LWU Berlin (Landeseigene Wohnungen)
- **Coordinate system:** EPSG:3035 (ETRS89-LAEA)
- **Scripts:** `analysis/lwu_statistics/calculate_lwu_weighted_stats.py`
- **Database table:** `analytics.fact_lwu_weighted_stats`
- **Database view (with geometry):** `analytics.view_lwu_stats_geo`

For database schema details, see [`DATABASE_TABLES_DOCUMENTATION.md`](DATABASE_TABLES_DOCUMENTATION.md).

