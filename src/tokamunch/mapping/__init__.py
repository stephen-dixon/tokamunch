"""Mapping execution: expand IDS paths and dispatch to mapper backends."""

from .data_source import _MISSING_MAPPING_PREFIX, TokamapInterface, _decode_s1_bytes
from .mapper_factory import create_mapper_from_config
from .runner import (
    MappingRecord,
    MappingSummary,
    build_records,
    collect_mapped_values,
    map_path,
    map_serial,
    normalise_map_result,
    should_suppress_mapping_error,
)

_build_records = build_records  # backward-compat alias
_map_serial = map_serial  # backward-compat alias

__all__ = [
    "_MISSING_MAPPING_PREFIX",
    "MappingRecord",
    "MappingSummary",
    "TokamapInterface",
    "_decode_s1_bytes",
    "build_records",
    "collect_mapped_values",
    "create_mapper_from_config",
    "map_path",
    "map_serial",
    "normalise_map_result",
    "should_suppress_mapping_error",
]
