from __future__ import annotations

from collections.abc import Iterator


def generate_ids_sub_paths(ids_name: str) -> Iterator[str]:
    from imas_data_dictionary import idsinfo as ids

    ids_info = ids.IDSInfo()
    info = ids_info.list_ids_fields(ids_name)
    yield from info[ids_name]


def generate_ids_paths(ids_name: str) -> Iterator[str]:
    for path in generate_ids_sub_paths(ids_name):
        yield f"{ids_name}/{path}"
