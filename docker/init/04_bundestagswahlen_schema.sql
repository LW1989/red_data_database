-- Bundestagswahlen (Federal Election) Schema
-- Contains electoral district boundaries and structural data for German federal elections
-- All geometries in EPSG:3035 (ETRS89-LAEA) to match Zensus grid data

-- Electoral Districts (Wahlkreise)
-- Stores boundaries for multiple election years (2017, 2021, 2025)
CREATE TABLE IF NOT EXISTS zensus.ref_electoral_district (
    wahlkreis_nr INTEGER NOT NULL,
    wahlkreis_name TEXT NOT NULL,
    land_nr TEXT NOT NULL,
    land_name TEXT NOT NULL,
    election_year INTEGER NOT NULL,
    geom GEOMETRY(MULTIPOLYGON, 3035) NOT NULL,
    CONSTRAINT pk_electoral_district PRIMARY KEY (wahlkreis_nr, election_year),
    CONSTRAINT chk_wahlkreis_nr CHECK (wahlkreis_nr BETWEEN 1 AND 299),
    CONSTRAINT chk_election_year CHECK (election_year IN (2017, 2021, 2025)),
    CONSTRAINT chk_electoral_district_valid CHECK (ST_IsValid(geom)),
    CONSTRAINT chk_electoral_district_srid CHECK (ST_SRID(geom) = 3035)
);

CREATE INDEX IF NOT EXISTS idx_electoral_district_geom ON zensus.ref_electoral_district USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_electoral_district_wkr_nr ON zensus.ref_electoral_district (wahlkreis_nr);
CREATE INDEX IF NOT EXISTS idx_electoral_district_year ON zensus.ref_electoral_district (election_year);
CREATE INDEX IF NOT EXISTS idx_electoral_district_land_nr ON zensus.ref_electoral_district (land_nr);

COMMENT ON TABLE zensus.ref_electoral_district IS 'Electoral district boundaries for German federal elections (Bundestagswahlen)';
COMMENT ON COLUMN zensus.ref_electoral_district.wahlkreis_nr IS 'Electoral district number (1-299)';
COMMENT ON COLUMN zensus.ref_electoral_district.election_year IS 'Election year (2017, 2021, or 2025)';
COMMENT ON COLUMN zensus.ref_electoral_district.land_nr IS 'State number (Bundesland)';


