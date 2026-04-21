"""Backward-compatibility shim. Canonical location: tokamunch.core.selection."""

from .core.selection import (  # noqa: F401
    IdsSelection,
    MultiPathSelection,
    Selection,
    SinglePathSelection,
    _included,
    generate_selected_paths,
    path_matches,
)
