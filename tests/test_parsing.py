import pytest

from tokamunch import (
    IDSNode,
    NodeType,
    concrete_path_to_template,
    normalise_schema_segment,
    parse_concrete_path,
    parse_schema_path,
    render_array_length_query_path,
    render_concrete_path,
    render_schema_path,
)


def test_normalise_schema_segment_strips_itime() -> None:
    assert normalise_schema_segment("time_slice(itime)") == "time_slice"


def test_parse_schema_path_plain_and_array() -> None:
    got = list(parse_schema_path("core_profiles/profiles_1d(:)/ion(:)/density"))

    assert got == [
        IDSNode("core_profiles", NodeType.SIMPLE_NODE, None),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, None),
        IDSNode("ion", NodeType.ARRAY_STRUCT, None),
        IDSNode("density", NodeType.SIMPLE_NODE, None),
    ]


def test_parse_concrete_path_plain_and_array() -> None:
    got = list(parse_concrete_path("core_profiles/profiles_1d[1]/ion[2]/density"))

    assert got == [
        IDSNode("core_profiles", NodeType.SIMPLE_NODE, None),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 1),
        IDSNode("ion", NodeType.ARRAY_STRUCT, 2),
        IDSNode("density", NodeType.SIMPLE_NODE, None),
    ]


def test_parse_concrete_path_invalid_segment_raises() -> None:
    with pytest.raises(ValueError):
        list(parse_concrete_path("core_profiles/profiles_1d[]/density"))


def test_render_schema_path() -> None:
    nodes = [
        IDSNode("core_profiles", NodeType.SIMPLE_NODE),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT),
        IDSNode("density", NodeType.SIMPLE_NODE),
    ]
    assert render_schema_path(nodes) == "core_profiles/profiles_1d(:)/density"


def test_render_concrete_path() -> None:
    nodes = [
        IDSNode("core_profiles", NodeType.SIMPLE_NODE),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 3),
        IDSNode("density", NodeType.SIMPLE_NODE),
    ]
    assert render_concrete_path(nodes) == "core_profiles/profiles_1d[3]/density"


def test_render_array_length_query_path_for_root_array() -> None:
    nodes = [
        IDSNode("core_profiles", NodeType.SIMPLE_NODE),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, None),
    ]
    assert render_array_length_query_path(nodes) == "core_profiles/profiles_1d"


def test_concrete_path_to_template_replaces_indices() -> None:
    assert (
        concrete_path_to_template("magnetics/flux_loop[0]/position[2]/r")
        == "magnetics/flux_loop[#]/position[#]/r"
    )


def test_concrete_path_to_template_no_arrays_unchanged() -> None:
    assert concrete_path_to_template("magnetics/time") == "magnetics/time"


def test_concrete_path_to_template_large_index() -> None:
    assert concrete_path_to_template("core_profiles/profiles_1d[123]/density") == (
        "core_profiles/profiles_1d[#]/density"
    )


def test_render_array_length_query_path_for_nested_array() -> None:
    nodes = [
        IDSNode("core_profiles", NodeType.SIMPLE_NODE),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 0),
        IDSNode("ion", NodeType.ARRAY_STRUCT, None),
    ]
    assert render_array_length_query_path(nodes) == "core_profiles/profiles_1d[0]/ion"


class TestParseSchemaPathItimeAnnotation:
    def test_itime_segment_is_array_struct(self) -> None:
        """A segment annotated with (itime) must be an ARRAY_STRUCT node."""
        got = list(parse_schema_path("equilibrium/time_slice(itime)/psi"))
        assert got[1] == IDSNode("time_slice", NodeType.ARRAY_STRUCT, None)

    def test_itime_name_has_annotation_stripped(self) -> None:
        """The ARRAY_STRUCT node's name must not include the (itime) annotation."""
        got = list(parse_schema_path("equilibrium/time_slice(itime)"))
        assert got[1].name == "time_slice"

    def test_itime_and_array_suffix_coexist(self) -> None:
        """A segment can have both (itime) and (:) — both indicate ARRAY_STRUCT."""
        got = list(parse_schema_path("equilibrium/time_slice(itime)(:)/psi"))
        assert got[1] == IDSNode("time_slice", NodeType.ARRAY_STRUCT, None)

    def test_itime_full_path_node_sequence(self) -> None:
        """Full path with (itime) array struct produces the correct node sequence."""
        got = list(
            parse_schema_path(
                "equilibrium/time_slice(itime)/coordinate_system/jacobian"
            )
        )
        assert got == [
            IDSNode("equilibrium", NodeType.SIMPLE_NODE, None),
            IDSNode("time_slice", NodeType.ARRAY_STRUCT, None),
            IDSNode("coordinate_system", NodeType.SIMPLE_NODE, None),
            IDSNode("jacobian", NodeType.SIMPLE_NODE, None),
        ]


class TestParseSchemaPathMultiDimSuffix:
    def test_2d_suffix_stripped(self) -> None:
        """(:,:) on a leaf field is stripped from the node name."""
        got = list(parse_schema_path("equilibrium/jacobian(:,:)"))
        assert got[1] == IDSNode("jacobian", NodeType.SIMPLE_NODE, None)

    def test_4d_suffix_stripped(self) -> None:
        """(:,:,:,:) on a leaf field is stripped from the node name."""
        got = list(parse_schema_path("ids/tensor_covariant(:,:,:,:)"))
        assert got[1] == IDSNode("tensor_covariant", NodeType.SIMPLE_NODE, None)

    def test_single_dim_suffix_not_stripped(self) -> None:
        """(:) is the array-struct marker and must NOT be stripped as a multi-dim suffix."""
        got = list(parse_schema_path("magnetics/flux_loop(:)/r"))
        assert got[1] == IDSNode("flux_loop", NodeType.ARRAY_STRUCT, None)

    def test_multi_dim_suffix_not_treated_as_array_struct(self) -> None:
        """A (:,:) leaf node must remain a SIMPLE_NODE, not become ARRAY_STRUCT."""
        got = list(parse_schema_path("equilibrium/jacobian(:,:)"))
        assert got[1].node_type is NodeType.SIMPLE_NODE

    def test_full_path_with_itime_and_multi_dim(self) -> None:
        """Path mixing (itime) struct and (:,:) leaf renders all nodes correctly."""
        got = list(
            parse_schema_path(
                "equilibrium/time_slice(itime)/coordinate_system/jacobian(:,:)"
            )
        )
        assert got == [
            IDSNode("equilibrium", NodeType.SIMPLE_NODE, None),
            IDSNode("time_slice", NodeType.ARRAY_STRUCT, None),
            IDSNode("coordinate_system", NodeType.SIMPLE_NODE, None),
            IDSNode("jacobian", NodeType.SIMPLE_NODE, None),
        ]
