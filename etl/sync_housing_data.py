"""
Sync housing data from external database to local database.
This script:
1. Connects to the external housing scraper database
2. Fetches new/updated properties
3. Geocodes addresses using Nominatim
4. Upserts data into local housing.properties table
"""

import sys
from pathlib import Path
import psycopg2
from psycopg2 import sql
import pandas as pd
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from etl.utils import logger
from etl.geocoding import create_geocoder


# Database connection parameters
EXTERNAL_DB = {
    'host': '157.180.47.26',
    'port': '5432',
    'database': 'housing_scraper_db',
    'user': 'scraper_user',
    'password': 'de2cdd2a1e225c850152cb96e19ae59728810bfc'
}

LOCAL_DB = {
    'host': 'dokploy.red-data.eu',
    'port': 54321,
    'database': 'red-data-db',
    'user': 'zensus_user',
    'password': 'kiskIv-kehcyh-hishu4'
}


def get_local_db_engine():
    """Create SQLAlchemy engine for local database."""
    password = quote_plus(LOCAL_DB['password'])
    connection_string = (
        f"postgresql://{LOCAL_DB['user']}:{password}@"
        f"{LOCAL_DB['host']}:{LOCAL_DB['port']}/{LOCAL_DB['database']}"
    )
    return create_engine(connection_string, pool_pre_ping=True)


def connect_to_external_db():
    """Connect to external housing database."""
    try:
        conn = psycopg2.connect(**EXTERNAL_DB, connect_timeout=10)
        logger.info("✓ Connected to external database")
        return conn
    except Exception as e:
        logger.error(f"✗ Failed to connect to external database: {e}")
        raise


