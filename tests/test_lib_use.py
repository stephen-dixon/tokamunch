"""Tests demonstrating programmatic (library) use of tokamunch without a config file."""

from typing import Any

import tokamunch as tm
from tokamunch.mapping import collect_mapped_values
from tokamunch.selection import IdsSelection, SinglePathSelection

IDSHelper = tm.IDSHelper


# ---------------------------------------------------------------------------
# Minimal fakes — no config files, no CLI setup needed
# ---------------------------------------------------------------------------


class MissingMappingMapper:
    """Raises the standard 'no mapping' error for every path."""

    _PREFIX = "Mapping error: failed to find mapping for"

    def map(self, device: str, ids_path: str, args: dict) -> Any:
        raise RuntimeError(f"{self._PREFIX} {ids_path}")


class LookupMapper:
    """Returns values from a fixed dict; falls back to MissingMapping for unknown paths."""

    _PREFIX = "Mapping error: failed to find mapping for"

    def __init__(self, values: dict[str, Any], lengths: dict[str, int] | None = None):
        self._values = values
        self._lengths = lengths or {}

    def map(self, device: str, ids_path: str, args: dict) -> Any:
        if ids_path in self._lengths:
            return self._lengths[ids_path]
        if ids_path in self._values:
            return self._values[ids_path]
        raise RuntimeError(f"{self._PREFIX} {ids_path}")


def _make_ctx(
    mapper: Any,
    device: str = "dev",
    shot: int = 1,
    concurrency: tm.ConcurrencyConfig | None = None,
) -> tm.MappingContext:
    tokamap = tm.TokamapInterface(mapper, device, shot=shot)
    return tm.MappingContext(
        mapper=mapper,
        tokamap=tokamap,
        device=device,
        shot=shot,
        concurrency=concurrency or tm.ConcurrencyConfig(),
    )


def _ctx_with_schema(
    schema_paths: list[str],
    mapper: Any,
    device: str = "dev",
    shot: int = 1,
) -> tm.MappingContext:
    """MappingContext whose ids_helper returns a pre-built IDSHelper."""

    class CtxWithSchema(tm.MappingContext):
        def ids_helper(self, ids_name: str) -> IDSHelper:
            return IDSHelper(schema_paths)

    tokamap = tm.TokamapInterface(mapper, device, shot=shot)
    return CtxWithSchema(
        mapper=mapper,
        tokamap=tokamap,
        device=device,
        shot=shot,
    )


# ---------------------------------------------------------------------------
# TokamapInterface construction
# ---------------------------------------------------------------------------


class TestTokamapInterfaceConstruction:
    def test_shot_encoded_in_args(self) -> None:
        class CapturingMapper:
            def __init__(self):
                self.calls: list[tuple] = []

            def map(self, device, ids_path, args):
                self.calls.append((device, ids_path, args))
                return 42

        capturing = CapturingMapper()
        iface = tm.TokamapInterface(capturing, "mastu", shot=47125)
        iface.map("some/path")

        assert capturing.calls == [("mastu", "some/path", {"shot": 47125})]

    def test_no_shot_sends_empty_args(self) -> None:
        class CapturingMapper:
            def __init__(self):
                self.last_args: dict = {}

            def map(self, device, ids_path, args):
                self.last_args = args
                return 0

        capturing = CapturingMapper()
        iface = tm.TokamapInterface(capturing, "device")
        iface.map("x")

        assert capturing.last_args == {}

    def test_extra_args_merged_with_shot(self) -> None:
        class CapturingMapper:
            def __init__(self):
                self.last_args: dict = {}

            def map(self, device, ids_path, args):
                self.last_args = args
                return 0

        capturing = CapturingMapper()
        iface = tm.TokamapInterface(
            capturing, "device", shot=99, extra_args={"host": "localhost"}
        )
        iface.map("x")

        assert capturing.last_args == {"shot": 99, "host": "localhost"}


# ---------------------------------------------------------------------------
# MappingContext direct construction
# ---------------------------------------------------------------------------


class TestMappingContextDirectConstruction:
    def test_map_path_without_config(self) -> None:
        mapper = LookupMapper({"magnetics/time": 0.5})
        ctx = _make_ctx(mapper)
        assert ctx.tokamap.map("magnetics/time") == 0.5

    def test_cli_config_is_none_by_default(self) -> None:
        ctx = _make_ctx(LookupMapper({}))
        assert ctx.cli_config is None

    def test_default_concurrency_is_serial(self) -> None:
        ctx = _make_ctx(LookupMapper({}))
        assert ctx.concurrency.mode == tm.ConcurrencyMode.SERIAL

    def test_custom_concurrency_configurable(self) -> None:
        mapper = LookupMapper({})
        ctx = _make_ctx(
            mapper,
            concurrency=tm.ConcurrencyConfig(mode=tm.ConcurrencyMode.THREAD, workers=4),
        )
        assert ctx.concurrency.mode == tm.ConcurrencyMode.THREAD
        assert ctx.concurrency.workers == 4


