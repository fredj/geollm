# Spatial Relations

etter supports 21 built-in spatial relations across four categories.

## Containment

| Relation | Behavior | Default distance |
|----------|----------|-----------------|
| `in` | Exact geometry match — passthrough | — |

**Example:** `"restaurants in Geneva"` → returns Geneva's boundary polygon as-is.

## Buffer / Proximity

| Relation | Behavior | Default distance |
|----------|----------|-----------------|
| `around` | Circular buffer from centroid | 1 km |
| `near` | Circular buffer from centroid | 5 km |
| `along` | Linear buffer along a feature | 500 m |
| `left_bank` | Left bank of a linear feature (relative to flow direction) | 500 m |
| `right_bank` | Right bank of a linear feature (relative to flow direction) | 500 m |
| `on_shores_of` | Ring buffer around a water boundary, excluding the water body | 1 km ring |
| `in_the_heart_of` | Negative buffer (erosion) toward center | −500 m |
| `bordering` | Thin ring just outside the reference boundary, for land-border adjacency | 2 km ring |

**One-sided buffers:** `left_bank` and `right_bank` produce a buffer on a single side of a linear feature (river, road) relative to its direction of flow.

**Ring buffer:** `on_shores_of` and `bordering` use `ring_only=True` — the reference geometry itself is subtracted, leaving only the surrounding ring.

**Example:** `"cities bordering Germany"` → 2 km ring just outside Germany's boundary, excluding Germany itself.

## Clipping

Clipping relations clip the reference geometry to a directional half-plane. They answer *"what is in the northern/southern/eastern/western portion of X?"* — as opposed to directional relations, which answer *"what is north/south/east/west of X?"*.

| Relation | Behavior |
|----------|----------|
| `northern_part_of` | Clip reference geometry to its northern bbox half (above midpoint latitude) |
| `southern_part_of` | Clip reference geometry to its southern bbox half (below midpoint latitude) |
| `eastern_part_of` | Clip reference geometry to its eastern bbox half (right of midpoint longitude) |
| `western_part_of` | Clip reference geometry to its western bbox half (left of midpoint longitude) |

**Example:** `"ski resorts in the northern part of Switzerland"` → Switzerland's polygon clipped to the area north of its bbox midpoint.

## Directional

All directional relations produce a 90° sector wedge extending outward from the reference geometry centroid.

| Relation | Direction | Default radius |
|----------|-----------|---------------|
| `north_of` | 0° | 10 km |
| `northeast_of` | 45° | 10 km |
| `east_of` | 90° | 10 km |
| `southeast_of` | 135° | 10 km |
| `south_of` | 180° | 10 km |
| `southwest_of` | 225° | 10 km |
| `west_of` | 270° | 10 km |
| `northwest_of` | 315° | 10 km |

**Example:** `"5km north of Lausanne"` → 90° sector polygon extending 5km north from Lausanne's centroid.

## Area-Based Distance Inference

The "Default distance" values above only apply when `buffer_config.inferred=False` (an explicit distance was set, e.g. from `SpatialRelation.explicit_distance`, "within 5km", "30 min walk"). When `inferred=True` — no explicit distance in the query — `apply_spatial_relation()` computes the geodesic area of the reference geometry (via `pyproj.Geod`) and picks a distance from area-based brackets instead:

| Geometry area | Proximity default | Erosion default |
|---|---|---|
| < 1 km² (point, station) | 500 m | −200 m |
| 1–50 km² (town, small lake) | 1 500 m | −500 m |
| 50–500 km² (city, medium region) | 5 000 m | −1 000 m |
| ≥ 500 km² (canton, country) | 15 000 m | −2 000 m |

This means the same relation (e.g. `near`) produces a smaller buffer around a village than around a canton, when the query doesn't state a distance explicitly.

## Registering Custom Relations

```python
from etter import SpatialRelationConfig, RelationConfig

config = SpatialRelationConfig()
config.register_relation(RelationConfig(
    name="close_to",
    category="buffer",
    description="Very close proximity, under 1km",
    default_distance_m=1000,
    buffer_from="center",
))
```

See [`SpatialRelationConfig`](../api/etter.html#SpatialRelationConfig) and [`RelationConfig`](../api/etter.html#RelationConfig) for all available options.

## Output Geometry Format

By default `apply_spatial_relation()` returns a GeoJSON geometry dict. Use the `geometry_format` parameter to request WKT or WKB instead:

```python
from etter import apply_spatial_relation
from etter.models import SpatialRelation, BufferConfig

geometry = datasource.search("Lausanne")[0]["geometry"]

# GeoJSON dict (default)
result = apply_spatial_relation(geometry, relation, buffer_config)

# WKT string
result_wkt = apply_spatial_relation(geometry, relation, buffer_config, geometry_format="wkt")

# WKB hex string
result_wkb = apply_spatial_relation(geometry, relation, buffer_config, geometry_format="wkb")
```

To convert raw datasource feature dicts, use `convert_feature_geometry()`:

```python
from etter import convert_feature_geometry

feature = datasource.search("Lausanne")[0]
feature_wkt = convert_feature_geometry(feature, "wkt")
# feature_wkt["geometry"] is now a WKT string
```


## Querying Available Relations

```python
# All relations
parser.get_available_relations()

# By category
parser.get_available_relations(category="directional")

# Description of a specific relation
parser.describe_relation("on_shores_of")
```
