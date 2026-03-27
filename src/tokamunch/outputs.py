from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .mapping import MappingRecord, MappingSummary


def make_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [make_json_safe(v) for v in value]
    if hasattr(value, "tolist"):
        # numpy's tolist() recurses into nested arrays, producing pure Python
        # types at every level — no need for a second make_json_safe pass.
        return value.tolist()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass
    return str(value)


def build_json_results(records: list[MappingRecord]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for record in records:
        if record.ok and record.value is not None:
            result[record.ids_path] = make_json_safe(record.value)
    return result


def render_text_records(records: list[MappingRecord], *, verbose_errors: bool) -> str:
    lines: list[str] = []
    for record in records:
        if record.ok:
            if record.value is not None:
                lines.append(f"{record.ids_path}: {record.value}")
        else:
            if verbose_errors or not record.suppressed:
                lines.append(f"{record.ids_path}: {record.error}")
    return "\n".join(lines)


def print_summary(summary: MappingSummary) -> None:
    print(
        f"Summary: scanned {summary.total_paths} paths; mapped {summary.mapped}; "
        f"returned None {summary.returned_none}; suppressed {summary.suppressed_errors}; "
        f"unexpected errors {summary.unexpected_errors}.",
        file=sys.stderr,
    )


def write_json_file(path: Path, data: Any, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
