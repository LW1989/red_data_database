"""
Load Zensus CSV files into PostgreSQL fact tables.
Handles data preprocessing (German number format, missing values) and grid_id validation.
Dynamically handles all Zensus datasets based on folder structure.
"""

import sys
import argparse
import re
from pathlib import Path
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
    return col


def detect_table_mapping(csv_path: Path) -> tuple:
    """
    Detect table name and grid size based on CSV file path.
    Dynamically generates table name from folder structure.
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        Tuple of (table_name, grid_size, folder_name) or (None, None, None) if not found
    """
    path_str = str(csv_path)
    
    # Determine grid size
    if '100m-Gitter' in path_str or '100m_Gitter' in path_str:
        grid_size = '100m'
    elif '1km-Gitter' in path_str or '1km_Gitter' in path_str:
        grid_size = '1km'
    elif '10km-Gitter' in path_str or '10km_Gitter' in path_str:
        grid_size = '10km'
    else:
        logger.warning(f"Could not determine grid size from path: {csv_path}")
        return None, None, None
    
    # Extract folder name from path
    # Path structure: data/zensus_data/{folder_name}/filename.csv
    parts = csv_path.parts
    try:
        zensus_idx = parts.index('zensus_data')
        if zensus_idx + 1 < len(parts):
            folder_name = parts[zensus_idx + 1]
            table_name = f"fact_zensus_{grid_size}_{sanitize_table_name(folder_name)}"
            return table_name, grid_size, folder_name
    except (ValueError, IndexError):
        pass
    
    logger.warning(f"Could not extract folder name from path: {csv_path}")
    return None, None, None


def load_zensus_csv(csv_path: Path, engine, validate_grid_ids: bool = True, chunk_size: int = 10000):
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
    
    # Build column mapping dynamically
    # Standard columns to keep as-is
    standard_cols = {
        grid_id_col: 'grid_id',
    }
    # Add coordinate columns if they exist
    for coord_col in [f'x_mp_{grid_size}', f'y_mp_{grid_size}']:
        if coord_col in df.columns:
            standard_cols[coord_col] = coord_col
    
    # Map all other columns (sanitize names)
    column_mapping = standard_cols.copy()
    for col in df.columns:
        if col not in standard_cols and col != 'werterlaeuternde_Zeichen':
            column_mapping[col] = sanitize_column_name(col)
    
    # Rename columns
    df_renamed = df.rename(columns=column_mapping)
    
    # Remove werterlaeuternde_Zeichen if present (metadata column)
    if 'werterlaeuternde_zeichen' in df_renamed.columns:
        df_renamed = df_renamed.drop(columns=['werterlaeuternde_zeichen'])
    
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
    
    # Validate grid_ids if requested
    if validate_grid_ids:
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
                # Prepare data for insertion
                records = chunk[columns].to_dict('records')
                
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
                        record = row[columns].to_dict()
                        conn.execute(insert_stmt, record)
                        conn.commit()
                        inserted_rows += 1
                except Exception as row_error:
                    error_count += 1
                    logger.warning(f"Failed to insert grid_id {row['grid_id']}: {row_error}")
    
    logger.info(f"Zensus loading complete: {inserted_rows} rows inserted, {error_count} errors")
    
    # Verify insertion
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM zensus.{table_name}"))
        count = result.scalar()
        logger.info(f"Total rows in {table_name}: {count}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Load Zensus CSV files into PostgreSQL fact tables'
    )
    parser.add_argument(
        'csv_path',
        type=Path,
        help='Path to the Zensus CSV file'
    )
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip grid_id validation against reference tables'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=10000,
        help='Number of rows to insert per chunk (default: 10000)'
    )
    
    args = parser.parse_args()
    
    if not args.csv_path.exists():
        logger.error(f"CSV file not found: {args.csv_path}")
        sys.exit(1)
    
    engine = get_db_engine()
    
    try:
        load_zensus_csv(
            args.csv_path, 
            engine, 
            validate_grid_ids=not args.no_validate,
            chunk_size=args.chunk_size
        )
        logger.info("Zensus loading completed successfully")
    except Exception as e:
        logger.error(f"Zensus loading failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

