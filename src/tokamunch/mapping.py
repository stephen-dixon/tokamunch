from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, TypeAlias

from .config import CLIConfig, ConcurrencyMode
from .context import MappingContext
from .data_source_interface import (
    _MISSING_MAPPING_PREFIX,
    TokamapInterface,
    _decode_s1_bytes,
)
from .selection import Selection, generate_selected_paths

# ── error classification ──────────────────────────────────────────────────────


def should_suppress_mapping_error(exc: Exception) -> bool:
    return str(exc).startswith(_MISSING_MAPPING_PREFIX)


# ── result normalisation ──────────────────────────────────────────────────────


def normalise_map_result(value: Any) -> Any:
    if value is None:
        return None
    return _decode_s1_bytes(value)


# ── record types ──────────────────────────────────────────────────────────────


@dataclass
class MappingRecord:
    ids_path: str
    value: Any | None = None
    error: Exception | None = None
    suppressed: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class MappingSummary:
    total_paths: int = 0
    mapped: int = 0
    returned_none: int = 0
    suppressed_errors: int = 0
    unexpected_errors: int = 0

    @property
    def has_unexpected_errors(self) -> bool:
        return self.unexpected_errors > 0


# ── process-worker state ──────────────────────────────────────────────────────
# Each worker process holds its own independently initialised mapper.
# Module-level so ProcessPoolExecutor can pickle these functions by name.

_worker_tokamap: TokamapInterface | None = None


def _init_process_worker(cli_config: CLIConfig, device: str, shot: int | None) -> None:
    """Run once per worker process to build a process-local mapper from a CLIConfig."""
    global _worker_tokamap
    from .mapper import create_mapper_from_config

    mapper = create_mapper_from_config(cli_config)
    _worker_tokamap = TokamapInterface(mapper, device, shot=shot)


def _process_worker_map(ids_path: str) -> tuple[str, Any, str | None]:
    """Map one path in a worker process. Returns (path, value, error_str).

    Errors are returned as strings rather than exception objects to avoid
    pickling failures for C-extension exceptions from libtokamap/plugins.
    """
    assert _worker_tokamap is not None, "Worker process was not initialised"
    try:
        value = normalise_map_result(_worker_tokamap.map(ids_path))
        return ids_path, value, None
    except Exception as exc:
        return ids_path, None, str(exc)


# ── raw result type ───────────────────────────────────────────────────────────
# (ids_path, value_or_None, exception_or_None)

_RawResult: TypeAlias = tuple[str, Any, Exception | None]


# ── execution strategies ──────────────────────────────────────────────────────


def _map_serial(tokamap: TokamapInterface, paths: list[str]) -> list[_RawResult]:
    results: list[_RawResult] = []
    for path in paths:
        try:
            results.append((path, normalise_map_result(tokamap.map(path)), None))
        except Exception as exc:
            results.append((path, None, exc))
    return results


def _thread_map_one(tokamap: TokamapInterface, path: str) -> Any:
    return normalise_map_result(tokamap.map(path))


def _map_threaded(
    tokamap: TokamapInterface, paths: list[str], workers: int
) -> list[_RawResult]:
    """Map paths concurrently using threads. Requires all plugins to be thread-safe."""
    results: list[_RawResult] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_thread_map_one, tokamap, path): path for path in paths}
        for future in as_completed(futures):
            path = futures[future]
            try:
                results.append((path, future.result(), None))
            except Exception as exc:
                results.append((path, None, exc))
    return results


def _map_multiprocess(
    cli_config: CLIConfig,
    device: str,
    shot: int | None,
    paths: list[str],
    workers: int,
) -> list[_RawResult]:
    """Map paths concurrently using processes. Each worker builds its own mapper."""
    results: list[_RawResult] = []
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_process_worker,
        initargs=(cli_config, device, shot),
    ) as pool:
        futures = {pool.submit(_process_worker_map, path): path for path in paths}
        for future in as_completed(futures):
            path = futures[future]
            try:
                _path, value, error_str = future.result()
                if error_str is not None:
                    results.append((_path, None, RuntimeError(error_str)))
                else:
                    results.append((_path, value, None))
            except Exception as exc:
                results.append((path, None, exc))
    return results


# ── record assembly ───────────────────────────────────────────────────────────


def _build_records(
    raw_results: list[_RawResult],
    *,
    verbose_errors: bool,
) -> tuple[list[MappingRecord], MappingSummary]:
    records: list[MappingRecord] = []
    summary = MappingSummary(total_paths=len(raw_results))

    for ids_path, value, exc in raw_results:
        if exc is None:
            if value is None:
                summary.returned_none += 1
                records.append(MappingRecord(ids_path=ids_path, value=None))
            else:
                summary.mapped += 1
                records.append(MappingRecord(ids_path=ids_path, value=value))
        else:
            suppressed = not verbose_errors and should_suppress_mapping_error(exc)
            if suppressed:
                summary.suppressed_errors += 1
            else:
                summary.unexpected_errors += 1
            records.append(
                MappingRecord(ids_path=ids_path, error=exc, suppressed=suppressed)
            )

    return records, summary


# ── public API ────────────────────────────────────────────────────────────────


def map_path(ctx: MappingContext, ids_path: str) -> Any:
    return normalise_map_result(ctx.tokamap.map(ids_path))


def collect_mapped_values(
    ctx: MappingContext,
    selection: Selection,
    *,
    verbose_errors: bool,
) -> tuple[list[MappingRecord], MappingSummary]:
    # Phase 1: expand all concrete paths (includes remote array-length queries).
    paths = list(generate_selected_paths(selection, ctx))

    # Phase 2: map each path, dispatching to the configured concurrency backend.
    concurrency = ctx.concurrency
    if concurrency.mode == ConcurrencyMode.SERIAL or concurrency.workers <= 1:
        raw = _map_serial(ctx.tokamap, paths)
    elif concurrency.mode == ConcurrencyMode.THREAD:
        raw = _map_threaded(ctx.tokamap, paths, concurrency.workers)
    elif concurrency.mode == ConcurrencyMode.PROCESS:
        if ctx.cli_config is None:
            raise RuntimeError(
                "Process-based concurrency requires a CLIConfig. "
                "Use MappingContext.from_config() or set cli_config explicitly."
            )
        raw = _map_multiprocess(
            ctx.cli_config, ctx.device, ctx.shot, paths, concurrency.workers
        )
    else:
        raise ValueError(f"Unknown concurrency mode: {concurrency.mode!r}")

    return _build_records(raw, verbose_errors=verbose_errors)
