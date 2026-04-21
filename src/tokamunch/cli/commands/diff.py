"""munchi diff — compare two mapping result files."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...io.diff import diff_files, render_diff


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "diff",
        help="Compare two mapping result files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file_a",
        metavar="FILE_A",
        help="First file (.json, .h5, or .nc)",
    )
    parser.add_argument(
        "file_b",
        metavar="FILE_B",
        help="Second file (.json, .h5, or .nc)",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        metavar="IDS",
        default=None,
        help="IDS name(s) to read when the input is an IMAS file",
    )
    parser.add_argument(
        "--show-unchanged",
        action="store_true",
        dest="show_unchanged",
        help="Also print unchanged paths",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    path_a = Path(args.file_a)
    path_b = Path(args.file_b)

    entries = diff_files(path_a, path_b, ids_names=args.ids or None)
    text = render_diff(
        entries,
        label_a=str(path_a),
        label_b=str(path_b),
        show_unchanged=args.show_unchanged,
    )
    print(text)

    has_diff = any(e.status != "unchanged" for e in entries)
    return 1 if has_diff else 0
