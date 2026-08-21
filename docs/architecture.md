# Architecture

tokamunch is organized into subpackages with clear responsibilities. Here is where to look for each concern.

## Directory structure

```
src/tokamunch/
  __init__.py          Public API re-exports
  types.py             Core data types (IDSNode, TrieNode, ExpansionContext, WriteContext)
  completions.py       Shell completion script generators

  cli/                 Command-line interface
    main.py            Entry point: main() function
    parser.py          Argparse wiring, shared argument helpers (add_common_arguments, etc.)
    common.py          Shared runtime helpers: config loading, context creation, error handling
    commands/          One file per subcommand
      map.py           munchi map
      paths.py         munchi paths
      convert.py       munchi convert
      init.py          munchi init-config, munchi init-mapping
      update.py        munchi update-mapping, munchi update
      check.py         munchi check
      diff.py          munchi diff
      completions.py   munchi completions

  core/                Runtime configuration and context
    config.py          CLIConfig, RunConfig, MapperConfig, load_cli_config
    context.py         MappingContext (holds mapper, device, shot, concurrency)
    selection.py       IdsSelection, SinglePathSelection, MultiPathSelection
    profiling.py       CallStats, ProfileData, render_profile_report
    checkpoint.py      Checkpoint save/load/apply for long runs
    checks.py          check_ids: validate IDS name and count schema paths

  ids/                 IDS schema, path manipulation, and IMAS data structures
    parsing.py         Path parsing and rendering (schema ↔ concrete ↔ template)
    trie.py            Schema trie construction and traversal
    path_expansion.py  Expand schema paths to concrete runtime paths
    imas_dd.py         Load IDS field lists from imas_data_dictionary
    helper.py          IDSHelper: convenient wrapper over trie + expansion
    mutation.py        IDS object traversal, array resizing, value assignment
    output.py          write_imas_output: write records to HDF5/NetCDF via imas-python
    templates.py       Mapping template generation and merging

  mapping/             Mapper backends and execution
    data_source.py     TokamapInterface: wraps libtokamap mapper for querying
    mapper_factory.py  create_mapper_from_config: build a libtokamap Mapper
    runner.py          collect_mapped_values: expand paths, dispatch to mapper, build records

  io/                  Format conversion and output formatting
    outputs.py         JSON serialization, text rendering, print_summary, write_json_file
    convert.py         read_json_records, read_imas_records, convert_file
    diff.py            diff_records, diff_files, render_diff

  plugins/             Plugin system for data source extensions
    api.py             MapperProtocol, DataSource, DataSourceFactory protocols
    registry.py        load_data_source_factory: discover plugins via entry_points
```

## Where to modify CLI behaviour

**Add/modify arguments for an existing command:**
Edit `cli/commands/<command>.py` → `register()` function.

**Add a new command:**
1. Create `cli/commands/<name>.py` with `register(subparsers)` and `run(args)` functions.
2. Import and call `register` in `cli/parser.py` → `build_parser()`.

**Shared argument patterns** (e.g. `--config`, `--ids`, `--force`):
Edit `cli/parser.py` → `add_*` helper functions.

**Shared runtime logic** (config loading, context creation, IMAS error handling):
Edit `cli/common.py`.

**Logging setup and top-level error handling:**
Edit `cli/main.py` → `main()`.

## Where mapping logic lives

The pipeline flows:

```
cli/commands/map.py
  → mapping/runner.py::collect_mapped_values
      Phase 1: core/selection.py::generate_selected_paths
                → ids/helper.py::IDSHelper.generate_concrete_paths
                → mapping/data_source.py::TokamapInterface.get_array_length
      Phase 2: mapping/runner.py::{map_serial, _map_threaded, _map_multiprocess}
                → mapping/data_source.py::TokamapInterface.map
```

- **Add a new concurrency backend:** `mapping/runner.py`
- **Change how errors are classified:** `mapping/runner.py::should_suppress_mapping_error`
- **Change array-length querying or mapper calling:** `mapping/data_source.py::TokamapInterface`
- **Change how the mapper is initialised:** `mapping/mapper_factory.py::create_mapper_from_config`

## Where IDS logic lives

- **Path parsing and rendering** (schema paths, concrete paths, template paths): `ids/parsing.py`
- **Trie construction and traversal**: `ids/trie.py`
- **Path expansion** (schema → concrete via array-length queries): `ids/path_expansion.py`
- **IDS schema introspection** (field lists from imas_data_dictionary): `ids/imas_dd.py`
- **High-level IDS helper** (wraps trie + expansion with caching): `ids/helper.py`
- **IDS object manipulation** (resize arrays, assign values, traverse): `ids/mutation.py`
- **Write mapped records to IMAS files**: `ids/output.py::write_imas_output`
- **Mapping template generation and merging**: `ids/templates.py`

## Where the plugin system lives

- **Protocols**: `plugins/api.py` — `MapperProtocol`, `DataSource`, `DataSourceFactory`
- **Discovery**: `plugins/registry.py` — `load_data_source_factory` (reads setuptools entry points under `tokamunch.data_sources`)
- **Registration**: `mapping/mapper_factory.py::create_mapper_from_config` — calls `mapper.register_python_data_source`

To add a new data source plugin, implement the `DataSource` protocol and register it as a `tokamunch.data_sources` entry point in your package's `pyproject.toml`.

## Where IO/output logic lives

- **JSON serialization** (`make_json_safe`, `build_json_results`, `write_json_file`): `io/outputs.py`
- **Text rendering** (`render_text_records`, `render_verbose_records`, `print_summary`): `io/outputs.py`
- **Format conversion** (JSON ↔ HDF5/NetCDF): `io/convert.py`
- **Diff** (compare two result sets or files): `io/diff.py`

## Backward-compatibility shims

All top-level module names that existed before the subpackage reorganisation are preserved as thin shim files (e.g. `tokamunch/config.py`, `tokamunch/selection.py`). These simply re-export from the canonical subpackage location and can be removed in a future major version.

The canonical import paths are the subpackages shown above.
