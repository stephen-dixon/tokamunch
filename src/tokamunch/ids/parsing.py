from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from ..types import IDSNode, NodeType, SegmentInterner

_SCHEMA_ARRAY_SUFFIX = "(:)"
_ITIME_ANNOTATION = "(itime)"
_CONCRETE_SEGMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\[(?P<index>\d+)\])?$"
)
_CONCRETE_INDEX_RE = re.compile(r"\[\d+\]")
# Matches multi-dimensional data annotations on leaf fields, e.g. (:,:), (:,:,:,:).
# One or more ':,' groups followed by a final ':' — requires at least two dimensions,
# so single-dimension (:) is deliberately excluded (that is the array-struct marker).
_MULTI_DIM_SUFFIX_RE = re.compile(r"\((?::\s*,\s*)+:\s*\)$")


def normalise_schema_segment(raw: str) -> str:
    return raw.replace(_ITIME_ANNOTATION, "")


def parse_schema_path(
    path: str, interner: SegmentInterner | None = None
) -> Iterator[IDSNode]:
    segment_factory = (
        interner.intern
        if interner is not None
        else lambda name, node_type: IDSNode(name, node_type)
    )

    for raw in path.split("/"):
        if not raw:
            raise ValueError(f"Invalid empty path segment in {path!r}")

        # Check for (itime) BEFORE stripping it: its presence marks an array-struct
        # dimension (time-indexed arrays in the IMAS data dictionary).
        is_itime = _ITIME_ANNOTATION in raw
        sanitised = normalise_schema_segment(raw)

        if is_itime or sanitised.endswith(_SCHEMA_ARRAY_SUFFIX):
            # Array-struct node — strip the (:) suffix if present to get the name.
            if sanitised.endswith(_SCHEMA_ARRAY_SUFFIX):
                name = sanitised[: -len(_SCHEMA_ARRAY_SUFFIX)]
            else:
                name = sanitised  # (itime) already stripped by normalise_schema_segment
            if not name:
                raise ValueError(f"Invalid array segment in {path!r}")
            yield segment_factory(name, NodeType.ARRAY_STRUCT)
        else:
            # Simple (leaf) node — strip multi-dimensional data annotations such as
            # (:,:) or (:,:,:,:).  These indicate the shape of the stored array but
            # are not array-struct dimensions and must not appear in rendered paths.
            name = _MULTI_DIM_SUFFIX_RE.sub("", sanitised)
            yield segment_factory(name, NodeType.SIMPLE_NODE)


def parse_concrete_path(path: str) -> Iterator[IDSNode]:
    for raw in path.split("/"):
        if not raw:
            raise ValueError(f"Invalid empty path segment in {path!r}")

        match = _CONCRETE_SEGMENT_RE.fullmatch(raw)
        if match is None:
            raise ValueError(f"Invalid concrete path segment {raw!r} in {path!r}")

        name = match.group("name")
        index_str = match.group("index")

        if index_str is None:
            yield IDSNode(name=name, node_type=NodeType.SIMPLE_NODE, index=None)
        else:
            yield IDSNode(
                name=name, node_type=NodeType.ARRAY_STRUCT, index=int(index_str)
            )


def render_schema_segment(node: IDSNode) -> str:
    if node.node_type is NodeType.ARRAY_STRUCT:
        return f"{node.name}{_SCHEMA_ARRAY_SUFFIX}"
    return node.name


def render_concrete_segment(node: IDSNode) -> str:
    if node.node_type is NodeType.ARRAY_STRUCT:
        if node.index is None:
            raise ValueError(
                f"Concrete rendering requires an index for ARRAY_STRUCT node {node.name!r}"
            )
        return f"{node.name}[{node.index}]"
    return node.name


def render_schema_path(nodes: Iterable[IDSNode]) -> str:
    return "/".join(render_schema_segment(node) for node in nodes)


def render_concrete_path(nodes: Iterable[IDSNode]) -> str:
    return "/".join(render_concrete_segment(node) for node in nodes)


def concrete_path_to_schema_path(path: str) -> str:
    """Convert a concrete runtime path to its schema form.

    Replaces every concrete array index ``[N]`` with the schema
    array-struct marker ``(:)``.

    Example::

        "magnetics/flux_loop[0]/position[2]/r"
        -> "magnetics/flux_loop(:)/position(:)/r"
    """
    return render_schema_path(parse_concrete_path(path))


def concrete_path_to_template(path: str) -> str:
    """Convert a concrete runtime path to its mapping-template form.

    Replaces every concrete array index ``[N]`` with the template
    placeholder ``[#]``, enabling lookup against mapping-file keys.

    Example::

        "magnetics/flux_loop[0]/position[2]/r"
        -> "magnetics/flux_loop[#]/position[#]/r"
    """
    return _CONCRETE_INDEX_RE.sub("[#]", path)


def render_array_length_query_path(nodes: Iterable[IDSNode]) -> str:
    parts: list[str] = []
    for node in nodes:
        if node.node_type is NodeType.ARRAY_STRUCT and node.index is None:
            parts.append(node.name)
        else:
            parts.append(render_concrete_segment(node))
    return "/".join(parts)
