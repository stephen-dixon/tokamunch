from __future__ import annotations

from collections.abc import Callable, Iterator

from .types import ExpansionContext, IDSNode, NodeType, TrieNode
from .parsing import render_array_length_query_path, render_concrete_path
from .trie import is_leaf_node


def expand_ids_path_trie_segments(
    root: TrieNode,
    get_length_callback: Callable[[str], int],
    *,
    context: ExpansionContext | None = None,
    leaves_only: bool = False,
) -> Iterator[tuple[IDSNode, ...]]:
    ctx = context or ExpansionContext()

    def recurse(node: TrieNode, built: list[IDSNode]) -> Iterator[tuple[IDSNode, ...]]:
        for ids_node, child in node.children.items():
            if ids_node.node_type is NodeType.SIMPLE_NODE:
                built.append(ids_node)
                if not leaves_only or is_leaf_node(child):
                    yield tuple(built)
                yield from recurse(child, built)
                built.pop()
                continue

            query_node = IDSNode(name=ids_node.name, node_type=NodeType.ARRAY_STRUCT, index=None)
            query_path = render_array_length_query_path([*built, query_node])

            if query_path not in ctx.array_sizes:
                ctx.array_sizes[query_path] = get_length_callback(query_path)

            n = ctx.array_sizes[query_path]

            for idx in range(n):
                concrete_node = IDSNode(name=ids_node.name, node_type=NodeType.ARRAY_STRUCT, index=idx)
                built.append(concrete_node)
                if not leaves_only or is_leaf_node(child):
                    yield tuple(built)
                yield from recurse(child, built)
                built.pop()

    yield from recurse(root, [])


def expand_ids_path_trie(
    root: TrieNode,
    get_length_callback: Callable[[str], int],
    *,
    context: ExpansionContext | None = None,
    leaves_only: bool = False,
) -> Iterator[str]:
    for concrete_nodes in expand_ids_path_trie_segments(
        root,
        get_length_callback,
        context=context,
        leaves_only=leaves_only,
    ):
        yield render_concrete_path(concrete_nodes)
