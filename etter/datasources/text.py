"""Shared text-normalization helper for datasource name matching."""

import unicodedata


def normalize_name(name: str) -> str:
    """Lowercase and strip diacritics (é→e, ü→u, etc.) for case-/accent-insensitive matching."""
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
