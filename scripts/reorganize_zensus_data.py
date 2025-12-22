#!/usr/bin/env python3
"""
Reorganize Zensus data files into a new structure:
- data/zensus_data/10km/ - All 10km CSV files
- data/zensus_data/1km/ - All 1km CSV files
- data/zensus_data/100m/ - All 100m CSV files
- data/zensus_data/descriptions/ - All Excel description files
"""

import shutil
from pathlib import Path
import re

def extract_dataset_name(csv_filename: str) -> str:
    """
    Extract dataset name from CSV filename.
    
    Examples:
    - Zensus2022_Bevoelkerungszahl_10km-Gitter.csv -> Bevoelkerungszahl
    - Zensus2022_Alter_in_5_Altersklassen_1km-Gitter.csv -> Alter_in_5_Altersklassen
    """
    # Remove Zensus2022_ prefix and _10km-Gitter.csv suffix
    name = csv_filename.replace('Zensus2022_', '')
    # Remove grid size suffix (e.g., _10km-Gitter, _1km-Gitter, _100m-Gitter)
    name = re.sub(r'_[0-9]+km-Gitter\.csv$', '', name)
    name = re.sub(r'_100m-Gitter\.csv$', '', name)
    return name

def reorganize_zensus_data(source_dir: Path, dry_run: bool = False):
    """
    Reorganize Zensus data files into new folder structure.
    
    Args:
        source_dir: Path to data/zensus_data directory
        dry_run: If True, only print what would be done without actually moving files
    """
    source_dir = Path(source_dir)
    
    # Create new directory structure
    dirs = {
        '10km': source_dir / '10km',
        '1km': source_dir / '1km',
        '100m': source_dir / '100m',
        'descriptions': source_dir / 'descriptions'
    }
    
    if not dry_run:
        for dir_path in dirs.values():
            dir_path.mkdir(exist_ok=True)
            print(f"Created directory: {dir_path}")
    
    # Find all CSV and Excel files
    csv_files = list(source_dir.rglob('*.csv'))
    xlsx_files = list(source_dir.rglob('*.xlsx'))
    
    # Filter out temporary Excel files (starting with ~$)
    xlsx_files = [f for f in xlsx_files if not f.name.startswith('~$')]
    
    moved_count = {'10km': 0, '1km': 0, '100m': 0, 'descriptions': 0}
    
    # Move CSV files
    for csv_file in csv_files:
        # Skip if already in target directory
        if csv_file.parent.name in ['10km', '1km', '100m', 'descriptions']:
            continue
        
        filename = csv_file.name
        source_path = csv_file
        
        # Determine target directory based on filename
        if '10km-Gitter' in filename or '10km_Gitter' in filename:
            target_dir = dirs['10km']
            moved_count['10km'] += 1
        elif '1km-Gitter' in filename or '1km_Gitter' in filename:
            target_dir = dirs['1km']
            moved_count['1km'] += 1
        elif '100m-Gitter' in filename or '100m_Gitter' in filename:
            target_dir = dirs['100m']
            moved_count['100m'] += 1
        else:
            print(f"⚠️  Could not determine grid size for: {csv_file}")
            continue
        
        target_path = target_dir / filename
        
        if dry_run:
            print(f"Would move: {source_path} -> {target_path}")
        else:
            if target_path.exists():
                print(f"⚠️  File already exists, skipping: {target_path}")
            else:
                shutil.move(str(source_path), str(target_path))
                print(f"✓ Moved: {filename} -> {target_dir.name}/")
    
    # Move Excel files
    for xlsx_file in xlsx_files:
        # Skip if already in target directory
        if xlsx_file.parent.name in ['10km', '1km', '100m', 'descriptions']:
            continue
        
        filename = xlsx_file.name
        source_path = xlsx_file
        target_path = dirs['descriptions'] / filename
        
        if dry_run:
            print(f"Would move: {source_path} -> {target_path}")
        else:
            if target_path.exists():
                print(f"⚠️  File already exists, skipping: {target_path}")
            else:
                shutil.move(str(source_path), str(target_path))
                print(f"✓ Moved: {filename} -> descriptions/")
                moved_count['descriptions'] += 1
    
    # Summary
    print("\n" + "="*60)
    print("Reorganization Summary")
    print("="*60)
    print(f"10km CSV files: {moved_count['10km']}")
    print(f"1km CSV files: {moved_count['1km']}")
    print(f"100m CSV files: {moved_count['100m']}")
    print(f"Description files: {moved_count['descriptions']}")
    print(f"Total files moved: {sum(moved_count.values())}")
    
    if dry_run:
        print("\n⚠️  DRY RUN - No files were actually moved")
        print("Run without --dry-run to perform the reorganization")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Reorganize Zensus data files into grid-size-based folders'
    )
    parser.add_argument(
        '--source-dir',
        type=Path,
        default=Path('data/zensus_data'),
        help='Source directory (default: data/zensus_data)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually moving files'
    )
    
    args = parser.parse_args()
    
    if not args.source_dir.exists():
        print(f"Error: Source directory does not exist: {args.source_dir}")
        return 1
    
    reorganize_zensus_data(args.source_dir, dry_run=args.dry_run)
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())

