"""
Load Zensus CSV files into PostgreSQL fact tables.
Handles data preprocessing (German number format, missing values) and grid_id validation.
Dynamically handles all Zensus datasets based on folder structure.
"""

import sys
import argparse
import re
from pathlib import Path

# Add project root to Python path so we can import etl module
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from sqlalchemy import text
from etl.utils import (
    get_db_engine, 
    logger, 
    preprocess_zensus_dataframe,
    validate_grid_id_exists
)


def sanitize_table_name(folder_name: str) -> str:
    """Convert folder name to valid PostgreSQL table name."""
    # Remove special characters, keep underscores
    name = re.sub(r'[^a-zA-Z0-9_]', '_', folder_name)
    # Convert to lowercase
    name = name.lower()
    # Remove multiple underscores
    name = re.sub(r'_+', '_', name)
    return name


def sanitize_column_name(col_name: str) -> str:
    """Convert CSV column name to valid PostgreSQL column name."""
    # Convert to lowercase
    col = col_name.lower()
    # Replace special characters with underscores
    col = re.sub(r'[^a-z0-9_]', '_', col)
    # Remove multiple underscores
    col = re.sub(r'_+', '_', col)
    # Remove leading/trailing underscores
    col = col.strip('_')
    # PostgreSQL identifiers cannot start with a number
    # If column name starts with a digit, prefix with 'col_'
    if col and col[0].isdigit():
        col = 'col_' + col
    return col


def detect_table_mapping(csv_path: Path) -> tuple:
    """
    Detect table name and grid size based on CSV file path.
    Supports both old structure (dataset folders) and new structure (grid-size folders).
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        Tuple of (table_name, grid_size, dataset_name) or (None, None, None) if not found
    """
    import re
    path_str = str(csv_path)
    filename = csv_path.name
    
    # Determine grid size from filename or path
    if '100m-Gitter' in path_str or '100m_Gitter' in path_str or '100m-Gitter' in filename:
        grid_size = '100m'
    elif '1km-Gitter' in path_str or '1km_Gitter' in path_str or '1km-Gitter' in filename:
        grid_size = '1km'
    elif '10km-Gitter' in path_str or '10km_Gitter' in path_str or '10km-Gitter' in filename:
        grid_size = '10km'
    else:
        logger.warning(f"Could not determine grid size from path: {csv_path}")
        return None, None, None
    
    # Extract dataset name from filename or folder structure
    # New structure: data/zensus_data/{grid_size}/Zensus2022_DatasetName_{grid_size}-Gitter.csv
    # Old structure: data/zensus_data/{dataset_folder}/Zensus2022_DatasetName_{grid_size}-Gitter.csv
    
    parts = csv_path.parts
    try:
        zensus_idx = parts.index('zensus_data')
        
        # Check if new structure (grid-size folders: 10km, 1km, 100m)
        if zensus_idx + 1 < len(parts):
            parent_folder = parts[zensus_idx + 1]
            if parent_folder in ['10km', '1km', '100m']:
                # New structure: extract dataset name from filename
                # Example: Zensus2022_Bevoelkerungszahl_10km-Gitter.csv -> Bevoelkerungszahl
                dataset_name = filename.replace('Zensus2022_', '')
                # Remove grid size suffix
                dataset_name = re.sub(r'_[0-9]+km-Gitter\.csv$', '', dataset_name)
                dataset_name = re.sub(r'_100m-Gitter\.csv$', '', dataset_name)
                dataset_name = dataset_name.strip('_')
            else:
                # Old structure: use folder name as dataset name
                dataset_name = parent_folder
        else:
            # Fallback: try to extract from filename
            dataset_name = filename.replace('Zensus2022_', '')
            dataset_name = re.sub(r'_[0-9]+km-Gitter\.csv$', '', dataset_name)
            dataset_name = re.sub(r'_100m-Gitter\.csv$', '', dataset_name)
            dataset_name = dataset_name.strip('_')
        
        if dataset_name:
            table_name = f"fact_zensus_{grid_size}_{sanitize_table_name(dataset_name)}"
            return table_name, grid_size, dataset_name
    except (ValueError, IndexError):
        pass
    
    logger.warning(f"Could not extract dataset name from path: {csv_path}")
    return None, None, None