# ---------------------------------------------------------------------------
# IDSHelper — direct construction from schema paths (no IDS name required)
# ---------------------------------------------------------------------------


class TestIDSHelperDirectConstruction:
    def test_build_from_schema_paths(self) -> None:
        helper = IDSHelper(
            [
                "magnetics/time",
                "magnetics/flux_loop(:)/field",
            ]
        )
        paths = set(helper.generate_non_concrete_paths())
        assert "magnetics/time" in paths
        assert "magnetics/flux_loop(:)/field" in paths

    def test_expand_concrete_paths(self) -> None:
        helper = IDSHelper(
            [
                "magnetics/flux_loop(:)",
                "magnetics/flux_loop(:)/field",
            ]
        )
        lengths = {"magnetics/flux_loop": 3}
        paths = list(helper.generate_concrete_paths(lengths.get, leaves_only=True))

        assert len(paths) == 3
        assert "magnetics/flux_loop[0]/field" in paths
        assert "magnetics/flux_loop[2]/field" in paths

    def test_reset_expansion_cache(self) -> None:
        helper = IDSHelper(["magnetics/flux_loop(:)/field"])
        call_count = 0

        def counting_lengths(path: str) -> int:
            nonlocal call_count
            call_count += 1
            return 2

        list(helper.generate_concrete_paths(counting_lengths))
        assert call_count == 1

        helper.reset_expansion_cache()
        list(helper.generate_concrete_paths(counting_lengths))
        assert call_count == 2


# ---------------------------------------------------------------------------
# collect_mapped_values — end-to-end programmatic use
# ---------------------------------------------------------------------------


class TestCollectMappedValuesLibUse:
    def test_single_path_mapped_successfully(self) -> None:
        ctx = _make_ctx(LookupMapper({"magnetics/time": 1.5}))
        sel = SinglePathSelection(path="magnetics/time")
        records, summary = collect_mapped_values(ctx, sel, verbose_errors=False)

        assert summary.total_paths == 1
        assert summary.mapped == 1
        assert records[0].value == 1.5

    def test_ids_selection_maps_all_concrete_paths(self) -> None:
        schema = ["magnetics/flux_loop(:)", "magnetics/flux_loop(:)/field"]
        mapper = LookupMapper(
            values={
                "magnetics/flux_loop[0]/field": 10.0,
                "magnetics/flux_loop[1]/field": 20.0,
            },
            lengths={"magnetics/flux_loop": 2},
        )
        ctx = _ctx_with_schema(schema, mapper)
        sel = IdsSelection(ids="magnetics", leaves_only=True)
        records, summary = collect_mapped_values(ctx, sel, verbose_errors=False)

        assert summary.total_paths == 2
        assert summary.mapped == 2
        by_path = {r.ids_path: r.value for r in records}
        assert by_path["magnetics/flux_loop[0]/field"] == 10.0
        assert by_path["magnetics/flux_loop[1]/field"] == 20.0

    def test_missing_mapping_error_suppressed(self) -> None:
        ctx = _make_ctx(MissingMappingMapper())
        sel = SinglePathSelection(path="magnetics/time")
        records, summary = collect_mapped_values(ctx, sel, verbose_errors=False)

        assert summary.suppressed_errors == 1
        assert summary.unexpected_errors == 0
        assert records[0].suppressed is True

    def test_mapping_keys_filter_excludes_unmatched_path(self) -> None:
        ctx = _make_ctx(LookupMapper({"magnetics/flux_loop[0]/field": 5.0}))
        keys = frozenset({"magnetics/flux_loop[#]/r"})
        sel = SinglePathSelection(
            path="magnetics/flux_loop[0]/field", mapping_keys=keys
        )
        _records, summary = collect_mapped_values(ctx, sel, verbose_errors=False)

        # path template is flux_loop[#]/field which is not in keys
        assert summary.total_paths == 0

    def test_process_concurrency_requires_cli_config(self) -> None:
        import pytest

        ctx = _make_ctx(
            LookupMapper({}),
            concurrency=tm.ConcurrencyConfig(
                mode=tm.ConcurrencyMode.PROCESS, workers=2
            ),
        )
        # cli_config is None when constructed directly without from_config()
        assert ctx.cli_config is None
        sel = SinglePathSelection(path="magnetics/time")
        with pytest.raises(RuntimeError, match="CLIConfig"):
            collect_mapped_values(ctx, sel, verbose_errors=False)
