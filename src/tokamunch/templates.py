from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import tokamunch as tm


def _to_template_path(schema_path: str) -> str:
    """Convert a schema path to its mapping-template form.

    ``(:)`` array markers become ``[#]`` placeholders, matching the concrete
    path convention of ``[N]`` indices.
    """
    return schema_path.replace("(:)", "[#]")


def build_blank_mapping_template(
    ids_name: str, *, leaves_only: bool
) -> dict[str, dict[str, Any]]:
    helper = tm.IDSHelper.from_ids_name(ids_name)
    converted = sorted(
        _to_template_path(path)
        for path in helper.generate_non_concrete_paths(leaves_only=leaves_only)
    )

    mapping: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []

    for path in converted:
        if path in mapping:
            duplicates.append(path)
            continue
        mapping[path] = {}

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
