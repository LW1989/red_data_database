"""
Load Bundestagswahlen (Federal Election) data into PostgreSQL.

Supports loading:
- Electoral district shapefiles (BTW2017, BTW2021, BTW2025)
- Structural data CSV files with complex parsing and column mapping

Key features:
- Dynamic header row detection (handles 8-9 comment rows)
- German number format parsing (comma decimals, dot thousands)
- Column name normalization (removes date-specific parts)
- BTW2017 column mapping to unified schema (86.5% compatibility)
- CRS reprojection from EPSG:25832 to EPSG:3035
"""

import sys
import argparse
import re
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import geopandas as gpd
from sqlalchemy import text
from etl.utils import get_db_engine, logger


# BTW2017 to unified schema column mapping
BTW2017_COLUMN_MAPPING = {
    # Exact matches
    'land': 'land',
    'wahlkreis_nr': 'wahlkreis_nr',
    'wahlkreis_name': 'wahlkreis_name',
    'gemeinden_anzahl': 'gemeinden_anzahl',
    'fl_che_km': 'flaeche_km2',
    'bev_lkerung_insgesamt_in': 'bevoelkerung_insgesamt_1000',
    'bev_lkerung_deutsche_in': 'bevoelkerung_deutsche_1000',
    'alter_von_bis_jahren_unter_18': 'alter_unter_18_pct',
    'alter_von_bis_jahren_18_24': 'alter_18_24_pct',
    'alter_von_bis_jahren_25_34': 'alter_25_34_pct',
    'alter_von_bis_jahren_35_59': 'alter_35_59_pct',
    'alter_von_bis_jahren_60_74': 'alter_60_74_pct',
    'alter_von_bis_jahren_75_und_mehr': 'alter_75_plus_pct',
    'sozialversicherungspflichtig_besch_ftigte_land_und_forstwirtschaft_fischerei': 'beschaeftigte_landwirtschaft_pct',
    'sozialversicherungspflichtig_besch_ftigte_produzierendes_gewerbe': 'beschaeftigte_produzierendes_gewerbe_pct',
    'sozialversicherungspflichtig_besch_ftigte_handel_gastgewerbe_verkehr': 'beschaeftigte_handel_gastgewerbe_verkehr_pct',
    'sozialversicherungspflichtig_besch_ftigte_ffentliche_und_private_dienstleister': 'beschaeftigte_oeffentliche_dienstleister_pct',
    'sozialversicherungspflichtig_besch_ftigte_brige_dienstleister_und_ohne_angabe': 'beschaeftigte_uebrige_dienstleister_pct',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_nicht_erwerbsf_hige_hilfebed_rftige': 'sgb2_nicht_erwerbsfaehig_pct',
    'fu_noten': 'fussnoten',
    
    # Semantic matches (different naming, same concept)
    'bev_lkerung_ausl_nder': 'bevoelkerung_auslaender_pct',
    'bev_lkerungsdichte_einwohner_je_km': 'bevoelkerungsdichte',
    'zu_bzw_abnahme_der_bev_lkerung_geburtensaldo_je_einwohner': 'bevoelkerung_geburten_saldo_je_1000ew',
    'zu_bzw_abnahme_der_bev_lkerung_wanderungssaldo_je_einwohner': 'bevoelkerung_wanderung_saldo_je_1000ew',
    'baut_tigkeit_und_wohnungswesen_fertiggestellte_wohnungen_je_einwohner': 'wohnungen_fertiggestellt_je_1000ew',
    'baut_tigkeit_und_wohnungswesen_bestand_an_wohnungen_je_einwohner': 'wohnungen_bestand_je_1000ew',
    'verf_gbares_einkommen_der_privaten_haushalte_je_einwohner': 'einkommen_verfuegbar_eur_je_ew',
    'bruttoinlandsprodukt_je_einwohner': 'bip_eur_je_ew',
    'unternehmensregister_unternehmen_insgesamt_je_einwohner': 'unternehmen_insgesamt_je_1000ew',
    'unternehmensregister_handwerksunternehmen_je_einwohner': 'unternehmen_handwerk_je_1000ew',
    'sozialversicherungspflichtig_besch_ftigte_insgesamt_je_einwohner': 'beschaeftigte_insgesamt_je_1000ew',
    'absolventen_abg_nger_beruflicher_schulen': 'schulabgaenger_berufliche_schulen',
    'absolventen_abg_nger_allgemeinbildender_schulen_insgesamt_ohne_externe_je_einwohner': 'schulabgaenger_allgemeinbildend_je_1000ew',
    'absolventen_abg_nger_allgemeinbildender_schulen_ohne_hauptschulabschluss': 'schulabgaenger_ohne_hauptschulabschluss_pct',
    'absolventen_abg_nger_allgemeinbildender_schulen_mit_hauptschulabschluss': 'schulabgaenger_hauptschulabschluss_pct',
    'absolventen_abg_nger_allgemeinbildender_schulen_mit_mittlerem_schulabschluss': 'schulabgaenger_mittlerer_abschluss_pct',
    'absolventen_abg_nger_allgemeinbildender_schulen_mit_allgemeiner_und_fachhochschulreife': 'schulabgaenger_abitur_pct',
    'kraftfahrzeugbestand_je_einwohner': 'pkw_bestand_je_1000ew',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_insgesamt_je_einwohner': 'sgb2_leistungsempfaenger_je_1000ew',
    'empf_nger_innen_von_leistungen_nach_sgb_ii_ausl_nder': 'sgb2_auslaender_pct',
    'arbeitslosenquote_m_rz_insgesamt': 'arbeitslosenquote_insgesamt_pct',
    'arbeitslosenquote_m_rz_m_nner': 'arbeitslosenquote_maenner_pct',
    'arbeitslosenquote_m_rz_frauen': 'arbeitslosenquote_frauen_pct',
    'arbeitslosenquote_m_rz_15_bis_unter_20_jahre': 'arbeitslosenquote_15_24_pct',
    'arbeitslosenquote_m_rz_55_bis_unter_65_jahre': 'arbeitslosenquote_55_64_pct',
}

