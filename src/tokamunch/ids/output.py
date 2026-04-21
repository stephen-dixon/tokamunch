"""IMAS file output: write mapped records to HDF5 or NetCDF via imas-python."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..types import IDSNode, NodeType, WriteContext
from .mutation import ensure_ids_arrays_resized, resize_and_set_ids_value
from .parsing import parse_concrete_path, render_array_length_query_path

logger = logging.getLogger(__name__)

# Supported output formats and their imas-python URI schemes.
SUPPORTED_SUFFIXES = {".h5", ".nc"}


@dataclass
class IdsWriteError:
    """Captures a per-IDS write failure together with the records that couldn't be written."""

    ids_name: str
    records: list[Any]  # list[MappingRecord] — typed as Any to avoid circular import
    cause: Exception


def _derive_array_sizes(paths: list[str]) -> dict[str, int]:
    """Compute required sizes for all array-struct nodes from a set of concrete paths.

    Returns a dict mapping query paths (e.g. ``"magnetics/flux_loop"``,
    ``"magnetics/flux_loop[0]/position"``) to the required array length,
    derived from the maximum index seen across all supplied paths.
    """
    sizes: dict[str, int] = {}
    for path in paths:
        segs = list(parse_concrete_path(path))
        built: list[IDSNode] = []
        for seg in segs:
            if seg.node_type is NodeType.ARRAY_STRUCT:
                assert seg.index is not None  # parse_concrete_path always sets index
                query_path = render_array_length_query_path(
                    [*built, IDSNode(seg.name, NodeType.ARRAY_STRUCT, None)]
                )
                sizes[query_path] = max(sizes.get(query_path, 0), seg.index + 1)
            built.append(seg)
    return sizes


def group_records_by_ids(records: list[Any]) -> dict[str, list[Any]]:
    """Split successfully-mapped records by IDS name (first path segment)."""
    groups: dict[str, list[Any]] = {}
    for record in records:
        if not record.ok or record.value is None:
            continue
        ids_name = record.ids_path.split("/")[0]
        groups.setdefault(ids_name, []).append(record)
    return groups


def populate_ids(
    ids_obj: Any,
    records: list[Any],
    *,
    array_sizes: dict[str, int] | None = None,
) -> None:
    """Write mapped values from *records* into an imas IDS object.

    Records whose final path segment is an array-struct node (e.g.
    ``equilibrium/time_slice[0]``) are treated as non-leaf nodes: the
    corresponding IDS array is resized to accommodate the index, but no value
    is assigned.

    *array_sizes* may be supplied by callers that already hold the expansion
    cache (e.g. ``IDSHelper.array_sizes``) and know that no path filters were
    applied.  When ``None``, sizes are derived from the records themselves via
    ``_derive_array_sizes``.
    """
    if array_sizes is None:
        array_sizes = _derive_array_sizes([r.ids_path for r in records])
    ctx = WriteContext()
    for record in records:
        segs = list(parse_concrete_path(record.ids_path))
        if segs and segs[-1].node_type is NodeType.ARRAY_STRUCT:
            ensure_ids_arrays_resized(
                ids_obj, segs, array_sizes, write_context=ctx, skip_root_segment=True
            )
        else:
            resize_and_set_ids_value(
                ids_obj,
                segs,
                record.value,
                array_sizes,
                write_context=ctx,
                skip_root_segment=True,
            )


def imas_uri(path: Path) -> str:
    """Build the imas-python DBEntry URI for the given output path."""
    if path.suffix.lower() == ".h5":
        return f"imas:hdf5?path={path.with_suffix('')}"
    return str(path)


def write_imas_output(
    path: Path,
    *,
    records: list[Any],
    force: bool,
    array_sizes: dict[str, int] | None = None,
) -> list[IdsWriteError]:
    """Write mapped IDS records to an HDF5 or NetCDF file via imas-python.

    The output format is inferred from the file extension:

    - ``.h5`` — IMAS HDF5 backend (requires ``imas-core``)
    - ``.nc`` — IMAS NetCDF backend

    Records with errors or ``None`` values are silently skipped. Each distinct
    IDS name found in the records (e.g. ``magnetics``, ``equilibrium``) is
    written as a separate ``dbentry.put()`` call.

    Returns a (possibly empty) list of :class:`IdsWriteError` — one entry per
    IDS whose ``dbentry.put()`` call raised an exception.

    Raises ``FileExistsError`` if *path* already exists and *force* is false.
    Raises ``ImportError`` if ``imas`` is not installed.
    """
    import imas  # optional dependency — only needed for IMAS file output

    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")

    factory = imas.IDSFactory()
    groups = group_records_by_ids(records)
    uri = imas_uri(path)
    write_errors: list[IdsWriteError] = []

    with imas.DBEntry(uri, "w") as dbentry:
        for ids_name, ids_records in groups.items():
            try:
                ids_obj = getattr(factory, ids_name)()
                populate_ids(ids_obj, ids_records, array_sizes=array_sizes)
                dbentry.put(ids_obj)
            except Exception as exc:
                logger.error("Failed to write IDS '%s': %s", ids_name, exc)
                write_errors.append(IdsWriteError(ids_name, ids_records, exc))

    return write_errors
