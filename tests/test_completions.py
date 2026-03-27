"""Tests for tokamunch.completions — shell completion generation."""

from __future__ import annotations

from tokamunch.completions import (
    generate_bash_completion,
    generate_fish_completion,
    generate_zsh_completion,
    get_ids_names,
)


class TestGetIdsNames:
    def test_returns_list(self) -> None:
        names = get_ids_names()
        assert isinstance(names, list)

    def test_does_not_raise(self) -> None:
        # Should degrade gracefully if imas_data_dictionary not available.
        get_ids_names()

    def test_names_are_strings(self) -> None:
        for name in get_ids_names():
            assert isinstance(name, str)


class TestGenerateBashCompletion:
    def test_returns_nonempty_string(self) -> None:
        out = generate_bash_completion([])
        assert isinstance(out, str)
        assert len(out) > 0

    def test_contains_munchi(self) -> None:
        assert "munchi" in generate_bash_completion([])

    def test_contains_completion_function(self) -> None:
        assert "_munchi" in generate_bash_completion([])

    def test_ids_names_embedded(self) -> None:
        out = generate_bash_completion(["magnetics", "equilibrium"])
        assert "magnetics" in out
        assert "equilibrium" in out

    def test_subcommands_listed(self) -> None:
        out = generate_bash_completion([])
        for cmd in ("paths", "map", "convert", "init-config", "diff", "completions"):
            assert cmd in out

    def test_empty_ids_list_valid(self) -> None:
        # Should not raise and should produce valid script.
        out = generate_bash_completion([])
        assert "complete" in out


class TestGenerateZshCompletion:
    def test_returns_nonempty_string(self) -> None:
        out = generate_zsh_completion([])
        assert isinstance(out, str)
        assert len(out) > 0

    def test_contains_munchi(self) -> None:
        assert "munchi" in generate_zsh_completion([])

    def test_ids_names_embedded(self) -> None:
        out = generate_zsh_completion(["magnetics", "equilibrium"])
        assert "magnetics" in out
        assert "equilibrium" in out

    def test_subcommands_listed(self) -> None:
        out = generate_zsh_completion([])
        for cmd in ("paths", "map", "convert", "diff", "completions"):
            assert cmd in out


class TestGenerateFishCompletion:
    def test_returns_nonempty_string(self) -> None:
        out = generate_fish_completion([])
        assert isinstance(out, str)
        assert len(out) > 0

    def test_contains_munchi(self) -> None:
        assert "munchi" in generate_fish_completion([])

    def test_ids_names_embedded(self) -> None:
        out = generate_fish_completion(["magnetics", "equilibrium"])
        assert "magnetics" in out
        assert "equilibrium" in out

    def test_subcommands_listed(self) -> None:
        out = generate_fish_completion([])
        for cmd in ("paths", "map", "convert", "diff", "completions"):
            assert cmd in out
