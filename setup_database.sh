#!/bin/bash
# Automated setup script for German Zensus 2022 Database
# Based on the manual setup process from README.md
#
# Usage: ./setup_database.sh [OPTIONS]
#
# Options:
#   --test-mode         Load only 10km grid data (faster, for testing)
#   --full              Load all data: 100m, 1km, and 10km (default: 1km + 10km)
#   --skip-vg250        Skip loading VG250 administrative boundaries
#   --skip-elections    Skip loading Bundestagswahlen election data
#   --containerized     Skip Docker checks (for running inside containers)
#   --help              Show this help message

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
TEST_MODE=false
FULL_MODE=false
SKIP_VG250=false
SKIP_ELECTIONS=false
CONTAINERIZED=false

# Auto-detect containerized environment
if [ -f /.dockerenv ] || [ -n "$KUBERNETES_SERVICE_HOST" ] || [ -n "$DB_HOST" ]; then
    CONTAINERIZED=true
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --test-mode)
            TEST_MODE=true
            shift
            ;;
        --full)
            FULL_MODE=true
            shift
            ;;
        --skip-vg250)
            SKIP_VG250=true
            shift
            ;;
        --skip-elections)
            SKIP_ELECTIONS=true
            shift
            ;;
        --containerized)
            CONTAINERIZED=true
            shift
            ;;
        --help)
            echo "Automated setup script for German Zensus 2022 Database"
            echo ""
            echo "Usage: ./setup_database.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --test-mode         Load only 10km grid data (faster, for testing)"
            echo "  --full              Load all data: 100m, 1km, and 10km"
            echo "  --skip-vg250        Skip loading VG250 administrative boundaries"
            echo "  --skip-elections    Skip loading Bundestagswahlen election data"
            echo "  --containerized     Skip Docker checks (auto-detected in containers)"
            echo "  --help              Show this help message"
            echo ""
            echo "Default behavior (no flags): Load 1km + 10km Zensus data"
            echo ""
            echo "Containerized mode: Automatically detected when DB_HOST env var is set"
            echo "or when running inside Docker/Kubernetes containers."
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Determine which grid sizes to load
if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}Running in TEST MODE: Only 10km data will be loaded${NC}"
    GRID_SIZES=("10km")
elif [ "$FULL_MODE" = true ]; then
    echo -e "${YELLOW}Running in FULL MODE: Loading 100m, 1km, and 10km data${NC}"
    GRID_SIZES=("10km" "1km" "100m")
else
    echo -e "${YELLOW}Running in DEFAULT MODE: Loading 1km and 10km data${NC}"
    GRID_SIZES=("10km" "1km")
fi

# Function to print section headers
print_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Start timer
START_TIME=$(date +%s)

print_section "Step 1: Checking Prerequisites"

