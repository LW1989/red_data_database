# Deploying German Zensus 2022 Database on Dokploy

This guide walks you through deploying the PostGIS-enabled German Zensus database on Dokploy using the web interface. Dokploy is a self-hosted PaaS (Platform as a Service) that simplifies Docker container management.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Overview](#installation-overview)
- [Method 1: Using Dokploy's Native Database Feature (Recommended)](#method-1-using-dokploys-native-database-feature-recommended)
- [Method 2: Using Dokploy's Compose Feature](#method-2-using-dokploys-compose-feature)
- [Post-Deployment: Loading Data](#post-deployment-loading-data)
- [Accessing Your Database](#accessing-your-database)
- [Backup and Maintenance](#backup-and-maintenance)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Server Requirements

- **VPS or Dedicated Server** running:
  - Ubuntu 20.04+ or Debian 11+
  - Minimum 4GB RAM (8GB+ recommended for large datasets)
  - 50GB+ storage (depends on grid size: 10km ≈ 2GB, 1km ≈ 20GB, 100m ≈ 200GB)
  - Docker and Docker Compose installed
  
- **Network Access**:
  - SSH access to your server
  - Ports 80, 443, and 3000 available for Dokploy
  - Port 5432 available for PostgreSQL (or custom port)

### Local Requirements

- SSH client (Terminal on macOS/Linux, PuTTY on Windows)
- Git (for cloning repository)
- PostgreSQL client tools (optional, for testing connections)

---

## Installation Overview

The deployment process consists of:

1. **Install Dokploy** on your server
2. **Deploy PostGIS database** via Dokploy web interface
3. **Upload project files** to server
4. **Load census data** using ETL scripts
5. **Configure access** and backups

**Estimated Time**: 30-60 minutes (excluding data loading, which varies by grid size)

---

## Step 1: Install Dokploy

### 1.1 Connect to Your Server

```bash
# SSH into your server
ssh your-username@your-server-ip
```

### 1.2 Install Docker (if not already installed)

```bash
# Install Docker using official script
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose plugin
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
exit
```

Reconnect via SSH:
```bash
ssh your-username@your-server-ip
```

### 1.3 Verify Docker Installation

```bash
docker --version
# Should output: Docker version 24.x.x or higher

docker compose version
# Should output: Docker Compose version v2.x.x or higher
```

### 1.4 Install Dokploy

```bash
# Run official Dokploy installation script
curl -sSL https://dokploy.com/install.sh | sudo sh
```

**Installation takes 2-5 minutes.** Once complete:

```bash
# Verify Dokploy is running
docker ps | grep dokploy
```

### 1.5 Access Dokploy Web Interface

1. Open your browser and navigate to: `http://your-server-ip:3000`
2. **Create admin account** on first login:
   - Username: Choose a secure username
   - Email: Your email address
   - Password: Strong password (save this!)

**🔒 Security Note**: For production, set up a domain with SSL/TLS. See [Dokploy SSL Documentation](https://docs.dokploy.com/docs/core/security/ssl).

---

## Method 1: Using Dokploy's Native Database Feature (Recommended)

This method uses Dokploy's built-in database management, which provides a clean UI for monitoring, backups, and configuration.

### 2.1 Create a Project

1. **Log into Dokploy** at `http://your-server-ip:3000`

2. **Click "Projects"** in the left sidebar

3. **Click "Create Project"** button
   - **Name**: `zensus-database`
   - **Description**: `German Zensus 2022 PostGIS Database`
   - Click **"Create"**

### 2.2 Create PostgreSQL Database

1. **Inside your project**, click **"Create Service"** → **"Database"**

2. **Select "PostgreSQL"** from database types

3. **Configure Database Settings**:

   | Field | Value | Notes |
   |-------|-------|-------|
   | **Name** | `zensus-postgres` | Service name in Dokploy |
   | **Database Name** | `zensus_db` | Name of the PostgreSQL database |
   | **Username** | `zensus_user` | Database user |
   | **Password** | `[generate strong password]` | Save this securely! |
   | **Version** | `15` or `16` | PostgreSQL version |
   | **Port** | `5432` | Internal port (leave default) |

4. **Click "Create"** to initialize the database

### 2.3 Configure PostGIS Extension

**Option A: Manual Installation (After Deployment)**

After the database is deployed, you'll need to enable PostGIS:

1. **In Dokploy**, go to your database service
2. **Click "Terminal"** tab to open database shell
3. **Connect to database**:
   ```bash
   psql -U zensus_user -d zensus_db
   ```
4. **Install PostGIS extension**:
   ```sql
   CREATE EXTENSION postgis;
   CREATE EXTENSION postgis_topology;
   ```
5. **Verify installation**:
   ```sql
   SELECT PostGIS_Full_Version();
   ```
   You should see PostGIS version information.

**Option B: Custom Docker Image (Recommended)**

To use a PostGIS-enabled image directly:

1. **In database settings**, find **"Image"** field
2. **Change from** `postgres:15` **to** `postgis/postgis:15-3.4`
3. **Save and redeploy**

This ensures PostGIS is pre-installed.

### 2.4 Configure External Access (Optional)

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

### 2.5 Deploy Database

1. **Click "Deploy"** button in the database service
2. **Monitor logs** to ensure successful startup
3. **Verify status**: Service should show as "Running" (green indicator)

### 2.6 Configure Database Volumes (Important for Persistence)

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

### 2.1 Create a Project

Same as Method 1, Step 2.1.

### 2.2 Create Compose Service

1. **Inside your project**, click **"Create Service"** → **"Compose"**

2. **Configure Service**:
   - **Name**: `zensus-database`
   - **Source Type**: Choose one:
     - **Git Repository**: If your code is on GitHub/GitLab
     - **Raw Compose**: Paste docker-compose.yml content directly

### 2.3 Option A: Using Git Repository

1. **Select "Git Repository"**

2. **Configure Git Settings**:
   - **Repository URL**: `https://github.com/YOUR_USERNAME/red_data_database.git`
   - **Branch**: `master` or `main`
   - **Compose File Path**: `docker-compose.yml` (default)
   
3. **Add Authentication** (if private repo):
   - Username/Password or
   - SSH Key

4. **Click "Create"**

### 2.4 Option B: Using Raw Compose

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

### 2.5 Configure Environment Variables

1. **Go to "Environment"** tab

2. **Add the following variables**:
   ```
   POSTGRES_DB=zensus_db
   POSTGRES_USER=zensus_user
   POSTGRES_PASSWORD=your_secure_production_password
   POSTGRES_PORT=5432
   ```

3. **Click "Save"**

### 2.6 Deploy Compose Stack

1. **Click "Deploy"** button
2. **Monitor logs** for successful deployment
3. **Verify status**: All services should show as "Running"

---

## Step 3: Upload Project to Server

You need to upload the project files (ETL scripts, schema files, etc.) to your server to load data.

### 3.1 Option A: Using Git (Recommended)

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

### 3.2 Option B: Using rsync (From Local Machine)

```bash
# On your local machine (not on server)
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '.git' \
  /path/to/local/red_data_database/ \
  your-username@your-server-ip:/opt/zensus-database/
```

### 3.3 Option C: Using scp

```bash
# On your local machine
scp -r /path/to/local/red_data_database \
  your-username@your-server-ip:/opt/zensus-database/
```

### 3.4 Verify Files

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

---

## Step 4: Upload Census Data to Server

The census data files are large and need to be uploaded separately.

### 4.1 Using rsync (Recommended for Large Files)

```bash
# On your local machine
rsync -avz --progress \
  /path/to/local/data/ \
  your-username@your-server-ip:/opt/zensus-database/data/
```

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

### 4.2 Using scp

```bash
# On your local machine
scp -r /path/to/local/data \
  your-username@your-server-ip:/opt/zensus-database/
```

### 4.3 Verify Data Upload

```bash
# On server
du -sh /opt/zensus-database/data/*

# You should see sizes like:
# 150M    data/geo_data
# 2.5G    data/zensus_data/10km
# 25G     data/zensus_data/1km
# etc.
```

---

## Step 5: Setup Python Environment on Server

### 5.1 Install Python Dependencies

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

### 5.2 Create Environment Configuration

```bash
# Create .env file for ETL scripts
cat > .env << 'EOF'
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=zensus_db
DB_USER=zensus_user
DB_PASSWORD=your_secure_production_password
EOF

# Secure the .env file
chmod 600 .env
```

**⚠️ Important**: Replace `your_secure_production_password` with the actual password you set in Dokploy.

---

## Step 6: Load Data into Database

### 6.1 Option A: Using Automated Setup Script (Recommended)

The repository includes an automated setup script that handles all data loading:

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

