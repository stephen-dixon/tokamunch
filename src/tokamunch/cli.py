from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import check_ids
from .config import render_cli_config_template
from .context import MappingContext
from .mapping import collect_mapped_values
from .outputs import build_json_results, print_summary, render_text_records, write_json_file
from .selection import IdsSelection, SinglePathSelection, path_matches
from .templates import build_blank_mapping_template, load_mapping_keys
from .write_ids import write_h5_output


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


def cmd_paths(args: argparse.Namespace) -> int:
    ctx = MappingContext.from_config(args.config, device=args.device, shot=args.shot)
    helper = ctx.ids_helper(args.ids)

    lines: list[str] = []
    for path in helper.generate_concrete_paths(
        ctx.tokamap.get_array_length,
        leaves_only=args.leaves_only,
    ):
        if path_matches(path, args.match):
            lines.append(path)

    if lines:
        print("\n".join(lines))
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    if args.output is not None:
        output_path = Path(args.output)
        if output_path.suffix.lower() not in {".json", ".h5"}:
            raise ValueError(
                f"Unsupported output file extension for {output_path!s}. "
                "Use no --output for terminal text, .json for JSON, or .h5 for HDF5."
            )

    ctx = MappingContext.from_config(args.config, device=args.device, shot=args.shot)

    mapping_keys = load_mapping_keys(Path(args.mapping)) if args.mapping else None

    if args.path is not None:
        selection: IdsSelection | SinglePathSelection = SinglePathSelection(
            path=args.path,
            mapping_keys=mapping_keys,
        )
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

    # suffix == ".h5" (already validated above)
    write_h5_output(output_path, records=records, force=args.force)
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
        help="Output destination. Default: terminal text. Use .json for JSON results.",
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