# Unified schema columns (all 52 columns)
UNIFIED_SCHEMA_COLUMNS = [
    'wahlkreis_nr', 'gemeinden_anzahl', 'flaeche_km2',
    'bevoelkerung_insgesamt_1000', 'bevoelkerung_deutsche_1000', 'bevoelkerung_auslaender_pct',
    'bevoelkerungsdichte', 'bevoelkerung_geburten_saldo_je_1000ew', 'bevoelkerung_wanderung_saldo_je_1000ew',
    'alter_unter_18_pct', 'alter_18_24_pct', 'alter_25_34_pct', 'alter_35_59_pct',
    'alter_60_74_pct', 'alter_75_plus_pct',
    'bodenflaeche_siedlung_verkehr_pct', 'bodenflaeche_vegetation_gewaesser_pct',
    'wohnungen_fertiggestellt_je_1000ew', 'wohnungen_bestand_je_1000ew',
    'wohnflaeche_je_wohnung', 'wohnflaeche_je_ew',
    'pkw_bestand_je_1000ew', 'pkw_elektro_hybrid_pct',
    'unternehmen_insgesamt_je_1000ew', 'unternehmen_handwerk_je_1000ew',
    'einkommen_verfuegbar_eur_je_ew', 'bip_eur_je_ew',
    'schulabgaenger_berufliche_schulen', 'schulabgaenger_allgemeinbildend_je_1000ew',
    'schulabgaenger_ohne_hauptschulabschluss_pct', 'schulabgaenger_hauptschulabschluss_pct',
    'schulabgaenger_mittlerer_abschluss_pct', 'schulabgaenger_abitur_pct',
    'kindertagesbetreuung_unter_3_pct', 'kindertagesbetreuung_3_6_pct',
    'beschaeftigte_insgesamt_je_1000ew', 'beschaeftigte_landwirtschaft_pct',
    'beschaeftigte_produzierendes_gewerbe_pct', 'beschaeftigte_handel_gastgewerbe_verkehr_pct',
    'beschaeftigte_oeffentliche_dienstleister_pct', 'beschaeftigte_uebrige_dienstleister_pct',
    'sgb2_leistungsempfaenger_je_1000ew', 'sgb2_nicht_erwerbsfaehig_pct', 'sgb2_auslaender_pct',
    'arbeitslosenquote_insgesamt_pct', 'arbeitslosenquote_maenner_pct', 'arbeitslosenquote_frauen_pct',
    'arbeitslosenquote_15_24_pct', 'arbeitslosenquote_55_64_pct',
    'fussnoten'
]


