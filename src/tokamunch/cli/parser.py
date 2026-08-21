"""Argparse structure for the munchi CLI.

All parser construction lives here. Commands register themselves via
``register(subparsers)`` in their respective ``cli/commands/*.py`` modules.
"""

from __future__ import annotations

import argparse

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
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        default=None,
        help=(
            "Override a config value at runtime, e.g. "
            "--set run.concurrency.mode=thread --set run.concurrency.workers=4. "
            "Can be repeated."
        ),
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
    """Build and return the top-level munchi argument parser."""
    from .commands import check, completions, convert, diff, init, map, paths, update

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

    paths.register(subparsers)
    map.register(subparsers)
    init.register_init_config(subparsers)
    init.register_init_mapping(subparsers)
    convert.register(subparsers)
    check.register(subparsers)
    update.register_update_mapping(subparsers)
    diff.register(subparsers)
    update.register_update(subparsers)
    completions.register(subparsers)

    return parser
