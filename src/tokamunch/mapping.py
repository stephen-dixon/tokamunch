from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .context import CLIContext
from .selection import PathSelection, iter_selected_paths


def should_suppress_mapping_error(exc: Exception) -> bool:
    return str(exc).startswith("Mapping error: failed to find mapping for")


def normalise_map_result(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "dtype") and value.dtype == "S1":
        return value.tobytes().decode()
    return value


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


def map_path(ctx: CLIContext, ids_path: str) -> Any:
    return normalise_map_result(ctx.tokamap.map(ids_path))


def collect_mapped_values(
    ctx: CLIContext,
    selection: PathSelection,
    *,
    verbose_errors: bool,
) -> tuple[list[MappingRecord], MappingSummary]:
    records: list[MappingRecord] = []
    summary = MappingSummary()

    for ids_path in iter_selected_paths(selection, ctx):
        summary.total_paths += 1
        try:
            value = map_path(ctx, ids_path)
            if value is None:
                summary.returned_none += 1
                records.append(MappingRecord(ids_path=ids_path, value=None))
            else:
                summary.mapped += 1
                records.append(MappingRecord(ids_path=ids_path, value=value))
        except Exception as exc:
            suppressed = not verbose_errors and should_suppress_mapping_error(exc)
            if suppressed:
                summary.suppressed_errors += 1
            else:
                summary.unexpected_errors += 1
            records.append(MappingRecord(ids_path=ids_path, error=exc, suppressed=suppressed))

    return records, summary
