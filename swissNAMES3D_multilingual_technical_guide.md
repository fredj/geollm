# swissNAMES3D Multilingual Names: Technical Implementation Guide

**Version:** May 2025  
**Target Audience:** Development teams and coding agents processing swissNAMES3D geographic names data  
**Last Updated:** 2025-02-13

---

## Table of Contents

1. [Overview](#overview)
2. [Data Model Architecture](#data-model-architecture)
3. [Multilingual Name Attributes](#multilingual-name-attributes)
4. [Name Types and Hierarchies](#name-types-and-hierarchies)
5. [Language Codes](#language-codes)
6. [Status Codes (Name Hierarchy)](#status-codes-name-hierarchy)
7. [Format-Specific Implementation](#format-specific-implementation)
8. [Practical Implementation Patterns](#practical-implementation-patterns)
9. [Edge Cases and Special Considerations](#edge-cases-and-special-considerations)

---

## Overview

swissNAMES3D implements a sophisticated multilingual naming system to handle Switzerland's four official languages (German, French, Italian, Romansh) plus local dialects. This document provides coding specifications for correctly parsing, querying, and rendering multilingual geographic names.

**Key Principle:** One geographic object can have multiple names representing:
- Different languages (endonyms/exonyms)
- Regional variants or colloquialisms (informal names)
- Multiple official designations in bilingual regions

---

## Data Model Architecture

### Core Concept: Geometry-to-Name Mapping

swissNAMES3D uses an **m:n (many-to-many) relationship** between geographic objects (geometries) and their names:

```
Geometry (Point/Line/Polygon)
    ↓
    └─→ Name 1 (e.g., "Interlaken", German, Official)
    └─→ Name 2 (e.g., "Interlâken", French, Informal)
    └─→ Name 3 (e.g., "Interlacken", Italian, Informal)
```

### Data Classes

All multilingual names are stored in the `TLM_NAMEN_ALLE` table (File Geodatabase) or attached to geometry records (Shapefile/CSV):

| Class | Geometry Type | Count | Multilingual Potential |
|-------|---------------|-------|------------------------|
| `TLM_NAME_PKT` | Point | 334,201 | High (mountain peaks, settlements) |
| `TLM_NAME_LIN` | Line | 12,125 | Medium (waterways, infrastructure) |
| `TLM_NAME_PLY` | Polygon | 91,303 | High (lakes, settlements, regions) |

---

## Multilingual Name Attributes

### Primary Attributes (stored in `TLM_NAMEN_ALLE`)

#### 1. `NAME` (Text, max 250 characters)
The actual name string in the specified language and orthography.

**Examples:**
- "Zürich" (German, official)
- "Zurich" (English exonym)
- "Zurique" (Portuguese exonym)

#### 2. `SPRACHCODE` (Language Code Domain)
Identifies which language/dialect the name is in. Follows ISO 639-2 standard.

**Valid Values:**
- `GER` - German (including Swiss German dialects)
- `FRA` - French (including Franco-Provençal dialects)
- `ITA` - Italian (including Italo-Romance dialects)
- `ROH` - Romansh (Rumantsch Grischun including local variants)
- `MULTI` - Bilingual official name (names separated by "/")
- `ub` - Unknown language
- `k_W` - No value

**Implementation Note:** Always normalize SPRACHCODE to uppercase when filtering.

#### 3. `NAMEN_TYP` (Name Type Domain)
Defines the classification of this name relative to others for the same object.

**Valid Values:**
- `100` - Einfacher Name (Simple/Single Name)
- `0` - Endonym (primary name in a national language)
- `1` - Exonym (common name in another language)
- `2` - Namenspaar (multilingual official name)
- `ub` - Unknown type

#### 4. `STATUS` (Name Status Domain)
Indicates the official standing and usage frequency of this name variant.

**Valid Values:**
- `1` - offiziell (Official primary name)
- `2` - ueblich (Common/usual variant)
- `3` - informell (Informal/colloquial variant) *(changed in 2025)*
- `999998` - k_W (No value)

**Introduced:** Version 2019  
**Updated:** Version 2025 - Code 3 redefined from "fremd" to "informell" to include colloquial variants

#### 5. `NAMENGRUPPE_UUID` (GUID)
Groups related names belonging to the same object.

**Critical for multilingual processing:** Names with identical `NAMENGRUPPE_UUID` values are variants of the same entity and should be treated as a group.

**Usage Pattern:**
```
SELECT * FROM TLM_NAMEN_ALLE
WHERE NAMENGRUPPE_UUID = {target_uuid}
ORDER BY STATUS, SPRACHCODE
```

---

## Name Types and Hierarchies

### Type 1: Simple Names (`NAMEN_TYP = 100`)

An object with a single name in a single language.

**Characteristics:**
- Only one name record per object
- Always `STATUS = 1` (offiziell)
- Majority of objects (~70% estimated)

**Example:**
```
Object UUID: {ABC123}
NAME: "Säntis"
SPRACHCODE: GER
NAMEN_TYP: 100
STATUS: 1
NAMENGRUPPE_UUID: {ABC123}
```

### Type 2: Endonym (`NAMEN_TYP = 0`)

The official name in one of the four national languages.

**Characteristics:**
- Used for objects in or near language regions
- Part of an object with multiple language variants
- `STATUS` can be 1 (offiziell) or 2 (ueblich)
- Name is written as it is used in the native language

**Example (Bilingual Lake):**
```
Object UUID: {LAKE001}
NAME: "Lac Léman"           | NAME: "Genfersee"
SPRACHCODE: FRA             | SPRACHCODE: GER
NAMEN_TYP: 0                | NAMEN_TYP: 0
STATUS: 1                   | STATUS: 1
NAMENGRUPPE_UUID: {G001}    | NAMENGRUPPE_UUID: {G001}
```

### Type 3: Exonym (`NAMEN_TYP = 1`)

A common name in a different language than the endonym, typically used outside the region.

**Characteristics:**
- Represents how a place is commonly called in other languages
- Usually `STATUS = 3` (informell as of 2025)
- Different from the official spelling in the native language
- Historical or alternative name

**Example (Geneva / Genève / Genf):**
```
Object UUID: {GENEVA}
NAME: "Genève"  | NAME: "Genf"    | NAME: "Geneva"
SPRACHCODE: FRA | SPRACHCODE: GER | SPRACHCODE: ENG*
NAMEN_TYP: 0    | NAMEN_TYP: 1    | NAMEN_TYP: 1
STATUS: 1       | STATUS: 3       | STATUS: 3*
```
*Note: English exonyms exist in the data but ENG is not officially supported in schema

### Type 4: Namenspaar (`NAMEN_TYP = 2`)

An officially multilingual name with multiple components separated by "/".

**Characteristics:**
- Official bilingual designation
- Used in regions with official multilingualism (e.g., Valais/Wallis)
- Single record with `SPRACHCODE = MULTI`
- Components separated by "/" character
- `STATUS = 1` (always official)

**Example (Bilingual Region Name):**
```
Object UUID: {VALAIS}
NAME: "Valais/Wallis"
SPRACHCODE: MULTI
NAMEN_TYP: 2
STATUS: 1
NAMENGRUPPE_UUID: {VALAIS}
```

**Parsing Rule:** Split on "/" and map first part to primary regional language, second to alternate.

---

## Language Codes

### ISO 639-2 Implementation

swissNAMES3D uses three-letter ISO 639-2 codes for language identification:

| Code | Language | Scope | Notes |
|------|----------|-------|-------|
| `GER` | German | Swiss German and High German dialects | ~60% of dataset |
| `FRA` | French | Standard French and Franco-Provençal dialects | ~25% of dataset |
| `ITA` | Italian | Standard Italian and Italo-Romance dialects | ~10% of dataset |
| `ROH` | Romansh | Rumantsch Grischun and local variants | ~3% of dataset |
| `MULTI` | Bilingual | Official multilingual names | Special handling |
| `ub` | Unknown | Language cannot be determined | Rare, handle with caution |

### Language Code Usage in Queries

**Filter by primary language:**
```sql
WHERE SPRACHCODE = 'GER'
```

**Filter for any German variant or German-affiliated bilingual names:**
```sql
WHERE SPRACHCODE IN ('GER', 'MULTI')
```

**Get all names for an object grouped by language:**
```sql
SELECT SPRACHCODE, NAME, STATUS
FROM TLM_NAMEN_ALLE
WHERE UUID = {target_uuid}
GROUP BY SPRACHCODE
ORDER BY SPRACHCODE
```

---

## Status Codes (Name Hierarchy)

The STATUS attribute enables intelligent name rendering with priority ordering.

### Status Hierarchy (High to Low Priority)

| Status Code | Value | Display Priority | Use Case |
|-------------|-------|------------------|----------|
| 1 | offiziell | PRIMARY | Display this name by default in official maps/documents |
| 2 | ueblich | SECONDARY | Display as alternative if context requires it |
| 3 | informell | TERTIARY | Display only in specific contexts (e.g., historical maps, user searches) |

### Status Value Definition (as of 2025)

**Status = 1 (offiziell)**
- Official primary name in the native language
- Appears in official publications and maps
- Examples: "Interlaken", "Genève", "Leventina"

**Status = 2 (ueblich)**
- Common locally-used variant
- May be used in same region as Status 1
- Often in different language than Status 1
- Examples: "Glion" in multiple languages, "Morat" alongside "Murten"

**Status = 3 (informell)** *(updated 2025)*
- Colloquial or informal names
- Includes exonyms (foreign language names)
- Includes informal/dialect variants that differ from official spelling
- Example: "Genf" (German informal for Genève), "Wetterhorn" (colloquial form of "Wätterhoren")
- Do NOT appear in official land registry maps

**Status = 999998 (k_W)**
- No value / missing data
- Handle with null safety checks

### Status Change Example (2025 Update)

Prior to 2025, Status 3 was labeled "fremd" (foreign). As of 2025:
- "fremd" status expanded to "informell"
- Now includes both exonyms AND colloquial variants in the same language
- Example: "Wätterhoren" (official) vs "Wetterhorn" (colloquial German variant)

---

## Format-Specific Implementation

### ESRI File Geodatabase

**Structure:** m:n relationship via `TLM_NAMEN_ALLE` table

**Tables:**
1. `TLM_NAME_PKT`, `TLM_NAME_LIN`, `TLM_NAME_PLY` - Geometry tables
2. `TLM_NAMEN_ALLE` - Name attributes table

**Attributes in `TLM_NAMEN_ALLE`:**
```
OBJECTID        (Object ID, sequential)
UUID            (GUID, geometry reference)
NAME            (Text, max 250 chars)
STATUS          (Domain: 1, 2, 3, 999998)
SPRACHCODE      (Domain: GER, FRA, ITA, ROH, MULTI, ub, k_W)
NAMEN_TYP       (Domain: 100, 0, 1, 2, ub)
NAMENGRUPPE_UUID (GUID, groups related names)
ISCED_STUFE     (Domain, education level for schools only)
```

**Query Pattern:**
```python
# Pseudocode for GDB query
names_by_object = []
for geometry in geometries:
    names = query(
        f"SELECT * FROM TLM_NAMEN_ALLE WHERE UUID = '{geometry.uuid}'"
    )
    # Group by NAMENGRUPPE_UUID for related names
    grouped = group_by(names, 'NAMENGRUPPE_UUID')
    names_by_object.append({
        'uuid': geometry.uuid,
        'name_groups': grouped
    })
```

### ESRI Shapefile (3D)

**Structure:** Geometry + attributes in single file per type

**Key Differences from GDB:**
- One Shapefile per geometry type (.shp, .shx, .dbf, .prj files)
- Attributes are embedded in DBF file, not in separate table
- Multilingual names cause **object duplication** (multiple UUIDs with same geometry UUID)
- Attributes stored as strings, not domains

**Attribute Names in Shapefile:**
```
Shapefile Name      | GDB Name            | Data Type
OBJEKTID           | OBJECTID            | String
SHAPE              | (geometry)          | Geometry Z
UUID               | UUID                | String (GUID format)
OBJEKTART          | OBJEKTART           | String
OBJEKTKLAS         | OBJEKTKLASSE_TLM    | String
NAME               | NAME (from table)   | String
STATUS             | STATUS              | String (1, 2, 3, 999998)
SPRACHCODE         | SPRACHCODE          | String (GER, FRA, ITA, ROH, MULTI, ub, k_W)
NAMEN_TYP          | NAMEN_TYP           | String (100, 0, 1, 2, ub)
NAMENGRUPP         | NAMENGRUPPE_UUID    | String (GUID format)
ISCED              | ISCED_STUFE         | String (for schools)
```

**Critical Pattern - Handling Duplicates:**

When an object has multiple languages:

```
Record 1: UUID={A1}, NAMENGRUPPE_UUID={A1}, NAME="Lac Léman", SPRACHCODE=FRA
Record 2: UUID={A1}, NAMENGRUPPE_UUID={A1}, NAME="Genfersee", SPRACHCODE=GER
Record 3: UUID={A1}, NAMENGRUPPE_UUID={A1}, NAME="Verbano", SPRACHCODE=ITA
```

All records share same `UUID` but appear as separate rows.

**Deduplication Pattern:**
```python
def deduplicate_shapefile_names(records):
    """Group duplicate geometry records by UUID"""
    result = {}
    for record in records:
        if record['UUID'] not in result:
            result[record['UUID']] = {
                'geometry': record.geometry,
                'names': []
            }
        result[record['UUID']]['names'].append({
            'name': record['NAME'],
            'language': record['SPRACHCODE'],
            'status': record['STATUS'],
            'type': record['NAMEN_TYP'],
            'group_id': record['NAMENGRUPP']
        })
    return result
```

### CSV (Text Format)

**Structure:** One record per name, geometry represented as single coordinate triplet

**Attributes:**
```
All attributes as string values, comma-separated:
OBJECTID, Shape_X, Shape_Y, Shape_Z, UUID, OBJEKTART, OBJEKTKLASSE_TLM,
NAME, STATUS, SPRACHCODE, NAMEN_TYP, NAMENGRUPPE_UUID, ISCED_STUFE
```

**Geometry Handling:**
- **Point objects:** Shape_X, Shape_Y, Shape_Z = exact point coordinates
- **Line objects:** Shape_X, Shape_Y, Shape_Z = centroid of line
- **Polygon objects:** Shape_X, Shape_Y, Shape_Z = centroid of polygon

**CSV Deduplication Pattern:**
```python
def parse_csv_multilingual(csv_path):
    """Parse CSV handling multilingual names"""
    import csv
    
    names_by_uuid = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            uuid = row['UUID']
            if uuid not in names_by_uuid:
                names_by_uuid[uuid] = {
                    'coordinates': (float(row['Shape_X']), 
                                   float(row['Shape_Y']), 
                                   float(row['Shape_Z'])),
                    'names': []
                }
            
            names_by_uuid[uuid]['names'].append({
                'name': row['NAME'],
                'language': row['SPRACHCODE'],
                'status': row['STATUS'],
                'type': row['NAMEN_TYP'],
                'group_id': row['NAMENGRUPPE_UUID']
            })
    
    return names_by_uuid
```

---

## Practical Implementation Patterns

### Pattern 1: Get Official Name in Specific Language

**Use Case:** Display the official German name for a geographic feature

```python
def get_official_name(uuid, language_code):
    """Get the official name (STATUS=1) for a specific language"""
    query = f"""
    SELECT NAME 
    FROM TLM_NAMEN_ALLE 
    WHERE UUID = '{uuid}' 
      AND SPRACHCODE = '{language_code}'
      AND STATUS = 1
    LIMIT 1
    """
    result = execute_query(query)
    return result[0]['NAME'] if result else None

# Usage
german_official = get_official_name('{lake-uuid}', 'GER')  # Returns "Genfersee"
french_official = get_official_name('{lake-uuid}', 'FRA')  # Returns "Lac Léman"
```

### Pattern 2: Get All Variants for an Object (Grouped)

**Use Case:** Display all available names with their language and status

```python
def get_all_name_variants(uuid):
    """Retrieve all name variants grouped by language"""
    query = f"""
    SELECT SPRACHCODE, NAME, STATUS, NAMEN_TYP
    FROM TLM_NAMEN_ALLE 
    WHERE UUID = '{uuid}'
    ORDER BY STATUS, SPRACHCODE
    """
    
    results = execute_query(query)
    
    variants = {
        'official': {},      # STATUS = 1
        'common': {},        # STATUS = 2
        'informal': {}       # STATUS = 3
    }
    
    for row in results:
        status_key = {
            '1': 'official',
            '2': 'common',
            '3': 'informal'
        }.get(row['STATUS'])
        
        if status_key:
            variants[status_key][row['SPRACHCODE']] = row['NAME']
    
    return variants

# Usage
variants = get_all_name_variants('{lake-uuid}')
# Returns:
# {
#   'official': {'GER': 'Genfersee', 'FRA': 'Lac Léman'},
#   'common': {'ITA': 'Verbano'},
#   'informal': {}
# }
```

### Pattern 3: Get Primary Name with Fallback Logic

**Use Case:** Display best available name with language preference cascade

```python
def get_preferred_name(uuid, preferred_languages=['GER', 'FRA', 'ITA']):
    """
    Get name with fallback language priority.
    1. Try official name in each preferred language (order matters)
    2. Fall back to common names in same order
    3. Fall back to first available official name
    """
    query = f"SELECT SPRACHCODE, NAME, STATUS FROM TLM_NAMEN_ALLE WHERE UUID = '{uuid}'"
    names = execute_query(query)
    
    # Try official in preferred order
    for lang in preferred_languages:
        for name in names:
            if name['SPRACHCODE'] == lang and name['STATUS'] == '1':
                return {'name': name['NAME'], 'language': lang, 'status': 'official'}
    
    # Try common in preferred order
    for lang in preferred_languages:
        for name in names:
            if name['SPRACHCODE'] == lang and name['STATUS'] == '2':
                return {'name': name['NAME'], 'language': lang, 'status': 'common'}
    
    # Fallback: first official name regardless of language
    for name in names:
        if name['STATUS'] == '1':
            return {'name': name['NAME'], 'language': name['SPRACHCODE'], 'status': 'official'}
    
    return None

# Usage
name_info = get_preferred_name('{lake-uuid}', preferred_languages=['GER', 'FRA'])
# Returns: {'name': 'Genfersee', 'language': 'GER', 'status': 'official'}
```

### Pattern 4: Handle Multilingual Name Pairs

**Use Case:** Parse and display bilingual official names (Status = 2, SPRACHCODE = MULTI)

```python
def parse_multilingual_pair(name_string, sprachcode):
    """Parse officially multilingual names"""
    if sprachcode != 'MULTI':
        return {'primary': name_string, 'secondary': None}
    
    parts = name_string.split('/')
    if len(parts) == 2:
        return {
            'primary': parts[0].strip(),
            'secondary': parts[1].strip(),
            'separator': '/'
        }
    else:
        return {
            'primary': name_string,
            'secondary': None,
            'warning': 'Unexpected format for MULTI language name'
        }

# Usage
query = """
SELECT NAME FROM TLM_NAMEN_ALLE 
WHERE SPRACHCODE = 'MULTI' AND STATUS = 1
"""
for row in execute_query(query):
    parsed = parse_multilingual_pair(row['NAME'], 'MULTI')
    print(f"{parsed['primary']} / {parsed['secondary']}")
    # Output examples:
    # Valais / Wallis
    # Fribourg / Freiburg
    # Genève / Genf
```

### Pattern 5: Filter Formal vs. Informal Names for Publication

**Use Case:** Generate map labels excluding colloquial variants

```python
def get_publication_names(uuid, exclude_status_3=True):
    """
    Get names suitable for official maps/publications.
    By default excludes Status 3 (informell) names.
    """
    status_filter = "STATUS IN (1, 2)" if exclude_status_3 else "STATUS IN (1, 2, 3)"
    
    query = f"""
    SELECT NAME, SPRACHCODE, STATUS
    FROM TLM_NAMEN_ALLE
    WHERE UUID = '{uuid}' AND {status_filter}
    ORDER BY STATUS
    """
    
    return execute_query(query)

# Usage - for official cartography
official_names = get_publication_names('{uuid}', exclude_status_3=True)
# Returns only Status 1 & 2 names
```

---

## Edge Cases and Special Considerations

### Edge Case 1: School and Education Areas

**Special Handling Required:** ISCED_STUFE attribute

School/University names may lack full attribute data:

```
STATUS: 'ub' (unknown)
SPRACHCODE: 'ub' (unknown)
NAMEN_TYP: 'ub' (unknown)
ISCED_STUFE: {100-700 or ub/k_W}  # International Classification of Education
```

**Implementation:**
```python
def handle_school_name(name_record):
    """Process school records with potentially missing language info"""
    
    if name_record.get('ISCED_STUFE') not in [None, 'ub', 'k_W']:
        # This is a school/university
        education_levels = {
            '600': 'Primary',
            '500': 'Lower Secondary',
            '400': 'Upper Secondary',
            '300': 'Non-tertiary Continued',
            '200': 'Tertiary',
            '100': 'Advanced Research'
        }
        
        # Handle missing language code
        lang = name_record.get('SPRACHCODE', 'ub')
        if lang == 'ub':
            # Infer from region or use default rendering
            lang = infer_language_from_geometry()
        
        return {
            'name': name_record['NAME'],
            'type': 'education',
            'level': education_levels.get(name_record['ISCED_STUFE']),
            'language': lang
        }
```

### Edge Case 2: Objects with No Multilingual Names

**Handling:**

Many objects have only a single name:

```python
def is_multilingual(uuid):
    """Check if an object has multiple language variants"""
    query = f"""
    SELECT COUNT(DISTINCT SPRACHCODE) as lang_count
    FROM TLM_NAMEN_ALLE
    WHERE UUID = '{uuid}' AND SPRACHCODE NOT IN ('MULTI', 'ub')
    """
    result = execute_query(query)[0]
    return result['lang_count'] > 1
```

### Edge Case 3: Status 3 (Informal) Names with Exonyms

**Behavior Change (2025):**

Status 3 now includes both:
1. Traditional exonyms (foreign language names): "Genf" for Geneva
2. Colloquial variants in same language: "Wetterhorn" vs official "Wätterhoren"

**Implementation Consideration:**

```python
def classify_informal_name(name_record):
    """Determine type of Status 3 name"""
    if name_record['STATUS'] != '3':
        return None
    
    # Check against official record
    official = get_official_name(
        name_record['UUID'], 
        name_record['SPRACHCODE']
    )
    
    if not official:
        return 'exonym'  # Different language than official
    elif official != name_record['NAME']:
        return 'colloquial'  # Same language, different spelling
    else:
        return 'variant'  # Other variant
```

### Edge Case 4: Missing or Unknown Language Code

**Handling:**

```python
def safe_language_handler(sprachcode):
    """Handle unknown or missing language codes"""
    valid_codes = {'GER', 'FRA', 'ITA', 'ROH', 'MULTI'}
    
    if sprachcode in valid_codes:
        return sprachcode
    elif sprachcode == 'ub':
        return 'UNKNOWN'
    elif sprachcode == 'k_W':
        return 'NO_VALUE'
    else:
        # Unexpected code
        log_warning(f"Unexpected SPRACHCODE: {sprachcode}")
        return 'INVALID'
```

### Edge Case 5: Handling Name Group Relationships Across Formats

**Shapefile/CSV Deduplication:**

In Shapefiles and CSV, related multilingual names are identified by `NAMENGRUPP`/`NAMENGRUPPE_UUID`:

```python
def group_related_names(records):
    """Group records by NAMENGRUPPE_UUID for multilingual objects"""
    groups = {}
    
    for record in records:
        group_id = record.get('NAMENGRUPPE_UUID') or record.get('NAMENGRUPP')
        if group_id not in groups:
            groups[group_id] = {
                'uuid': record['UUID'],
                'geometry': record.get('geometry'),
                'names': []
            }
        
        groups[group_id]['names'].append({
            'text': record['NAME'],
            'language': record['SPRACHCODE'],
            'status': record['STATUS'],
            'type': record['NAMEN_TYP']
        })
    
    return groups
```

---

## Implementation Checklist

- [ ] Determine output format (GDB, Shapefile, or CSV)
- [ ] Understand whether data is in single table (`TLM_NAMEN_ALLE`) or embedded in geometry
- [ ] Implement `NAMENGRUPPE_UUID` grouping logic for multilingual objects
- [ ] Create language filtering functions for each supported language
- [ ] Implement status-based prioritization (1 > 2 > 3)
- [ ] Handle MULTI language pairs with "/" separator parsing
- [ ] Add null-safety checks for `ub` and `k_W` status/language codes
- [ ] Test deduplication logic with actual multilingual objects
- [ ] Document any custom rules for status > 3 names in your application
- [ ] Create fallback logic for missing language variants
- [ ] Validate ISCED education levels for school/university objects
- [ ] Test with bilingual regions (Valais/Wallis, Fribourg/Freiburg, etc.)

---

## References

- swissNAMES3D Product Information (May 2025)
- ISO 639-2 Language Code Standard
- UNESCO ISCED Classification (1997)
- Swiss Federal Statistical Office (BFS/OFS)
- Swiss Federal Office of Topography (swisstopo)

---

**Document Purpose:** Technical reference for developers integrating swissNAMES3D multilingual names into applications, data pipelines, and cartographic systems.
