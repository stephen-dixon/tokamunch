"""Main entry point for the munchi CLI."""

from __future__ import annotations

import logging
import sys

from .parser import build_parser


def _add_file_log_handler(path: str, level: str) -> None:
    """Attach a file handler to the root logger."""
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level > handler.level:
        root.setLevel(handler.level)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s %(name)s: %(message)s", level=logging.WARNING
    )
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