if [ "$CONTAINERIZED" = true ]; then
    echo -e "${YELLOW}Running in containerized mode - skipping Docker checks${NC}"
    
    # Check for required environment variables
    if [ -z "$DB_HOST" ]; then
        print_error "DB_HOST environment variable not set"
        exit 1
    fi
    
    # Set defaults for other DB variables if not set
    export DB_PORT=${DB_PORT:-5432}
    export DB_NAME=${DB_NAME:-zensus_db}
    export DB_USER=${DB_USER:-zensus_user}
    export DB_PASSWORD=${DB_PASSWORD:-zensus123}
    
    print_success "Database connection configured: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    
    # Check Python
    if command_exists python3 || command_exists python; then
        PYTHON_CMD=$(command_exists python3 && echo "python3" || echo "python")
        PYTHON_VERSION=$($PYTHON_CMD --version)
        print_success "Python is available: $PYTHON_VERSION"
    else
        print_error "Python is not installed."
        exit 1
    fi
    
    print_section "Step 2: Verifying Database Connection"
    
    # Test database connection using psql if available, otherwise continue
    if command_exists psql; then
        echo "Testing database connection..."
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "SELECT 1;" >/dev/null 2>&1; then
            print_success "Database connection successful"
        else
            print_error "Cannot connect to database. Check connection settings."
            exit 1
        fi
    else
        echo -e "${YELLOW}psql not available, installing PostgreSQL client...${NC}"
        apt-get update -qq && apt-get install -y -qq postgresql-client >/dev/null 2>&1
        print_success "PostgreSQL client installed"
        
        # Test connection again
        echo "Testing database connection..."
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "SELECT 1;" >/dev/null 2>&1; then
            print_success "Database connection successful"
        else
            print_error "Cannot connect to database. Check connection settings."
            exit 1
        fi
    fi
    
    # Define psql command for reuse
    PSQL_CMD="PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT"
    
    print_section "Step 3: Applying Database Schema"
    
    echo "Applying SQL schema files to database..."
    
    # Apply schema files in order
    SCHEMA_FILES=(
        "docker/init/01_extensions.sql"
        "docker/init/02_schema.sql"
        "docker/init/03_vg250_schema.sql"
        "docker/init/04_bundestagswahlen_schema.sql"
        "docker/init/05_lwu_properties_schema.sql"
    )
    
    for schema_file in "${SCHEMA_FILES[@]}"; do
        if [ -f "$schema_file" ]; then
            echo "  Applying $(basename $schema_file)..."
            if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -f "$schema_file" >/dev/null 2>&1; then
                print_success "  $(basename $schema_file) applied"
            else
                print_error "  Failed to apply $(basename $schema_file)"
                exit 1
            fi
        else
            echo -e "${YELLOW}  Schema file not found: $schema_file (skipping)${NC}"
        fi
    done
    
    print_success "Database schema applied successfully"
    
else
    # Original Docker-based setup
    # Check Docker
    if command_exists docker; then
        print_success "Docker is installed"
    else
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check Docker Compose
    if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
        print_success "Docker Compose is available"
    else
        print_error "Docker Compose is not available. Please install it first."
        exit 1
    fi

    # Check Python
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version)
        print_success "Python is installed: $PYTHON_VERSION"
    else
        print_error "Python 3 is not installed. Please install Python 3.8+."
        exit 1
    fi

    print_section "Step 2: Setting Up Virtual Environment"

    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi

    # Activate virtual environment
    source venv/bin/activate
    print_success "Virtual environment activated"

    print_section "Step 3: Installing Python Dependencies"

    pip install -r requirements.txt -q
    print_success "Python dependencies installed"

    print_section "Step 3: Starting Docker Containers"

    # Stop any existing containers
    docker-compose down 2>/dev/null || true

    # Start containers
    docker-compose up -d

    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    sleep 10

    # Check if database is ready
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! docker-compose exec -T postgres pg_isready -U zensus_user -d zensus_db >/dev/null 2>&1; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            print_error "PostgreSQL failed to start after ${MAX_RETRIES} attempts"
            docker-compose logs postgres
            exit 1
        fi
        echo "Waiting for PostgreSQL... (${RETRY_COUNT}/${MAX_RETRIES})"
        sleep 2
    done

    print_success "PostgreSQL is ready"
fi

print_section "Step 4: Loading Grid Geometries"

# Check if grid data exists
if [ ! -d "data/geo_data" ]; then
    print_error "Grid data not found in data/geo_data/"
    echo "Please download and place the INSPIRE grid files:"
    echo "  - DE_Grid_ETRS89-LAEA_10km.gpkg"
    echo "  - DE_Grid_ETRS89-LAEA_1km.gpkg"
    echo "  - DE_Grid_ETRS89-LAEA_100m.gpkg"
    exit 1
fi

