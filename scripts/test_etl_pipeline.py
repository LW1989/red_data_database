#!/usr/bin/env python3
"""
Test script to validate the ETL pipeline implementation.
Tests against actual data files in the repository.
"""

import sys
from pathlib import Path
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Add etl to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

def test_csv_reading():
    """Test 1: Verify CSV files can be read correctly."""
    print("\n=== Test 1: CSV Reading ===")
    
    test_files = [
        'data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_1km-Gitter.csv',
        'data/zensus_data/Durchschnittsalter_in_Gitterzellen/Zensus2022_Durchschnittsalter_1km-Gitter.csv',
        'data/zensus_data/Auslaenderanteil_ab_18_Jahren/Zensus2022_Auslaenderanteil_ab18_1km-Gitter.csv',
    ]
    
    issues = []
    for csv_file in test_files:
        try:
            df = pd.read_csv(csv_file, sep=';', encoding='utf-8', low_memory=False, nrows=100)
            print(f"✓ {Path(csv_file).name}: {len(df)} rows, {len(df.columns)} columns")
            
            # Check for em-dash
            has_emdash = df.astype(str).apply(lambda x: x.str.contains('–', na=False)).any().any()
            if has_emdash:
                print(f"  → Contains em-dash: ✓")
            
            # Check for decimal commas
            has_comma = df.astype(str).apply(lambda x: x.str.contains(r',\d+', regex=True, na=False)).any().any()
            if has_comma:
                print(f"  → Contains decimal commas: ✓")
                
        except Exception as e:
            issues.append(f"{csv_file}: {e}")
            print(f"✗ {Path(csv_file).name}: {e}")
    
    return len(issues) == 0, issues


def test_gpkg_structure():
    """Test 2: Verify GPKG files structure and column names."""
    print("\n=== Test 2: GPKG File Structure ===")
    
    gpkg_files = [
        ('data/geo_data/DE_Grid_ETRS89-LAEA_100m.gpkg', '100m'),
        ('data/geo_data/DE_Grid_ETRS89-LAEA_1km.gpkg', '1km'),
        ('data/geo_data/DE_Grid_ETRS89-LAEA_10km.gpkg', '10km'),
    ]
    
    issues = []
    for gpkg_file, size in gpkg_files:
        try:
            gdf = gpd.read_file(gpkg_file, rows=10)  # Read only first 10 rows for testing
            print(f"✓ {Path(gpkg_file).name}:")
            print(f"  Columns: {list(gdf.columns)}")
            print(f"  CRS: {gdf.crs}")
            print(f"  Geometry type: {gdf.geometry.type.iloc[0] if len(gdf) > 0 else 'N/A'}")
            
            # Check for grid_id column
            possible_cols = ['id', 'grid_id', 'GITTER_ID', 'CELLCODE', 'gitter_id', 'GITTERID', 
                           'CELLCODE_10KM', 'CELLCODE_1KM', 'CELLCODE_100M']
            found_col = None
            for col in possible_cols:
                if col in gdf.columns:
                    found_col = col
                    break
            
            if found_col:
                print(f"  → Grid ID column found: {found_col} ✓")
                print(f"  → Sample grid_id: {gdf[found_col].iloc[0] if len(gdf) > 0 else 'N/A'}")
            else:
                # Check for any column that might be the ID
                for col in gdf.columns:
                    if col.lower() in ['id', 'code', 'cellcode', 'gitter_id', 'grid_id']:
                        found_col = col
                        print(f"  → Potential grid ID column: {col} (needs verification)")
                        break
                
                if not found_col:
                    issues.append(f"{gpkg_file}: No grid_id column found")
                    print(f"  ✗ No grid_id column found!")
                    
        except Exception as e:
            issues.append(f"{gpkg_file}: {e}")
            print(f"✗ {Path(gpkg_file).name}: {e}")
    
    return len(issues) == 0, issues


def test_data_preprocessing():
    """Test 3: Verify data preprocessing functions."""
    print("\n=== Test 3: Data Preprocessing ===")
    
    from etl.utils import normalize_decimal, normalize_integer
    
    test_cases = [
        # (input, expected_type, expected_output)
        ("129,1", "decimal", 129.1),
        ("50,00", "decimal", 50.0),
        ("129", "integer", 129),
        ("–", "missing", None),
        ("", "missing", None),
    ]
    
    issues = []
    for input_val, expected_type, expected_output in test_cases:
        if expected_type == "decimal":
            result = normalize_decimal(input_val)
            if result != expected_output:
                issues.append(f"normalize_decimal('{input_val}') = {result}, expected {expected_output}")
                print(f"✗ normalize_decimal('{input_val}') = {result}, expected {expected_output}")
            else:
                print(f"✓ normalize_decimal('{input_val}') = {result}")
        
        elif expected_type == "integer":
            result = normalize_integer(input_val)
            if result != expected_output:
                issues.append(f"normalize_integer('{input_val}') = {result}, expected {expected_output}")
                print(f"✗ normalize_integer('{input_val}') = {result}, expected {expected_output}")
            else:
                print(f"✓ normalize_integer('{input_val}') = {result}")
        
        elif expected_type == "missing":
            dec_result = normalize_decimal(input_val)
            int_result = normalize_integer(input_val)
            if dec_result is not None or int_result is not None:
                issues.append(f"Missing value '{input_val}' not converted to None")
                print(f"✗ Missing value '{input_val}' not converted to None")
            else:
                print(f"✓ Missing value '{input_val}' → None")
    
    return len(issues) == 0, issues


