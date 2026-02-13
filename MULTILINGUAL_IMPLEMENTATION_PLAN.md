# swissNAMES3D Multilingual Support - Implementation Plan

**Status:** Not Yet Implemented  
**Priority:** Medium  
**Estimated Effort:** 2-3 days  
**Created:** 2025-02-13

---

## Executive Summary

The current `SwissNames3DSource` implementation **ignores all multilingual attributes** in the swissNAMES3D dataset, causing:
- **Duplicate results** (same geometry with different language names appears multiple times)
- **No language filtering** (cannot search for French vs German names)
- **No status prioritization** (official vs informal names treated equally)
- **No bilingual name parsing** ("Valais/Wallis" returned as-is)

This document outlines a plan to implement full multilingual support based on the technical guide in `swissNAMES3D_multilingual_technical_guide.md`.

---

## Current Implementation Analysis

### Files Involved

- **Core:** `geollm/datasources/swissnames3d.py` (417 lines)
- **Tests:** `tests/test_swissnames3d.py` (195 lines)
- **Guide:** `swissNAMES3D_multilingual_technical_guide.md` (784 lines)

### What Works Now

✅ Basic name search with accent normalization  
✅ OBJEKTART type mapping (164 types)  
✅ Coordinate conversion (EPSG:2056 → WGS84)  
✅ Multi-file loading (PKT, LIN, PLY)  
✅ Common column detection  

### Critical Gaps

❌ **No language filtering** - SPRACHCODE preserved but unused  
❌ **No deduplication** - Same UUID appears multiple times for different languages  
❌ **No status ranking** - STATUS column ignored  
❌ **No bilingual parsing** - "Valais/Wallis" not split  
❌ **Language code mismatch** - Guide expects `GER`, data has `Hochdeutsch inkl. Lokalsprachen`

---

## Data Structure Findings

### Actual vs Expected Attribute Values

The technical guide documents ISO 639-2 codes, but the **real data uses German language names**:

| Attribute | Technical Guide | Actual Data |
|-----------|----------------|-------------|
| German | `GER` | `Hochdeutsch inkl. Lokalsprachen` |
| French | `FRA` | `Franzoesisch inkl. Lokalsprachen` |
| Italian | `ITA` | `Italienisch inkl. Lokalsprachen` |
| Romansh | `ROH` | `Rumantsch Grischun inkl. Lokalsprachen` |
| Multilingual | `MULTI` | `mehrsprachig` |
| Unknown | `ub` | Not found in sample |
| No value | `k_W` | `k_W` ✓ |

### Attribute Distributions (PKT file, 334,738 features)

**SPRACHCODE:**
- Hochdeutsch: 219,150 (65.5%)
- Franzoesisch: 58,839 (17.6%)
- Italienisch: 29,278 (8.7%)
- Rumantsch Grischun: 20,182 (6.0%)
- k_W: 6,862 (2.1%)
- mehrsprachig: 427 (0.1%)

**STATUS:**
- offiziell: 334,433 (99.9%)
- ueblich: 216 (0.06%)
- informell: 89 (0.03%)

**NAMEN_TYP:**
- einfacher Name: 333,467 (99.6%)
- Endonym: 952 (0.3%)
- Namenspaar: 245 (0.07%)
- Exonym: 74 (0.02%)

### Multilingual Examples Found

**Example 1: Monte Ceneri / Munt Schiember**
```
NAME: Monte Ceneri
UUID: {E63F34BB-83DE-4387-90FC-BE1404D9F388}
NAMENGRUPP: {0064FE4B-FE1D-4B99-8C99-9088792F109A}
SPRACHCODE: Italienisch inkl. Lokalsprachen
STATUS: offiziell
NAMEN_TYP: Endonym

NAME: Munt Schiember
UUID: {E63F34BB-83DE-4387-90FC-BE1404D9F388}  ← Same geometry!
NAMENGRUPP: {0064FE4B-FE1D-4B99-8C99-9088792F109A}  ← Same group!
SPRACHCODE: Rumantsch Grischun inkl. Lokalsprachen
STATUS: informell
NAMEN_TYP: Exonym
```

**Example 2: Bilingual Names (NAMEN_TYP = Namenspaar)**
- "Biel/Bienne-Ost/Est"
- "Domat/Ems"
- "Sils/Segl Maria Barchiröls (See)"

All have `SPRACHCODE='mehrsprachig'` and `NAMEN_TYP='Namenspaar'`.

---

## Proposed Implementation

