from __future__ import annotations

import argparse
import cProfile
import logging
import sys
import time
from pathlib import Path
from typing import Any

from .checks import check_ids
from .config import (
    CLIConfig,
    ConcurrencyConfig,
    ConcurrencyMode,
    apply_config_overrides,
    load_cli_config,
    render_cli_config_template,
)
from .context import MappingContext
from .convert import convert_file, read_json_records
from .mapping import collect_mapped_values
from .outputs import (
    build_json_results,
    build_schema_map,
    print_summary,
    render_text_records,
    render_text_schema_map,
    render_verbose_records,
    write_json_file,
)
from .selection import (
    IdsSelection,
    MultiPathSelection,
    SinglePathSelection,
    generate_selected_paths,
    path_matches,
)
from .templates import (
    build_blank_mapping_template,
    load_mapping_keys,
    merge_mapping_stubs,
)
from .write_ids import SUPPORTED_SUFFIXES, IdsWriteError, write_imas_output

logger = logging.getLogger(__name__)

PATH_SYNTAX_EPILOG = """Path syntax:
  Concrete runtime path:
    magnetics/flux_loop[0]/position[0]/r

  Non-concrete IDS/schema path:
    magnetics/flux_loop(:)/position(:)/r

  Mapping-template path:
    magnetics/flux_loop[#]/position[#]/r

Notes:
  - 'map --path' expects one concrete path.
  - 'map --ids magnetics' expands all concrete paths for that IDS.
  - '--match' filters expanded concrete paths, e.g. 'magnetics/flux_loop*'.
  - '--mapping' restricts paths to those present in a mapping JSON file.
"""


def _load_config_with_overrides(args: argparse.Namespace) -> CLIConfig | None:
    """Load CLIConfig from file (if it exists) and apply any --set overrides.

    Returns ``None`` when the config file does not exist (graceful degradation
    for subcommands that accept an optional config).
    """
    config_path = Path(getattr(args, "config", "munchi.toml"))
    if not config_path.exists():
        return None
    cfg = load_cli_config(config_path)
    overrides: list[str] = getattr(args, "set", None) or []
    if overrides:
        cfg = apply_config_overrides(cfg, overrides)
    return cfg


def _make_context(
    args: argparse.Namespace,
    *,
    cli_cfg: CLIConfig | None = None,
    shot: int | None = None,
) -> MappingContext:
    """Build a MappingContext, applying --set overrides if present.

    When *cli_cfg* is given it is used directly (avoids re-loading from disk).
    Otherwise ``MappingContext.from_config`` is called as usual.

    *shot* overrides ``args.shot`` when provided (for multi-shot support).
    """
    from .data_source_interface import TokamapInterface as _TokamapInterface
    from .mapper import create_mapper_from_config

    effective_shot = shot if shot is not None else getattr(args, "shot", None)

    if cli_cfg is not None:
        mapper = create_mapper_from_config(cli_cfg)
        resolved_device = getattr(args, "device", None) or cli_cfg.mapper.device
        resolved_shot = (
            effective_shot if effective_shot is not None else cli_cfg.run.default_shot
        )
        tokamap = _TokamapInterface(mapper, resolved_device, shot=resolved_shot)
        return MappingContext(
            mapper=mapper,
            tokamap=tokamap,
            device=resolved_device,
            shot=resolved_shot,
            cli_config=cli_cfg,
            concurrency=cli_cfg.run.concurrency,
        )

    return MappingContext.from_config(
        args.config, device=getattr(args, "device", None), shot=effective_shot
    )


def _apply_log_level(cli_override: str | None, cfg: CLIConfig | None) -> None:
    """Set the root logger level from config, unless the CLI flag was given.

    ``basicConfig`` in ``main()`` always runs first (at WARNING), so this only
    needs to call ``setLevel`` when a different level is required.
    """
    if cli_override is not None:
        return  # already applied in main()
    if cfg is not None:
        logging.getLogger().setLevel(cfg.run.log_level)


