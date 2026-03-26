from __future__ import annotations

import tokamunch as tm


def check_ids(ids_name: str, *, leaves_only: bool) -> int:
    helper = tm.IDSHelper.from_ids_name(ids_name)
    return len(list(helper.generate_non_concrete_paths(leaves_only=leaves_only)))