### Phase 1: Language Code Mapping (2-4 hours)

**Goal:** Normalize German attribute values to ISO codes for easier filtering.

**Changes to `swissnames3d.py`:**

```python
# Add at module level (after line 19)
SPRACHCODE_TO_ISO: dict[str, str] = {
    "Hochdeutsch inkl. Lokalsprachen": "de",
    "Franzoesisch inkl. Lokalsprachen": "fr",
    "Italienisch inkl. Lokalsprachen": "it",
    "Rumantsch Grischun inkl. Lokalsprachen": "rm",
    "mehrsprachig": "multi",
    "k_W": None,  # No value
}

# Also support technical guide codes for backward compatibility
SPRACHCODE_TO_ISO.update({
    "GER": "de",
    "FRA": "fr",
    "ITA": "it",
    "ROH": "rm",
    "MULTI": "multi",
    "ub": None,
})

def _normalize_language_code(sprachcode: str | None) -> str | None:
    """Convert SPRACHCODE to ISO 639-1 language code."""
    if not sprachcode or sprachcode == "k_W":
        return None
    return SPRACHCODE_TO_ISO.get(sprachcode, sprachcode.lower())
```

**New Methods:**

```python
def _detect_language_column(self) -> str | None:
    """Detect the language code column in the data."""
    for candidate in ("SPRACHCODE", "sprachcode", "Sprachcode"):
        if candidate in self._gdf.columns:
            return candidate
    return None

def _detect_status_column(self) -> str | None:
    """Detect the name status column in the data."""
    for candidate in ("STATUS", "status", "Status"):
        if candidate in self._gdf.columns:
            return candidate
    return None

def _detect_name_type_column(self) -> str | None:
    """Detect the name type column in the data."""
    for candidate in ("NAMEN_TYP", "namen_typ", "Namen_Typ"):
        if candidate in self._gdf.columns:
            return candidate
    return None

def _detect_name_group_column(self) -> str | None:
    """Detect the name group UUID column in the data."""
    for candidate in ("NAMENGRUPPE_UUID", "NAMENGRUPP", "namengrupp", "Namengrupp"):
        if candidate in self._gdf.columns:
            return candidate
    return None
```

**Tests to add:** `test_language_code_normalization()`

---

### Phase 2: Deduplication by Name Group (4-6 hours)

**Goal:** Fix duplicate UUID issue by grouping multilingual variants.

**Changes to `swissnames3d.py`:**

Add new method to group variants:

```python
def _group_multilingual_variants(self, indices: list[int]) -> dict[str, list[dict[str, Any]]]:
    """
    Group features by NAMENGRUPPE_UUID to handle multilingual variants.
    
    Returns:
        Dict mapping NAMENGRUPP UUID to list of name variant dicts.
    """
    name_group_col = self._detect_name_group_column()
    if not name_group_col:
        # No grouping possible, return as-is
        return {str(idx): [{'index': idx}] for idx in indices}
    
    groups: dict[str, list[dict[str, Any]]] = {}
    for idx in indices:
        row = self._gdf.iloc[idx]
        group_id = str(row.get(name_group_col, idx))
        
        if group_id not in groups:
            groups[group_id] = []
        
        groups[group_id].append({
            'index': idx,
            'name': row[self._detect_name_column()],
            'language': _normalize_language_code(row.get(self._detect_language_column())),
            'status': row.get(self._detect_status_column()),
            'type': row.get(self._detect_name_type_column()),
        })
    
    return groups
```

Modify `_row_to_feature()` to include language metadata:

```python
# Add to properties dict (around line 333)
lang_col = self._detect_language_column()
if lang_col and row.get(lang_col):
    properties['language'] = _normalize_language_code(row[lang_col])

status_col = self._detect_status_column()
if status_col and row.get(status_col):
    properties['status'] = row[status_col]

name_type_col = self._detect_name_type_column()
if name_type_col and row.get(name_type_col):
    properties['name_type'] = row[name_type_col]

name_group_col = self._detect_name_group_column()
if name_group_col and row.get(name_group_col):
    properties['name_group'] = str(row[name_group_col])
```

**New parameter for `search()` method:**

