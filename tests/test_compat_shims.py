"""Backward-compatibility guarantees for the pre-refactor module layout.

The rest of the suite imports from the canonical locations
(``tokamunch.core.*``, ``tokamunch.ids.*``, ``tokamunch.io.*``,
``tokamunch.mapping.*``, ``tokamunch.plugins.*``).  This module is the only
place that exercises the flat shim modules kept for downstream code written
against the previous layout.

``LEGACY_API`` is the public surface each flat module exported before the
refactor.  Removing an entry is a breaking change for external callers — do
that deliberately, not by accident.
"""

from __future__ import annotations

import importlib

import pytest

LEGACY_API: dict[str, list[str]] = {
    "tokamunch.checkpoint": [
        "CHECKPOINT_VERSION",
        "Checkpoint",
        "apply_checkpoint",
        "load_checkpoint",
        "save_checkpoint",
    ],
    "tokamunch.checks": ["check_ids"],
    "tokamunch.cli": [
        "PATH_SYNTAX_EPILOG",
        "add_common_arguments",
        "add_force_argument",
        "add_ids_or_path_arguments",
        "add_match_argument",
        "add_verbose_errors_argument",
        "build_parser",
        "cmd_check",
        "cmd_completions",
        "cmd_convert",
        "cmd_diff",
        "cmd_init_config",
        "cmd_init_mapping",
        "cmd_map",
        "cmd_paths",
        "cmd_update",
        "cmd_update_mapping",
        "main",
    ],
    "tokamunch.config": [
        "CLIConfig",
        "ConcurrencyConfig",
        "ConcurrencyMode",
        "DataSourceConfig",
        "MapperConfig",
        "RunConfig",
        "apply_config_overrides",
        "load_cli_config",
        "render_cli_config_template",
    ],
    "tokamunch.context": ["MappingContext"],
    "tokamunch.convert": [
        "convert_file",
        "read_ids_records",
        "read_imas_records",
        "read_json_records",
        "records_to_ids_objects",
    ],
    "tokamunch.data_source_interface": ["TokamapInterface"],
    "tokamunch.diff": ["DiffEntry", "diff_files", "diff_records", "render_diff"],
    "tokamunch.ids_helper": ["IDSHelper"],
    "tokamunch.ids_writer": [
        "ensure_ids_arrays_resized",
        "resize_and_set_ids_value",
        "resolve_ids_parent",
        "resolve_ids_segments",
        "set_ids_value",
    ],
    "tokamunch.imas_dd": [
        "generate_ids_paths",
        "generate_ids_sub_paths",
        "load_ids_field_metadata",
    ],
    "tokamunch.mapper": ["create_mapper_from_config"],
    "tokamunch.mapping": [
        "MappingRecord",
        "MappingSummary",
        "collect_mapped_values",
        "map_path",
        "normalise_map_result",
        "should_suppress_mapping_error",
    ],
    "tokamunch.outputs": [
        "build_json_results",
        "build_schema_map",
        "make_json_safe",
        "print_summary",
        "render_text_records",
        "render_text_schema_map",
        "render_verbose_records",
        "write_json_file",
    ],
    "tokamunch.parsing": [
        "concrete_path_to_schema_path",
        "concrete_path_to_template",
        "normalise_schema_segment",
        "parse_concrete_path",
        "parse_schema_path",
        "render_array_length_query_path",
        "render_concrete_path",
        "render_concrete_segment",
        "render_schema_path",
        "render_schema_segment",
    ],
    "tokamunch.path_expansion": [
        "expand_ids_path_trie",
        "expand_ids_path_trie_segments",
    ],
    "tokamunch.plugin_api": ["DataSource", "DataSourceFactory", "MapperProtocol"],
    "tokamunch.plugins": ["load_data_source_factory"],
    "tokamunch.profiling": [
        "CallStats",
        "PhaseTimings",
        "ProfileData",
        "render_profile_report",
    ],
    "tokamunch.selection": [
        "IdsSelection",
        "MultiPathSelection",
        "SinglePathSelection",
        "generate_selected_paths",
        "path_matches",
    ],
    "tokamunch.templates": [
        "build_blank_mapping_template",
        "is_comment_stub",
        "load_mapping_keys",
        "merge_mapping_stubs",
    ],
    "tokamunch.trie": [
        "build_ids_path_trie",
        "generate_schema_paths_from_trie",
        "insert_path",
        "is_leaf_node",
    ],
    "tokamunch.write_ids": ["IdsWriteError", "SUPPORTED_SUFFIXES", "write_imas_output"],
}

# Private helpers that downstream code and older tests reached for, kept as
# aliases where the name became public during the refactor.
LEGACY_PRIVATE_ALIASES: dict[str, list[str]] = {
    "tokamunch.convert": ["_get_ids_leaf_value", "_ids_length_callback"],
    "tokamunch.data_source_interface": ["_MISSING_MAPPING_PREFIX", "_decode_s1_bytes"],
    "tokamunch.ids_helper": ["_build_cached_trie"],
    "tokamunch.mapping": ["_build_records", "_map_serial"],
    "tokamunch.outputs": ["_format_value"],
    "tokamunch.selection": ["_included"],
    "tokamunch.templates": ["_to_template_path"],
    "tokamunch.write_ids": ["_group_records_by_ids", "_imas_uri", "_populate_ids"],
}


@pytest.mark.parametrize("module_name", sorted(LEGACY_API))
def test_legacy_module_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


@pytest.mark.parametrize(
    ("module_name", "attr"),
    [(mod, attr) for mod, attrs in sorted(LEGACY_API.items()) for attr in attrs],
)
def test_legacy_module_exports_name(module_name: str, attr: str) -> None:
    module = importlib.import_module(module_name)
    assert hasattr(module, attr), f"{module_name}.{attr} was dropped by the refactor"


@pytest.mark.parametrize(
    ("module_name", "attr"),
    [
        (mod, attr)
        for mod, attrs in sorted(LEGACY_PRIVATE_ALIASES.items())
        for attr in attrs
    ],
)
def test_legacy_private_alias_kept(module_name: str, attr: str) -> None:
    module = importlib.import_module(module_name)
    assert hasattr(module, attr)


def test_shim_reexports_are_the_canonical_objects() -> None:
    """A shim must forward to the canonical implementation, not copy it."""
    import tokamunch.config as legacy_config
    import tokamunch.outputs as legacy_outputs
    import tokamunch.parsing as legacy_parsing
    import tokamunch.plugin_api as legacy_plugin_api
    from tokamunch.core.config import load_cli_config
    from tokamunch.ids.parsing import parse_schema_path
    from tokamunch.io.outputs import make_json_safe
    from tokamunch.plugins.api import DataSource

    assert legacy_config.load_cli_config is load_cli_config
    assert legacy_parsing.parse_schema_path is parse_schema_path
    assert legacy_outputs.make_json_safe is make_json_safe
    assert legacy_plugin_api.DataSource is DataSource


def test_plugin_api_reachable_as_package_attribute() -> None:
    """``import tokamunch; tokamunch.plugin_api`` worked before the refactor."""
    import tokamunch

    assert tokamunch.plugin_api is importlib.import_module("tokamunch.plugin_api")
    assert "plugin_api" in tokamunch.__all__
