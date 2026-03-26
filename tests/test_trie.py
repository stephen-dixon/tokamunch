from tokamunch import build_ids_path_trie, generate_schema_paths_from_trie


def test_build_ids_path_trie_roundtrip_schema_paths() -> None:
    raw_paths = [
        "core_profiles/time",
        "core_profiles/profiles_1d(:)",
        "core_profiles/profiles_1d(:)/time",
        "core_profiles/profiles_1d(:)/electrons",
        "core_profiles/profiles_1d(:)/electrons/temperature",
        "core_profiles/profiles_1d(:)/ion(:)",
        "core_profiles/profiles_1d(:)/ion(:)/density",
    ]

    trie = build_ids_path_trie(raw_paths)
    regenerated = list(generate_schema_paths_from_trie(trie))[1:]

    assert set(regenerated) == set(raw_paths)
    assert len(regenerated) == len(raw_paths)
