"""
Inspect the external housing database to understand the table structure.
This script connects to the remote database and analyzes the all_properties table.
"""

import sys
from pathlib import Path
import psycopg2
from psycopg2 import sql
import pandas as pd
from typing import Dict, List, Tuple

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from etl.utils import logger


def connect_to_external_db():
    """
    Connect to the external housing database.
    
    Returns:
        Connection object
    """
    try:
        conn = psycopg2.connect(
            host="157.180.47.26",
            port="5432",
            database="housing_scraper_db",
            user="scraper_user",
            password="de2cdd2a1e225c850152cb96e19ae59728810bfc",
            connect_timeout=10
        )
        logger.info("✓ Successfully connected to external database")
        return conn
    except Exception as e:
        logger.error(f"✗ Failed to connect to external database: {e}")
        raise


def get_table_columns(conn, table_name: str = 'all_properties') -> List[Dict]:
    """
    Get detailed column information for a table.
    
    Args:
        conn: Database connection
        table_name: Name of the table to inspect
        
    Returns:
        List of dicts with column information
    """
    query = """
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """
    
    with conn.cursor() as cur:
        cur.execute(query, (table_name,))
        columns = cur.fetchall()
        
        return [
            {
                'name': col[0],
                'type': col[1],
                'max_length': col[2],
                'nullable': col[3],
                'default': col[4]
            }
            for col in columns
        ]


def get_sample_data(conn, table_name: str = 'all_properties', limit: int = 5) -> pd.DataFrame:
    """
    Get sample data from the table.
    
    Args:
        conn: Database connection
        table_name: Name of the table
        limit: Number of rows to fetch
        
    Returns:
        DataFrame with sample data
    """
    query = f"SELECT * FROM {table_name} LIMIT {limit}"
    return pd.read_sql_query(query, conn)


