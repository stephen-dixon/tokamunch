"""munchi update-mapping and munchi update commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ...core.selection import IdsSelection, generate_selected_paths
from ...ids.output import SUPPORTED_SUFFIXES, write_imas_output
from ...ids.templates import load_mapping_keys, merge_mapping_stubs
from ...io.convert import read_imas_records, read_json_records
from ...io.outputs import build_json_results, print_summary, write_json_file
from ...mapping.runner import build_records, map_serial
from ..common import (
    apply_log_level,
    handle_imas_write_errors,
    load_config_with_overrides,
    make_context,
)


def register_update_mapping(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    from ..parser import add_force_argument

    parser = subparsers.add_parser(
        "update-mapping",
        help="Add new stub entries to an existing mapping JSON file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name, e.g. 'magnetics'",
    )
    parser.add_argument(
        "--mapping",
        type=str,
        required=True,
        metavar="FILE",
        help="Existing mapping JSON file to update",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Output file (default: print JSON to stdout)",
    )
    parser.add_argument(
        "--leaves-only",
        action="store_true",
        help="Only add stubs for leaf schema paths",
    )
    add_force_argument(parser)
    parser.set_defaults(func=run_update_mapping)


def register_update(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    from ..parser import (
        add_common_arguments,
        add_force_argument,
        add_verbose_errors_argument,
    )

    parser = subparsers.add_parser(
        "update",
        help="Map missing paths and merge with existing results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser)
    parser.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Existing result file (.json, .h5, or .nc)",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="FILE",
        help="Output file (.json, .h5, or .nc)",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        help="IDS name to map (required for IMAS input; optional for JSON)",
    )
    parser.add_argument(
        "--mapping",
        type=str,
        default=None,
        metavar="FILE",
        help="Restrict paths to those present in this mapping JSON file",
    )
    add_force_argument(parser)
    add_verbose_errors_argument(parser)
    parser.set_defaults(func=run_update)


def run_update_mapping(args: argparse.Namespace) -> int:
    import json as _json

    existing_path = Path(args.mapping)
    merged = merge_mapping_stubs(
        args.ids,
        existing_path,
        leaves_only=args.leaves_only,
    )

    with existing_path.open(encoding="utf-8") as f:
        existing_keys = set(_json.load(f).keys())
    new_stub_count = sum(1 for k in merged if k not in existing_keys)

    print(f"{new_stub_count} new stub(s) added.", file=sys.stderr)

    if args.output is not None:
        output_path = Path(args.output)
        write_json_file(output_path, merged, force=args.force)
        print(f"Wrote updated mapping to {output_path}")
    else:
        print(_json.dumps(merged, indent=2, ensure_ascii=False))

    return 0


def run_update(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)

    in_suffix = input_path.suffix.lower()
    if in_suffix == ".json":
        existing_records = read_json_records(input_path)
    elif in_suffix in SUPPORTED_SUFFIXES:
        ids_names_for_read = [args.ids] if args.ids else None
        if not ids_names_for_read:
            raise ValueError(
                "Reading from an IMAS file requires --ids (one or more IDS names)."
            )
        existing_records = read_imas_records(input_path, ids_names_for_read)
    else:
        raise ValueError(
            f"Unsupported input format {in_suffix!r}. Use .json, .h5, or .nc."
        )

    existing_paths: set[str] = {r.ids_path for r in existing_records if r.ok}

    cli_cfg = load_config_with_overrides(args)
    ctx = make_context(args, cli_cfg=cli_cfg)
    apply_log_level(args.log_level, ctx.cli_config)

    mapping_keys = load_mapping_keys(Path(args.mapping)) if args.mapping else None

    if args.ids:
        selection: IdsSelection = IdsSelection(
            ids=args.ids,
            match=None,
            leaves_only=args.leaves_only,
            mapping_keys=mapping_keys,
        )
    else:
        raise ValueError("--ids is required for the update command")

    all_paths = list(generate_selected_paths(selection, ctx))
    new_paths = [p for p in all_paths if p not in existing_paths]
    print(
        f"Found {len(all_paths)} total paths; {len(existing_paths)} already present; "
        f"mapping {len(new_paths)} new path(s).",
        file=sys.stderr,
    )

    if new_paths:
        raw = map_serial(ctx.tokamap, new_paths)
        new_records, summary = build_records(raw, verbose_errors=args.verbose_errors)
        print_summary(summary)
    else:
        new_records = []

    merged_records = list(existing_records) + [
        r for r in new_records if r.ok and r.value is not None
    ]

    out_suffix = output_path.suffix.lower()
    binary_arrays = False
    if out_suffix == ".json":
        write_json_file(
            output_path,
            build_json_results(merged_records),
            force=args.force,
        )
        print(f"Wrote merged JSON to {output_path}")
    elif out_suffix in SUPPORTED_SUFFIXES:
        write_errors = write_imas_output(
            output_path, records=merged_records, force=args.force
        )
        print(f"Wrote merged {out_suffix.upper()[1:]} to {output_path}")
        if write_errors:
            handle_imas_write_errors(
                write_errors, output_path, "fallback-json", binary_arrays=binary_arrays
            )
    else:
        raise ValueError(
            f"Unsupported output format {out_suffix!r}. Use .json, .h5, or .nc."
        )

    return 0