def get_last_sync_timestamp(local_engine):
    """
    Get the timestamp of the last successful sync.
    
    Args:
        local_engine: SQLAlchemy engine for local database
        
    Returns:
        datetime or None
    """
    try:
        with local_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT MAX(date_scraped) 
                FROM housing.properties
            """))
            last_sync = result.scalar()
            
            if last_sync:
                logger.info(f"Last sync timestamp: {last_sync}")
            else:
                logger.info("No previous sync found - will do full sync")
            
            return last_sync
    except Exception as e:
        logger.warning(f"Could not determine last sync timestamp: {e}")
        return None


def fetch_properties_from_external_db(external_conn, last_sync: Optional[datetime] = None,
                                     limit: Optional[int] = None):
    """
    Fetch properties from external database.
    Excludes parking spaces (Stellplätze) and garages.
    
    Args:
        external_conn: Connection to external database
        last_sync: Timestamp of last sync (for incremental sync)
        limit: Optional limit for testing
        
    Returns:
        DataFrame with property data
    """
    # Filter out parking spaces and garages
    # Keep only actual apartments/houses (wohnung, haus, etc.)
    # Logic: Include if type is NULL OR (type doesn't contain ANY parking/garage keywords)
    type_filter = """
        AND (immo_type_scraped IS NULL 
             OR (LOWER(immo_type_scraped) NOT LIKE '%stellplatz%'
                 AND LOWER(immo_type_scraped) NOT LIKE '%stellplaetz%'
                 AND LOWER(immo_type_scraped) NOT LIKE '%garage%'
                 AND LOWER(immo_type_scraped) NOT LIKE '%tiefgarage%'
                 AND LOWER(immo_type_scraped) NOT LIKE '%parkplatz%'
                 AND LOWER(immo_type_scraped) != 'garage'
                 AND LOWER(immo_type_scraped) != 'stellplatz'))
    """
    
    if last_sync:
        # Incremental sync: fetch only new/updated records
        # Format timestamp directly into query (safe - from our own DB)
        query = f"""
            SELECT * FROM all_properties 
            WHERE date_scraped > '{last_sync}'
            {type_filter}
            ORDER BY date_scraped
        """
        logger.info(f"Fetching properties updated since {last_sync} (excluding parking/garages)")
    else:
        # Full sync: fetch all records
        query = f"""
            SELECT * FROM all_properties 
            WHERE 1=1
            {type_filter}
            ORDER BY date_scraped
        """
        logger.info("Fetching all properties (full sync, excluding parking/garages)")
    
    if limit:
        query += f" LIMIT {limit}"
        logger.info(f"Limiting to {limit} records for testing")
    
    df = pd.read_sql_query(query, external_conn)
    
    logger.info(f"✓ Fetched {len(df)} properties from external database")
    return df


def geocode_properties(df: pd.DataFrame, geocoder, max_records: Optional[int] = None):
    """
    Geocode addresses in the DataFrame.
    
    Args:
        df: DataFrame with property data
        geocoder: Geocoder instance
        max_records: Optional maximum number of records to geocode (for testing)
        
    Returns:
        DataFrame with added geocoding columns
    """
    logger.info(f"Starting geocoding for {len(df)} properties...")
    
    # Initialize geocoding columns
    df['latitude'] = None
    df['longitude'] = None
    df['geocoding_status'] = 'pending'
    df['geocoded_address'] = None
    df['last_geocoded_at'] = None
    
    # Limit records for testing if specified
    records_to_geocode = min(len(df), max_records) if max_records else len(df)
    
    success_count = 0
    fail_count = 0
    cache_hit_count = 0
    
    for idx in range(records_to_geocode):
        row = df.iloc[idx]
        
        # Build address from components
        street = row.get('strasse_normalized', '')
        house_number = row.get('hausnummer', '')
        postal_code = row.get('plz', '')
        city = row.get('ort', '')
        
        # Convert None/NaN to empty string
        street = str(street) if pd.notna(street) else ''
        house_number = str(house_number) if pd.notna(house_number) else ''
        postal_code = str(postal_code) if pd.notna(postal_code) else ''
        city = str(city) if pd.notna(city) else ''
        
        # Clean city name - remove district information (OT = Ortsteil)
        # "Berlin OT Reinickendorf" -> "Berlin"
        if city and ' OT ' in city:
            city = city.split(' OT ')[0].strip()
        
        # Skip if we don't have at least postal code OR (street and city)
        if not postal_code and not (street and city):
            logger.warning(f"Skipping row {idx}: Insufficient address components "
                          f"(street={bool(street)}, postal={bool(postal_code)}, city={bool(city)})")
            df.at[idx, 'geocoding_status'] = 'failed'
            df.at[idx, 'geocoded_address'] = 'NO_ADDRESS'
            fail_count += 1
            continue
        
        # Try geocoding with full address
        result = geocoder.geocode_components(
            street=street,
            house_number=house_number,
            postal_code=postal_code,
            city=city
        )
        
        # If failed and we have postal code + street, try without city
        # (German postal codes are very specific)
        if not result['success'] and postal_code and street:
            logger.debug(f"Retrying without city for row {idx}")
            result = geocoder.geocode_components(
                street=street,
                house_number=house_number,
                postal_code=postal_code,
                city=None  # Try without city
            )
        
        # Update DataFrame with results
        if result['success']:
            df.at[idx, 'latitude'] = result['latitude']
            df.at[idx, 'longitude'] = result['longitude']
            df.at[idx, 'geocoding_status'] = 'success'
            df.at[idx, 'geocoded_address'] = result.get('display_name', '')
            df.at[idx, 'last_geocoded_at'] = datetime.now()
            success_count += 1
            
            if result.get('cached'):
                cache_hit_count += 1
        else:
            df.at[idx, 'geocoding_status'] = 'failed'
            df.at[idx, 'geocoded_address'] = result.get('error_message', 'Unknown error')
            fail_count += 1
        
        # Progress update every 10 records
        if (idx + 1) % 10 == 0:
            logger.info(f"Progress: {idx + 1}/{records_to_geocode} geocoded "
                       f"(success: {success_count}, failed: {fail_count}, cached: {cache_hit_count})")
    
    # Mark remaining records as skipped if we limited geocoding
    if max_records and len(df) > max_records:
        df.loc[max_records:, 'geocoding_status'] = 'skipped'
        logger.info(f"Skipped geocoding for {len(df) - max_records} records (limit reached)")
    
    logger.info(f"✓ Geocoding complete: {success_count} success, {fail_count} failed, "
                f"{cache_hit_count} from cache")
    
    return df


def create_geometry_from_coordinates(local_engine):
    """
    Update geometry column from latitude/longitude coordinates.
    Uses PostGIS ST_SetSRID and ST_MakePoint.
    """
    logger.info("Creating PostGIS geometry from coordinates...")
    
    try:
        with local_engine.connect() as conn:
            conn.execute(text("""
                UPDATE housing.properties
                SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
                WHERE latitude IS NOT NULL 
                AND longitude IS NOT NULL
                AND geom IS NULL
            """))
            conn.commit()
            logger.info("✓ Geometry column updated")
    except Exception as e:
        logger.error(f"✗ Failed to create geometry: {e}")
        raise


def upsert_properties(df: pd.DataFrame, local_engine, chunk_size: int = 1000):
    """
    Upsert properties into local database.
    
    Args:
        df: DataFrame with property data
        local_engine: SQLAlchemy engine for local database
        chunk_size: Number of records to insert per batch
    """
    logger.info(f"Upserting {len(df)} properties to local database...")
    
    # Get column names from DataFrame
    columns = df.columns.tolist()
    
    # Add synced_at timestamp
    df['synced_at'] = datetime.now()
    
    # Convert DataFrame to list of dicts
    records = df.to_dict('records')
    
    # Build upsert query
    # ON CONFLICT DO UPDATE will update existing records
    update_columns = [col for col in columns if col not in ['internal_id']]
    update_set = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
    
    inserted_count = 0
    updated_count = 0
    error_count = 0
    
    # Process in chunks
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i+chunk_size]
        
        try:
            with local_engine.connect() as conn:
                for record in chunk:
                    # Convert NaN to None for SQL
                    record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
                    
                    # Build column names and placeholders
                    cols = list(record.keys())
                    placeholders = ", ".join([f":{col}" for col in cols])
                    col_names = ", ".join(cols)
                    
                    # Build update clause
                    update_clause = ", ".join([
                        f"{col} = EXCLUDED.{col}" 
                        for col in cols if col != 'internal_id'
                    ])
                    
                    query = text(f"""
                        INSERT INTO housing.properties ({col_names})
                        VALUES ({placeholders})
                        ON CONFLICT (internal_id) DO UPDATE SET
                            {update_clause}
                    """)
                    
                    conn.execute(query, record)
                    inserted_count += 1
                
                conn.commit()
                
            logger.info(f"Progress: {min(i + chunk_size, len(records))}/{len(records)} records upserted")
            
        except Exception as e:
            error_count += len(chunk)
            logger.error(f"Error upserting chunk {i//chunk_size + 1}: {e}")
            continue
    
    logger.info(f"✓ Upsert complete: {inserted_count} records processed, {error_count} errors")
    
    # Update geometry column
    create_geometry_from_coordinates(local_engine)


def sync_housing_data(incremental: bool = True, limit: Optional[int] = None,
                     geocode_limit: Optional[int] = None):
    """
    Main sync function.
    
    Args:
        incremental: If True, only sync records updated since last sync
        limit: Optional limit on number of records to fetch (for testing)
        geocode_limit: Optional limit on number of records to geocode (for testing)
    """
    logger.info("=" * 80)
    logger.info("HOUSING DATA SYNC STARTED")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        # Connect to databases
        logger.info("\n1. Connecting to databases...")
        external_conn = connect_to_external_db()
        local_engine = get_local_db_engine()
        logger.info("✓ Connected to local database")
        
        # Get last sync timestamp
        logger.info("\n2. Checking last sync timestamp...")
        last_sync = get_last_sync_timestamp(local_engine) if incremental else None
        
        # Fetch properties from external database
        logger.info("\n3. Fetching properties from external database...")
        df = fetch_properties_from_external_db(external_conn, last_sync, limit)
        
        if len(df) == 0:
            logger.info("✓ No new properties to sync")
            return
        
        # Initialize geocoder
        logger.info("\n4. Initializing geocoder...")
        geocoder = create_geocoder(cache_enabled=True, rate_limit=1.0)
        
        # Geocode addresses
        logger.info("\n5. Geocoding addresses...")
        df = geocode_properties(df, geocoder, max_records=geocode_limit)
        
        # Upsert to local database
        logger.info("\n6. Upserting to local database...")
        upsert_properties(df, local_engine, chunk_size=1000)
        
        # Close connections
        external_conn.close()
        local_engine.dispose()
        
        # Summary
        elapsed_time = datetime.now() - start_time
        logger.info("\n" + "=" * 80)
        logger.info("SYNC COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total records: {len(df)}")
        logger.info(f"Successfully geocoded: {(df['geocoding_status'] == 'success').sum()}")
        logger.info(f"Failed geocoding: {(df['geocoding_status'] == 'failed').sum()}")
        logger.info(f"Elapsed time: {elapsed_time}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n✗ SYNC FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync housing data from external database')
    parser.add_argument('--full', action='store_true', 
                       help='Do full sync instead of incremental')
    parser.add_argument('--limit', type=int, 
                       help='Limit number of records to fetch (for testing)')
    parser.add_argument('--geocode-limit', type=int,
                       help='Limit number of records to geocode (for testing)')
    
    args = parser.parse_args()
    
    sync_housing_data(
        incremental=not args.full,
        limit=args.limit,
        geocode_limit=args.geocode_limit
    )

