-- Data quality checks for Zensus database
-- Run these queries to verify data integrity

-- 1. Check for orphaned grid_ids in fact tables (grid_ids that don't exist in reference tables)
SELECT 
    'fact_zensus_1km_demography' AS table_name,
    COUNT(*) AS orphaned_count
FROM zensus.fact_zensus_1km_demography f
LEFT JOIN zensus.ref_grid_1km r ON f.grid_id = r.grid_id
WHERE r.grid_id IS NULL

UNION ALL

SELECT 
    'fact_zensus_10km_demography' AS table_name,
    COUNT(*) AS orphaned_count
FROM zensus.fact_zensus_10km_demography f
LEFT JOIN zensus.ref_grid_10km r ON f.grid_id = r.grid_id
WHERE r.grid_id IS NULL

UNION ALL

SELECT 
    'fact_zensus_1km_age_5klassen' AS table_name,
    COUNT(*) AS orphaned_count
FROM zensus.fact_zensus_1km_age_5klassen f
LEFT JOIN zensus.ref_grid_1km r ON f.grid_id = r.grid_id
WHERE r.grid_id IS NULL

UNION ALL

SELECT 
    'fact_zensus_10km_age_5klassen' AS table_name,
    COUNT(*) AS orphaned_count
FROM zensus.fact_zensus_10km_age_5klassen f
LEFT JOIN zensus.ref_grid_10km r ON f.grid_id = r.grid_id
WHERE r.grid_id IS NULL;

-- 2. Check for invalid geometries
SELECT 
    'ref_grid_1km' AS table_name,
    COUNT(*) AS invalid_geometries
FROM zensus.ref_grid_1km
WHERE NOT ST_IsValid(geom)

UNION ALL

SELECT 
    'ref_grid_10km' AS table_name,
    COUNT(*) AS invalid_geometries
FROM zensus.ref_grid_10km
WHERE NOT ST_IsValid(geom);

-- 3. Check for wrong SRID
SELECT 
    'ref_grid_1km' AS table_name,
    COUNT(*) AS wrong_srid
FROM zensus.ref_grid_1km
WHERE ST_SRID(geom) != 3035

UNION ALL

SELECT 
    'ref_grid_10km' AS table_name,
    COUNT(*) AS wrong_srid
FROM zensus.ref_grid_10km
WHERE ST_SRID(geom) != 3035;

-- 4. Check row counts
SELECT 
    'ref_grid_1km' AS table_name,
    COUNT(*) AS row_count
FROM zensus.ref_grid_1km

UNION ALL

SELECT 
    'ref_grid_10km' AS table_name,
    COUNT(*) AS row_count
FROM zensus.ref_grid_10km

UNION ALL

SELECT 
    'fact_zensus_1km_demography' AS table_name,
    COUNT(*) AS row_count
FROM zensus.fact_zensus_1km_demography

UNION ALL

SELECT 
    'fact_zensus_10km_demography' AS table_name,
    COUNT(*) AS row_count
FROM zensus.fact_zensus_10km_demography;

-- 5. Check for negative values in fact tables
SELECT 
    'fact_zensus_1km_demography' AS table_name,
    'einwohner' AS column_name,
    COUNT(*) AS negative_count
FROM zensus.fact_zensus_1km_demography
WHERE einwohner < 0

UNION ALL

SELECT 
    'fact_zensus_10km_demography' AS table_name,
    'einwohner' AS column_name,
    COUNT(*) AS negative_count
FROM zensus.fact_zensus_10km_demography
WHERE einwohner < 0;

