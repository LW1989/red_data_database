# Database Architecture and ETL Pipeline: Detailed Explanation

## Introduction

This document explains the database architecture and ETL (Extract, Transform, Load) pipeline built for the German Zensus 2022 data. As a data scientist, you're familiar with databases, but this document explains the **data engineering** aspects: how we structure data for efficient storage and querying, how we handle data quality issues, and why we made specific design decisions.

---

## 1. Overall Architecture: Star Schema Design

### What is a Star Schema?

We use a **star schema** (also called a dimensional model), which is a common pattern in data warehousing. Think of it like this:

- **Reference tables (dimension tables)**: Store the "things" you want to analyze - in our case, the grid cell geometries
- **Fact tables**: Store the "measurements" or "observations" - in our case, the census statistics

### Why This Design?

**Problem**: We have two types of data:
1. **Geographic data** (GPKG files): Polygon geometries for grid cells (100m, 1km, 10km resolution)
2. **Statistical data** (CSV files): Census statistics (population, age groups, housing, etc.) for those same grid cells

**Challenge**: We could store everything in one table per dataset, but that would:
- Duplicate geometry data (wasteful - geometries are large)
- Make it hard to join different statistics for the same grid cell
- Make spatial queries slower

**Solution**: Star schema separates concerns:
- **Reference tables** (`ref_grid_1km`, `ref_grid_10km`, `ref_grid_100m`): Store each grid cell's geometry **once**
- **Fact tables** (`fact_zensus_1km_*`, etc.): Store statistics, linked via `grid_id` foreign key

### The "Star" Visualization

```
                    ref_grid_1km (geometry)
                           |
                           | grid_id
                           |
        ┌──────────────────┼──────────────────┐
        |                  |                  |
fact_zensus_1km_    fact_zensus_1km_    fact_zensus_1km_
bevoelkerungszahl    durchschnittsalter  auslaenderanteil
   (population)         (avg_age)         (foreigner_%)
```

All fact tables reference the same grid table via `grid_id`. This allows you to:
- Join multiple statistics for the same grid cell
- Query spatial relationships efficiently (PostGIS uses the geometry index)
- Avoid duplicating geometry data

---

## 2. Database Setup: Docker and PostgreSQL

### Why Docker?

Docker containerizes the database, making it:
- **Reproducible**: Same setup on any machine
- **Isolated**: Doesn't interfere with other PostgreSQL installations
- **Easy to reset**: Delete container and start fresh
- **Portable**: Works on Mac, Linux, Windows

### What's in the Docker Container?

**PostgreSQL 15** with **PostGIS extension**:
- PostgreSQL: The database engine
- PostGIS: Adds spatial data types (GEOMETRY) and spatial functions (ST_Intersects, ST_Area, etc.)

### Database Initialization

When the Docker container starts, it automatically runs SQL scripts in `docker/init/`:

1. **`01_extensions.sql`**: Enables PostGIS extension
2. **`02_schema.sql`**: Creates all tables (reference + fact tables)
3. **`03_indexes.sql`**: Creates indexes for performance

This is a **data engineering best practice**: Infrastructure as Code. The database schema is defined in version-controlled SQL files, not manually created.

---

## 3. Data Preprocessing: Handling German Data Format

### The Problem

German data uses different conventions than English:
- **Decimal separator**: Comma (`,`) instead of dot (`.`)
  - Example: `"129,1"` means 129.1
- **Missing values**: Em-dash (`–`, Unicode U+2013) instead of empty or NULL
- **CSV delimiter**: Semicolon (`;`) instead of comma (`,`)

### The Solution: Normalization Functions

We created two functions in `etl/utils.py`:

#### `normalize_decimal(value)`
Converts German decimal format to Python float:
- `"129,1"` → `129.1`
- `"50,00"` → `50.0`
- `"–"` → `None` (NULL in database)

**Why this matters**: If we don't convert, PostgreSQL will reject `"129,1"` as invalid numeric input.

#### `normalize_integer(value)`
Converts integer strings, but **rejects** decimals:
- `"129"` → `129`
- `"129,1"` → `None` (not an integer!)

**Why separate functions?**: We need to distinguish between integer columns (counts) and numeric columns (percentages, averages). The ETL pipeline automatically detects which columns contain decimals and applies the correct function.

### Column Type Detection

**Challenge**: How do we know if a column should be INTEGER or NUMERIC?

**Solution**: We inspect the actual data values, not column names:
```python
# Read sample values from the column
sample_values = df[col].dropna().astype(str).head(100)
# If column contains "129,1" (comma + digits), it's NUMERIC
# If column contains only "129" (no comma), it's INTEGER
has_decimal_comma = sample_values.str.contains(r',\d+', regex=True).any()
```

