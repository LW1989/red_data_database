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

def determine_column_type_from_data(col_name, sample_values):
    """
    Determine PostgreSQL column type by inspecting actual data values.
    
    Checks if column contains decimal commas (German format: "129,1") to distinguish
    between INTEGER and NUMERIC types. This matches the logic used in the ETL pipeline.
    
    Args:
        col_name: Column name (for logging/debugging)
        sample_values: List or Series of sample values from the column
        
    Returns:
        'INTEGER' or 'NUMERIC'
    """
    if not sample_values or len(sample_values) == 0:
        # No data to inspect, default to NUMERIC (safer than INTEGER)
        return 'NUMERIC'
    
    # Convert to string and check for decimal commas
    # Pattern: comma followed by one or more digits (e.g., "129,1" or "129,12")
    # This matches the logic in etl/load_zensus.py
    sample_str = pd.Series(sample_values).dropna().astype(str)
    
    if len(sample_str) == 0:
        # All values are missing, default to NUMERIC
        return 'NUMERIC'
    
    # Check if any value contains a comma followed by digits (decimal comma)
    has_decimal_comma = sample_str.str.contains(r',\d+', regex=True, na=False).any()
    
    if has_decimal_comma:
        return 'NUMERIC'
    else:
        return 'INTEGER'

def read_csv_data(csv_path, max_rows=100):
    """
    Read CSV file and return headers and sample data.
    
    Args:
        csv_path: Path to CSV file
        max_rows: Maximum number of data rows to read for type detection
        
    Returns:
        Tuple of (headers, data_dict) where data_dict maps column names to sample values
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
        
        headers = list(df.columns)
        
        # Extract sample values for each column (up to max_rows)
        data_dict = {}
        for col in headers:
            # Get non-null sample values
            sample_values = df[col].dropna().head(max_rows).tolist()
            data_dict[col] = sample_values
        
        return headers, data_dict
    except Exception as e:
        print(f"Error reading {csv_path}: {e}", file=sys.stderr)
        return None, None

def generate_table_sql(folder_name, grid_size, columns, column_data):
    """
    Generate CREATE TABLE SQL for a fact table.
    
    Args:
        folder_name: Name of the folder containing the CSV
        grid_size: Grid size ('100m', '1km', or '10km')
        columns: List of column names from CSV header
        column_data: Dictionary mapping column names to sample values
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
        col_type = determine_column_type_from_data(col, sample_values)
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
    
    # Build SQL
    sql = f"""
-- {folder_name} fact table for {grid_size} grid
CREATE TABLE IF NOT EXISTS zensus.{table_name} (
    {',\n    '.join(col_defs)},
    CONSTRAINT chk_year_2022 CHECK (year = 2022),
    CONSTRAINT fk_grid_{grid_size} FOREIGN KEY (grid_id) REFERENCES zensus.ref_grid_{grid_size}(grid_id)
);
"""
    return sql, table_name

def main():
    base_dir = Path('data/zensus_data')
    schemas = {}
    
    # Read all 10km CSV files and inspect data
    print("Reading CSV files and inspecting data values for type detection...", file=sys.stderr)
    for subdir in sorted(base_dir.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith('.'):
            csv_files = list(subdir.glob('*10km-Gitter.csv'))
            if csv_files:
                csv_file = csv_files[0]
                headers, column_data = read_csv_data(csv_file, max_rows=100)
                if headers and column_data:
                    schemas[subdir.name] = (headers, column_data)
                    print(f"  Processed: {subdir.name} ({len(headers)} columns)", file=sys.stderr)
    
    # Generate SQL for all tables
    print("-- Auto-generated fact table definitions for all Zensus datasets", file=sys.stdout)
    print("-- Generated by scripts/generate_schema.py", file=sys.stdout)
    print("-- Data types determined by inspecting actual data values (decimal comma detection)", file=sys.stdout)
    print("", file=sys.stdout)
    
    for folder_name, (columns, column_data) in sorted(schemas.items()):
        # Generate for 100m, 1km, and 10km
        # Note: We use the 10km data for type detection, but generate schemas for all grid sizes
        # This assumes column types are consistent across grid sizes (which they should be)
        for grid_size in ['100m', '1km', '10km']:
            sql, table_name = generate_table_sql(folder_name, grid_size, columns, column_data)
            print(sql, file=sys.stdout)

if __name__ == '__main__':
    main()

