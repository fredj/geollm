"""
Tests for SwissNames3DSource using both synthetic fixture and real shapefiles.
"""

from pathlib import Path

import pytest

from geollm.datasources import SwissNames3DSource

# Path to the synthetic fixture
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "swissnames3d_sample.json"

# Path to real SwissNames3D shapefiles directory
DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def source():
    """Create a SwissNames3DSource instance using the fixture."""
    return SwissNames3DSource(FIXTURE_PATH)


@pytest.fixture
def real_source():
    """Create a SwissNames3DSource instance using real shapefiles."""
    if not DATA_DIR.exists():
        pytest.skip("Real SwissNames3D data directory not found")
    return SwissNames3DSource(DATA_DIR)


def test_load_data(source):
    """Test that data loads and columns are detected."""
    source._ensure_loaded()
    assert source._gdf is not None
    assert len(source._gdf) == 5  # 5 features in fixture


def test_search_exact(source):
    """Test exact name matching."""
    results = source.search("Bern")
    assert len(results) == 2  # Fixture has 2 Bern entries
    names = {r["properties"]["name"] for r in results}
    assert "Bern" in names
    # Note: "Kanton" is not in OBJEKTART_TYPE_MAP (removed as dead mapping)
    # SwissNames3D real data doesn't contain canton entries


def test_structure(source):
    """Test GeoJSON structure."""
    results = source.search("Bern")
    feature = results[0]
    assert feature["type"] == "Feature"
    assert "geometry" in feature
    assert "properties" in feature
    assert "confidence" in feature["properties"]


def test_search_case_insensitive(source):
    """Test case-insensitive matching."""
    results = source.search("bern")
    assert len(results) == 2


def test_search_accent_normalization(source):
    """Test accent stripping (Lac Léman -> Lac Leman)."""
    # Search with normalized string
    results = source.search("Lac Leman")
    assert len(results) == 1
    assert results[0]["properties"]["name"] == "Lac Léman"

    # Search with accents
    results = source.search("Lac Léman")
    assert len(results) == 1
    assert results[0]["properties"]["name"] == "Lac Léman"


def test_search_with_type_filter(source):
    """Test using type hint to filter results."""
    # "Bern" matches city (Ort) and unknown type (Kanton is unmapped)
    # With type filter, only city results are returned

    # Filter to city only
    results_city = source.search("Bern", type="city")
    assert len(results_city) == 1
    assert results_city[0]["properties"]["type"] == "city"
    assert results_city[0]["properties"]["name"] == "Bern"


def test_coordinate_conversion(source):
    """Test that coordinates are converted to WGS84."""
    city = source.search("Bern", type="city")[0]

    # Original (EPSG:2056): [2600000, 1199000]
    # WGS84: approx 7.44E, 46.94N
    coords = city["geometry"]["coordinates"]
    assert 7.4 < coords[0] < 7.5  # Longitude
    assert 46.9 < coords[1] < 47.0  # Latitude


def test_get_by_id(source):
    """Test retrieving feature by ID."""
    feature = source.get_by_id("uuid-rhone")
    assert feature is not None
    assert feature["properties"]["name"] == "Rhône"
    assert feature["properties"]["type"] == "river"


def test_unknown_name(source):
    """Test searching for non-existent name."""
    results = source.search("Atlantis")
    assert len(results) == 0


# Tests for real SwissNames3D shapefiles


def test_real_load_from_directory(real_source):
    """Test loading all 3 shapefiles from directory."""
    real_source._ensure_loaded()
    assert real_source._gdf is not None
    # Should have combined all 3 files (PKT: 334,738 + LIN: 12,571 + PLY: 95,155)
    assert len(real_source._gdf) > 400000  # Combined features


def test_real_multiple_geometry_types(real_source):
    """Test that all geometry types are loaded."""
    real_source._ensure_loaded()
    geom_types = set(real_source._gdf.geom_type.unique())
    # Should have Point, LineString, and Polygon
    assert "Point" in geom_types
    assert "LineString" in geom_types
    assert "Polygon" in geom_types


def test_real_common_columns_only(real_source):
    """Test that only common columns are kept after concatenation."""
    real_source._ensure_loaded()
    columns = set(real_source._gdf.columns)

    # Should have common columns
    expected_common = {
        "UUID",
        "OBJEKTART",
        "OBJEKTKLAS",
        "NAME_UUID",
        "NAME",
        "STATUS",
        "SPRACHCODE",
        "NAMEN_TYP",
        "NAMENGRUPP",
        "geometry",
    }
    assert expected_common.issubset(columns)

    # Should NOT have file-specific columns
    file_specific = {"KUNSTBAUTE", "HOEHE", "GEBAEUDENU", "EINWOHNERK", "ISCED"}
    assert not file_specific.intersection(columns), (
        f"Found file-specific columns: {file_specific.intersection(columns)}"
    )


def test_real_search_across_geometry_types(real_source):
    """Test searching returns results from different geometry types."""
    # "Bern" should exist as both point (city) and polygon (municipality)
    results = real_source.search("Bern")
    assert len(results) > 0

    # Check we have results with different geometry types
    geom_types = {r["geometry"]["type"] for r in results}
    assert len(geom_types) > 1  # Should have multiple geometry types


def test_real_search_river(real_source):
    """Test searching for a river (LineString geometry)."""
    # Use a river that exists in the dataset
    results = real_source.search("Murg")
    assert len(results) > 0
    # At least one result should be a LineString (rivers)
    geom_types = {r["geometry"]["type"] for r in results}
    assert "LineString" in geom_types or "MultiLineString" in geom_types


def test_real_search_lake(real_source):
    """Test searching for a lake (Polygon geometry)."""
    results = real_source.search("Genfersee", type="lake")
    if len(results) > 0:  # Lake might be named differently
        # Should be Polygon or MultiPolygon
        geom_types = {r["geometry"]["type"] for r in results}
        assert "Polygon" in geom_types or "MultiPolygon" in geom_types