# Load grids based on mode
for grid_size in "${GRID_SIZES[@]}"; do
    GRID_FILE="data/geo_data/DE_Grid_ETRS89-LAEA_${grid_size}.gpkg"
    if [ -f "$GRID_FILE" ]; then
        # Check if grid is already loaded
        TABLE_NAME="ref_grid_${grid_size}"
        ROW_COUNT=$(eval "$PSQL_CMD -t -c \"SELECT COUNT(*) FROM zensus.${TABLE_NAME};\" 2>/dev/null" || echo "0")
        ROW_COUNT=$(echo $ROW_COUNT | tr -d ' ')
        
        if [ "$ROW_COUNT" -gt 0 ]; then
            echo "Skipping ${grid_size} grid (already loaded with ${ROW_COUNT} rows)"
            continue
        fi
        
        echo "Loading ${grid_size} grid..."
        
        # Use ogr2ogr for 100m grid (memory-efficient), Python for others
        if [ "$grid_size" = "100m" ]; then
            echo "Using ogr2ogr for large 100m grid (memory-efficient method)..."
            
            # Check if ogr2ogr is available
            if ! command -v ogr2ogr &> /dev/null; then
                echo "Installing GDAL tools for ogr2ogr..."
                if [ "$IN_CONTAINER" = true ]; then
                    apt-get update -qq
                    apt-get install -y gdal-bin
                    
                    # Verify installation succeeded
                    if ! command -v ogr2ogr &> /dev/null; then
                        print_error "Failed to install ogr2ogr. Please install manually:"
                        echo "  apt-get update && apt-get install -y gdal-bin"
                        exit 1
                    fi
                    echo "✓ GDAL tools installed successfully"
                else
                    print_error "ogr2ogr not found. Please install GDAL tools:"
                    echo "  macOS: brew install gdal"
                    echo "  Ubuntu/Debian: sudo apt-get install gdal-bin"
                    exit 1
                fi
            fi
            
            # Load with ogr2ogr (streams data without loading all into memory)
            ogr2ogr \
                -f PostgreSQL \
                "PG:host=${DB_HOST} port=${DB_PORT} dbname=${DB_NAME} user=${DB_USER} password=${DB_PASSWORD}" \
                "$GRID_FILE" \
                -nln zensus.ref_grid_100m_temp \
                -lco GEOMETRY_NAME=geom \
                -lco SPATIAL_INDEX=NONE \
                -progress \
                --config PG_USE_COPY YES
            
            # Transform to match expected schema (construct grid_id from coordinates)
            echo "Transforming data to match expected schema..."
            $PSQL_CMD <<EOF
-- Create final table with proper schema
CREATE TABLE IF NOT EXISTS zensus.ref_grid_100m (
    grid_id TEXT PRIMARY KEY,
    geom GEOMETRY(POLYGON, 3035) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_100m_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_100m_srid CHECK (ST_SRID(geom) = 3035)
);

-- Insert with constructed grid_id from ogr2ogr temp table
INSERT INTO zensus.ref_grid_100m (grid_id, geom)
SELECT 
    'CRS3035RES100mN' || CAST(y_mp AS INTEGER) || 'E' || CAST(x_mp AS INTEGER) as grid_id,
    geom
FROM zensus.ref_grid_100m_temp
ON CONFLICT (grid_id) DO NOTHING;

-- Create spatial index
CREATE INDEX IF NOT EXISTS idx_grid_100m_geom 
    ON zensus.ref_grid_100m USING GIST (geom);

-- Drop temp table
DROP TABLE zensus.ref_grid_100m_temp;

-- Verify
SELECT COUNT(*) as total_rows FROM zensus.ref_grid_100m;
EOF
            
        else
            # Use Python script for 1km and 10km (works fine with available memory)
            python etl/load_grids.py "$GRID_FILE" "$grid_size"
        fi
        
        print_success "${grid_size} grid loaded"
    else
        print_error "${grid_size} grid file not found: $GRID_FILE"
        exit 1
    fi
done

print_section "Step 5: Generating and Applying Zensus Data Schema"

