"""munchi init-config and munchi init-mapping commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...core.config import render_cli_config_template
from ...ids.templates import build_blank_mapping_template
from ...io.outputs import write_json_file


def register_init_config(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    from ..parser import add_force_argument

    parser = subparsers.add_parser(
        "init-config",
        help="Create a skeleton munchi config file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="munchi.toml",
        help="Output config path",
    )
    add_force_argument(parser)
    parser.set_defaults(func=run_init_config)


def register_init_mapping(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    from ..parser import PATH_SYNTAX_EPILOG, add_force_argument

    parser = subparsers.add_parser(
        "init-mapping",
        help="Create a blank JSON mapping template from IDS schema paths",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name, e.g. 'magnetics'",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="mapping.json",
        help="Output mapping JSON path",
    )
    parser.add_argument(
        "--leaves-only",
        action="store_true",
        help="Only include leaf schema paths",
    )
    add_force_argument(parser)
    parser.set_defaults(func=run_init_mapping)


def run_init_config(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite existing file: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_cli_config_template(), encoding="utf-8")
    print(f"Wrote skeleton config to {output_path}")
    return 0


def run_init_mapping(args: argparse.Namespace) -> int:
    mapping = build_blank_mapping_template(
        args.ids,
        leaves_only=args.leaves_only,
    )
    output_path = Path(args.output)
    write_json_file(output_path, mapping, force=args.force)
    print(f"Wrote blank mapping template to {output_path}")
    return 0
