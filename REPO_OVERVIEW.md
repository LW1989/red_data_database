# Repository Overview: PostGIS Zensus Database

## What is This Repository?

This repository contains a **PostgreSQL + PostGIS database system** for storing and analyzing German census (Zensus) data from 2022. The database uses a **star schema design** to efficiently store spatial geometries and statistical data, enabling complex spatial queries and data analysis.

## Core Purpose

The database stores:
- **Spatial grid geometries**: INSPIRE grid cells at 1km and 10km resolution (EPSG:3035)
- **Census statistics**: 40+ datasets covering demographics, housing, employment, and more
- **Administrative boundaries**: Municipalities, counties, and federal states (VG250 data)
- **Election data**: Electoral district boundaries and structural data (Bundestagswahlen)

## Key Technologies

- **PostgreSQL 15**: Relational database
- **PostGIS**: Spatial extension for geometry storage and spatial queries
- **Docker**: Containerized database for easy setup and deployment
- **Python 3.8+**: ETL scripts for data loading and preprocessing
- **SQLAlchemy**: Python ORM for database interactions

## Repository Structure

```
red_data_database/
├── docker/
│   └── init/                    # Database initialization scripts
│       ├── 01_extensions.sql    # PostGIS extension setup
│       ├── 02_schema.sql        # Table definitions (reference + fact tables)
│       └── 03_indexes.sql       # Indexes for performance
│
├── etl/                         # Extract, Transform, Load scripts
│   ├── load_grids.py            # Loads grid geometries from GPKG files
│   ├── load_zensus.py           # Loads census statistics from CSV files
│   └── utils.py                 # Shared utilities (normalization, DB connection)
│
├── scripts/
│   ├── generate_schema.py       # Auto-generates SQL schemas from CSV files
│   ├── backup.sh                # Database backup script
│   ├── restore.sh               # Database restore script
│   └── reorganize_zensus_data.py # Data organization utilities
│
├── data/                        # Data files (not in git)
│   ├── geo_data/                # GPKG files with grid geometries
│   └── zensus_data/             # CSV files with census statistics
│       ├── 10km/                # 10km resolution data
│       ├── 1km/                 # 1km resolution data
│       └── descriptions/        # Excel files with data descriptions
│
├── tests/                       # Testing infrastructure
│   ├── dbt/                     # dbt test configuration
│   └── sql/                     # Manual quality check queries
│
├── Implementation_notes/        # Documentation and analysis files
│   ├── ARCHITECTURE_EXPLANATION.md    # Detailed architecture explanation
│   ├── VG250_ANALYSIS.md             # VG250 administrative boundaries analysis
│   ├── BUNDESTAGSWAHLEN_ANALYSIS.md  # Election data analysis
│   ├── IMPLEMENTATION_NOTE_NEW_TABLES.md # Implementation guide for new tables
│   └── TEST_*.md                      # Test documentation
│
├── docker-compose.yml           # Docker configuration
├── requirements.txt             # Python dependencies
├── README.md                    # User-facing documentation
└── REPO_OVERVIEW.md            # This file (for developers/agents)
```

## Database Architecture

### Star Schema Design

The database uses a **star schema** (dimensional model):

- **Reference Tables** (dimension tables): Store geometries once
  - `ref_grid_1km`, `ref_grid_10km`, `ref_grid_100m`: Grid cell polygons
  - `ref_municipality`, `ref_county`, `ref_federal_state`: Administrative boundaries
  - `ref_electoral_district`: Electoral district boundaries

- **Fact Tables**: Store statistics, linked via `grid_id`
  - `fact_zensus_1km_*`, `fact_zensus_10km_*`: Census statistics per grid cell
  - `fact_election_structural_data`: Socioeconomic data per electoral district

### Key Design Decisions

1. **Separation of geometry and statistics**: Avoids duplicating large geometry data
2. **Grid-based organization**: All data tied to INSPIRE grid cells via `grid_id`
3. **Multiple resolutions**: 1km and 10km grids for different analysis needs
4. **Spatial indexing**: GIST indexes on all geometry columns for fast spatial queries

