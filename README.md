# PostGIS Zensus Database

A PostgreSQL + PostGIS database for German Zensus 2022 data aggregated to INSPIRE grid cells (1km and 10km resolution).

## Overview

This project provides a complete database setup for storing and querying German census data with spatial geometries. The database uses a star schema design with:

- **Grid Reference tables**: Store authoritative polygon geometries from GeoGitter INSPIRE (EPSG:3035)
- **Administrative Reference tables**: Store VG250 administrative boundaries (federal states, counties, municipalities)
- **Electoral Reference tables**: Store Bundestagswahlen electoral district boundaries
- **Fact tables**: Store Zensus statistical data and election structural data, joined to reference tables via foreign keys

### Database Contents

**Zensus Grid Data:**
- 1km and 10km INSPIRE grid cells
- 40+ demographic, housing, and socioeconomic datasets

**VG250 Administrative Boundaries:**
- 34 federal states (Bundesländer)
- 433 counties (Kreise und kreisfreie Städte)
- 11,103 municipalities (Gemeinden)

**Bundestagswahlen Election Data:**
- Electoral districts (299 per year: 2017, 2021, 2025)
- Structural data (52 socioeconomic indicators per district)

**LWU Berlin Properties:**
- 5,468 property parcels owned by Berlin state housing companies
- Full polygon geometries for spatial analysis

## Features

- Docker-based local development setup
- PostgreSQL 15+ with PostGIS extension
- Automated ETL scripts with data preprocessing (German number format, missing values)
- Data quality tests using dbt
- Backup and restore scripts
- Security best practices (non-superuser roles)

## Prerequisites

- Docker and Docker Compose
- Python 3.8+ (for ETL scripts)
- PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`) for backup/restore

## Deployment Guide

This project can be run locally for development or deployed on a server using Dokploy. Choose the appropriate section below.

---

## Running Locally

### Prerequisites

- **Docker Desktop** (Mac/Windows) or **Docker Engine + Docker Compose** (Linux)
- **Python 3.8+** with `pip`
- **Git** (to clone the repository)

### Quick Start: Automated Setup (Recommended)

For a fully automated setup, use the provided setup script:

```bash
# Clone the repository
git clone <repository-url>
cd red_data_database

# Create .env file from template
cp .env.example .env
nano .env  # Edit and set passwords

# Run automated setup (loads 1km + 10km data by default)
./setup_database.sh

# OR: Test mode with only 10km data (faster)
./setup_database.sh --test-mode

# OR: Full setup with all data including 100m
./setup_database.sh --full
```

**Available options:**
- `--test-mode`: Load only 10km grid data (fastest, for testing)
- `--full`: Load all data including 100m, 1km, and 10km (slowest, complete dataset)
- `--skip-vg250`: Skip loading VG250 administrative boundaries
- `--skip-elections`: Skip loading Bundestagswahlen election data
- No flags: Load 1km + 10km data (recommended default)

The script will automatically:
1. Check prerequisites (Docker, Python)
2. Set up virtual environment and install dependencies
3. Start PostgreSQL container
4. Load grid geometries
5. Generate database schema
6. Load all Zensus datasets
7. Optionally load VG250 and election data
8. Verify the installation

**Time estimates:**
- `--test-mode` (10km only): ~5-10 minutes
- Default (1km + 10km): ~30-60 minutes
- `--full` (100m + 1km + 10km): Several hours

---

### Manual Setup (Step-by-Step)

If you prefer to run each step manually, follow these instructions:

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd red_data_database

# Create .env file from template
cp .env.example .env

# Edit .env and replace 'changeme' with a strong password
nano .env  # or use your preferred editor (vim, code, etc.)

# The .env file should contain:
# - POSTGRES_PASSWORD: Password for PostgreSQL database user
# - DB_PASSWORD: Same password (used by ETL scripts to connect)
# Make sure both passwords match!
```

### Step 2: Start Database Container

```bash
# Start PostgreSQL with PostGIS in detached mode
docker-compose up -d
```

**What this command does:**
- `docker-compose up`: Reads the `docker-compose.yml` file in the current directory and starts all services defined in it
- `-d` flag: Runs containers in "detached" mode (in the background), so you get your terminal back
- **Where it's defined**: The configuration is in `docker-compose.yml` at the root of the project. This file defines:
  - Which Docker image to use (`postgis/postgis:15-3.4`)
  - Environment variables (from your `.env` file)
  - Port mappings (e.g., host port 5432 → container port 5432)
  - Volume mounts (where data is stored)
  - Health checks (how Docker verifies the container is healthy)

**What happens when you run this:**
1. Docker checks if the `postgis/postgis:15-3.4` image exists locally
2. If not, it downloads it from Docker Hub (first time only)
3. Creates a container named `zensus_postgres` based on the image
4. Sets environment variables from your `.env` file
5. Mounts volumes (persistent data storage)
6. Runs initialization scripts from `docker/init/` directory:
   - `01_extensions.sql` - Enables PostGIS extension
   - `02_schema.sql` - Creates all tables
   - `03_indexes.sql` - Creates indexes for performance
7. Starts PostgreSQL and makes it available on port 5432

```bash
# Verify container is running
docker-compose ps
```

**What this does:**
- Lists all containers defined in `docker-compose.yml` and their status
- Shows if they're running, stopped, or restarting
- Displays port mappings (e.g., `0.0.0.0:5432->5432/tcp`)

```bash
# Check logs to ensure database initialized correctly
docker-compose logs postgres
```

**What this does:**
- Shows the output/logs from the `postgres` service (defined in `docker-compose.yml`)
- Useful for debugging - you'll see PostgreSQL startup messages
- You should see messages like:
  - "database system is ready to accept connections"
  - "PostGIS extension enabled"
  - Any errors if something went wrong

**Troubleshooting**:
- **"role 'zensus_user' does not exist" or connection errors**:
  - **Common Cause 1**: Local PostgreSQL is running and intercepting connections on port 5432
    - **Check**: `lsof -i :5432` - if you see a `postgres` process (not `com.docker`), you have a local PostgreSQL running
    - **Solution A** (Stop local PostgreSQL - Recommended):
      ```bash
      # If installed via Homebrew:
      brew services stop postgresql
      # Or if installed via other method:
      # Find and stop the PostgreSQL service
      ```
    - **Solution B** (Use different port for Docker):
      ```bash
      # Edit .env file: change POSTGRES_PORT=5433
      # Edit .env file: change DB_PORT=5433
      # Restart container:
      docker-compose down
      docker-compose up -d
      ```
  - **Common Cause 2**: Password mismatch between `.env` file and database
    - **Check if user exists in Docker container**:
      ```bash
      docker-compose exec postgres psql -U zensus_user -d zensus_db -c "\du"
      ```
    - **Solution** (Update password in database):
      ```bash
      # Replace 'your_password_from_env' with the actual password from .env
      docker-compose exec postgres psql -U zensus_user -d zensus_db -c "ALTER USER zensus_user WITH PASSWORD 'your_password_from_env';"
      ```
  - **Verify .env file matches database**:
    - Check `.env` file has: `POSTGRES_USER=zensus_user` and `POSTGRES_PASSWORD=your_actual_password`
    - Check `.env` file has: `DB_USER=zensus_user` and `DB_PASSWORD=your_actual_password` (must match!)
    - **Important**: `POSTGRES_PASSWORD` and `DB_PASSWORD` must be the same value
  - **Clean slate** (recreate database):
    ```bash
    # Stop and remove container and volumes (⚠️ deletes all data)
    docker-compose down -v
    # Make sure .env file has correct POSTGRES_USER and POSTGRES_PASSWORD
    # Start fresh
    docker-compose up -d
    ```
