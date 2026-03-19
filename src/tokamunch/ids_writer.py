from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .types import IDSNode, NodeType, WriteContext
from .parsing import render_array_length_query_path


def _ensure_array_size_exact(array_obj: Any, size: int) -> None:
    current_size = len(array_obj)
    if current_size != size:
        array_obj.resize(size)


def ensure_ids_arrays_resized(
    ids_obj: Any,
    segments: Iterable[IDSNode],
    array_sizes: dict[str, int],
    *,
    write_context: WriteContext | None = None,
    skip_root_segment: bool = True,
) -> None:
    full_seg_list = list(segments)
    walk_seg_list = full_seg_list[1:] if skip_root_segment and full_seg_list else full_seg_list

    ctx = write_context or WriteContext()
    current = ids_obj

    built_full: list[IDSNode] = []
    if skip_root_segment and full_seg_list:
        built_full.append(full_seg_list[0])

    for seg in walk_seg_list:
        child = getattr(current, seg.name)

        if seg.node_type is NodeType.SIMPLE_NODE:
            current = child
            built_full.append(seg)
            continue

        if seg.index is None:
            raise ValueError(f"Concrete IDS access requires an index for ARRAY_STRUCT segment {seg.name!r}")

        query_nodes = [*built_full, IDSNode(seg.name, NodeType.ARRAY_STRUCT, None)]
        query_path = render_array_length_query_path(query_nodes)

        if query_path not in ctx.resized_arrays:
            try:
                required_size = array_sizes[query_path]
            except KeyError as exc:
                raise KeyError(f"Missing cached array size for {query_path!r}") from exc

            _ensure_array_size_exact(child, required_size)
            ctx.resized_arrays.add(query_path)

        current = child[seg.index]
        built_full.append(seg)


def resolve_ids_segments(
    ids_obj: Any,
    segments: Iterable[IDSNode],
    *,
    skip_root_segment: bool = True,
) -> Any:
    seg_list = list(segments)

    if skip_root_segment and seg_list:
        seg_list = seg_list[1:]

    current = ids_obj

    for seg in seg_list:
        child = getattr(current, seg.name)

        if seg.node_type is NodeType.SIMPLE_NODE:
            current = child
            continue

        if seg.index is None:
            raise ValueError(f"Concrete IDS access requires an index for ARRAY_STRUCT segment {seg.name!r}")

        current = child[seg.index]

    return current


def resolve_ids_parent(
    ids_obj: Any,
    segments: Iterable[IDSNode],
    *,
    skip_root_segment: bool = True,
) -> tuple[Any, IDSNode]:
    seg_list = list(segments)

    if skip_root_segment and seg_list:
        seg_list = seg_list[1:]

    if not seg_list:
        raise ValueError("Path does not contain any usable segments")

    current = ids_obj

    for seg in seg_list[:-1]:
        child = getattr(current, seg.name)

        if seg.node_type is NodeType.SIMPLE_NODE:
            current = child
            continue

        if seg.index is None:
            raise ValueError(f"Concrete IDS access requires an index for ARRAY_STRUCT segment {seg.name!r}")

        current = child[seg.index]

    return current, seg_list[-1]


def set_ids_value(
    ids_obj: Any,
    segments: Iterable[IDSNode],
    value: Any,
    *,
    skip_root_segment: bool = True,
) -> None:
    parent, final_seg = resolve_ids_parent(ids_obj, segments, skip_root_segment=skip_root_segment)

    if final_seg.node_type is NodeType.ARRAY_STRUCT:
        raise ValueError(
            f"Cannot assign data directly to ARRAY_STRUCT node {final_seg.name!r}; "
            "array-structure nodes are resized only"
        )

    setattr(parent, final_seg.name, value)


def resize_and_set_ids_value(
    ids_obj: Any,
    segments: Iterable[IDSNode],
    value: Any,
    array_sizes: dict[str, int],
    *,
    write_context: WriteContext | None = None,
    skip_root_segment: bool = True,
) -> None:
    ensure_ids_arrays_resized(
        ids_obj,
        segments,
        array_sizes,
        write_context=write_context,
        skip_root_segment=skip_root_segment,
    )
    set_ids_value(ids_obj, segments, value, skip_root_segment=skip_root_segment)
