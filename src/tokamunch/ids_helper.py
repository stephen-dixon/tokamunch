from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from functools import cache

from .imas_dd import generate_ids_paths
from .path_expansion import expand_ids_path_trie, expand_ids_path_trie_segments
from .trie import build_ids_path_trie, generate_schema_paths_from_trie
from .types import ExpansionContext, IDSNode, TrieNode


@cache
def _build_cached_trie(ids_name: str) -> TrieNode:
    """Build and cache the schema trie for an IDS name.

    Cached alongside ``_load_ids_fields`` so repeated ``IDSHelper.from_ids_name``
    calls for the same IDS name skip both the IDS field fetch and the trie build.
    """
    return build_ids_path_trie(generate_ids_paths(ids_name))


class IDSHelper:
    def __init__(self, ids_paths: Iterable[str]):
        self._trie = build_ids_path_trie(ids_paths)
        self._expansion_context = ExpansionContext()

    @classmethod
    def from_ids_name(cls, ids_name: str) -> IDSHelper:
        inst = cls.__new__(cls)
        inst._trie = _build_cached_trie(ids_name)
        inst._expansion_context = ExpansionContext()
        return inst

    @property
    def trie(self) -> TrieNode:
        return self._trie

    @property
    def array_sizes(self) -> dict[str, int]:
        return self._expansion_context.array_sizes

    def reset_expansion_cache(self) -> None:
        """Discard all cached array-length results so the next expansion re-queries."""
        self._expansion_context = ExpansionContext()

    def generate_non_concrete_paths(
        self, *, leaves_only: bool = False
    ) -> Iterator[str]:
        yield from generate_schema_paths_from_trie(self._trie, leaves_only=leaves_only)

    def generate_concrete_segments(
        self,
        arraystruct_length_callback: Callable[[str], int],
        *,
        leaves_only: bool = False,
    ) -> Iterator[tuple[IDSNode, ...]]:
        yield from expand_ids_path_trie_segments(
            self._trie,
            arraystruct_length_callback,
            context=self._expansion_context,
            leaves_only=leaves_only,
        )

    def generate_concrete_paths(
        self,
        arraystruct_length_callback: Callable[[str], int],
        *,
        leaves_only: bool = False,
    ) -> Iterator[str]:
        yield from expand_ids_path_trie(
            self._trie,
            arraystruct_length_callback,
            context=self._expansion_context,
            leaves_only=leaves_only,
        )