def find_header_row(csv_path: Path, encoding: str = 'utf-8-sig') -> Optional[int]:
    """
    Find the header row in election CSV file (contains 'Land' and 'Wahlkreis').
    
    Args:
        csv_path: Path to CSV file
        encoding: File encoding
        
    Returns:
        Zero-indexed line number of header row, or None if not found
    """
    try:
        with open(csv_path, 'r', encoding=encoding) as f:
            for i, line in enumerate(f):
                parts = line.split(';')
                if len(parts) > 2 and 'Land' in parts[0] and 'Wahlkreis' in parts[1]:
                    logger.info(f"Found header row at line {i + 1} (0-indexed: {i})")
                    return i
    except Exception as e:
        logger.error(f"Error finding header row: {e}")
    return None


def normalize_column_name(col_name: str) -> str:
    """
    Normalize column name by removing date-specific parts and standardizing format.
    
    Examples:
        "Gemeinden am 31.12.2019 (Anzahl)" -> "gemeinden_anzahl"
        "Bevölkerung am 31.12.2023 - Insgesamt (in 1000)" -> "bev_lkerung_insgesamt_in"
    
    Args:
        col_name: Original column name
        
    Returns:
        Normalized column name
    """
    # Remove date patterns (am DD.MM.YYYY)
    col = re.sub(r'\s*am\s+\d{2}\.\d{2}\.\d{4}\s*', ' ', col_name)
    # Remove standalone years
    col = re.sub(r'\s+\d{4}\s+', ' ', col)
    # Remove month names (for unemployment data)
    col = re.sub(r'\s+(Januar|Februar|M.rz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+', ' ', col)
    # Convert to lowercase
    col = col.lower()
    # Replace non-alphanumeric with spaces
    col = re.sub(r'[^a-z0-9\s]', ' ', col)
    # Replace multiple spaces with single underscore
    col = re.sub(r'\s+', '_', col)
    # Remove leading/trailing underscores
    col = col.strip('_')
    return col


def parse_german_number(value: Any) -> Optional[float]:
    """
    Convert German number format to float.
    
    German format: 2.124,3 = 2124.3 (dot = thousands, comma = decimal)
    
    Args:
        value: Input value
        
    Returns:
        Float value or None
    """
    if pd.isna(value) or value == '' or value == '–':
        return None
    
    value_str = str(value).strip()
    # Remove thousands separators (dots)
    value_str = value_str.replace('.', '')
    # Replace decimal comma with dot
    value_str = value_str.replace(',', '.')
    
    try:
        return float(value_str)
    except (ValueError, TypeError):
        return None


def normalize_wahlkreis_nr(value: Any) -> Optional[int]:
    """
    Normalize Wahlkreis-Nr. to integer (handles zero-padding).
    
    Args:
        value: Input value (may be "001", "1", etc.)
        
    Returns:
        Integer value or None
    """
    if pd.isna(value):
        return None
    try:
        # Remove leading zeros and convert to int
        return int(str(value).lstrip('0') or '0')
    except (ValueError, TypeError):
        return None


