"""
Retry geocoding for failed addresses.
Use this after improving the geocoding logic to re-process addresses that failed.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from etl.sync_housing_data import get_local_db_engine
from etl.geocoding import create_geocoder
from etl.utils import logger
import pandas as pd


def fetch_failed_properties(local_engine):
    """
    Fetch properties that failed geocoding or were never geocoded.
    
    Args:
        local_engine: SQLAlchemy engine
        
    Returns:
        DataFrame with failed properties
    """
    logger.info("Fetching failed/missing geocoding records...")
    
    with local_engine.connect() as conn:
        df = pd.read_sql_query("""
            SELECT 
                internal_id,
                strasse_normalized,
                hausnummer,
                plz,
                ort,
                geocoding_status
            FROM housing.properties
            WHERE geocoding_status IN ('failed', 'pending')
               OR geocoding_status IS NULL
               OR (latitude IS NULL AND longitude IS NULL)
            ORDER BY internal_id
        """, conn)
    
    logger.info(f"Found {len(df)} properties needing geocoding")
    return df


def retry_geocoding(df, geocoder):
    """
    Retry geocoding for failed addresses.
    
    Args:
        df: DataFrame with property data
        geocoder: Geocoder instance
        
    Returns:
        DataFrame with updated geocoding results
    """
    logger.info(f"Retrying geocoding for {len(df)} properties...")
    
    # Initialize/reset geocoding columns
    df['latitude'] = None
    df['longitude'] = None
    df['geocoding_status'] = 'pending'
    df['geocoding_quality'] = None
    df['geocoded_address'] = None
    df['last_geocoded_at'] = None
    
    success_count = 0
    fail_count = 0
    cache_hit_count = 0
    
    for idx, row in df.iterrows():
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
        if city and ' OT ' in city:
            city = city.split(' OT ')[0].strip()
        
        # Skip if insufficient address components
        if not postal_code and not (street and city):
            logger.warning(f"Skipping {row['internal_id']}: Insufficient address components")
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
        if not result['success'] and postal_code and street:
            logger.debug(f"Retrying without city for {row['internal_id']}")
            result = geocoder.geocode_components(
                street=street,
                house_number=house_number,
                postal_code=postal_code,
                city=None
            )
        
        # Update DataFrame with results
        if result['success']:
            df.at[idx, 'latitude'] = result['latitude']
            df.at[idx, 'longitude'] = result['longitude']
            df.at[idx, 'geocoding_status'] = 'success'
            df.at[idx, 'geocoding_quality'] = result.get('quality', 0.5)
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
            logger.info(f"Progress: {idx + 1}/{len(df)} retried "
                       f"(success: {success_count}, failed: {fail_count}, cached: {cache_hit_count})")
    
    logger.info(f"✓ Retry complete: {success_count} success, {fail_count} still failed, "
                f"{cache_hit_count} from cache")
    
    return df


def update_geocoding_results(df, local_engine):
    """
    Update geocoding results in the database.
    
    Args:
        df: DataFrame with updated geocoding results
        local_engine: SQLAlchemy engine
    """
    logger.info(f"Updating {len(df)} records in database...")
    
    updated_count = 0
    error_count = 0
    
    with local_engine.connect() as conn:
        for idx, row in df.iterrows():
            try:
                # Convert NaN to None
                lat = None if pd.isna(row['latitude']) else float(row['latitude'])
                lon = None if pd.isna(row['longitude']) else float(row['longitude'])
                quality = None if pd.isna(row['geocoding_quality']) else float(row['geocoding_quality'])
                
                # Update query
                conn.execute(text("""
                    UPDATE housing.properties
                    SET 
                        latitude = :lat,
                        longitude = :lon,
                        geocoding_status = :status,
                        geocoding_quality = :quality,
                        geocoded_address = :address,
                        last_geocoded_at = :geocoded_at,
                        geom = CASE 
                            WHEN :lat IS NOT NULL AND :lon IS NOT NULL 
                            THEN ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                            ELSE NULL
                        END
                    WHERE internal_id = :id
                """), {
                    'id': row['internal_id'],
                    'lat': lat,
                    'lon': lon,
                    'status': row['geocoding_status'],
                    'quality': quality,
                    'address': row['geocoded_address'],
                    'geocoded_at': row['last_geocoded_at']
                })
                
                updated_count += 1
                
                if (idx + 1) % 100 == 0:
                    logger.info(f"Updated {idx + 1}/{len(df)} records")
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Error updating {row['internal_id']}: {e}")
        
        conn.commit()
    
    logger.info(f"✓ Update complete: {updated_count} records updated, {error_count} errors")


def retry_failed_geocoding():
    """Main function to retry failed geocoding."""
    
    logger.info("=" * 80)
    logger.info("RETRY FAILED GEOCODING")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        # Connect to database
        logger.info("\n1. Connecting to database...")
        local_engine = get_local_db_engine()
        logger.info("✓ Connected")
        
        # Fetch failed properties
        logger.info("\n2. Fetching failed properties...")
        df = fetch_failed_properties(local_engine)
        
        if len(df) == 0:
            logger.info("✓ No failed properties to retry!")
            return
        
        logger.info(f"✓ Found {len(df)} properties to retry")
        
        # Initialize geocoder
        logger.info("\n3. Initializing geocoder with improved logic...")
        geocoder = create_geocoder(cache_enabled=True, rate_limit=1.0)
        logger.info("✓ Geocoder ready (with abbreviation expansion & char normalization)")
        
        # Retry geocoding
        logger.info("\n4. Retrying geocoding...")
        df = retry_geocoding(df, geocoder)
        
        # Update database
        logger.info("\n5. Updating database...")
        update_geocoding_results(df, local_engine)
        
        # Summary
        elapsed_time = datetime.now() - start_time
        success_count = (df['geocoding_status'] == 'success').sum()
        failed_count = (df['geocoding_status'] == 'failed').sum()
        success_rate = (success_count / len(df) * 100) if len(df) > 0 else 0
        
        logger.info("\n" + "=" * 80)
        logger.info("RETRY COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total retried: {len(df)}")
        logger.info(f"Now successful: {success_count} ({success_rate:.1f}%)")
        logger.info(f"Still failed: {failed_count}")
        logger.info(f"Elapsed time: {elapsed_time}")
        logger.info("=" * 80)
        
        local_engine.dispose()
        
    except Exception as e:
        logger.error(f"\n✗ RETRY FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Retry geocoding for failed addresses')
    
    args = parser.parse_args()
    
    retry_failed_geocoding()