## Data Flow

### 1. Grid Geometry Loading (`etl/load_grids.py`)
- Reads GPKG files from `data/geo_data/`
- Reprojects to EPSG:3035 if needed
- Constructs `grid_id` from coordinates
- Inserts into `ref_grid_*` tables

### 2. Schema Generation (`scripts/generate_schema.py`)
- Scans CSV files in `data/zensus_data/{grid_size}/`
- Inspects data to determine column types (INTEGER vs NUMERIC)
- Generates SQL `CREATE TABLE` statements
- Handles German data format (decimal commas, em-dash missing values)

### 3. Census Data Loading (`etl/load_zensus.py`)
- Reads CSV files (semicolon-delimited, UTF-8)
- Preprocesses data:
  - Converts German decimal format (`"129,1"` → `129.1`)
  - Handles em-dash missing values (`"–"` → `NULL`)
  - Reconstructs `grid_id` from coordinates
- Validates `grid_id` exists in reference tables
- Inserts into appropriate `fact_zensus_*` tables

## Key Features

### Data Preprocessing
- **German number format**: Handles comma decimals (`normalize_decimal()`)
- **Missing values**: Converts em-dash (`–`) to NULL
- **Type detection**: Data-driven schema generation (checks for decimal commas)
- **Column sanitization**: Converts column names to valid PostgreSQL identifiers

### Spatial Operations
- All geometries in EPSG:3035 (ETRS89-LAEA)
- Spatial joins: `ST_Intersects()`, `ST_Within()`, etc.
- Spatial aggregation: Aggregate grid data by administrative boundaries

### Data Quality
- Grid ID validation before insertion
- Geometry validation (`ST_IsValid()`)
- SRID validation (must be 3035)
- dbt tests for data quality checks

## Common Tasks

### Adding New Data

1. **New census dataset**:
   - Place CSV in `data/zensus_data/{grid_size}/`
   - Run `scripts/generate_schema.py` to generate schema
   - Apply schema: `psql < schema_{grid_size}.sql`
   - Load data: `python etl/load_zensus.py data/zensus_data/{grid_size}/file.csv`

2. **New grid resolution**:
   - Add GPKG file to `data/geo_data/`
   - Update `docker/init/02_schema.sql` to add `ref_grid_{size}` table
   - Load: `python etl/load_grids.py --gpkg data/geo_data/DE_Grid_{size}.gpkg --grid-size {size}`

3. **New administrative boundaries**:
   - See `Implementation_notes/IMPLEMENTATION_NOTE_NEW_TABLES.md`
   - Create load script similar to `etl/load_grids.py`
   - Reproject from EPSG:25832 to EPSG:3035

### Querying Data

```sql
-- Aggregate census data by municipality
SELECT 
    m.name as municipality,
    SUM(f.einwohner) as total_population
FROM zensus.ref_municipality m
JOIN zensus.ref_grid_1km g ON ST_Intersects(m.geom, g.geom)
JOIN zensus.fact_zensus_1km_bevoelkerungszahl f ON g.grid_id = f.grid_id
GROUP BY m.name;

-- Spatial join with electoral districts
SELECT 
    ed.wahlkreis_nr,
    ed.wahlkreis_name,
    COUNT(g.grid_id) as grid_cells,
    SUM(f.einwohner) as population
FROM zensus.ref_electoral_district ed
JOIN zensus.ref_grid_1km g ON ST_Intersects(ed.geom, g.geom)
JOIN zensus.fact_zensus_1km_bevoelkerungszahl f ON g.grid_id = f.grid_id
WHERE ed.election_year = 2025
GROUP BY ed.wahlkreis_nr, ed.wahlkreis_name;
```

## Development Workflow

### Local Development
1. Start database: `docker-compose up -d`
2. Load grid geometries: `python etl/load_grids.py ...`
3. Generate schemas: `python scripts/generate_schema.py ...`
4. Load census data: `python etl/load_zensus.py ...`
5. Query data: Connect with `psql` or Python