def load_election_csv(csv_path: Path, election_year: int) -> pd.DataFrame:
    """
    Load election structural data CSV with proper parsing and column mapping.
    
    Args:
        csv_path: Path to CSV file
        election_year: Election year (2017, 2021, or 2025)
        
    Returns:
        DataFrame with unified schema
    """
    logger.info(f"Loading election CSV for {election_year}: {csv_path}")
    
    # Determine encoding
    if election_year == 2017:
        encoding = 'iso-8859-1'
    else:
        encoding = 'utf-8-sig'
    
    # Find header row
    header_row = find_header_row(csv_path, encoding)
    if header_row is None:
        raise ValueError(f"Could not find header row in {csv_path}")
    
    # Read CSV
    logger.info(f"Reading CSV with encoding {encoding}, header at row {header_row}")
    df = pd.read_csv(
        csv_path,
        encoding=encoding,
        sep=';',
        skiprows=header_row,
        low_memory=False
    )
    
    logger.info(f"Read {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"Original columns (first 5): {list(df.columns)[:5]}")
    
    # Normalize column names
    df.columns = [normalize_column_name(col) for col in df.columns]
    logger.info(f"Normalized columns (first 5): {list(df.columns)[:5]}")
    
    # Apply BTW2017 column mapping if needed
    if election_year == 2017:
        logger.info("Applying BTW2017 column mapping to unified schema")
        mapped_df = pd.DataFrame()
        
        for btw2017_col, unified_col in BTW2017_COLUMN_MAPPING.items():
            if btw2017_col in df.columns:
                mapped_df[unified_col] = df[btw2017_col]
            else:
                logger.debug(f"BTW2017 column not found: {btw2017_col}")
        
        df = mapped_df
        logger.info(f"After mapping: {len(df.columns)} columns")
    
    # Ensure all unified schema columns exist (fill missing with None)
    for col in UNIFIED_SCHEMA_COLUMNS:
        if col not in df.columns:
            df[col] = None
            logger.debug(f"Added missing column (NULL): {col}")
    
    # Select only unified schema columns in correct order
    df = df[UNIFIED_SCHEMA_COLUMNS].copy()
    
    # Normalize Wahlkreis-Nr.
    df['wahlkreis_nr'] = df['wahlkreis_nr'].apply(normalize_wahlkreis_nr)
    
    # Parse numeric columns (all except wahlkreis_nr and fussnoten)
    numeric_cols = [col for col in UNIFIED_SCHEMA_COLUMNS 
                   if col not in ['wahlkreis_nr', 'fussnoten']]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_german_number)
    
    # Filter out summary rows (keep only Wahlkreis-Nr. 1-299)
    original_len = len(df)
    df = df[df['wahlkreis_nr'].notna() & (df['wahlkreis_nr'] >= 1) & (df['wahlkreis_nr'] <= 299)]
    logger.info(f"Filtered summary rows: {original_len} -> {len(df)} rows")
    
    # Add election_year
    df['election_year'] = election_year
    
    logger.info(f"Final DataFrame: {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"Wahlkreis-Nr. range: {df['wahlkreis_nr'].min()} - {df['wahlkreis_nr'].max()}")
    
    return df


def load_electoral_district_shapefile(shapefile_path: Path, election_year: int, engine):
    """
    Load electoral district shapefile into PostgreSQL.
    
    Args:
        shapefile_path: Path to shapefile
        election_year: Election year (2017, 2021, or 2025)
        engine: Database engine
    """
    logger.info(f"Loading electoral district shapefile: {shapefile_path}")
    logger.info(f"Election year: {election_year}")
    
    # Read shapefile
    try:
        gdf = gpd.read_file(shapefile_path)
        logger.info(f"Read {len(gdf)} features from shapefile")
        logger.info(f"Available columns: {list(gdf.columns)}")
    except Exception as e:
        logger.error(f"Failed to read shapefile: {e}")
        raise
    
    # Ensure CRS is EPSG:3035
    if gdf.crs is None:
        # Bundestagswahlen shapefiles from Bundeswahlleiter are in EPSG:25832 (ETRS89 / UTM Zone 32N)
        # This fallback should rarely/never be needed since GeoPandas reads .prj files
        logger.warning("No CRS found in shapefile (unusual). Assuming EPSG:25832 (ETRS89/UTM32N) based on Bundeswahlleiter specification.")
        logger.warning("Verify the .prj file exists and is readable.")
        gdf.set_crs(epsg=25832, inplace=True)
    
    if gdf.crs.to_epsg() != 3035:
        logger.info(f"Reprojecting from {gdf.crs} to EPSG:3035")
        gdf = gdf.to_crs(epsg=3035)
    
    # Validate geometries
    invalid_count = (~gdf.geometry.is_valid).sum()
    if invalid_count > 0:
        logger.warning(f"Found {invalid_count} invalid geometries, fixing with buffer(0)")
        gdf.loc[~gdf.geometry.is_valid, 'geometry'] = gdf.loc[~gdf.geometry.is_valid, 'geometry'].buffer(0)
    
    # Extract required columns (column names vary by election year)
    # Common patterns: WKR_NR, WKNR, WKR (Wahlkreis number)
    #                  WKR_NAME, NAME (Wahlkreis name)
    #                  LAND_NR, BL_NR (Bundesland number)
    #                  LAND_NAME, BL_NAME (Bundesland name)
    
    result_df = gpd.GeoDataFrame()
    
    # Find Wahlkreis number column
    wkr_cols = ['WKR_NR', 'WKNR', 'WKR']
    wkr_col = next((col for col in wkr_cols if col in gdf.columns), None)
    if wkr_col:
        result_df['wahlkreis_nr'] = gdf[wkr_col].astype(int)
    else:
        raise ValueError(f"Could not find Wahlkreis number column. Available: {list(gdf.columns)}")
    
    # Find Wahlkreis name column
    name_cols = ['WKR_NAME', 'NAME']
    name_col = next((col for col in name_cols if col in gdf.columns), None)
    if name_col:
        result_df['wahlkreis_name'] = gdf[name_col].astype(str)
    else:
        logger.warning("Could not find Wahlkreis name column, using 'Unknown'")
        result_df['wahlkreis_name'] = 'Unknown'
    
    # Find Land number column
    land_nr_cols = ['LAND_NR', 'BL_NR', 'BL']
    land_nr_col = next((col for col in land_nr_cols if col in gdf.columns), None)
    if land_nr_col:
        result_df['land_nr'] = gdf[land_nr_col].astype(str)
    else:
        logger.warning("Could not find Land number column, using '00'")
        result_df['land_nr'] = '00'
    
    # Find Land name column
    land_name_cols = ['LAND_NAME', 'BL_NAME']
    land_name_col = next((col for col in land_name_cols if col in gdf.columns), None)
    if land_name_col:
        result_df['land_name'] = gdf[land_name_col].astype(str)
    else:
        logger.warning("Could not find Land name column, using 'Unknown'")
        result_df['land_name'] = 'Unknown'
    
    result_df['election_year'] = election_year
    result_df['geom'] = gdf.geometry
    result_df = result_df.set_geometry('geom', crs=3035)
    
    logger.info(f"Prepared {len(result_df)} electoral districts")
    logger.info(f"Wahlkreis-Nr. range: {result_df['wahlkreis_nr'].min()} - {result_df['wahlkreis_nr'].max()}")
    
    # Insert into database
    inserted_rows = 0
    error_count = 0
    
    for idx, row in result_df.iterrows():
        try:
            insert_stmt = text("""
                INSERT INTO zensus.ref_electoral_district 
                (wahlkreis_nr, wahlkreis_name, land_nr, land_name, election_year, geom)
                VALUES (:wahlkreis_nr, :wahlkreis_name, :land_nr, :land_name, :election_year,
                        ST_SetSRID(ST_GeomFromWKB(:geom_wkb), 3035))
                ON CONFLICT (wahlkreis_nr, election_year) DO NOTHING
            """)
            
            with engine.connect() as conn:
                conn.execute(insert_stmt, {
                    'wahlkreis_nr': int(row['wahlkreis_nr']),
                    'wahlkreis_name': row['wahlkreis_name'],
                    'land_nr': row['land_nr'],
                    'land_name': row['land_name'],
                    'election_year': election_year,
                    'geom_wkb': row['geom'].wkb
                })
                conn.commit()
                inserted_rows += 1
        except Exception as e:
            error_count += 1
            logger.warning(f"Failed to insert Wahlkreis {row['wahlkreis_nr']}: {e}")
    
    logger.info(f"Inserted {inserted_rows} electoral districts, {error_count} errors")
    
    # Verify insertion
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM zensus.ref_electoral_district WHERE election_year = :year"
        ), {"year": election_year})
        count = result.scalar()
        logger.info(f"Total electoral districts for {election_year}: {count}")


