from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Iterable

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


def generate_selected_paths(selection: PathSelection, ctx: CLIContext) -> Iterable[str]:
    if selection.path is not None:
        yield selection.path
        return

    assert selection.ids is not None
    helper = ctx.ids_helper(selection.ids)
    for ids_path in helper.generate_concrete_paths(
        ctx.tokamap.get_array_length,
        leaves_only=selection.leaves_only,
    ):
        if path_matches(ids_path, selection.match):
            yield ids_path