def get_table_stats(conn, table_name: str = 'all_properties') -> Dict:
    """
    Get statistics about the table.
    
    Args:
        conn: Database connection
        table_name: Name of the table
        
    Returns:
        Dict with table statistics
    """
    stats = {}
    
    # Total row count
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        stats['total_rows'] = cur.fetchone()[0]
    
    # Check for timestamp columns
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s 
            AND data_type IN ('timestamp', 'timestamp without time zone', 'timestamp with time zone', 'date')
        """, (table_name,))
        
        db_timestamp_cols = [row[0] for row in cur.fetchall()]
        stats['timestamp_columns'] = db_timestamp_cols
    
    # Check for ID columns
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s 
            AND (column_name LIKE '%%id%%' OR column_name = 'id')
            ORDER BY ordinal_position
        """, (table_name,))
        
        stats['id_columns'] = [row[0] for row in cur.fetchall()]
    
    # Check for primary key
    stats['primary_key'] = None
    try:
        with conn.cursor() as cur:
            # Try to get primary key using constraint name
            cur.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = %s
                AND tc.constraint_type = 'PRIMARY KEY'
                ORDER BY kcu.ordinal_position
            """, (table_name,))
            
            pk_cols = cur.fetchall()
            if pk_cols:
                stats['primary_key'] = [row[0] for row in pk_cols]
    except Exception as e:
        logger.warning(f"Could not determine primary key: {e}")
        stats['primary_key'] = None
    
    return stats


def identify_address_columns(columns: List[Dict]) -> Dict[str, str]:
    """
    Identify which columns likely contain address information.
    
    Args:
        columns: List of column information dicts
        
    Returns:
        Dict mapping address component types to column names
    """
    address_mapping = {
        'street': None,
        'house_number': None,
        'postal_code': None,
        'city': None,
        'state': None,
        'country': None,
        'full_address': None,
        'latitude': None,
        'longitude': None
    }
    
    col_names = [col['name'].lower() for col in columns]
    
    # Common patterns for address components
    patterns = {
        'street': ['street', 'strasse', 'str', 'road', 'adresse'],
        'house_number': ['house_number', 'hausnummer', 'number', 'nr'],
        'postal_code': ['postal', 'postcode', 'plz', 'zip', 'zipcode'],
        'city': ['city', 'stadt', 'ort', 'place'],
        'state': ['state', 'bundesland', 'land', 'region'],
        'country': ['country', 'land'],
        'full_address': ['address', 'adresse', 'location'],
        'latitude': ['lat', 'latitude', 'breitengrad'],
        'longitude': ['lon', 'lng', 'longitude', 'laengengrad']
    }
    
    for addr_type, keywords in patterns.items():
        for keyword in keywords:
            matching_cols = [col for col in col_names if keyword in col]
            if matching_cols:
                # Get the original column name (with proper casing)
                original_name = columns[col_names.index(matching_cols[0])]['name']
                address_mapping[addr_type] = original_name
                break
    
    return address_mapping


def generate_create_table_sql(table_name: str, columns: List[Dict], primary_key: List[str]) -> str:
    """
    Generate CREATE TABLE SQL statement.
    
    Args:
        table_name: Name for the new table
        columns: List of column information
        primary_key: List of primary key column names
        
    Returns:
        SQL CREATE TABLE statement
    """
    # PostgreSQL type mapping
    type_mapping = {
        'character varying': 'TEXT',
        'varchar': 'TEXT',
        'text': 'TEXT',
        'integer': 'INTEGER',
        'bigint': 'BIGINT',
        'numeric': 'NUMERIC',
        'decimal': 'NUMERIC',
        'timestamp without time zone': 'TIMESTAMP',
        'timestamp with time zone': 'TIMESTAMPTZ',
        'date': 'DATE',
        'boolean': 'BOOLEAN',
        'double precision': 'DOUBLE PRECISION',
        'real': 'REAL'
    }
    
    sql_parts = [f"CREATE TABLE IF NOT EXISTS housing.{table_name} ("]
    
    col_definitions = []
    for col in columns:
        pg_type = type_mapping.get(col['type'], col['type'].upper())
        nullable = "" if col['nullable'] == 'YES' else " NOT NULL"
        col_def = f"    {col['name']} {pg_type}{nullable}"
        col_definitions.append(col_def)
    
    # Add metadata columns
    col_definitions.append("    -- Geocoding columns")
    col_definitions.append("    latitude DOUBLE PRECISION")
    col_definitions.append("    longitude DOUBLE PRECISION")
    col_definitions.append("    geom GEOMETRY(POINT, 4326)")
    col_definitions.append("    geocoding_status TEXT")
    col_definitions.append("    geocoding_quality NUMERIC")
    col_definitions.append("    geocoded_address TEXT")
    col_definitions.append("    -- Metadata columns")
    col_definitions.append("    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    col_definitions.append("    last_geocoded_at TIMESTAMP")
    
    sql_parts.append(",\n".join(col_definitions))
    
    # Add primary key constraint
    if primary_key:
        pk_str = ", ".join(primary_key)
        sql_parts.append(f",\n    PRIMARY KEY ({pk_str})")
    
    sql_parts.append("\n);")
    
    # Add indexes
    indexes = []
    indexes.append(f"\nCREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON housing.{table_name} USING GIST (geom);")
    indexes.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geocoding_status ON housing.{table_name} (geocoding_status);")
    if primary_key and len(primary_key) == 1:
        indexes.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{primary_key[0]} ON housing.{table_name} ({primary_key[0]});")
    
    return "\n".join(sql_parts) + "\n" + "\n".join(indexes)


def inspect_database():
    """Main inspection function."""
    
    print("=" * 80)
    print("EXTERNAL DATABASE INSPECTION")
    print("=" * 80)
    print()
    
    try:
        # Connect to database
        conn = connect_to_external_db()
        
        # Get column information
        print("\n📋 ANALYZING TABLE STRUCTURE...")
        columns = get_table_columns(conn, 'all_properties')
        
        print(f"\n✓ Found {len(columns)} columns in 'all_properties' table:")
        print()
        print(f"{'Column Name':<30} {'Type':<25} {'Nullable':<10} {'Max Length':<12}")
        print("-" * 80)
        for col in columns:
            max_len = str(col['max_length']) if col['max_length'] else 'N/A'
            print(f"{col['name']:<30} {col['type']:<25} {col['nullable']:<10} {max_len:<12}")
        
        # Get table statistics
        print("\n📊 TABLE STATISTICS...")
        stats = get_table_stats(conn, 'all_properties')
        print(f"\n✓ Total rows: {stats['total_rows']:,}")
        print(f"✓ Primary key: {stats['primary_key']}")
        print(f"✓ ID columns: {stats['id_columns']}")
        print(f"✓ Timestamp columns: {stats['timestamp_columns']}")
        
        # Identify address columns
        print("\n🏠 ADDRESS COLUMN MAPPING...")
        address_mapping = identify_address_columns(columns)
        print()
        for addr_type, col_name in address_mapping.items():
            status = "✓" if col_name else "✗"
            value = col_name if col_name else "NOT FOUND"
            print(f"{status} {addr_type:<15}: {value}")
        
        # Get sample data
        print("\n📝 SAMPLE DATA (first 5 rows)...")
        sample_df = get_sample_data(conn, 'all_properties', limit=5)
        print()
        print(sample_df.to_string())
        
        # Analyze address columns more closely
        print("\n🔍 ADDRESS COLUMN ANALYSIS...")
        address_cols = [col for col in address_mapping.values() if col]
        if address_cols:
            for col in address_cols:
                print(f"\n  Column: {col}")
                # Get some sample values
                query = f"SELECT DISTINCT {col} FROM all_properties WHERE {col} IS NOT NULL LIMIT 5"
                with conn.cursor() as cur:
                    cur.execute(query)
                    values = cur.fetchall()
                    for val in values:
                        print(f"    - {val[0]}")
        
        # Generate CREATE TABLE SQL
        print("\n" + "=" * 80)
        print("GENERATED SQL SCHEMA")
        print("=" * 80)
        print()
        
        create_sql = generate_create_table_sql(
            'properties',
            columns,
            stats['primary_key'] or ['id']
        )
        print(create_sql)
        
        # Save to file
        output_file = project_root / 'docker' / 'init' / '07_housing_data_schema.sql'
        
        full_sql = f"""-- Housing data schema
