# Bundestagswahlen CSV Files - Detailed Analysis

## Executive Summary

The Bundestagswahlen structural data CSV files are **poorly designed** and have **inconsistent structures** across different election years. They require special parsing logic that:

1. Handles variable numbers of comment rows
2. Extracts column names from the first data row (not a proper header)
3. Deals with encoding issues (BTW2013)
4. Handles date-specific column names that differ between elections
5. Processes German number formats (comma decimals, dot thousands separators)

## File Structure Issues

### Common Problems Across All Files

1. **No proper header row**: Column names are in the first data row, not a separate header
2. **Variable comment rows**: Different number of comment/metadata rows between elections
3. **German number format**: Uses commas for decimals (`2.124,3` = 2124.3)
4. **Long column names**: Some columns have very long descriptive names
5. **Date-specific columns**: Column names contain dates (e.g., "am 31.12.2023") that differ between elections

### Election-Specific Issues

#### BTW2013 (2013 Election)
- **Encoding**: ISO-8859-1 (Latin-1) - **readable with correct encoding**
- **Structure**: Significantly different from later elections
- **Comment rows**: 4 rows (lines 1-4)
- **Header row**: Line 5 (contains "Land", "Wahlkreis-Nr.", "Wahlkreis-Name")
- **Column number row**: Line 6 (contains "1", "2", "3"... - **must be skipped**)
- **Data start**: Line 7
- **Reference dates**: 2011/2012 (e.g., "am 31.12.2011", "am 30.09.2012")
- **Total columns**: 43 (vs 52 in later elections)
- **Status**: **Readable but requires special handling** due to:
  - Different encoding (ISO-8859-1)
  - Different column structure (43 vs 52 columns)
  - Different column names and categories
  - Extra row with column numbers that must be skipped

#### BTW2021 (2021 Election)
- **Encoding**: UTF-8 with BOM
- **Comment rows**: 8 rows (lines 1-8)
- **Header row**: Line 9 (contains "Land", "Wahlkreis-Nr.", "Wahlkreis-Name")
- **Data start**: Line 10
- **Reference dates**: 2019 (e.g., "am 31.12.2019")
- **Total columns**: 52

#### BTW2025 (2025 Election)
- **Encoding**: UTF-8 with BOM
- **Comment rows**: 9 rows (lines 1-9)
- **Header row**: Line 10 (contains "Land", "Wahlkreis-Nr.", "Wahlkreis-Name")
- **Data start**: Line 11
- **Reference dates**: 2023 (e.g., "am 31.12.2023")
- **Total columns**: 52

## Detailed File Structure

### BTW2021 Structure

```
Line 1: # © Der Bundeswahlleiter, Wiesbaden 2021
Line 2: # Quelle der Rohdaten der Spalten 35 bis 48: © Bundesagentur für Arbeit
Line 3: # (empty comment)
Line 4: # Strukturdaten für die Wahlkreise zum 20. Deutschen Bundestag...
Line 5: # (empty comment)
Line 6: # Zeichensatz: UTF-8 mit BOM. Trennzeichen: Semikolon.
Line 7: # (empty comment)
Line 8: Spalten-Nr.;;;1;2;3;4;5;... (column numbers)
Line 9: Land;Wahlkreis-Nr.;Wahlkreis-Name;... (COLUMN NAMES - first data row)
Line 10: Schleswig-Holstein;001;Flensburg – Schleswig;... (ACTUAL DATA)
```

### BTW2025 Structure

```
Line 1: # © Die Bundeswahlleiterin, Wiesbaden 2025
Line 2: # Datenlizenz Deutschland – Namensnennung – Version 2.0...
Line 3: # Quelle der Rohdaten der Spalten 35 bis 48: © Bundesagentur für Arbeit
Line 4: # (empty comment)
Line 5: # Strukturdaten für die Wahlkreise zum 21. Deutschen Bundestag...
Line 6: # (empty comment)
Line 7: # Zeichensatz: UTF-8 mit BOM. Trennzeichen: Semikolon.
Line 8: # (empty comment)
Line 9: Spalten-Nr.;;;1;2;3;4;5;... (column numbers)
Line 10: Land;Wahlkreis-Nr.;Wahlkreis-Name;... (COLUMN NAMES - first data row)
Line 11: Schleswig-Holstein;1;Flensburg – Schleswig;... (ACTUAL DATA)
```

## Column Structure

### Standard Columns (All Elections)

1. **Land** - State name (e.g., "Schleswig-Holstein")
2. **Wahlkreis-Nr.** - Electoral district number (1-299, may be zero-padded)
3. **Wahlkreis-Name** - Electoral district name

### Data Columns (52 total, date-specific)

Columns 4-52 contain socioeconomic data. Column names include reference dates that differ between elections:

