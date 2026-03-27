import json
from pathlib import Path

import pytest

from tokamunch import IDSHelper
from tokamunch.templates import _to_template_path, load_mapping_keys


class TestToTemplatePath:
    def test_replaces_schema_array_markers(self) -> None:
        assert (
            _to_template_path("magnetics/flux_loop(:)/field")
            == "magnetics/flux_loop[#]/field"
        )

    def test_multiple_array_levels(self) -> None:
        result = _to_template_path("core_profiles/profiles_1d(:)/ion(:)/density")
        assert result == "core_profiles/profiles_1d[#]/ion[#]/density"

    def test_array_struct_terminal_keeps_hash_placeholder(self) -> None:
        # Array-struct terminal nodes use [#] like all other array dimensions.
        assert _to_template_path("magnetics/flux_loop(:)") == "magnetics/flux_loop[#]"

    def test_simple_path_unchanged(self) -> None:
        assert _to_template_path("magnetics/time") == "magnetics/time"


class TestBuildBlankMappingTemplate:
    def _helper_from_paths(self, *paths: str) -> IDSHelper:
        return IDSHelper(list(paths))

    def test_all_paths_present_as_keys(self) -> None:
        # Patch IDSHelper.from_ids_name by passing directly via build_blank_mapping_template
        # through a mock IDSHelper — instead test _to_template_path + IDSHelper together.
        helper = IDSHelper(
            [
                "magnetics/time",
                "magnetics/flux_loop(:)",
                "magnetics/flux_loop(:)/field",
            ]
        )
        converted = {_to_template_path(p) for p in helper.generate_non_concrete_paths()}
        assert "magnetics/time" in converted
        assert "magnetics/flux_loop[#]/field" in converted
        assert "magnetics/flux_loop[#]" in converted

    def test_leaves_only_excludes_intermediates(self) -> None:
        helper = IDSHelper(
            [
                "magnetics/flux_loop(:)",
                "magnetics/flux_loop(:)/field",
            ]
        )
        leaf_paths = {
            _to_template_path(p)
            for p in helper.generate_non_concrete_paths(leaves_only=True)
        }
        assert "magnetics/flux_loop[#]/field" in leaf_paths
        assert "magnetics/flux_loop[#]" not in leaf_paths


class TestLoadMappingKeys:
    def test_loads_keys_from_json_object(self, tmp_path: Path) -> None:
        data: dict[str, object] = {
            "magnetics/flux_loop[#]/field": {},
            "magnetics/time": {},
        }
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps(data), encoding="utf-8")

        keys = load_mapping_keys(mapping_file)

        assert isinstance(keys, frozenset)
        assert keys == frozenset({"magnetics/flux_loop[#]/field", "magnetics/time"})

    def test_raises_on_non_object_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        with pytest.raises(ValueError, match="must contain a JSON object"):
            load_mapping_keys(bad_file)

    def test_empty_mapping_file(self, tmp_path: Path) -> None:
        mapping_file = tmp_path / "empty.json"
        mapping_file.write_text("{}", encoding="utf-8")

        keys = load_mapping_keys(mapping_file)
        assert keys == frozenset()


# ── is_comment_stub ───────────────────────────────────────────────────────────


class TestIsCommentStub:
    def test_comment_dict_is_stub(self) -> None:
        from tokamunch.templates import is_comment_stub

        assert is_comment_stub({"comment": "some description"}) is True

    def test_empty_comment_is_stub(self) -> None:
        from tokamunch.templates import is_comment_stub

        assert is_comment_stub({"comment": ""}) is True

    def test_comment_with_metadata_is_stub(self) -> None:
        from tokamunch.templates import is_comment_stub

        assert (
            is_comment_stub({"comment": "desc", "units": "T", "source": "UDA"}) is True
        )

    def test_dict_without_comment_is_not_stub(self) -> None:
        from tokamunch.templates import is_comment_stub

        assert is_comment_stub({"mapping": "some_expression"}) is False

    def test_empty_dict_is_not_stub(self) -> None:
        from tokamunch.templates import is_comment_stub

        assert is_comment_stub({}) is False

    def test_plain_string_is_not_stub(self) -> None:
        from tokamunch.templates import is_comment_stub

        assert is_comment_stub("some_expression") is False

    def test_none_is_not_stub(self) -> None:
        from tokamunch.templates import is_comment_stub

        assert is_comment_stub(None) is False

    def test_comment_with_extra_key_is_not_stub(self) -> None:
        from tokamunch.templates import is_comment_stub

        # "expression" is not an allowed metadata key
        assert (
            is_comment_stub({"comment": "desc", "expression": "mapper_call()"}) is False
        )


