#!/usr/bin/env python3
"""
Load LWU Berlin property data into PostgreSQL.

LWU (Landeseigene Wohnungsunternehmen) = State-owned housing companies in Berlin.
This script loads property parcel geometries owned by these companies.
"""

import sys
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import geopandas as gpd
from sqlalchemy import text
from etl.utils import get_db_engine, logger


def clean_property_id(original_id: str) -> str:
    """
    Clean property ID by removing trailing underscores.
    
    Original format: lwu_fls.11058003400457______
    Clean format:    lwu_fls.11058003400457
    
    Args:
        original_id: Original ID with trailing underscores
        
    Returns:
        Cleaned ID without trailing underscores
    """
    return original_id.rstrip('_')


def load_lwu_properties(geojson_path: Path, engine, chunk_size: int = 1000) -> None:
    """
    Load LWU property data from GeoJSON into PostgreSQL.
    
    Args:
        geojson_path: Path to the GeoJSON file
        engine: SQLAlchemy engine
        chunk_size: Number of rows to insert per chunk
    """
    logger.info(f"Loading LWU properties from: {geojson_path}")
    
    # Read GeoJSON
    logger.info("Reading GeoJSON file...")
    gdf = gpd.read_file(geojson_path)
    
    logger.info(f"Read {len(gdf)} features from GeoJSON")
    logger.info(f"Current CRS: {gdf.crs}")
    logger.info(f"Geometry types: {gdf.geometry.type.value_counts().to_dict()}")
    
    # Validate that we have the expected columns
    if 'id' not in gdf.columns:
        logger.error("GeoJSON must contain 'id' column")
        raise ValueError("Missing 'id' column in GeoJSON")
    
    # Clean property IDs
    logger.info("Cleaning property IDs (removing trailing underscores)...")
    gdf['property_id'] = gdf['id'].apply(clean_property_id)
    gdf['original_id'] = gdf['id']
    
    # Check for duplicate IDs after cleaning
    duplicates = gdf['property_id'].duplicated().sum()
    if duplicates > 0:
        logger.warning(f"Found {duplicates} duplicate property IDs after cleaning")
        logger.warning("Keeping only first occurrence of each ID")
        gdf = gdf.drop_duplicates(subset=['property_id'], keep='first')
    
    logger.info(f"Cleaned IDs: {len(gdf)} unique properties")
    
    # Reproject to EPSG:3035 (ETRS89-LAEA) to match Zensus data
    if gdf.crs is None:
        logger.warning("No CRS found, assuming EPSG:4326 (WGS84)")
        gdf.set_crs(epsg=4326, inplace=True)
    
    if gdf.crs.to_epsg() != 3035:
        logger.info(f"Reprojecting from {gdf.crs.to_epsg()} to EPSG:3035")
        gdf = gdf.to_crs(epsg=3035)
    
    logger.info("Validating and repairing geometries...")
    # Validate geometries
    invalid_geoms = ~gdf.geometry.is_valid
    if invalid_geoms.sum() > 0:
        logger.warning(f"Found {invalid_geoms.sum()} invalid geometries, repairing...")
        gdf.loc[invalid_geoms, 'geometry'] = gdf.loc[invalid_geoms, 'geometry'].buffer(0)
    
    # Prepare data for insertion
    logger.info("Preparing data for database insertion...")
    gdf_prepared = gdf[['property_id', 'original_id', 'geometry']].copy()
    
    # Rename geometry column to geom for PostGIS
    gdf_prepared = gdf_prepared.rename(columns={'geometry': 'geom'})
    
    # Convert to WKT for insertion
    logger.info("Converting geometries to WKT format...")
    gdf_prepared['geom_wkt'] = gdf_prepared['geom'].apply(lambda g: g.wkt)
    
    # Insert data in chunks
    total_rows = len(gdf_prepared)
    inserted_rows = 0
    error_count = 0
    
    logger.info(f"Inserting {total_rows} rows into zensus.ref_lwu_properties in chunks of {chunk_size}")
    
    with engine.connect() as conn:
        for i in range(0, total_rows, chunk_size):
            chunk = gdf_prepared.iloc[i:i+chunk_size]
            
            try:
                # Prepare batch insert
                records = []
                for _, row in chunk.iterrows():
                    records.append({
                        'property_id': row['property_id'],
                        'original_id': row['original_id'],
                        'geom_wkt': row['geom_wkt']
                    })
                
                # Insert chunk
                insert_stmt = text("""
                    INSERT INTO zensus.ref_lwu_properties (property_id, original_id, geom)
                    VALUES (:property_id, :original_id, ST_GeomFromText(:geom_wkt, 3035))
                    ON CONFLICT (property_id) DO NOTHING
                """)
                
                conn.execute(insert_stmt, records)
                conn.commit()
                inserted_rows += len(chunk)
                logger.info(f"Inserted chunk {i//chunk_size + 1}: {inserted_rows}/{total_rows} rows")
            
            except Exception as e:
                logger.error(f"Error inserting chunk {i//chunk_size + 1}: {e}")
                logger.info(f"Falling back to individual row inserts for chunk {i//chunk_size + 1}")
                
                # Try individual row inserts (only count actual failures, not the entire batch)
                for record in records:
                    try:
                        conn.execute(insert_stmt, record)
                        conn.commit()
                        inserted_rows += 1
                    except Exception as row_error:
                        error_count += 1
                        logger.warning(f"Failed to insert property {record['property_id']}: {row_error}")
    
    logger.info(f"Loading complete: {inserted_rows} rows inserted, {error_count} errors")
    
    # Verify insertion
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM zensus.ref_lwu_properties"))
        count = result.scalar()
        logger.info(f"Total rows in zensus.ref_lwu_properties: {count}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Load LWU Berlin property GeoJSON into PostgreSQL'
    )
    parser.add_argument(
        'geojson_path',
        type=Path,
        help='Path to the LWU properties GeoJSON file'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=1000,
        help='Number of rows to insert per chunk (default: 1000)'
    )
    
    args = parser.parse_args()
    
    if not args.geojson_path.exists():
        logger.error(f"GeoJSON file not found: {args.geojson_path}")
        sys.exit(1)
    
    engine = get_db_engine()
    
    try:
        load_lwu_properties(args.geojson_path, engine, args.chunk_size)
        logger.info("LWU properties loading completed successfully")
    except Exception as e:
        logger.error(f"LWU properties loading failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

