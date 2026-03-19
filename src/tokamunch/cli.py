from __future__ import annotations

import argparse
from typing import Any

import tokamunch as tm


def should_suppress_mapping_error(exc: Exception) -> bool:
    return str(exc).startswith("Mapping error: failed to find mapping for")


def create_ids_object(ids_name: str) -> Any:
    import imas
    raise NotImplementedError("Wire this to your imas-python IDS factory")


def cmd_paths(args: argparse.Namespace) -> None:
    cfg = tm.load_cli_config(args.config)
    mapper = tm.create_mapper_from_config(cfg)

    device = args.device or cfg.mapper.device
    tokamap = tm.TokamapInterface(
        mapper,
        device,
        {"shot": args.shot if args.shot is not None else cfg.run.default_shot},
    )
    array_length_callback = tokamap.get_array_length

    helper = tm.IDSHelper.from_ids_name(args.ids)

    for path in helper.iter_concrete_paths(
        array_length_callback,
        leaves_only=args.leaves_only,
    ):
        print(path)


def cmd_map(args: argparse.Namespace) -> None:
    cfg = tm.load_cli_config(args.config)
    mapper = tm.create_mapper_from_config(cfg)

    device = args.device or cfg.mapper.device
    tokamap = tm.TokamapInterface(
        mapper,
        device,
        {"shot": args.shot if args.shot is not None else cfg.run.default_shot},
    )
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


def cmd_map_one(args: argparse.Namespace) -> None:
    cfg = tm.load_cli_config(args.config)
    mapper = tm.create_mapper_from_config(cfg)

    device = args.device or cfg.mapper.device
    tokamap = tm.TokamapInterface(
        mapper,
        device,
        {"shot": args.shot if args.shot is not None else cfg.run.default_shot},
    )
    ids_path = args.path
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
    cfg = tm.load_cli_config(args.config)
    mapper = tm.create_mapper_from_config(cfg)

    device = args.device or cfg.mapper.device
    tokamap = tm.TokamapInterface(
        mapper,
        device,
        {"shot": args.shot if args.shot is not None else cfg.run.default_shot},
    )
    helper = tm.IDSHelper.from_ids_name(args.ids)

    ids_obj = create_ids_object(args.ids)
    write_ctx = tm.WriteContext()

    for segments in helper.iter_concrete_segments(
        tokamap.get_array_length,
        leaves_only=True,
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
        prog="munchi",
        description="IDS mapping CLI",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_paths = subparsers.add_parser("paths", help="Expand and print IDS paths")
    add_common_arguments(parser_paths)
    parser_paths.set_defaults(func=cmd_paths)
    parser_paths.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name (e.g. magnetics, core_profiles)",
    )

    parser_map = subparsers.add_parser("map", help="Map IDS paths and print values")
    add_common_arguments(parser_map)
    parser_map.add_argument("--verbose-errors", action="store_true")
    parser_map.set_defaults(func=cmd_map)
    parser_map.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name (e.g. magnetics, core_profiles)",
    )

    # parser_write = subparsers.add_parser("write", help="Write mapped data into an IDS object")
    # add_common_arguments(parser_write)
    # parser_write.add_argument("--verbose-errors", action="store_true")
    # parser_write.set_defaults(func=cmd_write)

    parser_map_path = subparsers.add_parser("map-one", help="Map IDS paths and print values")
    add_common_arguments(parser_map_path)
    parser_map_path.add_argument("--verbose-errors", action="store_true")
    parser_map_path.set_defaults(func=cmd_map_one)
    parser_map_path.add_argument(
        "--path",
        type=str,
        required=True,
        help="IDS name (e.g. magnetics, core_profiles)",
    )

    return parser


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=str,
        default="munchi.toml",
        help="tokamap-ids CLI config file",
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
        help="Only iterate leaf paths",
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