```python
def search(
    self,
    name: str,
    type: str | None = None,
    language: str | list[str] | None = None,  # NEW
    include_variants: bool = False,  # NEW
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    Search for geographic features by name.
    
    Args:
        name: Location name to search for.
        type: Optional type hint for ranking results.
        language: Optional language filter (ISO 639-1: 'de', 'fr', 'it', 'rm')
                  or list for preference order ['de', 'fr'].
        include_variants: If True, include all language variants in results.
                         If False (default), return one result per geometry.
        max_results: Maximum number of results to return.
    """
    # ... existing search logic ...
    
    # NEW: Group by NAMENGRUPP
    groups = self._group_multilingual_variants(indices)
    
    if not include_variants:
        # Return one result per geometry (deduplicated)
        features = []
        for group_id, variants in groups.items():
            # Pick best variant based on language preference and status
            best = self._select_best_variant(variants, language)
            features.append(self._row_to_feature(best['index']))
    else:
        # Return all variants
        features = [self._row_to_feature(idx) for idx in indices]
    
    # ... rest of method ...
```

**New helper method:**

```python
def _select_best_variant(
    self,
    variants: list[dict[str, Any]],
    preferred_languages: str | list[str] | None = None
) -> dict[str, Any]:
    """
    Select the best name variant from a multilingual group.
    
    Priority:
    1. Preferred language(s) if specified
    2. STATUS: offiziell > ueblich > informell
    3. First variant
    """
    if not variants:
        raise ValueError("No variants provided")
    
    # Normalize language preference
    if isinstance(preferred_languages, str):
        preferred_languages = [preferred_languages]
    
    # Try preferred languages in order
    if preferred_languages:
        for lang in preferred_languages:
            for variant in variants:
                if variant.get('language') == lang:
                    return variant
    
    # Fall back to status priority
    status_priority = {'offiziell': 0, 'ueblich': 1, 'informell': 2}
    variants_sorted = sorted(
        variants,
        key=lambda v: status_priority.get(v.get('status', ''), 999)
    )
    
    return variants_sorted[0]
```

**Tests to add:**
- `test_deduplication_by_name_group()`
- `test_language_filtering()`
- `test_status_prioritization()`
- `test_include_variants_parameter()`

---

### Phase 3: Bilingual Name Parsing (2-3 hours)

**Goal:** Parse "Valais/Wallis" into structured components.

**Changes to `swissnames3d.py`:**

```python
def _parse_bilingual_name(
    self,
    name: str,
    name_type: str | None
) -> dict[str, Any]:
    """
    Parse bilingual names (Namenspaar) separated by '/'.
    
    Returns:
        {
            'is_bilingual': bool,
            'primary': str,
            'secondary': str | None,
            'full': str
        }
    """
    if name_type == 'Namenspaar' and '/' in name:
        parts = name.split('/', 1)
        return {
            'is_bilingual': True,
            'primary': parts[0].strip(),
            'secondary': parts[1].strip() if len(parts) > 1 else None,
            'full': name
        }
    
    return {
        'is_bilingual': False,
        'primary': name,
        'secondary': None,
        'full': name
    }
```

Update `_row_to_feature()` to use parsed names:

```python
# Replace simple name assignment (line 301)
name_col = self._detect_name_column()
name_type_col = self._detect_name_type_column()
raw_name = str(row[name_col])
name_type = row.get(name_type_col) if name_type_col else None

parsed_name = self._parse_bilingual_name(raw_name, name_type)

properties: dict[str, Any] = {
    'name': parsed_name['primary'],  # Use primary for main name
    'name_full': parsed_name['full'],  # Keep original
    'type': normalized_type,
    'confidence': 1.0,
}

if parsed_name['is_bilingual']:
    properties['bilingual'] = {
        'primary': parsed_name['primary'],
        'secondary': parsed_name['secondary'],
    }
```

**Tests to add:**
- `test_bilingual_name_parsing()`
- `test_namenspaar_detection()`

---

### Phase 4: Enhanced API Methods (3-4 hours)

**Goal:** Add convenience methods for multilingual workflows.

**New methods to add:**

