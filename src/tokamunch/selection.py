from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Iterable

import tokamunch as tm

from .context import MappingContext
from .parsing import concrete_path_to_template


@dataclass
class IdsSelection:
    """Expand all concrete paths for an IDS, with optional filtering."""

    ids: str
    match: str | None = None
    leaves_only: bool = False
    mapping_keys: frozenset[str] | None = field(default=None)


@dataclass
class SinglePathSelection:
    """Map a single known concrete path."""

    path: str
    mapping_keys: frozenset[str] | None = field(default=None)


# Public type alias — callers use this for annotations.
Selection = IdsSelection | SinglePathSelection


def path_matches(ids_path: str, pattern: str | None) -> bool:
    return pattern is None or fnmatch.fnmatch(ids_path, pattern)


def _included(
    ids_path: str,
    *,
    match: str | None,
    mapping_keys: frozenset[str] | None,
) -> bool:
    if not path_matches(ids_path, match):
        return False
    if mapping_keys is not None:
        if concrete_path_to_template(ids_path) not in mapping_keys:
            return False
    return True


def generate_selected_paths(selection: Selection, ctx: MappingContext) -> Iterable[str]:
    if isinstance(selection, SinglePathSelection):
        if _included(selection.path, match=None, mapping_keys=selection.mapping_keys):
            yield selection.path
        return

    helper = ctx.ids_helper(selection.ids)
    for ids_path in helper.generate_concrete_paths(
        ctx.tokamap.get_array_length,
        leaves_only=selection.leaves_only,
    ):
        if _included(ids_path, match=selection.match, mapping_keys=selection.mapping_keys):
            yield ids_path
