"""Backward-compatibility shim. Canonical location: tokamunch.ids.imas_dd."""

from .ids.imas_dd import (  # noqa: F401
    generate_ids_paths,
    generate_ids_sub_paths,
    load_ids_field_metadata,
)
