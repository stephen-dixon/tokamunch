"""Tests for new CLI subcommands and flags — argparse wiring only, no mapper."""
from __future__ import annotations

import pytest

from tokamunch.cli import build_parser


def _parse(*argv: str) -> object:
    return build_parser().parse_args(list(argv))


# ── update-mapping ────────────────────────────────────────────────────────────


class TestUpdateMappingParser:
    def test_basic(self) -> None:
        args = _parse("update-mapping", "--ids", "magnetics", "--mapping", "m.json")
        assert args.ids == "magnetics"
        assert args.mapping == "m.json"

    def test_with_output_and_force(self) -> None:
        args = _parse(
            "update-mapping", "--ids", "magnetics",
            "--mapping", "m.json", "--output", "out.json", "--force",
        )
        assert args.output == "out.json"
        assert args.force is True

    def test_leaves_only(self) -> None:
        args = _parse("update-mapping", "--ids", "magnetics", "--mapping", "m.json", "--leaves-only")
        assert args.leaves_only is True


# ── diff ──────────────────────────────────────────────────────────────────────


class TestDiffParser:
    def test_positional_files(self) -> None:
        args = _parse("diff", "a.json", "b.json")
        assert args.file_a == "a.json"
        assert args.file_b == "b.json"

    def test_ids_flag(self) -> None:
        args = _parse("diff", "a.json", "b.json", "--ids", "magnetics", "equilibrium")
        assert args.ids == ["magnetics", "equilibrium"]

    def test_show_unchanged(self) -> None:
        args = _parse("diff", "a.json", "b.json", "--show-unchanged")
        assert args.show_unchanged is True

    def test_show_unchanged_default_false(self) -> None:
        args = _parse("diff", "a.json", "b.json")
        assert args.show_unchanged is False

    def test_ids_default_none(self) -> None:
        args = _parse("diff", "a.json", "b.json")
        assert args.ids is None


# ── update ────────────────────────────────────────────────────────────────────


class TestUpdateParser:
    def test_basic(self) -> None:
        args = _parse("update", "--input", "existing.json", "--output", "new.json", "--ids", "magnetics")
        assert args.input == "existing.json"
        assert args.output == "new.json"
        assert args.ids == "magnetics"

    def test_mapping_optional(self) -> None:
        args = _parse("update", "--input", "e.json", "--output", "n.json", "--ids", "magnetics")
        assert getattr(args, "mapping", None) is None or args.mapping is None

    def test_with_config_and_device(self) -> None:
        args = _parse(
            "update", "--input", "e.json", "--output", "n.json",
            "--ids", "magnetics", "--config", "munchi.toml", "--device", "jet",
        )
        assert args.config == "munchi.toml"
        assert args.device == "jet"


# ── completions ───────────────────────────────────────────────────────────────


class TestCompletionsParser:
    def test_bash(self) -> None:
        args = _parse("completions", "bash")
        assert args.shell == "bash"

    def test_zsh(self) -> None:
        args = _parse("completions", "zsh")
        assert args.shell == "zsh"

    def test_fish(self) -> None:
        args = _parse("completions", "fish")
        assert args.shell == "fish"

    def test_invalid_shell_fails(self) -> None:
        with pytest.raises(SystemExit):
            _parse("completions", "powershell")


# ── map new flags ─────────────────────────────────────────────────────────────


class TestMapNewFlags:
    def test_set_single(self) -> None:
        args = _parse("map", "--ids", "magnetics", "--set", "run.concurrency.mode=thread")
        assert args.set == ["run.concurrency.mode=thread"]

    def test_set_multiple(self) -> None:
        args = _parse(
            "map", "--ids", "magnetics",
            "--set", "run.concurrency.mode=thread",
            "--set", "run.concurrency.workers=4",
        )
        assert len(args.set) == 2

    def test_verbose_flag(self) -> None:
        args = _parse("map", "--ids", "magnetics", "--verbose")
        assert args.verbose is True

    def test_verbose_default_false(self) -> None:
        args = _parse("map", "--ids", "magnetics")
        assert args.verbose is False

    def test_shots(self) -> None:
        args = _parse("map", "--ids", "magnetics", "--shots", "47125", "47126")
        assert args.shots == [47125, 47126]

    def test_shot_range(self) -> None:
        args = _parse("map", "--ids", "magnetics", "--shot-range", "47125", "47130")
        assert args.shot_range == [47125, 47130]

    def test_shots_and_shot_range_mutually_exclusive(self) -> None:
        with pytest.raises(SystemExit):
            _parse("map", "--ids", "magnetics", "--shots", "47125", "--shot-range", "47125", "47130")

    def test_checkpoint(self) -> None:
        args = _parse("map", "--ids", "magnetics", "--checkpoint", "cp.json")
        assert args.checkpoint == "cp.json"

    def test_checkpoint_default_none(self) -> None:
        args = _parse("map", "--ids", "magnetics")
        assert args.checkpoint is None

    def test_dry_run(self) -> None:
        args = _parse("map", "--ids", "magnetics", "--dry-run")
        assert args.dry_run is True

    def test_limit(self) -> None:
        args = _parse("map", "--ids", "magnetics", "--limit", "20")
        assert args.limit == 20
