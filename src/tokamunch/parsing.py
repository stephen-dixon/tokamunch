"""Backward-compatibility shim. Canonical location: tokamunch.ids.parsing."""

from .ids.parsing import (  # noqa: F401
    concrete_path_to_schema_path,
    concrete_path_to_template,
    normalise_schema_segment,
    parse_concrete_path,
    parse_schema_path,
    render_array_length_query_path,
    render_concrete_path,
    render_schema_path,
)