- **Platform mismatch error** (Apple Silicon/M1/M2 Macs):
  - **Error**: `platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)`
  - **Solution**: The `docker-compose.yml` already includes `platform: linux/amd64` to handle this
  - **What it does**: Runs the AMD64 image using Rosetta 2 emulation (slightly slower but works)
  - **Alternative**: If you want native ARM64, you could use `postgis/postgis:15-3.4` without platform specification, but the official image may not have ARM64 builds
- If port 5432 is already in use, change `POSTGRES_PORT` in `.env` to another port (e.g., `5433`)
  - **Why**: Another PostgreSQL instance or application might be using port 5432
  - **How to check**: `lsof -i :5432` (shows what's using the port)
- If container fails to start, check logs: `docker-compose logs postgres`
  - **What to look for**: Error messages about permissions, missing files, or configuration issues

### Step 3: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
```

**What this does:**
- `python3 -m venv`: Uses Python's built-in `venv` module to create a virtual environment
- `venv`: The name of the directory that will contain the isolated Python environment
- **Why use a virtual environment**: Isolates project dependencies from your system Python, preventing conflicts between different projects
- **What gets created**: A `venv/` directory with its own Python interpreter and package installation location

```bash
# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

**What this does:**
- `source venv/bin/activate`: Runs the activation script that modifies your shell's PATH
- **After activation**: When you run `python` or `pip`, they use the versions in `venv/` instead of system-wide versions
- **How you know it's active**: Your prompt will show `(venv)` at the beginning
- **To deactivate**: Just type `deactivate` (no need to source anything)

```bash
# Install dependencies
pip install -r requirements.txt
```

**What this does:**
- `pip install`: Python's package installer
- `-r requirements.txt`: Reads the `requirements.txt` file and installs all packages listed there
- **Where it's defined**: `requirements.txt` in the project root lists all Python packages needed:
  - `pandas` - Data manipulation
  - `geopandas` - Spatial data handling
  - `sqlalchemy` - Database connectivity
  - `python-dotenv` - Reading `.env` files
  - etc.
- **What happens**: pip downloads packages from PyPI (Python Package Index) and installs them into `venv/`

```bash
# Verify installation
python -c "import geopandas; import pandas; print('Dependencies installed successfully')"
```

**What this does:**
- `python -c`: Runs Python code directly from command line
- `import geopandas; import pandas`: Tries to import the packages (fails if not installed)
- **Purpose**: Quick verification that packages installed correctly

### Step 4: Verify Database Connection

```bash
# Test database connection (with venv activated)
python -c "
from etl.utils import get_db_engine
engine = get_db_engine()
print('Database connection successful!')
"
```

**What this does:**
- `from etl.utils import get_db_engine`: Imports the database connection function from `etl/utils.py`
- `get_db_engine()`: Creates a SQLAlchemy database engine (connection object)
  - **Where it's defined**: `etl/utils.py` - reads connection info from `.env` file
  - **What it reads**: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` from `.env`
  - **What it creates**: A connection string like `postgresql://user:password@host:port/database`
- **Purpose**: Verifies that:
  1. Python can connect to the database
  2. Your `.env` file has correct credentials
  3. The database container is running and accessible

### Step 5: Load Grid Geometries

**Important**: Load grid geometries before loading Zensus data, as fact tables have foreign key constraints.

```bash
# Ensure venv is activated AND you're in the project root directory
source venv/bin/activate
cd /Users/lutz/Documents/red_data/repos/red_data_database  # Make sure you're in project root

# Load grid geometries (start with smaller grids for testing)
# 10km grid (smallest, ~3.8K rows) - recommended for initial testing
# Note: Filename uses underscore: DE_Grid_ETRS89-LAEA_10km.gpkg (not hyphen!)
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_10km.gpkg 10km
```

**Important**: The scripts automatically add the project root to Python's path, so you can run them from any directory. However, it's still recommended to run from the project root for consistency.

**If you get "ModuleNotFoundError: No module named 'etl'"**:
- Make sure virtual environment is activated: Your prompt should show `(venv)`
- Make sure you're in the project root: `pwd` should show `/Users/lutz/Documents/red_data/repos/red_data_database`
- The scripts should handle this automatically, but if issues persist, try: `PYTHONPATH=. python etl/load_grids.py ...`

**What this command does:**
- `python etl/load_grids.py`: Runs the grid loading script
- **Arguments**:
  - `data/geo_data/DE_Grid_ETRS89-LAEA_10km.gpkg`: Path to the GPKG (GeoPackage) file containing grid cell polygons
  - `10km`: Grid size identifier (used to determine which table to load into: `ref_grid_10km`)
- **Where it's defined**: `etl/load_grids.py` - the main script that:
  1. Reads the GPKG file using GeoPandas
  2. Constructs `grid_id` from coordinates (format: `CRS3035RES10000mN{y}E{x}`)
  3. Validates and fixes geometries if needed
  4. Inserts data into `zensus.ref_grid_10km` table in chunks of 10,000 rows
- **What happens**:
  1. Script connects to database using credentials from `.env`
  2. Reads GPKG file (contains polygon geometries for each grid cell)
  3. Converts coordinate system to EPSG:3035 if needed
  4. Creates `grid_id` for each cell from its coordinates
  5. Inserts into database table `zensus.ref_grid_10km`
  6. Logs progress to `etl.log` file

```bash
# 1km grid (~214K rows) - takes a few minutes
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_1km.gpkg 1km

# 100m grid (12GB file, millions of rows) - requires 16GB+ RAM, takes hours
# Only load if you have sufficient resources
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_100m.gpkg 100m
```

**Progress tracking**: The script logs progress every 10,000 rows. Monitor `etl.log` for detailed information.
- **Where logs are written**: `etl.log` file in project root
- **What you'll see**: Messages like "Inserted chunk 1: 10000/214000 rows"

### Step 6: Generate Database Schema for Zensus Tables

**Important**: Before loading Zensus CSV data, you must create the fact tables in the database. The schema generation script analyzes the CSV files and creates the appropriate `CREATE TABLE` statements.

```bash
# Ensure venv is activated
source venv/bin/activate

# Generate schema for all 10km tables
# Note: 2>/dev/null redirects status messages to avoid them appearing in the SQL file
python scripts/generate_schema.py data/zensus_data/10km/ 2>/dev/null > schema_10km.sql

# Generate schema for all 1km tables (if you plan to load 1km data)
python scripts/generate_schema.py data/zensus_data/1km/ 2>/dev/null > schema_1km.sql

# Generate schema for all 100m tables (if you plan to load 100m data)
python scripts/generate_schema.py data/zensus_data/100m/ 2>/dev/null > schema_100m.sql
```

**What this does:**
- `python scripts/generate_schema.py`: Runs the schema generation script
- **Argument**: Path to directory containing CSV files (e.g., `data/zensus_data/10km/`)
- **Output**: SQL file with `CREATE TABLE` statements for all fact tables
- **Where it's defined**: `scripts/generate_schema.py` - the script that:
  1. Scans all CSV files in the specified directory
  2. Reads column headers from each CSV
  3. Inspects sample data (first 100 rows) to detect data types:
     - If data contains decimal commas (e.g., `"129,1"`), column is `NUMERIC`
     - Otherwise, column is `INTEGER`
  4. Generates `CREATE TABLE` SQL statements with proper data types
  5. Outputs SQL to stdout (redirected to `.sql` file)

**Apply the generated schema to the database:**

```bash
# Apply 10km schema
docker-compose exec -T postgres psql -U zensus_user -d zensus_db < schema_10km.sql

# Apply 1km schema (if generated)
docker-compose exec -T postgres psql -U zensus_user -d zensus_db < schema_1km.sql

# Apply 100m schema (if generated)
docker-compose exec -T postgres psql -U zensus_user -d zensus_db < schema_100m.sql
```

**What these commands do:**
- `docker-compose exec -T postgres`: Executes a command inside the running `postgres` container
  - `-T`: Disables pseudo-TTY allocation (needed for piping input)
- `psql -U zensus_user -d zensus_db`: Connects to PostgreSQL as `zensus_user` in database `zensus_db`
- `< schema_10km.sql`: Pipes the SQL file contents into `psql` to execute the `CREATE TABLE` statements

**Note**: You only need to generate and apply schemas for the grid sizes you plan to load. For example, if you're only working with 10km data, you only need `schema_10km.sql`.

### Step 7: Load Zensus Data

Load census statistics (can be done in any order, but grid geometries must be loaded first):

**Data Structure**: The Zensus data is organized by grid size:
- `data/zensus_data/10km/` - All 10km CSV files
- `data/zensus_data/1km/` - All 1km CSV files
- `data/zensus_data/100m/` - All 100m CSV files
- `data/zensus_data/descriptions/` - Excel description files

#### Option 1: Load All Files from a Folder (Recommended)

```bash
# Ensure venv is activated
source venv/bin/activate

# Load all 10km CSV files at once
python etl/load_zensus.py data/zensus_data/10km/

# Load all 1km CSV files at once
python etl/load_zensus.py data/zensus_data/1km/

# Load all 100m CSV files at once (takes longer)
python etl/load_zensus.py data/zensus_data/100m/
```

**What this does:**
- The script detects that the path is a directory
- Finds all `.csv` files in that directory
- Loads each file sequentially
- Shows progress for each file
- Provides a summary at the end

#### Option 2: Load a Single File

```bash
# Load a specific CSV file
python etl/load_zensus.py data/zensus_data/10km/Zensus2022_Bevoelkerungszahl_10km-Gitter.csv
```

**What the load script does:**
- `python etl/load_zensus.py`: Runs the Zensus data loading script
- **Argument**: Path to a CSV file or directory containing CSV files
- **Where it's defined**: `etl/load_zensus.py` - the main script that:
  1. Reads CSV file (semicolon-delimited, German format)
  2. Detects table name from filename (e.g., `Zensus2022_Bevoelkerungszahl_10km-Gitter.csv` → `fact_zensus_10km_bevoelkerungszahl`)
  3. Detects grid size from filename (`10km-Gitter` → `10km`)
  4. Sanitizes column names (removes special characters, converts to lowercase)
  5. Detects data types (INTEGER vs NUMERIC) by inspecting data values
  6. Preprocesses data:
     - Converts German decimals (`"129,1"` → `129.1`)
     - Converts em-dash missing values (`"–"` → `NULL`)
  7. Validates `grid_id` exists in reference table (optional)
  8. Inserts data into appropriate fact table

**What happens step-by-step:**
1. **Read CSV**: Uses pandas with `sep=';'` (semicolon delimiter, German format)
2. **Detect table**: From filename `Zensus2022_Bevoelkerungszahl_10km-Gitter.csv` → extracts `Bevoelkerungszahl` → table `fact_zensus_10km_bevoelkerungszahl`
3. **Detect grid size**: From filename pattern `*10km-Gitter.csv` → `10km`
4. **Type detection**: Scans first 100 rows, checks for decimal commas → determines INTEGER vs NUMERIC
5. **Preprocessing**: Applies `normalize_decimal()` or `normalize_integer()` functions
6. **Validation**: Checks each `grid_id` exists in `ref_grid_10km` table (if `--no-validate` not used)
7. **Insert**: Chunked inserts (10,000 rows at a time) with `ON CONFLICT DO UPDATE` for idempotency

**Command-line options:**
- `--no-validate`: Skip grid_id validation (faster, but less safe)
- `--chunk-size N`: Change chunk size (default: 10000)
- `--recursive`: If loading a directory, search subdirectories recursively

**Note**: Each CSV file is processed independently. When loading a directory, files are processed sequentially.

**Important**: 
- **You must complete Step 6 (Generate Database Schema) first** before loading data, otherwise the tables won't exist and the load will fail with errors like `relation "zensus.fact_zensus_10km_..." does not exist`.
- Grid geometries must be loaded first (Step 5) before loading Zensus data, as fact tables reference the grid tables.

### Step 7a: Load VG250 and Election Data (Optional)

The database now includes support for VG250 administrative boundaries and Bundestagswahlen election data.

**To load this data:**

```bash
# Load VG250 administrative boundaries
python etl/load_vg250.py path/to/VG250_LAN.shp --table ref_federal_state
python etl/load_vg250.py path/to/VG250_KRS.shp --table ref_county
python etl/load_vg250.py path/to/VG250_GEM.shp --table ref_municipality

# Load Bundestagswahlen election data (example for 2025)
python etl/load_elections.py \
    --shapefile path/to/btw25_geometrie_wahlkreise_vg250.shp \
    --csv path/to/btw2025_strukturdaten.csv \
    --election-year 2025
```

**What this enables:**
- Aggregate Zensus data by municipalities, counties, or federal states
- Compare Zensus demographics with election structural data
- Analyze electoral districts using fine-grained Zensus grid data
- Create administrative hierarchy queries

```bash
# Load LWU Berlin properties (state-owned housing company properties)
python etl/load_lwu_properties.py data/luw_berlin/lwu_berlin_small.geojson
```

**What this enables:**
- Identify state-owned properties in census grid cells
- Analyze demographics around state housing locations
- Compare with administrative boundaries and electoral districts

### Step 8: Verify Data Load (Local)

```bash
# Connect to database and check row counts
docker-compose exec postgres psql -U zensus_user -d zensus_db -c "
SELECT 
    'ref_grid_10km' as table_name, COUNT(*) as row_count 
FROM zensus.ref_grid_10km
UNION ALL
SELECT 
    'fact_zensus_10km_bevoelkerungszahl', COUNT(*) 
FROM zensus.fact_zensus_10km_bevoelkerungszahl;
"
```

**What this command does:**
- `docker-compose exec postgres`: Executes a command inside the running `postgres` container
- `psql`: PostgreSQL command-line client
- `-U zensus_user`: Connect as user `zensus_user`
- `-d zensus_db`: Connect to database `zensus_db`
- `-c "..."`: Execute SQL command directly (instead of interactive mode)
- **The SQL query**:
  - `SELECT ... COUNT(*)`: Counts rows in each table
  - `UNION ALL`: Combines results from multiple SELECT statements
  - **Purpose**: Verifies data was loaded correctly by checking row counts

**Alternative verification** (interactive):
```bash
docker-compose exec postgres psql -U zensus_user -d zensus_db
# Then in psql prompt:
SELECT COUNT(*) FROM zensus.ref_grid_10km;
\q  # Exit
```

### Step 9: Access Database

See the **"Accessing the Database"** section below for detailed instructions on connecting from your local machine using various tools.

### Understanding docker-compose.yml

The `docker-compose.yml` file defines how Docker should run your database. Here's what each part does:

```yaml
services:
  postgres:  # Service name (you reference this with docker-compose commands)
    image: postgis/postgis:15-3.4  # Docker image to use (PostgreSQL 15 with PostGIS extension)
    platform: linux/amd64  # Platform specification (needed for Apple Silicon Macs)
    container_name: zensus_postgres  # Name of the container (visible in docker ps)
    
    environment:  # Environment variables passed to the container
      POSTGRES_DB: ${POSTGRES_DB:-zensus_db}  # ${VAR:-default} = use VAR from .env, or default
      POSTGRES_USER: ${POSTGRES_USER:-zensus_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      # These are read from your .env file when you run docker-compose up
    
    ports:
      - "${POSTGRES_PORT:-5432}:5432"  # host_port:container_port
      # Maps your machine's port 5432 to container's port 5432
      # This is how you connect: localhost:5432 → container:5432
    
    volumes:  # Persistent storage (data survives container restarts)
      - postgres_data:/var/lib/postgresql/data  # Named volume for database files
      - ./docker/init:/docker-entrypoint-initdb.d  # Mount init scripts
      # This runs SQL files in docker/init/ when database first starts
    
    healthcheck:  # How Docker checks if container is healthy
      test: ["CMD-SHELL", "pg_isready -U zensus_user -d zensus_db"]
      interval: 10s  # Check every 10 seconds
      timeout: 5s
      retries: 5
    
    restart: unless-stopped  # Auto-restart if container crashes (unless manually stopped)

volumes:
  postgres_data:  # Named volume (Docker manages where it's stored)
    driver: local  # Store on local filesystem
```

**Key concepts:**
- **Image**: A template/blueprint for containers (like a class in programming)
- **Container**: A running instance of an image (like an object instance)
- **Volume**: Persistent storage that survives container deletion
- **Port mapping**: Makes container ports accessible from your machine
- **Environment variables**: Configuration passed to the container

### Local Development Tips

- **Stop database**: `docker-compose down` (keeps data in volume)
  - **What it does**: Stops and removes containers, but keeps volumes (your data is safe)
- **Stop and remove data**: `docker-compose down -v` (⚠️ deletes all data)
  - **What it does**: Same as above, but also removes volumes (deletes all database data)
- **View logs**: `docker-compose logs -f postgres`
  - **What it does**: Shows logs from the `postgres` service, `-f` follows (updates in real-time)
- **Restart database**: `docker-compose restart postgres`
  - **What it does**: Restarts the container without recreating it (faster than down/up)
- **Check disk usage**: `docker system df`
  - **What it does**: Shows disk space used by Docker images, containers, and volumes

---

## Deploying on Server with Dokploy

[Dokploy](https://dokploy.com/) is a self-hosted Docker deployment platform (similar to Portainer) that simplifies managing Docker containers on a server. This guide provides two approaches: using Dokploy's web interface or running Docker Compose directly on the server.

### Prerequisites

- **VPS or dedicated server** with:
  - Ubuntu 20.04+ or Debian 11+ (see [Dokploy requirements](https://docs.dokploy.com/docs/core/installation))
  - At least 4GB RAM (8GB+ recommended for 100m grid)
  - Docker and Docker Compose installed
  - SSH access
  - Ports 80, 443, and 3000 available

### Step 1: Prepare Server

```bash
# SSH into your server
ssh user@your-server-ip

# Install Docker (if not already installed)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose plugin (if not already installed)
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect

# Verify installation
docker --version
docker compose version
```

### Step 2: Install Dokploy

```bash
# Run Dokploy installation script
curl -sSL https://dokploy.com/install.sh | sudo sh

# Access Dokploy web interface
# Open browser: http://your-server-ip:3000
# Create admin account on first login
```

**Note**: Dokploy will be accessible on port 3000. For production, consider setting up a domain and reverse proxy.

### Step 3: Upload Project to Server

Choose one of these methods:

**Option A: Using Git (Recommended if repository is on GitHub/GitLab)**
```bash
# On server
ssh user@your-server-ip
cd /opt
git clone <your-repository-url> zensus-database
cd zensus-database
```

**Option B: Using rsync (from your local machine)**
```bash
# On your local machine
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
  ./ user@your-server-ip:/opt/zensus-database/
```

**Option C: Using scp**
```bash
# On your local machine
scp -r ./ user@your-server-ip:/opt/zensus-database/
```

### Step 4: Choose Deployment Method

You have two options for deploying with Dokploy:

---

## Option A: Deploy via Dokploy Web Interface (Recommended for Management)

This approach uses Dokploy's application deployment feature, which provides a web interface for managing your database.

### Step 4A.1: Create Project in Dokploy

1. **Log into Dokploy** web interface (`http://your-server-ip:3000`)

2. **Create a new project**:
   - Click "New Project" or "+" button
   - Name: `zensus-database`
   - Description: `PostGIS database for German Zensus 2022 data`
   - Click "Create"

### Step 4A.2: Deploy Database Container

1. **In your project, click "New Application"** or "Create Service"

2. **Configure the application**:
   - **Name**: `zensus-postgres`
   - **Source Type**: Choose one:
     - **Git Repository**: If your code is in a Git repo, connect it here
     - **Docker Image**: Use `postgis/postgis:15-3.4` directly
     - **Dockerfile**: If you want to customize the image

3. **For Docker Image deployment** (simplest):
   - **Image**: `postgis/postgis:15-3.4`
   - **Container Name**: `zensus_postgres`
   - **Restart Policy**: `unless-stopped`

4. **Set Environment Variables**:
   ```
   POSTGRES_DB=zensus_db
   POSTGRES_USER=zensus_user
   POSTGRES_PASSWORD=your_secure_production_password
   POSTGRES_PORT=5432
   PGDATA=/var/lib/postgresql/data/pgdata
   ```

5. **Configure Ports**:
   - **Container Port**: `5432`
   - **Host Port**: `5432` (or custom port like `5433` if 5432 is in use)

6. **Configure Volumes**:
   - **Persistent Volume**: 
     - Name: `postgres_data`
     - Container Path: `/var/lib/postgresql/data`
   - **Init Scripts Volume** (for schema initialization):
     - Host Path: `/opt/zensus-database/docker/init`
     - Container Path: `/docker-entrypoint-initdb.d`
     - Type: `bind mount`

7. **Health Check** (optional but recommended):
   - **Command**: `pg_isready -U zensus_user -d zensus_db`
   - **Interval**: `10s`
   - **Timeout**: `5s`
   - **Retries**: `5`

8. **Deploy**: Click "Deploy" or "Save" and wait for container to start

### Step 4A.3: Verify Deployment

1. **Check container status** in Dokploy dashboard
2. **View logs** to ensure database initialized correctly
3. **Test connection**:
   ```bash
   # SSH into server
   ssh user@your-server-ip
   docker exec zensus_postgres pg_isready -U zensus_user -d zensus_db
   ```

---

## Option B: Deploy via Docker Compose (Recommended for Simplicity)

This approach runs Docker Compose directly on the server, which is simpler and gives you full control. You can still use Dokploy to monitor the containers.

### Step 4B.1: Setup Environment File

```bash
# On server
ssh user@your-server-ip
cd /opt/zensus-database

# Create .env file
cat > .env << EOF
# Database Configuration
POSTGRES_DB=zensus_db
POSTGRES_USER=zensus_user
POSTGRES_PASSWORD=your_secure_production_password
POSTGRES_PORT=5432

# ETL Script Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=zensus_db
DB_USER=zensus_user
DB_PASSWORD=your_secure_production_password
EOF

# Secure the .env file
chmod 600 .env
```

### Step 4B.2: Start Database with Docker Compose

```bash
# Start database container
docker compose up -d

# Verify container is running
docker compose ps

# Check logs
docker compose logs postgres

# Verify database is ready
docker compose exec postgres pg_isready -U zensus_user -d zensus_db
```

### Step 4B.3: (Optional) Add to Dokploy for Monitoring

Even if you deploy with Docker Compose, you can add the container to Dokploy for monitoring:

1. In Dokploy, go to your project
2. Click "Add Existing Container"
3. Select `zensus_postgres` from the list
4. Dokploy will now show logs, metrics, and allow you to restart from the web interface

### Step 5: Setup Python Environment on Server

```bash
# SSH into server
ssh user@your-server-ip
cd /opt/zensus-database

# Install Python 3.8+ (if not installed)
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Note**: If you used Option B (Docker Compose), you already created the `.env` file in Step 4B.1. If you used Option A (Dokploy web interface), create the `.env` file now:

```bash
# On server
cd /opt/zensus-database
cat > .env << EOF
# Database Configuration (matches Dokploy/Compose environment variables)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=zensus_db
DB_USER=zensus_user
DB_PASSWORD=your_secure_production_password
EOF

# Secure the file
chmod 600 .env
```

**Important**: Use the same password as set in your deployment method (Dokploy environment variables or Docker Compose `.env`).

### Step 6: Generate Schema and Load Data on Server

```bash
# SSH into server
ssh user@your-server-ip
cd /opt/zensus-database

# Activate virtual environment
source venv/bin/activate

# Step 6A: Generate database schema for Zensus tables
# Note: 2>/dev/null redirects status messages to avoid them appearing in the SQL file
python scripts/generate_schema.py data/zensus_data/10km/ 2>/dev/null > schema_10km.sql
python scripts/generate_schema.py data/zensus_data/1km/ 2>/dev/null > schema_1km.sql

# Step 6B: Apply schemas to database
docker-compose exec -T postgres psql -U zensus_user -d zensus_db < schema_10km.sql
docker-compose exec -T postgres psql -U zensus_user -d zensus_db < schema_1km.sql

# Step 6C: Load grid geometries first (required before Zensus data)
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_10km.gpkg 10km
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_1km.gpkg 1km

# Step 6D: Load Zensus data
python etl/load_zensus.py data/zensus_data/10km/
python etl/load_zensus.py data/zensus_data/1km/
```

### Step 7: Configure Network Access (Optional)

If you need to access the database from outside the server:

1. **In Dokploy**: Configure port mapping
   - Map container port `5432` to host port (e.g., `5432` or custom port)

2. **Firewall configuration**:
   ```bash
   # Allow PostgreSQL port (only if needed)
   sudo ufw allow 5432/tcp
   
   # Or restrict to specific IP
   sudo ufw allow from your-ip-address to any port 5432
   ```

3. **Security**: Consider using SSH tunnel instead of exposing port directly:
   ```bash
   # On your local machine
   ssh -L 5432:localhost:5432 user@your-server-ip
   ```

### Step 9: Setup Automated Backups

```bash
# On server, create cron job for daily backups
crontab -e

# Add this line (runs daily at 2 AM):
0 2 * * * cd /opt/zensus-database && /opt/zensus-database/venv/bin/python -c "from scripts.backup import backup; backup()" >> /var/log/zensus_backup.log 2>&1

# Or use the backup script directly:
0 2 * * * /opt/zensus-database/scripts/backup.sh >> /var/log/zensus_backup.log 2>&1
```

### Dokploy Management

**If using Option A (Dokploy Web Interface)**:
- **View logs**: Dokploy web interface → Your project → Application → Logs
- **Restart service**: Dokploy → Your project → Application → Restart
- **Update environment variables**: Dokploy → Your project → Application → Environment → Edit
- **Monitor resources**: Dokploy → Your project → Application → Metrics
- **Access container shell**: Dokploy → Your project → Application → Terminal

**If using Option B (Docker Compose)**:
- **View logs**: `docker compose logs -f postgres`
- **Restart service**: `docker compose restart postgres`
- **Update environment variables**: Edit `.env` file, then `docker compose up -d`
- **Monitor resources**: `docker stats zensus_postgres`
- **Access container shell**: `docker compose exec postgres bash`

### Troubleshooting Dokploy Deployment

1. **Container won't start**:
   - **Option A**: Check logs in Dokploy interface → Application → Logs
   - **Option B**: Check logs with `docker compose logs postgres`
   - Verify environment variables are set correctly
   - Ensure volumes are mounted properly
   - Check if port 5432 is already in use: `sudo lsof -i :5432`

2. **ETL scripts can't connect**:
   - Verify `.env` file has correct database credentials
   - Check if database container is running: `docker ps | grep zensus`
   - Test connection: `docker exec zensus_postgres pg_isready -U zensus_user -d zensus_db`
   - Verify network: If using Docker Compose, ensure scripts run on the same host

3. **Schema not initialized**:
   - Check if init scripts volume is mounted correctly
   - View container logs for SQL execution errors
   - Manually run init scripts: `docker compose exec postgres psql -U zensus_user -d zensus_db -f /docker-entrypoint-initdb.d/02_schema.sql`

4. **Out of memory errors**:
   - Increase server RAM or use smaller grid sizes
   - Monitor memory: `docker stats zensus_postgres`
   - Consider loading only 10km and 1km grids initially

5. **Data not persisting**:
   - **Option A**: Verify volume is mounted in Dokploy → Application → Volumes
   - **Option B**: Check volume: `docker volume ls` and `docker volume inspect zensus-database_postgres_data`
   - Ensure volume path is correct in configuration

6. **Permission errors**:
   - Ensure Docker user has permissions: `sudo usermod -aG docker $USER`
   - Check file permissions on mounted volumes
   - Verify `.env` file permissions: `chmod 600 .env`

---

## Quick Start (Summary)

For a quick local test:

```bash
# 1. Setup
git clone <repo> && cd red_data_database
echo "POSTGRES_PASSWORD=test123" > .env
echo "DB_PASSWORD=test123" >> .env

# 2. Start database
docker-compose up -d

# 3. Install Python deps
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 4. Load test data (10km grid only)
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_10km.gpkg 10km
python etl/load_zensus.py data/zensus_data/10km/

# 5. Query
docker-compose exec postgres psql -U zensus_user -d zensus_db -c "SELECT COUNT(*) FROM zensus.ref_grid_10km;"
```

---

## Accessing the Database

This section explains how to connect to your database from your local machine, whether it's running locally or on a remote server.

### Prerequisites

- **PostgreSQL client tools** installed on your local machine:
  - **macOS**: `brew install postgresql` or `brew install libpq`
  - **Linux**: `sudo apt-get install postgresql-client` (Debian/Ubuntu) or `sudo yum install postgresql` (RHEL/CentOS)
  - **Windows**: Download from [PostgreSQL website](https://www.postgresql.org/download/windows/) or use WSL

- **For GUI tools**: Install one of these (optional):
  - [pgAdmin](https://www.pgadmin.org/) - Official PostgreSQL GUI
  - [DBeaver](https://dbeaver.io/) - Universal database tool
  - [TablePlus](https://tableplus.com/) - Modern database GUI (macOS/Windows)
  - [DataGrip](https://www.jetbrains.com/datagrip/) - Professional IDE (paid)

---

## Accessing Local Database

If you're running the database locally via Docker Compose:

### Method 1: Using psql Command Line

```bash
# Direct connection (if psql is installed locally)
psql -h localhost -p 5432 -U zensus_user -d zensus_db

# Or using Docker (no need to install psql locally)
docker-compose exec postgres psql -U zensus_user -d zensus_db

# Once connected, you can run queries:
SELECT COUNT(*) FROM zensus.ref_grid_1km;
SELECT * FROM zensus.fact_zensus_1km_bevoelkerungszahl LIMIT 10;
\q  # Exit psql
```

**Connection String**:
```
postgresql://zensus_user:your_password@localhost:5432/zensus_db
```

### Method 2: Using GUI Tools (pgAdmin, DBeaver, etc.)

#### pgAdmin Setup

1. **Open pgAdmin** and right-click "Servers" → "Create" → "Server"

2. **General Tab**:
   - Name: `Zensus Local`

3. **Connection Tab**:
   - Host: `localhost`
   - Port: `5432`
   - Database: `zensus_db`
   - Username: `zensus_user`
   - Password: (your password from `.env`)

4. **Click "Save"** and expand the server to browse tables

#### DBeaver Setup

1. **Open DBeaver** → "New Database Connection" → Select "PostgreSQL"

2. **Connection Settings**:
   - Host: `localhost`
   - Port: `5432`
   - Database: `zensus_db`
   - Username: `zensus_user`
   - Password: (your password from `.env`)

3. **Test Connection** → "Finish"

#### TablePlus Setup

1. **Open TablePlus** → "Create a new connection" → "PostgreSQL"

2. **Connection Details**:
   - Name: `Zensus Local`
   - Host: `localhost`
   - Port: `5432`
   - User: `zensus_user`
   - Password: (your password from `.env`)
   - Database: `zensus_db`

3. **Click "Test"** → "Connect"

### Method 3: Using Python (for data analysis)

```python
import pandas as pd
from sqlalchemy import create_engine

# Create connection
engine = create_engine('postgresql://zensus_user:your_password@localhost:5432/zensus_db')

# Query data
df = pd.read_sql("""
    SELECT 
        g.grid_id,
        d.einwohner,
        ST_AsText(ST_Centroid(g.geom)) as centroid
    FROM zensus.ref_grid_1km g
    JOIN zensus.fact_zensus_1km_bevoelkerungszahl d ON g.grid_id = d.grid_id
    WHERE d.einwohner > 1000
    LIMIT 10
""", engine)

print(df)
```

---

## Accessing Remote Database (on Server)

To access the database running on your server, you have several options. **SSH tunneling is recommended** for security.

### Method 1: SSH Tunnel (Recommended - Most Secure)

This method creates a secure tunnel through SSH, so you don't need to expose the database port publicly.

#### Step 1: Create SSH Tunnel

```bash
# On your local machine
ssh -L 5432:localhost:5432 user@your-server-ip

# Keep this terminal open - the tunnel stays active while this session is running
# To run in background:
ssh -f -N -L 5432:localhost:5432 user@your-server-ip
```

**Explanation**:
- `-L 5432:localhost:5432`: Forward local port 5432 to server's localhost:5432
- `-f`: Run in background
- `-N`: Don't execute remote commands (just forward)

**If server uses different port**:
```bash
ssh -L 5432:localhost:5432 -p 2222 user@your-server-ip
```

#### Step 2: Connect Using Local Tools

Once the tunnel is active, connect as if the database is local:

```bash
# Using psql
psql -h localhost -p 5432 -U zensus_user -d zensus_db

# Connection string for GUI tools
postgresql://zensus_user:your_password@localhost:5432/zensus_db
```

**Note**: Use the same connection settings as "Accessing Local Database" above - the SSH tunnel makes the remote database appear local.

### Method 2: Direct Connection (Less Secure)

**⚠️ Warning**: Only use this if you've configured firewall rules and understand the security implications.

#### Step 1: Configure Server Firewall

```bash
# On server, allow PostgreSQL port (restrict to your IP for security)
sudo ufw allow from YOUR_LOCAL_IP_ADDRESS to any port 5432

# Or allow from specific IP range
sudo ufw allow from 192.168.1.0/24 to any port 5432
```

#### Step 2: Configure PostgreSQL to Accept Remote Connections

**Note**: If using Docker, PostgreSQL is already configured. You just need to ensure the port is mapped.

For non-Docker installations:
```bash
# On server, edit PostgreSQL config
sudo nano /etc/postgresql/15/main/postgresql.conf

# Find and uncomment/modify:
listen_addresses = '*'  # or specific IP

# Edit pg_hba.conf to allow connections
sudo nano /etc/postgresql/15/main/pg_hba.conf

# Add line (replace with your IP):
host    zensus_db    zensus_user    YOUR_LOCAL_IP_ADDRESS/32    md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

#### Step 3: Connect from Local Machine

```bash
# Using psql
psql -h your-server-ip -p 5432 -U zensus_user -d zensus_db

# Connection string
postgresql://zensus_user:your_password@your-server-ip:5432/zensus_db
```

### Method 3: Using GUI Tools with SSH Tunnel

Most GUI tools support SSH tunneling:

#### pgAdmin with SSH Tunnel

1. **Create Server** → **Connection Tab**
2. **Enable "Use SSH tunneling"**
3. **SSH Tunnel Tab**:
   - Tunnel host: `your-server-ip`
   - Tunnel port: `22` (or your SSH port)
   - Username: `user` (your SSH username)
   - Authentication: Password or SSH key
4. **Connection Tab**:
   - Host: `localhost` (not server IP!)
   - Port: `5432`
   - Database: `zensus_db`
   - Username: `zensus_user`
   - Password: (database password)

#### DBeaver with SSH Tunnel

1. **New Connection** → **PostgreSQL**
2. **Main Tab**:
   - Host: `localhost` (not server IP!)
   - Port: `5432`
   - Database: `zensus_db`
   - Username: `zensus_user`
   - Password: (database password)
3. **SSH Tab**:
   - Enable "Use SSH Tunnel"
   - Host: `your-server-ip`
   - Port: `22`
   - User: `user` (SSH username)
   - Authentication: Password or key file

#### TablePlus with SSH Tunnel

1. **New Connection** → **PostgreSQL**
2. **Connection Tab**:
   - Host: `localhost`
   - Port: `5432`
   - Database: `zensus_db`
   - User: `zensus_user`
   - Password: (database password)
3. **SSH Tab**:
   - Enable "Use SSH tunnel"
   - Host: `your-server-ip`
   - Port: `22`
   - User: `user` (SSH username)
   - Authentication: Password or key

### Method 4: Using Python with SSH Tunnel

```python
import pandas as pd
from sqlalchemy import create_engine
import sshtunnel

# Create SSH tunnel
with sshtunnel.SSHTunnelForwarder(
    ('your-server-ip', 22),
    ssh_username='user',
    ssh_password='ssh_password',  # or use ssh_pkey for key-based auth
    remote_bind_address=('localhost', 5432),
    local_bind_address=('localhost', 5433)  # Local port
) as tunnel:
    
    # Connect through tunnel
    engine = create_engine(
        'postgresql://zensus_user:db_password@localhost:5433/zensus_db'
    )
    
    # Query data
    df = pd.read_sql("SELECT * FROM zensus.ref_grid_1km LIMIT 10", engine)
    print(df)
```

**Install SSH tunnel library**:
```bash
pip install sshtunnel
```

---

## Connection String Reference

### Local Database
```
postgresql://zensus_user:password@localhost:5432/zensus_db
```

### Remote Database (Direct)
```
postgresql://zensus_user:password@your-server-ip:5432/zensus_db
```

### Remote Database (via SSH Tunnel)
```
postgresql://zensus_user:password@localhost:5432/zensus_db
```
(SSH tunnel must be active separately)

### With Schema
```
postgresql://zensus_user:password@localhost:5432/zensus_db?options=-csearch_path%3Dzensus
```

---

## Useful Database Queries

Once connected, here are some useful queries to explore your data:

```sql
-- List all tables in zensus schema
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'zensus'
ORDER BY table_name;

-- Count rows in reference tables
SELECT 
    'ref_grid_10km' as table_name, COUNT(*) as row_count 
FROM zensus.ref_grid_10km
UNION ALL
SELECT 'ref_grid_1km', COUNT(*) FROM zensus.ref_grid_1km
UNION ALL
SELECT 'ref_grid_100m', COUNT(*) FROM zensus.ref_grid_100m;

-- List all fact tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'zensus' 
AND table_name LIKE 'fact_zensus%'
ORDER BY table_name;

-- Sample data from a fact table
SELECT * FROM zensus.fact_zensus_1km_bevoelkerungszahl LIMIT 10;

-- Join grid geometry with population data
SELECT 
    g.grid_id,
    ST_AsText(ST_Centroid(g.geom)) as centroid,
    d.einwohner
FROM zensus.ref_grid_1km g
JOIN zensus.fact_zensus_1km_bevoelkerungszahl d ON g.grid_id = d.grid_id
WHERE d.einwohner > 1000
ORDER BY d.einwohner DESC
LIMIT 10;
```

---

## Security Best Practices

1. **Always use SSH tunnels** for remote access when possible
2. **Never expose PostgreSQL port publicly** without firewall restrictions
3. **Use strong passwords** for both database and SSH
4. **Limit database user permissions** - create read-only users for analysis
5. **Use SSL/TLS** for direct connections (configure `sslmode=require` in connection string)
6. **Regularly update** PostgreSQL and server security patches

---

## Troubleshooting Connections

### "Connection refused" Error

**Local database**:
- Check if container is running: `docker compose ps`
- Verify port mapping: `docker compose port postgres 5432`
- Check logs: `docker compose logs postgres`

**Remote database**:
- Verify SSH tunnel is active: `ps aux | grep ssh`
- Check firewall rules: `sudo ufw status`
- Test SSH connection: `ssh user@server-ip`

### "Authentication failed" Error

- Verify username and password match `.env` file
- Check PostgreSQL user exists: `docker compose exec postgres psql -U postgres -c "\du"`
- Reset password if needed: `docker compose exec postgres psql -U postgres -c "ALTER USER zensus_user PASSWORD 'new_password';"`

### "Database does not exist" Error

- List databases: `docker compose exec postgres psql -U postgres -c "\l"`
- Verify database name matches: should be `zensus_db`

### "Connection timeout" (Remote)

- Check if port is open: `telnet your-server-ip 5432` (or use `nc`)
- Verify firewall allows your IP
- Check if PostgreSQL is listening: `sudo netstat -tlnp | grep 5432` (on server)

---

## Data Preprocessing

The ETL scripts automatically handle German data format:

1. **Decimal Numbers**: Converts comma separators to dots (`"129,1"` → `129.1`)
2. **Missing Values**: Converts em dash (`"–"`) to `NULL`
3. **Grid ID Validation**: Validates that `grid_id` exists in reference tables before insertion

## Database Schema

### Reference Tables

- `zensus.ref_grid_100m`: 100m grid cell geometries
- `zensus.ref_grid_1km`: 1km grid cell geometries
- `zensus.ref_grid_10km`: 10km grid cell geometries

### Fact Tables

- `zensus.fact_zensus_1km_demography`: Population counts (1km)
- `zensus.fact_zensus_10km_demography`: Population counts (10km)
- `zensus.fact_zensus_1km_age_5klassen`: Age groups (1km)
- `zensus.fact_zensus_10km_age_5klassen`: Age groups (10km)
- `zensus.fact_zensus_1km_durchschnittsalter`: Average age (1km)
- `zensus.fact_zensus_10km_durchschnittsalter`: Average age (10km)
- `zensus.fact_zensus_1km_miete`: Average rent (1km)
- `zensus.fact_zensus_10km_miete`: Average rent (10km)

All geometries use **EPSG:3035** (ETRS89-LAEA).

## Data Quality Tests

### dbt Tests

Run dbt tests to verify data quality:

```bash
cd tests/dbt
dbt deps  # Install dbt packages
dbt test
```

Tests include:
- Uniqueness and not-null constraints
- Foreign key relationships
- Geometry validity and SRID checks
- Value range checks

### SQL Quality Checks

Run manual quality checks:

```bash
psql -h localhost -U zensus_user -d zensus_db -f tests/sql/quality_checks.sql
```

## Example Queries

### Count population by grid cell

```sql
SELECT 
    g.grid_id,
    ST_AsText(ST_Centroid(g.geom)) AS centroid,
    d.einwohner
FROM zensus.ref_grid_1km g
JOIN zensus.fact_zensus_1km_demography d ON g.grid_id = d.grid_id
WHERE d.einwohner > 1000
ORDER BY d.einwohner DESC
LIMIT 10;
```

### Spatial query: Find grid cells within a bounding box

```sql
SELECT 
    g.grid_id,
    d.einwohner,
    ST_AsGeoJSON(g.geom) AS geometry
FROM zensus.ref_grid_1km g
JOIN zensus.fact_zensus_1km_demography d ON g.grid_id = d.grid_id
WHERE ST_Intersects(
    g.geom,
    ST_MakeEnvelope(4300000, 2680000, 4400000, 2700000, 3035)
);
```

## Backup and Restore

### Create Backup

```bash
./scripts/backup.sh
```

Backups are stored in `./backups/` directory with timestamps.

### Restore from Backup

```bash
./scripts/restore.sh backups/zensus_backup_20240101_120000.dump
```

**Warning**: Restore will overwrite existing data!

## Security

### Create Application Roles

For production deployment, create non-superuser roles:

```bash
psql -h localhost -U postgres -d zensus_db -f scripts/create_roles.sql
```

**Important**: Change default passwords in `scripts/create_roles.sql` before running!

### Security Best Practices

1. **Never expose PostgreSQL port publicly** - Use SSH tunnels or VPN
2. **Use strong passwords** - Change default passwords in `.env` and `create_roles.sql`
3. **Limit network access** - Configure firewall rules on the server
4. **Regular backups** - Schedule automated backups using cron
5. **Monitor access logs** - Review PostgreSQL logs regularly

## Additional Deployment Options

### Traditional Server Deployment (without Dokploy)

If you prefer not to use Dokploy, you can deploy directly on a Linux server:

1. **Copy project to server**:
   ```bash
   rsync -avz ./ user@server:/opt/zensus-database/
   ```

2. **SSH into server and follow local setup steps** (Steps 1-8 from "Running Locally" section)

3. **Configure as systemd service** (optional, for auto-start):
   ```bash
   # Create systemd service file
   sudo nano /etc/systemd/system/zensus-db.service
   ```
   
   Add:
   ```ini
   [Unit]
   Description=Zensus PostgreSQL Database
   Requires=docker.service
   After=docker.service
   
   [Service]
   Type=oneshot
   RemainAfterExit=yes
   WorkingDirectory=/opt/zensus-database
   ExecStart=/usr/bin/docker compose up -d
   ExecStop=/usr/bin/docker compose down
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   Enable service:
   ```bash
   sudo systemctl enable zensus-db
   sudo systemctl start zensus-db
   ```

See the **"Deploying on Server with Dokploy"** section above for detailed server deployment instructions using Dokploy (recommended for easier management).

## Troubleshooting

### Database connection issues

- Verify Docker container is running: `docker-compose ps`
- Check logs: `docker-compose logs postgres`
- Verify environment variables in `.env`

### ETL script errors

- Check `etl.log` for detailed error messages
- Verify CSV file paths are correct
- Ensure grid geometries are loaded before loading Zensus data
- Check database connection settings

### Geometry errors

- Verify GPKG files have valid geometries
- Check that CRS is EPSG:3035 or can be reprojected
- Review PostGIS logs for geometry validation errors

## Project Structure

```
red_data_database/
├── docker/
│   └── init/
│       ├── 01_extensions.sql      # PostGIS extension
│       ├── 02_schema.sql           # Table definitions
│       └── 03_indexes.sql          # Indexes and constraints
├── etl/
│   ├── load_grids.py              # Load GeoGitter GPKG files
│   ├── load_zensus.py              # Load Zensus CSV files
│   └── utils.py                    # Shared utilities
├── tests/
│   ├── dbt/                        # dbt test configuration
│   └── sql/
│       └── quality_checks.sql      # Manual quality checks
├── scripts/
│   ├── backup.sh                   # Backup script
│   ├── restore.sh                  # Restore script
│   └── create_roles.sql           # Role creation
├── docker-compose.yml              # Docker setup
├── requirements.txt               # Python dependencies
└── README.md                       # This file
```

## Future Extensions

The schema includes placeholders for:

- **100m grid**: Currently skipped, can be added when data is available
- **Election data**: Wahlkreis and Wahlbezirk tables (commented in schema)
- **Bridge tables**: Precomputed spatial intersections

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Contact

[Add contact information here]

