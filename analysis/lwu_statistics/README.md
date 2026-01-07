# LWU Statistics Analysis

This folder contains scripts and documentation for calculating weighted demographic statistics for LWU (Landeseigene Wohnungen) properties in Berlin.

## Files

- **`calculate_lwu_weighted_stats.py`** - Main calculation script
- **`insert_lwu_weighted_stats_to_db.py`** - Database insertion tool
- **`LWU_STATISTICS_GUIDE.md`** - Complete documentation and usage guide

## Quick Start

```bash
# Calculate statistics
python analysis/lwu_statistics/calculate_lwu_weighted_stats.py

# Insert into database
python analysis/lwu_statistics/insert_lwu_weighted_stats_to_db.py lwu_weighted_stats_YYYY-MM-DD.csv
```

See `LWU_STATISTICS_GUIDE.md` for detailed documentation.

