"""
Test script for housing data sync functionality.
Tests connection, geocoding, and sync with a small dataset.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from etl.sync_housing_data import (
    connect_to_external_db,
    get_local_db_engine,
    fetch_properties_from_external_db,
    geocode_properties,
    upsert_properties
)
from etl.geocoding import create_geocoder
from etl.utils import logger


def test_external_db_connection():
    """Test connection to external housing database."""
    print("\n" + "=" * 80)
    print("TEST 1: External Database Connection")
    print("=" * 80)
    
    try:
        conn = connect_to_external_db()
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM all_properties")
        count = cursor.fetchone()[0]
        
        print(f"✓ Connection successful")
        print(f"✓ Total properties in external DB: {count:,}")
        
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


def test_local_db_connection():
    """Test connection to local database."""
    print("\n" + "=" * 80)
    print("TEST 2: Local Database Connection")
    print("=" * 80)
    
    try:
        from sqlalchemy import text
        engine = get_local_db_engine()
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ Connection successful")
            print(f"✓ PostgreSQL version: {version[:50]}...")
        
        engine.dispose()
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


def test_geocoding():
    """Test geocoding functionality with sample addresses."""
    print("\n" + "=" * 80)
    print("TEST 3: Geocoding Functionality")
    print("=" * 80)
    
    try:
        geocoder = create_geocoder(cache_enabled=True, rate_limit=1.0)
        
        # Test addresses
        test_cases = [
            ("Alexanderplatz", None, "10178", "Berlin"),
            ("Marienplatz", "1", "80331", "München"),
            ("Hauptbahnhof", None, "60329", "Frankfurt am Main"),
        ]
        
        success_count = 0
        
        for street, house_number, postal_code, city in test_cases:
            print(f"\nTesting: {street} {house_number or ''}, {postal_code} {city}")
            
            result = geocoder.geocode_components(
                street=street,
                house_number=house_number,
                postal_code=postal_code,
                city=city
            )
            
            if result['success']:
                print(f"  ✓ SUCCESS")
                print(f"    Coordinates: {result['latitude']:.6f}, {result['longitude']:.6f}")
                print(f"    Display: {result.get('display_name', 'N/A')[:60]}")
                print(f"    Cached: {result.get('cached', False)}")
                success_count += 1
            else:
                print(f"  ✗ FAILED: {result.get('error_message', 'Unknown error')}")
        
        print(f"\n✓ Geocoding test: {success_count}/{len(test_cases)} successful")
        
        return success_count == len(test_cases)
    except Exception as e:
        print(f"✗ Geocoding test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fetch_properties():
    """Test fetching properties from external database."""
    print("\n" + "=" * 80)
    print("TEST 4: Fetch Properties")
    print("=" * 80)
    
    try:
        conn = connect_to_external_db()
        
        # Fetch a small sample
        df = fetch_properties_from_external_db(conn, last_sync=None, limit=5)
        
        print(f"✓ Fetched {len(df)} properties")
        print(f"\nSample data:")
        print(df[['internal_id', 'strasse_normalized', 'hausnummer', 'plz', 'ort']].head())
        
        conn.close()
        return len(df) == 5
    except Exception as e:
        print(f"✗ Fetch test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_sync_small():
    """Test full sync with a very small dataset."""
    print("\n" + "=" * 80)
    print("TEST 5: Full Sync (Small Dataset)")
    print("=" * 80)
    print("This will sync 10 properties with geocoding (may take ~15 seconds)")
    
    try:
        # Connect to databases
        external_conn = connect_to_external_db()
        local_engine = get_local_db_engine()
        
        # Fetch small sample
        df = fetch_properties_from_external_db(external_conn, last_sync=None, limit=10)
        print(f"✓ Fetched {len(df)} properties")
        
        # Initialize geocoder
        geocoder = create_geocoder(cache_enabled=True, rate_limit=1.0)
        print(f"✓ Geocoder initialized")
        
        # Geocode
        df = geocode_properties(df, geocoder, max_records=10)
        success_count = (df['geocoding_status'] == 'success').sum()
        print(f"✓ Geocoded: {success_count}/{len(df)} successful")
        
        # Upsert
        upsert_properties(df, local_engine, chunk_size=100)
        print(f"✓ Upserted {len(df)} properties")
        
        # Verify in database
        with local_engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT COUNT(*) FROM housing.properties"))
            total_count = result.scalar()
            print(f"✓ Total properties in local DB: {total_count:,}")
        
        external_conn.close()
        local_engine.dispose()
        
        return True
    except Exception as e:
        print(f"✗ Full sync test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("HOUSING DATA SYNC TEST SUITE")
    print("=" * 80)
    
    tests = [
        ("External DB Connection", test_external_db_connection),
        ("Local DB Connection", test_local_db_connection),
        ("Geocoding", test_geocoding),
        ("Fetch Properties", test_fetch_properties),
        ("Full Sync (Small)", test_full_sync_small),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print("\n" + "=" * 80)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 80)
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