# Generate and apply schema for each grid size
for grid_size in "${GRID_SIZES[@]}"; do
    CSV_DIR="data/zensus_data/${grid_size}"
    if [ ! -d "$CSV_DIR" ]; then
        print_error "Zensus data directory not found: $CSV_DIR"
        exit 1
    fi
    
    CSV_COUNT=$(find "$CSV_DIR" -name "*.csv" -type f | wc -l | tr -d ' ')
    echo "Found ${CSV_COUNT} CSV files for ${grid_size}"
    
    if [ "$CSV_COUNT" -eq 0 ]; then
        print_error "No CSV files found in $CSV_DIR"
        exit 1
    fi
    
    echo "Generating schema for ${grid_size}..."
    # Generate SQL (redirect stderr to not pollute SQL output)
    python scripts/generate_schema.py "$CSV_DIR" 2>/dev/null > "/tmp/schema_${grid_size}.sql"
    
    echo "Applying schema to database..."
    # Apply SQL to database
    if [ "$CONTAINERIZED" = true ]; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" < "/tmp/schema_${grid_size}.sql"
    else
        docker-compose exec -T postgres psql -U zensus_user -d zensus_db < "/tmp/schema_${grid_size}.sql"
    fi
    
    # Clean up temp file
    rm -f "/tmp/schema_${grid_size}.sql"
    
    print_success "Schema generated and applied for ${grid_size}"
done

print_section "Step 6: Loading Zensus Data"

# Load Zensus data for each grid size
for grid_size in "${GRID_SIZES[@]}"; do
    CSV_DIR="data/zensus_data/${grid_size}"
    
    # Check if Zensus data is already loaded (check one representative table)
    SAMPLE_TABLE="fact_zensus_${grid_size}_zensus2022_bevoelkerungszahl"
    ROW_COUNT=$(eval "$PSQL_CMD -t -c \"SELECT COUNT(*) FROM zensus.${SAMPLE_TABLE};\" 2>/dev/null" || echo "0")
    ROW_COUNT=$(echo $ROW_COUNT | tr -d ' ')
    
    if [ "$ROW_COUNT" -gt 0 ]; then
        echo "Skipping ${grid_size} Zensus data (already loaded with ${ROW_COUNT} rows in ${SAMPLE_TABLE})"
        continue
    fi
    
    echo "Loading all ${grid_size} CSV files..."
    # Load entire directory at once
    python etl/load_zensus.py "$CSV_DIR"
    
    print_success "All ${grid_size} Zensus data loaded"
done

# Optional: Load VG250 data
if [ "$SKIP_VG250" = false ]; then
    print_section "Step 7: Loading VG250 Administrative Boundaries (Optional)"
    
    # Try multiple possible VG250 directory names
    VG250_DIR=""
    for dir in "data/vg250_ebenen_0101" "data/vg250_ebenen" "data/vg250"; do
        if [ -d "$dir" ]; then
            VG250_DIR="$dir"
            break
        fi
    done
    
    if [ -n "$VG250_DIR" ]; then
        echo "Found VG250 data in: $VG250_DIR"
        
        # Check if VG250 data is already loaded
        VG250_COUNT=$(eval "$PSQL_CMD -t -c \"SELECT COUNT(*) FROM zensus.ref_federal_state;\" 2>/dev/null" || echo "0")
        VG250_COUNT=$(echo $VG250_COUNT | tr -d ' ')
        
        if [ "$VG250_COUNT" -gt 0 ]; then
            echo "Skipping VG250 data (already loaded with ${VG250_COUNT} federal states)"
        else
            # Look for VG250 shapefiles
            FED_SHP=$(find "$VG250_DIR" -name "*VG250_LAN*.shp" -type f | head -n 1)
            COUNTY_SHP=$(find "$VG250_DIR" -name "*VG250_KRS*.shp" -type f | head -n 1)
            MUNI_SHP=$(find "$VG250_DIR" -name "*VG250_GEM*.shp" -type f | head -n 1)
            
            if [ -n "$FED_SHP" ]; then
                echo "Loading federal states..."
                python etl/load_vg250.py "$FED_SHP" --table ref_federal_state
                print_success "Federal states loaded"
            else
                echo "Federal states shapefile not found, skipping..."
            fi
            
            if [ -n "$COUNTY_SHP" ]; then
                echo "Loading counties..."
                python etl/load_vg250.py "$COUNTY_SHP" --table ref_county
                print_success "Counties loaded"
            else
                echo "Counties shapefile not found, skipping..."
            fi
            
            if [ -n "$MUNI_SHP" ]; then
                echo "Loading municipalities..."
                python etl/load_vg250.py "$MUNI_SHP" --table ref_municipality --chunk-size 2000
                print_success "Municipalities loaded"
            else
                echo "Municipalities shapefile not found, skipping..."
            fi
        fi
    else
        echo "VG250 data directory not found, skipping..."
    fi
