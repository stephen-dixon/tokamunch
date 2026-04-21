"""Backward-compatibility shim. Canonical location: tokamunch.io.outputs."""

from .io.outputs import (  # noqa: F401
    build_json_results,
    build_schema_map,
    format_value,
    make_json_safe,
    print_summary,
    render_text_records,
    render_text_schema_map,
    render_verbose_records,
    write_json_file,
)

_format_value = format_value  # backward-compat alias
