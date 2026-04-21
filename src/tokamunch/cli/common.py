"""Shared helpers used across CLI command implementations."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ..core.config import (
    CLIConfig,
    ConcurrencyConfig,
    ConcurrencyMode,
    apply_config_overrides,
    load_cli_config,
)
from ..core.context import MappingContext
from ..ids.output import IdsWriteError
from ..io.outputs import build_json_results, write_json_file

logger = logging.getLogger(__name__)


def load_config_with_overrides(args: argparse.Namespace) -> CLIConfig | None:
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


def make_context(
    args: argparse.Namespace,
    *,
    cli_cfg: CLIConfig | None = None,
    shot: int | None = None,
) -> MappingContext:
    """Build a MappingContext, applying --set overrides if present.

    When *cli_cfg* is given it is used directly (avoids re-loading from disk).
    *shot* overrides ``args.shot`` when provided (for multi-shot support).
    """
    from ..mapping.data_source import TokamapInterface
    from ..mapping.mapper_factory import create_mapper_from_config

    effective_shot = shot if shot is not None else getattr(args, "shot", None)

    if cli_cfg is not None:
        mapper = create_mapper_from_config(cli_cfg)
        resolved_device = getattr(args, "device", None) or cli_cfg.mapper.device
        resolved_shot = (
            effective_shot if effective_shot is not None else cli_cfg.run.default_shot
        )
        tokamap = TokamapInterface(mapper, resolved_device, shot=resolved_shot)
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


def apply_log_level(cli_override: str | None, cfg: CLIConfig | None) -> None:
    """Set the root logger level from config, unless the CLI flag was given."""
    if cli_override is not None:
        return  # already applied in main()
    if cfg is not None:
        logging.getLogger().setLevel(cfg.run.log_level)


def apply_concurrency_overrides(args: argparse.Namespace, ctx: MappingContext) -> None:
    """Patch ctx.concurrency with any CLI overrides for mode or workers."""
    raw_mode = getattr(args, "concurrency_mode", None)
    raw_workers = getattr(args, "workers", None)
    mode = ConcurrencyMode(raw_mode) if raw_mode is not None else ctx.concurrency.mode
    workers = raw_workers if raw_workers is not None else ctx.concurrency.workers
    if mode is not ctx.concurrency.mode or workers != ctx.concurrency.workers:
        ctx.concurrency = ConcurrencyConfig(mode=mode, workers=workers)
        logger.debug("Concurrency overridden: mode=%s workers=%d", mode.value, workers)


def resolve_binary_arrays(cli_flag: bool, cfg: CLIConfig | None) -> bool:
    """Return effective binary_arrays setting: CLI flag wins when True."""
    if cli_flag:
        return True
    if cfg is not None:
        return cfg.run.binary_arrays
    return False


def resolve_on_imas_error(cli_override: str | None, cfg: CLIConfig | None) -> str:
    """Return effective on_imas_error setting: CLI override wins when given."""
    if cli_override is not None:
        return cli_override
    if cfg is not None:
        return cfg.run.on_imas_error
    return "fallback-json"


def handle_imas_write_errors(
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


def resolve_paths_arg(values: list[str]) -> list[str]:
    """Return a list of concrete paths from the ``--paths`` argument.

    If exactly one value is given and it names an existing file, the file is
    read and its non-empty, non-comment lines are returned as paths.
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


def shot_output_path(template: str, shot: int) -> Path:
    """Resolve per-shot output path.

    If *template* contains ``{shot}``, substitute it; otherwise insert
    ``_SHOT`` before the file extension (e.g. ``results.json`` →
    ``results_47125.json``).
    """
    if "{shot}" in template:
        return Path(template.format(shot=shot))
    p = Path(template)
    return p.with_name(p.stem + f"_{shot}" + p.suffix)
