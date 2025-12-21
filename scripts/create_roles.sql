-- Create non-superuser database roles for application access
-- Run this script as a PostgreSQL superuser (e.g., postgres user)

-- Application role with read/write access to zensus schema
CREATE ROLE zensus_app WITH
    LOGIN
    PASSWORD 'changeme_app_password';  -- CHANGE THIS PASSWORD!

-- Grant usage on schema
GRANT USAGE ON SCHEMA zensus TO zensus_app;

-- Grant privileges on all tables in zensus schema
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA zensus TO zensus_app;

-- Grant privileges on all sequences (for future use)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA zensus TO zensus_app;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA zensus
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zensus_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA zensus
    GRANT USAGE, SELECT ON SEQUENCES TO zensus_app;

-- Read-only role for reporting/analytics
CREATE ROLE zensus_readonly WITH
    LOGIN
    PASSWORD 'changeme_readonly_password';  -- CHANGE THIS PASSWORD!

-- Grant usage on schema
GRANT USAGE ON SCHEMA zensus TO zensus_readonly;

-- Grant SELECT only on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA zensus TO zensus_readonly;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA zensus
    GRANT SELECT ON TABLES TO zensus_readonly;

-- Optional: Create a role for ETL operations (if needed separately)
-- CREATE ROLE zensus_etl WITH
--     LOGIN
--     PASSWORD 'changeme_etl_password';  -- CHANGE THIS PASSWORD!
--
-- GRANT USAGE ON SCHEMA zensus TO zensus_etl;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA zensus TO zensus_etl;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA zensus
--     GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zensus_etl;

-- Verify roles were created
SELECT 
    rolname,
    rolcanlogin,
    rolsuper
FROM pg_roles
WHERE rolname LIKE 'zensus_%'
ORDER BY rolname;