**BTW2021 examples**:
- `Gemeinden am 31.12.2019 (Anzahl)`
- `Fläche am 31.12.2019 (km²)`
- `Bevölkerung am 31.12.2019 - Insgesamt (in 1000)`

**BTW2025 examples**:
- `Gemeinden am 31.12.2023 (Anzahl)`
- `Fläche am 31.12.2023 (km²)`
- `Bevölkerung am 31.12.2023 - Insgesamt (in 1000)`

### Column Categories

1. **Administrative** (columns 4-5)
   - Number of municipalities
   - Area in km²

2. **Demographics** (columns 6-11)
   - Total population
   - German population
   - Foreign population percentage
   - Population density
   - Birth rate
   - Migration rate

3. **Age Structure** (columns 12-17)
   - Age groups: under 18, 18-24, 25-34, 35-59, 60-74, 75+

4. **Land Use** (columns 18-19)
   - Settlement and traffic
   - Vegetation and water

5. **Housing** (columns 20-23)
   - Completed housing units
   - Housing stock
   - Living space per unit
   - Living space per person

6. **Transportation** (columns 24-25)
   - Car ownership
   - Electric/hybrid cars

7. **Economy** (columns 26-29)
   - Companies
   - Craft businesses
   - Disposable income
   - GDP per capita

8. **Education** (columns 30-37)
   - School graduates
   - Education levels
   - Childcare coverage

9. **Employment** (columns 38-48)
   - Employment by sector
   - Social benefit recipients
   - Unemployment rates (overall, by gender, by age)

10. **Footnotes** (column 52)
    - Additional notes/references

## Parsing Strategy

### Step 1: Detect Header Row

Find the row that contains "Land" and "Wahlkreis-Nr.":

```python
def find_header_row(csv_path):
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for i, line in enumerate(f):
            parts = line.split(';')
            if len(parts) > 2 and 'Land' in parts[0] and 'Wahlkreis' in parts[1]:
                return i  # Zero-indexed line number
    return None
```

### Step 2: Read with Dynamic Header

```python
def read_election_csv(csv_path, election_year):
    # Find header row
    header_row = find_header_row(csv_path)
    if header_row is None:
        raise ValueError(f"Could not find header row in {csv_path}")
    
    # Read with header row as column names
    df = pd.read_csv(
        csv_path,
        encoding='utf-8-sig',
        sep=';',
        skiprows=header_row,
        low_memory=False
    )
    
    # First row contains column names, second row is first data row
    # But pandas already used first row as column names, so we're good
    
    return df
```

### Step 3: Normalize Column Names

Since column names contain dates that differ between elections, we need to normalize them:

```python
def normalize_column_name(col_name, election_year):
    """
    Normalize column names by removing date-specific parts.
    
    Examples:
    - "Gemeinden am 31.12.2019 (Anzahl)" -> "gemeinden_anzahl"
    - "Bevölkerung am 31.12.2023 - Insgesamt (in 1000)" -> "bevoelkerung_insgesamt_1000"
    """
    # Remove date patterns (am DD.MM.YYYY)
    col = re.sub(r'\s*am\s+\d{2}\.\d{2}\.\d{4}\s*', ' ', col_name)
    # Remove other date references
    col = re.sub(r'\s*\d{4}\s*', ' ', col)
    # Convert to lowercase
    col = col.lower()
    # Replace special characters
    col = re.sub(r'[^a-z0-9\s]', ' ', col)
    # Replace spaces with underscores
    col = re.sub(r'\s+', '_', col)
    # Remove leading/trailing underscores
    col = col.strip('_')
    return col
```

### Step 4: Handle German Number Format

Values use German format:
- `2.124,3` = 2124.3 (dot = thousands, comma = decimal)
- `-6,1` = -6.1

```python
def parse_german_number(value):
    """Convert German number format to float."""
    if pd.isna(value) or value == '' or value == '–':
        return None
    
    value_str = str(value).strip()
    # Remove thousands separators (dots)
    value_str = value_str.replace('.', '')
    # Replace decimal comma with dot
    value_str = value_str.replace(',', '.')
    
    try:
        return float(value_str)
    except ValueError:
        return None
```

### Step 5: Handle Wahlkreis-Nr. Format

BTW2021 uses zero-padded format (`001`, `002`), BTW2025 uses plain integers (`1`, `2`):

```python
def normalize_wahlkreis_nr(value):
    """Convert Wahlkreis-Nr. to integer."""
    if pd.isna(value):
        return None
    # Remove leading zeros and convert to int
    return int(str(value).lstrip('0') or '0')
```

## Data Quality Issues

