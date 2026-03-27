from __future__ import annotations

import argparse
import cProfile
import logging
import sys
import time
from pathlib import Path

from .checks import check_ids
from .config import CLIConfig, ConcurrencyConfig, ConcurrencyMode, render_cli_config_template
from .context import MappingContext
from .convert import convert_file
from .mapping import collect_mapped_values
from .outputs import (
    build_json_results,
    build_schema_map,
    print_summary,
    render_text_records,
    render_text_schema_map,
    write_json_file,
)
from .selection import IdsSelection, MultiPathSelection, SinglePathSelection, path_matches
from .templates import build_blank_mapping_template, load_mapping_keys
from .write_ids import SUPPORTED_SUFFIXES, IdsWriteError, write_imas_output

logger = logging.getLogger(__name__)

PATH_SYNTAX_EPILOG = """Path syntax:
  Concrete runtime path:
    magnetics/flux_loop[0]/position[0]/r

  Non-concrete IDS/schema path:
    magnetics/flux_loop(:)/position(:)/r

  Mapping-template path:
    magnetics/flux_loop[#]/position[#]/r

Notes:
  - 'map --path' expects one concrete path.
  - 'map --ids magnetics' expands all concrete paths for that IDS.
  - '--match' filters expanded concrete paths, e.g. 'magnetics/flux_loop*'.
  - '--mapping' restricts paths to those present in a mapping JSON file.
"""


def _apply_log_level(cli_override: str | None, cfg: CLIConfig | None) -> None:
    """Set the root logger level from config, unless the CLI flag was given.

    ``basicConfig`` in ``main()`` always runs first (at WARNING), so this only
    needs to call ``setLevel`` when a different level is required.
    """
    if cli_override is not None:
        return  # already applied in main()
    if cfg is not None:
        logging.getLogger().setLevel(cfg.run.log_level)


def _apply_concurrency_overrides(args: argparse.Namespace, ctx: MappingContext) -> None:
    """Patch ctx.concurrency with any CLI overrides for mode or workers."""
    raw_mode = getattr(args, "concurrency_mode", None)
    raw_workers = getattr(args, "workers", None)
    mode = ConcurrencyMode(raw_mode) if raw_mode is not None else ctx.concurrency.mode
    workers = raw_workers if raw_workers is not None else ctx.concurrency.workers
    if mode is not ctx.concurrency.mode or workers != ctx.concurrency.workers:
        ctx.concurrency = ConcurrencyConfig(mode=mode, workers=workers)
        logger.debug("Concurrency overridden: mode=%s workers=%d", mode.value, workers)


def _resolve_binary_arrays(cli_flag: bool, cfg: CLIConfig | None) -> bool:
    """Return effective binary_arrays setting: CLI flag wins when True."""
    if cli_flag:
        return True
    if cfg is not None:
        return cfg.run.binary_arrays
    return False


def _resolve_on_imas_error(cli_override: str | None, cfg: CLIConfig | None) -> str:
    """Return effective on_imas_error setting: CLI override wins when given."""
    if cli_override is not None:
        return cli_override
    if cfg is not None:
        return cfg.run.on_imas_error
    return "fallback-json"


def _handle_imas_write_errors(
    errors: list[IdsWriteError],
    output_path: Path,
    on_imas_error: str,
    *,
    binary_arrays: bool,
) -> None:
    """Log errors from write_imas_output and apply the configured error strategy."""
    for err in errors:
        msg = f"IDS '{err.ids_name}' failed to write: {err.cause}"
        logger.error(msg)
        print(f"ERROR: {msg}", file=sys.stderr)

    if on_imas_error == "raise":
        raise RuntimeError(
            f"{len(errors)} IDS(es) could not be written to {output_path}. "
            "See log for details."
        )

    # fallback-json: write the failed IDS records to a companion JSON file.
    fallback_path = output_path.with_name(output_path.stem + "_fallback.json")
    fallback_records = [r for err in errors for r in err.records]
    write_json_file(
        fallback_path,
        build_json_results(fallback_records, binary_arrays=binary_arrays),
        force=True,
    )
    print(
        f"Fallback JSON for {len(errors)} failed IDS(es) written to {fallback_path}",
        file=sys.stderr,
    )


