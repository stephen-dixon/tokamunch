"""Format conversion utilities for tokamunch IDS data.

Provides functions for moving data between the formats that tokamunch
understands: imas-python HDF5/NetCDF files, munchi JSON output, and
in-memory imas IDS objects.

Primary use case — load a non-compliant JSON into IDS objects so that
missing fields can be added before a validated IMAS write::

    from tokamunch.convert import read_json_records, records_to_ids_objects
    import imas

    records = read_json_records(Path("results.json"))
    ids_objects = records_to_ids_objects(records)

    eq = ids_objects["equilibrium"]
    eq.time_slice[0].time = 0.5   # add missing required field

    with imas.DBEntry("imas:hdf5?path=output", "w") as db:
        db.put(eq)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .ids_writer import ensure_ids_arrays_resized, resize_and_set_ids_value
from .ids_helper import IDSHelper
from .mapping import MappingRecord
from .parsing import IDSNode, NodeType, parse_concrete_path
from .types import WriteContext
from .write_ids import (
    IdsWriteError,
    _derive_array_sizes,
    _group_records_by_ids,
    _imas_uri,
    _populate_ids,
    SUPPORTED_SUFFIXES,
)

logger = logging.getLogger(__name__)


# ── reading from IDS objects ──────────────────────────────────────────────────


def _ids_length_callback(ids_obj: Any) -> Callable[[str], int]:
    """Return a get_array_length callback that reads sizes from an IDS object.

    The callback accepts a query path in the same format produced by
    ``render_array_length_query_path`` — e.g. ``"magnetics/flux_loop"`` or
    ``"magnetics/flux_loop[0]/position"``.  The final segment is always a bare
    field name (no index); all preceding ARRAY_STRUCT segments carry concrete
    indices.
    """

    def get_length(query_path: str) -> int:
        node = ids_obj
        segs = list(parse_concrete_path(query_path))
        for seg in segs[1:]:  # skip IDS name (first segment)
            try:
                child = getattr(node, seg.name)
            except AttributeError:
                return 0
            if seg.node_type is NodeType.ARRAY_STRUCT:
                # Concrete indexed segment — step inside the array element.
                try:
                    node = child[seg.index]
                except (IndexError, TypeError):
                    return 0
            else:
                # Bare name = the array we are measuring.
                try:
                    return len(child)
                except TypeError:
                    return 0
        return 0

    return get_length


def _is_empty_imas_value(value: Any) -> bool:
    """Return True when *value* is unset/empty in an imas IDS object."""
    if value is None:
        return True
    # Zero-size arrays (unset array fields) — covers numpy arrays and imas
    # IDSStructArray objects.
    if hasattr(value, "__len__"):
        return len(value) == 0
    if hasattr(value, "size"):
        return value.size == 0
    return False


def _get_ids_leaf_value(ids_obj: Any, concrete_path: str) -> Any:
    """Traverse *ids_obj* along *concrete_path* and return the leaf value."""
    segs = list(parse_concrete_path(concrete_path))
    node = ids_obj
    for seg in segs[1:]:  # skip IDS name
        try:
            child = getattr(node, seg.name)
        except AttributeError:
            return None
        if seg.node_type is NodeType.ARRAY_STRUCT:
            try:
                node = child[seg.index]
            except (IndexError, TypeError):
                return None
        else:
            node = child
    return node


def read_ids_records(ids_obj: Any, ids_name: str) -> list[MappingRecord]:
    """Extract all non-empty leaf values from a loaded imas IDS object.

    Uses the IMAS data-dictionary schema to enumerate candidate paths and
    reads each field value directly from *ids_obj* — no mapper required.
    Empty/unset fields (zero-length arrays, ``None``) are silently skipped.

    Parameters
    ----------
    ids_obj:
        An imas IDS object as returned by ``imas.IDSFactory().<ids_name>()``
        or ``imas.DBEntry.get(ids_name)``.
    ids_name:
        The IDS name (e.g. ``"magnetics"``), used to look up the schema.
    """
    helper = IDSHelper.from_ids_name(ids_name)
    callback = _ids_length_callback(ids_obj)
    records: list[MappingRecord] = []

    for concrete_path in helper.generate_concrete_paths(callback, leaves_only=True):
        value = _get_ids_leaf_value(ids_obj, concrete_path)
        if not _is_empty_imas_value(value):
            records.append(MappingRecord(ids_path=concrete_path, value=value))

    logger.info("Read %d records from IDS '%s'", len(records), ids_name)
    return records


def read_imas_records(path: Path, ids_names: list[str]) -> list[MappingRecord]:
    """Read IDS records from an imas HDF5 or NetCDF file.

    Parameters
    ----------
    path:
        Path to an ``.h5`` or ``.nc`` file.
    ids_names:
        Names of the IDS objects to read (e.g. ``["magnetics", "equilibrium"]``).
        The file format does not expose its contents without reading each IDS
        explicitly, so the names must be supplied by the caller.
    """
    import imas

    uri = _imas_uri(path)
    records: list[MappingRecord] = []

    with imas.DBEntry(uri, "r") as dbentry:
        for ids_name in ids_names:
            logger.debug("Reading IDS '%s' from %s", ids_name, path)
            ids_obj = dbentry.get(ids_name)
            records.extend(read_ids_records(ids_obj, ids_name))

    logger.info("Read %d total records from %s", len(records), path)
    return records


# ── reading from JSON ─────────────────────────────────────────────────────────


def read_json_records(path: Path) -> list[MappingRecord]:
    """Read a munchi JSON output file and return the entries as MappingRecord list.

    The JSON must be a flat ``{concrete_path: value}`` object as produced by
    ``munchi map --output results.json``.  Binary-encoded ndarrays
    (``{"__ndarray__": ..., "dtype": ..., "shape": ...}``) are decoded back
    to numpy arrays automatically.
    """
    import base64

    import numpy as np

    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    records: list[MappingRecord] = []

    for ids_path, value in data.items():
        if (
            isinstance(value, dict)
            and "__ndarray__" in value
            and "dtype" in value
            and "shape" in value
        ):
            raw = base64.b64decode(value["__ndarray__"])
            value = np.frombuffer(raw, dtype=value["dtype"]).reshape(value["shape"])
        records.append(MappingRecord(ids_path=ids_path, value=value))

    logger.info("Read %d records from %s", len(records), path)
    return records


# ── converting records → IDS objects ─────────────────────────────────────────


def records_to_ids_objects(records: list[MappingRecord]) -> dict[str, Any]:
    """Convert a list of MappingRecords into a dict of imas IDS objects.

    Returns a ``{ids_name: ids_obj}`` mapping.  Each IDS object is populated
    with the supplied records via ``setattr`` traversal, with array-struct
    nodes resized as needed.

    This is the primary building block for the JSON → IMAS workflow::

        records = read_json_records(Path("results.json"))
        ids_objects = records_to_ids_objects(records)

        # Augment the IDS with any missing required fields, then write:
        ids_objects["equilibrium"].time_slice[0].time = 0.5
        with imas.DBEntry("imas:hdf5?path=output", "w") as db:
            for ids_obj in ids_objects.values():
                db.put(ids_obj)
    """
    import imas

    factory = imas.IDSFactory()
    groups = _group_records_by_ids(records)
    result: dict[str, Any] = {}

    for ids_name, ids_records in groups.items():
        ids_obj = getattr(factory, ids_name)()
        _populate_ids(ids_obj, ids_records)
        result[ids_name] = ids_obj
        logger.info("Built IDS object '%s' from %d records", ids_name, len(ids_records))

    return result


# ── high-level file converter ─────────────────────────────────────────────────


def convert_file(
    input_path: Path,
    output_path: Path,
    *,
    ids_names: list[str] | None = None,
    force: bool = False,
    binary_arrays: bool = False,
    on_imas_error: str = "fallback-json",
) -> list[IdsWriteError]:
    """Convert data between supported file formats.

    Supported input formats:
        - ``.json`` — munchi JSON output
        - ``.h5`` / ``.nc`` — imas-python IMAS files (requires *ids_names*)

    Supported output formats:
        - ``.json`` — munchi JSON output
        - ``.h5`` / ``.nc`` — imas-python IMAS files

    Parameters
    ----------
    input_path:
        Source file.
    output_path:
        Destination file.  If ``None`` the records are returned but not written.
    ids_names:
        IDS names to read when the input is an IMAS file.  Ignored for JSON.
    force:
        Overwrite *output_path* if it already exists.
    binary_arrays:
        Encode numpy arrays as base64 binary objects in JSON output.
    on_imas_error:
        ``"fallback-json"`` or ``"raise"``.  Controls what happens when an
        individual IDS fails to write.  See :func:`write_imas_output`.

    Returns
    -------
    list[IdsWriteError]
        Per-IDS write errors (empty on full success).  Only relevant when the
        output format is IMAS.
    """
    from .outputs import build_json_results, make_json_safe
    from .write_ids import write_imas_output

    in_suffix = input_path.suffix.lower()
    out_suffix = output_path.suffix.lower()

    _valid_in = {".json"} | SUPPORTED_SUFFIXES
    _valid_out = {".json"} | SUPPORTED_SUFFIXES

    if in_suffix not in _valid_in:
        raise ValueError(
            f"Unsupported input format {in_suffix!r}. Must be one of: "
            + ", ".join(sorted(_valid_in))
        )
    if out_suffix not in _valid_out:
        raise ValueError(
            f"Unsupported output format {out_suffix!r}. Must be one of: "
            + ", ".join(sorted(_valid_out))
        )

    # ── read ──
    if in_suffix == ".json":
        records = read_json_records(input_path)
    else:
        if not ids_names:
            raise ValueError(
                "Reading from an IMAS file requires --ids (one or more IDS names)."
            )
        records = read_imas_records(input_path, ids_names)

    logger.info("Loaded %d records from %s", len(records), input_path)

    # ── write ──
    if out_suffix == ".json":
        if output_path.exists() and not force:
            raise FileExistsError(f"Refusing to overwrite existing file: {output_path}")
        data = build_json_results(records, binary_arrays=binary_arrays)
        output_path.write_text(
            __import__("json").dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Wrote %d records to %s", len(data), output_path)
        return []

    return write_imas_output(output_path, records=records, force=force)
