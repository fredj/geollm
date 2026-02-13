"""
Geographic data source layer for resolving location names to geometries.

Provides a Protocol-based interface for data sources and a SwissNames3D implementation.
"""

from .protocol import GeoDataSource
from .swissnames3d import SwissNames3DSource

__all__ = [
    "GeoDataSource",
    "SwissNames3DSource",
]