def load_zensus_csv(csv_path: Path, engine, validate_grid_ids: bool = True, chunk_size: int = 50000):
    """
    Load a Zensus CSV file into the appropriate fact table.
    Dynamically handles all Zensus datasets.
    
    Args:
        csv_path: Path to CSV file
        engine: Database engine
        validate_grid_ids: Whether to validate grid_ids exist in reference tables
        chunk_size: Number of rows to insert per chunk
    """
    logger.info(f"Loading Zensus data from {csv_path}")
    
    # Detect table name and grid size
    table_name, grid_size, folder_name = detect_table_mapping(csv_path)
    if table_name is None:
        logger.error(f"Could not determine table mapping for {csv_path}")
        return
    
    logger.info(f"Using table: {table_name}, grid_size: {grid_size}, folder: {folder_name}")
    
    # Read CSV (semicolon-delimited)
    # Parameters:
    # - sep=';': German CSV files use semicolon as delimiter
    # - encoding='utf-8': Handles German characters and em-dash properly
    # - low_memory=False: Read entire file into memory for better type inference
    # - on_bad_lines='skip': Skip malformed lines instead of failing
    try:
        df = pd.read_csv(
            csv_path, 
            sep=';', 
            encoding='utf-8', 
            low_memory=False,
            on_bad_lines='skip'  # Skip malformed lines gracefully
        )
        logger.info(f"Read {len(df)} rows from CSV with columns: {list(df.columns)}")
    except Exception as e:
        logger.error(f"Failed to read CSV file: {e}")
        raise
    
    # Determine grid_id column name (handle both GITTER_ID and Gitter_ID typo)
    grid_id_col = None
    for col in [f'GITTER_ID_{grid_size}', f'Gitter_ID_{grid_size}', f'GITTER_ID_100m', f'Gitter_ID_100m']:
        if col in df.columns:
            grid_id_col = col
            break
    
    if grid_id_col is None:
        logger.error(f"Grid ID column not found in CSV. Expected: GITTER_ID_{grid_size} or Gitter_ID_{grid_size}")
        return
    
    # Reconstruct grid_id from x_mp/y_mp to match database format
    # CSV files have grid_ids with corner coordinates, but database uses center coordinates
    # We need to reconstruct grid_id from x_mp/y_mp (center coordinates) to match the database
    x_mp_col = f'x_mp_{grid_size}'
    y_mp_col = f'y_mp_{grid_size}'
    
    if x_mp_col in df.columns and y_mp_col in df.columns:
        # Size mapping for grid_id format
        size_map = {'100m': '100m', '1km': '1000m', '10km': '10000m'}
        size_str = size_map.get(grid_size, f'{grid_size}m')
        
        # Reconstruct grid_id from center coordinates (x_mp, y_mp) to match database
        df['grid_id'] = df.apply(
            lambda row: f"CRS3035RES{size_str}N{int(row[y_mp_col])}E{int(row[x_mp_col])}",
            axis=1
        )
        logger.info(f"Reconstructed grid_id from {x_mp_col}/{y_mp_col} (center coordinates) to match database format")
    else:
        # Fallback: use the grid_id column from CSV (may not match database)
        df['grid_id'] = df[grid_id_col]
        logger.warning(f"Could not find {x_mp_col} or {y_mp_col} columns. Using grid_id from CSV (may not match database format)")
    
    # Build column mapping dynamically
    # Standard columns to keep as-is (but sanitize to lowercase for PostgreSQL)
    standard_cols = {
        'grid_id': 'grid_id',
    }
    # Add coordinate columns if they exist (sanitize to lowercase to match schema)
    for coord_col in [x_mp_col, y_mp_col]:
        if coord_col in df.columns:
            standard_cols[coord_col] = sanitize_column_name(coord_col)
    
    # Map all other columns (sanitize names)
    # Exclude the original grid_id column (GITTER_ID_10km) since we use the reconstructed grid_id
    column_mapping = standard_cols.copy()
    for col in df.columns:
        if col not in standard_cols and col != 'werterlaeuternde_Zeichen' and col != grid_id_col:
            column_mapping[col] = sanitize_column_name(col)
    
    # Rename columns
    df_renamed = df.rename(columns=column_mapping)
    
    # Remove the original grid_id column (GITTER_ID_10km) since we use the reconstructed grid_id
    # Also remove werterlaeuternde_Zeichen if present (metadata column) - check both original and renamed versions
    cols_to_drop = []
    if grid_id_col in df_renamed.columns:
        cols_to_drop.append(grid_id_col)
    # Check for werterlaeuternde_Zeichen in both original form and sanitized form
    for col in df_renamed.columns:
        if col.lower() == 'werterlaeuternde_zeichen' or col == 'werterlaeuternde_Zeichen':
            cols_to_drop.append(col)
    if cols_to_drop:
        df_renamed = df_renamed.drop(columns=cols_to_drop)
    
    # Add year column
    df_renamed['year'] = 2022
    
    # Determine integer vs numeric columns by checking for decimal commas in the data
    # If a column contains values with commas followed by digits (e.g., "129,1"), it's numeric
    # Otherwise, it's treated as integer
    integer_cols = []
    numeric_cols = []
    
    for col in df_renamed.columns:
        if col in ['grid_id', 'year'] or col.startswith('x_mp_') or col.startswith('y_mp_'):
            continue
        
        # Check if column contains decimal commas (German format: "129,1")
        # Pattern: comma followed by at least one digit (not just trailing comma)
        sample_values = df_renamed[col].dropna().astype(str).head(100)
        # Match comma followed by one or more digits (e.g., "129,1" or "129,12")
        has_decimal_comma = sample_values.str.contains(r',\d+', regex=True, na=False).any()
        
        if has_decimal_comma:
            numeric_cols.append(col)
            logger.debug(f"Column '{col}' detected as NUMERIC (contains decimal commas)")
        else:
            integer_cols.append(col)
            logger.debug(f"Column '{col}' detected as INTEGER (no decimal commas)")
    
    # Preprocess data (comma decimals, em-dash to NULL)
    df_processed = preprocess_zensus_dataframe(
        df_renamed,
        integer_columns=integer_cols,
        numeric_columns=numeric_cols
    )
    
    # Validate grid_ids if requested (skip for 100m due to performance - 38M reference rows)
    if validate_grid_ids and grid_size != '100m':
        logger.info("Validating grid_ids against reference tables...")
        invalid_grid_ids = []
        for grid_id in df_processed['grid_id'].unique():
            if not validate_grid_id_exists(engine, grid_id, grid_size):
                invalid_grid_ids.append(grid_id)
        
        if invalid_grid_ids:
            logger.warning(f"Found {len(invalid_grid_ids)} invalid grid_ids (first 10: {invalid_grid_ids[:10]})")
            # Remove rows with invalid grid_ids
            initial_count = len(df_processed)
            df_processed = df_processed[~df_processed['grid_id'].isin(invalid_grid_ids)]
            logger.info(f"Removed {initial_count - len(df_processed)} rows with invalid grid_ids")
    elif validate_grid_ids and grid_size == '100m':
        logger.info("Skipping grid_id validation for 100m (performance: 38M reference rows)")
    
    # Insert data in chunks
    total_rows = len(df_processed)
    inserted_rows = 0
    error_count = 0
    
    if total_rows == 0:
        logger.warning("No rows to insert after preprocessing and validation")
        return
    
    logger.info(f"Inserting {total_rows} rows into {table_name} in chunks of {chunk_size}")
    
    # Get column names for INSERT statement
    columns = [col for col in df_processed.columns if col != 'geometry']
    columns_str = ', '.join(columns)
    placeholders = ', '.join([f':{col}' for col in columns])
    
    for i in range(0, total_rows, chunk_size):
        chunk = df_processed.iloc[i:i+chunk_size]
        
        try:
            with engine.connect() as conn:
                # Prepare data for insertion (replace NaN with None for NULL values)
                chunk_clean = chunk[columns].where(pd.notna(chunk[columns]), None)
                records = chunk_clean.to_dict('records')
                
                # Build dynamic UPDATE clause safely
                update_clause = ', '.join([f'{col} = EXCLUDED.{col}' for col in columns if col not in ['grid_id', 'year']])
                
                # Insert with ON CONFLICT DO UPDATE to handle duplicates
                # Note: table_name is validated against known mappings, so safe to use
                insert_stmt = text(f"""
                    INSERT INTO zensus.{table_name} ({columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT (grid_id) DO UPDATE SET
                        year = EXCLUDED.year,
                        {update_clause}
                """)
                
                conn.execute(insert_stmt, records)
                conn.commit()
                
                inserted_rows += len(chunk)
                logger.info(f"Inserted chunk {i//chunk_size + 1}: {inserted_rows}/{total_rows} rows")
        except Exception as e:
            error_count += len(chunk)
            logger.error(f"Error inserting chunk {i//chunk_size + 1}: {e}")
            # Try individual row inserts for this chunk
            for idx, row in chunk.iterrows():
                try:
                    with engine.connect() as conn:
                        # Replace NaN with None for NULL values
                        row_clean = row[columns].where(pd.notna(row[columns]), None)
                        record = row_clean.to_dict()
                        conn.execute(insert_stmt, record)
                        conn.commit()
                        inserted_rows += 1
                except Exception as row_error:
                    error_count += 1
                    logger.warning(f"Failed to insert grid_id {row['grid_id']}: {row_error}")
    
    logger.info(f"Zensus loading complete: {inserted_rows} rows inserted, {error_count} errors")
    
    # Verify insertion (only if rows were inserted)
    if inserted_rows > 0:
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM zensus.{table_name}"))
                count = result.scalar()
                logger.info(f"Total rows in {table_name}: {count}")
        except Exception as e:
            logger.warning(f"Could not verify row count in {table_name} (table may not exist yet): {e}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Load Zensus CSV files into PostgreSQL fact tables',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load a single CSV file:
  python etl/load_zensus.py data/zensus_data/10km/Zensus2022_Bevoelkerungszahl_10km-Gitter.csv
  
  # Load all CSV files from a folder (e.g., all 10km files):
  python etl/load_zensus.py data/zensus_data/10km/
  
  # Load all CSV files recursively from a directory:
  python etl/load_zensus.py data/zensus_data/10km/ --recursive
        """
    )
    parser.add_argument(
        'csv_path',
        type=Path,
        help='Path to a Zensus CSV file or directory containing CSV files'
    )
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip grid_id validation against reference tables'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=50000,
        help='Number of rows to insert per chunk (default: 50000)'
    )
    parser.add_argument(
        '--recursive',
        action='store_true',
        help='If csv_path is a directory, recursively search for CSV files'
    )
    
    args = parser.parse_args()
    
    if not args.csv_path.exists():
        logger.error(f"Path not found: {args.csv_path}")
        sys.exit(1)
    
    engine = get_db_engine()
    
    # Determine if path is a file or directory
    csv_files = []
    if args.csv_path.is_file():
        if args.csv_path.suffix.lower() == '.csv':
            csv_files = [args.csv_path]
        else:
            logger.error(f"File is not a CSV file: {args.csv_path}")
            sys.exit(1)
    elif args.csv_path.is_dir():
        # Find all CSV files in directory
        if args.recursive:
            csv_files = list(args.csv_path.rglob('*.csv'))
        else:
            csv_files = list(args.csv_path.glob('*.csv'))
        
        if not csv_files:
            logger.error(f"No CSV files found in: {args.csv_path}")
            sys.exit(1)
        
        logger.info(f"Found {len(csv_files)} CSV file(s) to load")
    else:
        logger.error(f"Path is neither a file nor directory: {args.csv_path}")
        sys.exit(1)
    
    # Load each CSV file
    success_count = 0
    error_count = 0
    
    for csv_file in csv_files:
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"Loading: {csv_file.name}")
            logger.info(f"{'='*60}")
            load_zensus_csv(
                csv_file, 
                engine, 
                validate_grid_ids=not args.no_validate,
                chunk_size=args.chunk_size
            )
            success_count += 1
        except Exception as e:
            error_count += 1
            logger.error(f"Failed to load {csv_file}: {e}", exc_info=True)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Loading Summary: {success_count} succeeded, {error_count} failed")
    logger.info(f"{'='*60}")
    
    if error_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()

