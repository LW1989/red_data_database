# Deploying German Zensus 2022 Database on Dokploy

This guide walks you through deploying the PostGIS-enabled German Zensus database on Dokploy using the web interface. Dokploy is a self-hosted PaaS (Platform as a Service) that simplifies Docker container management.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Deployment Overview](#deployment-overview)
- [Method 1: Using Dokploy's Native Database Feature (Recommended)](#method-1-using-dokploys-native-database-feature-recommended)
- [Method 2: Using Dokploy's Compose Feature](#method-2-using-dokploys-compose-feature)
- [Post-Deployment: Loading Data](#post-deployment-loading-data)
- [Accessing Your Database](#accessing-your-database)
- [Backup and Maintenance](#backup-and-maintenance)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Server Requirements

- **Dokploy Instance**: Access to a running Dokploy installation (managed by your team)
  - Dokploy web interface accessible
  - Appropriate permissions to create projects and databases

- **Server Specifications** (for database):
  - Ubuntu 20.04+ or Debian 11+
  - Minimum 4GB RAM (8GB+ recommended for large datasets)
  - 50GB+ storage (depends on grid size: 10km ≈ 2GB, 1km ≈ 20GB, 100m ≈ 200GB)
  
- **Network Access**:
  - SSH access to your server
  - Port 5432 available for PostgreSQL (or custom port)

### Local Requirements

- SSH client (Terminal on macOS/Linux, PuTTY on Windows)
- Git (for cloning repository)
- PostgreSQL client tools (optional, for testing connections)

---

## Deployment Overview

This guide assumes Dokploy is already installed and running on your server.

**📝 Keep Track of Your Settings**: As you go through this guide, you'll set several values. Write them down:

```
Project Name:    _______________________
Database Name:   _______________________  (e.g., red-data-db)
Database User:   _______________________  (e.g., zensus_user)
Database Password: _____________________  (keep this secure!)
Docker Image:    postgis/postgis:15-3.4  (don't change this!)
```

You'll need these values when:
- Connecting to the database
- Configuring the `.env` file for data loading scripts
- Setting up backups and monitoring

---

The deployment process consists of:

1. **Access Dokploy** web interface
2. **Deploy PostGIS database** via Dokploy
3. **Upload project files** to server
4. **Load census data** using ETL scripts
5. **Configure access** and backups

**Estimated Time**: 30-60 minutes (excluding data loading, which varies by grid size)

---

## 🚨 Don't Have SSH Access? Read This First!

If you **don't have SSH access** to the server, you'll need to **collaborate with your colleague** who manages Dokploy. Here's the workflow:

### What You Can Do in Dokploy (No SSH Needed):
1. ✅ Create database via web interface (Steps 1-2)
2. ✅ Configure database settings (image, credentials, ports)
3. ✅ Enable PostGIS extension via Dokploy terminal (Step 4)
4. ✅ Monitor database status and logs

### What Requires Server Access (Ask Your Colleague):
1. ❓ Upload project files to `/opt/zensus-database/`
2. ❓ Upload census data files to `/opt/zensus-database/data/`
3. ❓ Install Python dependencies
4. ❓ Create `.env` configuration file
5. ❓ Run ETL scripts to load data

### Recommended Approach:

**Option 1: Full Collaboration**
- You: Create and configure database in Dokploy
- Colleague: Handle file uploads and run ETL scripts
- You: Verify data and connect for analysis

**Option 2: Use Dokploy's Git Integration**
- You: Set up Git repository deployment in Dokploy (no SSH needed)
- Colleague: Upload data files and run scripts
- You: Monitor via Dokploy interface

**Option 3: Request Setup Script Execution**
- Provide your colleague with the automated `setup_database.sh` script
- They run it once, and everything is loaded automatically
- You connect and start analyzing

**💡 Tip**: Share this deployment guide with your colleague - it has all the commands they'll need!

---

## Method 1: Using Dokploy's Native Database Feature (Recommended)

This method uses Dokploy's built-in database management, which provides a clean UI for monitoring, backups, and configuration.

### Step 1: Access Dokploy

1. **Open Dokploy web interface** in your browser (URL provided by your colleague/admin)
2. **Log in** with your credentials

### Step 2: Create a Project

1. **Click "Projects"** in the left sidebar

2. **Click "Create Project"** button
   - **Name**: `red-data` (or `zensus-database`)
   - **Description**: `PostGIS database for German Zensus 2022 census data, administrative boundaries, and electoral districts`
   - Click **"Create"**

### Step 3: Create PostgreSQL Database

1. **Inside your project**, click **"Create Service"** → **"Database"**

2. **Select "PostgreSQL"** from database types

3. **Configure Database Settings**:

   | Field | Value | Notes |
   |-------|-------|-------|
   | **Name** | `red-data` | Project name in Dokploy |
   | **App Name** | `datahub-reddata` | Application identifier |
   | **Description** | `Spatial database for German census and electoral data` | Optional but helpful |
   | **Database Name** | `red-data-db` | Name of the PostgreSQL database (or `zensus_db`) |
   | **Database User** | `zensus_user` | Database user |
   | **Database Password** | `[generate strong password]` | Save this securely! |
   | **Docker Image** | `postgis/postgis:15-3.4` | **⚠️ Important: Use PostGIS, not default postgres** |
   | **Port** | `5432` | Internal port (leave default) |

   **⚠️ Critical**: Make sure to change the **Docker Image** field from `postgres:15` to `postgis/postgis:15-3.4` to enable spatial/GIS functionality!

4. **Click "Create"** to initialize the database

### Step 4: Enable PostGIS Extension

After the database is deployed, you need to activate the PostGIS extension:

1. **In Dokploy**, go to your database service
2. **Click "Terminal"** tab to open database shell
3. **Connect to database**:
   ```bash
   psql -U zensus_user -d red-data-db
   ```
   (Replace `red-data-db` with your actual database name if different)

4. **Enable PostGIS extension**:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE EXTENSION IF NOT EXISTS postgis_topology;
   ```

5. **Verify installation**:
   ```sql
   SELECT PostGIS_Full_Version();
   ```
   You should see PostGIS version information like:
   ```
   POSTGIS="3.4.0" [EXTENSION] PGSQL="150" GEOS="3.11.1" PROJ="9.1.1" ...
   ```

**Note**: Since you used the `postgis/postgis:15-3.4` image, PostGIS is already installed - you just need to enable the extension in your database.

### Step 5: Configure External Access (Optional)

If you need to access the database from outside the server (e.g., from your local machine):

1. **In database settings**, find **"External Port"** section
2. **Enable external access** and set port (e.g., `5432` or custom like `5433`)
3. **Click "Save"**
4. **Configure firewall** on server:
   ```bash
   # Allow PostgreSQL port (replace YOUR_IP with your IP address)
   sudo ufw allow from YOUR_IP to any port 5432
   
   # Or allow from anywhere (less secure)
   sudo ufw allow 5432/tcp
   ```

**🔒 Security Recommendation**: Use SSH tunneling instead of exposing the database port publicly (see [Accessing Your Database](#accessing-your-database) section).

### Step 6: Deploy Database

1. **Click "Deploy"** button in the database service
2. **Monitor logs** to ensure successful startup
3. **Verify status**: Service should show as "Running" (green indicator)

### Step 7: Configure Database Volumes (Important for Persistence)

1. **In database settings**, go to **"Volumes"** tab
2. **Verify the following volumes are configured**:
   
   | Volume Type | Container Path | Purpose |
   |-------------|----------------|---------|
   | **Named Volume** | `/var/lib/postgresql/data` | Database data persistence |
   | **Bind Mount** | `/docker-entrypoint-initdb.d` | Schema initialization scripts |

3. **For bind mount** (schema scripts):
   - **Host Path**: `/opt/zensus-database/docker/init`
   - **Container Path**: `/docker-entrypoint-initdb.d`
   - **Mode**: Read-only

**Note**: Bind mount setup requires project files on server (see [Step 3](#step-3-upload-project-to-server)).

---

## Method 2: Using Dokploy's Compose Feature

This method deploys the database using the existing `docker-compose.yml` file from this repository. Useful if you want full control over the Docker configuration.

### Step 1-2: Access Dokploy and Create Project

Follow Steps 1-2 from Method 1 above.

### Step 3: Create Compose Service

1. **Inside your project**, click **"Create Service"** → **"Compose"**

2. **Configure Service**:
   - **Name**: `zensus-database`
   - **Source Type**: Choose one:
     - **Git Repository**: If your code is on GitHub/GitLab
     - **Raw Compose**: Paste docker-compose.yml content directly

### Step 4: Configure Compose Source

**Option A: Using Git Repository**

1. **Select "Git Repository"**

2. **Configure Git Settings**:
   - **Repository URL**: `https://github.com/YOUR_USERNAME/red_data_database.git`
   - **Branch**: `master` or `main`
   - **Compose File Path**: `docker-compose.yml` (default)
   
3. **Add Authentication** (if private repo):
   - Username/Password or
   - SSH Key

4. **Click "Create"**

**Option B: Using Raw Compose**

1. **Select "Raw Compose"**

2. **Paste your docker-compose.yml content**:
   ```yaml
   version: '3.8'
   
   services:
     postgres:
       image: postgis/postgis:15-3.4
       container_name: zensus_postgres
       restart: unless-stopped
       environment:
         POSTGRES_DB: ${POSTGRES_DB:-zensus_db}
         POSTGRES_USER: ${POSTGRES_USER:-zensus_user}
         POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
         POSTGRES_PORT: ${POSTGRES_PORT:-5432}
         PGDATA: /var/lib/postgresql/data/pgdata
       ports:
         - "${POSTGRES_PORT:-5432}:5432"
       volumes:
         - postgres_data:/var/lib/postgresql/data
         - ./docker/init:/docker-entrypoint-initdb.d:ro
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-zensus_user} -d ${POSTGRES_DB:-zensus_db}"]
         interval: 10s
         timeout: 5s
         retries: 5
   
   volumes:
     postgres_data:
       driver: local
   ```

3. **Click "Create"**

### Step 5: Configure Environment Variables

1. **Go to "Environment"** tab

2. **Add the following variables**:
   ```
   POSTGRES_DB=zensus_db
   POSTGRES_USER=zensus_user
   POSTGRES_PASSWORD=your_secure_production_password
   POSTGRES_PORT=5432
   ```

3. **Click "Save"**

### Step 6: Deploy Compose Stack

1. **Click "Deploy"** button
2. **Monitor logs** for successful deployment
3. **Verify status**: All services should show as "Running"

---

## Step 3: Upload Project to Server

You need to get the project files (ETL scripts, schema files, etc.) onto your server to load data.

### Option A: Using Dokploy's Git Integration (Recommended - No SSH Required)

If your project is on GitHub/GitLab and you **don't have SSH access**, use Dokploy to clone the repository:

1. **In Dokploy**, go to your project
2. **Click "Create Service"** → Select **"Application"**
3. **Configure Application**:
   - **Name**: `zensus-etl-scripts`
   - **Source Type**: **Git Repository**
   - **Repository URL**: `https://github.com/YOUR_USERNAME/red_data_database.git`
   - **Branch**: `master` or `main`
   - **Build Path**: `/` (root)
   
4. **Important Settings**:
   - **Autodeploy**: Enable if you want automatic updates on git push
   - **Build Command**: Leave empty (we're not building, just cloning files)
   - **Deploy**: You can skip deploying this as a service - we just need the files

5. **Alternative: Work with Your Colleague**
   
   If Dokploy's Git integration doesn't fit your workflow, **ask your colleague who manages the server** to:
   
   ```bash
   # They can run these commands via SSH:
   sudo mkdir -p /opt/zensus-database
   sudo chown $USER:$USER /opt/zensus-database
   cd /opt/zensus-database
   git clone https://github.com/YOUR_USERNAME/red_data_database.git .
   ```

### Option B: Using SSH (If You Have Access)

```bash
# SSH into server
ssh your-username@your-server-ip

# Create project directory
sudo mkdir -p /opt/zensus-database
sudo chown $USER:$USER /opt/zensus-database
cd /opt/zensus-database

# Clone repository
git clone https://github.com/YOUR_USERNAME/red_data_database.git .
```

### Option C: Using File Transfer Tools (From Local Machine)

**Using rsync**:
```bash
# On your local machine (not on server)
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
  /path/to/local/red_data_database/ \
  your-username@your-server-ip:/opt/zensus-database/
```

**Using scp**:
```bash
# On your local machine
scp -r /path/to/local/red_data_database \
  your-username@your-server-ip:/opt/zensus-database/
```

### Verify Files Are on Server

**If you have SSH access**:
```bash
# On server
cd /opt/zensus-database
ls -la

# You should see:
# docker/
# etl/
# scripts/
# data/
# docker-compose.yml
# requirements.txt
# README.md
```

**If you don't have SSH access**:
- Ask your colleague to verify the files were cloned successfully
- Check Dokploy's file browser (if available) for the application you created

---

## Step 4: Upload Census Data to Server

The census data files are large (10km ≈ 2GB, 1km ≈ 20GB) and need to be uploaded separately.

### Option A: Ask Your Colleague (Recommended if No SSH Access)

If you don't have SSH/SFTP access:

1. **Provide your colleague with**:
   - Link to download census data files
   - Or send them a shared drive link (Google Drive, Dropbox, etc.)
   - Expected directory structure (see below)

2. **Ask them to place files in**: `/opt/zensus-database/data/`

### Option B: Using File Transfer (If You Have Access)

**Using rsync** (recommended for large files - supports resume):
```bash
# On your local machine
rsync -avz --progress \
  /path/to/local/data/ \
  your-username@your-server-ip:/opt/zensus-database/data/
```

**Using scp**:
```bash
# On your local machine
scp -r /path/to/local/data \
  your-username@your-server-ip:/opt/zensus-database/
```

**Using SFTP client** (GUI tools like FileZilla, Cyberduck):
- Connect to server via SFTP
- Navigate to `/opt/zensus-database/`
- Upload `data/` folder

**Expected data structure**:
```
/opt/zensus-database/data/
├── geo_data/
│   ├── DE_Grid_ETRS89-LAEA_10km.gpkg
│   ├── DE_Grid_ETRS89-LAEA_1km.gpkg
│   └── DE_Grid_ETRS89-LAEA_100m.gpkg
├── zensus_data/
│   ├── 10km/
│   ├── 1km/
│   └── 100m/
├── vg250_ebenen_0101/
├── bundestagswahlen/
└── luw_berlin/
```

### Verify Data Upload

**If you have SSH access**:
```bash
# On server
du -sh /opt/zensus-database/data/*

# You should see sizes like:
# 150M    data/geo_data
# 2.5G    data/zensus_data/10km
# 25G     data/zensus_data/1km
# etc.
```

**If you don't have SSH access**:
- Ask your colleague to verify the file sizes
- Or check Dokploy's file browser (if available)

---

## Step 5: Setup Python Environment on Server

This step prepares the Python environment to run the ETL scripts that load data into your database.

### If You Have SSH Access:

```bash
# SSH into server
ssh your-username@your-server-ip
cd /opt/zensus-database

# Install Python 3.8+ (if not installed)
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt
```

### If You DON'T Have SSH Access:

**Ask your colleague to run the setup commands**, or provide them with this setup script:

```bash
#!/bin/bash
# Python environment setup script for red_data_database

cd /opt/zensus-database

# Install Python dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

echo "Python environment setup complete!"
```

### Create Environment Configuration

**If you have SSH access**:
```bash
# Create .env file for ETL scripts
cat > .env << 'EOF'
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=red-data-db
DB_USER=zensus_user
DB_PASSWORD=your_secure_production_password
EOF

# Secure the .env file
chmod 600 .env
```

**If you don't have SSH access**:

Ask your colleague to create a file `/opt/zensus-database/.env` with this content:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=red-data-db
DB_USER=zensus_user
DB_PASSWORD=your_actual_password_here
```

**⚠️ Important Configuration Notes**: 
- Replace `your_actual_password_here` with the actual password you set in Dokploy
- Replace `red-data-db` with your actual database name if different (e.g., `zensus_db`)
- `DB_HOST=localhost` works because ETL scripts run on the same server as the database
- `DB_PORT=5432` is the internal Docker port (not the external port if you configured one)

---

## Step 6: Load Data into Database

**🔑 Note About Access**: Loading data requires running commands on the server. If you don't have SSH access, **coordinate with your colleague** to run these commands, or ask them to set up a scheduled task/cron job in Dokploy.

### Option A: Using Automated Setup Script (Recommended)

The repository includes an automated setup script that handles all data loading:

**If you have SSH access**:
```bash
# SSH into server
ssh your-username@your-server-ip
cd /opt/zensus-database
source venv/bin/activate

# Make script executable
chmod +x setup_database.sh

# Run setup (test mode - 10km only, ~5-10 minutes)
./setup_database.sh --test

# Or full setup (10km + 1km, ~30-60 minutes)
./setup_database.sh --full

# Or skip optional data
./setup_database.sh --full --skip-vg250 --skip-elections
```

**If you don't have SSH access**, share these commands with your colleague to run:
```bash
cd /opt/zensus-database
source venv/bin/activate
chmod +x setup_database.sh
./setup_database.sh --test  # Start with test mode
```

**What the script does**:
1. ✅ Verifies database connection
2. ✅ Generates and applies schemas
3. ✅ Loads grid geometries
4. ✅ Loads Zensus census data
5. ✅ Loads VG250 administrative boundaries (optional)
6. ✅ Loads Bundestagswahlen election data (optional)
7. ✅ Loads LWU Berlin properties (optional)
8. ✅ Verifies all data was loaded correctly

### 6.2 Option B: Manual Step-by-Step Loading

If you prefer manual control:

#### Step 6.2.1: Apply Base Schema

```bash
# Activate virtual environment
source venv/bin/activate

# Get container name (if using Dokploy's native database)
CONTAINER_NAME=$(docker ps --filter "name=zensus" --format "{{.Names}}")

# Apply base schema
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < docker/init/01_schema.sql
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < docker/init/02_zensus_reference_grids.sql
```

#### Step 6.2.2: Load Grid Geometries

```bash
# Load 10km grid
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_10km.gpkg 10km

# Load 1km grid (optional, takes longer)
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_1km.gpkg 1km
```

#### Step 6.2.3: Generate and Apply Zensus Schemas

```bash
# Generate schema for 10km data
python scripts/generate_schema.py data/zensus_data/10km/ > schema_10km.sql

# Apply schema
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < schema_10km.sql

# Repeat for 1km if needed
python scripts/generate_schema.py data/zensus_data/1km/ > schema_1km.sql
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < schema_1km.sql
```

#### Step 6.2.4: Load Zensus Data

```bash
# Load 10km census data
python etl/load_zensus.py data/zensus_data/10km/

# Load 1km census data (optional)
python etl/load_zensus.py data/zensus_data/1km/
```

#### Step 6.2.5: Load Optional Datasets

```bash
# VG250 administrative boundaries
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < docker/init/03_vg250_schema.sql
python etl/load_vg250.py data/vg250_ebenen_0101

# Bundestagswahlen election data
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < docker/init/04_bundestagswahlen_schema.sql
python etl/load_elections.py --shapefile data/bundestagswahlen/btw2017/[shapefile].shp \
                              --csv data/bundestagswahlen/btw2017/[csv].csv \
                              --election-year 2017

# LWU Berlin properties
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < docker/init/05_lwu_properties_schema.sql
python etl/load_lwu_properties.py data/luw_berlin/lwu_berlin_small.geojson
```

### 6.3 Verify Data Loading

```bash
# Connect to database
docker exec -it $CONTAINER_NAME psql -U zensus_user -d zensus_db

# Run verification queries
\dt zensus.*

# Count rows in key tables
SELECT 'ref_grid_10km' as table_name, COUNT(*) as rows FROM zensus.ref_grid_10km
UNION ALL
SELECT 'ref_grid_1km', COUNT(*) FROM zensus.ref_grid_1km
UNION ALL
SELECT 'ref_federal_state', COUNT(*) FROM zensus.ref_federal_state
UNION ALL
SELECT 'ref_county', COUNT(*) FROM zensus.ref_county
UNION ALL
SELECT 'ref_lwu_properties', COUNT(*) FROM zensus.ref_lwu_properties;

# Exit
\q
```

**Expected results**:
- `ref_grid_10km`: ~11,000 cells
- `ref_grid_1km`: ~900,000 cells
- `ref_federal_state`: 34 states
- `ref_county`: 433 counties
- `ref_lwu_properties`: 5,468 properties

---

## Accessing Your Database

### From Within the Server

```bash
# Get container name
CONTAINER_NAME=$(docker ps --filter "name=zensus" --format "{{.Names}}")

# Connect via psql
docker exec -it $CONTAINER_NAME psql -U zensus_user -d zensus_db
```

### From Your Local Machine

#### Option 1: SSH Tunnel (Recommended - Most Secure)

```bash
# On your local machine
ssh -L 5432:localhost:5432 your-username@your-server-ip

# Keep this terminal open, then in another terminal:
psql -h localhost -p 5432 -U zensus_user -d zensus_db
```

#### Option 2: Direct Connection (if external port is configured)

```bash
# On your local machine
psql -h your-server-ip -p 5432 -U zensus_user -d zensus_db
```

### Using GUI Tools (pgAdmin, DBeaver, TablePlus)

**pgAdmin Setup with SSH Tunnel**:
1. Create new server → **SSH Tunnel** tab
2. **Tunnel host**: `your-server-ip`
3. **Tunnel port**: `22`
4. **Username**: `your-username`
5. **Authentication**: SSH key or password
6. **Connection** tab:
   - Host: `localhost` (not server IP!)
   - Port: `5432`
   - Database: `zensus_db`
   - Username: `zensus_user`
   - Password: [your database password]

**DBeaver Setup**:
1. New Connection → PostgreSQL
2. **Main** tab:
   - Host: `localhost`
   - Port: `5432`
   - Database: `zensus_db`
   - Username: `zensus_user`
3. **SSH** tab:
   - ✓ Use SSH Tunnel
   - Host: `your-server-ip`
   - Port: `22`
   - User: `your-username`

### Connection String

```
# Local (with SSH tunnel)
postgresql://zensus_user:password@localhost:5432/zensus_db

# Direct (if external access enabled)
postgresql://zensus_user:password@your-server-ip:5432/zensus_db
```

---

## Backup and Maintenance

### Manual Backup

```bash
# SSH into server
ssh your-username@your-server-ip
cd /opt/zensus-database

# Create backup directory
mkdir -p backups

# Backup database
docker exec $CONTAINER_NAME pg_dump -U zensus_user -d zensus_db -F c -f /tmp/backup.dump

# Copy backup out of container
docker cp $CONTAINER_NAME:/tmp/backup.dump backups/zensus_db_$(date +%Y%m%d).dump
```

### Automated Backups via Cron

```bash
# Create backup script
cat > /opt/zensus-database/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/zensus-database/backups"
DATE=$(date +%Y%m%d_%H%M%S)
CONTAINER=$(docker ps --filter "name=zensus" --format "{{.Names}}")

mkdir -p $BACKUP_DIR
docker exec $CONTAINER pg_dump -U zensus_user -d zensus_db -F c > $BACKUP_DIR/zensus_db_$DATE.dump

# Keep only last 7 backups
ls -t $BACKUP_DIR/zensus_db_*.dump | tail -n +8 | xargs rm -f

echo "Backup completed: zensus_db_$DATE.dump"
EOF

# Make executable
chmod +x /opt/zensus-database/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e

# Add this line:
0 2 * * * /opt/zensus-database/backup.sh >> /var/log/zensus_backup.log 2>&1
```

### Restore from Backup

```bash
# List backups
ls -lh /opt/zensus-database/backups/

# Restore specific backup
docker cp backups/zensus_db_20241224.dump $CONTAINER_NAME:/tmp/restore.dump
docker exec $CONTAINER_NAME pg_restore -U zensus_user -d zensus_db -c /tmp/restore.dump
```

### Monitor Database Size

```bash
# Check disk usage
docker exec $CONTAINER_NAME psql -U zensus_user -d zensus_db -c "
SELECT 
    pg_database.datname as database,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'zensus_db';
"
```

---

## Troubleshooting

### 🔥 Common Deployment Issues (Lessons Learned)

#### Issue 1: Tables Don't Exist When Running ETL Scripts

**Symptom**:
```
psycopg2.errors.UndefinedTable: relation "zensus.ref_grid_10km" does not exist
```

**Root Cause**: In containerized deployments (Dokploy), the SQL schema files in `docker/init/` are NOT automatically applied because the database container starts independently from the ETL container.

**Solution**: The `setup_database.sh` script (v2.0+) now automatically applies SQL schema files when running in containerized mode.

```bash
# Update to latest version
cd /app/red_data_database
curl -o setup_database.sh https://raw.githubusercontent.com/LW1989/red_data_database/master/setup_database.sh
chmod +x setup_database.sh

# Run setup (it will auto-install psql and apply schemas)
./setup_database.sh --full
```

**Manual Fix** (if script fails):
```bash
# Install psql client
apt-get update && apt-get install -y postgresql-client

# Apply schemas manually in order
cd /app/red_data_database
export PGPASSWORD="your_db_password"
psql -h your-db-host -U your-db-user -d your-db-name -f docker/init/01_extensions.sql
psql -h your-db-host -U your-db-user -d your-db-name -f docker/init/02_schema.sql
psql -h your-db-host -U your-db-user -d your-db-name -f docker/init/03_vg250_schema.sql
psql -h your-db-host -U your-db-user -d your-db-name -f docker/init/04_bundestagswahlen_schema.sql
psql -h your-db-host -U your-db-user -d your-db-name -f docker/init/05_lwu_properties_schema.sql
```

---

#### Issue 2: Container Can't Resolve Database Hostname

**Symptom**:
```
could not translate host name "datahub-reddata" to address: Temporary failure in name resolution
```

**Root Cause**: Incorrect or incomplete `DB_HOST` in Python ETL service environment variables.

**Solution**: Use the **full internal hostname** from Dokploy:

1. Go to your Dokploy database → **General** tab
2. Find **"Internal Host"** (e.g., `datahub-reddata-smnviv-data`)
3. Update your Python service's environment variables:
   ```yaml
   environment:
     - DB_HOST=datahub-reddata-smnviv-data  # Use FULL internal hostname
   ```

**❌ Wrong**: `DB_HOST=datahub-reddata` (partial name - DNS won't resolve)  
**✅ Right**: `DB_HOST=datahub-reddata-smnviv-data` (full internal hostname from Dokploy UI)

---

#### Issue 3: Google Drive Download Limits (50 Files)

**Symptom**:
```
The gdrive folder has more than 50 files, gdrive can't download more than this limit.
```

**Root Cause**: `gdown` tool has a 50-file limit per folder for public links.

**Solutions**:

**Option A: Use rclone (Recommended for Large Datasets)**
```bash
# On server: Install rclone
apt-get update && apt-get install -y rclone

# On local machine with browser: Configure rclone
rclone config
# Follow prompts to authorize Google Drive

# Add Google Drive folders to "My Drive":
# 1. Open folder links in browser while logged in
# 2. Right-click folder → "Add shortcut to Drive" → "My Drive"

# On server: Download with rclone
rclone copy "gdrive:10km" /app/red_data_database/data/zensus_data/10km/ -P
rclone copy "gdrive:1km" /app/red_data_database/data/zensus_data/1km/ -P
rclone copy "gdrive:100m" /app/red_data_database/data/zensus_data/100m/ -P
```

**Option B: Download Subfolders Separately with gdown**
Get individual subfolder URLs and download in batches:
```bash
gdown --folder "URL_TO_10KM_FOLDER" -O data/zensus_data/10km/
gdown --folder "URL_TO_1KM_FOLDER" -O data/zensus_data/1km/
gdown --folder "URL_TO_100M_FOLDER" -O data/zensus_data/100m/
gdown --folder "URL_TO_BTW2017_FOLDER" -O data/bundestagswahlen/btw2017/
# etc...
```

**Option C: SCP from Colleague with SSH Access**
```bash
# If colleague has data locally
scp -r /local/path/to/data/* user@server:/app/red_data_database/data/
```

---

#### Issue 4: Git Not Installed in Python Container

**Symptom**:
```
bash: git: command not found
```

**Root Cause**: The `python:3.11-slim` base image doesn't include git.

**Solutions**:

**Quick Fix**:
```bash
apt-get update && apt-get install -y git
git pull origin master
```

**Or Download Directly Without Git**:
```bash
# Download specific file
curl -o setup_database.sh https://raw.githubusercontent.com/LW1989/red_data_database/master/setup_database.sh

# Or clone with curl + unzip
curl -L https://github.com/LW1989/red_data_database/archive/refs/heads/master.zip -o repo.zip
apt-get install -y unzip
unzip repo.zip
mv red_data_database-master/* /app/red_data_database/
```

---

#### Issue 5: Nested Directories After Download

**Symptom**: Files end up in `data/zensus_data/10km/10km/` instead of `data/zensus_data/10km/`

**Root Cause**: `gdown` creates a subfolder with the same name as the Google Drive folder.

**Solution**:
```bash
# Fix nested directories for all grid sizes
cd /app/red_data_database
for dir in 10km 1km 100m; do
    if [ -d "data/zensus_data/$dir/$dir" ]; then
        mv data/zensus_data/$dir/$dir/* data/zensus_data/$dir/
        rmdir data/zensus_data/$dir/$dir
        echo "✓ Fixed $dir"
    fi
done
```

---

#### Issue 6: pip/Python Not Available in Database Container

**Symptom**:
```
bash: pip: command not found
```

**Root Cause**: Trying to run Python/ETL scripts inside the PostgreSQL database container (which only has PostgreSQL).

**Solution**: ETL scripts must run in a **separate Python container** or on the **host machine**. Create a Python service in Dokploy:

```yaml
# docker-compose.yml for Python ETL Service
version: '3.8'

services:
  python-etl:
    image: python:3.11-slim
    container_name: zensus-etl
    working_dir: /app
    volumes:
      - etl-data:/app/data
      - etl-scripts:/app
    environment:
      - DB_HOST=your-database-internal-hostname  # From Dokploy DB settings
      - DB_PORT=5432
      - DB_NAME=red-data-db
      - DB_USER=zensus_user
      - DB_PASSWORD=your_password
    command: tail -f /dev/null  # Keep container running

volumes:
  etl-data:
  etl-scripts:
```

Then exec into this container to run ETL scripts, not the database container.

---

### Database Won't Start

**Check logs in Dokploy**:
1. Go to your database service
2. Click **"Logs"** tab
3. Look for error messages

**Common issues**:
- Port 5432 already in use: Change `POSTGRES_PORT` to different port (e.g., `5433`)
- Insufficient permissions: Check volume mount permissions
- Out of memory: Increase server RAM or reduce dataset size

### ETL Scripts Can't Connect

```bash
# Verify database is running
docker ps | grep zensus

# Test connection
docker exec $CONTAINER_NAME pg_isready -U zensus_user -d zensus_db

# Check if it returns:
# /var/run/postgresql:5432 - accepting connections
```

**If connection fails**:
1. Verify `.env` file has correct credentials
2. Check `DB_HOST=localhost` (not server IP if running on server)
3. Verify database user exists:
   ```bash
   docker exec $CONTAINER_NAME psql -U postgres -c "\du"
   ```

### PostGIS Extension Not Found

```bash
# Install PostGIS extension
docker exec -it $CONTAINER_NAME psql -U zensus_user -d zensus_db -c "CREATE EXTENSION postgis;"

# Verify
docker exec -it $CONTAINER_NAME psql -U zensus_user -d zensus_db -c "SELECT PostGIS_Full_Version();"
```

### Schema Initialization Failed

```bash
# Manually apply schemas
cd /opt/zensus-database
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < docker/init/01_schema.sql
docker exec -i $CONTAINER_NAME psql -U zensus_user -d zensus_db < docker/init/02_zensus_reference_grids.sql
```

### Data Not Persisting After Restart

**Check volumes in Dokploy**:
1. Go to database service → **"Volumes"** tab
2. Verify `/var/lib/postgresql/data` is mounted to a named volume
3. Check volume exists:
   ```bash
   docker volume ls | grep postgres
   docker volume inspect [volume-name]
   ```

### Out of Memory Errors

**Solutions**:
1. **Start with smaller dataset**: Use `--test` mode (10km only)
2. **Increase server RAM**: Upgrade VPS plan
3. **Adjust PostgreSQL memory settings**:
   ```bash
   docker exec -it $CONTAINER_NAME psql -U postgres -c "
   ALTER SYSTEM SET shared_buffers = '256MB';
   ALTER SYSTEM SET effective_cache_size = '1GB';
   "
   docker restart $CONTAINER_NAME
   ```

### Permission Denied Errors

```bash
# Fix file permissions
sudo chown -R $USER:$USER /opt/zensus-database

# Fix .env permissions
chmod 600 /opt/zensus-database/.env

# Fix Docker socket permissions
sudo usermod -aG docker $USER
# Log out and back in
```

### Can't Access Database Externally

**Firewall check**:
```bash
# Check if port is open
sudo ufw status

# Allow specific IP
sudo ufw allow from YOUR_IP to any port 5432

# Or allow all (less secure)
sudo ufw allow 5432/tcp
```

**Port forwarding check** (in Dokploy):
1. Go to database service → **"Settings"**
2. Verify **"External Port"** is set to `5432`
3. Check service is running

**Test connection from local machine**:
```bash
# Test if port is reachable
nc -zv your-server-ip 5432

# Or use telnet
telnet your-server-ip 5432
```

---

## Performance Optimization

### PostgreSQL Configuration

For better performance with large spatial datasets:

```sql
-- Connect to database
docker exec -it $CONTAINER_NAME psql -U postgres

-- Increase shared buffers (25% of RAM)
ALTER SYSTEM SET shared_buffers = '2GB';

-- Increase work memory for spatial operations
ALTER SYSTEM SET work_mem = '64MB';

-- Increase maintenance work memory (for indexing)
ALTER SYSTEM SET maintenance_work_mem = '512MB';

-- Increase effective cache size (50-75% of RAM)
ALTER SYSTEM SET effective_cache_size = '6GB';

-- Restart database
\q
```

```bash
docker restart $CONTAINER_NAME
```

### Spatial Indexing

Verify spatial indexes exist:

```sql
SELECT 
    tablename, 
    indexname, 
    indexdef 
FROM pg_indexes 
WHERE schemaname = 'zensus' 
AND indexdef LIKE '%GIST%';
```

All `geom` columns should have GIST indexes for optimal spatial query performance.

---

## Monitoring in Dokploy

### View Logs

1. Navigate to your database service in Dokploy
2. Click **"Logs"** tab
3. Select log level (Info, Warning, Error)
4. Use search to filter logs

### Monitor Resources

1. Go to **"Metrics"** tab (if available)
2. View CPU, memory, and disk usage
3. Set up alerts for resource thresholds

### Database Management Commands

**In Dokploy Terminal**:

```bash
# List all databases
psql -U postgres -c "\l"

# List all tables
psql -U zensus_user -d zensus_db -c "\dt zensus.*"

# Get table sizes
psql -U zensus_user -d zensus_db -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'zensus'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

---

## Security Best Practices

### 1. Use Strong Passwords

```bash
# Generate strong password
openssl rand -base64 32
```

### 2. Restrict Database Access

```sql
-- Create read-only user for analytics
CREATE USER analyst_user WITH PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE zensus_db TO analyst_user;
GRANT USAGE ON SCHEMA zensus TO analyst_user;
GRANT SELECT ON ALL TABLES IN SCHEMA zensus TO analyst_user;
```

### 3. Enable SSL/TLS (Production)

Follow [Dokploy SSL Documentation](https://docs.dokploy.com/docs/core/security/ssl) to set up:
- Let's Encrypt SSL certificate
- Automatic certificate renewal
- HTTPS redirect

### 4. Regular Updates

```bash
# Update Dokploy
curl -sSL https://dokploy.com/install.sh | sudo sh

# Update PostgreSQL image (in Dokploy)
# Go to database service → Settings → Image → Change version → Redeploy
```

### 5. Backup Encryption

```bash
# Encrypt backup
gpg --symmetric --cipher-algo AES256 backups/zensus_db_20241224.dump

# Decrypt when restoring
gpg --decrypt backups/zensus_db_20241224.dump.gpg > restore.dump
```

---

## Next Steps

After successful deployment:

1. **✅ Verify data integrity**: Run queries to check data was loaded correctly
2. **✅ Set up automated backups**: Configure cron job for daily backups
3. **✅ Configure monitoring**: Set up alerts for disk space, memory usage
4. **✅ Create read-only users**: For analysts accessing the database
5. **✅ Document connection details**: Share with team members
6. **✅ Set up SSL** (production): Enable HTTPS for Dokploy interface

---

## Useful Resources

- **Dokploy Documentation**: https://docs.dokploy.com
- **PostGIS Documentation**: https://postgis.net/docs/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Project README**: See `README.md` for detailed database schema and usage examples

---

## Support and Contributing

If you encounter issues:

1. Check [Troubleshooting](#troubleshooting) section above
2. Review Dokploy logs for error messages
3. Check PostgreSQL logs: `docker logs $CONTAINER_NAME`
4. Open an issue on the project's GitHub repository

---

## Summary

You've successfully deployed a production-ready PostGIS database on Dokploy containing:

- ✅ **Zensus 2022 census data** (population, demographics, housing)
- ✅ **German administrative boundaries** (federal states, counties, municipalities)
- ✅ **Electoral district data** (Bundestagswahlen 2017, 2021, 2025)
- ✅ **LWU Berlin properties** (state-owned housing)
- ✅ **Spatial indexes** for fast geographic queries

**Total deployment time**: 1-2 hours (depending on dataset size and server specs)

**Database is now ready for**:
- Spatial analysis and GIS applications
- Demographics research and visualization
- Integration with QGIS, Python, R, and other data tools

---

**Happy analyzing! 🎉**

