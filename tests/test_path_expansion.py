from tokamunch import (
    IDSNode,
    NodeType,
    ExpansionContext,
    build_ids_path_trie,
    expand_ids_path_trie,
    expand_ids_path_trie_segments,
)


def test_expand_ids_path_trie_nested_arrays_to_strings() -> None:
    raw_paths = [
        "core_profiles",
        "core_profiles/profiles_1d(:)",
        "core_profiles/profiles_1d(:)/ion(:)",
        "core_profiles/profiles_1d(:)/ion(:)/density",
    ]
    trie = build_ids_path_trie(raw_paths)

    lengths = {
        "core_profiles/profiles_1d": 2,
        "core_profiles/profiles_1d[0]/ion": 2,
        "core_profiles/profiles_1d[1]/ion": 1,
    }

    def get_length(path: str) -> int:
        return lengths[path]

    got = list(expand_ids_path_trie(trie, get_length))

    assert got == [
        "core_profiles",
        "core_profiles/profiles_1d[0]",
        "core_profiles/profiles_1d[0]/ion[0]",
        "core_profiles/profiles_1d[0]/ion[0]/density",
        "core_profiles/profiles_1d[0]/ion[1]",
        "core_profiles/profiles_1d[0]/ion[1]/density",
        "core_profiles/profiles_1d[1]",
        "core_profiles/profiles_1d[1]/ion[0]",
        "core_profiles/profiles_1d[1]/ion[0]/density",
    ]


def test_expand_ids_path_trie_nested_arrays_to_segments() -> None:
    raw_paths = [
        "core_profiles",
        "core_profiles/profiles_1d(:)",
        "core_profiles/profiles_1d(:)/time",
    ]
    trie = build_ids_path_trie(raw_paths)

    def get_length(path: str) -> int:
        if path == "core_profiles/profiles_1d":
            return 2
        raise AssertionError(f"Unexpected length query: {path}")

    got = list(expand_ids_path_trie_segments(trie, get_length))

    assert got == [
        (IDSNode("core_profiles", NodeType.SIMPLE_NODE, None),),
        (
            IDSNode("core_profiles", NodeType.SIMPLE_NODE, None),
            IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 0),
        ),
        (
            IDSNode("core_profiles", NodeType.SIMPLE_NODE, None),
            IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 0),
            IDSNode("time", NodeType.SIMPLE_NODE, None),
        ),
        (
            IDSNode("core_profiles", NodeType.SIMPLE_NODE, None),
            IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 1),
        ),
        (
            IDSNode("core_profiles", NodeType.SIMPLE_NODE, None),
            IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 1),
            IDSNode("time", NodeType.SIMPLE_NODE, None),
        ),
    ]


def test_expand_ids_path_trie_leaves_only() -> None:
    raw_paths = [
        "core_profiles",
        "core_profiles/profiles_1d(:)",
        "core_profiles/profiles_1d(:)/time",
    ]
    trie = build_ids_path_trie(raw_paths)

    def get_length(path: str) -> int:
        return 2

    got = list(expand_ids_path_trie(trie, get_length, leaves_only=True))

    assert got == [
        "core_profiles/profiles_1d[0]/time",
        "core_profiles/profiles_1d[1]/time",
    ]


def test_expand_ids_path_trie_caches_length_queries_in_context() -> None:
    raw_paths = [
        "core_profiles",
        "core_profiles/profiles_1d(:)",
        "core_profiles/profiles_1d(:)/time",
        "core_profiles/profiles_1d(:)/electrons",
    ]
    trie = build_ids_path_trie(raw_paths)
    ctx = ExpansionContext()

    calls: list[str] = []

    def get_length(path: str) -> int:
        calls.append(path)
        return 2

    list(expand_ids_path_trie(trie, get_length, context=ctx))

    assert calls == ["core_profiles/profiles_1d"]
    assert ctx.array_sizes == {"core_profiles/profiles_1d": 2}
