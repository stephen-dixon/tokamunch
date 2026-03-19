import pytest

from tokamunch import (
    IDSNode,
    NodeType,
    WriteContext,
    ensure_ids_arrays_resized,
    resolve_ids_segments,
    resolve_ids_parent,
    set_ids_value,
    resize_and_set_ids_value,
)


class FakeAoS:
    def __init__(self) -> None:
        self.items = []
        self.resize_calls = []

    def __len__(self) -> int:
        return len(self.items)

    def resize(self, n: int) -> None:
        self.resize_calls.append(n)
        while len(self.items) < n:
            self.items.append(FakeNode())
        while len(self.items) > n:
            self.items.pop()

    def __getitem__(self, idx: int):
        return self.items[idx]

    def __setitem__(self, idx: int, value) -> None:
        self.items[idx] = value


class FakeNode:
    def __init__(self) -> None:
        self.profiles_1d = FakeAoS()
        self.ion = FakeAoS()
        self.density = None
        self.temperature = None
        self.time = None


def test_ensure_ids_arrays_resized_resizes_once_per_concrete_array_prefix() -> None:
    ids = FakeNode()
    write_ctx = WriteContext()
    array_sizes = {
        "core_profiles/profiles_1d": 2,
        "core_profiles/profiles_1d[1]/ion": 3,
    }
    segments = [
        IDSNode("core_profiles", NodeType.STRUCT),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 1),
        IDSNode("ion", NodeType.ARRAY_STRUCT, 2),
        IDSNode("density", NodeType.STRUCT),
    ]

    ensure_ids_arrays_resized(
        ids,
        segments,
        array_sizes,
        write_context=write_ctx,
        skip_root_segment=True,
    )
    ensure_ids_arrays_resized(
        ids,
        segments,
        array_sizes,
        write_context=write_ctx,
        skip_root_segment=True,
    )

    assert ids.profiles_1d.resize_calls == [2]
    assert ids.profiles_1d[1].ion.resize_calls == [3]


def test_resolve_ids_segments_after_resize() -> None:
    ids = FakeNode()
    array_sizes = {
        "core_profiles/profiles_1d": 2,
        "core_profiles/profiles_1d[1]/ion": 3,
    }
    segments = [
        IDSNode("core_profiles", NodeType.STRUCT),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 1),
        IDSNode("ion", NodeType.ARRAY_STRUCT, 2),
    ]

    ensure_ids_arrays_resized(ids, segments, array_sizes, skip_root_segment=True)
    obj = resolve_ids_segments(ids, segments, skip_root_segment=True)

    assert obj is ids.profiles_1d[1].ion[2]


def test_resolve_ids_parent_returns_parent_and_final_segment() -> None:
    ids = FakeNode()
    array_sizes = {"core_profiles/profiles_1d": 1}
    segments = [
        IDSNode("core_profiles", NodeType.STRUCT),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 0),
        IDSNode("time", NodeType.STRUCT),
    ]

    ensure_ids_arrays_resized(ids, segments, array_sizes, skip_root_segment=True)
    parent, final_seg = resolve_ids_parent(ids, segments, skip_root_segment=True)

    assert parent is ids.profiles_1d[0]
    assert final_seg == IDSNode("time", NodeType.STRUCT, None)


def test_set_ids_value_sets_struct_leaf() -> None:
    ids = FakeNode()
    array_sizes = {
        "core_profiles/profiles_1d": 2,
        "core_profiles/profiles_1d[1]/ion": 3,
    }
    segments = [
        IDSNode("core_profiles", NodeType.STRUCT),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 1),
        IDSNode("ion", NodeType.ARRAY_STRUCT, 2),
        IDSNode("density", NodeType.STRUCT),
    ]

    ensure_ids_arrays_resized(ids, segments, array_sizes, skip_root_segment=True)
    set_ids_value(ids, segments, 42.0, skip_root_segment=True)

    assert ids.profiles_1d[1].ion[2].density == 42.0


def test_set_ids_value_rejects_array_struct_assignment() -> None:
    ids = FakeNode()
    segments = [
        IDSNode("core_profiles", NodeType.STRUCT),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 1),
    ]

    with pytest.raises(ValueError):
        set_ids_value(ids, segments, 42.0, skip_root_segment=True)


def test_resize_and_set_ids_value_combines_both_steps() -> None:
    ids = FakeNode()
    write_ctx = WriteContext()
    array_sizes = {
        "core_profiles/profiles_1d": 2,
        "core_profiles/profiles_1d[1]/ion": 3,
    }
    segments = [
        IDSNode("core_profiles", NodeType.STRUCT),
        IDSNode("profiles_1d", NodeType.ARRAY_STRUCT, 1),
        IDSNode("ion", NodeType.ARRAY_STRUCT, 2),
        IDSNode("density", NodeType.STRUCT),
    ]

    resize_and_set_ids_value(
        ids,
        segments,
        99.0,
        array_sizes,
        write_context=write_ctx,
        skip_root_segment=True,
    )

    assert ids.profiles_1d.resize_calls == [2]
    assert ids.profiles_1d[1].ion.resize_calls == [3]
    assert ids.profiles_1d[1].ion[2].density == 99.0
