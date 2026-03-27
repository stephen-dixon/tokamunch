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
        data = {
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