def _resolve_paths_arg(values: list[str]) -> list[str]:
    """Return a list of concrete paths from the ``--paths`` argument.

    If exactly one value is given and it names an existing file, the file is
    read and its non-empty, non-comment lines are returned as paths.  Otherwise
    the values themselves are used directly.
    """
    if len(values) == 1:
        candidate = Path(values[0])
        if candidate.is_file():
            paths = [
                line.strip()
                for line in candidate.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            logger.debug("Read %d paths from %s", len(paths), candidate)
            return paths
    return values


def cmd_paths(args: argparse.Namespace) -> int:
    import tqdm as tqdm_mod

    if args.output is not None:
        output_path = Path(args.output)
        if output_path.suffix.lower() != ".json":
            raise ValueError(
                f"Unsupported output file extension for {output_path!s}. Use .json."
            )

    ctx = MappingContext.from_config(args.config, device=args.device, shot=args.shot)
    _apply_log_level(args.log_level, ctx.cli_config)
    logger.info("Loaded config: device=%s shot=%s", ctx.device, ctx.shot)
    helper = ctx.ids_helper(args.ids)

    # Use the number of schema leaf paths as an approximate total for the progress
    # bar. Concrete paths may exceed this when array structs expand to multiple
    # elements, so the percentage can exceed 100 % — this is expected.
    schema_leaf_count = sum(1 for _ in helper.generate_non_concrete_paths(leaves_only=True))

    t0 = time.perf_counter()
    concrete_paths: list[str] = []
    disable_bar = not sys.stderr.isatty()
    with tqdm_mod.tqdm(
        total=schema_leaf_count,
        desc="Expanding",
        unit="path",
        disable=disable_bar,
        file=sys.stderr,
    ) as bar:
        for path in helper.generate_concrete_paths(
            ctx.tokamap.get_array_length,
            leaves_only=args.leaves_only,
        ):
            bar.update(1)
            if path_matches(path, args.match):
                concrete_paths.append(path)

    elapsed = time.perf_counter() - t0
    logger.info("Found %d concrete paths for IDS '%s'", len(concrete_paths), args.ids)
    print(
        f"Paths: {len(concrete_paths)} concrete paths in {elapsed:.2f}s.",
        file=sys.stderr,
    )

    if args.schema_map:
        schema_map = build_schema_map(concrete_paths)
        if args.output is not None:
            write_json_file(Path(args.output), schema_map, force=args.force)
            print(f"Wrote schema map to {args.output}")
        else:
            text = render_text_schema_map(schema_map)
            if text:
                print(text)
    else:
        if args.output is not None:
            write_json_file(Path(args.output), concrete_paths, force=args.force)
            print(f"Wrote paths to {args.output}")
        elif concrete_paths:
            print("\n".join(concrete_paths))

    return 0


def cmd_map(args: argparse.Namespace) -> int:
    import tqdm as tqdm_mod

    from .profiling import ProfileData, render_profile_report

    if args.output is not None:
        output_path = Path(args.output)
        if output_path.suffix.lower() not in {".json", *SUPPORTED_SUFFIXES}:
            raise ValueError(
                f"Unsupported output file extension for {output_path!s}. "
                "Use no --output for terminal text, .json for JSON, "
                ".h5 for HDF5, or .nc for NetCDF."
            )

    ctx = MappingContext.from_config(args.config, device=args.device, shot=args.shot)
    _apply_log_level(args.log_level, ctx.cli_config)
    _apply_concurrency_overrides(args, ctx)
    logger.info("Loaded config: device=%s shot=%s", ctx.device, ctx.shot)

    binary_arrays = _resolve_binary_arrays(args.binary_arrays, ctx.cli_config)
    on_imas_error = _resolve_on_imas_error(
        getattr(args, "on_imas_error", None), ctx.cli_config
    )
    dry_run: bool = getattr(args, "dry_run", False)
    limit: int | None = getattr(args, "limit", None)
    profile_stats: bool = getattr(args, "profile_stats", False)
    profile_file: str | None = getattr(args, "profile", None)

    mapping_keys = load_mapping_keys(Path(args.mapping)) if args.mapping else None

    selection: IdsSelection | SinglePathSelection | MultiPathSelection
    if args.path is not None:
        selection = SinglePathSelection(path=args.path, mapping_keys=mapping_keys)
    elif args.paths is not None:
        resolved = _resolve_paths_arg(args.paths)
        logger.info("Selected %d explicit paths", len(resolved))
        selection = MultiPathSelection(paths=resolved, mapping_keys=mapping_keys)
    else:
        selection = IdsSelection(
            ids=args.ids,
            match=args.match,
            leaves_only=args.leaves_only,
            mapping_keys=mapping_keys,
        )

    profile_data = ProfileData() if (profile_stats or profile_file) else None

    # The bar is created with total=None (indeterminate) during path expansion,
    # then switched to the exact count once phase 1 completes and mapping begins.
    disable_bar = not sys.stderr.isatty()

    profiler = cProfile.Profile() if profile_file else None
    if profiler is not None:
        profiler.enable()

    t0_wall = time.perf_counter()
    with tqdm_mod.tqdm(
        total=None,
        desc="Expanding paths",
        unit="path",
        disable=disable_bar,
        file=sys.stderr,
    ) as bar:

        def _on_path_expanded(n: int) -> None:
            # Called by collect_mapped_values once it knows the full path list,
            # before mapping starts: set the exact total and switch description.
            if dry_run:
                bar.reset(total=n)
                bar.set_description("Dry run")
            else:
                bar.reset(total=n)
                bar.set_description("Mapping")

        def _on_path_mapped(n: int) -> None:
            bar.update(n)

        records, summary = collect_mapped_values(
            ctx,
            selection,
            verbose_errors=args.verbose_errors,
            on_paths_ready=_on_path_expanded,
            progress_callback=_on_path_mapped,
            profile=profile_data,
            dry_run=dry_run,
            limit=limit,
        )

    if profiler is not None:
        profiler.disable()
        profiler.dump_stats(profile_file)  # type: ignore[arg-type]
        print(f"cProfile stats written to {profile_file}", file=sys.stderr)
        print(
            f"  Inspect with: python -m pstats {profile_file}  "
            f"or  snakeviz {profile_file}",
            file=sys.stderr,
        )

    total_wall = time.perf_counter() - t0_wall
    if profile_data is not None:
        # Attribute any remaining wall time to output phase when writing below.
        _profile_data = profile_data
        _t_before_output = time.perf_counter()
    else:
        _profile_data = None
        _t_before_output = 0.0

    logger.info(
        "Results: mapped=%d none=%d suppressed=%d errors=%d",
        summary.mapped,
        summary.returned_none,
        summary.suppressed_errors,
        summary.unexpected_errors,
    )

    if dry_run:
        print(
            f"Dry run: {len(records)} paths expanded in {summary.elapsed_s:.2f}s "
            "(no mapper calls made).",
            file=sys.stderr,
        )
        if profile_stats and profile_data is not None:
            print(render_profile_report(profile_data, total_wall), file=sys.stderr)
        return 0

    if args.output is None:
        text = render_text_records(records, verbose_errors=args.verbose_errors)
        if text:
            print(text)
        print_summary(summary)
        if profile_stats and profile_data is not None:
            print(render_profile_report(profile_data, total_wall), file=sys.stderr)
        return 1 if summary.has_unexpected_errors else 0

    output_path = Path(args.output)
    suffix = output_path.suffix.lower()

    if suffix == ".json":
        write_json_file(
            output_path,
            build_json_results(records, binary_arrays=binary_arrays),
            force=args.force,
        )
        if _profile_data is not None:
            _profile_data.phases.output_s = time.perf_counter() - _t_before_output
        print(f"Wrote JSON output to {output_path}")
        print_summary(summary)
        if profile_stats and profile_data is not None:
            print(render_profile_report(profile_data, total_wall), file=sys.stderr)
        return 1 if summary.has_unexpected_errors else 0

    # suffix in SUPPORTED_SUFFIXES (already validated above)
    write_errors = write_imas_output(output_path, records=records, force=args.force)
    if _profile_data is not None:
        _profile_data.phases.output_s = time.perf_counter() - _t_before_output
    print(f"Wrote {output_path.suffix.upper()[1:]} output to {output_path}")
    if write_errors:
        _handle_imas_write_errors(
            write_errors, output_path, on_imas_error, binary_arrays=binary_arrays
        )
    print_summary(summary)
    if profile_stats and profile_data is not None:
        print(render_profile_report(profile_data, total_wall), file=sys.stderr)
    return 1 if (summary.has_unexpected_errors or write_errors) else 0


def cmd_convert(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)

    binary_arrays = _resolve_binary_arrays(args.binary_arrays, None)
    on_imas_error = _resolve_on_imas_error(
        getattr(args, "on_imas_error", None), None
    )

    write_errors = convert_file(
        input_path,
        output_path,
        ids_names=args.ids or None,
        force=args.force,
        binary_arrays=binary_arrays,
        on_imas_error=on_imas_error,
    )

    print(f"Converted {input_path} → {output_path}")

    if write_errors:
        _handle_imas_write_errors(
            write_errors, output_path, on_imas_error, binary_arrays=binary_arrays
        )
        return 1

    return 0


def cmd_init_config(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite existing file: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_cli_config_template(), encoding="utf-8")
    print(f"Wrote skeleton config to {output_path}")
    return 0


def cmd_init_mapping(args: argparse.Namespace) -> int:
    mapping = build_blank_mapping_template(
        args.ids,
        leaves_only=args.leaves_only,
    )
    output_path = Path(args.output)
    write_json_file(output_path, mapping, force=args.force)
    print(f"Wrote blank mapping template to {output_path}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    ctx = MappingContext.from_config(args.config, device=args.device, shot=args.shot)
    _apply_log_level(args.log_level, ctx.cli_config)
    print("Config loaded successfully.")
    print(f"Device: {ctx.device}")
    print(f"Shot: {ctx.shot}")

    if args.ids:
        count = check_ids(args.ids, leaves_only=args.leaves_only)
        print(f"IDS recognised: {args.ids}")
        print(f"Schema paths found: {count}")

    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=str,
        default="munchi.toml",
        help="munchi config file",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Override device from config",
    )
    parser.add_argument(
        "--shot",
        type=int,
        default=None,
        help="Override shot from config",
    )
    parser.add_argument(
        "--leaves-only",
        action="store_true",
        help="Only include leaf paths",
    )


def add_match_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--match",
        type=str,
        default=None,
        help="Glob-style filter applied to expanded concrete runtime paths, e.g. 'magnetics/flux_loop*'",
    )


