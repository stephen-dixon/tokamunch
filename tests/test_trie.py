from tokamunch import build_ids_path_trie, generate_schema_paths_from_trie


_SCHEMA_PATHS = [
    "core_profiles/time",
    "core_profiles/profiles_1d(:)",
    "core_profiles/profiles_1d(:)/time",
    "core_profiles/profiles_1d(:)/electrons",
    "core_profiles/profiles_1d(:)/electrons/temperature",
    "core_profiles/profiles_1d(:)/ion(:)",
    "core_profiles/profiles_1d(:)/ion(:)/density",
]


def test_build_ids_path_trie_roundtrip_schema_paths() -> None:
    trie = build_ids_path_trie(_SCHEMA_PATHS)
    regenerated = list(generate_schema_paths_from_trie(trie))[1:]

    assert set(regenerated) == set(_SCHEMA_PATHS)
    assert len(regenerated) == len(_SCHEMA_PATHS)


def test_generate_schema_paths_leaves_only() -> None:
    trie = build_ids_path_trie(_SCHEMA_PATHS)
    leaves = set(generate_schema_paths_from_trie(trie, leaves_only=True))

    # Only true leaf nodes (no children) should appear.
    assert "core_profiles/time" in leaves
    assert "core_profiles/profiles_1d(:)/time" in leaves
    assert "core_profiles/profiles_1d(:)/electrons/temperature" in leaves
    assert "core_profiles/profiles_1d(:)/ion(:)/density" in leaves

    # Intermediate nodes must be excluded.
    assert "core_profiles/profiles_1d(:)" not in leaves
    assert "core_profiles/profiles_1d(:)/electrons" not in leaves
    assert "core_profiles/profiles_1d(:)/ion(:)" not in leaves
