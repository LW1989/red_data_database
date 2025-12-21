# PostGIS Zensus Database

A PostgreSQL + PostGIS database for German Zensus 2022 data aggregated to INSPIRE grid cells (1km and 10km resolution).

## Overview

This project provides a complete database setup for storing and querying German census data with spatial geometries. The database uses a star schema design with:

- **Reference tables**: Store authoritative polygon geometries from GeoGitter INSPIRE (EPSG:3035)
- **Fact tables**: Store Zensus statistical data, joined to reference tables via `grid_id`

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

# Verify container is running
docker-compose ps

# Check logs to ensure database initialized correctly
docker-compose logs postgres

# You should see messages like:
# - "database system is ready to accept connections"
# - "PostGIS extension enabled"
```

**Troubleshooting**:
- If port 5432 is already in use, change `POSTGRES_PORT` in `.env` to another port (e.g., `5433`)
- If container fails to start, check logs: `docker-compose logs postgres`

### Step 3: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import geopandas; import pandas; print('Dependencies installed successfully')"
```

### Step 4: Verify Database Connection

```bash
# Test database connection (with venv activated)
python -c "
from etl.utils import get_db_engine
engine = get_db_engine()
print('Database connection successful!')
"
```

### Step 5: Load Grid Geometries

**Important**: Load grid geometries before loading Zensus data, as fact tables have foreign key constraints.

```bash
# Ensure venv is activated
source venv/bin/activate

# Load grid geometries (start with smaller grids for testing)
# 10km grid (smallest, ~3.8K rows) - recommended for initial testing
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_10km.gpkg 10km

# 1km grid (~214K rows) - takes a few minutes
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_1km.gpkg 1km

# 100m grid (12GB file, millions of rows) - requires 16GB+ RAM, takes hours
# Only load if you have sufficient resources
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_100m.gpkg 100m
```

**Progress tracking**: The script logs progress every 10,000 rows. Monitor `etl.log` for detailed information.

### Step 6: Load Zensus Data

Load census statistics (can be done in any order, but grid geometries must be loaded first):

```bash
# Ensure venv is activated
source venv/bin/activate

# Example: Load population data for 1km grid
python etl/load_zensus.py data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_1km-Gitter.csv

# Example: Load population data for 10km grid
python etl/load_zensus.py data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_10km-Gitter.csv

# Load all datasets (example script)
# You can create a simple loop to load all CSV files:
find data/zensus_data -name "*1km-Gitter.csv" -exec python etl/load_zensus.py {} \;
```

**Note**: Each CSV file is processed independently. You can load them in parallel or sequentially.

### Step 7: Verify Data Load

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

### Step 8: Access Database

See the **"Accessing the Database"** section below for detailed instructions on connecting from your local machine using various tools.

### Local Development Tips

- **Stop database**: `docker-compose down` (keeps data in volume)
- **Stop and remove data**: `docker-compose down -v` (⚠️ deletes all data)
- **View logs**: `docker-compose logs -f postgres`
- **Restart database**: `docker-compose restart postgres`
- **Check disk usage**: `docker system df`

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

### Step 6: Load Data on Server

```bash
# SSH into server
ssh user@your-server-ip
cd /opt/zensus-database

# Activate virtual environment
source venv/bin/activate

# Load grid geometries
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_10km.gpkg 10km
python etl/load_grids.py data/geo_data/DE_Grid_ETRS89-LAEA_1km.gpkg 1km

# Load Zensus data
python etl/load_zensus.py data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_1km-Gitter.csv
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

### Step 8: Setup Automated Backups

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
python etl/load_zensus.py data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_10km-Gitter.csv

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

