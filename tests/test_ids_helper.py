from tokamunch import IDSHelper, build_ids_path_trie


def _make_helper(*schema_paths: str) -> IDSHelper:
    return IDSHelper(list(schema_paths))


def _constant_length(n: int):
    def callback(path: str) -> int:
        return n
    return callback


class TestGenerateNonConcretePaths:
    def test_returns_all_schema_paths(self) -> None:
        helper = _make_helper(
            "magnetics/time",
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
        )
        paths = set(helper.generate_non_concrete_paths())
        # The trie also yields the root IDS segment ("magnetics") as an intermediate node.
        assert paths == {
            "magnetics",
            "magnetics/time",
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
        }

    def test_leaves_only_excludes_intermediates(self) -> None:
        helper = _make_helper(
            "magnetics/time",
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
        )
        leaves = set(helper.generate_non_concrete_paths(leaves_only=True))

        assert "magnetics/time" in leaves
        assert "magnetics/flux_loop(:)/field" in leaves
        # Array-struct intermediate node must not appear.
        assert "magnetics/flux_loop(:)" not in leaves

    def test_leaves_only_was_previously_broken(self) -> None:
        # Regression: the old check was `path.endswith("/#")` which never
        # matched schema paths (they use `(:)` notation), so leaves_only had
        # no effect. Verify the fix: the full set must differ from leaves-only.
        helper = _make_helper(
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
        )
        all_paths = set(helper.generate_non_concrete_paths(leaves_only=False))
        leaf_paths = set(helper.generate_non_concrete_paths(leaves_only=True))

        assert all_paths != leaf_paths
        assert leaf_paths < all_paths  # strict subset


class TestGenerateConcretePaths:
    def test_expands_arrays_to_concrete_paths(self) -> None:
        helper = _make_helper(
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
        )
        lengths = {"magnetics/flux_loop": 2}
        paths = list(helper.generate_concrete_paths(lengths.get))

        assert "magnetics/flux_loop[0]/field" in paths
        assert "magnetics/flux_loop[1]/field" in paths

    def test_leaves_only_omits_array_struct_nodes(self) -> None:
        helper = _make_helper(
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
        )
        lengths = {"magnetics/flux_loop": 2}
        paths = list(helper.generate_concrete_paths(lengths.get, leaves_only=True))

        assert all("/field" in p for p in paths)
        assert "magnetics/flux_loop[0]" not in paths
        assert "magnetics/flux_loop[1]" not in paths

    def test_array_sizes_cached_after_expansion(self) -> None:
        helper = _make_helper(
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
        )
        call_count = 0

        def counting_callback(path: str) -> int:
            nonlocal call_count
            call_count += 1
            return 3

        list(helper.generate_concrete_paths(counting_callback))

        assert call_count == 1
        assert helper.array_sizes == {"magnetics/flux_loop": 3}
