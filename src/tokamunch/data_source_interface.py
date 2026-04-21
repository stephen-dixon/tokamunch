"""Backward-compatibility shim. Canonical location: tokamunch.mapping.data_source."""

from .mapping.data_source import (  # noqa: F401
    _MISSING_MAPPING_PREFIX,
    TokamapInterface,
    _decode_s1_bytes,
)
