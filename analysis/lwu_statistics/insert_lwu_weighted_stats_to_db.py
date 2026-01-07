#!/usr/bin/env python3
"""
Quick script to insert LWU weighted statistics into the database.
Run this after reviewing and approving the CSV file.

Usage:
    python etl/insert_lwu_weighted_stats_to_db.py lwu_weighted_stats_2026-01-07.csv
"""

import sys
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_db_connection():
    """Create database connection."""
    DB_HOST = "dokploy.red-data.eu"
    DB_PORT = "54321"
    DB_NAME = "red-data-db"
    DB_USER = "zensus_user"
    DB_PASSWORD = "kiskIv-kehcyh-hishu4"
    
    connection_string = (
        f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=disable"
    )
    
    engine = create_engine(connection_string)
    logger.info(f"✅ Connected to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    return engine


def create_table(engine):
    """Create the table if it doesn't exist."""
    logger.info("Creating table analytics.fact_lwu_weighted_stats...")
    
    with open('docker/init/06_lwu_weighted_stats_schema.sql', 'r') as f:
        schema_sql = f.read()
    
    with engine.connect() as conn:
        conn.execute(text(schema_sql))
        conn.commit()
    
    logger.info("✅ Table created successfully")


def insert_data(engine, csv_file):
    """Insert data from CSV into the database."""
    logger.info(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    logger.info(f"✅ Loaded {len(df):,} rows from CSV")
    
    logger.info("Inserting data into database...")
    df.to_sql(
        'fact_lwu_weighted_stats',
        engine,
        schema='analytics',
        if_exists='append',
        index=False,
        method='multi',
        chunksize=1000
    )
    
    logger.info(f"✅ Inserted {len(df):,} rows into analytics.fact_lwu_weighted_stats")


def verify_insertion(engine):
    """Verify the data was inserted correctly."""
    logger.info("Verifying insertion...")
    
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) as count FROM analytics.fact_lwu_weighted_stats"
        ))
        count = result.fetchone()[0]
        logger.info(f"✅ Table contains {count:,} rows")
        
        # Check coverage
        result = conn.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE weighted_avg_rent_per_sqm IS NOT NULL) as rent_count,
                COUNT(*) FILTER (WHERE heating_total_buildings > 0) as heating_count,
                COUNT(*) FILTER (WHERE energy_total_buildings > 0) as energy_count,
                COUNT(*) FILTER (WHERE baujahr_total_buildings > 0) as baujahr_count,
                COUNT(*) as total
            FROM analytics.fact_lwu_weighted_stats
        """))
        row = result.fetchone()
        
        logger.info("\nData coverage:")
        logger.info(f"  Rent:         {row[0]:,} / {row[4]:,} ({row[0]/row[4]*100:.1f}%)")
        logger.info(f"  Heating:      {row[1]:,} / {row[4]:,} ({row[1]/row[4]*100:.1f}%)")
        logger.info(f"  Energy:       {row[2]:,} / {row[4]:,} ({row[2]/row[4]*100:.1f}%)")
        logger.info(f"  Construction: {row[3]:,} / {row[4]:,} ({row[3]/row[4]*100:.1f}%)")


def main():
    """Main execution function."""
    if len(sys.argv) < 2:
        print("Usage: python insert_lwu_weighted_stats_to_db.py <csv_file>")
        print("Example: python insert_lwu_weighted_stats_to_db.py lwu_weighted_stats_2026-01-07.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    print("="*80)
    print("LWU WEIGHTED STATISTICS - DATABASE INSERTION")
    print("="*80)
    print(f"\n📁 CSV File: {csv_file}")
    print("\n⚠️  WARNING: This will DROP and recreate the table!")
    print("   All existing data in analytics.fact_lwu_weighted_stats will be lost.")
    
    response = input("\n❓ Do you want to proceed? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Aborted")
        sys.exit(0)
    
    print("\n" + "="*80)
    
    # Connect to database
    engine = create_db_connection()
    
    # Create table
    create_table(engine)
    
    # Insert data
    insert_data(engine, csv_file)
    
    # Verify
    verify_insertion(engine)
    
    print("\n" + "="*80)
    print("✅ DATABASE INSERTION COMPLETE!")
    print("="*80)
    print(f"\nTable: zensus.fact_lwu_weighted_stats")
    print(f"You can now query this table in your analyses.\n")


if __name__ == "__main__":
    main()

