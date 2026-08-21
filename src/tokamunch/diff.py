"""Backward-compatibility shim. Canonical location: tokamunch.io.diff."""

from .io.diff import (  # noqa: F401
    DiffEntry,
    diff_files,
    diff_records,
    render_diff,
)
