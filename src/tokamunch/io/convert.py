"""Format conversion utilities for tokamunch IDS data.

Provides functions for moving data between the formats that tokamunch
understands: imas-python HDF5/NetCDF files, munchi JSON output, and
in-memory imas IDS objects.

Primary use case — load a non-compliant JSON into IDS objects so that
missing fields can be added before a validated IMAS write::

    from tokamunch.io.convert import read_json_records, records_to_ids_objects
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

from ..ids.helper import IDSHelper
from ..ids.output import (
    SUPPORTED_SUFFIXES,
    IdsWriteError,
    group_records_by_ids,
    imas_uri,
    populate_ids,
)
from ..ids.parsing import parse_concrete_path
from ..mapping.runner import MappingRecord
from ..types import NodeType

logger = logging.getLogger(__name__)


# ── reading from IDS objects ──────────────────────────────────────────────────


def _ids_length_callback(ids_obj: Any) -> Callable[[str], int]:
    """Return a get_array_length callback that reads sizes from an IDS object."""

    def get_length(query_path: str) -> int:
        node = ids_obj
        segs = list(parse_concrete_path(query_path))
        for seg in segs[1:]:  # skip IDS name (first segment)
            try:
                child = getattr(node, seg.name)
            except AttributeError:
                return 0
            if seg.node_type is NodeType.ARRAY_STRUCT:
                try:
                    node = child[seg.index]
                except (IndexError, TypeError):
                    return 0
            else:
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
    if hasattr(value, "__len__"):
        return len(value) == 0
    if hasattr(value, "size"):
        return bool(value.size == 0)
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
    """Read IDS records from an imas HDF5 or NetCDF file."""
    import imas

    uri = imas_uri(path)
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

    Binary-encoded ndarrays (``{"__ndarray__": ..., "dtype": ..., "shape": ...}``)
    are decoded back to numpy arrays automatically.
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
    """
    import imas

    factory = imas.IDSFactory()
    groups = group_records_by_ids(records)
    result: dict[str, Any] = {}

    for ids_name, ids_records in groups.items():
        ids_obj = getattr(factory, ids_name)()
        populate_ids(ids_obj, ids_records)
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
    """
    from ..ids.output import write_imas_output
    from .outputs import build_json_results

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