else
    echo -e "${YELLOW}Skipping VG250 data (--skip-vg250 flag)${NC}"
fi

# Optional: Load Election data
if [ "$SKIP_ELECTIONS" = false ]; then
    print_section "Step 8: Loading Bundestagswahlen Election Data (Optional)"
    
    ELECTION_DIR="data/bundestagswahlen"
    if [ -d "$ELECTION_DIR" ]; then
        # Check if election data is already loaded
        ELECTION_COUNT=$(eval "$PSQL_CMD -t -c \"SELECT COUNT(*) FROM zensus.ref_electoral_district;\" 2>/dev/null" || echo "0")
        ELECTION_COUNT=$(echo $ELECTION_COUNT | tr -d ' ')
        
        if [ "$ELECTION_COUNT" -gt 0 ]; then
            echo "Skipping election data (already loaded with ${ELECTION_COUNT} electoral districts)"
        else
            # Load BTW2017
            if [ -d "$ELECTION_DIR/btw2017" ]; then
                BTW2017_SHP=$(find "$ELECTION_DIR/btw2017" -name "*.shp" -type f | head -n 1)
                BTW2017_CSV=$(find "$ELECTION_DIR/btw2017" -name "*strukturdaten*.csv" -type f | head -n 1)
                
                if [ -n "$BTW2017_SHP" ] && [ -n "$BTW2017_CSV" ]; then
                    echo "Loading BTW2017 data..."
                    python etl/load_elections.py --shapefile "$BTW2017_SHP" --csv "$BTW2017_CSV" --election-year 2017
                    print_success "BTW2017 loaded"
                else
                    echo "BTW2017 data incomplete, skipping..."
                fi
            fi
        
        # Load BTW2021
        if [ -d "$ELECTION_DIR/btw2021" ]; then
            BTW2021_SHP=$(find "$ELECTION_DIR/btw2021" -name "*.shp" -type f | head -n 1)
            BTW2021_CSV=$(find "$ELECTION_DIR/btw2021" -name "*strukturdaten*.csv" -type f | head -n 1)
            
            if [ -n "$BTW2021_SHP" ] && [ -n "$BTW2021_CSV" ]; then
                echo "Loading BTW2021 data..."
                python etl/load_elections.py --shapefile "$BTW2021_SHP" --csv "$BTW2021_CSV" --election-year 2021
                print_success "BTW2021 loaded"
            else
                echo "BTW2021 data incomplete, skipping..."
            fi
        fi
        
        # Load BTW2025
        if [ -d "$ELECTION_DIR/btw2025" ]; then
            BTW2025_SHP=$(find "$ELECTION_DIR/btw2025" -name "*.shp" -type f | head -n 1)
            BTW2025_CSV=$(find "$ELECTION_DIR/btw2025" -name "*strukturdaten*.csv" -type f | head -n 1)
            
            if [ -n "$BTW2025_SHP" ] && [ -n "$BTW2025_CSV" ]; then
                echo "Loading BTW2025 data..."
                python etl/load_elections.py --shapefile "$BTW2025_SHP" --csv "$BTW2025_CSV" --election-year 2025
                print_success "BTW2025 loaded"
            else
                    echo "BTW2025 data incomplete, skipping..."
                fi
            fi
        fi
    else
        echo "Election data directory not found ($ELECTION_DIR), skipping..."
    fi
else
    echo -e "${YELLOW}Skipping election data (--skip-elections flag)${NC}"
fi

# Load LWU properties (always if data exists)
print_section "Step 9: Loading LWU Berlin Properties (Optional)"

