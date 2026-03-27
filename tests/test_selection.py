from tokamunch import IDSHelper
from tokamunch.selection import (
    IdsSelection,
    MultiPathSelection,
    SinglePathSelection,
    _included,
    generate_selected_paths,
)


class FakeTokamap:
    def __init__(self, lengths: dict[str, int]):
        self._lengths = lengths

    def get_array_length(self, path: str) -> int:
        return self._lengths.get(path, 0)


class FakeCtx:
    def __init__(self, schema_paths: list[str], lengths: dict[str, int]):
        self._helper = IDSHelper(schema_paths)
        self.tokamap = FakeTokamap(lengths)

    def ids_helper(self, ids_name: str) -> IDSHelper:
        return self._helper


class TestIncluded:
    def test_no_filters_always_included(self) -> None:
        assert (
            _included("magnetics/flux_loop[0]/field", match=None, mapping_keys=None)
            is True
        )

    def test_match_filter(self) -> None:
        assert (
            _included(
                "magnetics/flux_loop[0]/field",
                match="magnetics/flux_loop*",
                mapping_keys=None,
            )
            is True
        )
        assert (
            _included(
                "magnetics/b_field_pol_probe[0]/field",
                match="magnetics/flux_loop*",
                mapping_keys=None,
            )
            is False
        )

    def test_mapping_keys_filter(self) -> None:
        keys = frozenset({"magnetics/flux_loop[#]/field"})
        assert (
            _included("magnetics/flux_loop[0]/field", match=None, mapping_keys=keys)
            is True
        )
        assert (
            _included("magnetics/flux_loop[1]/field", match=None, mapping_keys=keys)
            is True
        )
        assert (
            _included(
                "magnetics/b_field_pol_probe[0]/field", match=None, mapping_keys=keys
            )
            is False
        )

    def test_mapping_keys_and_match_are_combined(self) -> None:
        keys = frozenset({"magnetics/flux_loop[#]/field", "magnetics/flux_loop[#]/r"})
        # Passes both filters.
        assert (
            _included(
                "magnetics/flux_loop[0]/field", match="*field*", mapping_keys=keys
            )
            is True
        )
        # In mapping keys but excluded by match.
        assert (
            _included("magnetics/flux_loop[0]/r", match="*field*", mapping_keys=keys)
            is False
        )
        # Passes match but not in mapping keys.
        assert (
            _included(
                "magnetics/something_else[0]/field", match="*field*", mapping_keys=keys
            )
            is False
        )

    def test_mapping_keys_none_means_no_filter(self) -> None:
        assert _included("anything/at/all", match=None, mapping_keys=None) is True


class TestGenerateSelectedPathsIdsSelection:
    def test_intersection_filters_to_mapping_keys_only(self) -> None:
        schema = [
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
            "magnetics/flux_loop(:)/r",
        ]
        ctx = FakeCtx(schema, {"magnetics/flux_loop": 2})
        keys = frozenset({"magnetics/flux_loop[#]/field"})
        sel = IdsSelection(ids="magnetics", mapping_keys=keys)

        paths = list(generate_selected_paths(sel, ctx))
        assert paths == [
            "magnetics/flux_loop[0]/field",
            "magnetics/flux_loop[1]/field",
        ]

    def test_empty_intersection_yields_nothing(self) -> None:
        schema = ["magnetics/flux_loop(:)", "magnetics/flux_loop(:)/field"]
        ctx = FakeCtx(schema, {"magnetics/flux_loop": 3})
        keys = frozenset({"magnetics/completely_different[#]/path"})
        sel = IdsSelection(ids="magnetics", mapping_keys=keys)

        assert list(generate_selected_paths(sel, ctx)) == []

    def test_match_filter_applied(self) -> None:
        schema = [
            "magnetics/flux_loop(:)/field",
            "magnetics/flux_loop(:)/r",
        ]
        ctx = FakeCtx(schema, {"magnetics/flux_loop": 2})
        sel = IdsSelection(ids="magnetics", match="*field*")

        paths = list(generate_selected_paths(sel, ctx))
        assert all("field" in p for p in paths)
        assert not any("/r" in p for p in paths)

    def test_leaves_only_flag(self) -> None:
        schema = [
            "magnetics/flux_loop(:)",
            "magnetics/flux_loop(:)/field",
        ]
        ctx = FakeCtx(schema, {"magnetics/flux_loop": 1})
        sel = IdsSelection(ids="magnetics", leaves_only=True)

        paths = list(generate_selected_paths(sel, ctx))
        assert "magnetics/flux_loop[0]/field" in paths
        assert "magnetics/flux_loop[0]" not in paths


class TestGenerateSelectedPathsMultiPathSelection:
    def _make_ctx(self) -> FakeCtx:
        return FakeCtx([], {})

    def test_yields_all_paths(self) -> None:
        ctx = self._make_ctx()
        paths = ["magnetics/flux_loop[0]/field", "magnetics/flux_loop[1]/field"]
        sel = MultiPathSelection(paths=paths)
        assert list(generate_selected_paths(sel, ctx)) == paths

    def test_filtered_by_mapping_keys(self) -> None:
        ctx = self._make_ctx()
        keys = frozenset({"magnetics/flux_loop[#]/field"})
        sel = MultiPathSelection(
            paths=[
                "magnetics/flux_loop[0]/field",
                "magnetics/other[0]/field",
            ],
            mapping_keys=keys,
        )
        assert list(generate_selected_paths(sel, ctx)) == ["magnetics/flux_loop[0]/field"]

    def test_empty_paths_yields_nothing(self) -> None:
        ctx = self._make_ctx()
        sel = MultiPathSelection(paths=[])
        assert list(generate_selected_paths(sel, ctx)) == []

    def test_order_preserved(self) -> None:
        ctx = self._make_ctx()
        paths = ["magnetics/time", "magnetics/flux_loop[0]/r", "magnetics/flux_loop[1]/r"]
        sel = MultiPathSelection(paths=paths)
        assert list(generate_selected_paths(sel, ctx)) == paths


class TestGenerateSelectedPathsSinglePathSelection:
    def _make_ctx(self) -> FakeCtx:
        return FakeCtx([], {})

    def test_yields_path_when_no_filter(self) -> None:
        ctx = self._make_ctx()
        sel = SinglePathSelection(path="magnetics/flux_loop[0]/field")
        assert list(generate_selected_paths(sel, ctx)) == [
            "magnetics/flux_loop[0]/field"
        ]

    def test_filtered_by_mapping_keys(self) -> None:
        ctx = self._make_ctx()
        keys = frozenset({"magnetics/flux_loop[#]/field"})

        sel_match = SinglePathSelection(
            path="magnetics/flux_loop[0]/field", mapping_keys=keys
        )
        assert list(generate_selected_paths(sel_match, ctx)) == [
            "magnetics/flux_loop[0]/field"
        ]

        sel_no_match = SinglePathSelection(
            path="magnetics/other[0]/field", mapping_keys=keys
        )
        assert list(generate_selected_paths(sel_no_match, ctx)) == []
