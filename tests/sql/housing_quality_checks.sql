-- Quality checks for housing data
-- Run these checks after syncing to verify data quality

-- Check 1: Total record count
SELECT 
    'Total Properties' as check_name,
    COUNT(*) as count
FROM housing.properties;

-- Check 2: Geocoding success rate
SELECT 
    'Geocoding Status' as check_name,
    geocoding_status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM housing.properties
GROUP BY geocoding_status
ORDER BY count DESC;

-- Check 3: Properties with missing address components
SELECT 
    'Missing Address Components' as check_name,
    COUNT(*) as count
FROM housing.properties
WHERE (strasse_normalized IS NULL OR strasse_normalized = '')
   OR (plz IS NULL OR plz = '')
   OR (ort IS NULL OR ort = '');

-- Check 4: Properties with coordinates
SELECT 
    'With Coordinates' as check_name,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM housing.properties), 2) as percentage
FROM housing.properties
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Check 5: Properties with PostGIS geometry
SELECT 
    'With PostGIS Geometry' as check_name,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM housing.properties), 2) as percentage
FROM housing.properties
WHERE geom IS NOT NULL;

-- Check 6: Coordinate bounds check (Germany approx: lat 47-55, lon 6-15)
SELECT 
    'Out of Germany Bounds' as check_name,
    COUNT(*) as count
FROM housing.properties
WHERE latitude IS NOT NULL 
  AND longitude IS NOT NULL
  AND (latitude < 47 OR latitude > 55 OR longitude < 6 OR longitude > 15);

-- Check 7: Properties by company
SELECT 
    'Properties by Company' as check_name,
    company,
    COUNT(*) as count
FROM housing.properties
GROUP BY company
ORDER BY count DESC;

-- Check 8: Recent sync statistics (last 24 hours)
SELECT 
    'Synced in Last 24 Hours' as check_name,
    COUNT(*) as count
FROM housing.properties
WHERE synced_at >= NOW() - INTERVAL '24 hours';

-- Check 9: Geocoding quality distribution
SELECT 
    'Geocoding Quality' as check_name,
    CASE 
        WHEN geocoding_quality >= 0.8 THEN 'High (0.8-1.0)'
        WHEN geocoding_quality >= 0.5 THEN 'Medium (0.5-0.8)'
        WHEN geocoding_quality >= 0.2 THEN 'Low (0.2-0.5)'
        ELSE 'Very Low (<0.2)'
    END as quality_range,
    COUNT(*) as count
FROM housing.properties
WHERE geocoding_quality IS NOT NULL
GROUP BY quality_range
ORDER BY MIN(geocoding_quality) DESC;

-- Check 10: Duplicate properties (same address)
SELECT 
    'Potential Duplicates' as check_name,
    strasse_normalized,
    hausnummer,
    plz,
    ort,
    COUNT(*) as count
FROM housing.properties
GROUP BY strasse_normalized, hausnummer, plz, ort
HAVING COUNT(*) > 1
ORDER BY count DESC
LIMIT 10;

-- Check 11: Properties with missing prices
SELECT 
    'Missing Price Data' as check_name,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM housing.properties), 2) as percentage
FROM housing.properties
WHERE preis IS NULL OR preis = 0;

-- Check 12: Average property statistics
SELECT 
    'Average Property Stats' as check_name,
    ROUND(AVG(preis), 2) as avg_preis,
    ROUND(AVG(groesse), 2) as avg_groesse,
    ROUND(AVG(anzahl_zimmer), 2) as avg_zimmer,
    ROUND(AVG(eur_per_m2), 2) as avg_eur_per_m2
FROM housing.properties
WHERE preis > 0 AND groesse > 0;

-- Check 13: Data freshness
SELECT 
    'Data Freshness' as check_name,
    MIN(date_scraped) as oldest_scraped,
    MAX(date_scraped) as newest_scraped,
    MAX(synced_at) as last_sync
FROM housing.properties;

-- Check 14: Failed geocoding samples (for review)
SELECT 
    'Failed Geocoding Samples' as check_name,
    internal_id,
    strasse_normalized,
    hausnummer,
    plz,
    ort,
    geocoded_address as error_message
FROM housing.properties
WHERE geocoding_status = 'failed'
LIMIT 5;

-- Check 15: Geocoding cache statistics
SELECT 
    'Geocoding Cache Stats' as check_name,
    COUNT(*) as total_cached,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_cached,
    SUM(hit_count) as total_cache_hits,
    ROUND(AVG(hit_count), 2) as avg_hits_per_address
FROM housing.geocoding_cache;

