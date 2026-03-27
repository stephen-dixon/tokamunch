from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .checks import check_ids
from .config import render_cli_config_template
from .context import MappingContext
from .mapping import collect_mapped_values
from .outputs import (
    build_json_results,
    print_summary,
    render_text_records,
    write_json_file,
)
from .selection import IdsSelection, MultiPathSelection, SinglePathSelection, path_matches
from .templates import build_blank_mapping_template, load_mapping_keys
from .write_ids import SUPPORTED_SUFFIXES, write_imas_output

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
    ctx = MappingContext.from_config(args.config, device=args.device, shot=args.shot)
    logger.info("Loaded config: device=%s shot=%s", ctx.device, ctx.shot)
    helper = ctx.ids_helper(args.ids)

    lines: list[str] = []
    for path in helper.generate_concrete_paths(
        ctx.tokamap.get_array_length,
        leaves_only=args.leaves_only,
    ):
        if path_matches(path, args.match):
            lines.append(path)

    logger.info("Found %d concrete paths for IDS '%s'", len(lines), args.ids)
    if lines:
        print("\n".join(lines))
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    if args.output is not None:
        output_path = Path(args.output)
        if output_path.suffix.lower() not in {".json", *SUPPORTED_SUFFIXES}:
            raise ValueError(
                f"Unsupported output file extension for {output_path!s}. "
                "Use no --output for terminal text, .json for JSON, "
                ".h5 for HDF5, or .nc for NetCDF."
            )

    ctx = MappingContext.from_config(args.config, device=args.device, shot=args.shot)
    logger.info("Loaded config: device=%s shot=%s", ctx.device, ctx.shot)

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

    records, summary = collect_mapped_values(
        ctx,
        selection,
        verbose_errors=args.verbose_errors,
    )
    logger.info(
        "Results: mapped=%d none=%d suppressed=%d errors=%d",
        summary.mapped,
        summary.returned_none,
        summary.suppressed_errors,
        summary.unexpected_errors,
    )

    if args.output is None:
        text = render_text_records(records, verbose_errors=args.verbose_errors)
        if text:
            print(text)
        print_summary(summary)
        return 1 if summary.has_unexpected_errors else 0

    output_path = Path(args.output)
    suffix = output_path.suffix.lower()

    if suffix == ".json":
        write_json_file(output_path, build_json_results(records), force=args.force)
        print(f"Wrote JSON output to {output_path}")
        print_summary(summary)
        return 1 if summary.has_unexpected_errors else 0

    # suffix in SUPPORTED_SUFFIXES (already validated above)
    write_imas_output(output_path, records=records, force=args.force)
    print(f"Wrote {output_path.suffix.upper()[1:]} output to {output_path}")
    print_summary(summary)
    return 1 if summary.has_unexpected_errors else 0


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
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: WARNING)",
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s %(name)s: %(message)s",
        level=getattr(logging, args.log_level),
    )

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
