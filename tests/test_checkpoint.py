"""Tests for tokamunch.checkpoint — save/load/apply checkpoint state."""

from __future__ import annotations

from pathlib import Path

import pytest

from tokamunch.checkpoint import (
    Checkpoint,
    apply_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
from tokamunch.mapping import MappingRecord


class TestLoadSaveCheckpoint:
    def test_load_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert load_checkpoint(tmp_path / "nonexistent.json") is None

    def test_save_creates_file(self, tmp_path: Path) -> None:
        cp = Checkpoint(
            output_path="out.json", completed_paths=["a/b"], results={"a/b": 1.0}
        )
        path = tmp_path / "cp.json"
        save_checkpoint(path, cp)
        assert path.exists()

    def test_round_trip(self, tmp_path: Path) -> None:
        cp = Checkpoint(
            output_path="results.nc",
            completed_paths=["magnetics/time", "magnetics/flux_loop[0]/psi"],
            results={"magnetics/time": [0.1, 0.2], "magnetics/flux_loop[0]/psi": 3.14},
        )
        path = tmp_path / "cp.json"
        save_checkpoint(path, cp)
        loaded = load_checkpoint(path)
        assert loaded is not None
        assert loaded.output_path == "results.nc"
        assert loaded.completed_paths == cp.completed_paths
        assert loaded.results["magnetics/time"] == [0.1, 0.2]

    def test_atomic_write_does_not_leave_tmp_on_success(self, tmp_path: Path) -> None:
        cp = Checkpoint(output_path="out.json")
        path = tmp_path / "cp.json"
        save_checkpoint(path, cp)
        # .tmp file should be gone after successful rename
        assert not (tmp_path / "cp.json.tmp").exists()
        assert path.exists()

    def test_overwrites_existing_checkpoint(self, tmp_path: Path) -> None:
        path = tmp_path / "cp.json"
        save_checkpoint(path, Checkpoint(output_path="v1.json", completed_paths=["a"]))
        save_checkpoint(
            path, Checkpoint(output_path="v2.json", completed_paths=["a", "b"])
        )
        loaded = load_checkpoint(path)
        assert loaded is not None
        assert loaded.output_path == "v2.json"
        assert len(loaded.completed_paths) == 2

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="valid JSON"):
            load_checkpoint(path)

    def test_empty_checkpoint(self, tmp_path: Path) -> None:
        cp = Checkpoint(output_path="out.json")
        path = tmp_path / "cp.json"
        save_checkpoint(path, cp)
        loaded = load_checkpoint(path)
        assert loaded is not None
        assert loaded.completed_paths == []
        assert loaded.results == {}


class TestApplyCheckpoint:
    def test_no_completed_paths_all_remain(self) -> None:
        paths = ["a/b", "c/d", "e/f"]
        cp = Checkpoint(output_path="out.json")
        remaining, done = apply_checkpoint(paths, cp)
        assert remaining == paths
        assert done == []

    def test_completed_paths_excluded_from_remaining(self) -> None:
        paths = ["a/b", "c/d", "e/f"]
        cp = Checkpoint(
            output_path="out.json",
            completed_paths=["c/d"],
            results={"c/d": 42},
        )
        remaining, _done = apply_checkpoint(paths, cp)
        assert "c/d" not in remaining
        assert "a/b" in remaining
        assert "e/f" in remaining

    def test_done_records_have_correct_values(self) -> None:
        paths = ["a/b", "c/d"]
        cp = Checkpoint(
            output_path="out.json",
            completed_paths=["a/b"],
            results={"a/b": 99.9},
        )
        _, done = apply_checkpoint(paths, cp)
        assert len(done) == 1
        assert done[0].ids_path == "a/b"
        assert done[0].value == 99.9

    def test_done_records_are_mapping_records(self) -> None:
        paths = ["a/b"]
        cp = Checkpoint(
            output_path="out.json", completed_paths=["a/b"], results={"a/b": 1}
        )
        _, done = apply_checkpoint(paths, cp)
        assert all(isinstance(r, MappingRecord) for r in done)

    def test_all_paths_completed_remaining_empty(self) -> None:
        paths = ["a/b", "c/d"]
        cp = Checkpoint(
            output_path="out.json",
            completed_paths=["a/b", "c/d"],
            results={"a/b": 1, "c/d": 2},
        )
        remaining, done = apply_checkpoint(paths, cp)
        assert remaining == []
        assert len(done) == 2

    def test_order_of_remaining_preserved(self) -> None:
        paths = ["z/first", "a/second", "m/third"]
        cp = Checkpoint(
            output_path="out.json", completed_paths=["a/second"], results={}
        )
        remaining, _ = apply_checkpoint(paths, cp)
        assert remaining == ["z/first", "m/third"]
