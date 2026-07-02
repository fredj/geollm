"""
Tests for SwissBoundaries3DSource using both synthetic fixture and real shapefiles.
"""

from pathlib import Path

import pytest

from etter.datasources import SwissBoundaries3DSource

# Path to the synthetic fixture
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "swissboundaries3d_sample.json"

# Path to real SwissBoundaries3D shapefiles directory
DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def source():
    """Create a SwissBoundaries3DSource instance using the fixture."""
    return SwissBoundaries3DSource(FIXTURE_PATH)


@pytest.fixture(scope="module")
def real_source():
    """Create a SwissBoundaries3DSource instance using real shapefiles (loaded once per module — tests must not mutate it)."""
    if not DATA_DIR.exists():
        pytest.skip("Real SwissBoundaries3D data directory not found")
    # Check for at least one of the expected shapefiles
    expected = [
        "swissBOUNDARIES3D_1_5_TLM_BEZIRKSGEBIET.shp",
        "swissBOUNDARIES3D_1_5_TLM_HOHEITSGEBIET.shp",
        "swissBOUNDARIES3D_1_5_TLM_KANTONSGEBIET.shp",
    ]
    if not any((DATA_DIR / f).exists() for f in expected):
        pytest.skip("SwissBoundaries3D shapefiles not found in data directory")
    return SwissBoundaries3DSource(DATA_DIR)


def test_load_data(source):
    """Test that data loads and columns are detected."""
    source._ensure_loaded()
    assert source._gdf is not None
    assert len(source._gdf) == 5  # 5 features in fixture


def test_search_exact(source):
    """Test exact name matching."""
    results = source.search("Bern")
    assert len(results) == 2  # Fixture has 2 Bern entries (canton + district)
    names = {r["properties"]["name"] for r in results}
    assert "Bern" in names


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
    """Test accent stripping (Zürich -> Zurich)."""
    results = source.search("Zurich")
    assert len(results) == 2  # canton + municipality
    names = {r["properties"]["name"] for r in results}
    assert "Zürich" in names

    results = source.search("Zürich")
    assert len(results) == 2
    names = {r["properties"]["name"] for r in results}
    assert "Zürich" in names


def test_search_with_type_filter(source):
    """Test using type hint to filter results."""
    results_canton = source.search("Bern", type="canton")
    assert len(results_canton) == 1
    assert results_canton[0]["properties"]["type"] == "canton"
    assert results_canton[0]["properties"]["name"] == "Bern"


def test_coordinate_conversion(source):
    """Test that coordinates are converted to WGS84."""
    canton = source.search("Bern", type="canton")[0]

    # Original (EPSG:2056): [2600000, 1200000] center of the polygon
    # WGS84: approx 7.44E, 46.94N
    geom = canton["geometry"]
    assert geom["type"] == "Polygon"


def test_get_by_id(source):
    """Test retrieving feature by ID."""
    feature = source.get_by_id("uuid-district-bern")
    assert feature is not None
    assert feature["properties"]["name"] == "Bern"
    assert feature["properties"]["type"] == "district"


def test_unknown_name(source):
    """Test searching for non-existent name."""
    results = source.search("Atlantis")
    assert len(results) == 0


def test_search_type_category_expansion(source):
    """Test that a category type hint expands to all concrete types within that category.

    Searching with type='administrative' should match features whose concrete type
    is in the administrative hierarchy (canton, municipality).
    Note: district is in the 'settlement' category, not 'administrative'.
    """
    results_canton = source.search("Bern", type="administrative")
    assert len(results_canton) == 1, "Category hint 'administrative' should match canton"
    assert results_canton[0]["properties"]["type"] == "canton"

    results_zh = source.search("Zürich", type="administrative")
    assert len(results_zh) == 2, "Category hint 'administrative' should match canton and municipality"
    types = {r["properties"]["type"] for r in results_zh}
    assert types == {"canton", "municipality"}

    results_settlement = source.search("Bern", type="settlement")
    assert len(results_settlement) == 1, "Category hint 'settlement' should match district"
    assert results_settlement[0]["properties"]["type"] == "district"


def test_search_type_exact_still_works(source):
    """Test that an exact concrete type still filters correctly after hierarchy change."""
    results = source.search("Bern", type="canton")
    assert len(results) == 1
    assert results[0]["properties"]["type"] == "canton"

    results_none = source.search("Bern", type="lake")
    assert len(results_none) == 0


def test_municipality_search(source):
    """Test searching for municipality features."""
    results = source.search("Thun", type="municipality")
    assert len(results) == 1
    assert results[0]["properties"]["type"] == "municipality"
    assert results[0]["properties"]["name"] == "Thun"


# Tests for real SwissBoundaries3D shapefiles


def test_real_load_from_directory(real_source):
    """Test loading all 3 shapefiles from directory."""
    real_source._ensure_loaded()
    assert real_source._gdf is not None
    # Should have combined all 3 files
    assert len(real_source._gdf) > 0


def test_real_common_columns_only(real_source):
    """Test that only common columns are kept after concatenation."""
    real_source._ensure_loaded()
    columns = set(real_source._gdf.columns)

    # Should have common columns
    expected_common = {
        "UUID",
        "OBJEKTART",
        "NAME",
        "geometry",
    }
    assert expected_common.issubset(columns)


def test_real_search_canton(real_source):
    """Test searching for a canton."""
    results = real_source.search("Bern", type="canton")
    assert len(results) > 0
    for result in results:
        assert result["properties"]["type"] == "canton"


def test_real_search_municipality(real_source):
    """Test searching for a municipality."""
    results = real_source.search("Thun", type="municipality")
    if len(results) > 0:
        for result in results:
            assert result["properties"]["type"] == "municipality"
