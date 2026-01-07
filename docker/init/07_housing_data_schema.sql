-- Housing data schema
-- Auto-generated from external database inspection
-- Source: housing_scraper_db.all_properties

-- Create housing schema
CREATE SCHEMA IF NOT EXISTS housing;

-- Properties table
CREATE TABLE IF NOT EXISTS housing.properties (
    internal_id TEXT NOT NULL,
    company TEXT NOT NULL,
    strasse_normalized TEXT,
    hausnummer TEXT,
    plz TEXT,
    ort TEXT,
    preis NUMERIC,
    groesse NUMERIC,
    anzahl_zimmer NUMERIC,
    eur_per_m2 NUMERIC,
    immo_type_scraped TEXT,
    date_scraped TIMESTAMP NOT NULL,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    -- Geocoding columns,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom GEOMETRY(POINT, 4326),
    geocoding_status TEXT,
    geocoded_address TEXT,
    -- Metadata columns,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_geocoded_at TIMESTAMP
,
    PRIMARY KEY (internal_id)

);

CREATE INDEX IF NOT EXISTS idx_properties_geom ON housing.properties USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_properties_geocoding_status ON housing.properties (geocoding_status);
CREATE INDEX IF NOT EXISTS idx_properties_internal_id ON housing.properties (internal_id);

-- Comments
COMMENT ON SCHEMA housing IS 'Housing property data synced from external scraper database';
COMMENT ON TABLE housing.properties IS 'Property listings with geocoded coordinates';
