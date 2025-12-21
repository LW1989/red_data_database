"""
Utility functions for ETL scripts.
Provides database connection, logging, and data preprocessing functions.
"""

import os
import logging
from typing import Optional, Any
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('etl.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def get_db_engine() -> Engine:
    """
    Create and return a SQLAlchemy database engine.
    
    Reads connection parameters from environment variables:
    - DB_HOST (default: localhost)
    - DB_PORT (default: 5432)
    - DB_NAME (default: zensus_db)
    - DB_USER (default: zensus_user)
    - DB_PASSWORD (required)
    
    Returns:
        SQLAlchemy Engine instance
    """
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'zensus_db')
    db_user = os.getenv('DB_USER', 'zensus_user')
    db_password = os.getenv('DB_PASSWORD', 'changeme')
    
    connection_string = (
        f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )
    
    engine = create_engine(
        connection_string,
        pool_pre_ping=True,  # Verify connections before using
        echo=False  # Set to True for SQL query logging
    )
    
    logger.info(f"Database engine created for {db_user}@{db_host}:{db_port}/{db_name}")
    return engine


def normalize_decimal(value: Any) -> Optional[float]:
    """
    Normalize a German-formatted decimal string to a float.
    
    Converts:
    - "129,1" → 129.1
    - "–" (em dash) → None
    - Empty strings → None
    - Already numeric values → float
    
    Args:
        value: Input value (string, number, or None)
        
    Returns:
        float or None
    """
    if value is None:
        return None
    
    # Convert to string for processing
    if isinstance(value, (int, float)):
        return float(value)
    
    str_value = str(value).strip()
    
    # Handle missing values (em dash U+2013, regular dash, empty string)
    if str_value in ['–', '-', '', 'nan', 'None', 'NULL']:
        return None
    
    # Replace comma with dot for decimal separator
    if ',' in str_value:
        str_value = str_value.replace(',', '.')
    
    try:
        return float(str_value)
    except (ValueError, TypeError):
        logger.warning(f"Could not convert '{value}' to float, returning None")
        return None


def normalize_integer(value: Any) -> Optional[int]:
    """
    Normalize a value to an integer, handling German format and missing values.
    
    This function only converts values that are actually integers (no decimal part).
    If a value has a decimal part (e.g., "129,1" or "129.1"), it returns None
    as it's not an integer.
    
    Args:
        value: Input value
        
    Returns:
        int or None (None if value has decimal part or cannot be converted)
    """
    if value is None:
        return None
    
    str_value = str(value).strip()
    
    # Handle missing values
    if str_value in ['–', '-', '', 'nan', 'None', 'NULL']:
        return None
    
    # Check if value has a decimal part (comma or dot with digits after)
    # German format: "129,1" or "129,10" - these are NOT integers
    # English format: "129.1" or "129.10" - these are NOT integers
    # Integer format: "129" or "129," or "129." (trailing comma/dot without digits) - these ARE integers
    
    # Check for comma decimal separator (German format)
    if ',' in str_value:
        parts = str_value.split(',')
        if len(parts) == 2 and parts[1].strip():  # Has digits after comma
            # This is a decimal number, not an integer
            logger.debug(f"Value '{value}' has decimal part (comma), not converting to integer")
            return None
        # Trailing comma without digits - treat as integer
        str_value = parts[0]
    
    # Note: All numeric values in this dataset use comma as decimal separator
    # If a value has a dot, it's likely already in English format or an integer
    # We don't need to check for dots since the dataset only uses commas for decimals
    
    try:
        return int(str_value)
    except (ValueError, TypeError):
        logger.warning(f"Could not convert '{value}' to int, returning None")
        return None


def preprocess_zensus_dataframe(df: pd.DataFrame, 
                                integer_columns: Optional[list] = None,
                                numeric_columns: Optional[list] = None) -> pd.DataFrame:
    """
    Preprocess a Zensus DataFrame to handle German number format and missing values.
    
    Converts:
    - Comma decimal separators to dots for numeric columns
    - Em dash missing values to None/NULL
    - Empty strings to None
    
    Args:
        df: Input DataFrame
        integer_columns: List of column names that should be treated as integers
        numeric_columns: List of column names that should be treated as numeric (floats)
                        If None, auto-detect numeric columns
        
    Returns:
        Preprocessed DataFrame
    """
    df = df.copy()
    
    # Statistics for logging
    stats = {
        'decimal_conversions': 0,
        'nulls_created': 0,
        'integer_conversions': 0
    }
    
    # If numeric_columns is not provided, assume all non-integer, non-coordinate columns are numeric
    # This should not happen in practice since load_zensus.py always provides both lists
    if numeric_columns is None:
        exclude_cols = ['GITTER_ID_1km', 'GITTER_ID_10km', 'GITTER_ID_100m', 
                       'x_mp_1km', 'x_mp_10km', 'x_mp_100m',
                       'y_mp_1km', 'y_mp_10km', 'y_mp_100m',
                       'werterlaeuternde_Zeichen', 'grid_id', 'year']
        numeric_columns = [col for col in df.columns 
                          if col not in exclude_cols and col not in (integer_columns or [])]
        logger.warning("numeric_columns not provided, auto-detecting from remaining columns")
    
    # Process integer columns
    if integer_columns:
        for col in integer_columns:
            if col in df.columns:
                original_nulls = df[col].isna().sum()
                df[col] = df[col].apply(normalize_integer)
                stats['nulls_created'] += df[col].isna().sum() - original_nulls
                stats['integer_conversions'] += df[col].notna().sum()
    
    # Process numeric (float) columns
    for col in numeric_columns:
        if col in df.columns:
            original_nulls = df[col].isna().sum()
            # Count comma-separated values before conversion
            if df[col].dtype == 'object':
                stats['decimal_conversions'] += df[col].astype(str).str.contains(',').sum()
            df[col] = df[col].apply(normalize_decimal)
            stats['nulls_created'] += df[col].isna().sum() - original_nulls
    
    # Handle coordinate columns (x_mp, y_mp) - these should be numeric
    coord_cols = [col for col in df.columns if col.startswith('x_mp_') or col.startswith('y_mp_')]
    for col in coord_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    logger.info(f"Preprocessing complete: {stats['decimal_conversions']} decimal conversions, "
                f"{stats['integer_conversions']} integer conversions, "
                f"{stats['nulls_created']} NULLs created")
    
    return df


def validate_grid_id_exists(engine: Engine, grid_id: str, grid_size: str = '1km') -> bool:
    """
    Validate that a grid_id exists in the reference grid table.
    
    Args:
        engine: Database engine
        grid_id: Grid ID to validate
        grid_size: Grid size ('100m', '1km', or '10km')
        
    Returns:
        True if grid_id exists, False otherwise
    """
    table_name = f"ref_grid_{grid_size}"
    query = f"SELECT 1 FROM zensus.{table_name} WHERE grid_id = %s LIMIT 1"
    
    with engine.connect() as conn:
        result = conn.execute(query, (grid_id,))
        return result.fetchone() is not None

