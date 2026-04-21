"""munchi convert — convert data between supported file formats."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...io.convert import convert_file
from ..common import (
    handle_imas_write_errors,
    resolve_binary_arrays,
    resolve_on_imas_error,
)


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    from ..parser import add_force_argument

    parser = subparsers.add_parser(
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
    parser.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Input file (.json, .h5, or .nc)",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="FILE",
        help="Output file (.json, .h5, or .nc)",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        metavar="IDS",
        default=None,
        help=(
            "IDS name(s) to read when the input is an IMAS file "
            "(e.g. --ids magnetics equilibrium). Not needed for JSON input."
        ),
    )
    parser.add_argument(
        "--binary-arrays",
        action="store_true",
        default=False,
        help="Encode numpy arrays as base64 binary objects in JSON output",
    )
    parser.add_argument(
        "--on-imas-error",
        default=None,
        choices=["fallback-json", "raise"],
        dest="on_imas_error",
        help=(
            "Action when an IDS fails to write: 'fallback-json' (default) writes "
            "failed records to a _fallback.json companion file; 'raise' stops immediately."
        ),
    )
    add_force_argument(parser)
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)

    binary_arrays = resolve_binary_arrays(args.binary_arrays, None)
    on_imas_error = resolve_on_imas_error(getattr(args, "on_imas_error", None), None)

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
        handle_imas_write_errors(
            write_errors, output_path, on_imas_error, binary_arrays=binary_arrays
        )
        return 1

    return 0
