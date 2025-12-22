"""
Load VG250 administrative boundary shapefiles into PostgreSQL reference tables.

Supports loading:
- Federal states (Bundesländer) from VG250_LAN.shp
- Counties (Kreise) from VG250_KRS.shp
- Municipalities (Gemeinden) from VG250_GEM.shp

All geometries are reprojected from EPSG:25832 to EPSG:3035 to match Zensus grid data.
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import geopandas as gpd
from sqlalchemy import text
from etl.utils import get_db_engine, logger


# Mapping from shapefile layer to database table
TABLE_MAPPING = {
    'VG250_LAN': 'ref_federal_state',
    'VG250_KRS': 'ref_county',
    'VG250_GEM': 'ref_municipality'
}

# Expected geometry types for validation
EXPECTED_GEOM_TYPES = {
    'ref_federal_state': ['MultiPolygon', 'Polygon'],
    'ref_county': ['Polygon', 'MultiPolygon'],
    'ref_municipality': ['Polygon', 'MultiPolygon']
}


def get_state_name_from_land_nr(land_nr: str) -> str:
    """
    Get state name from state number (LKZ or first 2 digits of ARS).
    
    Args:
        land_nr: State number (e.g., "01", "02")
    
    Returns:
        State name
    """
    state_map = {
        '01': 'Schleswig-Holstein',
        '02': 'Hamburg',
        '03': 'Niedersachsen',
        '04': 'Bremen',
        '05': 'Nordrhein-Westfalen',
        '06': 'Hessen',
        '07': 'Rheinland-Pfalz',
        '08': 'Baden-Württemberg',
        '09': 'Bayern',
        '10': 'Saarland',
        '11': 'Berlin',
        '12': 'Brandenburg',
        '13': 'Mecklenburg-Vorpommern',
        '14': 'Sachsen',
        '15': 'Sachsen-Anhalt',
        '16': 'Thüringen'
    }
    return state_map.get(land_nr, 'Unknown')


def prepare_vg250_data(gdf: gpd.GeoDataFrame, table_name: str) -> gpd.GeoDataFrame:
    """
    Prepare VG250 GeoDataFrame for database insertion.
    
    Args:
        gdf: Input GeoDataFrame from shapefile
        table_name: Target table name
        
    Returns:
        Prepared GeoDataFrame with correct columns and geometry
    """
    logger.info(f"Preparing {len(gdf)} features for {table_name}")
    logger.info(f"Available columns: {list(gdf.columns)}")
    
    # Ensure CRS is EPSG:3035
    if gdf.crs is None:
        # VG250 shapefiles from BKG are always in EPSG:25832 (ETRS89 / UTM Zone 32N)
        # as confirmed by the .prj files (AUTHORITY["EPSG",25832])
        # This fallback should rarely/never be needed since GeoPandas reads .prj files
        logger.warning("No CRS found in shapefile (unusual). Assuming EPSG:25832 (ETRS89/UTM32N) based on VG250 specification.")
        logger.warning("Verify the .prj file exists and is readable.")
        gdf.set_crs(epsg=25832, inplace=True)
    
    if gdf.crs.to_epsg() != 3035:
        logger.info(f"Reprojecting from {gdf.crs} to EPSG:3035")
        gdf = gdf.to_crs(epsg=3035)
    
    # Validate geometries
    invalid_count = (~gdf.geometry.is_valid).sum()
    if invalid_count > 0:
        logger.warning(f"Found {invalid_count} invalid geometries, fixing with buffer(0)")
        gdf.loc[~gdf.geometry.is_valid, 'geometry'] = gdf.loc[~gdf.geometry.is_valid, 'geometry'].buffer(0)
    
    # Handle geometry types based on table
    expected_types = EXPECTED_GEOM_TYPES.get(table_name, ['Polygon', 'MultiPolygon'])
    logger.info(f"Geometry types in data: {gdf.geometry.type.value_counts().to_dict()}")
    
    if table_name == 'ref_federal_state':
        # Federal states should be MultiPolygon (for states with islands)
        def to_multipolygon(geom):
            if geom.geom_type == 'Polygon':
                from shapely.geometry import MultiPolygon
                return MultiPolygon([geom])
            return geom
        gdf['geometry'] = gdf.geometry.apply(to_multipolygon)
    else:
        # Counties and municipalities: prefer Polygon, but accept MultiPolygon
        # Keep as-is since both are valid
        pass
    
    # Extract required columns based on table type
    result_df = gpd.GeoDataFrame()
    
    # Common columns (all VG250 layers have these)
    result_df['ars'] = gdf['ARS'].astype(str)
    result_df['ags'] = gdf['AGS'].astype(str) if 'AGS' in gdf.columns else gdf['ARS'].astype(str)
    result_df['name'] = gdf['GEN'].astype(str)
    result_df['bez'] = gdf['BEZ'].astype(str) if 'BEZ' in gdf.columns else None
    result_df['nuts'] = gdf['NUTS'].astype(str) if 'NUTS' in gdf.columns else None
    
    # Extract state number (first 2 digits of ARS)
    result_df['land_nr'] = result_df['ars'].str[:2]
    
    # Add state name for counties and municipalities
    if table_name in ['ref_county', 'ref_municipality']:
        result_df['land_name'] = result_df['land_nr'].apply(get_state_name_from_land_nr)
    
    # Parse BEGINN date (format: YYYY-MM-DD in shapefile)
    if 'BEGINN' in gdf.columns:
        result_df['beginn'] = gpd.pd.to_datetime(gdf['BEGINN'], errors='coerce')
    else:
        result_df['beginn'] = None
    
    # Geometry column
    result_df['geom'] = gdf.geometry
    result_df = result_df.set_geometry('geom', crs=3035)
    
    logger.info(f"Prepared {len(result_df)} features with columns: {list(result_df.columns)}")
    logger.info(f"Sample ARS codes: {result_df['ars'].head(3).tolist()}")
    
    return result_df


def load_vg250_shapefile(shapefile_path: Path, table_name: str, engine, chunk_size: int = 1000):
    """
    Load VG250 shapefile into PostgreSQL table.
    
    Args:
        shapefile_path: Path to the shapefile
        table_name: Target table name (ref_federal_state, ref_county, ref_municipality)
        engine: Database engine
        chunk_size: Number of rows to insert per chunk
    """
    logger.info(f"Loading VG250 shapefile: {shapefile_path}")
    logger.info(f"Target table: zensus.{table_name}")
    
    # Read shapefile
    try:
        gdf = gpd.read_file(shapefile_path)
        logger.info(f"Read {len(gdf)} features from shapefile")
    except Exception as e:
        logger.error(f"Failed to read shapefile: {e}")
        raise
    
    # Prepare data
    gdf_prepared = prepare_vg250_data(gdf, table_name)
    
    # Insert data in chunks
    total_rows = len(gdf_prepared)
    inserted_rows = 0
    error_count = 0
    
    logger.info(f"Inserting {total_rows} rows into zensus.{table_name} in chunks of {chunk_size}")
    
    for i in range(0, total_rows, chunk_size):
        chunk = gdf_prepared.iloc[i:i+chunk_size].copy()
        
        # Prepare batch insert
        records = []
        for idx, row in chunk.iterrows():
            records.append({
                'ars': row['ars'],
                'ags': row['ags'],
                'name': row['name'],
                'bez': row['bez'],
                'nuts': row['nuts'],
                'land_nr': row['land_nr'],
                'land_name': row.get('land_name'),  # Only for counties and municipalities
                'beginn': row['beginn'],
                'geom_wkb': row['geom'].wkb
            })
        
        try:
            # Build INSERT statement based on table type
            if table_name == 'ref_federal_state':
                insert_stmt = text(f"""
                    INSERT INTO zensus.{table_name} (ars, ags, name, bez, nuts, land_nr, beginn, geom)
                    VALUES (:ars, :ags, :name, :bez, :nuts, :land_nr, :beginn, 
                            ST_SetSRID(ST_GeomFromWKB(:geom_wkb), 3035))
                    ON CONFLICT (ars) DO NOTHING
                """)
            else:
                insert_stmt = text(f"""
                    INSERT INTO zensus.{table_name} (ars, ags, name, bez, nuts, land_nr, land_name, beginn, geom)
                    VALUES (:ars, :ags, :name, :bez, :nuts, :land_nr, :land_name, :beginn,
                            ST_SetSRID(ST_GeomFromWKB(:geom_wkb), 3035))
                    ON CONFLICT (ars) DO NOTHING
                """)
            
            with engine.connect() as conn:
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
                    with engine.connect() as conn:
                        conn.execute(insert_stmt, record)
                        conn.commit()
                        inserted_rows += 1
                except Exception as row_error:
                    error_count += 1
                    logger.warning(f"Failed to insert ARS {record['ars']}: {row_error}")
    
    logger.info(f"Loading complete: {inserted_rows} rows inserted, {error_count} errors")
    
    # Verify insertion
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM zensus.{table_name}"))
        count = result.scalar()
        logger.info(f"Total rows in zensus.{table_name}: {count}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Load VG250 administrative boundary shapefiles into PostgreSQL'
    )
    parser.add_argument(
        'shapefile_path',
        type=Path,
        help='Path to the VG250 shapefile (e.g., VG250_LAN.shp, VG250_KRS.shp, VG250_GEM.shp)'
    )
    parser.add_argument(
        '--table',
        choices=['ref_federal_state', 'ref_county', 'ref_municipality'],
        required=True,
        help='Target table name'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=1000,
        help='Number of rows to insert per chunk (default: 1000)'
    )
    
    args = parser.parse_args()
    
    if not args.shapefile_path.exists():
        logger.error(f"Shapefile not found: {args.shapefile_path}")
        
        # Suggest possible files
        shp_dir = args.shapefile_path.parent
        if shp_dir.exists():
            available_files = list(shp_dir.glob('VG250_*.shp'))
            if available_files:
                logger.error(f"Available VG250 shapefiles in {shp_dir}:")
                for f in available_files:
                    logger.error(f"  - {f.name}")
        sys.exit(1)
    
    engine = get_db_engine()
    
    try:
        load_vg250_shapefile(args.shapefile_path, args.table, engine, args.chunk_size)
        logger.info("VG250 loading completed successfully")
    except Exception as e:
        logger.error(f"VG250 loading failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

