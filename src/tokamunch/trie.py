"""Backward-compatibility shim. Canonical location: tokamunch.ids.trie."""

from .ids.trie import (  # noqa: F401
    build_ids_path_trie,
    generate_schema_paths_from_trie,
    is_leaf_node,
)
