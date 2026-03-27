from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

from .mapping import MappingRecord, MappingSummary


def _encode_ndarray_binary(arr: Any) -> dict[str, Any]:
    """Encode a numpy array as a base64 binary blob with dtype/shape metadata.

    The resulting dict is JSON-serialisable and can be decoded with::

        import base64, numpy as np
        np.frombuffer(base64.b64decode(d["__ndarray__"]), dtype=d["dtype"]).reshape(d["shape"])
    """
    return {
        "__ndarray__": base64.b64encode(arr.tobytes()).decode("ascii"),
        "dtype": str(arr.dtype),
        "shape": list(arr.shape),
    }


def make_json_safe(value: Any, *, binary_arrays: bool = False) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): make_json_safe(v, binary_arrays=binary_arrays) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [make_json_safe(v, binary_arrays=binary_arrays) for v in value]
    if binary_arrays and hasattr(value, "dtype") and hasattr(value, "tobytes"):
        return _encode_ndarray_binary(value)
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


def build_json_results(
    records: list[MappingRecord], *, binary_arrays: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for record in records:
        if record.ok and record.value is not None:
            result[record.ids_path] = make_json_safe(record.value, binary_arrays=binary_arrays)
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
        f"unexpected errors {summary.unexpected_errors}; "
        f"elapsed {summary.elapsed_s:.2f}s.",
        file=sys.stderr,
    )


def build_schema_map(concrete_paths: list[str]) -> dict[str, list[str]]:
    """Group concrete paths by their schema path.

    Returns an ordered dict mapping each distinct schema path (in ``(:)``
    notation) to the list of concrete paths that expand from it.
    """
    from .parsing import concrete_path_to_schema_path

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
