#!/usr/bin/env python3
"""
Calculate weighted demographic statistics for LWU Berlin properties.

This script:
1. Spatially intersects LWU properties with 100m zensus grid cells
2. Calculates weighted averages for:
   - Durchschnittsmiete (average rent)
   - Heizungsart (heating types)
   - Energieträger (energy sources)
   - Baujahr (construction years)
3. Exports results to CSV for review
4. Optionally inserts into database table
"""

import sys
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from datetime import datetime
import numpy as np
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LWUWeightedStatsCalculator:
    """Calculate weighted statistics for LWU properties from zensus data."""
    
    def __init__(self, save_intermediates=True):
        """Initialize database connection."""
        self.engine = self._create_db_connection()
        self.results_df = None
        self.save_intermediates = save_intermediates
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Store intermediate dataframes for debugging/inspection
        self.intermediates = {}
        
    def _create_db_connection(self):
        """Create database connection using credentials."""
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
        logger.info(f"Connected to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        return engine
    
    def load_spatial_intersections(self):
        """
        Load spatial intersections between properties and 100m grid cells.
        Calculate overlap areas and ratios.
        """
        logger.info("Loading spatial intersections...")
        
        query = """
        WITH property_grid_intersections AS (
            SELECT 
                p.property_id,
                g.grid_id,
                ST_Area(ST_Intersection(p.geom, g.geom)) as overlap_area,
                ST_Area(g.geom) as grid_area,
                ST_Area(ST_Intersection(p.geom, g.geom)) / ST_Area(g.geom) as overlap_ratio
            FROM zensus.ref_lwu_properties p
            INNER JOIN zensus.ref_grid_100m g
                ON ST_Intersects(p.geom, g.geom)
        )
        SELECT * FROM property_grid_intersections
        ORDER BY property_id, grid_id;
        """
        
        df = pd.read_sql(query, self.engine)
        logger.info(f"Loaded {len(df):,} property-grid intersections")
        logger.info(f"Covering {df['property_id'].nunique():,} unique properties")
        
        # Save for inspection
        self.intermediates['spatial_intersections'] = df
        if self.save_intermediates:
            filename = f"intermediate_spatial_intersections_{self.timestamp}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"💾 Saved intermediate: {filename}")
        
        return df
    
    def load_rent_data(self, grid_ids):
        """Load rent data for specific grid cells."""
        logger.info("Loading rent data...")
        
        # Convert grid_ids to list for query
        grid_list = tuple(grid_ids.tolist())
        
        query = f"""
        SELECT 
            grid_id,
            durchschnmieteqm,
            anzahlwohnungen
        FROM zensus.fact_zensus_100m_durchschnittliche_nettokaltmiete_und_anzahl_der_wohnungen
        WHERE grid_id IN {grid_list}
        AND durchschnmieteqm IS NOT NULL
        AND anzahlwohnungen IS NOT NULL
        AND anzahlwohnungen > 0;
        """
        
        df = pd.read_sql(query, self.engine)
        logger.info(f"Loaded rent data for {len(df):,} grid cells")
        
        # Save for inspection
        self.intermediates['rent_data'] = df
        if self.save_intermediates:
            filename = f"intermediate_rent_data_{self.timestamp}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"💾 Saved intermediate: {filename}")
        
        return df
    
    def load_heating_data(self, grid_ids):
        """Load heating type data for specific grid cells."""
        logger.info("Loading heating data...")
        
        grid_list = tuple(grid_ids.tolist())
        
        query = f"""
        SELECT 
            grid_id,
            fernheizung,
            etagenheizung,
            blockheizung,
            zentralheizung,
            einzel_mehrraumoefen,
            keine_heizung
        FROM zensus.fact_zensus_100m_heizungsart
        WHERE grid_id IN {grid_list};
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Calculate own total from non-NULL categories
        heating_cols = ['fernheizung', 'etagenheizung', 'blockheizung', 
                       'zentralheizung', 'einzel_mehrraumoefen', 'keine_heizung']
        df['calculated_total'] = df[heating_cols].sum(axis=1, min_count=1)
        
        logger.info(f"Loaded heating data for {len(df):,} grid cells")
        logger.info(f"Grid cells with calculated totals: {df['calculated_total'].notna().sum():,}")
        
        # Save for inspection
        self.intermediates['heating_data'] = df
        if self.save_intermediates:
            filename = f"intermediate_heating_data_{self.timestamp}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"💾 Saved intermediate: {filename}")
        
        return df
    
    def load_energy_data(self, grid_ids):
        """Load energy source data for specific grid cells."""
        logger.info("Loading energy data...")
        
        grid_list = tuple(grid_ids.tolist())
        
        query = f"""
        SELECT 
            grid_id,
            gas,
            heizoel,
            holz_holzpellets,
            biomasse_biogas,
            solar_geothermie_waermepumpen,
            strom,
            kohle,
            fernwaerme,
            kein_energietraeger
        FROM zensus.fact_zensus_100m_energietraeger
        WHERE grid_id IN {grid_list};
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Calculate own total from non-NULL categories
        energy_cols = ['gas', 'heizoel', 'holz_holzpellets', 'biomasse_biogas',
                      'solar_geothermie_waermepumpen', 'strom', 'kohle', 
                      'fernwaerme', 'kein_energietraeger']
        df['calculated_total'] = df[energy_cols].sum(axis=1, min_count=1)
        
        logger.info(f"Loaded energy data for {len(df):,} grid cells")
        logger.info(f"Grid cells with calculated totals: {df['calculated_total'].notna().sum():,}")
        
        # Save for inspection
        self.intermediates['energy_data'] = df
        if self.save_intermediates:
            filename = f"intermediate_energy_data_{self.timestamp}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"💾 Saved intermediate: {filename}")
        
        return df
    
    def load_baujahr_data(self, grid_ids):
        """Load construction year data for specific grid cells."""
        logger.info("Loading construction year data...")
        
        grid_list = tuple(grid_ids.tolist())
        
        query = f"""
        SELECT 
            grid_id,
            vor1919,
            a1919bis1948,
            a1949bis1978,
            a1979bis1990,
            a1991bis2000,
            a2001bis2010,
            a2011bis2019,
            a2020undspaeter
        FROM zensus.fact_zensus_100m_gebaeude_nach_baujahr_in_mikrozensus_klassen
        WHERE grid_id IN {grid_list};
        """
        
        df = pd.read_sql(query, self.engine)
        
        # Calculate own total from non-NULL categories
        baujahr_cols = ['vor1919', 'a1919bis1948', 'a1949bis1978', 'a1979bis1990',
                       'a1991bis2000', 'a2001bis2010', 'a2011bis2019', 'a2020undspaeter']
        df['calculated_total'] = df[baujahr_cols].sum(axis=1, min_count=1)
        
        logger.info(f"Loaded construction year data for {len(df):,} grid cells")
        logger.info(f"Grid cells with calculated totals: {df['calculated_total'].notna().sum():,}")
        
        # Save for inspection
        self.intermediates['baujahr_data'] = df
        if self.save_intermediates:
            filename = f"intermediate_baujahr_data_{self.timestamp}.csv"
            df.to_csv(filename, index=False)
            logger.info(f"💾 Saved intermediate: {filename}")
        
        return df
    
    def calculate_weighted_rent(self, intersections_df, rent_df):
        """
        Calculate weighted average rent for each property.
        
        WEIGHTED AVERAGE APPROACH:
        ==========================
        A property may span multiple 100m grid cells. We need to combine rent data
        from all these grid cells into a single weighted average for the property.
        
        The weight for each grid cell should reflect:
        1. How much of the property overlaps with that grid cell (overlap_ratio)
        2. How many flats are in that grid cell (anzahlwohnungen)
        
        Formula:
        weighted_avg_rent = Σ(overlap_ratio × anzahlwohnungen × rent) / Σ(overlap_ratio × anzahlwohnungen)
        
        This ensures that:
        - Grid cells with more flats contribute more to the average
        - Grid cells with larger overlap contribute more to the average
        - The result is a proper weighted average (not just a simple mean)
        """
        logger.info("Calculating weighted average rent...")
        
        # Step 1: Merge spatial intersections with rent data from zensus
        # This gives us, for each property-grid combination:
        # - property_id
        # - grid_id
        # - overlap_ratio (how much of the property is in this grid cell)
        # - durchschnmieteqm (average rent in this grid cell)
        # - anzahlwohnungen (number of flats in this grid cell)
        merged = intersections_df.merge(rent_df, on='grid_id', how='left')
        
        # Step 2: Calculate the weight for each property-grid combination
        # Weight = overlap_ratio × anzahlwohnungen
        # 
        # Why this weight?
        # - If a property has 50% overlap with a grid cell (overlap_ratio = 0.5)
        #   and that grid has 100 flats, we treat it as if the property contains
        #   50 equivalent flats from that grid cell
        # - This properly accounts for both spatial overlap AND flat density
        merged['weight'] = merged['overlap_ratio'] * merged['anzahlwohnungen'].fillna(0)
        
        # Step 3: Calculate weighted rent contribution from each grid cell
        # weighted_rent = weight × rent
        #               = (overlap_ratio × anzahlwohnungen) × durchschnmieteqm
        #
        # This is the numerator of our weighted average formula
        merged['weighted_rent'] = merged['weight'] * merged['durchschnmieteqm'].fillna(0)
        
        # Step 4: Aggregate by property (sum across all grid cells)
        # For each property, we sum:
        # - weighted_rent: Σ(overlap_ratio × anzahlwohnungen × rent)
        # - weight: Σ(overlap_ratio × anzahlwohnungen)
        result = merged.groupby('property_id').agg({
            'weighted_rent': 'sum',
            'weight': 'sum'
        }).reset_index()
        
        # Step 5: Calculate final weighted average
        # weighted_avg = Σ(weighted_rent) / Σ(weight)
        #              = Σ(overlap × flats × rent) / Σ(overlap × flats)
        #
        # This is the standard weighted average formula where:
        # - Each grid cell's rent is weighted by (overlap × flats)
        # - Grid cells with more overlap and more flats have more influence
        result['weighted_avg_rent_per_sqm'] = np.where(
            result['weight'] > 0,
            result['weighted_rent'] / result['weight'],
            np.nan  # Return NaN if no data (weight = 0)
        )
        
        result = result.rename(columns={'weight': 'rent_total_flats'})
        result = result[['property_id', 'weighted_avg_rent_per_sqm', 'rent_total_flats']]
        
        properties_with_data = result['weighted_avg_rent_per_sqm'].notna().sum()
        logger.info(f"Calculated rent for {properties_with_data:,} properties")
        
        # Save merged data for inspection
        self.intermediates['rent_merged'] = merged
        if self.save_intermediates:
            filename = f"intermediate_rent_merged_{self.timestamp}.csv"
            merged.to_csv(filename, index=False)
            logger.info(f"💾 Saved intermediate: {filename}")
        
        return result
    
    def calculate_weighted_proportions(self, intersections_df, fact_df, 
                                      category_cols, prefix):
        """
        Calculate weighted proportions for categorical data (heating, energy, baujahr).
        
        WEIGHTED PROPORTION APPROACH:
        ==============================
        For categorical data (e.g., heating types), each grid cell has counts for
        different categories (e.g., 62 buildings with Fernheizung, 44 with Zentralheizung).
        
        We want to calculate the proportion of each category for a property that spans
        multiple grid cells.
        
        Formula:
        category_proportion = Σ(overlap_ratio × category_count) / Σ(overlap_ratio × total_count)
        
        This is mathematically equivalent to:
        category_proportion = Σ(weight × (category / total)) / Σ(weight)
        
        Where weight = overlap_ratio × total_count
        
        Why this works:
        - Each grid cell contributes proportionally to how much the property overlaps it
        - Grid cells with more buildings contribute more to the final proportion
        - The result is a proper weighted average of proportions
        """
        logger.info(f"Calculating weighted proportions for {prefix}...")
        
        # Step 1: Merge spatial intersections with fact data
        # This gives us, for each property-grid combination:
        # - property_id
        # - grid_id  
        # - overlap_ratio
        # - category counts (e.g., fernheizung, zentralheizung, etc.)
        # - calculated_total (sum of all category counts for this grid)
        merged = intersections_df.merge(fact_df, on='grid_id', how='left')
        
        # Step 2: Calculate weight for each property-grid combination
        # Weight = overlap_ratio × calculated_total
        #
        # Why this weight?
        # - If a property has 50% overlap with a grid (overlap_ratio = 0.5)
        #   and that grid has 100 buildings total, we treat it as if the property
        #   contains 50 equivalent buildings from that grid
        # - This accounts for both spatial overlap AND building density
        merged['weight'] = merged['overlap_ratio'] * merged['calculated_total'].fillna(0)
        
        # Step 3: Calculate weighted value for each category
        # For each category (e.g., fernheizung):
        # weighted_category = overlap_ratio × category_count
        #
        # This is the numerator of our proportion formula
        # Note: We multiply by overlap_ratio, NOT by weight
        # This is mathematically correct and equivalent to the standard
        # weighted average formula (see docstring above for proof)
        results = []
        for col in category_cols:
            merged[f'weighted_{col}'] = (
                merged['overlap_ratio'] * merged[col].fillna(0)
            )
        
        # Step 4: Aggregate by property (sum across all grid cells)
        # For each property, we sum:
        # - weight: Σ(overlap_ratio × calculated_total) [denominator]
        # - weighted_category: Σ(overlap_ratio × category_count) [numerator]
        agg_dict = {'weight': 'sum'}
        for col in category_cols:
            agg_dict[f'weighted_{col}'] = 'sum'
        
        result = merged.groupby('property_id').agg(agg_dict).reset_index()
        
        # Step 5: Calculate final proportions
        # category_pct = Σ(weighted_category) / Σ(weight)
        #              = Σ(overlap × category_count) / Σ(overlap × total_count)
        #
        # Important: The sum of all category_pct will always equal 1.0 (100%)
        # because Σ(all categories) = total by definition
        for col in category_cols:
            result[f'{prefix}_{col}_pct'] = np.where(
                result['weight'] > 0,
                result[f'weighted_{col}'] / result['weight'],
                np.nan  # Return NaN if no data (weight = 0)
            )
        
        # Rename weight column
        result = result.rename(columns={'weight': f'{prefix}_total_buildings'})
        
        # Select final columns
        final_cols = ['property_id', f'{prefix}_total_buildings']
        final_cols.extend([f'{prefix}_{col}_pct' for col in category_cols])
        result = result[final_cols]
        
        properties_with_data = result[f'{prefix}_total_buildings'] > 0
        logger.info(f"Calculated {prefix} for {properties_with_data.sum():,} properties")
        
        # Save merged data for inspection
        self.intermediates[f'{prefix}_merged'] = merged
        if self.save_intermediates:
            filename = f"intermediate_{prefix}_merged_{self.timestamp}.csv"
            merged.to_csv(filename, index=False)
            logger.info(f"💾 Saved intermediate: {filename}")
        
        return result
    
    def calculate_all_statistics(self):
        """Main method to calculate all weighted statistics."""
        logger.info("="*80)
        logger.info("STARTING LWU WEIGHTED STATISTICS CALCULATION")
        logger.info("="*80)
        
        # Step 1: Load spatial intersections
        intersections_df = self.load_spatial_intersections()
        unique_grids = intersections_df['grid_id'].unique()
        
        # Step 2: Load all fact tables
        rent_df = self.load_rent_data(unique_grids)
        heating_df = self.load_heating_data(unique_grids)
        energy_df = self.load_energy_data(unique_grids)
        baujahr_df = self.load_baujahr_data(unique_grids)
        
        # Step 3: Calculate weighted statistics
        rent_results = self.calculate_weighted_rent(intersections_df, rent_df)
        
        heating_results = self.calculate_weighted_proportions(
            intersections_df, heating_df,
            ['fernheizung', 'etagenheizung', 'blockheizung', 'zentralheizung',
             'einzel_mehrraumoefen', 'keine_heizung'],
            'heating'
        )
        
        energy_results = self.calculate_weighted_proportions(
            intersections_df, energy_df,
            ['gas', 'heizoel', 'holz_holzpellets', 'biomasse_biogas',
             'solar_geothermie_waermepumpen', 'strom', 'kohle', 
             'fernwaerme', 'kein_energietraeger'],
            'energy'
        )
        
        baujahr_results = self.calculate_weighted_proportions(
            intersections_df, baujahr_df,
            ['vor1919', 'a1919bis1948', 'a1949bis1978', 'a1979bis1990',
             'a1991bis2000', 'a2001bis2010', 'a2011bis2019', 'a2020undspaeter'],
            'baujahr'
        )
        
        # Step 4: Get all property IDs to ensure we include all 5,468 properties
        logger.info("Loading all property IDs...")
        all_properties = pd.read_sql(
            "SELECT property_id FROM zensus.ref_lwu_properties ORDER BY property_id",
            self.engine
        )
        logger.info(f"Total properties in database: {len(all_properties):,}")
        
        # Step 5: Merge all results
        logger.info("Merging all results...")
        result = all_properties.copy()
        result = result.merge(rent_results, on='property_id', how='left')
        result = result.merge(heating_results, on='property_id', how='left')
        result = result.merge(energy_results, on='property_id', how='left')
        result = result.merge(baujahr_results, on='property_id', how='left')
        
        # Add timestamp
        result['created_at'] = datetime.now()
        
        self.results_df = result
        logger.info(f"Final dataset: {len(result):,} properties × {len(result.columns)} columns")
        
        return result
    
    def validate_results(self):
        """Validate calculation results."""
        logger.info("="*80)
        logger.info("VALIDATION CHECKS")
        logger.info("="*80)
        
        df = self.results_df
        
        # Check 1: Coverage statistics
        logger.info("\n1. DATA COVERAGE:")
        logger.info("-" * 40)
        rent_coverage = (df['weighted_avg_rent_per_sqm'].notna().sum() / len(df)) * 100
        heating_coverage = (df['heating_total_buildings'] > 0).sum() / len(df) * 100
        energy_coverage = (df['energy_total_buildings'] > 0).sum() / len(df) * 100
        baujahr_coverage = (df['baujahr_total_buildings'] > 0).sum() / len(df) * 100
        
        logger.info(f"Rent data:         {rent_coverage:.1f}% ({df['weighted_avg_rent_per_sqm'].notna().sum():,}/{len(df):,})")
        logger.info(f"Heating data:      {heating_coverage:.1f}% ({(df['heating_total_buildings'] > 0).sum():,}/{len(df):,})")
        logger.info(f"Energy data:       {energy_coverage:.1f}% ({(df['energy_total_buildings'] > 0).sum():,}/{len(df):,})")
        logger.info(f"Construction year: {baujahr_coverage:.1f}% ({(df['baujahr_total_buildings'] > 0).sum():,}/{len(df):,})")
        
        # Check 2: Proportion sums
        logger.info("\n2. PROPORTION SUMS (should be ~90-95% due to privacy protection):")
        logger.info("-" * 40)
        
        # Heating proportions
        heating_cols = [col for col in df.columns if col.startswith('heating_') and col.endswith('_pct')]
        df_with_heating = df[df['heating_total_buildings'] > 0].copy()
        if len(df_with_heating) > 0:
            df_with_heating['heating_sum'] = df_with_heating[heating_cols].sum(axis=1)
            within_range = ((df_with_heating['heating_sum'] >= 0.85) & 
                          (df_with_heating['heating_sum'] <= 1.05)).sum()
            pct_within_range = (within_range / len(df_with_heating)) * 100
            mean_sum = df_with_heating['heating_sum'].mean()
            logger.info(f"Heating:  {pct_within_range:.1f}% within 85-105% range, mean sum: {mean_sum:.2%}")
        
        # Energy proportions
        energy_cols = [col for col in df.columns if col.startswith('energy_') and col.endswith('_pct')]
        df_with_energy = df[df['energy_total_buildings'] > 0].copy()
        if len(df_with_energy) > 0:
            df_with_energy['energy_sum'] = df_with_energy[energy_cols].sum(axis=1)
            within_range = ((df_with_energy['energy_sum'] >= 0.85) & 
                          (df_with_energy['energy_sum'] <= 1.05)).sum()
            pct_within_range = (within_range / len(df_with_energy)) * 100
            mean_sum = df_with_energy['energy_sum'].mean()
            logger.info(f"Energy:   {pct_within_range:.1f}% within 85-105% range, mean sum: {mean_sum:.2%}")
        
        # Baujahr proportions
        baujahr_cols = [col for col in df.columns if col.startswith('baujahr_') and col.endswith('_pct')]
        df_with_baujahr = df[df['baujahr_total_buildings'] > 0].copy()
        if len(df_with_baujahr) > 0:
            df_with_baujahr['baujahr_sum'] = df_with_baujahr[baujahr_cols].sum(axis=1)
            within_range = ((df_with_baujahr['baujahr_sum'] >= 0.85) & 
                          (df_with_baujahr['baujahr_sum'] <= 1.05)).sum()
            pct_within_range = (within_range / len(df_with_baujahr)) * 100
            mean_sum = df_with_baujahr['baujahr_sum'].mean()
            logger.info(f"Baujahr:  {pct_within_range:.1f}% within 85-105% range, mean sum: {mean_sum:.2%}")
        
        # Check 3: Value ranges
        logger.info("\n3. VALUE RANGE CHECKS:")
        logger.info("-" * 40)
        
        # Rent should be positive
        if df['weighted_avg_rent_per_sqm'].notna().any():
            min_rent = df['weighted_avg_rent_per_sqm'].min()
            max_rent = df['weighted_avg_rent_per_sqm'].max()
            logger.info(f"Rent range: €{min_rent:.2f} - €{max_rent:.2f} per m²")
            if min_rent < 0:
                logger.warning(f"⚠️  Found {(df['weighted_avg_rent_per_sqm'] < 0).sum()} properties with negative rent")
        
        # Proportions should be 0-1 (or slightly above due to data quality)
        all_pct_cols = heating_cols + energy_cols + baujahr_cols
        for col in all_pct_cols:
            if df[col].notna().any():
                max_val = df[col].max()
                if max_val > 1.05:
                    count = (df[col] > 1.05).sum()
                    logger.warning(f"⚠️  {col}: {count} properties > 105% (max: {max_val:.2%})")
        
        # Check 4: Sample validation
        logger.info("\n4. SAMPLE PROPERTIES FOR MANUAL VERIFICATION:")
        logger.info("-" * 40)
        
        # Sample properties with different coverage patterns
        sample_ids = []
        
        # Property with all data
        all_data = df[
            (df['weighted_avg_rent_per_sqm'].notna()) &
            (df['heating_total_buildings'] > 0) &
            (df['energy_total_buildings'] > 0) &
            (df['baujahr_total_buildings'] > 0)
        ]
        if len(all_data) > 0:
            sample_ids.append(all_data.iloc[0]['property_id'])
            logger.info(f"✓ Property with full coverage: {all_data.iloc[0]['property_id']}")
        
        # Property with only rent data
        rent_only = df[
            (df['weighted_avg_rent_per_sqm'].notna()) &
            (df['heating_total_buildings'].isna() | (df['heating_total_buildings'] == 0))
        ]
        if len(rent_only) > 0:
            sample_ids.append(rent_only.iloc[0]['property_id'])
            logger.info(f"✓ Property with rent only: {rent_only.iloc[0]['property_id']}")
        
        # Property with no data
        no_data = df[
            (df['weighted_avg_rent_per_sqm'].isna()) &
            (df['heating_total_buildings'].isna() | (df['heating_total_buildings'] == 0))
        ]
        if len(no_data) > 0:
            sample_ids.append(no_data.iloc[0]['property_id'])
            logger.info(f"✓ Property with no coverage: {no_data.iloc[0]['property_id']}")
        
        logger.info("\n" + "="*80)
        logger.info("VALIDATION COMPLETE")
        logger.info("="*80)
        
        return True
    
    def export_to_csv(self, filename=None):
        """Export results to CSV file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            filename = f"lwu_weighted_stats_{timestamp}.csv"
        
        filepath = filename
        self.results_df.to_csv(filepath, index=False)
        logger.info(f"\n✓ Results exported to: {filepath}")
        logger.info(f"  Rows: {len(self.results_df):,}")
        logger.info(f"  Columns: {len(self.results_df.columns)}")
        
        return filepath
    
    def create_database_table(self):
        """Create the database table for storing results."""
        logger.info("Creating database table...")
        
        create_table_sql = """
        CREATE SCHEMA IF NOT EXISTS analytics;
        
        DROP TABLE IF EXISTS analytics.fact_lwu_weighted_stats;
        
        CREATE TABLE analytics.fact_lwu_weighted_stats (
            property_id TEXT PRIMARY KEY,
            
            -- Rent statistics
            weighted_avg_rent_per_sqm DOUBLE PRECISION,
            rent_total_flats DOUBLE PRECISION,
            
            -- Heating type proportions
            heating_fernheizung_pct DOUBLE PRECISION,
            heating_etagenheizung_pct DOUBLE PRECISION,
            heating_blockheizung_pct DOUBLE PRECISION,
            heating_zentralheizung_pct DOUBLE PRECISION,
            heating_einzel_mehrraumoefen_pct DOUBLE PRECISION,
            heating_keine_heizung_pct DOUBLE PRECISION,
            heating_total_buildings DOUBLE PRECISION,
            
            -- Energy source proportions
            energy_gas_pct DOUBLE PRECISION,
            energy_heizoel_pct DOUBLE PRECISION,
            energy_holz_holzpellets_pct DOUBLE PRECISION,
            energy_biomasse_biogas_pct DOUBLE PRECISION,
            energy_solar_geothermie_waermepumpen_pct DOUBLE PRECISION,
            energy_strom_pct DOUBLE PRECISION,
            energy_kohle_pct DOUBLE PRECISION,
            energy_fernwaerme_pct DOUBLE PRECISION,
            energy_kein_energietraeger_pct DOUBLE PRECISION,
            energy_total_buildings DOUBLE PRECISION,
            
            -- Construction year proportions
            baujahr_vor1919_pct DOUBLE PRECISION,
            baujahr_a1919bis1948_pct DOUBLE PRECISION,
            baujahr_a1949bis1978_pct DOUBLE PRECISION,
            baujahr_a1979bis1990_pct DOUBLE PRECISION,
            baujahr_a1991bis2000_pct DOUBLE PRECISION,
            baujahr_a2001bis2010_pct DOUBLE PRECISION,
            baujahr_a2011bis2019_pct DOUBLE PRECISION,
            baujahr_a2020undspaeter_pct DOUBLE PRECISION,
            baujahr_total_buildings DOUBLE PRECISION,
            
            -- Metadata
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            
            -- Foreign key
            FOREIGN KEY (property_id) REFERENCES zensus.ref_lwu_properties(property_id)
        );
        
        -- Create index on property_id
        CREATE INDEX idx_fact_lwu_weighted_stats_property_id 
            ON analytics.fact_lwu_weighted_stats(property_id);
        
        -- Add comments
        COMMENT ON TABLE analytics.fact_lwu_weighted_stats IS 
            'Weighted demographic statistics for LWU properties calculated from 100m grid intersections';
        """
        
        with self.engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        
        logger.info("✓ Table created: analytics.fact_lwu_weighted_stats")
    
    def insert_to_database(self):
        """Insert results into the database table."""
        logger.info("Inserting data into database...")
        
        # Ensure table exists
        self.create_database_table()
        
        # Insert data
        self.results_df.to_sql(
            'fact_lwu_weighted_stats',
            self.engine,
            schema='analytics',
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )
        
        logger.info(f"✓ Inserted {len(self.results_df):,} rows into analytics.fact_lwu_weighted_stats")


def main():
    """Main execution function."""
    calculator = LWUWeightedStatsCalculator(save_intermediates=True)
    
    # Calculate all statistics
    results = calculator.calculate_all_statistics()
    
    # Validate results
    calculator.validate_results()
    
    # Export to CSV for review
    csv_file = calculator.export_to_csv()
    
    print("\n" + "="*80)
    print("CALCULATION COMPLETE!")
    print("="*80)
    print(f"\n📊 Results exported to: {csv_file}")
    print(f"   Total properties: {len(results):,}")
    print(f"   Total columns: {len(results.columns)}")
    
    # List intermediate files saved
    if calculator.save_intermediates:
        print("\n💾 Intermediate dataframes saved:")
        print(f"   1. intermediate_spatial_intersections_{calculator.timestamp}.csv")
        print(f"   2. intermediate_rent_data_{calculator.timestamp}.csv")
        print(f"   3. intermediate_rent_merged_{calculator.timestamp}.csv")
        print(f"   4. intermediate_heating_data_{calculator.timestamp}.csv")
        print(f"   5. intermediate_heating_merged_{calculator.timestamp}.csv")
        print(f"   6. intermediate_energy_data_{calculator.timestamp}.csv")
        print(f"   7. intermediate_energy_merged_{calculator.timestamp}.csv")
        print(f"   8. intermediate_baujahr_data_{calculator.timestamp}.csv")
        print(f"   9. intermediate_baujahr_merged_{calculator.timestamp}.csv")
        print("\n   These files show the step-by-step calculations for inspection.")
    
    print("\n⚠️  Please review the CSV file before inserting into the database.")
    print("\nTo insert into database, run:")
    print("  calculator.insert_to_database()")
    print("\n" + "="*80)
    
    return calculator


if __name__ == "__main__":
    calculator = main()