This is **data-driven schema detection** - we don't rely on column names (which might be inconsistent or misleading), we look at the actual data values. This same logic is used in both:
- The ETL pipeline (`etl/load_zensus.py`) - for runtime type detection
- The schema generation script (`scripts/generate_schema.py`) - for CREATE TABLE statements

**Why this matters**: Column names can be misleading. A column named "Anzahl" (count) might actually contain decimal values in some datasets. By inspecting the data, we ensure accurate type detection.

---

## 4. ETL Pipeline: Extract, Transform, Load

### What is ETL?

- **Extract**: Read data from source files (GPKG, CSV)
- **Transform**: Clean, normalize, validate data
- **Load**: Insert into database

### Component 1: Loading Grid Geometries (`etl/load_grids.py`)

**Purpose**: Load polygon geometries from GPKG files into reference tables.

**Key Steps**:

1. **Read GPKG file** using GeoPandas
   ```python
   gdf = gpd.read_file(gpkg_path)
   ```

2. **Handle Coordinate Reference System (CRS)**
   - Check if CRS is EPSG:3035 (ETRS89-LAEA, the standard for European INSPIRE data)
   - If not, reproject: `gdf.to_crs(epsg=3035)`
   - **Why**: All spatial data must use the same CRS for spatial queries to work

3. **Construct grid_id from coordinates**
   - **Problem**: GPKG files use format `"1kmN2684E4334"`, but CSV files use `"CRS3035RES1000mN2689000E4337000"`
   - **Solution**: We construct the CSV format from GPKG coordinates:
     ```python
     grid_id = f"CRS3035RES{size_str}N{int(y_mp)}E{int(x_mp)}"
     ```
   - **Why**: We need consistent `grid_id` format to join grid and census data

4. **Validate and fix geometries**
   - Check for invalid geometries: `gdf.geometry.is_valid`
   - Fix invalid ones: `geom.buffer(0)` (common PostGIS trick)
   - Convert MultiPolygon to Polygon (if needed)

5. **Chunked inserts**
   - Insert in batches of 10,000 rows (configurable)
   - **Why**: Prevents memory issues and allows progress tracking

### Component 2: Loading Census Data (`etl/load_zensus.py`)

**Purpose**: Load CSV statistics into fact tables.

**Key Steps**:

1. **Detect table name from file path**
   - Path: `data/zensus_data/Durchschnittsalter_in_Gitterzellen/Zensus2022_Durchschnittsalter_1km-Gitter.csv`
   - Extracts: `folder_name = "Durchschnittsalter_in_Gitterzellen"`, `grid_size = "1km"`
   - Generates: `table_name = "fact_zensus_1km_durchschnittsalter_in_gitterzellen"`
   - **Why**: Dynamic table mapping - we don't hardcode table names for 40+ datasets

2. **Read CSV with correct parameters**
   ```python
   df = pd.read_csv(csv_path, sep=';', encoding='utf-8', on_bad_lines='skip')
   ```
   - `sep=';'`: German CSV uses semicolon
   - `encoding='utf-8'`: Handles German characters (ä, ö, ü) and em-dash
   - `on_bad_lines='skip'`: Gracefully handle malformed rows

3. **Sanitize column names**
   - Convert to lowercase, replace special characters with underscores
   - Example: `"Anteil Ausländer ab 18"` → `"anteil_auslaender_ab_18"`
   - **Why**: PostgreSQL identifiers must be lowercase and can't contain spaces

4. **Detect integer vs numeric columns**
   - Scan data for decimal commas (see Section 3)
   - Apply `normalize_integer()` or `normalize_decimal()` accordingly

5. **Preprocess data**
   - Apply normalization functions to all columns
   - Convert em-dash to NULL
   - Add `year = 2022` column

6. **Validate grid_ids (optional)**
   - Check that each `grid_id` exists in reference table
   - Remove rows with invalid `grid_id`
   - **Why**: Data quality - ensures referential integrity

7. **Chunked inserts with conflict handling**
   ```sql
   INSERT INTO zensus.fact_zensus_1km_... (grid_id, ...)
   VALUES (...)
   ON CONFLICT (grid_id) DO UPDATE SET ...
   ```
   - `ON CONFLICT`: If `grid_id` already exists, update instead of error
   - **Why**: Allows re-running ETL scripts safely (idempotent)

### Component 3: Utilities (`etl/utils.py`)

