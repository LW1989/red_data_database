#!/usr/bin/env python3
"""
Generate SQL schema for all Zensus fact tables based on CSV file headers and data.
This script reads all 10km CSV files, inspects actual data values, and generates table definitions.
Data types are determined by inspecting the data itself (presence of decimal commas), not column names.
"""

import csv
import sys
from pathlib import Path
import re
import pandas as pd

def sanitize_column_name(col_name):
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

def sanitize_table_name(folder_name):
    """Convert folder name to valid PostgreSQL table name."""
    # Remove special characters, keep underscores
    name = re.sub(r'[^a-zA-Z0-9_]', '_', folder_name)
    # Convert to lowercase
    name = name.lower()
    # Remove multiple underscores
    name = re.sub(r'_+', '_', name)
    return name

def determine_column_type_from_data(col_name, sample_values, pandas_dtype=None):
    """
    Determine PostgreSQL column type by inspecting actual data values.
    
    Checks if column contains decimal commas (German format: "129,1") or if values
    are floats to distinguish between INTEGER and NUMERIC types.
    This matches the logic used in the ETL pipeline.
    
    Args:
        col_name: Column name (for logging/debugging)
        sample_values: List or Series of sample values from the column
        pandas_dtype: Pandas dtype of the column (optional, helps detect float columns)
        
    Returns:
        'INTEGER' or 'NUMERIC'
    """
    if not sample_values or len(sample_values) == 0:
        # No data to inspect, default to NUMERIC (safer than INTEGER)
        return 'NUMERIC'
    
    # Convert to pandas Series for easier manipulation
    sample_series = pd.Series(sample_values).dropna()
    
    if len(sample_series) == 0:
        # All values are missing, default to NUMERIC
        return 'NUMERIC'
    
    # Check if values are numeric (int or float)
    try:
        # Try to convert to numeric
        numeric_values = pd.to_numeric(sample_series, errors='coerce')
        numeric_values = numeric_values.dropna()
        
        if len(numeric_values) == 0:
            # Couldn't convert to numeric, default to NUMERIC
            return 'NUMERIC'
        
        # Check if any value is a float (has decimal part)
        has_decimal = (numeric_values % 1 != 0).any()
        if has_decimal:
            return 'NUMERIC'
    except:
        pass
    
    # Check for decimal commas in string representation (German format: "129,1")
    sample_str = sample_series.astype(str)
    has_decimal_comma = sample_str.str.contains(r',\d+', regex=True, na=False).any()
    
    if has_decimal_comma:
        return 'NUMERIC'
    
    # Check if column contains em-dash (German missing value indicator: "–")
    # If it does, the ETL will convert it to NaN, which will cause pandas to convert
    # the column to float64. So we should use NUMERIC instead of INTEGER.
    has_em_dash = sample_str.str.contains('–', na=False).any()
    if has_em_dash:
        return 'NUMERIC'
    
    # IMPORTANT: If ANY column in the CSV has em-dash, pandas may convert ALL integer
    # columns to float64 during preprocessing (when NaN values are introduced).
    # To be safe, if the pandas dtype is float (even if values are whole numbers),
    # use NUMERIC instead of INTEGER.
    # Check the pandas dtype first (most reliable)
    if pandas_dtype is not None and pd.api.types.is_float_dtype(pandas_dtype):
        # If pandas detected it as float (possibly due to NaN in other columns), use NUMERIC
        return 'NUMERIC'
    
    # Also check the sample_series dtype as fallback
    if pd.api.types.is_float_dtype(sample_series.dtype):
        # If pandas detected it as float (possibly due to NaN), use NUMERIC
        return 'NUMERIC'
    
    # Additional safety check: if any values in the sample are floats (have .0 suffix)
    # This can happen when pandas converts integers to floats due to NaN in the DataFrame
    try:
        numeric_vals = pd.to_numeric(sample_series, errors='coerce').dropna()
        if len(numeric_vals) > 0:
            # Check if values are stored as floats (even if they're whole numbers like 87.0)
            # This happens when pandas converts int columns to float due to NaN elsewhere
            if pd.api.types.is_float_dtype(numeric_vals.dtype):
                return 'NUMERIC'
    except:
        pass
    
    return 'INTEGER'

