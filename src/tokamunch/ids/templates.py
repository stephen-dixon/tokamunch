from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .helper import IDSHelper
from .imas_dd import load_ids_field_metadata

# Metadata-only keys that may appear alongside "comment" in a comment stub.
_COMMENT_STUB_ALLOWED_KEYS = frozenset({"comment", "units", "source"})


def _field_comment(ids_name: str, schema_path: str) -> str:
    """Return a comment string populated from IDS field metadata.

    *schema_path* is a full path including the IDS name prefix, e.g.
    ``magnetics/flux_loop(:)/position(:)/r``.  The ``documentation`` and
    ``units`` fields from ``imas_data_dictionary`` are combined into a single
    string: ``"Major radius [m]"`` when units are present, or just the
    documentation text otherwise.  Returns an empty string if metadata is
    unavailable.
    """
    field_meta = load_ids_field_metadata(ids_name)
    # list_ids_fields keys are relative to the IDS root (no IDS-name prefix).
    subpath = schema_path.split("/", 1)[1] if "/" in schema_path else schema_path
    # Some array fields are stored with a trailing (:) marker in the metadata
    # even when the schema path carries no array suffix (e.g. 2-D index arrays).
    meta = field_meta.get(subpath) or field_meta.get(subpath + "(:)") or {}
    doc = meta.get("documentation", "").strip()
    units = meta.get("units", "").strip()
    if doc and units:
        return f"{doc} [{units}]"
    return doc


def _to_template_path(schema_path: str) -> str:
    """Convert a schema path to its mapping-template form.

    ``(:)`` array markers become ``[#]`` placeholders, matching the concrete
    path convention of ``[N]`` indices.
    """
    return schema_path.replace("(:)", "[#]")


def is_comment_stub(value: Any) -> bool:
    """Return True if *value* is a documented stub with no mapping expression.

    A comment stub is a dict that has a ``"comment"`` key and whose remaining
    keys are limited to the allowed metadata set (``"units"``, ``"source"``).
    Any other key (e.g. an expression) means this entry carries real data and
    is therefore *not* a stub.
    """
    if not isinstance(value, dict):
        return False
    if "comment" not in value:
        return False
    return set(value.keys()) <= _COMMENT_STUB_ALLOWED_KEYS


def build_blank_mapping_template(
    ids_name: str, *, leaves_only: bool
) -> dict[str, dict[str, Any]]:
    helper = IDSHelper.from_ids_name(ids_name)
    pairs = sorted(
        (_to_template_path(p), p)
        for p in helper.generate_non_concrete_paths(leaves_only=leaves_only)
    )

    mapping: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []

    for template_path, schema_path in pairs:
        if template_path in mapping:
            duplicates.append(template_path)
            continue
        mapping[template_path] = {"comment": _field_comment(ids_name, schema_path)}

    if duplicates:
        examples = ", ".join(repr(path) for path in duplicates[:10])
        raise ValueError(
            "Duplicate mapping keys were produced after path normalisation. "
            f"Examples: {examples}"
        )

    return mapping


def load_mapping_keys(path: Path) -> frozenset[str]:
    """Load a mapping JSON file and return its top-level keys as a frozenset.

    The keys are expected to be mapping-template paths (``[#]`` notation).
    Used with ``--mapping`` to restrict a run to the intersection of
    the mapping file and the expanded IDS paths.
    """
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"Mapping file {path} must contain a JSON object at the top level"
        )
    return frozenset(data.keys())


def merge_mapping_stubs(
    ids_name: str,
    existing_path: Path,
    *,
    leaves_only: bool = False,
) -> dict[str, Any]:
    """Merge an existing mapping file with blank stubs for any missing IDS paths.

    All existing entries are preserved with their original values.  Any
    template path present in the IDS schema but absent from the file is added
    as ``{"comment": ""}``.

    Existing entries appear first (in their original file order), followed by
    new stubs sorted alphabetically.
    """
    with existing_path.open(encoding="utf-8") as f:
        existing: dict[str, Any] = json.load(f)
    if not isinstance(existing, dict):
        raise ValueError(
            f"Mapping file {existing_path} must contain a JSON object at the top level"
        )

    helper = IDSHelper.from_ids_name(ids_name)
    all_pairs = sorted(
        (_to_template_path(p), p)
        for p in helper.generate_non_concrete_paths(leaves_only=leaves_only)
    )

    existing_keys = set(existing.keys())
    merged: dict[str, Any] = dict(existing)
    for template_path, schema_path in all_pairs:
        if template_path not in existing_keys:
            merged[template_path] = {"comment": _field_comment(ids_name, schema_path)}

    return merged