**Database connection**:
- Reads credentials from `.env` file (environment variables)
- Creates SQLAlchemy engine (Python's standard database interface)
- **Why `.env` file**: Keeps credentials out of code (security best practice)

**Logging**:
- Logs to both file (`etl.log`) and console
- **Why**: Debugging ETL issues requires detailed logs

---

## 5. Schema Generation: Automating Table Creation

### The Challenge

We have **40+ different census datasets**, each with different columns. Manually writing CREATE TABLE statements would be:
- Error-prone
- Time-consuming
- Hard to maintain when CSV structure changes

### The Solution: `scripts/generate_schema.py`

This script:
1. Scans all CSV files in `data/zensus_data/`
2. Reads column headers **and sample data values** (first 100 rows)
3. Determines data types (INTEGER vs NUMERIC) by **inspecting actual data values** - checks for decimal commas (German format: "129,1")
4. Generates CREATE TABLE SQL statements

**Key improvement**: Data types are determined by inspecting the data itself, not column names. This matches the logic used in the ETL pipeline and ensures accurate type detection even if column names are inconsistent or misleading.

**Example output**:
```sql
CREATE TABLE IF NOT EXISTS zensus.fact_zensus_1km_durchschnittsalter (
    grid_id TEXT PRIMARY KEY,
    year INTEGER NOT NULL DEFAULT 2022,
    durchschnittsalter NUMERIC,
    x_mp_1km NUMERIC,
    y_mp_1km NUMERIC,
    CONSTRAINT fk_grid_1km FOREIGN KEY (grid_id) REFERENCES zensus.ref_grid_1km(grid_id)
);
```

**When to run**: When CSV file structure changes (new columns, renamed columns).

---

## 6. Design Decisions and Trade-offs

### Decision 1: Star Schema vs. Flat Tables

**Star Schema (chosen)**:
- ✅ No geometry duplication
- ✅ Easy to join multiple statistics
- ✅ Efficient spatial queries (geometry index on reference table)
- ❌ More complex (requires joins)

**Flat Tables (alternative)**:
- ✅ Simpler (one table per dataset)
- ❌ Duplicates geometry data (wasteful)
- ❌ Harder to combine statistics

**Why we chose star schema**: The benefits outweigh the complexity, especially for spatial queries.

### Decision 2: Separate Tables per Grid Size vs. Single Table

**Separate tables (chosen)**:
- `ref_grid_100m`, `ref_grid_1km`, `ref_grid_10km`
- `fact_zensus_1km_*`, `fact_zensus_10km_*`, etc.

**Why**:
- Different grid sizes have different row counts (100m has millions, 10km has thousands)
- Queries are simpler (no need to filter by grid_size)
- Indexes are more efficient (smaller tables = faster index scans)

**Alternative**: Single table with `grid_size` column
- ❌ Would require filtering in every query
- ❌ Less efficient indexes

### Decision 3: Chunked Inserts vs. Bulk Insert

**Chunked inserts (chosen)**:
- Insert 10,000 rows at a time
- ✅ Progress tracking (see "Inserted chunk X/Y")
- ✅ Error recovery (if one chunk fails, others continue)
- ✅ Memory efficient

**Bulk insert (alternative)**:
- Insert all rows at once
- ❌ No progress feedback
- ❌ All-or-nothing (one error fails entire load)
- ❌ Memory intensive for large files

### Decision 4: Data Type Detection: Heuristic vs. Schema File

**Heuristic detection (chosen)**:
- Inspect data values for decimal commas
- ✅ Works automatically for new datasets
- ✅ Handles data inconsistencies
- ❌ Might misclassify edge cases

**Schema file (alternative)**:
- Manually specify column types in config file
- ✅ Explicit control
- ❌ Requires maintenance when data changes
- ❌ Doesn't scale to 40+ datasets

**Why we chose heuristic**: Automation and scalability.

### Decision 5: Grid ID Validation: Optional vs. Required

**Optional validation (chosen)**:
- Can skip with `--no-validate` flag
- ✅ Faster loading (skips database lookups)
- ✅ Useful for initial loads where some grid_ids might be missing
- ⚠️ Risk of orphaned rows (grid_id not in reference table)

**Why optional**: Flexibility - validate when needed, skip for speed.

---

## 7. Security and Best Practices

### SQL Injection Prevention

**Problem**: User-provided file paths could contain malicious SQL if we concatenated strings.

**Solution**: Parameterized queries
```python
# ❌ BAD (SQL injection risk)
query = f"SELECT * FROM {table_name} WHERE grid_id = '{user_input}'"

# ✅ GOOD (parameterized)
query = text("SELECT * FROM zensus.table WHERE grid_id = :grid_id")
conn.execute(query, {'grid_id': user_input})
```

**Table/column name sanitization**:
- All table and column names are sanitized (lowercase, underscores only)
- Validated against known patterns before use

### Error Handling

- **Graceful degradation**: If chunk insert fails, try individual rows
- **Logging**: All errors logged to `etl.log` for debugging
- **Transaction safety**: Each chunk is a transaction (rollback on error)

### Data Quality

- **Geometry validation**: Invalid geometries are fixed automatically
- **Referential integrity**: Foreign key constraints ensure `grid_id` exists
- **Type checking**: Constraints ensure `year = 2022` (data quality)

---

## 8. Performance Optimizations

### Indexes

**GiST indexes on geometry columns**:
```sql
CREATE INDEX idx_ref_grid_1km_geom ON zensus.ref_grid_1km USING GIST (geom);
```
- **Why**: Spatial queries (ST_Intersects, ST_Within) are much faster with GiST indexes
- **What is GiST**: Generalized Search Tree - optimized for spatial data

**B-tree indexes on grid_id**:
- Primary keys automatically have indexes
- Foreign keys benefit from indexes for joins

**B-tree indexes on year**:
- For filtering by year (though all data is 2022 currently)

### Chunked Processing

- Prevents memory exhaustion on large files
- Allows progress tracking
- Enables error recovery

### Connection Pooling

SQLAlchemy uses connection pooling by default:
- Reuses database connections (faster than creating new ones)
- `pool_pre_ping=True`: Verifies connections before use (handles stale connections)

---

## 9. Common Data Engineering Patterns Used

### 1. **Idempotent ETL**
- Running the same ETL script twice produces the same result
- Achieved via `ON CONFLICT DO UPDATE`
- **Why**: Allows safe re-runs if something fails mid-process

### 2. **Schema-on-Read vs. Schema-on-Write**
- **Schema-on-Write (chosen)**: Define schema before loading (CREATE TABLE)
- **Why**: Better data quality, type safety, query performance
- **Alternative**: Schema-on-Read (load raw data, infer types later) - less control

### 3. **Separation of Concerns**
- Reference data (geometries) separate from fact data (statistics)
- ETL scripts separate from database setup
- **Why**: Easier to maintain, test, and modify

### 4. **Configuration via Environment Variables**
- Database credentials in `.env` file
- **Why**: Security (not in code), flexibility (different configs for dev/prod)

### 5. **Logging and Observability**
- Detailed logs for debugging
- Progress tracking during long-running loads
- **Why**: ETL pipelines run for hours - need visibility into progress

---

## 10. How to Use This System

### Typical Workflow

1. **Start database**:
   ```bash
   docker-compose up -d
   ```

2. **Load grid geometries** (one-time):
   ```bash
   python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_1km.gpkg 1km
   ```

3. **Load census data**:
   ```bash
   python etl/load_zensus.py data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_1km-Gitter.csv
   ```

4. **Query data**:
   ```sql
   -- Join grid geometry with population statistics
   SELECT 
       g.grid_id,
       g.geom,
       f.einwohner
   FROM zensus.ref_grid_1km g
   JOIN zensus.fact_zensus_1km_bevoelkerungszahl f ON g.grid_id = f.grid_id
   WHERE f.einwohner > 1000;
   ```

### When to Regenerate Schema

Run `scripts/generate_schema.py` if:
- CSV files get new columns
- Column names change
- New datasets are added

Then update `docker/init/02_schema.sql` with the output.

---

## 11. Troubleshooting Common Issues

### Issue: "Out of memory" loading 100m grid

**Cause**: 100m GPKG file is 12GB - too large for available RAM.

**Solution**: 
- Use a machine with 16GB+ RAM
- Or implement chunked reading (read GPKG in chunks, not implemented yet)

### Issue: "Invalid geometry" errors

**Cause**: Some geometries in GPKG files are invalid (self-intersecting, etc.).

**Solution**: Already handled - we automatically fix with `buffer(0)`.

### Issue: "Grid ID not found" warnings

**Cause**: CSV has `grid_id` that doesn't exist in reference table.

**Possible reasons**:
- Grid geometries not loaded yet
- Different geographic coverage (some CSV cells might not have geometries)
- Grid ID format mismatch

**Solution**: Check logs, verify grid_id format matches.

### Issue: "Column type mismatch" errors

**Cause**: Schema says INTEGER but data has decimals.

**Solution**: Regenerate schema using `generate_schema.py` (it detects types from data).

---

## 12. Summary: Key Takeaways

1. **Star schema** separates reference data (geometries) from fact data (statistics) for efficiency and flexibility.

2. **Data preprocessing** handles German format (comma decimals, em-dash missing values) automatically.

3. **Dynamic schema generation** scales to 40+ datasets without manual table definitions.

4. **Chunked processing** enables loading large files with progress tracking and error recovery.

5. **Docker** provides reproducible, isolated database environment.

6. **PostGIS** enables spatial queries (intersections, area calculations, etc.).

7. **Best practices**: Parameterized queries (SQL injection prevention), logging, error handling, idempotent ETL.

This architecture is designed to be **maintainable**, **scalable**, and **robust** - key principles in data engineering.

---

## Further Reading

- **Star Schema**: [Kimball Group Dimensional Modeling](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/)
- **PostGIS**: [PostGIS Documentation](https://postgis.net/documentation/)
- **ETL Best Practices**: [Data Engineering Cookbook](https://github.com/andkret/Cookbook)

