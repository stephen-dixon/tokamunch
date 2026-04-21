"""munchi map — map one concrete path or all concrete paths of an IDS."""

from __future__ import annotations

import argparse
import cProfile
import sys
import time
from pathlib import Path
from typing import Any

from ...core.config import CLIConfig
from ...core.selection import IdsSelection, MultiPathSelection, SinglePathSelection
from ...ids.output import SUPPORTED_SUFFIXES, write_imas_output
from ...ids.templates import load_mapping_keys
from ...io.outputs import (
    build_json_results,
    print_summary,
    render_text_records,
    render_verbose_records,
    write_json_file,
)
from ...mapping.runner import collect_mapped_values
from ..common import (
    apply_concurrency_overrides,
    apply_log_level,
    handle_imas_write_errors,
    load_config_with_overrides,
    make_context,
    resolve_binary_arrays,
    resolve_on_imas_error,
    resolve_paths_arg,
    shot_output_path,
)


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    from ..parser import (
        PATH_SYNTAX_EPILOG,
        add_common_arguments,
        add_force_argument,
        add_ids_or_path_arguments,
        add_match_argument,
        add_verbose_errors_argument,
    )

    parser = subparsers.add_parser(
        "map",
        help="Map one concrete path or all concrete paths of an IDS",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser)
    add_ids_or_path_arguments(parser)
    add_match_argument(parser)
    add_force_argument(parser)
    add_verbose_errors_argument(parser)
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output destination. Default: terminal text. Use .json for JSON, .h5 for HDF5, .nc for NetCDF (imas-python required for .h5/.nc).",
    )
    parser.add_argument(
        "--mapping",
        type=str,
        default=None,
        metavar="FILE",
        help=(
            "Path to a mapping JSON file. Only IDS paths whose template form "
            "appears as a key in the file will be mapped."
        ),
    )
    parser.add_argument(
        "--concurrency-mode",
        default=None,
        choices=["serial", "thread", "process"],
        help="Override concurrency mode from config",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help="Override number of parallel workers from config",
    )
    parser.add_argument(
        "--binary-arrays",
        action="store_true",
        default=False,
        help=(
            "Encode numpy arrays as base64 binary objects in JSON output "
            "(overrides run.binary_arrays in config; default: false)"
        ),
    )
    parser.add_argument(
        "--on-imas-error",
        default=None,
        choices=["fallback-json", "raise"],
        dest="on_imas_error",
        help=(
            "Action when an IDS fails to write to an IMAS file. "
            "'fallback-json' (default) logs the error and writes failed IDS records "
            "to a companion _fallback.json file; 'raise' stops the run immediately."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help=(
            "Expand paths only — do not call the mapper. "
            "Useful for checking how many paths will be mapped."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Map at most N paths (after expansion and filtering). Useful for quick tests.",
    )
    parser.add_argument(
        "--profile-stats",
        action="store_true",
        dest="profile_stats",
        help=(
            "Print a profiling report after the run: phase timings, per-call stats, "
            "and bottleneck hints."
        ),
    )
    parser.add_argument(
        "--profile",
        default=None,
        metavar="FILE",
        help=(
            "Write a cProfile stats file to FILE for detailed line-level profiling. "
            "Inspect with: python -m pstats FILE  or  snakeviz FILE"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help=(
            "Show expanded output for each mapped value (dtype, shape, min/max, "
            "first elements). Errors show full traceback."
        ),
    )
    shots_group = parser.add_mutually_exclusive_group()
    shots_group.add_argument(
        "--shots",
        nargs="+",
        type=int,
        metavar="N",
        help=(
            "Map these specific shot numbers. "
            "--output is required and may contain {shot} as a template."
        ),
    )
    shots_group.add_argument(
        "--shot-range",
        nargs="+",
        type=int,
        metavar=("START", "END"),
        dest="shot_range",
        help=(
            "Map shots in range START..END (inclusive), with optional STEP. "
            "Provide 2 or 3 integers: START END [STEP]. "
            "--output is required and may contain {shot} as a template."
        ),
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        metavar="FILE",
        help=(
            "Checkpoint file path. If the file exists, completed paths are skipped "
            "and mapping resumes from where it left off."
        ),
    )
    parser.set_defaults(func=run)


def _run_mapping_for_shot(
    args: argparse.Namespace,
    cli_cfg: CLIConfig | None,
    shot: int | None,
    *,
    selection: IdsSelection | SinglePathSelection | MultiPathSelection,
    dry_run: bool,
    limit: int | None,
    profile_data: Any,
    verbose: bool,
    checkpoint_path: Path | None,
) -> tuple[list[Any], Any, float]:
    """Run mapping for a single shot and return (records, summary, total_wall)."""
    import tqdm as tqdm_mod

    ctx = make_context(args, cli_cfg=cli_cfg, shot=shot)
    apply_concurrency_overrides(args, ctx)

    disable_bar = not sys.stderr.isatty()

    t0_wall = time.perf_counter()
    with tqdm_mod.tqdm(
        total=None,
        desc="Expanding paths",
        unit="path",
        disable=disable_bar,
        file=sys.stderr,
    ) as bar:

        def _on_path_expanded(n: int) -> None:
            if dry_run:
                bar.reset(total=n)
                bar.set_description("Dry run")
            else:
                bar.reset(total=n)
                bar.set_description("Mapping")

        def _on_path_mapped(n: int) -> None:
            bar.update(n)

        records, summary = collect_mapped_values(
            ctx,
            selection,
            verbose_errors=args.verbose_errors,
            on_paths_ready=_on_path_expanded,
            progress_callback=_on_path_mapped,
            profile=profile_data,
            dry_run=dry_run,
            limit=limit,
        )

    total_wall = time.perf_counter() - t0_wall
    return records, summary, total_wall


def run(args: argparse.Namespace) -> int:
    from ...core.profiling import ProfileData, render_profile_report

    if args.output is not None:
        output_path_template = args.output
        output_path = Path(args.output)
        if output_path.suffix.lower() not in {".json", *SUPPORTED_SUFFIXES}:
            raise ValueError(
                f"Unsupported output file extension for {output_path!s}. "
                "Use no --output for terminal text, .json for JSON, "
                ".h5 for HDF5, or .nc for NetCDF."
            )
    else:
        output_path_template = None

    cli_cfg = load_config_with_overrides(args)
    apply_log_level(args.log_level, cli_cfg)

    binary_arrays = resolve_binary_arrays(args.binary_arrays, cli_cfg)
    on_imas_error = resolve_on_imas_error(getattr(args, "on_imas_error", None), cli_cfg)
    dry_run: bool = getattr(args, "dry_run", False)
    limit: int | None = getattr(args, "limit", None)
    profile_stats: bool = getattr(args, "profile_stats", False)
    profile_file: str | None = getattr(args, "profile", None)
    verbose: bool = getattr(args, "verbose", False)
    checkpoint_path: Path | None = (
        Path(args.checkpoint) if getattr(args, "checkpoint", None) else None
    )

    mapping_keys = load_mapping_keys(Path(args.mapping)) if args.mapping else None

    selection: IdsSelection | SinglePathSelection | MultiPathSelection
    if args.path is not None:
        selection = SinglePathSelection(path=args.path, mapping_keys=mapping_keys)
    elif args.paths is not None:
        resolved = resolve_paths_arg(args.paths)
        selection = MultiPathSelection(paths=resolved, mapping_keys=mapping_keys)
    else:
        selection = IdsSelection(
            ids=args.ids,
            match=args.match,
            leaves_only=args.leaves_only,
            mapping_keys=mapping_keys,
        )

    shots_arg: list[int] | None = getattr(args, "shots", None)
    shot_range_arg: list[int] | None = getattr(args, "shot_range", None)
    single_shot: int | None = getattr(args, "shot", None)

    shots_list: list[int | None]
    if shots_arg is not None:
        shots_list = list(shots_arg)
    elif shot_range_arg is not None:
        if len(shot_range_arg) == 2:
            shots_list = list(range(shot_range_arg[0], shot_range_arg[1] + 1))
        else:
            shots_list = list(
                range(shot_range_arg[0], shot_range_arg[1] + 1, shot_range_arg[2])
            )
    else:
        shots_list = [single_shot]

    multi_shot = len(shots_list) > 1 or (
        len(shots_list) == 1 and shots_list[0] is not None and shots_arg is not None
    )

    if multi_shot and output_path_template is None:
        raise ValueError("--output is required when using --shots or --shot-range")

    profile_data = ProfileData() if (profile_stats or profile_file) else None

    profiler = cProfile.Profile() if profile_file else None
    if profiler is not None:
        profiler.enable()

    all_records: list[Any] = []
    all_summaries: list[Any] = []
    overall_t0 = time.perf_counter()

    for shot in shots_list:
        if multi_shot:
            print(f"\n--- Shot {shot} ---", file=sys.stderr)

        records, summary, total_wall = _run_mapping_for_shot(
            args,
            cli_cfg,
            shot,
            selection=selection,
            dry_run=dry_run,
            limit=limit,
            profile_data=profile_data,
            verbose=verbose,
            checkpoint_path=checkpoint_path,
        )
        all_records.extend(records)
        all_summaries.append(summary)

        if dry_run:
            print(
                f"Dry run: {len(records)} paths expanded in {summary.elapsed_s:.2f}s "
                "(no mapper calls made).",
                file=sys.stderr,
            )
            continue

        if output_path_template is not None:
            if multi_shot and shot is not None:
                eff_output = shot_output_path(output_path_template, shot)
            else:
                eff_output = Path(output_path_template)
        else:
            eff_output = None

        if eff_output is None:
            if verbose:
                text = render_verbose_records(
                    records, verbose_errors=args.verbose_errors
                )
            else:
                text = render_text_records(records, verbose_errors=args.verbose_errors)
            if text:
                print(text)
            print_summary(summary)
        else:
            _t_before_output = time.perf_counter()

            if checkpoint_path is not None:
                from ...core.checkpoint import Checkpoint, save_checkpoint
                from ...io.outputs import make_json_safe

                cp = Checkpoint(
                    output_path=str(eff_output),
                    completed_paths=[
                        r.ids_path for r in records if r.ok and r.value is not None
                    ],
                    results={
                        r.ids_path: make_json_safe(r.value)
                        for r in records
                        if r.ok and r.value is not None
                    },
                )
                save_checkpoint(checkpoint_path, cp)

            suffix = eff_output.suffix.lower()
            if suffix == ".json":
                write_json_file(
                    eff_output,
                    build_json_results(records, binary_arrays=binary_arrays),
                    force=args.force,
                )
                print(f"Wrote JSON output to {eff_output}")
            else:
                write_errors = write_imas_output(
                    eff_output, records=records, force=args.force
                )
                print(f"Wrote {eff_output.suffix.upper()[1:]} output to {eff_output}")
                if write_errors:
                    handle_imas_write_errors(
                        write_errors,
                        eff_output,
                        on_imas_error,
                        binary_arrays=binary_arrays,
                    )

            if profile_data is not None:
                profile_data.phases.output_s += time.perf_counter() - _t_before_output

            if checkpoint_path is not None and checkpoint_path.exists():
                checkpoint_path.unlink()

            print_summary(summary)

    if profiler is not None:
        profiler.disable()
        profiler.dump_stats(profile_file)  # type: ignore[arg-type]
        print(f"cProfile stats written to {profile_file}", file=sys.stderr)
        print(
            f"  Inspect with: python -m pstats {profile_file}  "
            f"or  snakeviz {profile_file}",
            file=sys.stderr,
        )

    if dry_run:
        if profile_stats and profile_data is not None:
            total_wall = time.perf_counter() - overall_t0
            print(render_profile_report(profile_data, total_wall), file=sys.stderr)
        return 0

    if profile_stats and profile_data is not None:
        total_wall = time.perf_counter() - overall_t0
        print(render_profile_report(profile_data, total_wall), file=sys.stderr)

    if multi_shot and all_summaries:
        total_paths = sum(s.total_paths for s in all_summaries)
        total_mapped = sum(s.mapped for s in all_summaries)
        total_elapsed = time.perf_counter() - overall_t0
        print(
            f"\nCombined: {len(shots_list)} shots, {total_paths} total paths, "
            f"{total_mapped} mapped, {total_elapsed:.2f}s elapsed.",
            file=sys.stderr,
        )

    has_errors = any(s.has_unexpected_errors for s in all_summaries)
    return 1 if has_errors else 0