def _apply_concurrency_overrides(args: argparse.Namespace, ctx: MappingContext) -> None:
    """Patch ctx.concurrency with any CLI overrides for mode or workers."""
    raw_mode = getattr(args, "concurrency_mode", None)
    raw_workers = getattr(args, "workers", None)
    mode = ConcurrencyMode(raw_mode) if raw_mode is not None else ctx.concurrency.mode
    workers = raw_workers if raw_workers is not None else ctx.concurrency.workers
    if mode is not ctx.concurrency.mode or workers != ctx.concurrency.workers:
        ctx.concurrency = ConcurrencyConfig(mode=mode, workers=workers)
        logger.debug("Concurrency overridden: mode=%s workers=%d", mode.value, workers)


def _resolve_binary_arrays(cli_flag: bool, cfg: CLIConfig | None) -> bool:
    """Return effective binary_arrays setting: CLI flag wins when True."""
    if cli_flag:
        return True
    if cfg is not None:
        return cfg.run.binary_arrays
    return False


def _resolve_on_imas_error(cli_override: str | None, cfg: CLIConfig | None) -> str:
    """Return effective on_imas_error setting: CLI override wins when given."""
    if cli_override is not None:
        return cli_override
    if cfg is not None:
        return cfg.run.on_imas_error
    return "fallback-json"


def _handle_imas_write_errors(
    errors: list[IdsWriteError],
    output_path: Path,
    on_imas_error: str,
    *,
    binary_arrays: bool,
) -> None:
    """Log errors from write_imas_output and apply the configured error strategy."""
    for err in errors:
        msg = f"IDS '{err.ids_name}' failed to write: {err.cause}"
        logger.error(msg)
        print(f"ERROR: {msg}", file=sys.stderr)

    if on_imas_error == "raise":
        raise RuntimeError(
            f"{len(errors)} IDS(es) could not be written to {output_path}. "
            "See log for details."
        )

    # fallback-json: write the failed IDS records to a companion JSON file.
    fallback_path = output_path.with_name(output_path.stem + "_fallback.json")
    fallback_records = [r for err in errors for r in err.records]
    write_json_file(
        fallback_path,
        build_json_results(fallback_records, binary_arrays=binary_arrays),
        force=True,
    )
    print(
        f"Fallback JSON for {len(errors)} failed IDS(es) written to {fallback_path}",
        file=sys.stderr,
    )