def load_structural_data_csv(csv_path: Path, election_year: int, engine):
    """
    Load election structural data CSV into PostgreSQL.
    
    Args:
        csv_path: Path to CSV file
        election_year: Election year (2017, 2021, or 2025)
        engine: Database engine
    """
    # Load and parse CSV
    df = load_election_csv(csv_path, election_year)
    
    # Prepare column list for INSERT
    # UNIFIED_SCHEMA_COLUMNS already starts with 'wahlkreis_nr', so insert 'election_year' after it
    columns = [UNIFIED_SCHEMA_COLUMNS[0], 'election_year'] + UNIFIED_SCHEMA_COLUMNS[1:]
    
    # Insert into database
    inserted_rows = 0
    error_count = 0
    
    logger.info(f"Inserting {len(df)} rows into fact_election_structural_data")
    
    for idx, row in df.iterrows():
        try:
            # Build VALUES placeholders
            placeholders = ', '.join([f':{col}' for col in columns])
            
            insert_stmt = text(f"""
                INSERT INTO zensus.fact_election_structural_data 
                ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (wahlkreis_nr, election_year) DO NOTHING
            """)
            
            # Prepare record
            record = {col: row.get(col) for col in UNIFIED_SCHEMA_COLUMNS}
            record['wahlkreis_nr'] = int(row['wahlkreis_nr'])
            record['election_year'] = election_year
            
            with engine.connect() as conn:
                conn.execute(insert_stmt, record)
                conn.commit()
                inserted_rows += 1
                
                if inserted_rows % 50 == 0:
                    logger.info(f"Inserted {inserted_rows}/{len(df)} rows")
        
        except Exception as e:
            error_count += 1
            logger.warning(f"Failed to insert Wahlkreis {row['wahlkreis_nr']}: {e}")
    
    logger.info(f"Inserted {inserted_rows} structural data rows, {error_count} errors")
    
    # Verify insertion
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM zensus.fact_election_structural_data WHERE election_year = :year"
        ), {"year": election_year})
        count = result.scalar()
        logger.info(f"Total structural data records for {election_year}: {count}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Load Bundestagswahlen election data into PostgreSQL'
    )
    parser.add_argument(
        '--shapefile',
        type=Path,
        help='Path to electoral district shapefile'
    )
    parser.add_argument(
        '--csv',
        type=Path,
        help='Path to structural data CSV file'
    )
    parser.add_argument(
        '--election-year',
        type=int,
        choices=[2017, 2021, 2025],
        required=True,
        help='Election year'
    )
    
    args = parser.parse_args()
    
    if not args.shapefile and not args.csv:
        parser.error("At least one of --shapefile or --csv must be provided")
    
    engine = get_db_engine()
    
    try:
        if args.shapefile:
            if not args.shapefile.exists():
                logger.error(f"Shapefile not found: {args.shapefile}")
                sys.exit(1)
            load_electoral_district_shapefile(args.shapefile, args.election_year, engine)
        
        if args.csv:
            if not args.csv.exists():
                logger.error(f"CSV file not found: {args.csv}")
                sys.exit(1)
            load_structural_data_csv(args.csv, args.election_year, engine)
        
        logger.info("Election data loading completed successfully")
    except Exception as e:
        logger.error(f"Election data loading failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

