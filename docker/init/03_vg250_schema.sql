-- VG250 Administrative Boundaries Schema
-- Contains German administrative boundaries from BKG (Bundesamt für Kartographie und Geodäsie)
-- All geometries in EPSG:3035 (ETRS89-LAEA) to match Zensus grid data

-- Federal States (Bundesländer)
CREATE TABLE IF NOT EXISTS zensus.ref_federal_state (
    ars TEXT PRIMARY KEY,  -- 2-digit Official Regional Key (e.g., "01")
    ags TEXT NOT NULL,     -- Same as ARS for states
    name TEXT NOT NULL,    -- State name (GEN) - e.g., "Schleswig-Holstein"
    bez TEXT,              -- Type (BEZ) - e.g., "Land", "Freistaat"
    nuts TEXT,             -- NUTS code (e.g., "DEF")
    land_nr TEXT NOT NULL, -- State number (same as first 2 digits of ARS)
    beginn DATE,           -- Validity start date
    geom GEOMETRY(MULTIPOLYGON, 3035) NOT NULL,
    CONSTRAINT chk_federal_state_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_federal_state_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX IF NOT EXISTS idx_federal_state_geom ON zensus.ref_federal_state USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_federal_state_ags ON zensus.ref_federal_state (ags);
CREATE INDEX IF NOT EXISTS idx_federal_state_nuts ON zensus.ref_federal_state (nuts);

COMMENT ON TABLE zensus.ref_federal_state IS 'German federal states (Bundesländer) from VG250 dataset';
COMMENT ON COLUMN zensus.ref_federal_state.ars IS 'Amtlicher Regionalschlüssel (Official Regional Key) - 2 digits';
COMMENT ON COLUMN zensus.ref_federal_state.ags IS 'Amtlicher Gemeindeschlüssel (Official Municipality Key)';
COMMENT ON COLUMN zensus.ref_federal_state.name IS 'Official name of the federal state';
COMMENT ON COLUMN zensus.ref_federal_state.bez IS 'Type designation (e.g., Land, Freistaat)';
COMMENT ON COLUMN zensus.ref_federal_state.nuts IS 'NUTS code for European statistical regions';


-- Counties (Landkreise und kreisfreie Städte)
CREATE TABLE IF NOT EXISTS zensus.ref_county (
    ars TEXT PRIMARY KEY,  -- 5-digit Official Regional Key (e.g., "01001")
    ags TEXT NOT NULL,     -- Same as ARS for counties
    name TEXT NOT NULL,    -- County name (GEN)
    bez TEXT,              -- Type (BEZ) - e.g., "Kreisfreie Stadt", "Landkreis"
    land_nr TEXT NOT NULL, -- State number (first 2 digits of ARS)
    land_name TEXT NOT NULL, -- State name
    nuts TEXT,             -- NUTS code
    beginn DATE,           -- Validity start date
    geom GEOMETRY(GEOMETRY, 3035) NOT NULL,  -- Accepts both Polygon and MultiPolygon (for coastal counties with islands)
    CONSTRAINT chk_county_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_county_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX IF NOT EXISTS idx_county_geom ON zensus.ref_county USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_county_ags ON zensus.ref_county (ags);
CREATE INDEX IF NOT EXISTS idx_county_land_nr ON zensus.ref_county (land_nr);
CREATE INDEX IF NOT EXISTS idx_county_nuts ON zensus.ref_county (nuts);

COMMENT ON TABLE zensus.ref_county IS 'German counties (Kreise and kreisfreie Städte) from VG250 dataset';
COMMENT ON COLUMN zensus.ref_county.ars IS 'Amtlicher Regionalschlüssel - 5 digits';
COMMENT ON COLUMN zensus.ref_county.bez IS 'Type (Kreisfreie Stadt, Landkreis, Stadtkreis)';


-- Municipalities (Gemeinden)
CREATE TABLE IF NOT EXISTS zensus.ref_municipality (
    ars TEXT PRIMARY KEY,  -- 12-digit Official Regional Key
    ags TEXT NOT NULL,     -- 8-digit Official Municipality Key
    name TEXT NOT NULL,    -- Municipality name (GEN)
    bez TEXT,              -- Type/Designation (BEZ) - e.g., "Stadt", "Gemeinde"
    land_nr TEXT NOT NULL, -- State number (first 2 digits of ARS)
    land_name TEXT NOT NULL, -- State name
    nuts TEXT,             -- NUTS code
    beginn DATE,           -- Validity start date
    geom GEOMETRY(GEOMETRY, 3035) NOT NULL,  -- Accepts both Polygon and MultiPolygon (for island municipalities)
    CONSTRAINT chk_municipality_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_municipality_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX IF NOT EXISTS idx_municipality_geom ON zensus.ref_municipality USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_municipality_ags ON zensus.ref_municipality (ags);
CREATE INDEX IF NOT EXISTS idx_municipality_land_nr ON zensus.ref_municipality (land_nr);
CREATE INDEX IF NOT EXISTS idx_municipality_nuts ON zensus.ref_municipality (nuts);

COMMENT ON TABLE zensus.ref_municipality IS 'German municipalities (Gemeinden) from VG250 dataset - smallest administrative unit';
COMMENT ON COLUMN zensus.ref_municipality.ars IS 'Amtlicher Regionalschlüssel - 12 digits (full hierarchical code)';
COMMENT ON COLUMN zensus.ref_municipality.ags IS 'Amtlicher Gemeindeschlüssel - 8 digits';
COMMENT ON COLUMN zensus.ref_municipality.bez IS 'Type (Stadt, Gemeinde, etc.)';

