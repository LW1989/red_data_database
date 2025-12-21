-- Create indexes for reference tables

-- GiST indexes on geometry columns (spatial queries)
CREATE INDEX IF NOT EXISTS idx_ref_grid_100m_geom ON zensus.ref_grid_100m USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_ref_grid_1km_geom ON zensus.ref_grid_1km USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_ref_grid_10km_geom ON zensus.ref_grid_10km USING GIST (geom);

-- B-tree indexes on grid_id (already covered by PRIMARY KEY, but explicit for clarity)
-- Primary keys automatically create indexes, so these are optional but documented

-- Create indexes for fact tables

-- B-tree indexes on grid_id (foreign keys)
-- Note: Primary keys already have indexes, but we add explicit ones for clarity
CREATE INDEX IF NOT EXISTS idx_fact_zensus_1km_demography_grid_id ON zensus.fact_zensus_1km_demography (grid_id);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_10km_demography_grid_id ON zensus.fact_zensus_10km_demography (grid_id);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_1km_age_5klassen_grid_id ON zensus.fact_zensus_1km_age_5klassen (grid_id);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_10km_age_5klassen_grid_id ON zensus.fact_zensus_10km_age_5klassen (grid_id);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_1km_durchschnittsalter_grid_id ON zensus.fact_zensus_1km_durchschnittsalter (grid_id);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_10km_durchschnittsalter_grid_id ON zensus.fact_zensus_10km_durchschnittsalter (grid_id);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_1km_miete_grid_id ON zensus.fact_zensus_1km_miete (grid_id);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_10km_miete_grid_id ON zensus.fact_zensus_10km_miete (grid_id);

-- B-tree indexes on year columns (for filtering)
CREATE INDEX IF NOT EXISTS idx_fact_zensus_1km_demography_year ON zensus.fact_zensus_1km_demography (year);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_10km_demography_year ON zensus.fact_zensus_10km_demography (year);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_1km_age_5klassen_year ON zensus.fact_zensus_1km_age_5klassen (year);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_10km_age_5klassen_year ON zensus.fact_zensus_10km_age_5klassen (year);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_1km_durchschnittsalter_year ON zensus.fact_zensus_1km_durchschnittsalter (year);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_10km_durchschnittsalter_year ON zensus.fact_zensus_10km_durchschnittsalter (year);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_1km_miete_year ON zensus.fact_zensus_1km_miete (year);
CREATE INDEX IF NOT EXISTS idx_fact_zensus_10km_miete_year ON zensus.fact_zensus_10km_miete (year);

-- Analyze tables for query optimization
ANALYZE zensus.ref_grid_100m;
ANALYZE zensus.ref_grid_1km;
ANALYZE zensus.ref_grid_10km;

-- Analyze all fact tables (dynamically created)
-- Note: With many fact tables, we analyze them all using a DO block
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'zensus' 
        AND tablename LIKE 'fact_zensus_%'
    LOOP
        EXECUTE 'ANALYZE zensus.' || quote_ident(r.tablename);
    END LOOP;
END $$;

