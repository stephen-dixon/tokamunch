"""Tests for tokamunch.diff — record comparison utilities."""

from __future__ import annotations

import numpy as np

from tokamunch.diff import DiffEntry, diff_records, render_diff
from tokamunch.mapping import MappingRecord


def _ok(path: str, value: object) -> MappingRecord:
    return MappingRecord(ids_path=path, value=value)


def _err(path: str) -> MappingRecord:
    return MappingRecord(ids_path=path, error=RuntimeError("oops"))


# ── diff_records ──────────────────────────────────────────────────────────────


class TestDiffRecords:
    def test_path_only_in_a_is_removed(self) -> None:
        entries = diff_records([_ok("a/b", 1.0)], [])
        assert len(entries) == 1
        assert entries[0].status == "removed"
        assert entries[0].path == "a/b"
        assert entries[0].value_a == 1.0
        assert entries[0].value_b is None

    def test_path_only_in_b_is_added(self) -> None:
        entries = diff_records([], [_ok("a/b", 2.0)])
        assert len(entries) == 1
        assert entries[0].status == "added"
        assert entries[0].path == "a/b"
        assert entries[0].value_a is None
        assert entries[0].value_b == 2.0

    def test_same_scalar_is_unchanged(self) -> None:
        entries = diff_records([_ok("a/b", 42.0)], [_ok("a/b", 42.0)])
        assert entries[0].status == "unchanged"

    def test_different_scalar_is_changed(self) -> None:
        entries = diff_records([_ok("a/b", 1.0)], [_ok("a/b", 2.0)])
        assert entries[0].status == "changed"
        assert entries[0].value_a == 1.0
        assert entries[0].value_b == 2.0

    def test_same_numpy_array_is_unchanged(self) -> None:
        arr = np.array([1.0, 2.0, 3.0])
        entries = diff_records([_ok("a/b", arr)], [_ok("a/b", arr.copy())])
        assert entries[0].status == "unchanged"

    def test_different_numpy_array_is_changed(self) -> None:
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 9.9])
        entries = diff_records([_ok("a/b", a)], [_ok("a/b", b)])
        assert entries[0].status == "changed"

    def test_different_shape_arrays_are_changed(self) -> None:
        a = np.array([1.0, 2.0])
        b = np.array([1.0, 2.0, 3.0])
        entries = diff_records([_ok("a/b", a)], [_ok("a/b", b)])
        assert entries[0].status == "changed"

    def test_error_records_excluded_from_values(self) -> None:
        """Error records are not included in the value maps used for diffing."""
        entries = diff_records([_err("a/b")], [_ok("a/b", 1.0)])
        # a/b absent from A's value map → shows as added
        assert entries[0].status == "added"

    def test_all_statuses_returned(self) -> None:
        records_a = [_ok("same", 1), _ok("removed", 2), _ok("changed", 3)]
        records_b = [_ok("same", 1), _ok("added", 4), _ok("changed", 99)]
        by_path = {e.path: e.status for e in diff_records(records_a, records_b)}
        assert by_path["same"] == "unchanged"
        assert by_path["removed"] == "removed"
        assert by_path["changed"] == "changed"
        assert by_path["added"] == "added"

    def test_added_paths_sorted_alphabetically(self) -> None:
        b = [_ok("z/path", 1), _ok("a/path", 2), _ok("m/path", 3)]
        entries = diff_records([], b)
        added = [e.path for e in entries]
        assert added == sorted(added)


# ── render_diff ───────────────────────────────────────────────────────────────


class TestRenderDiff:
    def _make_entries(self) -> list[DiffEntry]:
        return [
            DiffEntry(path="a/added", value_a=None, value_b=1.0, status="added"),
            DiffEntry(path="b/removed", value_a=2.0, value_b=None, status="removed"),
            DiffEntry(path="c/changed", value_a=3.0, value_b=9.0, status="changed"),
            DiffEntry(path="d/same", value_a=4.0, value_b=4.0, status="unchanged"),
        ]

    def test_added_has_plus_prefix(self) -> None:
        out = render_diff(self._make_entries(), "A", "B")
        assert any(
            line.startswith("+ ") and "a/added" in line for line in out.splitlines()
        )

    def test_removed_has_minus_prefix(self) -> None:
        out = render_diff(self._make_entries(), "A", "B")
        assert any(
            line.startswith("- ") and "b/removed" in line for line in out.splitlines()
        )

    def test_changed_has_tilde_prefix(self) -> None:
        out = render_diff(self._make_entries(), "A", "B")
        assert any(
            line.startswith("~ ") and "c/changed" in line for line in out.splitlines()
        )

    def test_unchanged_hidden_by_default(self) -> None:
        out = render_diff(self._make_entries(), "A", "B")
        assert "d/same" not in out

    def test_unchanged_shown_when_requested(self) -> None:
        out = render_diff(self._make_entries(), "A", "B", show_unchanged=True)
        assert "d/same" in out

    def test_header_contains_labels(self) -> None:
        out = render_diff(self._make_entries(), "file_a.json", "file_b.json")
        assert "file_a.json" in out
        assert "file_b.json" in out

    def test_summary_line_present(self) -> None:
        out = render_diff(self._make_entries(), "A", "B")
        summary_line = [ln for ln in out.splitlines() if "Summary" in ln]
        assert len(summary_line) == 1
        assert "added" in summary_line[0]
        assert "removed" in summary_line[0]
        assert "changed" in summary_line[0]

    def test_summary_counts_correct(self) -> None:
        entries = [
            DiffEntry(path="p1", value_a=None, value_b=1, status="added"),
            DiffEntry(path="p2", value_a=2, value_b=None, status="removed"),
            DiffEntry(path="p3", value_a=3, value_b=9, status="changed"),
            DiffEntry(path="p4", value_a=4, value_b=4, status="unchanged"),
        ]
        out = render_diff(entries, "A", "B")
        assert "1 added" in out
        assert "1 removed" in out
        assert "1 changed" in out
        assert "1 unchanged" in out