def add_ids_or_path_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--ids",
        type=str,
        help="IDS name to expand into concrete runtime paths, e.g. 'magnetics'",
    )
    group.add_argument(
        "--path",
        type=str,
        help="Single concrete runtime path, e.g. 'magnetics/flux_loop[0]/position[0]/r'",
    )
    group.add_argument(
        "--paths",
        nargs="+",
        metavar="PATH_OR_FILE",
        help=(
            "One or more concrete runtime paths, or a single path to a text file "
            "containing newline-delimited paths (lines starting with '#' are ignored)"
        ),
    )


def add_force_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists",
    )


def add_verbose_errors_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--verbose-errors",
        action="store_true",
        help="Show suppressed 'missing mapping' errors as well",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="munchi",
        description="IDS mapping CLI",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity; overrides log_level in config (default: WARNING)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="FILE",
        help="Write log output to FILE in addition to (or instead of) the console",
    )
    parser.add_argument(
        "--log-file-level",
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Verbosity for the file log sink (default: DEBUG)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_paths = subparsers.add_parser(
        "paths",
        help="Expand and print concrete IDS runtime paths",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser_paths)
    parser_paths.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name to expand, e.g. 'magnetics'",
    )
    add_match_argument(parser_paths)
    parser_paths.add_argument(
        "--schema-map",
        action="store_true",
        help=(
            "Show each schema path ((:) notation) alongside the concrete path(s) "
            "it expands to. Console: 'schema -> concrete' lines. "
            "JSON: {schema_path: [concrete_path, ...]}."
        ),
    )
    parser_paths.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write output to a JSON file instead of printing to the console",
    )
    add_force_argument(parser_paths)
    parser_paths.set_defaults(func=cmd_paths)

    parser_map = subparsers.add_parser(
        "map",
        help="Map one concrete path or all concrete paths of an IDS",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser_map)
    add_ids_or_path_arguments(parser_map)
    add_match_argument(parser_map)
    add_force_argument(parser_map)
    add_verbose_errors_argument(parser_map)
    parser_map.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output destination. Default: terminal text. Use .json for JSON, .h5 for HDF5, .nc for NetCDF (imas-python required for .h5/.nc).",
    )
    parser_map.add_argument(
        "--mapping",
        type=str,
        default=None,
        metavar="FILE",
        help=(
            "Path to a mapping JSON file. Only IDS paths whose template form "
            "appears as a key in the file will be mapped."
        ),
    )
    parser_map.add_argument(
        "--concurrency-mode",
        default=None,
        choices=["serial", "thread", "process"],
        help="Override concurrency mode from config",
    )
    parser_map.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help="Override number of parallel workers from config",
    )
    parser_map.add_argument(
        "--binary-arrays",
        action="store_true",
        default=False,
        help=(
            "Encode numpy arrays as base64 binary objects in JSON output "
            "(overrides run.binary_arrays in config; default: false)"
        ),
    )
    parser_map.add_argument(
        "--on-imas-error",
        default=None,
        choices=["fallback-json", "raise"],
        dest="on_imas_error",
        help=(
            "Action when an IDS fails to write to an IMAS file. "
            "'fallback-json' (default) logs the error and writes failed IDS records "
            "to a companion _fallback.json file; 'raise' stops the run immediately."
        ),
    )
    parser_map.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help=(
            "Expand paths only — do not call the mapper. "
            "Useful for checking how many paths will be mapped and "
            "how long path expansion takes."
        ),
    )
    parser_map.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Map at most N paths (after expansion and filtering). Useful for quick tests.",
    )
    parser_map.add_argument(
        "--profile-stats",
        action="store_true",
        dest="profile_stats",
        help=(
            "Print a profiling report after the run: phase timings (expansion / "
            "mapping / output), per-call stats for mapper.map() and "
            "get_array_length(), and bottleneck hints."
        ),
    )
    parser_map.add_argument(
        "--profile",
        default=None,
        metavar="FILE",
        help=(
            "Write a cProfile stats file to FILE for detailed line-level profiling. "
            "Inspect with: python -m pstats FILE  or  snakeviz FILE"
        ),
    )
    parser_map.set_defaults(func=cmd_map)

    parser_init_config = subparsers.add_parser(
        "init-config",
        help="Create a skeleton munchi config file",
    )
    parser_init_config.add_argument(
        "--output",
        type=str,
        default="munchi.toml",
        help="Output config path",
    )
    add_force_argument(parser_init_config)
    parser_init_config.set_defaults(func=cmd_init_config)

    parser_init_mapping = subparsers.add_parser(
        "init-mapping",
        help="Create a blank JSON mapping template from IDS schema paths",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser_init_mapping.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name, e.g. 'magnetics'",
    )
    parser_init_mapping.add_argument(
        "--output",
        type=str,
        default="mapping.json",
        help="Output mapping JSON path",
    )
    parser_init_mapping.add_argument(
        "--leaves-only",
        action="store_true",
        help="Only include leaf schema paths",
    )
    add_force_argument(parser_init_mapping)
    parser_init_mapping.set_defaults(func=cmd_init_mapping)

    parser_convert = subparsers.add_parser(
        "convert",
        help="Convert data between supported file formats (.json, .h5, .nc)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Convert between munchi JSON output and imas-python IMAS files.\n\n"
            "Supported formats: .json  .h5  .nc\n\n"
            "Primary use case — load a non-compliant JSON into IDS objects in Python:\n"
            "  records = read_json_records(Path('results.json'))\n"
            "  ids_objects = records_to_ids_objects(records)\n"
            "  ids_objects['equilibrium'].time_slice[0].time = 0.5  # add missing fields\n"
            "  with imas.DBEntry(...) as db: db.put(ids_objects['equilibrium'])\n"
        ),
    )
    parser_convert.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Input file (.json, .h5, or .nc)",
    )
    parser_convert.add_argument(
        "--output",
        required=True,
        metavar="FILE",
        help="Output file (.json, .h5, or .nc)",
    )
    parser_convert.add_argument(
        "--ids",
        nargs="+",
        metavar="IDS",
        default=None,
        help=(
            "IDS name(s) to read when the input is an IMAS file "
            "(e.g. --ids magnetics equilibrium). Not needed for JSON input."
        ),
    )
    parser_convert.add_argument(
        "--binary-arrays",
        action="store_true",
        default=False,
        help="Encode numpy arrays as base64 binary objects in JSON output",
    )
    parser_convert.add_argument(
        "--on-imas-error",
        default=None,
        choices=["fallback-json", "raise"],
        dest="on_imas_error",
        help=(
            "Action when an IDS fails to write: 'fallback-json' (default) writes "
            "failed records to a _fallback.json companion file; 'raise' stops immediately."
        ),
    )
    add_force_argument(parser_convert)
    parser_convert.set_defaults(func=cmd_convert)

    parser_check = subparsers.add_parser(
        "check",
        help="Validate config/mapper setup and optionally an IDS schema",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser_check)
    parser_check.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Optional IDS name to validate and inspect",
    )
    parser_check.set_defaults(func=cmd_check)

    return parser


def _add_file_log_handler(path: str, level: str) -> None:
    """Attach a file handler to the root logger.

    The file handler uses a timestamped format so log entries can be
    correlated with wall-clock time when inspecting errors offline.
    The root logger level is lowered to ``level`` if it is currently
    more restrictive, ensuring the new handler actually receives records.
    """
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.addHandler(handler)
    # The root logger acts as a gate: if its level is higher than the handler's
    # level, records are discarded before reaching the handler.
    if root.level > handler.level:
        root.setLevel(handler.level)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s", level=logging.WARNING)
    if args.log_level is not None:
        logging.getLogger().setLevel(args.log_level)

    if args.log_file is not None:
        _add_file_log_handler(args.log_file, args.log_file_level)

    try:
        raise SystemExit(args.func(args))
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except NotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
