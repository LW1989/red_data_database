#!/bin/bash
# Transform 100m grid data from temp table to final table

set -e

echo "=========================================="
echo "Transforming 100m Grid Data"
echo "=========================================="
echo ""

# Get DB connection details from environment
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-zensus_db}
DB_USER=${DB_USER:-zensus_user}
DB_PASSWORD=${DB_PASSWORD:-changeme}

echo "Checking temp table row count..."
TEMP_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM zensus.ref_grid_100m_temp;")
echo "Temp table has: $TEMP_COUNT rows"

if [ "$TEMP_COUNT" -eq 0 ]; then
    echo "❌ Error: Temp table is empty. Run ogr2ogr first."
    exit 1
fi

echo ""
echo "Starting transformation (this will take 10-20 minutes)..."
echo ""

PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME << 'EOF'
-- Insert with constructed grid_id from ogr2ogr temp table
INSERT INTO zensus.ref_grid_100m (grid_id, geom)
SELECT 
    'CRS3035RES100mN' || CAST(y_mp AS INTEGER) || 'E' || CAST(x_mp AS INTEGER) as grid_id,
    geom
FROM zensus.ref_grid_100m_temp
ON CONFLICT (grid_id) DO NOTHING;

-- Create spatial index
CREATE INDEX IF NOT EXISTS idx_grid_100m_geom 
    ON zensus.ref_grid_100m USING GIST (geom);

-- Show final count
SELECT COUNT(*) as total_rows FROM zensus.ref_grid_100m;
EOF

echo ""
echo "=========================================="
echo "Transformation Complete!"
echo "=========================================="
echo ""
echo "Cleaning up temp table..."

PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "DROP TABLE IF EXISTS zensus.ref_grid_100m_temp;"

echo "✅ Done! 100m grid is ready."

