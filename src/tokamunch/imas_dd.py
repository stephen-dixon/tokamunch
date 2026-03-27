from __future__ import annotations

from collections.abc import Iterator
from functools import cache


@cache
def _load_ids_fields(ids_name: str) -> tuple[str, ...]:
    from imas_data_dictionary import idsinfo as ids

    ids_info = ids.IDSInfo()
    return tuple(ids_info.list_ids_fields(ids_name)[ids_name])


def generate_ids_sub_paths(ids_name: str) -> Iterator[str]:
    yield from _load_ids_fields(ids_name)


def generate_ids_paths(ids_name: str) -> Iterator[str]:
    for path in _load_ids_fields(ids_name):
        yield f"{ids_name}/{path}"
