"""tokamunch: IMAS IDS mapping utilities.

Public API — import from here for stable, version-tracked names.
For internal implementation, import from the relevant subpackage:
  tokamunch.core.*      — config, context, selection, profiling
  tokamunch.ids.*       — IDS schema, path parsing, trie, helper, output
  tokamunch.mapping.*   — mapper creation, runner, data source interface
  tokamunch.io.*        — JSON/IMAS format conversion and output formatting
  tokamunch.plugins.*   — plugin protocol and registry
  tokamunch.cli.*       — CLI entry point and commands
"""

from . import plugins
from .core.config import (
    CLIConfig,
    ConcurrencyConfig,
    ConcurrencyMode,
    DataSourceConfig,
    MapperConfig,
    RunConfig,
    apply_config_overrides,
    load_cli_config,
)
from .core.context import MappingContext
from .core.selection import (
    IdsSelection,
    MultiPathSelection,
    Selection,
    SinglePathSelection,
)
from .ids.helper import IDSHelper
from .ids.imas_dd import generate_ids_paths
from .ids.mutation import (
    ensure_ids_arrays_resized,
    resize_and_set_ids_value,
    resolve_ids_parent,
    resolve_ids_segments,
    set_ids_value,
)
from .ids.parsing import (
    concrete_path_to_schema_path,
    concrete_path_to_template,
    normalise_schema_segment,
    parse_concrete_path,
    parse_schema_path,
    render_array_length_query_path,
    render_concrete_path,
    render_schema_path,
)
from .ids.path_expansion import expand_ids_path_trie, expand_ids_path_trie_segments
from .ids.templates import load_mapping_keys, merge_mapping_stubs
from .ids.trie import build_ids_path_trie, generate_schema_paths_from_trie
from .io.convert import (
    convert_file,
    read_ids_records,
    read_imas_records,
    read_json_records,
    records_to_ids_objects,
)
from .io.diff import diff_files, diff_records
from .mapping.data_source import TokamapInterface
from .mapping.mapper_factory import create_mapper_from_config
from .mapping.runner import collect_mapped_values
from .plugins.api import DataSource, DataSourceFactory, MapperProtocol
from .types import ExpansionContext, IDSNode, NodeType, TrieNode, WriteContext

__all__ = [
    "CLIConfig",
    "ConcurrencyConfig",
    "ConcurrencyMode",
    "DataSource",
    "DataSourceConfig",
    "DataSourceFactory",
    "ExpansionContext",
    "IDSHelper",
    "IDSNode",
    "IdsSelection",
    "MapperConfig",
    "MapperProtocol",
    "MappingContext",
    "MultiPathSelection",
    "NodeType",
    "RunConfig",
    "Selection",
    "SinglePathSelection",
    "TokamapInterface",
    "TrieNode",
    "WriteContext",
    "apply_config_overrides",
    "build_ids_path_trie",
    "collect_mapped_values",
    "concrete_path_to_schema_path",
    "concrete_path_to_template",
    "convert_file",
    "create_mapper_from_config",
    "diff_files",
    "diff_records",
    "ensure_ids_arrays_resized",
    "expand_ids_path_trie",
    "expand_ids_path_trie_segments",
    "generate_ids_paths",
    "generate_schema_paths_from_trie",
    "load_cli_config",
    "load_mapping_keys",
    "merge_mapping_stubs",
    "normalise_schema_segment",
    "parse_concrete_path",
    "parse_schema_path",
    "plugins",
    "read_ids_records",
    "read_imas_records",
    "read_json_records",
    "records_to_ids_objects",
    "render_array_length_query_path",
    "render_concrete_path",
    "render_schema_path",
    "resize_and_set_ids_value",
    "resolve_ids_parent",
    "resolve_ids_segments",
    "set_ids_value",
]