```python
def get_all_variants(self, feature_id: str) -> list[dict[str, Any]]:
    """
    Get all language variants for a geographic feature.
    
    Args:
        feature_id: UUID or name group UUID.
    
    Returns:
        List of all name variants (different languages for same geometry).
    """
    self._ensure_loaded()
    name_group_col = self._detect_name_group_column()
    
    if not name_group_col:
        # Fallback to get_by_id
        feature = self.get_by_id(feature_id)
        return [feature] if feature else []
    
    # Find all features with matching NAMENGRUPP
    matches = self._gdf[self._gdf[name_group_col].astype(str) == feature_id]
    
    return [self._row_to_feature(idx) for idx in matches.index]


def get_languages(self) -> list[str]:
    """
    Get list of all languages present in the dataset.
    
    Returns:
        List of ISO 639-1 language codes (e.g., ['de', 'fr', 'it', 'rm']).
    """
    self._ensure_loaded()
    lang_col = self._detect_language_column()
    
    if not lang_col:
        return []
    
    languages = set()
    for lang in self._gdf[lang_col].unique():
        normalized = _normalize_language_code(lang)
        if normalized:
            languages.add(normalized)
    
    return sorted(languages)


def search_by_language(
    self,
    language: str,
    type: str | None = None,
    limit: int = 100
) -> list[dict[str, Any]]:
    """
    Get all features with names in a specific language.
    
    Args:
        language: ISO 639-1 language code ('de', 'fr', 'it', 'rm').
        type: Optional type filter.
        limit: Maximum results.
    
    Returns:
        List of features in the specified language.
    """
    self._ensure_loaded()
    lang_col = self._detect_language_column()
    
    if not lang_col:
        return []
    
    # Filter by language
    matches = []
    for idx, row in self._gdf.iterrows():
        lang = _normalize_language_code(row.get(lang_col))
        if lang == language:
            if type is None or self._matches_type(row, type):
                matches.append(self._row_to_feature(idx))
                if len(matches) >= limit:
                    break
    
    return matches
```

**Tests to add:**
- `test_get_all_variants()`
- `test_get_languages()`
- `test_search_by_language()`

---

### Phase 5: Comprehensive Testing (4-6 hours)

**New test fixtures needed:**

Create `tests/fixtures/swissnames3d_multilingual.json`:

```json
{
  "type": "FeatureCollection",
  "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::2056"}},
  "features": [
    {
      "type": "Feature",
      "properties": {
        "UUID": "uuid-geneva-fr",
        "NAME": "Genève",
        "OBJEKTART": "Ort",
        "STATUS": "offiziell",
        "SPRACHCODE": "Franzoesisch inkl. Lokalsprachen",
        "NAMEN_TYP": "Endonym",
        "NAMENGRUPP": "group-geneva"
      },
      "geometry": {"type": "Point", "coordinates": [2500000.0, 1117000.0]}
    },
    {
      "type": "Feature",
      "properties": {
        "UUID": "uuid-geneva-de",
        "NAME": "Genf",
        "OBJEKTART": "Ort",
        "STATUS": "informell",
        "SPRACHCODE": "Hochdeutsch inkl. Lokalsprachen",
        "NAMEN_TYP": "Exonym",
        "NAMENGRUPP": "group-geneva"
      },
      "geometry": {"type": "Point", "coordinates": [2500000.0, 1117000.0]}
    },
    {
      "type": "Feature",
      "properties": {
        "UUID": "uuid-valais",
        "NAME": "Valais/Wallis",
        "OBJEKTART": "Kanton",
        "STATUS": "offiziell",
        "SPRACHCODE": "mehrsprachig",
        "NAMEN_TYP": "Namenspaar",
        "NAMENGRUPP": "group-valais"
      },
      "geometry": {"type": "Polygon", "coordinates": [[[2600000, 1100000], [2650000, 1100000], [2650000, 1150000], [2600000, 1100000]]]}
    }
  ]
}
```

**Test cases to implement:**

