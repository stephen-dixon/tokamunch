"""munchi paths — expand and print concrete IDS runtime paths."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ...core.selection import path_matches
from ...io.outputs import (
    build_schema_map,
    render_text_schema_map,
    write_json_file,
)
from ..common import apply_log_level, load_config_with_overrides, make_context


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    from ..parser import (
        PATH_SYNTAX_EPILOG,
        add_common_arguments,
        add_force_argument,
        add_match_argument,
    )

    parser = subparsers.add_parser(
        "paths",
        help="Expand and print concrete IDS runtime paths",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser)
    parser.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name to expand, e.g. 'magnetics'",
    )
    add_match_argument(parser)
    parser.add_argument(
        "--schema-map",
        action="store_true",
        help=(
            "Show each schema path ((:) notation) alongside the concrete path(s) "
            "it expands to. Console: 'schema -> concrete' lines. "
            "JSON: {schema_path: [concrete_path, ...]}."
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write output to a JSON file instead of printing to the console",
    )
    add_force_argument(parser)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    import tqdm as tqdm_mod

    if args.output is not None:
        output_path = Path(args.output)
        if output_path.suffix.lower() != ".json":
            raise ValueError(
                f"Unsupported output file extension for {output_path!s}. Use .json."
            )

    cli_cfg = load_config_with_overrides(args)
    ctx = make_context(args, cli_cfg=cli_cfg)
    apply_log_level(args.log_level, ctx.cli_config)
    helper = ctx.ids_helper(args.ids)

    schema_leaf_count = sum(
        1 for _ in helper.generate_non_concrete_paths(leaves_only=True)
    )

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