LWU_FILE="data/luw_berlin/lwu_berlin_small.geojson"
if [ -f "$LWU_FILE" ]; then
    # Check if LWU data is already loaded
    LWU_COUNT=$(eval "$PSQL_CMD -t -c \"SELECT COUNT(*) FROM zensus.ref_lwu_properties;\" 2>/dev/null" || echo "0")
    LWU_COUNT=$(echo $LWU_COUNT | tr -d ' ')
    
    if [ "$LWU_COUNT" -gt 0 ]; then
        echo "Skipping LWU properties (already loaded with ${LWU_COUNT} properties)"
    else
        echo "Loading LWU Berlin properties..."
        python etl/load_lwu_properties.py "$LWU_FILE"
        print_success "LWU properties loaded"
    fi
else
    echo "LWU data file not found ($LWU_FILE), skipping..."
fi

print_section "Step 10: Verifying Database"

# Run verification queries
echo "Running verification queries..."

python -c "
from etl.utils import get_db_engine
from sqlalchemy import text

engine = get_db_engine()
with engine.connect() as conn:
    # Count grids
    for grid_size in ['10km', '1km', '100m']:
        try:
            count = conn.execute(text(f'SELECT COUNT(*) FROM zensus.ref_grid_{grid_size}')).scalar()
            if count > 0:
                print(f'  Grid {grid_size}: {count:,} cells')
        except:
            pass
    
    # Count fact tables
    try:
        result = conn.execute(text(\"\"\"
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'zensus' 
            AND table_name LIKE 'fact_zensus_%'
            ORDER BY table_name
        \"\"\")).fetchall()
        fact_count = len(result)
        print(f'  Fact tables: {fact_count}')
    except Exception as e:
        print(f'  Error counting fact tables: {e}')
    
    # Count VG250 if loaded
    if '$SKIP_VG250' == 'false':
        try:
            fed = conn.execute(text('SELECT COUNT(*) FROM zensus.ref_federal_state')).scalar()
            county = conn.execute(text('SELECT COUNT(*) FROM zensus.ref_county')).scalar()
            muni = conn.execute(text('SELECT COUNT(*) FROM zensus.ref_municipality')).scalar()
            if fed > 0:
                print(f'  Federal states: {fed}')
            if county > 0:
                print(f'  Counties: {county}')
            if muni > 0:
                print(f'  Municipalities: {muni:,}')
        except:
            pass
    
    # Count elections if loaded
    if '$SKIP_ELECTIONS' == 'false':
        try:
            districts = conn.execute(text('SELECT COUNT(*) FROM zensus.ref_electoral_district')).scalar()
            structural = conn.execute(text('SELECT COUNT(*) FROM zensus.fact_election_structural_data')).scalar()
            if districts > 0:
                print(f'  Electoral districts: {districts}')
            if structural > 0:
                print(f'  Election structural data: {structural}')
        except:
            pass
    
    # Count LWU properties if loaded
    try:
        lwu = conn.execute(text('SELECT COUNT(*) FROM zensus.ref_lwu_properties')).scalar()
        if lwu > 0:
            print(f'  LWU properties: {lwu:,}')
    except:
        pass
"

print_success "Database verification complete"

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

print_section "Setup Complete!"

echo -e "${GREEN}Database successfully set up and populated!${NC}"
echo ""
echo "Time elapsed: ${MINUTES}m ${SECONDS}s"
echo ""
echo "Connection details:"
if [ "$CONTAINERIZED" = true ]; then
    echo "  Host: $DB_HOST"
    echo "  Port: $DB_PORT"
    echo "  Database: $DB_NAME"
    echo "  User: $DB_USER"
    echo "  Password: $DB_PASSWORD"
    echo ""
    echo "Connect with:"
    echo "  psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
else
    echo "  Host: localhost"
    echo "  Port: 5432"
    echo "  Database: zensus_db"
    echo "  User: zensus_user"
    echo "  Password: zensus123"
    echo ""
    echo "Connect with:"
    echo "  psql -h localhost -p 5432 -U zensus_user -d zensus_db"
fi
echo ""
echo "Or use pgAdmin, DBeaver, or QGIS to connect and query the data."
echo ""

if [ "$TEST_MODE" = true ]; then
    echo -e "${YELLOW}Note: Running in TEST MODE with only 10km data.${NC}"
    echo "To load all data, run: ./setup_database.sh --full"
fi
