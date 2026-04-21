from __future__ import annotations

import base64
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from ..mapping.runner import MappingRecord, MappingSummary


def format_value(value: Any) -> str:
    """Format a mapped value compactly for terminal display.

    - numpy arrays: ``dtype[DxD] min=X max=Y [a, b, c, ...]``
    - Python lists with >6 elements: ``list[N] [a, b, c, ...]``
    - Everything else: ``str(value)``
    """
    # numpy array — detected by presence of .dtype and .shape
    if hasattr(value, "dtype") and hasattr(value, "shape"):
        dtype_str = str(value.dtype)
        shape_str = "x".join(str(d) for d in value.shape)
        # Try to compute min/max for numeric dtypes
        try:
            import numpy as np

            mn = np.min(value)
            mx = np.max(value)
            stats = f" min={mn:.4g} max={mx:.4g}"
        except (TypeError, ValueError):
            stats = ""
        # First 3 elements
        flat = value.flat if hasattr(value, "flat") else iter(value)
        first3 = []
        for i, v in enumerate(flat):
            if i >= 3:
                break
            first3.append(f"{v:.4g}" if isinstance(v, float) else str(v))
        total = value.size if hasattr(value, "size") else len(value)
        ellipsis_suffix = ", ..." if total > 3 else ""
        preview = "[" + ", ".join(first3) + ellipsis_suffix + "]"
        return f"{dtype_str}[{shape_str}]{stats} {preview}"

    # Python list with more than 6 elements
    if isinstance(value, list) and len(value) > 6:
        n = len(value)
        first3 = [str(v) for v in value[:3]]
        preview = "[" + ", ".join(first3) + ", ...]"
        return f"list[{n}] {preview}"

    return str(value)


def _encode_ndarray_binary(arr: Any) -> dict[str, Any]:
    """Encode a numpy array as a base64 binary blob with dtype/shape metadata."""
    return {
        "__ndarray__": base64.b64encode(arr.tobytes()).decode("ascii"),
        "dtype": str(arr.dtype),
        "shape": list(arr.shape),
    }


def make_json_safe(value: Any, *, binary_arrays: bool = False) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {
            str(k): make_json_safe(v, binary_arrays=binary_arrays)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [make_json_safe(v, binary_arrays=binary_arrays) for v in value]
    if binary_arrays and hasattr(value, "dtype") and hasattr(value, "tobytes"):
        return _encode_ndarray_binary(value)
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass
    return str(value)


def build_json_results(
    records: list[MappingRecord], *, binary_arrays: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for record in records:
        if record.ok and record.value is not None:
            result[record.ids_path] = make_json_safe(
                record.value, binary_arrays=binary_arrays
            )
    return result


def render_text_records(records: list[MappingRecord], *, verbose_errors: bool) -> str:
    lines: list[str] = []
    for record in records:
        if record.ok:
            if record.value is not None:
                lines.append(f"{record.ids_path}: {format_value(record.value)}")
        else:
            if verbose_errors or not record.suppressed:
                lines.append(f"{record.ids_path}: {record.error}")
    return "\n".join(lines)


def render_verbose_records(
    records: list[MappingRecord], *, verbose_errors: bool
) -> str:
    """Render records in an expanded block format with tracebacks for errors."""
    lines: list[str] = []
    for record in records:
        if record.ok:
            if record.value is not None:
                lines.append(record.ids_path)
                lines.append(f"  value: {format_value(record.value)}")
        else:
            show = verbose_errors or not record.suppressed
            if show:
                lines.append(record.ids_path)
                if record.error is not None:
                    tb = "".join(
                        traceback.format_exception(
                            type(record.error), record.error, record.error.__traceback__
                        )
                    ).rstrip()
                    for tb_line in tb.splitlines():
                        lines.append(f"  {tb_line}")
                else:
                    lines.append("  <error>")
    return "\n".join(lines)


def print_summary(summary: MappingSummary) -> None:
    print(
        f"Summary: scanned {summary.total_paths} paths; mapped {summary.mapped}; "
        f"returned None {summary.returned_none}; suppressed {summary.suppressed_errors}; "
        f"unexpected errors {summary.unexpected_errors}; "
        f"elapsed {summary.elapsed_s:.2f}s.",
        file=sys.stderr,
    )


def build_schema_map(concrete_paths: list[str]) -> dict[str, list[str]]:
    """Group concrete paths by their schema path."""
    from ..ids.parsing import concrete_path_to_schema_path

    result: dict[str, list[str]] = {}
    for p in concrete_paths:
        schema = concrete_path_to_schema_path(p)
        result.setdefault(schema, []).append(p)
    return result


def render_text_schema_map(schema_map: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for schema_path, concrete_paths in schema_map.items():
        for cp in concrete_paths:
            lines.append(f"{schema_path} -> {cp}")
    return "\n".join(lines)


def write_json_file(path: Path, data: Any, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
