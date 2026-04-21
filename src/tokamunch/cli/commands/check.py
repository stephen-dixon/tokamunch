"""munchi check — validate config/mapper setup and optionally an IDS schema."""

from __future__ import annotations

import argparse

from ...core.checks import check_ids
from ..common import apply_log_level, load_config_with_overrides, make_context


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    from ..parser import PATH_SYNTAX_EPILOG, add_common_arguments

    parser = subparsers.add_parser(
        "check",
        help="Validate config/mapper setup and optionally an IDS schema",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser)
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Optional IDS name to validate and inspect",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    cli_cfg = load_config_with_overrides(args)
    ctx = make_context(args, cli_cfg=cli_cfg)
    apply_log_level(args.log_level, ctx.cli_config)
    print("Config loaded successfully.")
    print(f"Device: {ctx.device}")
    print(f"Shot: {ctx.shot}")

    if args.ids:
        count = check_ids(args.ids, leaves_only=args.leaves_only)
        print(f"IDS recognised: {args.ids}")
        print(f"Schema paths found: {count}")

    return 0
