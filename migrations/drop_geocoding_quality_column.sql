-- Migration: Remove geocoding_quality column
-- Date: 2026-01-07
-- Reason: Simplify schema - quality scoring not needed for current use case

-- Drop the geocoding_quality column from housing.properties table
ALTER TABLE housing.properties 
DROP COLUMN IF EXISTS geocoding_quality;

-- Verify the column is dropped
\d housing.properties

