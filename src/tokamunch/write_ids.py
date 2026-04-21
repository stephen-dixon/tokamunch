"""Backward-compatibility shim. Canonical location: tokamunch.ids.output."""

from .ids.output import (  # noqa: F401
    SUPPORTED_SUFFIXES,
    IdsWriteError,
    _derive_array_sizes,
    group_records_by_ids,
    imas_uri,
    populate_ids,
    write_imas_output,
)

_group_records_by_ids = group_records_by_ids  # backward-compat alias
_imas_uri = imas_uri  # backward-compat alias
_populate_ids = populate_ids  # backward-compat alias
