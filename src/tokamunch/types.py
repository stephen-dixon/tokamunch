from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class NodeType(Enum):
    STRUCT = auto()
    ARRAY_STRUCT = auto()


@dataclass(frozen=True, slots=True)
class IDSNode:
    name: str
    node_type: NodeType
    index: int | None = None


@dataclass(slots=True)
class TrieNode:
    ids_node: IDSNode | None = None
    children: dict[IDSNode, "TrieNode"] = field(default_factory=dict)
    parent: TrieNode | None = None
    depth: int = 0


class SegmentInterner:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, NodeType], IDSNode] = {}

    def intern(self, name: str, node_type: NodeType) -> IDSNode:
        key = (name, node_type)
        node = self._cache.get(key)
        if node is None:
            node = IDSNode(name=name, node_type=node_type, index=None)
            self._cache[key] = node
        return node


@dataclass(slots=True)
class ExpansionContext:
    array_sizes: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class WriteContext:
    resized_arrays: set[str] = field(default_factory=set)
