-- LWU Weighted Statistics Table and View
-- This table stores weighted demographic statistics for LWU (Landeseigene Wohnungen) properties
-- calculated from intersections with 100m zensus grid cells

-- Create analytics schema for derived data
CREATE SCHEMA IF NOT EXISTS analytics;

DROP TABLE IF EXISTS analytics.fact_lwu_weighted_stats;

CREATE TABLE analytics.fact_lwu_weighted_stats (
    property_id TEXT PRIMARY KEY,
    
    -- Rent statistics
    weighted_avg_rent_per_sqm DOUBLE PRECISION,
    rent_total_flats DOUBLE PRECISION,
    
    -- Heating type proportions (Heizungsart)
    heating_fernheizung_pct DOUBLE PRECISION,
    heating_etagenheizung_pct DOUBLE PRECISION,
    heating_blockheizung_pct DOUBLE PRECISION,
    heating_zentralheizung_pct DOUBLE PRECISION,
    heating_einzel_mehrraumoefen_pct DOUBLE PRECISION,
    heating_keine_heizung_pct DOUBLE PRECISION,
    heating_total_buildings DOUBLE PRECISION,
    
    -- Energy source proportions (Energieträger)
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
    
    -- Construction year proportions (Baujahr)
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

-- Add table comment
COMMENT ON TABLE analytics.fact_lwu_weighted_stats IS 
    'Weighted demographic statistics for LWU properties calculated from 100m grid intersections. '
    'Statistics include average rent, heating types, energy sources, and construction years. '
    'Weights are based on overlap ratios and relevant counts (flats/buildings).';

-- Add column comments
COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.property_id IS 
    'LWU property identifier';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.weighted_avg_rent_per_sqm IS 
    'Weighted average rent per square meter (€/m²)';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.rent_total_flats IS 
    'Total weighted flats used for rent calculation';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.heating_fernheizung_pct IS 
    'Proportion of district heating (Fernheizung)';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.heating_total_buildings IS 
    'Total weighted buildings used for heating calculation';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.energy_gas_pct IS 
    'Proportion of gas as energy source';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.energy_total_buildings IS 
    'Total weighted buildings used for energy calculation';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.baujahr_vor1919_pct IS 
    'Proportion of buildings constructed before 1919';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.baujahr_total_buildings IS 
    'Total weighted buildings used for construction year calculation';

COMMENT ON COLUMN zensus.fact_lwu_weighted_stats.created_at IS 
    'Timestamp when the statistics were calculated';

