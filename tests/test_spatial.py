"""
Tests for spatial operations module.
"""

from shapely.geometry import LineString, Point, Polygon, mapping, shape

from etter.models import BufferConfig, SpatialRelation
from etter.spatial import apply_spatial_relation


def test_containment_polygon_passthrough():
    """Test that containment returns a polygon reference geometry unchanged."""
    geom = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    relation = SpatialRelation(relation="in", category="containment")

    result = apply_spatial_relation(geom, relation)
    assert result == geom


def test_containment_point_falls_back_to_buffer():
    """A point reference can't meaningfully "contain" anything; containment must
    fall back to a buffer instead of the (near-always-empty) unchanged point."""
    geom = {"type": "Point", "coordinates": [0, 0]}
    relation = SpatialRelation(relation="in", category="containment")

    result = apply_spatial_relation(geom, relation)

    assert result["type"] != "Point"
    result_shape = shape(result)
    assert result_shape.area > 0
    assert result_shape.contains(Point(0, 0))


def test_containment_linestring_falls_back_to_buffer():
    """A line reference falls back to a buffer covering its whole length, not just
    a buffer around its centroid/midpoint."""
    geom = {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 0.0]]}
    relation = SpatialRelation(relation="in", category="containment")

    result = apply_spatial_relation(geom, relation)

    assert result["type"] != "LineString"
    result_shape = shape(result)
    assert result_shape.area > 0
    # Buffered along the whole line, not just around the midpoint.
    assert result_shape.contains(Point(0.0, 0.0))
    assert result_shape.contains(Point(1.0, 0.0))


def test_around_buffer():
    """Test around relation produces a circular buffer from center."""
    geom = {"type": "Point", "coordinates": [0, 0]}
    relation = SpatialRelation(relation="around", category="buffer")
    config = BufferConfig(distance_m=111320, buffer_from="center", inferred=False)

    result = apply_spatial_relation(geom, relation, config)

    assert result["type"] == "Polygon"
    result_shape = shape(result)
    assert result_shape.contains(Point(0, 0))


def test_buffer_positive():
    """Test positive circular buffer."""
    geom = {"type": "Point", "coordinates": [0, 0]}  # Null island
    relation = SpatialRelation(relation="near", category="buffer")
    config = BufferConfig(distance_m=111320, buffer_from="center", inferred=False)  # ~1 degree at equator

    result = apply_spatial_relation(geom, relation, config)

    assert result["type"] == "Polygon"
    # Check bounding box approx (should be ~ +/- 1 degree)
    bounds = shape(result).bounds
    assert -1.1 < bounds[0] < -0.9  # Min X
    assert 0.9 < bounds[2] < 1.1  # Max X


def test_buffer_negative_erosion():
    """Test negative buffer (erosion)."""
    # 2x2 degree square
    poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
    geom = mapping(poly)

    relation = SpatialRelation(relation="in_the_heart_of", category="buffer")
    # Erode by ~0.5 degrees (~55km)
    config = BufferConfig(distance_m=-55000, buffer_from="boundary", inferred=False)

    result = apply_spatial_relation(geom, relation, config)

    assert result["type"] == "Polygon"
    area_orig = poly.area
    area_new = shape(result).area
    assert area_new < area_orig
    assert area_new > 0


def test_ring_buffer():
    """Test ring buffer (difference)."""
    geom = {"type": "Point", "coordinates": [0, 0]}
    relation = SpatialRelation(relation="on_shores_of", category="buffer")
    # Buffer 1 deg, but ring only? point has no area, so ring matches buffer
    # unless we use it on a polygon. Let's use a polygon.

    # 1x1 degree square
    poly = Polygon([(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)])
    geom = mapping(poly)

    config = BufferConfig(distance_m=100000, buffer_from="boundary", ring_only=True, inferred=False)

    result = apply_spatial_relation(geom, relation, config)

    res_shape = shape(result)
    assert res_shape.area > poly.area  # Should be larger total area
    assert not res_shape.contains(Point(0, 0))  # Should NOT contain center (hole)


def test_directional_sector():
    """Test directional sector generation."""
    geom = {"type": "Point", "coordinates": [0, 0]}
    relation = SpatialRelation(relation="north_of", category="directional")
    # North sector (0 degrees), 90 degree width
    config = BufferConfig(distance_m=100000, buffer_from="center", inferred=False)

    # Mocking the spatial config lookup inside apply_spatial_relation requires mocking
    # SpatialRelationConfig. Or we can rely on defaults if we didn't mock it?
    # The implementation instantiates SpatialRelationConfig() internally.
    # "north_of" is a built-in relation, so it should work.

    result = apply_spatial_relation(geom, relation, config)

    poly = shape(result)
    assert poly.contains(Point(0, 0.5))  # Point to North should be inside
    assert not poly.contains(Point(0, -0.5))  # Point to South should be outside
    assert not poly.contains(Point(0.5, 0))  # Point to East should be outside (45 deg boundary)