def read_csv_data(csv_path, max_rows=100):
    """
    Read CSV file and return headers and sample data.
    
    Args:
        csv_path: Path to CSV file
        max_rows: Maximum number of data rows to read for type detection
        
    Returns:
        Tuple of (headers, data_dict, dtype_dict) where:
        - headers: List of column names
        - data_dict: Maps column names to sample values
        - dtype_dict: Maps column names to pandas dtypes
    """
    try:
        # Read CSV with pandas to handle encoding and delimiters correctly
        df = pd.read_csv(
            csv_path,
            sep=';',
            encoding='utf-8',
            nrows=max_rows,
            low_memory=False
        )
        
        # Check if ANY column in the CSV has em-dash values
        # If so, pandas may convert all integer columns to float64 during preprocessing
        has_em_dash_anywhere = False
        for col in df.columns:
            if df[col].dtype == 'object':
                if df[col].astype(str).str.contains('–', na=False).any():
                    has_em_dash_anywhere = True
                    break
        
        headers = list(df.columns)
        
        # Extract sample values for each column (up to max_rows)
        data_dict = {}
        dtype_dict = {}
        for col in headers:
            # Get non-null sample values
            sample_values = df[col].dropna().head(max_rows).tolist()
            data_dict[col] = sample_values
            # Store the pandas dtype for the column
            # If em-dash exists anywhere and column is integer, mark as float to be safe
            dtype = df[col].dtype
            if has_em_dash_anywhere and pd.api.types.is_integer_dtype(dtype):
                # Mark as float64 to indicate it might become float during preprocessing
                dtype_dict[col] = 'float64'
            else:
                dtype_dict[col] = dtype
        
        return headers, data_dict, dtype_dict
    except Exception as e:
        print(f"Error reading {csv_path}: {e}", file=sys.stderr)
        return None, None, None

def generate_table_sql(folder_name, grid_size, columns, column_data, dtype_dict=None):
    """
    Generate CREATE TABLE SQL for a fact table.
    
    Args:
        folder_name: Name of the folder containing the CSV
        grid_size: Grid size ('100m', '1km', or '10km')
        columns: List of column names from CSV header
        column_data: Dictionary mapping column names to sample values
        dtype_dict: Dictionary mapping column names to pandas dtypes (optional)
    """
    table_name = f"fact_zensus_{grid_size}_{sanitize_table_name(folder_name)}"
    
    # Filter out standard columns
    standard_cols = ['GITTER_ID_10km', 'GITTER_ID_1km', 'GITTER_ID_100m',
                     'Gitter_ID_10km', 'Gitter_ID_1km', 'Gitter_ID_100m',  # Handle typo
                     'x_mp_10km', 'x_mp_1km', 'x_mp_100m',
                     'y_mp_10km', 'y_mp_1km', 'y_mp_100m',
                     'werterlaeuternde_Zeichen']
    
    data_columns = [col for col in columns if col not in standard_cols]
    
    # Build column definitions
    col_defs = ['grid_id TEXT PRIMARY KEY']
    col_defs.append('year INTEGER NOT NULL DEFAULT 2022')
    
    for col in data_columns:
        col_name = sanitize_column_name(col)
        # Determine type by inspecting actual data values
        sample_values = column_data.get(col, [])
        # Also check pandas dtype if available
        pandas_dtype = dtype_dict.get(col) if dtype_dict else None
        col_type = determine_column_type_from_data(col, sample_values, pandas_dtype)
        col_defs.append(f'{col_name} {col_type}')
    
    # Add coordinate columns
    if grid_size == '100m':
        col_defs.append('x_mp_100m NUMERIC')
        col_defs.append('y_mp_100m NUMERIC')
    elif grid_size == '1km':
        col_defs.append('x_mp_1km NUMERIC')
        col_defs.append('y_mp_1km NUMERIC')
    elif grid_size == '10km':
        col_defs.append('x_mp_10km NUMERIC')
        col_defs.append('y_mp_10km NUMERIC')
    
    # Build SQL (join column definitions first to avoid backslash in f-string)
    columns_str = ',\n    '.join(col_defs)
    sql = f"""
-- {folder_name} fact table for {grid_size} grid
CREATE TABLE IF NOT EXISTS zensus.{table_name} (
    {columns_str},
    CONSTRAINT chk_year_2022 CHECK (year = 2022),
    CONSTRAINT fk_grid_{grid_size} FOREIGN KEY (grid_id) REFERENCES zensus.ref_grid_{grid_size}(grid_id)
);
"""
    return sql, table_name