def _resolve_paths_arg(values: list[str]) -> list[str]:
    """Return a list of concrete paths from the ``--paths`` argument.

    If exactly one value is given and it names an existing file, the file is
    read and its non-empty, non-comment lines are returned as paths.  Otherwise
    the values themselves are used directly.
    """
    if len(values) == 1:
        candidate = Path(values[0])
        if candidate.is_file():
            paths = [
                line.strip()
                for line in candidate.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            logger.debug("Read %d paths from %s", len(paths), candidate)
            return paths
    return values


def cmd_paths(args: argparse.Namespace) -> int:
    import tqdm as tqdm_mod

    if args.output is not None:
        output_path = Path(args.output)
        if output_path.suffix.lower() != ".json":
            raise ValueError(
                f"Unsupported output file extension for {output_path!s}. Use .json."
            )

    cli_cfg = _load_config_with_overrides(args)
    ctx = _make_context(args, cli_cfg=cli_cfg)
    _apply_log_level(args.log_level, ctx.cli_config)
    logger.info("Loaded config: device=%s shot=%s", ctx.device, ctx.shot)
    helper = ctx.ids_helper(args.ids)

    # Use the number of schema leaf paths as an approximate total for the progress
    # bar. Concrete paths may exceed this when array structs expand to multiple
    # elements, so the percentage can exceed 100 % — this is expected.
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
    logger.info("Found %d concrete paths for IDS '%s'", len(concrete_paths), args.ids)
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


def _shot_output_path(template: str, shot: int) -> Path:
    """Resolve per-shot output path.

    If *template* contains ``{shot}``, substitute it; otherwise insert
    ``_SHOT`` before the file extension (e.g. ``results.json`` →
    ``results_47125.json``).
    """
    if "{shot}" in template:
        return Path(template.format(shot=shot))
    p = Path(template)
    return p.with_name(p.stem + f"_{shot}" + p.suffix)


def _run_mapping_for_shot(
    args: argparse.Namespace,
    cli_cfg: CLIConfig | None,
    shot: int | None,
    *,
    selection: IdsSelection | SinglePathSelection | MultiPathSelection,
    binary_arrays: bool,
    on_imas_error: str,
    dry_run: bool,
    limit: int | None,
    profile_data: Any,
    verbose: bool,
    checkpoint_path: Path | None,
) -> tuple[list[Any], Any, float]:
    """Run mapping for a single shot and return (records, summary, total_wall)."""
    import tqdm as tqdm_mod

    ctx = _make_context(args, cli_cfg=cli_cfg, shot=shot)
    _apply_concurrency_overrides(args, ctx)

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


def cmd_map(args: argparse.Namespace) -> int:
    from .profiling import ProfileData, render_profile_report

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

    cli_cfg = _load_config_with_overrides(args)

    # Resolve log level early using config
    _apply_log_level(args.log_level, cli_cfg)

    binary_arrays = _resolve_binary_arrays(args.binary_arrays, cli_cfg)
    on_imas_error = _resolve_on_imas_error(
        getattr(args, "on_imas_error", None), cli_cfg
    )
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
        resolved = _resolve_paths_arg(args.paths)
        logger.info("Selected %d explicit paths", len(resolved))
        selection = MultiPathSelection(paths=resolved, mapping_keys=mapping_keys)
    else:
        selection = IdsSelection(
            ids=args.ids,
            match=args.match,
            leaves_only=args.leaves_only,
            mapping_keys=mapping_keys,
        )

    # Determine the list of shots to run
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
        shots_list = [single_shot]  # may be None — resolved later per shot

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
            binary_arrays=binary_arrays,
            on_imas_error=on_imas_error,
            dry_run=dry_run,
            limit=limit,
            profile_data=profile_data,
            verbose=verbose,
            checkpoint_path=checkpoint_path,
        )
        all_records.extend(records)
        all_summaries.append(summary)

        logger.info(
            "Results: mapped=%d none=%d suppressed=%d errors=%d",
            summary.mapped,
            summary.returned_none,
            summary.suppressed_errors,
            summary.unexpected_errors,
        )

        if dry_run:
            print(
                f"Dry run: {len(records)} paths expanded in {summary.elapsed_s:.2f}s "
                "(no mapper calls made).",
                file=sys.stderr,
            )
            continue

        # Determine effective output path for this shot
        if output_path_template is not None:
            if multi_shot and shot is not None:
                eff_output = _shot_output_path(output_path_template, shot)
            else:
                eff_output = Path(output_path_template)
        else:
            eff_output = None

        if eff_output is None:
            # Print to terminal
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
            # Checkpointing: save before writing output; delete on success
            _t_before_output = time.perf_counter()

            if checkpoint_path is not None:
                from .checkpoint import Checkpoint, save_checkpoint
                from .outputs import make_json_safe

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
                    _handle_imas_write_errors(
                        write_errors,
                        eff_output,
                        on_imas_error,
                        binary_arrays=binary_arrays,
                    )

            if profile_data is not None:
                profile_data.phases.output_s += time.perf_counter() - _t_before_output

            # Delete checkpoint on successful write
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

    # Combined summary for multi-shot
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


def cmd_convert(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)

    binary_arrays = _resolve_binary_arrays(args.binary_arrays, None)
    on_imas_error = _resolve_on_imas_error(getattr(args, "on_imas_error", None), None)

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
        _handle_imas_write_errors(
            write_errors, output_path, on_imas_error, binary_arrays=binary_arrays
        )
        return 1

    return 0