def test_column_detection():
    """Test 4: Verify integer vs numeric column detection."""
    print("\n=== Test 4: Column Type Detection ===")
    
    test_files = [
        ('data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_1km-Gitter.csv', 
         {'Einwohner': 'integer'}),
        ('data/zensus_data/Durchschnittsalter_in_Gitterzellen/Zensus2022_Durchschnittsalter_1km-Gitter.csv',
         {'Durchschnittsalter': 'numeric'}),
        ('data/zensus_data/Auslaenderanteil_ab_18_Jahren/Zensus2022_Auslaenderanteil_ab18_1km-Gitter.csv',
         {'AnteilAuslaenderAb18': 'numeric'}),
    ]
    
    issues = []
    for csv_file, expected_types in test_files:
        try:
            df = pd.read_csv(csv_file, sep=';', encoding='utf-8', nrows=100)
            
            for col, expected_type in expected_types.items():
                if col not in df.columns:
                    issues.append(f"{csv_file}: Column '{col}' not found")
                    continue
                
                sample_values = df[col].dropna().astype(str).head(100)
                has_decimal_comma = sample_values.str.contains(r',\d+', regex=True, na=False).any()
                
                detected_type = 'numeric' if has_decimal_comma else 'integer'
                
                if detected_type != expected_type:
                    issues.append(f"{csv_file}: Column '{col}' detected as {detected_type}, expected {expected_type}")
                    print(f"✗ {Path(csv_file).name}: '{col}' detected as {detected_type}, expected {expected_type}")
                else:
                    print(f"✓ {Path(csv_file).name}: '{col}' correctly detected as {detected_type}")
                    
        except Exception as e:
            issues.append(f"{csv_file}: {e}")
            print(f"✗ {Path(csv_file).name}: {e}")
    
    return len(issues) == 0, issues


def test_schema_generation():
    """Test 5: Verify schema generation matches actual CSV columns."""
    print("\n=== Test 5: Schema Generation ===")
    
    # Test a few CSV files
    test_files = [
        'data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_10km-Gitter.csv',
        'data/zensus_data/Alter_in_5_Altersklassen/Zensus2022_Alter_in_5_Altersklassen_10km-Gitter.csv',
    ]
    
    issues = []
    for csv_file in test_files:
        try:
            df = pd.read_csv(csv_file, sep=';', encoding='utf-8', nrows=1)
            csv_columns = set(df.columns)
            
            # Exclude standard columns
            standard_cols = {'GITTER_ID_10km', 'x_mp_10km', 'y_mp_10km', 'werterlaeuternde_Zeichen'}
            data_columns = csv_columns - standard_cols
            
            print(f"✓ {Path(csv_file).name}:")
            print(f"  CSV columns: {sorted(data_columns)}")
            print(f"  Total data columns: {len(data_columns)}")
            
            # Note: Full schema validation would require checking generated SQL
            # This is a basic check that columns can be read
            
        except Exception as e:
            issues.append(f"{csv_file}: {e}")
            print(f"✗ {Path(csv_file).name}: {e}")
    
    return len(issues) == 0, issues


def test_table_mapping():
    """Test 6: Verify table name mapping from CSV paths."""
    print("\n=== Test 6: Table Name Mapping ===")
    
    from etl.load_zensus import detect_table_mapping
    
    test_cases = [
        ('data/zensus_data/Zensus2022_Bevoelkerungszahl/Zensus2022_Bevoelkerungszahl_1km-Gitter.csv', 
         '1km', 'Zensus2022_Bevoelkerungszahl'),
        ('data/zensus_data/Durchschnittsalter_in_Gitterzellen/Zensus2022_Durchschnittsalter_10km-Gitter.csv',
         '10km', 'Durchschnittsalter_in_Gitterzellen'),
    ]
    
    issues = []
    for csv_path, expected_size, expected_folder in test_cases:
        table_name, grid_size, folder_name = detect_table_mapping(Path(csv_path))
        
        if table_name is None:
            issues.append(f"{csv_path}: Could not detect table mapping")
            print(f"✗ {Path(csv_path).name}: Could not detect table mapping")
            continue
        
        if grid_size != expected_size:
            issues.append(f"{csv_path}: Detected grid_size={grid_size}, expected {expected_size}")
            print(f"✗ {Path(csv_path).name}: grid_size={grid_size}, expected {expected_size}")
        else:
            print(f"✓ {Path(csv_path).name}:")
            print(f"  → grid_size: {grid_size}")
            print(f"  → folder_name: {folder_name}")
            print(f"  → table_name: {table_name}")
    
    return len(issues) == 0, issues


def main():
    """Run all tests."""
    print("=" * 60)
    print("ETL Pipeline Validation Tests")
    print("=" * 60)
    
    tests = [
        ("CSV Reading", test_csv_reading),
        ("GPKG Structure", test_gpkg_structure),
        ("Data Preprocessing", test_data_preprocessing),
        ("Column Detection", test_column_detection),
        ("Schema Generation", test_schema_generation),
        ("Table Mapping", test_table_mapping),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success, issues = test_func()
            results.append((test_name, success, issues))
        except Exception as e:
            print(f"\n✗ {test_name} failed with exception: {e}")
            results.append((test_name, False, [str(e)]))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for test_name, success, issues in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")
        if issues:
            for issue in issues[:3]:  # Show first 3 issues
                print(f"    - {issue}")
            if len(issues) > 3:
                print(f"    ... and {len(issues) - 3} more issues")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! ETL pipeline looks good.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Review issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())


