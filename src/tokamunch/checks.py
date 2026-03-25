from __future__ import annotations

import tokamunch as tm

from .context import CLIContext


def check_context(ctx: CLIContext) -> None:
    _ = ctx.cfg
    _ = ctx.mapper
    _ = ctx.tokamap


def check_ids(ids_name: str, *, leaves_only: bool) -> int:
    helper = tm.IDSHelper.from_ids_name(ids_name)
    return len(list(helper.iter_non_concrete_paths(leaves_only=leaves_only)))
