"""Diff utilities for comparing two sets of tokamunch mapping records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mapping import MappingRecord


@dataclass
class DiffEntry:
    """A single entry in a mapping diff."""

    path: str
    value_a: Any
    """Value from the first file, or ``None`` if the path was absent."""
    value_b: Any
    """Value from the second file, or ``None`` if the path was absent."""
    status: str
    """One of ``"added"``, ``"removed"``, ``"changed"``, ``"unchanged"``."""


def _values_equal(a: Any, b: Any) -> bool:
    """Return True when *a* and *b* should be considered the same."""
    try:
        import numpy as np

        if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
            if a.shape != b.shape or a.dtype.kind != b.dtype.kind:
                return False
            if np.issubdtype(a.dtype, np.floating) or np.issubdtype(
                a.dtype, np.complexfloating
            ):
                return bool(np.allclose(a, b, equal_nan=True))
            return bool(np.array_equal(a, b))
    except ImportError:
        pass
    return bool(a == b)


def diff_records(
    records_a: list[MappingRecord],
    records_b: list[MappingRecord],
) -> list[DiffEntry]:
    """Compare two sets of mapping records.

    Parameters
    ----------
    records_a, records_b:
        Lists of ``MappingRecord`` objects from two separate mapping runs or
        files.

    Returns
    -------
    list[DiffEntry]
        One entry per unique path across both sets.  The order is: paths
        present in A (in their original order), then paths only in B
        (alphabetically).  ``"unchanged"`` entries are included so that callers
        can compute statistics.
    """
    map_a = {r.ids_path: r.value for r in records_a if r.ok}
    map_b = {r.ids_path: r.value for r in records_b if r.ok}

    entries: list[DiffEntry] = []
    seen: set[str] = set()

    for path in map_a:
        seen.add(path)
        if path not in map_b:
            entries.append(
                DiffEntry(
                    path=path, value_a=map_a[path], value_b=None, status="removed"
                )
            )
        else:
            try:
                equal = _values_equal(map_a[path], map_b[path])
            except Exception:
                equal = False
            status = "unchanged" if equal else "changed"
            entries.append(
                DiffEntry(
                    path=path, value_a=map_a[path], value_b=map_b[path], status=status
                )
            )

    for path in sorted(p for p in map_b if p not in seen):
        entries.append(
            DiffEntry(path=path, value_a=None, value_b=map_b[path], status="added")
        )

    return entries


def render_diff(
    entries: list[DiffEntry],
    label_a: str,
    label_b: str,
    *,
    show_unchanged: bool = False,
) -> str:
    """Render a human-readable diff.

    Lines are prefixed with:
    * ``+`` for added paths (in B but not A)
    * ``-`` for removed paths (in A but not B)
    * ``~`` for changed values
    * `` `` (space) for unchanged (only shown when *show_unchanged* is True)
    """
    from .outputs import _format_value

    lines: list[str] = [
        f"--- {label_a}",
        f"+++ {label_b}",
    ]

    for entry in entries:
        if entry.status == "unchanged":
            if show_unchanged:
                lines.append(f"  {entry.path}: {_format_value(entry.value_a)}")
        elif entry.status == "added":
            lines.append(f"+ {entry.path}: {_format_value(entry.value_b)}")
        elif entry.status == "removed":
            lines.append(f"- {entry.path}: {_format_value(entry.value_a)}")
        elif entry.status == "changed":
            lines.append(
                f"~ {entry.path}: {_format_value(entry.value_a)} → {_format_value(entry.value_b)}"
            )

    # Summary counts
    added = sum(1 for e in entries if e.status == "added")
    removed = sum(1 for e in entries if e.status == "removed")
    changed = sum(1 for e in entries if e.status == "changed")
    unchanged = sum(1 for e in entries if e.status == "unchanged")
    lines.append(
        f"Summary: {added} added, {removed} removed, {changed} changed, {unchanged} unchanged"
    )

    return "\n".join(lines)


def diff_files(
    path_a: Path,
    path_b: Path,
    *,
    ids_names: list[str] | None = None,
) -> list[DiffEntry]:
    """Load two files and return diff entries.

    Supports ``.json`` (munchi JSON output) and IMAS files (``.h5``, ``.nc``).
    For IMAS files, *ids_names* must be supplied.

    Parameters
    ----------
    path_a, path_b:
        Input files to compare.
    ids_names:
        IDS names to read from IMAS files.  Ignored for JSON input.
    """
    from .convert import read_imas_records, read_json_records
    from .write_ids import SUPPORTED_SUFFIXES

    def _read(path: Path) -> list[MappingRecord]:
        suffix = path.suffix.lower()
        if suffix == ".json":
            return read_json_records(path)
        if suffix in SUPPORTED_SUFFIXES:
            if not ids_names:
                raise ValueError(
                    f"Reading IMAS file {path} requires --ids (one or more IDS names)."
                )
            return read_imas_records(path, ids_names)
        raise ValueError(
            f"Unsupported file format {suffix!r} for {path}. Use .json, .h5, or .nc."
        )

    records_a = _read(path_a)
    records_b = _read(path_b)
    return diff_records(records_a, records_b)
