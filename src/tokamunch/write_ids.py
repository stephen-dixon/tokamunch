from __future__ import annotations

from pathlib import Path
from typing import Any

from .ids_writer import resize_and_set_ids_value
from .mapping import MappingRecord
from .parsing import IDSNode, NodeType, parse_concrete_path, render_array_length_query_path
from .types import WriteContext

# Supported output formats and their imas-python URI schemes.
SUPPORTED_SUFFIXES = {".h5", ".nc"}


def _derive_array_sizes(paths: list[str]) -> dict[str, int]:
    """Compute required sizes for all array-struct nodes from a set of concrete paths.

    Returns a dict mapping query paths (e.g. ``"magnetics/flux_loop"``,
    ``"magnetics/flux_loop[0]/position"``) to the required array length,
    derived from the maximum index seen across all supplied paths.

    Sizes are derived from the records rather than taken from the expansion
    cache (``IDSHelper.array_sizes``) so that path filters (``--match``,
    ``--mapping``, ``leaves_only``) are respected.  Using the expansion cache
    would resize arrays to the full device size even when only a filtered
    subset of paths is being written, creating empty array elements in the
    output file for data that was never mapped.
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


def _group_records_by_ids(records: list[MappingRecord]) -> dict[str, list[MappingRecord]]:
    """Split successfully-mapped records by IDS name (first path segment)."""
    groups: dict[str, list[MappingRecord]] = {}
    for record in records:
        if not record.ok or record.value is None:
            continue
        ids_name = record.ids_path.split("/")[0]
        groups.setdefault(ids_name, []).append(record)
    return groups


def _populate_ids(
    ids_obj: Any,
    records: list[MappingRecord],
    *,
    array_sizes: dict[str, int] | None = None,
) -> None:
    """Write mapped values from *records* into an imas IDS object.

    Array-struct nodes are resized once (tracked via ``WriteContext``) before
    any values are set. Records whose final segment is an array-struct node
    (i.e. the path points to a struct array rather than a scalar/array field)
    are skipped — those nodes are sized by the resize pass only.

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
            continue
        resize_and_set_ids_value(
            ids_obj,
            segs,
            record.value,
            array_sizes,
            write_context=ctx,
            skip_root_segment=True,
        )


def _imas_uri(path: Path) -> str:
    """Build the imas-python DBEntry URI for the given output path."""
    if path.suffix.lower() == ".h5":
        # The imas HDF5 backend manages its own file naming; strip the extension.
        return f"imas:hdf5?path={path.with_suffix('')}"
    # NetCDF: pass the path directly.
    return str(path)


def write_imas_output(
    path: Path,
    *,
    records: list[MappingRecord],
    force: bool,
    array_sizes: dict[str, int] | None = None,
) -> None:
    """Write mapped IDS records to an HDF5 or NetCDF file via imas-python.

    The output format is inferred from the file extension:

    - ``.h5`` — IMAS HDF5 backend (requires ``imas-core``)
    - ``.nc`` — IMAS NetCDF backend

    Records with errors or ``None`` values are silently skipped. Each distinct
    IDS name found in the records (e.g. ``magnetics``, ``equilibrium``) is
    written as a separate ``dbentry.put()`` call.

    *array_sizes* is an optional shortcut for callers that already hold the
    expansion-context cache (e.g. ``IDSHelper.array_sizes``) **and** know that
    no path filters were applied.  When omitted, sizes are derived from the
    records themselves so that filtered subsets are written correctly without
    creating empty array elements in the output file.

    Raises ``FileExistsError`` if *path* already exists and *force* is false.
    Raises ``ImportError`` if ``imas`` is not installed.
    """
    import imas  # optional dependency — only needed for IMAS file output

    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")

    factory = imas.IDSFactory()
    groups = _group_records_by_ids(records)
    uri = _imas_uri(path)

    with imas.DBEntry(uri, "w") as dbentry:
        for ids_name, ids_records in groups.items():
            ids_obj = getattr(factory, ids_name)()
            _populate_ids(ids_obj, ids_records, array_sizes=array_sizes)
            dbentry.put(ids_obj)