### Testing
- Run dbt tests: `dbt test` (from `tests/dbt/` directory)
- Manual quality checks: `tests/sql/quality_checks.sql`
- ETL pipeline tests: `python scripts/test_etl_pipeline.py`

## Important Files to Understand

1. **`etl/utils.py`**: Core utilities
   - `normalize_decimal()`: German decimal format conversion
   - `normalize_integer()`: Integer conversion with validation
   - `get_db_engine()`: Database connection
   - `preprocess_zensus_dataframe()`: Data preprocessing pipeline

2. **`etl/load_zensus.py`**: Main ETL script
   - `detect_table_mapping()`: Maps CSV files to table names
   - `load_zensus_csv()`: Loads and preprocesses CSV data
   - Handles grid_id reconstruction from coordinates

3. **`scripts/generate_schema.py`**: Schema generation
   - `determine_column_type_from_data()`: Data-driven type detection
   - `sanitize_column_name()`: PostgreSQL identifier sanitization
   - Generates SQL CREATE TABLE statements

4. **`docker/init/02_schema.sql`**: Database schema
   - Defines all reference tables
   - Placeholder for fact tables (auto-generated)

## Data Sources

- **Zensus 2022**: German census data from Destatis
- **GeoGitter INSPIRE**: Grid geometries from BKG
- **VG250**: Administrative boundaries from BKG
- **Bundestagswahlen**: Election data from Bundeswahlleiter

## Coordinate Systems

- **All geometries**: EPSG:3035 (ETRS89-LAEA)
- **Input data**: May be EPSG:25832 (UTM Zone 32N) - automatically reprojected
- **Grid ID format**: `CRS3035RES{size}mN{y_mp}E{x_mp}`

## Common Issues and Solutions

1. **Column name errors**: Columns starting with numbers are prefixed with `col_`
2. **Type mismatches**: Schema generation detects NUMERIC vs INTEGER from data
3. **Invalid geometries**: Fixed with `geom.buffer(0)` before insertion
4. **Grid ID mismatches**: CSV uses corner coordinates, database uses center coordinates - handled by reconstruction

## Future Extensions

Planned additions (see `Implementation_notes/IMPLEMENTATION_NOTE_NEW_TABLES.md`):
- VG250 administrative boundaries (municipalities, counties, states)
- Bundestagswahlen electoral districts and structural data
- 100m grid resolution (when data available)
- Bridge tables for precomputed spatial intersections

## Getting Started for New Developers

1. **Read this file** (you're doing it!)
2. **Read `README.md`**: User-facing setup instructions
3. **Read `Implementation_notes/ARCHITECTURE_EXPLANATION.md`**: Deep dive into architecture
4. **Explore the code**:
   - Start with `etl/utils.py` to understand data preprocessing
   - Then `etl/load_zensus.py` to see the ETL pipeline
   - Finally `scripts/generate_schema.py` for schema generation
5. **Run the setup**: Follow `README.md` to get the database running
6. **Load sample data**: Start with 10km data (smaller, faster)

## Key Concepts for Understanding the Codebase

- **Star Schema**: Reference tables (geometries) + Fact tables (statistics)
- **Grid ID**: Unique identifier for each grid cell, format: `CRS3035RES{size}mN{y}E{x}`
- **Data Preprocessing**: German format → Standard format (commas → dots, em-dash → NULL)
- **Spatial Joins**: Using PostGIS functions to join geometries with statistics
- **Schema Generation**: Dynamic table creation based on CSV structure

## Contact and Documentation

- **User Documentation**: `README.md`
- **Architecture Details**: `Implementation_notes/ARCHITECTURE_EXPLANATION.md`
- **Implementation Guides**: `Implementation_notes/IMPLEMENTATION_NOTE_NEW_TABLES.md`
- **Data Analysis**: `Implementation_notes/VG250_ANALYSIS.md`, `Implementation_notes/BUNDESTAGSWAHLEN_ANALYSIS.md`

