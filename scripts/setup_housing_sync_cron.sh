#!/bin/bash
# Setup cron job for daily housing data sync
# This script configures a cron job to run the sync at 5:00 AM daily

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================================================"
echo "Housing Data Sync - Cron Job Setup"
echo "================================================================================"
echo ""

# Get the project root directory (parent of scripts directory)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Project root: $PROJECT_ROOT"
echo ""

# Check if virtual environment exists
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${RED}✗ Virtual environment not found at $PROJECT_ROOT/venv${NC}"
    echo "  Please create a virtual environment first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

echo -e "${GREEN}✓ Virtual environment found${NC}"

# Check if sync script exists
if [ ! -f "$PROJECT_ROOT/etl/sync_housing_data.py" ]; then
    echo -e "${RED}✗ Sync script not found at $PROJECT_ROOT/etl/sync_housing_data.py${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Sync script found${NC}"
echo ""

# Create log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✓ Log directory created/verified: $LOG_DIR${NC}"

# Create the cron job command
CRON_COMMAND="0 5 * * * cd $PROJECT_ROOT && $PROJECT_ROOT/venv/bin/python $PROJECT_ROOT/etl/sync_housing_data.py >> $LOG_DIR/housing_sync.log 2>&1"

echo ""
echo "================================================================================"
echo "Cron Job Configuration"
echo "================================================================================"
echo "Schedule: Daily at 5:00 AM"
echo "Script: $PROJECT_ROOT/etl/sync_housing_data.py"
echo "Log file: $LOG_DIR/housing_sync.log"
echo ""
echo "Cron entry:"
echo "$CRON_COMMAND"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "sync_housing_data.py"; then
    echo -e "${YELLOW}⚠ Cron job already exists for housing sync${NC}"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep "sync_housing_data.py"
    echo ""
    read -p "Do you want to replace it? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
    
    # Remove old cron job
    crontab -l | grep -v "sync_housing_data.py" | crontab -
    echo -e "${GREEN}✓ Old cron job removed${NC}"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_COMMAND") | crontab -

echo -e "${GREEN}✓ Cron job installed successfully!${NC}"
echo ""

# Verify installation
echo "================================================================================"
echo "Verification"
echo "================================================================================"
echo "Current cron jobs related to housing sync:"
crontab -l | grep "sync_housing_data.py" || echo "None found"
echo ""

# Create a manual run script
MANUAL_SCRIPT="$PROJECT_ROOT/scripts/run_housing_sync.sh"
cat > "$MANUAL_SCRIPT" << 'MANUAL_EOF'
#!/bin/bash
# Manual run script for housing data sync

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "================================================================================"
echo "Housing Data Sync - Manual Run"
echo "================================================================================"
echo ""

cd "$PROJECT_ROOT"
source venv/bin/activate

python etl/sync_housing_data.py "$@"

echo ""
echo "✓ Sync complete"
MANUAL_EOF

chmod +x "$MANUAL_SCRIPT"

echo -e "${GREEN}✓ Manual run script created: $MANUAL_SCRIPT${NC}"
echo ""

# Create a test script
TEST_SCRIPT="$PROJECT_ROOT/scripts/run_housing_sync_test.sh"
cat > "$TEST_SCRIPT" << 'TEST_EOF'
#!/bin/bash
# Test run script for housing data sync (small dataset)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "================================================================================"
echo "Housing Data Sync - Test Run (10 records)"
echo "================================================================================"
echo ""

cd "$PROJECT_ROOT"
source venv/bin/activate

python etl/sync_housing_data.py --limit 10 --geocode-limit 10

echo ""
echo "✓ Test sync complete"
TEST_EOF

chmod +x "$TEST_SCRIPT"

echo -e "${GREEN}✓ Test run script created: $TEST_SCRIPT${NC}"
echo ""

echo "================================================================================"
echo "Next Steps"
echo "================================================================================"
echo ""
echo "1. Test the sync manually:"
echo "   $MANUAL_SCRIPT --limit 10 --geocode-limit 10"
echo ""
echo "2. Or use the test script:"
echo "   $TEST_SCRIPT"
echo ""
echo "3. Check the logs:"
echo "   tail -f $LOG_DIR/housing_sync.log"
echo ""
echo "4. View cron jobs:"
echo "   crontab -l"
echo ""
echo "5. Remove cron job (if needed):"
echo "   crontab -e"
echo "   (then delete the line with 'sync_housing_data.py')"
echo ""
echo "6. Run quality checks after sync:"
echo "   psql -h dokploy.red-data.eu -p 54321 -U zensus_user -d red-data-db -f tests/sql/housing_quality_checks.sql"
echo ""
echo "================================================================================"
echo -e "${GREEN}✓ Setup complete!${NC}"
echo "================================================================================"