# ── build_blank_mapping_template stubs ────────────────────────────────────────


class TestBuildBlankMappingTemplateStubs:
    def test_values_are_comment_stubs(self) -> None:
        from tokamunch.templates import build_blank_mapping_template, is_comment_stub

        template = build_blank_mapping_template("magnetics", leaves_only=True)
        assert len(template) > 0
        for value in template.values():
            assert is_comment_stub(value), f"Expected stub, got {value!r}"

    def test_comment_is_populated_from_data_dictionary(self) -> None:
        from tokamunch.templates import build_blank_mapping_template

        template = build_blank_mapping_template("magnetics", leaves_only=True)
        for value in template.values():
            assert isinstance(value.get("comment"), str)
            # Comments should be non-empty strings from the IDS documentation.
            assert value["comment"] != "", f"Expected populated comment, got {value!r}"


# ── merge_mapping_stubs ───────────────────────────────────────────────────────


class TestMergeMappingStubs:
    def test_existing_entries_preserved(self, tmp_path: Path) -> None:
        from tokamunch.templates import merge_mapping_stubs

        existing = {
            "magnetics/time": "UDA:time",
            "magnetics/flux_loop[#]/psi": {"comment": "my note"},
        }
        f = tmp_path / "m.json"
        f.write_text(json.dumps(existing), encoding="utf-8")
        merged = merge_mapping_stubs("magnetics", f)
        assert merged["magnetics/time"] == "UDA:time"
        assert merged["magnetics/flux_loop[#]/psi"] == {"comment": "my note"}

    def test_new_paths_added_as_stubs(self, tmp_path: Path) -> None:
        from tokamunch.templates import is_comment_stub, merge_mapping_stubs

        existing = {"magnetics/time": "UDA:time"}
        f = tmp_path / "m.json"
        f.write_text(json.dumps(existing), encoding="utf-8")
        merged = merge_mapping_stubs("magnetics", f)
        # There should be many more keys from the IDS schema
        assert len(merged) > 1
        # All new entries must be stubs
        for key, val in merged.items():
            if key != "magnetics/time":
                assert is_comment_stub(
                    val
                ), f"Expected stub for new key {key!r}, got {val!r}"

    def test_existing_path_not_overwritten(self, tmp_path: Path) -> None:
        from tokamunch.templates import merge_mapping_stubs

        existing = {"magnetics/time": "my_custom_expression"}
        f = tmp_path / "m.json"
        f.write_text(json.dumps(existing), encoding="utf-8")
        merged = merge_mapping_stubs("magnetics", f)
        assert merged["magnetics/time"] == "my_custom_expression"

    def test_result_contains_more_keys_than_existing(self, tmp_path: Path) -> None:
        from tokamunch.templates import merge_mapping_stubs

        existing = {"magnetics/time": "UDA:time"}
        f = tmp_path / "m.json"
        f.write_text(json.dumps(existing), encoding="utf-8")
        merged = merge_mapping_stubs("magnetics", f)
        assert len(merged) > len(existing)

    def test_raises_on_non_object_json(self, tmp_path: Path) -> None:
        from tokamunch.templates import merge_mapping_stubs

        f = tmp_path / "bad.json"
        f.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="JSON object"):
            merge_mapping_stubs("magnetics", f)