def extract_dataset_name_from_filename(filename, grid_size):
    """
    Extract dataset name from CSV filename.
    
    Examples:
    - Zensus2022_Bevoelkerungszahl_10km-Gitter.csv -> Bevoelkerungszahl
    - Zensus2022_Alter_in_5_Altersklassen_1km-Gitter.csv -> Alter_in_5_Altersklassen
    """
    name = filename.replace('Zensus2022_', '')
    # Remove grid size suffix (e.g., _10km-Gitter, _1km-Gitter, _100m-Gitter)
    name = re.sub(r'_[0-9]+km-Gitter\.csv$', '', name)
    name = re.sub(r'_100m-Gitter\.csv$', '', name)
    name = name.strip('_')
    return name

def detect_grid_size_from_path(path):
    """Detect grid size from directory path or filename."""
    path_str = str(path)
    if '100m' in path_str or '100m-Gitter' in path_str:
        return '100m'
    elif '1km' in path_str or '1km-Gitter' in path_str:
        return '1km'
    elif '10km' in path_str or '10km-Gitter' in path_str:
        return '10km'
    return None

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate SQL schema for Zensus fact tables based on CSV files'
    )
    parser.add_argument(
        'csv_dir',
        type=Path,
        help='Directory containing CSV files (e.g., data/zensus_data/10km/)'
    )
    
    args = parser.parse_args()
    
    csv_dir = Path(args.csv_dir)
    if not csv_dir.exists() or not csv_dir.is_dir():
        print(f"Error: Directory not found: {csv_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Detect grid size from directory name
    grid_size = detect_grid_size_from_path(csv_dir)
    if grid_size is None:
        print(f"Error: Could not determine grid size from path: {csv_dir}", file=sys.stderr)
        print("Expected directory name to contain '10km', '1km', or '100m'", file=sys.stderr)
        sys.exit(1)
    
    # Find all CSV files in the directory
    csv_files = sorted(csv_dir.glob('*.csv'))
    if not csv_files:
        print(f"Error: No CSV files found in {csv_dir}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Found {len(csv_files)} CSV file(s) in {csv_dir}", file=sys.stderr)
    
    schemas = {}
    
    # Read each CSV file and inspect data
    print(f"Reading CSV files and inspecting data values for type detection...", file=sys.stderr)
    for csv_file in csv_files:
        dataset_name = extract_dataset_name_from_filename(csv_file.name, grid_size)
        if not dataset_name:
            print(f"  Warning: Could not extract dataset name from {csv_file.name}, skipping", file=sys.stderr)
            continue
        
        headers, column_data, dtype_dict = read_csv_data(csv_file, max_rows=100)
        if headers and column_data:
            schemas[dataset_name] = (headers, column_data, dtype_dict)
            print(f"  Processed: {csv_file.name} -> {dataset_name} ({len(headers)} columns)", file=sys.stderr)
    
    if not schemas:
        print("Error: No valid CSV files processed", file=sys.stderr)
        sys.exit(1)
    
    # Generate SQL for all tables
    print(f"-- Auto-generated fact table definitions for {grid_size} grid", file=sys.stdout)
    print("-- Generated by scripts/generate_schema.py", file=sys.stdout)
    print("-- Data types determined by inspecting actual data values (decimal comma detection)", file=sys.stdout)
    print("", file=sys.stdout)
    
    for dataset_name, schema_data in sorted(schemas.items()):
        if len(schema_data) == 3:
            columns, column_data, dtype_dict = schema_data
        else:
            # Backward compatibility
            columns, column_data = schema_data
            dtype_dict = None
        sql, table_name = generate_table_sql(dataset_name, grid_size, columns, column_data, dtype_dict)
        print(sql, file=sys.stdout)

if __name__ == '__main__':
    main()

