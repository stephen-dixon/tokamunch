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
