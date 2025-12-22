-- LWU Berlin Properties Schema
-- Properties owned by state-owned housing companies (Landeseigene Wohnungsunternehmen)
-- in Berlin. All geometries in EPSG:3035 (ETRS89-LAEA) to match Zensus grid data.

CREATE TABLE IF NOT EXISTS zensus.ref_lwu_properties (
    property_id TEXT PRIMARY KEY,
    original_id TEXT NOT NULL,
    geom GEOMETRY(MULTIPOLYGON, 3035) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_lwu_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_lwu_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX IF NOT EXISTS idx_lwu_properties_geom 
    ON zensus.ref_lwu_properties USING GIST (geom);

COMMENT ON TABLE zensus.ref_lwu_properties IS 
    'Properties owned by Berlin state-owned housing companies (Landeseigene Wohnungsunternehmen)';
COMMENT ON COLUMN zensus.ref_lwu_properties.property_id IS 
    'Cleaned property identifier (format: lwu_fls.{number})';
COMMENT ON COLUMN zensus.ref_lwu_properties.original_id IS 
    'Original ID from source data including padding underscores';
COMMENT ON COLUMN zensus.ref_lwu_properties.geom IS 
    'Property parcel boundary as MultiPolygon in EPSG:3035';

