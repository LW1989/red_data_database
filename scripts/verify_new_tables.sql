-- Verification queries for VG250 and Bundestagswahlen tables
-- Run with: psql -U zensus_user -d zensus_db -f scripts/verify_new_tables.sql

\echo '===================='
\echo 'Table Structure Check'
\echo '===================='

-- List all new tables
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE schemaname = 'zensus' 
  AND tablename IN (
      'ref_federal_state',
      'ref_county',
      'ref_municipality',
      'ref_electoral_district',
      'fact_election_structural_data'
  )
ORDER BY tablename;

\echo ''
\echo '===================='
\echo 'Row Counts (Expected)'
\echo '===================='
\echo 'ref_federal_state: 34 (16 states + variants)'
\echo 'ref_county: 433'
\echo 'ref_municipality: 11,103'
\echo 'ref_electoral_district: 299 per year (2017, 2021, 2025)'
\echo 'fact_election_structural_data: 299 per year (2017, 2021, 2025)'
\echo ''

-- Check row counts
SELECT 'ref_federal_state' as table_name, COUNT(*) as row_count FROM zensus.ref_federal_state
UNION ALL
SELECT 'ref_county', COUNT(*) FROM zensus.ref_county
UNION ALL
SELECT 'ref_municipality', COUNT(*) FROM zensus.ref_municipality
UNION ALL
SELECT 'ref_electoral_district', COUNT(*) FROM zensus.ref_electoral_district
UNION ALL
SELECT 'fact_election_structural_data', COUNT(*) FROM zensus.fact_election_structural_data;

\echo ''
\echo '===================='
\echo 'Electoral Districts by Year'
\echo '===================='

SELECT 
    election_year,
    COUNT(*) as district_count,
    MIN(wahlkreis_nr) as min_wkr,
    MAX(wahlkreis_nr) as max_wkr
FROM zensus.ref_electoral_district
GROUP BY election_year
ORDER BY election_year;

\echo ''
\echo '===================='
\echo 'Structural Data by Year'
\echo '===================='

SELECT 
    election_year,
    COUNT(*) as record_count,
    COUNT(CASE WHEN bodenflaeche_siedlung_verkehr_pct IS NULL THEN 1 END) as null_land_use,
    COUNT(CASE WHEN pkw_elektro_hybrid_pct IS NULL THEN 1 END) as null_ev_pct
FROM zensus.fact_election_structural_data
GROUP BY election_year
ORDER BY election_year;

\echo ''
\echo 'Note: BTW2017 should have ~299 NULLs for columns not available in 2017'
\echo ''

\echo '===================='
\echo 'Geometry Validation'
\echo '===================='

-- Check for invalid geometries
SELECT 'ref_federal_state' as table_name, COUNT(*) as invalid_geoms 
FROM zensus.ref_federal_state WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT 'ref_county', COUNT(*) FROM zensus.ref_county WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT 'ref_municipality', COUNT(*) FROM zensus.ref_municipality WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT 'ref_electoral_district', COUNT(*) FROM zensus.ref_electoral_district WHERE NOT ST_IsValid(geom);

\echo ''
\echo '===================='
\echo 'SRID Validation'
\echo '===================='

-- Check SRIDs (all should be 3035)
SELECT 'ref_federal_state' as table_name, COUNT(*) as wrong_srid 
FROM zensus.ref_federal_state WHERE ST_SRID(geom) != 3035
UNION ALL
SELECT 'ref_county', COUNT(*) FROM zensus.ref_county WHERE ST_SRID(geom) != 3035
UNION ALL
SELECT 'ref_municipality', COUNT(*) FROM zensus.ref_municipality WHERE ST_SRID(geom) != 3035
UNION ALL
SELECT 'ref_electoral_district', COUNT(*) FROM zensus.ref_electoral_district WHERE ST_SRID(geom) != 3035;

\echo ''
\echo '===================='
\echo 'Sample Data - Federal States'
\echo '===================='

SELECT 
    ars,
    name,
    bez,
    nuts,
    ST_Area(geom) / 1000000 as area_km2
FROM zensus.ref_federal_state
ORDER BY ars
LIMIT 5;

\echo ''
\echo '===================='
\echo 'Sample Data - Counties (Top 5 by area)'
\echo '===================='

SELECT 
    ars,
    name,
    bez,
    land_name,
    ST_Area(geom) / 1000000 as area_km2
FROM zensus.ref_county
ORDER BY ST_Area(geom) DESC
LIMIT 5;

\echo ''
\echo '===================='
\echo 'Sample Data - Electoral Districts 2025'
\echo '===================='

SELECT 
    wahlkreis_nr,
    wahlkreis_name,
    land_name,
    ST_Area(geom) / 1000000 as area_km2
FROM zensus.ref_electoral_district
WHERE election_year = 2025
ORDER BY wahlkreis_nr
LIMIT 5;

\echo ''
\echo '===================='
\echo 'Sample Structural Data - BTW 2025'
\echo '===================='

SELECT 
    wahlkreis_nr,
    bevoelkerung_insgesamt_1000,
    bevoelkerungsdichte,
    arbeitslosenquote_insgesamt_pct,
    pkw_elektro_hybrid_pct
FROM zensus.fact_election_structural_data
WHERE election_year = 2025
ORDER BY wahlkreis_nr
LIMIT 5;

\echo ''
\echo '===================='
\echo 'Index Check'
\echo '===================='

-- List all indexes on new tables
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes 
WHERE schemaname = 'zensus' 
  AND tablename IN (
      'ref_federal_state',
      'ref_county',
      'ref_municipality',
      'ref_electoral_district',
      'fact_election_structural_data'
  )
ORDER BY tablename, indexname;

