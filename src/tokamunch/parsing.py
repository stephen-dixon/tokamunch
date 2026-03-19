from __future__ import annotations

from collections.abc import Iterable, Iterator
import re

from .types import IDSNode, NodeType, SegmentInterner


_SCHEMA_ARRAY_SUFFIX = "(:)"
_CONCRETE_SEGMENT_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\[(?P<index>\d+)\])?$")


def normalise_schema_segment(raw: str) -> str:
    return raw.replace("(itime)", "")


def parse_schema_path(path: str, interner: SegmentInterner | None = None) -> Iterator[IDSNode]:
    segment_factory = interner.intern if interner is not None else lambda name, node_type: IDSNode(name, node_type)

    for raw in path.split("/"):
        if not raw:
            raise ValueError(f"Invalid empty path segment in {path!r}")

        sanitised = normalise_schema_segment(raw)

        if sanitised.endswith(_SCHEMA_ARRAY_SUFFIX):
            name = sanitised[: -len(_SCHEMA_ARRAY_SUFFIX)]
            if not name:
                raise ValueError(f"Invalid array segment in {path!r}")
            yield segment_factory(name, NodeType.ARRAY_STRUCT)
        else:
            yield segment_factory(sanitised, NodeType.SIMPLE_NODE)


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
            yield IDSNode(name=name, node_type=NodeType.ARRAY_STRUCT, index=int(index_str))


def render_schema_segment(node: IDSNode) -> str:
    if node.node_type is NodeType.ARRAY_STRUCT:
        return f"{node.name}{_SCHEMA_ARRAY_SUFFIX}"
    return node.name


def render_concrete_segment(node: IDSNode) -> str:
    if node.node_type is NodeType.ARRAY_STRUCT:
        if node.index is None:
            raise ValueError(f"Concrete rendering requires an index for ARRAY_STRUCT node {node.name!r}")
        return f"{node.name}[{node.index}]"
    return node.name


def render_schema_path(nodes: Iterable[IDSNode]) -> str:
    return "/".join(render_schema_segment(node) for node in nodes)


def render_concrete_path(nodes: Iterable[IDSNode]) -> str:
    return "/".join(render_concrete_segment(node) for node in nodes)


def render_array_length_query_path(nodes: Iterable[IDSNode]) -> str:
    parts: list[str] = []
    for node in nodes:
        if node.node_type is NodeType.ARRAY_STRUCT and node.index is None:
            parts.append(node.name)
        else:
            parts.append(render_concrete_segment(node))
    return "/".join(parts)
