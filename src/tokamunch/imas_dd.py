from __future__ import annotations

import re
from collections.abc import Iterator
from functools import cache

_ARRAY_MARKER_RE = re.compile(r"\([^)]+\)")


@cache
def _load_ids_fields(ids_name: str) -> tuple[str, ...]:
    from imas_data_dictionary import idsinfo as ids

    ids_info = ids.IDSInfo()
    return tuple(ids_info.list_ids_fields(ids_name)[ids_name])


@cache
def load_ids_field_metadata(ids_name: str) -> dict[str, dict[str, str]]:
    """Return ``{subpath: {"documentation": ..., "units": ...}}`` for *ids_name*.

    The subpath keys are relative to the IDS root and use ``(:)`` notation,
    matching the keys returned by ``imas_data_dictionary.idsinfo.IDSInfo.list_ids_fields``.
    Returns an empty dict if ``imas_data_dictionary`` is unavailable.
    """
    try:
        from imas_data_dictionary import idsinfo as ids

        ids_info = ids.IDSInfo()
        raw: dict[str, dict[str, str]] = ids_info.list_ids_fields(ids_name)[ids_name]
        # Normalise all array-dimension markers (e.g. ``(itime)``, ``(:,:)``) to
        # ``(:)`` so that keys match the ``(:)``-style paths used elsewhere.
        return {_ARRAY_MARKER_RE.sub("(:)", k): v for k, v in raw.items()}
    except Exception:
        return {}


def generate_ids_sub_paths(ids_name: str) -> Iterator[str]:
    yield from _load_ids_fields(ids_name)


def generate_ids_paths(ids_name: str) -> Iterator[str]:
    for path in _load_ids_fields(ids_name):
        yield f"{ids_name}/{path}"
