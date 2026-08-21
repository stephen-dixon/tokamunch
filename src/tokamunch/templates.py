"""Backward-compatibility shim. Canonical location: tokamunch.ids.templates."""

from .ids.templates import (  # noqa: F401
    _to_template_path,
    build_blank_mapping_template,
    is_comment_stub,
    load_mapping_keys,
    merge_mapping_stubs,
)