def cmd_init_config(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    if output_path.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite existing file: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_cli_config_template(), encoding="utf-8")
    print(f"Wrote skeleton config to {output_path}")
    return 0


def cmd_init_mapping(args: argparse.Namespace) -> int:
    mapping = build_blank_mapping_template(
        args.ids,
        leaves_only=args.leaves_only,
    )
    output_path = Path(args.output)
    write_json_file(output_path, mapping, force=args.force)
    print(f"Wrote blank mapping template to {output_path}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    cli_cfg = _load_config_with_overrides(args)
    ctx = _make_context(args, cli_cfg=cli_cfg)
    _apply_log_level(args.log_level, ctx.cli_config)
    print("Config loaded successfully.")
    print(f"Device: {ctx.device}")
    print(f"Shot: {ctx.shot}")

    if args.ids:
        count = check_ids(args.ids, leaves_only=args.leaves_only)
        print(f"IDS recognised: {args.ids}")
        print(f"Schema paths found: {count}")

    return 0


def cmd_update_mapping(args: argparse.Namespace) -> int:
    existing_path = Path(args.mapping)
    merged = merge_mapping_stubs(
        args.ids,
        existing_path,
        leaves_only=args.leaves_only,
    )

    import json as _json

    with existing_path.open(encoding="utf-8") as f:
        existing_keys = set(_json.load(f).keys())
    new_stub_count = sum(1 for k in merged if k not in existing_keys)

    print(f"{new_stub_count} new stub(s) added.", file=sys.stderr)

    if args.output is not None:
        output_path = Path(args.output)
        write_json_file(output_path, merged, force=args.force)
        print(f"Wrote updated mapping to {output_path}")
    else:
        import json as _json2

        print(_json2.dumps(merged, indent=2, ensure_ascii=False))

    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    from .diff import diff_files, render_diff

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


def cmd_update(args: argparse.Namespace) -> int:
    from .convert import read_imas_records
    from .write_ids import SUPPORTED_SUFFIXES as _SUPPORTED

    input_path = Path(args.input)
    output_path = Path(args.output)

    # Load existing records
    in_suffix = input_path.suffix.lower()
    if in_suffix == ".json":
        existing_records = read_json_records(input_path)
    elif in_suffix in _SUPPORTED:
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

    cli_cfg = _load_config_with_overrides(args)
    ctx = _make_context(args, cli_cfg=cli_cfg)
    _apply_log_level(args.log_level, ctx.cli_config)

    mapping_keys = load_mapping_keys(Path(args.mapping)) if args.mapping else None

    if args.ids:
        selection: IdsSelection | SinglePathSelection | MultiPathSelection = (
            IdsSelection(
                ids=args.ids,
                match=None,
                leaves_only=args.leaves_only,
                mapping_keys=mapping_keys,
            )
        )
    else:
        raise ValueError("--ids is required for the update command")

    # Expand all concrete paths
    all_paths = list(generate_selected_paths(selection, ctx))
    new_paths = [p for p in all_paths if p not in existing_paths]
    print(
        f"Found {len(all_paths)} total paths; {len(existing_paths)} already present; "
        f"mapping {len(new_paths)} new path(s).",
        file=sys.stderr,
    )

    if new_paths:
        from .mapping import _map_serial

        raw = _map_serial(ctx.tokamap, new_paths)
        from .mapping import _build_records

        new_records, summary = _build_records(raw, verbose_errors=args.verbose_errors)
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
    elif out_suffix in _SUPPORTED:
        write_errors = write_imas_output(
            output_path, records=merged_records, force=args.force
        )
        print(f"Wrote merged {out_suffix.upper()[1:]} to {output_path}")
        if write_errors:
            _handle_imas_write_errors(
                write_errors, output_path, "fallback-json", binary_arrays=binary_arrays
            )
    else:
        raise ValueError(
            f"Unsupported output format {out_suffix!r}. Use .json, .h5, or .nc."
        )

    return 0


def cmd_completions(args: argparse.Namespace) -> int:
    from .completions import (
        generate_bash_completion,
        generate_fish_completion,
        generate_zsh_completion,
        get_ids_names,
    )

    ids_names = get_ids_names()

    if args.shell == "bash":
        print(generate_bash_completion(ids_names), end="")
    elif args.shell == "zsh":
        print(generate_zsh_completion(ids_names), end="")
    elif args.shell == "fish":
        print(generate_fish_completion(ids_names), end="")
    else:
        raise ValueError(f"Unknown shell {args.shell!r}")

    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=str,
        default="munchi.toml",
        help="munchi config file",
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
        help="Only include leaf paths",
    )
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        default=None,
        help=(
            "Override a config value at runtime, e.g. "
            "--set run.concurrency.mode=thread --set run.concurrency.workers=4. "
            "Can be repeated."
        ),
    )


