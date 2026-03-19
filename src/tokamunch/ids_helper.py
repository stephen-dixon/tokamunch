from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

from .path_expansion import expand_ids_path_trie, expand_ids_path_trie_segments
from .imas_dd import generate_ids_paths
from .types import ExpansionContext, IDSNode, TrieNode
from .trie import build_ids_path_trie, iter_schema_paths_from_trie


class IDSHelper:
    def __init__(self, ids_paths: Iterable[str]):
        self._trie = build_ids_path_trie(ids_paths)
        self.expansion_context = ExpansionContext()

    @classmethod
    def from_ids_name(cls, ids_name: str) -> "IDSHelper":
        return cls(generate_ids_paths(ids_name))

    @property
    def trie(self) -> TrieNode:
        return self._trie

    @property
    def array_sizes(self) -> dict[str, int]:
        return self.expansion_context.array_sizes

    def iter_schema_paths(self) -> Iterator[str]:
        yield from iter_schema_paths_from_trie(self._trie)

    def iter_concrete_segments(
        self,
        arraystruct_length_callback: Callable[[str], int],
        *,
        leaves_only: bool = False,
    ) -> Iterator[tuple[IDSNode, ...]]:
        yield from expand_ids_path_trie_segments(
            self._trie,
            arraystruct_length_callback,
            context=self.expansion_context,
            leaves_only=leaves_only,
        )

    def iter_concrete_paths(
        self,
        arraystruct_length_callback: Callable[[str], int],
        *,
        leaves_only: bool = False,
    ) -> Iterator[str]:
        yield from expand_ids_path_trie(
            self._trie,
            arraystruct_length_callback,
            context=self.expansion_context,
            leaves_only=leaves_only,
        )
