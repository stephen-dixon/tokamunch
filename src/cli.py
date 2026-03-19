from __future__ import annotations

import argparse
from typing import Any

import libtokamap
import tokamap_ids as tm

from pyuda_pydatasource_plugin import PyudaDataSource


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name (e.g. magnetics, core_profiles)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="mastu",
        help="Device name / mapping folder",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.toml",
        help="libtokamap config file",
    )
    parser.add_argument(
        "--shot",
        type=int,
        default=47125,
        help="Shot number",
    )
    parser.add_argument(
        "--leaves-only",
        action="store_true",
        help="Only iterate leaf paths",
    )


def register_default_data_sources(mapper: libtokamap.Mapper) -> None:
    mapper.register_python_data_source(
        "UDA",
        PyudaDataSource("uda2.hpc.l", 59876, "UDA"),
    )
    mapper.register_python_data_source(
        "GEOMETRY",
        PyudaDataSource("uda2.hpc.l", 59876, "GEOMETRY"),
    )


def should_suppress_mapping_error(exc: Exception) -> bool:
    return str(exc).startswith("Mapping error: failed to find mapping for")


def create_ids_object(ids_name: str) -> Any:
    import imas  # adjust to your real API

    raise NotImplementedError(
        "Wire this to your imas-python IDS factory"
    )


# ---------------------------
# Subcommands
# ---------------------------

def cmd_paths(args: argparse.Namespace) -> None:
    mapper = libtokamap.Mapper(args.config)
    register_default_data_sources(mapper)

    tokamap = tm.TokamapInterface(mapper, args.device, {"shot": args.shot})
    helper = tm.IDSHelper.from_ids_name(args.ids)

    for path in helper.iter_concrete_paths(
        tokamap.get_array_length,
        leaves_only=args.leaves_only,
    ):
        print(path)


def cmd_map(args: argparse.Namespace) -> None:
    mapper = libtokamap.Mapper(args.config)
    register_default_data_sources(mapper)

    tokamap = tm.TokamapInterface(mapper, args.device, {"shot": args.shot})
    helper = tm.IDSHelper.from_ids_name(args.ids)

    for segments in helper.iter_concrete_segments(
        tokamap.get_array_length,
        leaves_only=args.leaves_only,
    ):
        ids_path = tm.render_concrete_path(segments)

        try:
            res = tokamap.map(ids_path)

            if res is not None and hasattr(res, "dtype") and res.dtype == "S1":
                res = res.tobytes().decode()

            if res is not None:
                print(f"{ids_path}: {res}")

        except Exception as exc:
            if args.verbose_errors or not should_suppress_mapping_error(exc):
                print(f"{ids_path}: {exc}")


def cmd_write(args: argparse.Namespace) -> None:
    mapper = libtokamap.Mapper(args.config)
    register_default_data_sources(mapper)

    tokamap = tm.TokamapInterface(mapper, args.device, {"shot": args.shot})
    helper = tm.IDSHelper.from_ids_name(args.ids)

    ids_obj = create_ids_object(args.ids)
    write_ctx = tm.WriteContext()

    for segments in helper.iter_concrete_segments(
        tokamap.get_array_length,
        leaves_only=True,  # always leaf-only for writing
    ):
        ids_path = tm.render_concrete_path(segments)

        try:
            value = tokamap.map(ids_path)

            if value is not None and hasattr(value, "dtype") and value.dtype == "S1":
                value = value.tobytes().decode()

            if value is None:
                continue

            tm.resize_and_set_ids_value(
                ids_obj,
                segments,
                value,
                helper.array_sizes,
                write_context=write_ctx,
                skip_root_segment=True,
            )

        except Exception as exc:
            if args.verbose_errors or not should_suppress_mapping_error(exc):
                print(f"{ids_path}: {exc}")

    print(ids_obj)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tokamap-ids",
        description="IDS mapping CLI",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # paths
    parser_paths = subparsers.add_parser(
        "paths",
        help="Expand and print IDS paths",
    )
    add_common_arguments(parser_paths)
    parser_paths.set_defaults(func=cmd_paths)

    # map
    parser_map = subparsers.add_parser(
        "map",
        help="Map IDS paths and print values",
    )
    add_common_arguments(parser_map)
    parser_map.add_argument(
        "--verbose-errors",
        action="store_true",
        help="Print all mapping errors",
    )
    parser_map.set_defaults(func=cmd_map)

    # write
    parser_write = subparsers.add_parser(
        "write",
        help="Write mapped data into an IDS object",
    )
    add_common_arguments(parser_write)
    parser_write.add_argument(
        "--verbose-errors",
        action="store_true",
    )
    parser_write.set_defaults(func=cmd_write)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
