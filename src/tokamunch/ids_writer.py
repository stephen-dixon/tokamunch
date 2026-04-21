"""Backward-compatibility shim. Canonical location: tokamunch.ids.mutation."""

from .ids.mutation import (  # noqa: F401
    ensure_ids_arrays_resized,
    resize_and_set_ids_value,
    resolve_ids_parent,
    resolve_ids_segments,
    set_ids_value,
)
