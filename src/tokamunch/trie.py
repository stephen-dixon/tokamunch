from __future__ import annotations

from collections.abc import Iterable, Iterator

from .types import IDSNode, SegmentInterner, TrieNode
from .parsing import parse_schema_path, render_schema_path


def insert_path(root: TrieNode, ids_segments: Iterable[IDSNode]) -> None:
    node = root
    for ids_segment in ids_segments:
        child = node.children.get(ids_segment)
        if child is None:
            child = TrieNode(ids_node=ids_segment, parent=node, depth=node.depth + 1)
            node.children[ids_segment] = child
        node = child


def build_ids_path_trie(ids_paths: Iterable[str]) -> TrieNode:
    root = TrieNode()
    interner = SegmentInterner()

    for ids_path in ids_paths:
        insert_path(root, parse_schema_path(ids_path, interner))

    return root


def iter_schema_paths_from_trie(root: TrieNode) -> Iterator[str]:
    def recurse(node: TrieNode, built: list[IDSNode]) -> Iterator[str]:
        for ids_node, child in node.children.items():
            built.append(ids_node)
            yield render_schema_path(built)
            yield from recurse(child, built)
            built.pop()

    yield from recurse(root, [])


def is_leaf_node(node: TrieNode) -> bool:
    return not node.children
