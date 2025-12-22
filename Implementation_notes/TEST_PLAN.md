# ETL Pipeline Test Plan

## Data Analysis Summary

### Data Characteristics Observed:
1. **CSV Files:**
   - Semicolon-delimited (`;`)
   - UTF-8 encoding (no BOM detected)
   - Missing values: `–` (em-dash, Unicode U+2013)
   - Decimal format: `"50,00"` (comma separator)
   - Some files have `werterlaeuternde_Zeichen` column with values like `"KLAMMERN"`
   - Grid ID format: `CRS3035RES1000mN2689000E4337000`
   - File sizes: ~214K rows for 1km, ~3.8K rows for 10km

2. **GPKG Files:**
   - 100m: 12GB (very large, needs chunked processing)
   - 1km: 125MB
   - 10km: 1.3MB
   - CRS: Should be EPSG:3035 (ETRS89-LAEA)
   - Column names: Unknown (needs verification)

3. **Data Patterns:**
   - Integer columns: Counts (Einwohner, Anzahl, etc.)
   - Numeric columns: Percentages, averages (contain comma decimals)
   - Coordinate columns: `x_mp_{size}`, `y_mp_{size}`

## Test Plan

### Phase 1: Data Structure Validation

#### Test 1.1: GPKG File Structure
**Goal:** Verify GPKG files can be read and identify grid_id column

**Steps:**
1. Read each GPKG file (100m, 1km, 10km) with `geopandas`
2. Check available columns
3. Verify CRS is EPSG:3035 (or can be reprojected)
4. Identify grid_id column name
5. Check geometry types (should be Polygon)

**Expected Issues:**
- Unknown column name for grid_id (needs to be identified)
- Possible CRS mismatch (needs reprojection)
- MultiPolygon geometries (needs conversion)

**Validation:**
```bash
python3 -c "
import geopandas as gpd
gdf = gpd.read_file('data/geo_data/DE_Grid_ETRS89-LAEA_1km.gpkg', rows=10)
print('Columns:', list(gdf.columns))
print('CRS:', gdf.crs)
print('Sample grid_id:', gdf.iloc[0] if len(gdf) > 0 else 'N/A')
"
```

#### Test 1.2: CSV File Structure
**Goal:** Verify all CSV files can be read correctly

**Steps:**
1. Read sample rows from each CSV category
2. Verify semicolon delimiter works
3. Check for em-dash missing values
4. Verify decimal comma format
5. Check column name variations

**Validation:**
- All files readable with `sep=';'`
- Em-dash characters detected correctly
- Decimal commas (`50,00`) present in numeric columns

### Phase 2: Preprocessing Validation

#### Test 2.1: Decimal Conversion
**Goal:** Verify `normalize_decimal()` handles German format

**Test Cases:**
- `"50,00"` → `50.0`
- `"129,1"` → `129.1`
- `"–"` → `None`
- `""` → `None`

#### Test 2.2: Integer Conversion
**Goal:** Verify `normalize_integer()` doesn't truncate decimals

**Test Cases:**
- `"129"` → `129` ✓
- `"129,1"` → `None` ✓ (not an integer, should return None)
- `"–"` → `None` ✓

#### Test 2.3: Column Type Detection
**Goal:** Verify integer vs numeric detection based on decimal commas

**Test Cases:**
- Column with `"50,00"` → detected as NUMERIC ✓
- Column with only `"129"` → detected as INTEGER ✓
- Column with mix → detected based on presence of commas

### Phase 3: ETL Pipeline Validation

#### Test 3.1: Grid Loading (`load_grids.py`)
**Critical Checks:**
1. ✅ Grid ID column detection (logs available columns)
2. ✅ CRS handling (reproject to 3035 if needed)
3. ✅ Geometry validation (fix invalid geometries)
4. ✅ MultiPolygon → Polygon conversion
5. ⚠️ **ISSUE**: Large 100m file (12GB) - needs chunked reading, not just chunked inserts

**Potential Issues:**
- `gpd.read_file()` loads entire file into memory (12GB is too large)
- Need to use `rows` parameter or chunked reading for 100m file

#### Test 3.2: Zensus Loading (`load_zensus.py`)
**Critical Checks:**
1. ✅ Table name detection from path
2. ✅ Grid size detection (100m, 1km, 10km)
3. ✅ Column mapping and sanitization
4. ✅ Integer vs numeric detection
5. ✅ Grid ID validation (if enabled)
6. ✅ Chunked inserts
7. ⚠️ **ISSUE**: Column order in CSV might not match table schema

**Potential Issues:**
- Column order mismatch between CSV and generated table
- Missing columns in table (if CSV has new columns)
- Extra columns in table (if CSV missing columns)

#### Test 3.3: Schema Generation
**Critical Checks:**
1. ✅ All datasets have corresponding tables
2. ✅ Column names match (after sanitization)
3. ✅ Data types correct (INTEGER vs NUMERIC)
4. ⚠️ **ISSUE**: Column order in generated SQL might not match CSV order

### Phase 4: Integration Tests

#### Test 4.1: End-to-End Load Test
**Steps:**
1. Start database (Docker)
2. Load 10km grid (smallest, fastest)
3. Load one 10km CSV file
4. Verify data in database:
   - Row count matches
   - Grid IDs match
   - Data types correct
   - Missing values are NULL

#### Test 4.2: Data Quality Checks
**Steps:**
1. Check for orphaned grid_ids (fact table grid_ids not in ref table)
2. Verify no invalid geometries
3. Check SRID is 3035
4. Verify constraints (year = 2022, etc.)

## Identified Issues & Recommendations

### Critical Issues:

1. **100m GPKG File Size (12GB)**
   - **Problem**: `gpd.read_file()` loads entire file into memory
   - **Solution**: Use chunked reading or `rows` parameter
   - **Impact**: Will fail on systems with <16GB RAM

2. **Column Order Mismatch**
   - **Problem**: Generated table columns might not match CSV column order
   - **Solution**: Use explicit column mapping in INSERT statement (already done ✓)
   - **Status**: Already handled correctly

3. **GPKG Column Name Unknown**
   - **Problem**: Don't know actual grid_id column name in GPKG files
   - **Solution**: Test script will identify it
   - **Impact**: Script will fail if column not found (but logs available columns)

### Medium Priority:

4. **Schema Regeneration**
   - **Problem**: If CSV structure changes, schema needs regeneration
   - **Solution**: Document that `generate_schema.py` should be run
   - **Status**: Documented in schema file comments

5. **Error Handling**
   - **Status**: Good - has chunked error handling, individual row fallback
   - **Recommendation**: Add retry logic for transient database errors

### Low Priority:

6. **Performance Optimization**
   - Large files might benefit from parallel processing
   - Consider using `COPY` instead of `INSERT` for bulk loads
   - Current chunked approach is acceptable

## Test Execution

Run the test script:
```bash
source venv/bin/activate
python scripts/test_etl_pipeline.py
```

This will:
1. Test CSV reading
2. Test GPKG structure (identify column names)
3. Test preprocessing functions
4. Test column type detection
5. Test table mapping
6. Test schema generation

## Next Steps After Testing

1. **Fix GPKG column detection** if column name differs from expected
2. **Fix 100m file loading** if memory issues occur
3. **Verify schema matches** actual CSV columns
4. **Run full load** on small subset (10km data)
5. **Validate data quality** using SQL checks