1. **Missing values**: May be represented as empty strings, `–`, or `NaN`
2. **Inconsistent formatting**: Some numbers may have spaces
3. **Special rows**: Some files include summary rows (e.g., "Land insgesamt") that should be filtered out
4. **Column name truncation**: Very long column names may be truncated in some tools

## Recommended Parsing Implementation

```python
def load_election_structural_data(csv_path, election_year):
    """
    Load election structural data CSV with proper handling of format issues.
    
    Args:
        csv_path: Path to CSV file
        election_year: Election year (2013, 2021, 2025)
    
    Returns:
        DataFrame with normalized column names and parsed values
    """
    # Step 1: Determine encoding
    if election_year == 2013:
        encoding = 'iso-8859-1'
    else:
        encoding = 'utf-8-sig'
    
    # Step 2: Find header row
    with open(csv_path, 'r', encoding=encoding) as f:
        for i, line in enumerate(f):
            parts = line.split(';')
            if len(parts) > 2 and 'Land' in parts[0] and 'Wahlkreis' in parts[1]:
                header_row = i
                break
    else:
        raise ValueError(f"Could not find header row in {csv_path}")
    
    # Step 3: Handle BTW2013 special case (column number row)
    if election_year == 2013:
        # For BTW2013, we need to extract column names from header row
        # because there's a column number row between header and data
        with open(csv_path, 'r', encoding=encoding) as f:
            lines = f.readlines()
            header_line = lines[header_row]
            column_names = [part.strip() for part in header_line.split(';')]
        
        # Read data skipping header + column number row, using extracted names
        df = pd.read_csv(
            csv_path,
            encoding=encoding,
            sep=';',
            skiprows=header_row + 2,  # Skip header + column number row
            names=column_names,
            low_memory=False
        )
    else:
        # For 2021 and 2025, header row contains column names directly
        df = pd.read_csv(
            csv_path,
            encoding=encoding,
            sep=';',
            skiprows=header_row,
            low_memory=False
        )
    
    # Step 5: Normalize column names
    df.columns = [normalize_column_name(col, election_year) for col in df.columns]
    
    # Step 6: Normalize Wahlkreis-Nr.
    if 'wahlkreis_nr' in df.columns:
        df['wahlkreis_nr'] = df['wahlkreis_nr'].apply(normalize_wahlkreis_nr)
    
    # Step 7: Parse numeric columns (all except Land, Wahlkreis-Nr., Wahlkreis-Name)
    numeric_cols = [col for col in df.columns 
                   if col not in ['land', 'wahlkreis_nr', 'wahlkreis_name', 'fussnoten']]
    
    for col in numeric_cols:
        df[col] = df[col].apply(parse_german_number)
    
    # Step 8: Filter out summary rows
    df = df[df['wahlkreis_nr'].notna() & (df['wahlkreis_nr'] <= 299)]
    
    # Step 9: Add election_year column
    df['election_year'] = election_year
    
    return df
```

## Differences Between Elections

| Aspect | BTW2013 | BTW2021 | BTW2025 |
|--------|---------|---------|---------|
| Encoding | ISO-8859-1 | UTF-8-sig | UTF-8-sig |
| Comment rows | 4 | 8 | 9 |
| Header row | 5 | 9 | 10 |
| Column number row | Yes (line 6, must skip) | No | No |
| Data start | 7 | 10 | 11 |
| Total columns | 43 | 52 | 52 |
| Reference dates | 2011/2012 | 2019 | 2023 |
| Wahlkreis-Nr. format | Plain (1) | Zero-padded (001) | Plain (1) |
| Status | Special handling required | OK | OK |

**Key Differences in BTW2013**:
- **Fewer columns**: 43 vs 52 (missing some categories like land use, some employment details)
- **Different age groups**: Uses "18-25", "25-35", "35-60" instead of "18-24", "25-34", "35-59"
- **Different column names**: Some categories have different names (e.g., "männlich" column, different education column names)
- **Extra row to skip**: Column number row between header and data

## Recommendations

1. **BTW2013 requires special handling**:
   - Use ISO-8859-1 encoding
   - Skip the column number row (line 6)
   - Handle different column structure (43 vs 52 columns)
   - Map columns to normalized names (may need separate mapping for 2013)
2. **Use dynamic header detection**: Don't hardcode skiprows values
3. **Normalize column names**: Remove date-specific parts for consistency
4. **Handle German number format**: Convert comma decimals to dot decimals
5. **Validate Wahlkreis-Nr.**: Ensure values are 1-299
6. **Filter summary rows**: Remove rows with Wahlkreis-Nr. > 299 or special names
7. **Column mapping**: May need separate column mapping logic for BTW2013 due to structural differences

## Implementation Notes

- Column names will differ between elections due to date references
- Need flexible schema that can handle column name variations
- Consider using a mapping table to standardize column names across elections
- Store original column names as metadata for reference