```python
def test_multilingual_deduplication(multilingual_source):
    """Test that Geneva returns one result, not two."""
    results = multilingual_source.search("Genève")
    # Should return 1 result (deduplicated) by default
    assert len(results) == 1
    assert results[0]['properties']['name'] == 'Genève'
    assert results[0]['properties']['language'] == 'fr'

def test_multilingual_include_variants(multilingual_source):
    """Test that include_variants returns all languages."""
    results = multilingual_source.search("Genève", include_variants=True)
    assert len(results) == 2
    names = {r['properties']['name'] for r in results}
    assert names == {'Genève', 'Genf'}

def test_language_preference_french(multilingual_source):
    """Test language preference for French."""
    results = multilingual_source.search("Genève", language='fr')
    assert results[0]['properties']['name'] == 'Genève'
    assert results[0]['properties']['language'] == 'fr'

def test_language_preference_german(multilingual_source):
    """Test language preference for German."""
    results = multilingual_source.search("Genève", language='de')
    assert results[0]['properties']['name'] == 'Genf'
    assert results[0]['properties']['language'] == 'de'

def test_language_cascade(multilingual_source):
    """Test language preference cascade."""
    # Prefer German, fallback to French
    results = multilingual_source.search("Genève", language=['de', 'fr'])
    assert results[0]['properties']['name'] == 'Genf'

def test_status_prioritization(multilingual_source):
    """Test that official names rank higher than informal."""
    results = multilingual_source.search("Genève")
    # Should prefer 'Genève' (offiziell) over 'Genf' (informell)
    assert results[0]['properties']['name'] == 'Genève'
    assert results[0]['properties']['status'] == 'offiziell'

def test_bilingual_name_parsing(multilingual_source):
    """Test parsing of Namenspaar."""
    results = multilingual_source.search("Valais")
    assert len(results) == 1
    feature = results[0]
    assert feature['properties']['name'] == 'Valais'
    assert feature['properties']['bilingual']['secondary'] == 'Wallis'

def test_get_all_variants(multilingual_source):
    """Test retrieving all language variants."""
    variants = multilingual_source.get_all_variants("group-geneva")
    assert len(variants) == 2
    names = {v['properties']['name'] for v in variants}
    assert names == {'Genève', 'Genf'}

def test_get_languages(multilingual_source):
    """Test listing available languages."""
    languages = multilingual_source.get_languages()
    assert 'fr' in languages
    assert 'de' in languages
    assert 'multi' in languages
```

---

## Breaking Changes & Migration

### Option A: Breaking Change (Recommended)

**Change default behavior:**
- `search()` now returns **deduplicated** results by default
- Users wanting all variants must pass `include_variants=True`

**Migration guide:**
```python
# Old behavior (duplicates)
results = source.search("Genève")  # Returns 2 results

# New behavior (deduplicated by default)
results = source.search("Genève")  # Returns 1 result
results = source.search("Genève", include_variants=True)  # Returns 2 results
```

### Option B: Backward Compatible

**Keep old behavior as default:**
- Add `deduplicate=False` parameter (default False for now)
- Deprecation warning for `deduplicate=False`
- Remove in next major version

```python
# Current behavior
results = source.search("Genève", deduplicate=False)  # Default, returns duplicates

# New behavior (opt-in)
results = source.search("Genève", deduplicate=True)  # Returns 1 result
```

**Recommended:** Option A (breaking change) since this is likely a bug, not a feature.

---

## Testing Strategy

### Unit Tests
- Language code normalization
- Bilingual name parsing
- Status prioritization logic
- Variant selection algorithm

### Integration Tests
- Real data loading with all 3 geometry types
- Cross-language search (search "Geneva" finds "Genève")
- Multi-language regions (Fribourg/Freiburg, Biel/Bienne)

### Real-World Scenarios
```python
# Test Case 1: Lake Geneva
results = source.search("Lac Léman", language='fr')
# Should return: "Lac Léman" (FR, official, Polygon)

results = source.search("Genfersee", language='de')
# Should return: "Genfersee" (DE, official, Polygon)
# Same geometry as above, different name

# Test Case 2: Bilingual Canton
results = source.search("Valais")
# Should return: "Valais/Wallis" parsed as bilingual

# Test Case 3: Mountain with Multiple Languages
results = source.search("Monte Ceneri")
# Should return: "Monte Ceneri" (IT, official)
# Variants should include: "Munt Schiember" (RM, informal)
```

---

## Performance Considerations

### Indexing Strategy

**Current:**
- Single index: `normalized_name → [indices]`

**Proposed:**
- Add secondary indexes:
  - `language → [indices]` for fast language filtering
  - `name_group → [indices]` for variant lookup
  - `status → [indices]` for official-only queries

**Memory impact:** ~5-10% increase for 3 additional indexes

### Query Performance

**Deduplication overhead:**
- Grouping by NAMENGRUPP: O(n) where n = matching names
- Expected: <1ms for typical queries (5-20 matches)
- Worst case: 100ms for queries matching >10k features

**Optimization:** Cache grouped results if same query repeats.

---

## Documentation Updates

### 1. README.md

Add multilingual examples:

```markdown
### Multilingual Search

swissNAMES3D includes names in 4 Swiss languages. Search automatically deduplicates multilingual variants:

```python
# Search returns one result per geometry (deduplicated)
results = source.search("Genève")  # Returns French official name

# Filter by preferred language
results = source.search("Genève", language='de')  # Returns "Genf"

# Get all language variants
results = source.search("Genève", include_variants=True)
# Returns: [
#   {"name": "Genève", "language": "fr", "status": "offiziell"},
#   {"name": "Genf", "language": "de", "status": "informell"}
# ]

