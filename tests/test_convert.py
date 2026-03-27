"""Tests for tokamunch.convert — format conversion utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tokamunch.convert import (
    _get_ids_leaf_value,
    _ids_length_callback,
    _is_empty_imas_value,
    read_ids_records,
    read_json_records,
)
from tokamunch.mapping import MappingRecord

# ── minimal fake IDS objects ──────────────────────────────────────────────────


class _FakeAoS(list):
    """Fake array-of-structs: a plain list that supports .resize()."""

    def resize(self, n: int) -> None:
        while len(self) < n:
            self.append(_FakeStruct())
        del self[n:]


class _FakeStruct:
    def __init__(self) -> None:
        self.psi: float = 1.23
        self.r: float = 0.5
        self.position = _FakeAoS()


class _FakeMagnetics:
    """Fake top-level IDS with a time leaf and an AoS."""

    def __init__(self, n_loops: int = 0) -> None:
        self.time = [0.1, 0.2, 0.3]
        self.flux_loop = _FakeAoS()
        self.flux_loop.resize(n_loops)


# ── _ids_length_callback ──────────────────────────────────────────────────────


class TestIdsLengthCallback:
    def test_top_level_array_length(self) -> None:
        ids = _FakeMagnetics(n_loops=3)
        cb = _ids_length_callback(ids)
        assert cb("magnetics/flux_loop") == 3

    def test_zero_when_empty(self) -> None:
        ids = _FakeMagnetics(n_loops=0)
        cb = _ids_length_callback(ids)
        assert cb("magnetics/flux_loop") == 0

    def test_nested_array_length(self) -> None:
        ids = _FakeMagnetics(n_loops=2)
        ids.flux_loop[0].position.resize(4)
        cb = _ids_length_callback(ids)
        assert cb("magnetics/flux_loop[0]/position") == 4

    def test_missing_attribute_returns_zero(self) -> None:
        ids = _FakeMagnetics()
        cb = _ids_length_callback(ids)
        assert cb("magnetics/nonexistent_field") == 0

    def test_index_out_of_range_returns_zero(self) -> None:
        ids = _FakeMagnetics(n_loops=1)
        cb = _ids_length_callback(ids)
        # flux_loop[5] doesn't exist
        assert cb("magnetics/flux_loop[5]/position") == 0


# ── _is_empty_imas_value ──────────────────────────────────────────────────────


class TestIsEmptyImasValue:
    def test_none_is_empty(self) -> None:
        assert _is_empty_imas_value(None) is True

    def test_empty_list_is_empty(self) -> None:
        assert _is_empty_imas_value([]) is True

    def test_empty_numpy_array_is_empty(self) -> None:
        assert _is_empty_imas_value(np.array([])) is True

    def test_nonempty_list_is_not_empty(self) -> None:
        assert _is_empty_imas_value([1, 2, 3]) is False

    def test_nonempty_numpy_array_is_not_empty(self) -> None:
        assert _is_empty_imas_value(np.array([1.0])) is False

    def test_scalar_float_is_not_empty(self) -> None:
        assert _is_empty_imas_value(3.14) is False

    def test_scalar_zero_is_not_empty(self) -> None:
        # 0 is a valid value — only None and empty containers are empty.
        assert _is_empty_imas_value(0) is False


# ── _get_ids_leaf_value ───────────────────────────────────────────────────────


class TestGetIdsLeafValue:
    def test_simple_leaf(self) -> None:
        ids = _FakeMagnetics()
        result = _get_ids_leaf_value(ids, "magnetics/time")
        assert result == [0.1, 0.2, 0.3]

    def test_nested_leaf_via_array_index(self) -> None:
        ids = _FakeMagnetics(n_loops=1)
        ids.flux_loop[0].psi = 9.9
        result = _get_ids_leaf_value(ids, "magnetics/flux_loop[0]/psi")
        assert result == pytest.approx(9.9)

    def test_missing_attribute_returns_none(self) -> None:
        ids = _FakeMagnetics()
        result = _get_ids_leaf_value(ids, "magnetics/nonexistent")
        assert result is None

    def test_index_out_of_range_returns_none(self) -> None:
        ids = _FakeMagnetics(n_loops=1)
        result = _get_ids_leaf_value(ids, "magnetics/flux_loop[5]/psi")
        assert result is None


# ── read_ids_records ──────────────────────────────────────────────────────────


class TestReadIdsRecords:
    """read_ids_records uses the real schema trie but a fake IDS object."""

    def _make_magnetics_ids(self, n_loops: int = 0) -> _FakeMagnetics:
        return _FakeMagnetics(n_loops=n_loops)

    def test_returns_list_of_mapping_records(self) -> None:
        ids = self._make_magnetics_ids()
        records = read_ids_records(ids, "magnetics")
        assert isinstance(records, list)
        assert all(isinstance(r, MappingRecord) for r in records)

    def test_all_records_have_magnetics_prefix(self) -> None:
        ids = self._make_magnetics_ids()
        records = read_ids_records(ids, "magnetics")
        assert all(r.ids_path.startswith("magnetics/") for r in records)

    def test_skips_empty_list_fields(self) -> None:
        """flux_loop is empty (n_loops=0) so nothing under it should appear."""
        ids = self._make_magnetics_ids(n_loops=0)
        records = read_ids_records(ids, "magnetics")
        paths = [r.ids_path for r in records]
        assert not any("flux_loop" in p for p in paths)

    def test_expands_array_struct_when_populated(self) -> None:
        """With one flux_loop element the callback returns 1; expansion occurs.

        We verify via the length callback directly — the expansion machinery
        is exercised by test_path_expansion.py, and the IDS field layout from
        the real data dictionary would not match our fake struct attributes.
        """
        ids = self._make_magnetics_ids(n_loops=1)
        cb = _ids_length_callback(ids)
        assert cb("magnetics/flux_loop") == 1

    def test_all_records_are_ok(self) -> None:
        ids = self._make_magnetics_ids()
        records = read_ids_records(ids, "magnetics")
        assert all(r.ok for r in records)


# ── read_json_records ─────────────────────────────────────────────────────────


class TestReadJsonRecords:
    def test_reads_plain_values(self, tmp_path: Path) -> None:
        data = {
            "magnetics/time": [0.1, 0.2],
            "magnetics/flux_loop[0]/psi": 1.5,
        }
        p = tmp_path / "results.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        records = read_json_records(p)

        assert len(records) == 2
        paths = {r.ids_path for r in records}
        assert "magnetics/time" in paths
        assert "magnetics/flux_loop[0]/psi" in paths

    def test_decodes_binary_ndarray(self, tmp_path: Path) -> None:
        """Binary-encoded ndarrays are decoded back to numpy arrays."""
        import base64

        arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        encoded = {
            "__ndarray__": base64.b64encode(arr.tobytes()).decode("ascii"),
            "dtype": str(arr.dtype),
            "shape": list(arr.shape),
        }
        data = {"magnetics/flux_loop[0]/flux/data": encoded}
        p = tmp_path / "results.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        records = read_json_records(p)

        assert len(records) == 1
        value = records[0].value
        assert isinstance(value, np.ndarray)
        np.testing.assert_array_almost_equal(value, arr)

    def test_plain_dict_not_decoded_as_ndarray(self, tmp_path: Path) -> None:
        """A dict without __ndarray__ key is not decoded."""
        data = {"magnetics/meta": {"key": "value"}}
        p = tmp_path / "results.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        records = read_json_records(p)

        assert records[0].value == {"key": "value"}

    def test_all_records_are_ok(self, tmp_path: Path) -> None:
        data = {"magnetics/time": 1.0}
        p = tmp_path / "results.json"
        p.write_text(json.dumps(data), encoding="utf-8")

        records = read_json_records(p)

        assert all(r.ok for r in records)


# ── records_to_ids_objects ────────────────────────────────────────────────────


def _make_imas_mock(ids_map: dict[str, Any]) -> MagicMock:
    """Build a minimal imas module mock with the given IDS name → obj mapping."""
    factory = MagicMock()
    for ids_name, ids_obj in ids_map.items():
        getattr(factory, ids_name).return_value = ids_obj

    mock_imas = MagicMock()
    mock_imas.IDSFactory.return_value = factory
    return mock_imas


class TestRecordsToIdsObjects:
    """Tests for records_to_ids_objects, mocking imas via sys.modules.

    imas is imported lazily (inside the function), so patch.dict on sys.modules
    is the correct way to inject a mock without the module needing to be
    present at import time.
    """

    def test_returns_dict_keyed_by_ids_name(self) -> None:
        ids_obj = MagicMock()
        ids_obj.time_slice = _FakeAoS()
        mock_imas = _make_imas_mock({"magnetics": ids_obj})
        records = [MappingRecord(ids_path="magnetics/time", value=[0.1, 0.2])]

        with patch.dict("sys.modules", {"imas": mock_imas}):
            from tokamunch.convert import records_to_ids_objects

            result = records_to_ids_objects(records)

        assert "magnetics" in result

    def test_groups_records_by_ids_name(self) -> None:
        """Records from two IDS names produce two entries in the result dict."""
        mag_ids = MagicMock()
        mag_ids.time_slice = _FakeAoS()
        eq_ids = MagicMock()
        eq_ids.time_slice = _FakeAoS()
        mock_imas = _make_imas_mock({"magnetics": mag_ids, "equilibrium": eq_ids})

        records = [
            MappingRecord(ids_path="magnetics/time", value=[0.1]),
            MappingRecord(ids_path="equilibrium/time", value=[0.2]),
        ]

        with patch.dict("sys.modules", {"imas": mock_imas}):
            from tokamunch.convert import records_to_ids_objects

            result = records_to_ids_objects(records)

        assert set(result.keys()) == {"magnetics", "equilibrium"}

    def test_skips_error_records(self) -> None:
        """Error records are excluded by _group_records_by_ids."""
        mock_imas = _make_imas_mock({})
        records = [
            MappingRecord(ids_path="magnetics/time", error=RuntimeError("oops")),
        ]

        with patch.dict("sys.modules", {"imas": mock_imas}):
            from tokamunch.convert import records_to_ids_objects

            result = records_to_ids_objects(records)

        assert result == {}


# ── write_imas_output error recovery ─────────────────────────────────────────


def _make_write_imas_mock(
    ids_map: dict[str, Any],
    dbentry: MagicMock,
) -> MagicMock:
    """Build an imas module mock suitable for write_imas_output tests."""
    factory = MagicMock()
    for ids_name, ids_obj in ids_map.items():
        getattr(factory, ids_name).return_value = ids_obj

    mock_imas = MagicMock()
    mock_imas.IDSFactory.return_value = factory
    mock_imas.DBEntry.return_value = dbentry
    return mock_imas


def _make_dbentry_mock() -> MagicMock:
    dbentry = MagicMock()
    dbentry.__enter__ = MagicMock(return_value=dbentry)
    dbentry.__exit__ = MagicMock(return_value=False)
    return dbentry


class TestWriteImasOutputErrorRecovery:
    """write_imas_output catches per-IDS failures and returns IdsWriteError list.

    imas is imported lazily so sys.modules patching is used throughout.
    """

    def test_returns_empty_list_on_success(self, tmp_path: Path) -> None:
        from tokamunch.write_ids import write_imas_output

        records = [
            MappingRecord(ids_path="magnetics/time", value=[0.1]),
            MappingRecord(ids_path="equilibrium/time", value=[0.2]),
        ]
        dbentry = _make_dbentry_mock()
        ids_map = {
            "magnetics": MagicMock(time_slice=_FakeAoS()),
            "equilibrium": MagicMock(time_slice=_FakeAoS()),
        }
        mock_imas = _make_write_imas_mock(ids_map, dbentry)

        with patch.dict("sys.modules", {"imas": mock_imas}):
            errors = write_imas_output(tmp_path / "out.nc", records=records, force=True)

        assert errors == []

    def test_returns_ids_write_error_on_put_failure(self, tmp_path: Path) -> None:
        from tokamunch.write_ids import IdsWriteError, write_imas_output

        records = [MappingRecord(ids_path="magnetics/time", value=[0.1])]
        dbentry = _make_dbentry_mock()
        dbentry.put.side_effect = RuntimeError("IDS magnetics is not valid")
        mock_imas = _make_write_imas_mock(
            {"magnetics": MagicMock(time_slice=_FakeAoS())}, dbentry
        )

        with patch.dict("sys.modules", {"imas": mock_imas}):
            errors = write_imas_output(tmp_path / "out.nc", records=records, force=True)

        assert len(errors) == 1
        assert isinstance(errors[0], IdsWriteError)
        assert errors[0].ids_name == "magnetics"
        assert "not valid" in str(errors[0].cause)

    def test_failed_ids_records_preserved_in_error(self, tmp_path: Path) -> None:
        from tokamunch.write_ids import write_imas_output

        records = [MappingRecord(ids_path="magnetics/time", value=[0.1])]
        dbentry = _make_dbentry_mock()
        dbentry.put.side_effect = RuntimeError("validation error")
        mock_imas = _make_write_imas_mock(
            {"magnetics": MagicMock(time_slice=_FakeAoS())}, dbentry
        )

        with patch.dict("sys.modules", {"imas": mock_imas}):
            errors = write_imas_output(tmp_path / "out.nc", records=records, force=True)

        assert errors[0].records == records

    def test_other_ids_still_written_after_failure(self, tmp_path: Path) -> None:
        """A failure writing one IDS must not prevent writing others."""
        from tokamunch.write_ids import write_imas_output

        records = [
            MappingRecord(ids_path="magnetics/time", value=[0.1]),
            MappingRecord(ids_path="equilibrium/time", value=[0.2]),
        ]
        dbentry = _make_dbentry_mock()
        put_calls: list[Any] = []

        def _put(ids_obj: Any) -> None:
            put_calls.append(ids_obj)
            if len(put_calls) == 1:
                raise RuntimeError("magnetics failed")

        dbentry.put.side_effect = _put
        ids_map = {
            "magnetics": MagicMock(time_slice=_FakeAoS()),
            "equilibrium": MagicMock(time_slice=_FakeAoS()),
        }
        mock_imas = _make_write_imas_mock(ids_map, dbentry)

        with patch.dict("sys.modules", {"imas": mock_imas}):
            errors = write_imas_output(tmp_path / "out.nc", records=records, force=True)

        assert len(errors) == 1
        assert dbentry.put.call_count == 2