def add_match_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--match",
        type=str,
        default=None,
        help="Glob-style filter applied to expanded concrete runtime paths, e.g. 'magnetics/flux_loop*'",
    )


def add_ids_or_path_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--ids",
        type=str,
        help="IDS name to expand into concrete runtime paths, e.g. 'magnetics'",
    )
    group.add_argument(
        "--path",
        type=str,
        help="Single concrete runtime path, e.g. 'magnetics/flux_loop[0]/position[0]/r'",
    )
    group.add_argument(
        "--paths",
        nargs="+",
        metavar="PATH_OR_FILE",
        help=(
            "One or more concrete runtime paths, or a single path to a text file "
            "containing newline-delimited paths (lines starting with '#' are ignored)"
        ),
    )


def add_force_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists",
    )


def add_verbose_errors_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--verbose-errors",
        action="store_true",
        help="Show suppressed 'missing mapping' errors as well",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="munchi",
        description="IDS mapping CLI",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity; overrides log_level in config (default: WARNING)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="FILE",
        help="Write log output to FILE in addition to (or instead of) the console",
    )
    parser.add_argument(
        "--log-file-level",
        default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Verbosity for the file log sink (default: DEBUG)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_paths = subparsers.add_parser(
        "paths",
        help="Expand and print concrete IDS runtime paths",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser_paths)
    parser_paths.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name to expand, e.g. 'magnetics'",
    )
    add_match_argument(parser_paths)
    parser_paths.add_argument(
        "--schema-map",
        action="store_true",
        help=(
            "Show each schema path ((:) notation) alongside the concrete path(s) "
            "it expands to. Console: 'schema -> concrete' lines. "
            "JSON: {schema_path: [concrete_path, ...]}."
        ),
    )
    parser_paths.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write output to a JSON file instead of printing to the console",
    )
    add_force_argument(parser_paths)
    parser_paths.set_defaults(func=cmd_paths)

    parser_map = subparsers.add_parser(
        "map",
        help="Map one concrete path or all concrete paths of an IDS",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser_map)
    add_ids_or_path_arguments(parser_map)
    add_match_argument(parser_map)
    add_force_argument(parser_map)
    add_verbose_errors_argument(parser_map)
    parser_map.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output destination. Default: terminal text. Use .json for JSON, .h5 for HDF5, .nc for NetCDF (imas-python required for .h5/.nc).",
    )
    parser_map.add_argument(
        "--mapping",
        type=str,
        default=None,
        metavar="FILE",
        help=(
            "Path to a mapping JSON file. Only IDS paths whose template form "
            "appears as a key in the file will be mapped."
        ),
    )
    parser_map.add_argument(
        "--concurrency-mode",
        default=None,
        choices=["serial", "thread", "process"],
        help="Override concurrency mode from config",
    )
    parser_map.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help="Override number of parallel workers from config",
    )
    parser_map.add_argument(
        "--binary-arrays",
        action="store_true",
        default=False,
        help=(
            "Encode numpy arrays as base64 binary objects in JSON output "
            "(overrides run.binary_arrays in config; default: false)"
        ),
    )
    parser_map.add_argument(
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
    parser_map.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help=(
            "Expand paths only — do not call the mapper. "
            "Useful for checking how many paths will be mapped and "
            "how long path expansion takes."
        ),
    )
    parser_map.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Map at most N paths (after expansion and filtering). Useful for quick tests.",
    )
    parser_map.add_argument(
        "--profile-stats",
        action="store_true",
        dest="profile_stats",
        help=(
            "Print a profiling report after the run: phase timings (expansion / "
            "mapping / output), per-call stats for mapper.map() and "
            "get_array_length(), and bottleneck hints."
        ),
    )
    parser_map.add_argument(
        "--profile",
        default=None,
        metavar="FILE",
        help=(
            "Write a cProfile stats file to FILE for detailed line-level profiling. "
            "Inspect with: python -m pstats FILE  or  snakeviz FILE"
        ),
    )
    parser_map.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help=(
            "Show expanded output for each mapped value (dtype, shape, min/max, "
            "first elements). Errors show full traceback."
        ),
    )
    _shots_group = parser_map.add_mutually_exclusive_group()
    _shots_group.add_argument(
        "--shots",
        nargs="+",
        type=int,
        metavar="N",
        help=(
            "Map these specific shot numbers. "
            "--output is required and may contain {shot} as a template."
        ),
    )
    _shots_group.add_argument(
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
    parser_map.add_argument(
        "--checkpoint",
        default=None,
        metavar="FILE",
        help=(
            "Checkpoint file path. If the file exists, completed paths are skipped "
            "and mapping resumes from where it left off. "
            "The checkpoint is deleted on successful completion."
        ),
    )
    parser_map.set_defaults(func=cmd_map)

    parser_init_config = subparsers.add_parser(
        "init-config",
        help="Create a skeleton munchi config file",
    )
    parser_init_config.add_argument(
        "--output",
        type=str,
        default="munchi.toml",
        help="Output config path",
    )
    add_force_argument(parser_init_config)
    parser_init_config.set_defaults(func=cmd_init_config)

    parser_init_mapping = subparsers.add_parser(
        "init-mapping",
        help="Create a blank JSON mapping template from IDS schema paths",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser_init_mapping.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name, e.g. 'magnetics'",
    )
    parser_init_mapping.add_argument(
        "--output",
        type=str,
        default="mapping.json",
        help="Output mapping JSON path",
    )
    parser_init_mapping.add_argument(
        "--leaves-only",
        action="store_true",
        help="Only include leaf schema paths",
    )
    add_force_argument(parser_init_mapping)
    parser_init_mapping.set_defaults(func=cmd_init_mapping)

    parser_convert = subparsers.add_parser(
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
    parser_convert.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Input file (.json, .h5, or .nc)",
    )
    parser_convert.add_argument(
        "--output",
        required=True,
        metavar="FILE",
        help="Output file (.json, .h5, or .nc)",
    )
    parser_convert.add_argument(
        "--ids",
        nargs="+",
        metavar="IDS",
        default=None,
        help=(
            "IDS name(s) to read when the input is an IMAS file "
            "(e.g. --ids magnetics equilibrium). Not needed for JSON input."
        ),
    )
    parser_convert.add_argument(
        "--binary-arrays",
        action="store_true",
        default=False,
        help="Encode numpy arrays as base64 binary objects in JSON output",
    )
    parser_convert.add_argument(
        "--on-imas-error",
        default=None,
        choices=["fallback-json", "raise"],
        dest="on_imas_error",
        help=(
            "Action when an IDS fails to write: 'fallback-json' (default) writes "
            "failed records to a _fallback.json companion file; 'raise' stops immediately."
        ),
    )
    add_force_argument(parser_convert)
    parser_convert.set_defaults(func=cmd_convert)

    parser_check = subparsers.add_parser(
        "check",
        help="Validate config/mapper setup and optionally an IDS schema",
        epilog=PATH_SYNTAX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser_check)
    parser_check.add_argument(
        "--ids",
        type=str,
        default=None,
        help="Optional IDS name to validate and inspect",
    )
    parser_check.set_defaults(func=cmd_check)

    # ── update-mapping ────────────────────────────────────────────────────────
    parser_update_mapping = subparsers.add_parser(
        "update-mapping",
        help="Add new stub entries to an existing mapping JSON file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser_update_mapping.add_argument(
        "--ids",
        type=str,
        required=True,
        help="IDS name, e.g. 'magnetics'",
    )
    parser_update_mapping.add_argument(
        "--mapping",
        type=str,
        required=True,
        metavar="FILE",
        help="Existing mapping JSON file to update",
    )
    parser_update_mapping.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Output file (default: print JSON to stdout)",
    )
    parser_update_mapping.add_argument(
        "--leaves-only",
        action="store_true",
        help="Only add stubs for leaf schema paths",
    )
    add_force_argument(parser_update_mapping)
    parser_update_mapping.set_defaults(func=cmd_update_mapping)

    # ── diff ──────────────────────────────────────────────────────────────────
    parser_diff = subparsers.add_parser(
        "diff",
        help="Compare two mapping result files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser_diff.add_argument(
        "file_a",
        metavar="FILE_A",
        help="First file (.json, .h5, or .nc)",
    )
    parser_diff.add_argument(
        "file_b",
        metavar="FILE_B",
        help="Second file (.json, .h5, or .nc)",
    )
    parser_diff.add_argument(
        "--ids",
        nargs="+",
        metavar="IDS",
        default=None,
        help="IDS name(s) to read when the input is an IMAS file",
    )
    parser_diff.add_argument(
        "--show-unchanged",
        action="store_true",
        dest="show_unchanged",
        help="Also print unchanged paths",
    )
    parser_diff.set_defaults(func=cmd_diff)

    # ── update ────────────────────────────────────────────────────────────────
    parser_update = subparsers.add_parser(
        "update",
        help="Map missing paths and merge with existing results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_arguments(parser_update)
    parser_update.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Existing result file (.json, .h5, or .nc)",
    )
    parser_update.add_argument(
        "--output",
        required=True,
        metavar="FILE",
        help="Output file (.json, .h5, or .nc)",
    )
    parser_update.add_argument(
        "--ids",
        type=str,
        default=None,
        help="IDS name to map (required for IMAS input; optional for JSON)",
    )
    parser_update.add_argument(
        "--mapping",
        type=str,
        default=None,
        metavar="FILE",
        help="Restrict paths to those present in this mapping JSON file",
    )
    add_force_argument(parser_update)
    add_verbose_errors_argument(parser_update)
    parser_update.set_defaults(func=cmd_update)

    # ── completions ───────────────────────────────────────────────────────────
    parser_completions = subparsers.add_parser(
        "completions",
        help="Generate shell completion scripts",
    )
    parser_completions.add_argument(
        "shell",
        choices=["bash", "zsh", "fish"],
        help="Target shell",
    )
    parser_completions.set_defaults(func=cmd_completions)

    return parser


def _add_file_log_handler(path: str, level: str) -> None:
    """Attach a file handler to the root logger.

    The file handler uses a timestamped format so log entries can be
    correlated with wall-clock time when inspecting errors offline.
    The root logger level is lowered to ``level`` if it is currently
    more restrictive, ensuring the new handler actually receives records.
    """
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.addHandler(handler)
    # The root logger acts as a gate: if its level is higher than the handler's
    # level, records are discarded before reaching the handler.
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