# Retrieve all variants for a location
variants = source.get_all_variants(feature_id)
```
```

### 2. API Documentation

Add docstring examples for all new parameters and methods.

### 3. ARCHITECTURE.md

Update Layer 2 (Resolution) section:

```markdown
#### Multilingual Support

SwissNames3DSource handles Switzerland's multilingual naming:
- **Deduplication:** Groups variants by NAMENGRUPPE_UUID
- **Language filtering:** ISO 639-1 codes (de, fr, it, rm)
- **Status ranking:** Official > Common > Informal
- **Bilingual parsing:** Splits "Valais/Wallis" into components
```

---

## Implementation Checklist

### Phase 1: Language Code Mapping
- [ ] Add `SPRACHCODE_TO_ISO` mapping dict
- [ ] Add `_normalize_language_code()` function
- [ ] Add `_detect_language_column()` method
- [ ] Add `_detect_status_column()` method
- [ ] Add `_detect_name_type_column()` method
- [ ] Add `_detect_name_group_column()` method
- [ ] Write tests for language normalization

### Phase 2: Deduplication
- [ ] Add `_group_multilingual_variants()` method
- [ ] Add `_select_best_variant()` method
- [ ] Update `search()` with `language` and `include_variants` parameters
- [ ] Update `_row_to_feature()` to include language metadata
- [ ] Write deduplication tests
- [ ] Write language filtering tests
- [ ] Write status prioritization tests

### Phase 3: Bilingual Parsing
- [ ] Add `_parse_bilingual_name()` method
- [ ] Update `_row_to_feature()` to use parsed names
- [ ] Write bilingual parsing tests

### Phase 4: Enhanced API
- [ ] Add `get_all_variants()` method
- [ ] Add `get_languages()` method
- [ ] Add `search_by_language()` method
- [ ] Write API method tests

### Phase 5: Testing & Documentation
- [ ] Create multilingual test fixture
- [ ] Write comprehensive integration tests
- [ ] Test with real data (all 3 geometry types)
- [ ] Update README.md
- [ ] Update API docstrings
- [ ] Update ARCHITECTURE.md
- [ ] Add migration guide

---

## Future Enhancements (Post-MVP)

### Fuzzy Matching Across Languages
- Search "Geneva" finds "Genève" and "Genf"
- Use transliteration or cross-language dictionary

### Historical Names
- Some features have STATUS='historisch' for old names
- Add temporal filtering

### Dialect Support
- Fine-grained dialects (Züritüütsch, Bärndütsch, etc.)
- Requires additional metadata not in current dataset

### Performance Optimization
- Pre-compute language indexes at load time
- Cache frequent queries
- Lazy-load name groups only when needed

---

## References

- **Technical Guide:** `swissNAMES3D_multilingual_technical_guide.md`
- **Current Implementation:** `geollm/datasources/swissnames3d.py`
- **Current Tests:** `tests/test_swissnames3d.py`
- **Data Source:** https://www.swisstopo.admin.ch/en/landscape-model-swissnames3d

---

## Questions & Decisions

### Decision Log

| Date | Question | Decision | Rationale |
|------|----------|----------|-----------|
| 2025-02-13 | Handle duplicates? | Yes, deduplicate by default | Current behavior (duplicates) is likely a bug |
| 2025-02-13 | Breaking change? | TBD | Need user feedback on impact |
| 2025-02-13 | Language codes? | Map German names to ISO | Real data uses German, not ISO codes |
| 2025-02-13 | API design? | `language` parameter on `search()` | Most flexible, backward compatible |

### Open Questions

1. **Should we support fuzzy cross-language search?**
   - Example: Search "Geneva" finds "Genève"
   - Requires transliteration or dictionary

2. **How to handle NAMEN_TYP='einfacher Name' with multiple language variants?**
   - Observed: Some "einfacher Name" entries still have duplicates
   - May be data quality issue

3. **Should STATUS='informell' be excluded by default?**
   - Technical guide suggests informal names shouldn't appear on official maps
   - Add `official_only=False` parameter?

4. **Cross-file name groups?**
   - Does same NAMENGRUPP appear across PKT/LIN/PLY files?
   - If yes, need cross-geometry-type deduplication

5. **English exonym support?**
   - Technical guide mentions "Geneva" (ENG) exists but isn't officially supported
   - Should we detect and handle English names?

---

**End of Document**
