# GeoLLM Architecture

## Core Principle

**GeoLLM has ONE responsibility: Extract geographic filters from natural language queries.**

### What GeoLLM Does ✅

- Parse spatial relations: "north of", "in", "near", "within 5km"
- Extract reference locations: "Lausanne", "Lake Geneva"
- Parse distance parameters: "within 5km", "2 kilometers"
- Return structured geographic filter criteria

### What GeoLLM Does NOT Do ❌

- Subject/feature identification ("hiking", "restaurants", "hotels")
- Attribute filtering ("with children", "vegetarian", "4-star")
- Search execution or result ranking
- Geometry resolution (future enhancement)

---

## Integration Pattern

GeoLLM is designed to work within larger search systems:

```
User Query: "Hiking with children north of Lausanne"
     ↓
Parent System → Extracts: Activity="Hiking", Audience="children"
     ↓
GeoLLM → Extracts: relation="north_of", location="Lausanne"
     ↓
Parent System → Combines: activity + audience + geo_filter
     ↓
Database Query → Results
```

**Example:** Outdoor Activity Search Engine

- Parent system: "Hiking with children" → activity filter
- GeoLLM: "north of Lausanne" → geographic filter
- Combined query: WHERE activity='hiking' AND audience='children' AND ST_Within(geom, north_of_lausanne)

---

## Component Overview

### 1. GeoFilterParser (Entry Point)

Main API class for parsing queries.

**Configuration:**

- LLM provider (OpenAI, Anthropic, local models)
- Spatial relation config
- Confidence threshold
- Strict/permissive mode

**Methods:**

- `parse(query: str) -> GeoQuery` - Parse single query
- `parse_batch(queries: List[str]) -> List[GeoQuery]` - Parse multiple
- `get_available_relations(category: Optional[str]) -> List[str]` - List relations
- `describe_relation(name: str) -> str` - Get relation description

### 2. LLM Integration

- **Model:** Configurable (default: GPT-4o with strict schema)
- **Prompt:** Multilingual input handling with few-shot examples
- **Output:** Structured Pydantic models with validation
- **Framework:** LangChain with structured output

### 3. Data Models (Pydantic v2)

```python
GeoQuery(
    query_type: str,                    # "simple" (future: "compound", etc)
    spatial_relation: SpatialRelation,
    reference_location: ReferenceLocation,
    buffer_config: Optional[BufferConfig],
    confidence_breakdown: ConfidenceScore,
    original_query: str
)

SpatialRelation(
    relation: str,                      # e.g., "north_of", "in", "near"
    category: str,                      # "containment", "buffer", "directional"
    description: str
)

ReferenceLocation(
    name: str,                          # Location name as mentioned in query
    type: str,                          # "city", "lake", "region" (optional)
    type_confidence: float,             # Confidence in type (0-1)
    parent_context: Optional[str]       # Parent location for disambiguation
)

BufferConfig(
    distance_m: int,                    # Positive (expand) or negative (erode)
    buffer_from: str,                   # "center" or "boundary"
    ring_only: bool                     # true for ring buffers
)

ConfidenceScore(
    overall: float,
    spatial_relation_confidence: float,
    reference_location_confidence: float,
    reasoning: str
)
```

### 4. Spatial Relations (12 Total)

#### Containment (2)

- `in` - Exact boundary matching

#### Buffer/Proximity (6)

- `near` - 5km radius from center
- `around` - 3km radius from center
- `on_shores_of` - 1km ring buffer around boundary
- `along` - 500m buffer along linear features
- `in_the_heart_of` - -500m erosion (central area)
- `deep_inside` - -1km erosion (deep interior)

#### Directional (8)

- **Cardinal**: `north_of`, `south_of`, `east_of`, `west_of` (10km, 90° sectors)
- **Diagonal**: `northeast_of`, `southeast_of`, `southwest_of`, `northwest_of` (10km, 90° sectors)

**Buffer Notes:**

- Positive buffers expand outward
- Negative buffers erode inward
- Ring buffers (`ring_only: true`) exclude the reference feature
- `buffer_from` determines whether buffer originates from center or boundary

### 5. Processing Pipeline

```
Raw Query Text
    ↓
LangChain LLM Call (with prompt + examples)
    ↓
Structured Output Parsing (Pydantic validation)
    ↓
Business Logic Validation
    ├─ Check relation is registered
    ├─ Apply default parameters
    └─ Check confidence thresholds
    ↓
Return GeoQuery (or raise error)
```

### 6. Validation

**Schema Validation:** Automatic via Pydantic

- Type checking
- Required field checking
- Format validation

**Business Logic Validation:**

- Is spatial_relation registered in config?
- Are required parameters present?
- Does confidence meet threshold?
- Strict vs permissive mode handling

---

## Error Handling

| Error | Cause | Response |
|-------|-------|----------|
| ParsingError | LLM failed to parse | Return error with raw response |
| ValidationError | Schema mismatch | Return validation error details |
| UnknownRelationError | Relation not registered | Return available relations |
| LowConfidenceError | Confidence below threshold (strict mode) | Raise or warn based on mode |

---

## Phase 1 Scope

**What's Implemented:**

- ✅ Natural language → GeoQuery (Pydantic model)
- ✅ Multilingual input handling
- ✅ 12 spatial relations
- ✅ Confidence scoring with reasoning
- ✅ Flexible configuration
- ✅ Comprehensive validation

**What's NOT Implemented (Future):**

- ❌ Geometry resolution (converting locations to polygons)
- ❌ Data source integration (SwissNames3D, OpenStreetMap)
- ❌ Complex query types (compound, boolean, nested)
- ❌ Target feature extraction (handled by parent system)

---

## Configuration Points

- LLM model selection and parameters
- Spatial relation defaults (distances, buffer settings)
- Confidence thresholds and mode (strict/permissive)
- Custom relation registration
- Language and localization

---

## Extension Points

- Add new spatial relations
- Configure existing relations (distances, angles)
- Custom validation rules
- Pre/post-processing hooks
- Language-specific handling
- Future: Complex query handlers

---

## Project Structure

```
geollm/
├── parser.py              # Main API entry point
├── models.py              # Pydantic models
├── spatial_config.py      # Relations registry (12 relations)
├── prompts.py            # LLM prompt templates
├── examples.py           # Few-shot examples (8, multilingual)
├── validators.py         # Validation pipeline
├── exceptions.py         # Error hierarchy
└── __init__.py          # Public exports
```

---

## Next Steps (Phase 2+)

When ready to expand:

1. Data source interface (abstract base)
2. SwissNames3D adapter (location resolution)
3. Query execution (geometric operations)
4. Result aggregation (geometry collection)
