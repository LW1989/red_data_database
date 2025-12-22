# VG250 Administrative Boundaries - Database Table Analysis

## Overview
The VG250 dataset contains official German administrative boundaries from the Bundesamt für Kartographie und Geodäsie (BKG). All data is in **EPSG:25832** (ETRS89 / UTM Zone 32N) and needs to be reprojected to **EPSG:3035** to match your database.

**Data Validity Date**: 01.01.2025 (as per `aktualitaet.txt`)

## Documentation

The dataset includes comprehensive documentation in the `dokumentation/` folder:

- **`vg250.pdf`** / **`vg250_eng.pdf`** (915-918 KB): Main documentation in German/English
- **`verwaltungsgliederung_vg.pdf`** (432 KB): Administrative structure documentation
- **`datenquellen_vg_nuts.pdf`** (128 KB): Data sources and NUTS codes reference
- **`anlagen_vg.pdf`** / **`annex_vg.pdf`** (629-636 KB): Annexes and appendices
- **`nutzungsbedingungen_vg250.pdf`** / **`nutzungsbedingungen_vg250_eng.pdf`** (67-68 KB): Terms of use
- **`aktualitaet.txt`**: Validity date (01.01.2025)

**Note**: The main documentation PDFs contain detailed information about:
- Column definitions and data dictionary
- Administrative hierarchy and relationships
- NUTS code mappings
- Data quality and update procedures
- Coordinate system specifications

## Available Layers

### 1. **VG250_STA** - States/Countries
- **Features**: 11
- **Geometry**: MultiPolygon
- **Purpose**: National boundaries (Germany and neighboring countries)
- **Key Columns**:
  - `ARS`: Official Regional Key
  - `AGS`: Official Municipality Key
  - `GEN`: Name (e.g., "Deutschland", "Polen")
  - `NUTS`: NUTS code
  - `LKZ`: State code
- **Suggested Table**: `ref_country` or `ref_state_boundary`

### 2. **VG250_LAN** - Federal States (Länder)
- **Features**: 34 (16 German states + historical/administrative variants)
- **Geometry**: MultiPolygon
- **Purpose**: German federal state boundaries
- **Key Columns**:
  - `ARS`: Official Regional Key (e.g., "01" for Schleswig-Holstein)
  - `AGS`: Official Municipality Key
  - `GEN`: State name (e.g., "Schleswig-Holstein", "Bayern")
  - `NUTS`: NUTS code (e.g., "DEF" for Schleswig-Holstein)
  - `LKZ`: State code (e.g., "SH", "BY")
- **Suggested Table**: `ref_federal_state` or `ref_land`

### 3. **VG250_RBZ** - Government Districts (Regierungsbezirke)
- **Features**: 21
- **Geometry**: Polygon
- **Purpose**: Administrative districts within states (only some states have these)
- **Key Columns**:
  - `ARS`: Official Regional Key
  - `GEN`: District name
  - `NUTS`: NUTS code
- **Suggested Table**: `ref_government_district` or `ref_regierungsbezirk`

### 4. **VG250_KRS** - Counties (Kreise)
- **Features**: 433
- **Geometry**: Polygon
- **Purpose**: County-level administrative boundaries (Kreise and kreisfreie Städte)
- **Key Columns**:
  - `ARS`: Official Regional Key (e.g., "01001" for Flensburg)
  - `AGS`: Official Municipality Key
  - `GEN`: County name (e.g., "Flensburg", "München")
  - `BEZ`: Type (e.g., "Kreisfreie Stadt", "Landkreis")
  - `NUTS`: NUTS code
  - `LKZ`: State code
- **Suggested Table**: `ref_county` or `ref_kreis`
- **Note**: This is very useful for joining with Zensus data at county level

### 5. **VG250_VWG** - Administrative Communities (Verwaltungsgemeinschaften)
- **Features**: 4,680
- **Geometry**: Polygon
- **Purpose**: Administrative communities (groups of municipalities)
- **Key Columns**:
  - `ARS`: Official Regional Key
  - `GEN`: Community name
- **Suggested Table**: `ref_admin_community` or `ref_verwaltungsgemeinschaft`

### 6. **VG250_GEM** - Municipalities (Gemeinden)
- **Features**: 11,103
- **Geometry**: Polygon
- **Purpose**: Municipal-level boundaries (smallest administrative unit)
- **Key Columns**:
  - `ARS`: Official Regional Key (12 digits, e.g., "010010000000")
  - `AGS`: Official Municipality Key (8 digits, e.g., "01001000")
  - `GEN`: Municipality name (e.g., "Flensburg", "Berlin")
  - `BEZ`: Type (e.g., "Stadt", "Gemeinde")
  - `NUTS`: NUTS code
  - `LKZ`: State code
- **Suggested Table**: `ref_municipality` or `ref_gemeinde`
- **Note**: This is the most detailed level and can be joined with Zensus grid data

### 7. **VG250_PK** - Postal Codes (Postleitzahlen)
- **Features**: 10,949
- **Geometry**: Point
- **Purpose**: Postal code locations (centroids)
- **Key Columns**:
  - `ARS`: Official Regional Key
  - `GEN`: Postal code area name
  - `LON_DEZ`: Longitude (decimal degrees)
  - `LAT_DEZ`: Latitude (decimal degrees)
  - `OTL`: Place name
- **Suggested Table**: `ref_postal_code` or `ref_postleitzahl`
- **Note**: Point geometry, not polygons

### 8. **VG250_LI** - Administrative Boundaries (Lines)
- **Features**: 35,456
- **Geometry**: LineString
- **Purpose**: Boundary lines between administrative units
- **Key Columns**:
  - `AGZ`: Administrative boundary type
  - `RDG`: Boundary classification