def test_left_side_buffer():
    """Test one-sided buffer on the left side of a line."""
    # Horizontal line going east (left side = north)
    line = LineString([(0, 0), (2, 0)])
    geom = mapping(line)

    relation = SpatialRelation(relation="left_bank", category="buffer")
    config = BufferConfig(distance_m=111320, buffer_from="boundary", side="left", inferred=False)  # ~1 degree

    result = apply_spatial_relation(geom, relation, config)

    result_shape = shape(result)
    assert not result_shape.is_empty
    # Left side of an eastward line is the north side
    assert result_shape.contains(Point(1, 0.5))  # North of line (left)
    assert not result_shape.contains(Point(1, -0.5))  # South of line (right)


def test_right_side_buffer():
    """Test one-sided buffer on the right side of a line."""
    # Horizontal line going east (right side = south)
    line = LineString([(0, 0), (2, 0)])
    geom = mapping(line)

    relation = SpatialRelation(relation="right_bank", category="buffer")
    config = BufferConfig(distance_m=111320, buffer_from="boundary", side="right", inferred=False)  # ~1 degree

    result = apply_spatial_relation(geom, relation, config)

    result_shape = shape(result)
    assert not result_shape.is_empty
    # Right side of an eastward line is the south side
    assert result_shape.contains(Point(1, -0.5))  # South of line (right)
    assert not result_shape.contains(Point(1, 0.5))  # North of line (left)


def test_clipping():
    """Test all four clipping directions produce the correct half of the reference geometry."""
    # 10x10 degree square centred at (5,5): lon 0-10, lat 0-10
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    geom = mapping(poly)

    cases = [
        ("northern_part_of", (0.0, 5.0, 10.0, 10.0)),
        ("southern_part_of", (0.0, 0.0, 10.0, 5.0)),
        ("eastern_part_of", (5.0, 0.0, 10.0, 10.0)),
        ("western_part_of", (0.0, 0.0, 5.0, 10.0)),
    ]
    for relation_name, expected_bounds in cases:
        relation = SpatialRelation(relation=relation_name, category="clipping")
        result = apply_spatial_relation(geom, relation)
        result_bounds = shape(result).bounds
        assert result_bounds == expected_bounds, (
            f"{relation_name}: expected bounds {expected_bounds}, got {result_bounds}"
        )
        # Clipped area should be exactly half the original
        assert abs(shape(result).area - poly.area / 2) < 1e-9


def test_side_none_symmetric_buffer():
    """Test that side=None preserves existing symmetric buffer behavior."""
    line = LineString([(0, 0), (2, 0)])
    geom = mapping(line)

    relation = SpatialRelation(relation="along", category="buffer")
    config = BufferConfig(distance_m=111320, buffer_from="boundary", side=None, inferred=False)  # ~1 degree

    result = apply_spatial_relation(geom, relation, config)

    result_shape = shape(result)
    assert not result_shape.is_empty
    # Symmetric buffer covers both sides
    assert result_shape.contains(Point(1, 0.5))  # North of line
    assert result_shape.contains(Point(1, -0.5))  # South of line


# --- list input (union) tests ---


def test_list_input_buffer_union():
    """Two line segments passed as a list produce the same buffer as the merged line."""
    seg1 = {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 0.0]]}
    seg2 = {"type": "LineString", "coordinates": [[1.0, 0.0], [2.0, 0.0]]}
    full = {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]}
    relation = SpatialRelation(relation="along", category="buffer")
    config = BufferConfig(distance_m=111320, buffer_from="boundary", inferred=False)

    result = shape(apply_spatial_relation([seg1, seg2], relation, config))
    reference = shape(apply_spatial_relation(full, relation, config))

    assert not result.is_empty
    assert abs(result.area - reference.area) / reference.area < 0.01


def test_list_input_single_matches_dict():
    """Single-element list gives the same result as passing the dict directly."""
    geom = {"type": "Point", "coordinates": [0.0, 0.0]}
    relation = SpatialRelation(relation="near", category="buffer")
    config = BufferConfig(distance_m=111320, buffer_from="center", inferred=False)

    assert shape(apply_spatial_relation(geom, relation, config)).equals_exact(
        shape(apply_spatial_relation([geom], relation, config)), tolerance=1e-10
    )


def test_list_input_empty_raises():
    """Empty list raises ValueError."""
    import pytest

    relation = SpatialRelation(relation="near", category="buffer")
    config = BufferConfig(distance_m=5000, buffer_from="center", inferred=False)
    with pytest.raises(ValueError, match="empty"):
        apply_spatial_relation([], relation, config)


def test_list_input_containment_union():
    """Multiple polygons passed as a list are unioned for containment."""
    poly1 = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    poly2 = {"type": "Polygon", "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]]}
    relation = SpatialRelation(relation="in", category="containment")

    result = shape(apply_spatial_relation([poly1, poly2], relation))

    assert result.contains(shape(poly1))
    assert result.contains(shape(poly2))
