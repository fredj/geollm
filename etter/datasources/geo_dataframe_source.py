"""Shared base for lazily-loaded, in-memory GeoDataFrame-backed geo datasources."""

from typing import TYPE_CHECKING

from geojson import Feature

from .location_types import fuzzy_search_index

if TYPE_CHECKING:
    import geopandas as gpd


class GeoDataFrameSource:
    """
    Shared lazy-loading, fuzzy-search, and by-id lookup behavior for datasources backed by
    an in-memory GeoDataFrame with a name/token index (SwissNames3DSource, IGNBDCartoSource,
    SwissBoundaries3DSource).

    Subclasses set ``self._gdf``, ``self._name_index``, ``self._token_index``, and
    ``self._id_col`` in ``__init__``, and implement ``_load_data()`` and ``_row_to_feature()``.
    """

    _gdf: "gpd.GeoDataFrame | None"
    _name_index: dict[str, list[int]]
    _token_index: dict[str, set[str]]
    _id_col: str | None

    def preload(self) -> None:
        """Eagerly load data. Call at startup to avoid first-query latency."""
        self._ensure_loaded()

    def _ensure_loaded(self) -> None:
        """Load data lazily on first access."""
        if self._gdf is not None:
            return
        self._load_data()

    def _load_data(self) -> None:
        raise NotImplementedError

    def _row_to_feature(self, idx: int) -> Feature:
        raise NotImplementedError

    def _fuzzy_search(self, normalized: str, threshold: float = 75.0) -> list[int]:
        return fuzzy_search_index(normalized, self._token_index, self._name_index, threshold)

    def get_by_id(self, feature_id: str) -> Feature | None:
        """
        Get a specific feature by its unique identifier.

        Args:
            feature_id: Unique identifier (e.g. a UUID, ``cleabs`` string, or row index).

        Returns:
            The matching GeoJSON Feature dict, or None if not found.
        """
        self._ensure_loaded()
        assert self._gdf is not None

        if self._id_col:
            matches = self._gdf[self._gdf[self._id_col].astype(str) == feature_id]
            if not matches.empty:
                return self._row_to_feature(matches.index[0])

        # Fallback: try as row index
        try:
            idx = int(feature_id)
            if 0 <= idx < len(self._gdf):
                return self._row_to_feature(idx)
        except ValueError:
            pass

        return None
