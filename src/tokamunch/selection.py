from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any, Iterable

import tokamunch as tm

from .context import CLIContext


@dataclass
class PathSelection:
    ids: str | None
    path: str | None
    match: str | None
    leaves_only: bool


def path_matches(ids_path: str, pattern: str | None) -> bool:
    return pattern is None or fnmatch.fnmatch(ids_path, pattern)


def iter_concrete_ids_paths(
    helper: tm.IDSHelper,
    array_length_callback: Any,
    *,
    leaves_only: bool,
) -> Iterable[str]:
    yield from helper.iter_concrete_paths(
        array_length_callback,
        leaves_only=leaves_only,
    )


def iter_selected_paths(selection: PathSelection, ctx: CLIContext) -> Iterable[str]:
    if selection.path is not None:
        yield selection.path
        return

    assert selection.ids is not None
    helper = ctx.ids_helper(selection.ids)
    for ids_path in iter_concrete_ids_paths(
        helper,
        ctx.tokamap.get_array_length,
        leaves_only=selection.leaves_only,
    ):
        if path_matches(ids_path, selection.match):
            yield ids_path