- **Suggested Table**: `ref_boundary_line` or `ref_grenzlinie`
- **Note**: Less useful for typical analysis, mainly for cartography

## Common Column Definitions

All polygon layers share these key columns (see `vg250.pdf` for complete documentation):

- **`OBJID`**: Unique object identifier (BKG internal ID)
- **`BEGINN`**: Validity start date (when this administrative unit became valid)
- **`ARS`**: Amtlicher Regionalschlüssel (Official Regional Key) - hierarchical 12-digit code
  - Structure: `LLRRKKVVVGGG` where:
    - `LL` = State (Land)
    - `RR` = Government District (Regierungsbezirk, 00 if none)
    - `KK` = County (Kreis)
    - `VVV` = Administrative Community (Verwaltungsgemeinschaft, 000 if none)
    - `GGG` = Municipality (Gemeinde, 000 if none)
- **`AGS`**: Amtlicher Gemeindeschlüssel (Official Municipality Key) - 8-digit code
  - Structure: `LLRRKKGG` (first 8 digits of ARS)
- **`GEN`**: Name (Gemeindename) - official name of the administrative unit
- **`BEZ`**: Type/Designation (Bezeichnung) - e.g., "Stadt", "Gemeinde", "Landkreis", "Kreisfreie Stadt"
- **`NUTS`**: NUTS code (European statistical regions classification)
  - Format: `DEF` (country) → `DEF0X` (state) → `DEF0XX` (county level)
- **`LKZ`**: Landkreis code (State abbreviation) - e.g., "SH", "BY", "BE"
- **`IBZ`**: Internal classification code (BKG internal classification)
- **`WSK`**: Last update date (Wirkungsdatum)
- **`ADE`**: Administrative level code
  - `2` = Federal State (Land)
  - `4` = County (Kreis)
  - `6` = Municipality (Gemeinde)
- **`GF`**: Geometry type code (typically `4` for polygons)
- **`BSG`**: Boundary status code (typically `1` for active boundaries)
- **`IBZ`**: Internal classification code (BKG internal classification)
  - Examples: `20-23` for states, `40-42` for counties, `60-64` for municipalities
- **`NBD`**: "ja" if unit has no boundaries (e.g., city-states like Berlin, Hamburg)
- **`SDV_ARS`**: Standardized ARS (same as ARS for most cases)
- **`DLM_ID`**: Digital Landscape Model identifier (BKG internal reference)

## Recommended Tables for Your Database

Based on your Zensus data structure, I recommend creating these reference tables:

### Priority 1 (Most Useful):
1. **`ref_municipality`** (VG250_GEM) - Join with Zensus grid cells
2. **`ref_county`** (VG250_KRS) - Aggregate Zensus data by county
3. **`ref_federal_state`** (VG250_LAN) - Aggregate Zensus data by state

### Priority 2 (Useful for Analysis):
4. **`ref_postal_code`** (VG250_PK) - Spatial joins with postal codes
5. **`ref_government_district`** (VG250_RBZ) - Regional analysis

### Priority 3 (Less Critical):
6. **`ref_admin_community`** (VG250_VWG) - Detailed administrative grouping
7. **`ref_country`** (VG250_STA) - National boundaries
8. **`ref_boundary_line`** (VG250_LI) - Boundary visualization

## Coordinate System Conversion

**Current**: EPSG:25832 (ETRS89 / UTM Zone 32N)  
**Target**: EPSG:3035 (ETRS89-LAEA) - matches your Zensus grid data

The load script should automatically reproject from 25832 to 3035.

## Integration with Zensus Data

You can join administrative boundaries with Zensus data using:

1. **Spatial Join**: `ST_Intersects(zensus.ref_grid_1km.geom, ref_municipality.geom)`
   - Most flexible method - works regardless of whether Zensus data has administrative codes
   - Can be computationally expensive for large datasets
   - Use spatial indexes for performance

2. **ARS/AGS Codes**: If Zensus data includes municipality codes, direct joins
   - Fastest method if codes are available
   - Requires Zensus data to include administrative unit identifiers

3. **Aggregation**: Group Zensus statistics by administrative units
   - Example: `SUM(einwohner) GROUP BY municipality_id`
   - Useful for creating summary statistics at county/state level

## Administrative Hierarchy

The VG250 data follows a hierarchical structure:

```
Country (STA)
  └── Federal State (LAN) - e.g., "Schleswig-Holstein"
      └── Government District (RBZ) - e.g., "Kiel" (only in some states)
          └── County (KRS) - e.g., "Flensburg" (Kreisfreie Stadt) or "Kreis Plön"
              └── Administrative Community (VWG) - optional grouping
                  └── Municipality (GEM) - e.g., "Flensburg"
```

**Key Relationships**:
- Each municipality (`GEM`) belongs to exactly one county (`KRS`)
- Each county belongs to one federal state (`LAN`)
- Some states have government districts (`RBZ`) between state and county level
- ARS codes encode this hierarchy: `LLRRKKVVVGGG`

## Data Quality Notes

- **Validity Dates**: The `BEGINN` column indicates when an administrative unit became valid
- **Historical Data**: Some layers may contain multiple entries for the same unit with different validity periods
- **Boundary Changes**: Administrative boundaries change over time (municipality mergers, etc.)
- **Coordinate System**: All data is in EPSG:25832 and must be reprojected to EPSG:3035 for your database

## Next Steps

1. Create a load script similar to `etl/load_grids.py` for VG250 data
2. Define table schemas for each administrative level
3. Load data with automatic CRS reprojection (25832 → 3035)
4. Create spatial indexes for efficient joins
5. Add foreign key relationships if applicable

