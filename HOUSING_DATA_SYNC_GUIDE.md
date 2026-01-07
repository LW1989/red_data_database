# Housing Data Sync - User Guide

Complete guide for syncing housing property data from the external scraper database with automatic geocoding.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Setup](#setup)
- [Usage](#usage)
- [Geocoding](#geocoding)
- [Cron Job](#cron-job)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Overview

This feature syncs housing property data from an external scraper database (`housing_scraper_db`) to the local database, automatically geocoding German addresses to coordinates using the Nominatim (OpenStreetMap) API.

**Key Features:**
- Automatic daily sync at 5:00 AM
- Incremental sync (only fetch new/updated records)
- Address geocoding with Nominatim API
- Database-backed caching (avoids re-geocoding)
- Rate limiting (respects Nominatim's 1 req/sec policy)
- Comprehensive logging and error handling
- Quality checks and monitoring

## Architecture

```
External DB                    Local Database
(housing_scraper_db)          (red-data-db)
┌──────────────────┐          ┌─────────────────────┐
│  all_properties  │          │  housing.properties │
│  (15,261 rows)   │          │  (synced data)      │
│                  │          │                     │
│  - internal_id   │   Sync   │  - internal_id      │
│  - company       │  ────>   │  - company          │
│  - strasse_...   │          │  - strasse_...      │
│  - hausnummer    │          │  - hausnummer       │
│  - plz           │          │  - plz              │
│  - ort           │          │  - ort              │
│  - preis         │          │  - preis            │
│  - ...           │          │  - ...              │
└──────────────────┘          │                     │
                              │  + latitude         │
        ┌─────────────────────┤  + longitude        │
        │  Nominatim API      │  + geom (PostGIS)   │
        │  (Geocoding)        │  + geocoding_status │
        └─────────────────────┤  + geocoding_quality│
                              │  + synced_at        │
                              └─────────────────────┘
```

## Setup

### 1. Create the Database Schema

The schema was auto-generated from the external database inspection:

```bash
# Schema is in docker/init/07_housing_data_schema.sql
# It will be automatically created when Docker starts

# Or manually apply it:
psql -h dokploy.red-data.eu -p 54321 -U zensus_user -d red-data-db \
     -f docker/init/07_housing_data_schema.sql
```

### 2. Install Dependencies

The required packages are already in `requirements.txt`:
- `psycopg2` - PostgreSQL adapter
- `pandas` - Data manipulation
- `requests` - HTTP requests for geocoding API
- `sqlalchemy` - Database ORM

### 3. Run Tests

Test the sync functionality with a small dataset:

```bash
# Activate virtual environment
source venv/bin/activate

# Run test suite
python scripts/test_housing_sync.py

# Or run a quick test sync (10 records)
./scripts/run_housing_sync_test.sh
```

## Usage

### Manual Sync

```bash
# Activate virtual environment
source venv/bin/activate

# Run incremental sync (only new/updated records)
python etl/sync_housing_data.py

# Run full sync (all records)
python etl/sync_housing_data.py --full

# Limit records for testing
python etl/sync_housing_data.py --limit 100 --geocode-limit 50
```

**Command-line options:**
- `--full`: Do full sync instead of incremental
- `--limit N`: Limit number of records to fetch (for testing)
- `--geocode-limit N`: Limit number of records to geocode (for testing)

### Using Helper Scripts

```bash
# Manual run (full sync)
./scripts/run_housing_sync.sh

# Test run (10 records)
./scripts/run_housing_sync_test.sh
```

## Geocoding

### How It Works

1. **Address Normalization**: Combines address components (street, house number, postal code, city)
2. **Cache Check**: Checks database cache for previously geocoded addresses
3. **API Request**: Queries Nominatim API if not cached
4. **Rate Limiting**: Respects 1 request/second limit
5. **Retry Logic**: 3 attempts with exponential backoff on failures
6. **Result Storage**: Caches results in `housing.geocoding_cache` table

### Geocoding Provider

**Nominatim (OpenStreetMap)**
- Free and open-source
- Optimized for European/German addresses
- Rate limit: 1 request per second
- No API key required
- Usage policy: https://operations.osmfoundation.org/policies/nominatim/

**Note:** Photon API was tested but is currently blocked (403 errors). Nominatim achieved 100% success rate for valid German addresses during testing.

### Geocoding Quality

Results include a quality score (0-1):
- **0.8-1.0**: High quality (exact address match)
- **0.5-0.8**: Medium quality (street or area match)
- **0.2-0.5**: Low quality (city or district match)
- **< 0.2**: Very low quality (approximate location)

### Cache Performance

The caching system significantly improves performance:
- First sync: ~15,000 API requests needed
- Subsequent syncs: Only new addresses geocoded
- Cache hit rate: Typically >90% after initial sync

View cache statistics:

```sql
SELECT 
    COUNT(*) as total_cached,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
    SUM(hit_count) as total_hits,
    ROUND(AVG(hit_count), 2) as avg_hits_per_address
FROM housing.geocoding_cache;
```

## Cron Job

### Setup

Install the cron job for automatic daily sync at 5:00 AM:

```bash
./scripts/setup_housing_sync_cron.sh
```

This will:
- Create cron job entry
- Set up log directory (`logs/`)
- Create helper scripts
- Verify installation

### Verify Installation

```bash
# View cron jobs
crontab -l | grep housing_sync

# Expected output:
# 0 5 * * * cd /path/to/red_data_database && venv/bin/python etl/sync_housing_data.py >> logs/housing_sync.log 2>&1
```

### Remove Cron Job

```bash
# Edit crontab
crontab -e

# Delete the line containing 'sync_housing_data.py'
# Save and exit
```

## Monitoring

### View Logs

```bash
# Follow live logs
tail -f logs/housing_sync.log

# View recent logs
tail -n 100 logs/housing_sync.log

# View etl logs
tail -f etl.log
```

### Run Quality Checks

Execute SQL quality checks to verify data:

```bash
psql -h dokploy.red-data.eu -p 54321 -U zensus_user -d red-data-db \
     -f tests/sql/housing_quality_checks.sql
```

**Quality checks include:**
1. Total record count
2. Geocoding success rate
3. Missing address components
4. Coordinate coverage
5. PostGIS geometry coverage
6. Out-of-bounds coordinates
7. Properties by company
8. Recent sync statistics
9. Geocoding quality distribution
10. Duplicate detection
11. Missing price data
12. Average property statistics
13. Data freshness
14. Failed geocoding samples
15. Cache statistics

### Database Queries

```sql
-- Check sync status
SELECT 
    COUNT(*) as total_properties,
    COUNT(CASE WHEN geocoding_status = 'success' THEN 1 END) as geocoded,
    MAX(synced_at) as last_sync,
    MAX(date_scraped) as newest_data
FROM housing.properties;

-- View recent properties
SELECT 
    internal_id,
    strasse_normalized,
    hausnummer,
    plz,
    ort,
    latitude,
    longitude,
    geocoding_status,
    synced_at
FROM housing.properties
ORDER BY synced_at DESC
LIMIT 10;

-- Failed geocoding
SELECT 
    internal_id,
    strasse_normalized,
    hausnummer,
    plz,
    ort,
    geocoded_address as error
FROM housing.properties
WHERE geocoding_status = 'failed'
LIMIT 20;

-- Geocoding statistics
SELECT 
    geocoding_status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM housing.properties
GROUP BY geocoding_status;
```

## Troubleshooting

### Sync Fails with Connection Error

**Problem:** Cannot connect to external database

**Solutions:**
1. Check network connectivity: `ping 157.180.47.26`
2. Verify database credentials in `etl/sync_housing_data.py`
3. Check if external database is accessible
4. Review firewall rules

### Geocoding Rate Limit Errors

**Problem:** Too many requests to Nominatim API

**Solution:** The script already implements 1 req/sec rate limiting. If you still see errors:
1. Check if another process is using the API
2. Increase delay between requests in `etl/geocoding.py`
3. Use `--geocode-limit` to process fewer records at a time

### Low Geocoding Success Rate

**Problem:** Many addresses fail to geocode

**Possible causes:**
1. Poor address quality in source data
2. Missing address components
3. API temporary issues

**Solutions:**
1. Review failed addresses: Run quality check #14
2. Check address data quality in source database
3. Consider manual correction for critical addresses

### Database Schema Errors

**Problem:** Table or schema doesn't exist

**Solution:**
```bash
# Manually create schema
psql -h dokploy.red-data.eu -p 54321 -U zensus_user -d red-data-db \
     -f docker/init/07_housing_data_schema.sql
```

### Cron Job Not Running

**Problem:** Sync doesn't run automatically

**Solutions:**
1. Verify cron job exists: `crontab -l`
2. Check cron service is running: `systemctl status cron` (Linux)
3. Review logs for errors: `tail -f logs/housing_sync.log`
4. Test manual run: `./scripts/run_housing_sync.sh`
5. Check script permissions: `ls -l etl/sync_housing_data.py`

### Performance Issues

**Problem:** Sync takes too long

**Solutions:**
1. Use incremental sync (default)
2. Increase chunk size in `upsert_properties()` function
3. Optimize database indexes
4. Use `--geocode-limit` to process addresses in batches

### Cache Not Working

**Problem:** Repeated geocoding of same addresses

**Solution:**
```sql
-- Check cache table exists
SELECT COUNT(*) FROM housing.geocoding_cache;

-- Manually clear cache (if needed)
TRUNCATE housing.geocoding_cache;
```

## Data Schema

### housing.properties Table

| Column | Type | Description |
|--------|------|-------------|
| `internal_id` | TEXT | Primary key (from external DB) |
| `company` | TEXT | Housing company name |
| `strasse_normalized` | TEXT | Street name |
| `hausnummer` | TEXT | House number |
| `plz` | TEXT | Postal code (PLZ) |
| `ort` | TEXT | City name |
| `preis` | NUMERIC | Rent price (EUR) |
| `groesse` | NUMERIC | Size (m²) |
| `anzahl_zimmer` | NUMERIC | Number of rooms |
| `eur_per_m2` | NUMERIC | Price per m² |
| `immo_type_scraped` | TEXT | Property type |
| `date_scraped` | TIMESTAMP | Scraping timestamp |
| `first_seen` | TIMESTAMP | First seen date |
| `last_seen` | TIMESTAMP | Last seen date |
| `created_at` | TIMESTAMP | Created timestamp |
| `updated_at` | TIMESTAMP | Updated timestamp |
| `latitude` | DOUBLE PRECISION | Geocoded latitude |
| `longitude` | DOUBLE PRECISION | Geocoded longitude |
| `geom` | GEOMETRY(POINT, 4326) | PostGIS geometry |
| `geocoding_status` | TEXT | success/failed/pending |
| `geocoding_quality` | NUMERIC | Quality score (0-1) |
| `geocoded_address` | TEXT | Matched address or error |
| `synced_at` | TIMESTAMP | Sync timestamp |
| `last_geocoded_at` | TIMESTAMP | Geocoding timestamp |

### housing.geocoding_cache Table

| Column | Type | Description |
|--------|------|-------------|
| `address_hash` | TEXT | MD5 hash of address (PK) |
| `address` | TEXT | Full address string |
| `latitude` | DOUBLE PRECISION | Cached latitude |
| `longitude` | DOUBLE PRECISION | Cached longitude |
| `display_name` | TEXT | Display name from API |
| `quality` | NUMERIC | Quality score |
| `provider` | TEXT | Geocoding provider |
| `success` | BOOLEAN | Success flag |
| `error_message` | TEXT | Error if failed |
| `cached_at` | TIMESTAMP | Cache timestamp |
| `hit_count` | INTEGER | Number of cache hits |

## Performance Tips

1. **Use Incremental Sync**: Default mode only fetches new/updated records
2. **Enable Caching**: Always enabled by default for best performance
3. **Monitor Cache Hits**: High cache hit rate = faster syncs
4. **Batch Processing**: Use `--limit` for large initial syncs
5. **Off-Peak Scheduling**: Cron runs at 5 AM to avoid peak hours

## Support

For issues or questions:
1. Check this guide first
2. Review logs: `logs/housing_sync.log` and `etl.log`
3. Run quality checks: `tests/sql/housing_quality_checks.sql`
4. Test with small dataset: `./scripts/run_housing_sync_test.sh`

## Related Documentation

- [README.md](README.md) - Main project documentation
- [DATABASE_TABLES_DOCUMENTATION.md](DATABASE_TABLES_DOCUMENTATION.md) - Database schema
- [Implementation Plan](/.cursor/plans/housing_data_import_&_geocoding_01cfe305.plan.md) - Technical details

