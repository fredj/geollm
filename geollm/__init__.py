"""
GeoLLM - Natural Language Geographic Query Parsing

Parse location queries into structured geographic queries using LLM.
"""

# Main API
# Exceptions
from .exceptions import (
    GeoFilterError,
    LowConfidenceError,
    LowConfidenceWarning,
    ParsingError,
    UnknownRelationError,
    ValidationError,
)

# Models (for type hints and result access)
from .models import (
    BufferConfig,
    ConfidenceScore,
    GeoQuery,
    ReferenceLocation,
    SpatialRelation,
)
from .parser import GeoFilterParser

# Configuration
from .spatial_config import RelationConfig, SpatialRelationConfig

__all__ = [
    # Main API
    "GeoFilterParser",
    # Models
    "GeoQuery",
    "SpatialRelation",
    "ReferenceLocation",
    "BufferConfig",
    "ConfidenceScore",
    # Configuration
    "SpatialRelationConfig",
    "RelationConfig",
    # Exceptions
    "GeoFilterError",
    "ParsingError",
    "ValidationError",
    "UnknownRelationError",
    "LowConfidenceError",
    "LowConfidenceWarning",
]
