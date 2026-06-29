"""Tests for _populate_ids behaviour around array-struct vs leaf nodes."""

from __future__ import annotations

from typing import Any

import pytest

from tokamunch.mapping import MappingRecord
from tokamunch.write_ids import _populate_ids

# ── minimal fake IDS objects ──────────────────────────────────────────────────


class FakeAoS:
    """Fake array-of-structs node (mimics imas AoS)."""

    def __init__(self) -> None:
        self._items: list[FakeStruct] = []
        self.resize_calls: list[int] = []

    def __len__(self) -> int:
        return len(self._items)

    def resize(self, n: int) -> None:
        self.resize_calls.append(n)
        while len(self._items) < n:
            self._items.append(FakeStruct())
        self._items = self._items[:n]

    def __getitem__(self, idx: int) -> FakeStruct:
        return self._items[idx]


class FakeStruct:
    """Fake IDS struct node with a scalar leaf and a nested AoS."""

    def __init__(self) -> None:
        self.psi: float | None = None
        self.profiles_1d = FakeAoS()


class FakeEquilibrium:
    """Fake top-level IDS (stands in for imas equilibrium)."""

    def __init__(self) -> None:
        self.time_slice = FakeAoS()
        self.time: list[float] = []


class FakeTypedEquilibrium:
    """Fake top-level IDS with a typed scalar setter."""

    def __init__(self) -> None:
        self._ids_properties_homogeneous_time: int | None = None

    @property
    def ids_properties(self) -> Any:
        return self

    @property
    def homogeneous_time(self) -> int | None:
        return self._ids_properties_homogeneous_time

    @homogeneous_time.setter
    def homogeneous_time(self, value: object) -> None:
        self._ids_properties_homogeneous_time = int(value)


# ── helpers ───────────────────────────────────────────────────────────────────


def _ok(ids_path: str, value: object) -> MappingRecord:
    return MappingRecord(ids_path=ids_path, value=value)


# ── tests ─────────────────────────────────────────────────────────────────────


class TestPopulateIdsArrayStructNodes:
    def test_array_struct_terminal_triggers_resize(self) -> None:
        """An array-struct record (e.g. time_slice[0]) must resize the IDS
        array even when no leaf children are present in the records."""
        ids = FakeEquilibrium()
        records = [_ok("equilibrium/time_slice[0]", 42)]

        _populate_ids(ids, records)

        assert ids.time_slice.resize_calls == [1]

    def test_array_struct_terminal_does_not_set_value(self) -> None:
        """The mapped value for an array-struct path must not be written into
        the IDS — only the resize should occur."""
        ids = FakeEquilibrium()
        records = [_ok("equilibrium/time_slice[0]", 99)]

        _populate_ids(ids, records)

        # After resize the element exists but none of its attributes should
        # have been set to the record value.
        elem = ids.time_slice[0]
        assert elem.psi is None

    def test_array_struct_multi_element_resize(self) -> None:
        """Multiple array-struct records derive the correct required size."""
        ids = FakeEquilibrium()
        records = [
            _ok("equilibrium/time_slice[0]", None),
            _ok("equilibrium/time_slice[1]", None),
            _ok("equilibrium/time_slice[2]", None),
        ]

        _populate_ids(ids, records)

        assert len(ids.time_slice) == 3
        # Resize should have been called exactly once (WriteContext deduplication).
        assert ids.time_slice.resize_calls == [3]

    def test_leaf_node_sets_value(self) -> None:
        """Leaf records are written normally alongside array-struct records."""
        ids = FakeEquilibrium()
        records = [
            _ok("equilibrium/time_slice[0]", None),
            _ok("equilibrium/time_slice[0]/psi", 1.23),
        ]

        _populate_ids(ids, records)

        assert ids.time_slice[0].psi == 1.23

    def test_array_struct_only_resize_is_idempotent(self) -> None:
        """The WriteContext ensures a given array-struct path is resized at
        most once even when multiple records share the same prefix."""
        ids = FakeEquilibrium()
        records = [
            _ok("equilibrium/time_slice[0]", None),
            _ok("equilibrium/time_slice[0]/psi", 1.0),
        ]

        _populate_ids(ids, records)

        assert ids.time_slice.resize_calls == [1]

    def test_assignment_error_includes_path_and_value(self) -> None:
        ids = FakeTypedEquilibrium()
        records = [
            _ok("equilibrium/ids_properties/homogeneous_time", "<INSERT>"),
        ]

        with pytest.raises(RuntimeError) as excinfo:
            _populate_ids(ids, records)

        msg = str(excinfo.value)
        assert "equilibrium/ids_properties/homogeneous_time" in msg
        assert "'<INSERT>'" in msg
        assert "invalid literal for int()" in msg