-- Auto-generated from external database inspection
-- Source: housing_scraper_db.all_properties

-- Create housing schema
CREATE SCHEMA IF NOT EXISTS housing;

-- Properties table
{create_sql}

-- Comments
COMMENT ON SCHEMA housing IS 'Housing property data synced from external scraper database';
COMMENT ON TABLE housing.properties IS 'Property listings with geocoded coordinates';
"""
        
        with open(output_file, 'w') as f:
            f.write(full_sql)
        
        print(f"\n✓ Schema saved to: {output_file}")
        
        # Summary and recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print()
        
        if stats['primary_key']:
            print(f"✓ Use '{stats['primary_key'][0]}' as primary key for upsert logic")
        else:
            print("⚠ No primary key found - will need to define one for upsert logic")
        
        if stats['timestamp_columns']:
            print(f"✓ Use '{stats['timestamp_columns'][0]}' for incremental sync")
        else:
            print("⚠ No timestamp columns found - will do full table sync each time")
        
        if any(address_mapping.values()):
            print("✓ Address columns identified - ready for geocoding")
        else:
            print("⚠ No clear address columns found - may need manual mapping")
        
        # Check if coordinates already exist
        if address_mapping['latitude'] and address_mapping['longitude']:
            print("⚠ Coordinates already exist in source data!")
            print("  Consider using existing coordinates instead of geocoding")
        
        conn.close()
        logger.info("✓ Inspection complete")
        
    except Exception as e:
        logger.error(f"✗ Inspection failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    inspect_database()

