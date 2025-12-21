"""
Load GeoGitter INSPIRE GPKG files into PostgreSQL reference grid tables.
"""

import sys
import argparse
from pathlib import Path
import geopandas as gpd
from sqlalchemy import text
from etl.utils import get_db_engine, logger


def load_grid_from_gpkg(gpkg_path: Path, grid_size: str, engine, chunk_size: int = 10000):
    """
    Load grid geometries from a GPKG file into the reference grid table.
    
    Args:
        gpkg_path: Path to the GPKG file
        grid_size: Grid size ('100m', '1km', or '10km')
        engine: Database engine
        chunk_size: Number of rows to insert per chunk
    """
    logger.info(f"Loading {grid_size} grid from {gpkg_path}")
    
    # Read GPKG file
    # For very large files (100m grid ~12GB), we need to handle memory carefully
    # Check file size first and use chunked reading if needed
    file_size_mb = gpkg_path.stat().st_size / (1024 * 1024)
    logger.info(f"GPKG file size: {file_size_mb:.2f} MB")
    
    try:
        # For files > 1GB, read in chunks to avoid memory issues
        if file_size_mb > 1000:
            logger.warning(f"Large file detected ({file_size_mb:.2f} MB). Consider using chunked reading.")
            logger.info("Reading GPKG file (this may take a while for large files)...")
        
        gdf = gpd.read_file(gpkg_path)
        logger.info(f"Read {len(gdf)} features from GPKG file")
    except MemoryError:
        logger.error(f"Out of memory reading {gpkg_path}. File is too large ({file_size_mb:.2f} MB).")
        logger.error("Consider using a machine with more RAM or implementing chunked reading.")
        raise
    except Exception as e:
        logger.error(f"Failed to read GPKG file: {e}")
        raise
    
    # Ensure CRS is EPSG:3035
    if gdf.crs is None:
        logger.warning("No CRS found in GPKG, assuming EPSG:3035")
        gdf.set_crs(epsg=3035, inplace=True)
    elif gdf.crs.to_epsg() != 3035:
        logger.info(f"Reprojecting from {gdf.crs} to EPSG:3035")
        gdf = gdf.to_crs(epsg=3035)
    
    # Construct grid_id from GPKG coordinates to match CSV format
    # CSV format: CRS3035RES{size}mN{y_mp}E{x_mp}
    # GPKG has x_mp and y_mp columns with cell center coordinates
    logger.info(f"Available columns in GPKG: {list(gdf.columns)}")
    
    # Verify required columns exist
    if 'x_mp' not in gdf.columns or 'y_mp' not in gdf.columns:
        logger.error(f"GPKG file missing x_mp or y_mp columns. Available: {list(gdf.columns)}")
        raise ValueError(f"GPKG file must contain x_mp and y_mp columns for grid_id construction")
    
    # Size mapping for grid_id format
    size_map = {'100m': '100m', '1km': '1000m', '10km': '10000m'}
    size_str = size_map.get(grid_size, f'{grid_size}m')
    
    # Construct grid_id in CSV format: CRS3035RES{size}mN{y_mp}E{x_mp}
    # Coordinates are cell centers (x_mp, y_mp)
    gdf['grid_id'] = gdf.apply(
        lambda row: f"CRS3035RES{size_str}N{int(row['y_mp'])}E{int(row['x_mp'])}",
        axis=1
    )
    
    logger.info(f"Constructed grid_id from x_mp/y_mp coordinates (format: CRS3035RES{size_str}N{{y}}E{{x}})")
    logger.info(f"Sample grid_id: {gdf['grid_id'].iloc[0] if len(gdf) > 0 else 'N/A'}")
    
    # Select only required columns
    gdf = gdf[['grid_id', 'geometry']]
    
    # Validate geometries
    invalid_count = (~gdf.geometry.is_valid).sum()
    if invalid_count > 0:
        logger.warning(f"Found {invalid_count} invalid geometries, attempting to fix")
        gdf.loc[~gdf.geometry.is_valid, 'geometry'] = gdf.loc[~gdf.geometry.is_valid, 'geometry'].buffer(0)
    
    # Ensure polygons (not multipolygons)
    if gdf.geometry.type.str.contains('MultiPolygon').any():
        logger.info("Converting MultiPolygon to Polygon (taking first polygon)")
        gdf['geometry'] = gdf.geometry.apply(
            lambda geom: geom.geoms[0] if hasattr(geom, 'geoms') else geom
        )
    
    table_name = f"ref_grid_{grid_size}"
    
    # Insert data in chunks
    total_rows = len(gdf)
    inserted_rows = 0
    error_count = 0
    
    logger.info(f"Inserting {total_rows} rows into {table_name} in chunks of {chunk_size}")
    
    for i in range(0, total_rows, chunk_size):
        chunk = gdf.iloc[i:i+chunk_size].copy()
        
        try:
            # Use GeoPandas to_postgis for geometry handling
            chunk.to_postgis(
                name=table_name,
                con=engine,
                schema='zensus',
                if_exists='append',
                index=False
            )
            inserted_rows += len(chunk)
            logger.info(f"Inserted chunk {i//chunk_size + 1}: {inserted_rows}/{total_rows} rows")
        except Exception as e:
            error_count += len(chunk)
            logger.error(f"Error inserting chunk {i//chunk_size + 1}: {e}")
            # Try individual row inserts for this chunk
            for idx, row in chunk.iterrows():
                try:
                    with engine.connect() as conn:
                        conn.execute(
                            text(f"""
                                INSERT INTO zensus.{table_name} (grid_id, geom)
                                VALUES (:grid_id, ST_GeomFromWKB(:geom, 3035))
                                ON CONFLICT (grid_id) DO NOTHING
                            """),
                            {
                                'grid_id': row['grid_id'],
                                'geom': row['geometry'].wkb
                            }
                        )
                        conn.commit()
                        inserted_rows += 1
                except Exception as row_error:
                    error_count += 1
                    logger.warning(f"Failed to insert grid_id {row['grid_id']}: {row_error}")
    
    logger.info(f"Grid loading complete: {inserted_rows} rows inserted, {error_count} errors")
    
    # Verify insertion
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM zensus.{table_name}"))
        count = result.scalar()
        logger.info(f"Total rows in {table_name}: {count}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Load GeoGitter INSPIRE GPKG files into PostgreSQL'
    )
    parser.add_argument(
        'gpkg_path',
        type=Path,
        help='Path to the GPKG file'
    )
    parser.add_argument(
        'grid_size',
        choices=['100m', '1km', '10km'],
        help='Grid size (100m, 1km, or 10km)'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=10000,
        help='Number of rows to insert per chunk (default: 10000)'
    )
    
    args = parser.parse_args()
    
    if not args.gpkg_path.exists():
        logger.error(f"GPKG file not found: {args.gpkg_path}")
        sys.exit(1)
    
    engine = get_db_engine()
    
    try:
        load_grid_from_gpkg(args.gpkg_path, args.grid_size, engine, args.chunk_size)
        logger.info("Grid loading completed successfully")
    except Exception as e:
        logger.error(f"Grid loading failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

