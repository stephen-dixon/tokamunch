from __future__ import annotations

from typing import Any

import tokamunch as tm


def non_concrete_to_mapping_template_path(path: str) -> str:
    path = path.replace("(:)", "[#]")
    if path.endswith("[#]"):
        path = path[:-3]
    return path


def build_blank_mapping_template(ids_name: str, *, leaves_only: bool) -> dict[str, dict[str, Any]]:
    helper = tm.IDSHelper.from_ids_name(ids_name)
    converted = sorted(
        non_concrete_to_mapping_template_path(path)
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