-- Election Structural Data
-- Socioeconomic and demographic indicators per electoral district
-- Unified schema based on BTW2021/2025 structure with 52 columns
-- BTW2017 data is mapped to this schema (45/52 columns, 7 will be NULL)
CREATE TABLE IF NOT EXISTS zensus.fact_election_structural_data (
    wahlkreis_nr INTEGER NOT NULL,
    election_year INTEGER NOT NULL,
    
    -- Administrative
    gemeinden_anzahl INTEGER,
    flaeche_km2 NUMERIC,
    
    -- Demographics (reference dates differ by election)
    bevoelkerung_insgesamt_1000 NUMERIC,
    bevoelkerung_deutsche_1000 NUMERIC,
    bevoelkerung_auslaender_pct NUMERIC,
    bevoelkerungsdichte NUMERIC,
    bevoelkerung_geburten_saldo_je_1000ew NUMERIC,
    bevoelkerung_wanderung_saldo_je_1000ew NUMERIC,
    
    -- Age Structure
    alter_unter_18_pct NUMERIC,
    alter_18_24_pct NUMERIC,
    alter_25_34_pct NUMERIC,
    alter_35_59_pct NUMERIC,
    alter_60_74_pct NUMERIC,
    alter_75_plus_pct NUMERIC,
    
    -- Land Use (NULL for BTW2017)
    bodenflaeche_siedlung_verkehr_pct NUMERIC,
    bodenflaeche_vegetation_gewaesser_pct NUMERIC,
    
    -- Housing
    wohnungen_fertiggestellt_je_1000ew NUMERIC,
    wohnungen_bestand_je_1000ew NUMERIC,
    wohnflaeche_je_wohnung NUMERIC,  -- NULL for BTW2017
    wohnflaeche_je_ew NUMERIC,  -- NULL for BTW2017
    
    -- Transportation
    pkw_bestand_je_1000ew NUMERIC,
    pkw_elektro_hybrid_pct NUMERIC,  -- NULL for BTW2017
    
    -- Economy
    unternehmen_insgesamt_je_1000ew NUMERIC,
    unternehmen_handwerk_je_1000ew NUMERIC,
    einkommen_verfuegbar_eur_je_ew NUMERIC,
    bip_eur_je_ew NUMERIC,
    
    -- Education
    schulabgaenger_berufliche_schulen INTEGER,
    schulabgaenger_allgemeinbildend_je_1000ew NUMERIC,
    schulabgaenger_ohne_hauptschulabschluss_pct NUMERIC,
    schulabgaenger_hauptschulabschluss_pct NUMERIC,
    schulabgaenger_mittlerer_abschluss_pct NUMERIC,
    schulabgaenger_abitur_pct NUMERIC,
    kindertagesbetreuung_unter_3_pct NUMERIC,  -- NULL for BTW2017
    kindertagesbetreuung_3_6_pct NUMERIC,  -- NULL for BTW2017
    
    -- Employment
    beschaeftigte_insgesamt_je_1000ew NUMERIC,
    beschaeftigte_landwirtschaft_pct NUMERIC,
    beschaeftigte_produzierendes_gewerbe_pct NUMERIC,
    beschaeftigte_handel_gastgewerbe_verkehr_pct NUMERIC,
    beschaeftigte_oeffentliche_dienstleister_pct NUMERIC,
    beschaeftigte_uebrige_dienstleister_pct NUMERIC,
    sgb2_leistungsempfaenger_je_1000ew NUMERIC,
    sgb2_nicht_erwerbsfaehig_pct NUMERIC,
    sgb2_auslaender_pct NUMERIC,
    arbeitslosenquote_insgesamt_pct NUMERIC,
    arbeitslosenquote_maenner_pct NUMERIC,
    arbeitslosenquote_frauen_pct NUMERIC,
    arbeitslosenquote_15_24_pct NUMERIC,
    arbeitslosenquote_55_64_pct NUMERIC,
    
    -- Metadata
    fussnoten TEXT,  -- Footnotes column (may contain additional notes)
    
    CONSTRAINT pk_election_structural_data PRIMARY KEY (wahlkreis_nr, election_year),
    CONSTRAINT fk_election_structural_data_district 
        FOREIGN KEY (wahlkreis_nr, election_year) 
        REFERENCES zensus.ref_electoral_district(wahlkreis_nr, election_year),
    CONSTRAINT chk_wahlkreis_nr_range CHECK (wahlkreis_nr BETWEEN 1 AND 299),
    CONSTRAINT chk_structural_election_year CHECK (election_year IN (2017, 2021, 2025))
);

CREATE INDEX IF NOT EXISTS idx_election_structural_data_wkr_nr ON zensus.fact_election_structural_data (wahlkreis_nr);
CREATE INDEX IF NOT EXISTS idx_election_structural_data_year ON zensus.fact_election_structural_data (election_year);

COMMENT ON TABLE zensus.fact_election_structural_data IS 'Socioeconomic and demographic indicators per electoral district';
COMMENT ON COLUMN zensus.fact_election_structural_data.election_year IS 'Election year - critical for distinguishing between elections and handling NULLs';
COMMENT ON COLUMN zensus.fact_election_structural_data.bodenflaeche_siedlung_verkehr_pct IS 'Land use: Settlement and traffic (NULL for 2017)';
COMMENT ON COLUMN zensus.fact_election_structural_data.wohnflaeche_je_wohnung IS 'Living area per dwelling (NULL for 2017)';
COMMENT ON COLUMN zensus.fact_election_structural_data.pkw_elektro_hybrid_pct IS 'Electric/hybrid vehicles percentage (NULL for 2017)';
COMMENT ON COLUMN zensus.fact_election_structural_data.kindertagesbetreuung_unter_3_pct IS 'Childcare under 3 years (NULL for 2017)';

