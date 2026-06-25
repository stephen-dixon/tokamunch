"""Integration tests for the tokamunch plugin system.

These tests exercise the full plugin load path — discovery, metadata
resolution, factory invocation, and registration — without requiring a real
libtokamap installation.  A fake entry point is injected via
``importlib.metadata`` mocking rather than a real setuptools install.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tokamunch.plugins import (
    DataSourceMetadata,
    LoadedPlugin,
    load_plugin,
)
from tokamunch.plugins.registry import _load_metadata

# ---------------------------------------------------------------------------
# Fake plugin objects used across the tests
# ---------------------------------------------------------------------------


class FakeDataSource:
    """Minimal PythonDataSourceProtocol-compatible data source."""

    def __init__(self, return_value: Any = 42) -> None:
        self._return_value = return_value
        self.calls: list[dict[str, Any]] = []

    def get(self, args: dict[str, Any]) -> Any:
        self.calls.append(args)
        return self._return_value


def fake_factory(config: dict[str, Any]) -> FakeDataSource:
    return FakeDataSource(return_value=config.get("value", 0))


PLUGIN_METADATA = DataSourceMetadata(
    name="fake",
    display_name="Fake Data Source",
    thread_safe=True,
    process_safe=True,
    description="Test-only data source.",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry_point(name: str, value: str, factory: Any) -> MagicMock:
    ep = MagicMock()
    ep.name = name
    ep.value = value
    ep.load.return_value = factory
    return ep


# ---------------------------------------------------------------------------
# Tests: metadata loading
# ---------------------------------------------------------------------------


def test_load_metadata_reads_plugin_metadata_from_module() -> None:
    """_load_metadata should find PLUGIN_METADATA defined in this test module."""
    meta = _load_metadata(__name__ + ":fake_factory", "fake")

    assert meta.name == "fake"
    assert meta.display_name == "Fake Data Source"
    assert meta.thread_safe is True
    assert meta.description == "Test-only data source."


def test_load_metadata_returns_default_when_not_defined() -> None:
    """Module without PLUGIN_METADATA should yield a safe default."""
    # Use a real stdlib module that definitely has no PLUGIN_METADATA.
    meta = _load_metadata("os:path", "no_meta_plugin")

    assert meta.name == "no_meta_plugin"
    assert meta.thread_safe is False
    assert meta.process_safe is True


def test_load_metadata_returns_default_on_import_error() -> None:
    meta = _load_metadata("nonexistent_xyz_module:factory", "missing_plugin")

    assert meta.name == "missing_plugin"
    assert meta.thread_safe is False


# ---------------------------------------------------------------------------
# Tests: load_plugin
# ---------------------------------------------------------------------------


def _patch_entry_points(eps: list[MagicMock]):
    return patch(
        "tokamunch.plugins.registry.entry_points",
        return_value=eps,
    )


def test_load_plugin_returns_loaded_plugin() -> None:
    ep = _make_entry_point("fake", __name__ + ":fake_factory", fake_factory)

    with _patch_entry_points([ep]):
        plugin = load_plugin("fake")

    assert isinstance(plugin, LoadedPlugin)
    assert callable(plugin.factory)
    assert isinstance(plugin.metadata, DataSourceMetadata)


def test_load_plugin_metadata_is_correct() -> None:
    ep = _make_entry_point("fake", __name__ + ":fake_factory", fake_factory)

    with _patch_entry_points([ep]):
        plugin = load_plugin("fake")

    assert plugin.metadata.name == "fake"
    assert plugin.metadata.thread_safe is True


def test_load_plugin_raises_on_missing_plugin() -> None:
    with (
        _patch_entry_points([]),
        pytest.raises(ValueError, match="No data-source plugin named 'fake'"),
    ):
        load_plugin("fake")


def test_load_plugin_raises_on_duplicate_plugin() -> None:
    ep1 = _make_entry_point("fake", __name__ + ":fake_factory", fake_factory)
    ep2 = _make_entry_point("fake", __name__ + ":fake_factory", fake_factory)

    with (
        _patch_entry_points([ep1, ep2]),
        pytest.raises(ValueError, match="Multiple data-source plugins"),
    ):
        load_plugin("fake")


# ---------------------------------------------------------------------------
# Tests: factory invocation and data source protocol
# ---------------------------------------------------------------------------


def test_factory_creates_data_source() -> None:
    ep = _make_entry_point("fake", __name__ + ":fake_factory", fake_factory)

    with _patch_entry_points([ep]):
        plugin = load_plugin("fake")

    data_source = plugin.factory({"value": 7})
    assert isinstance(data_source, FakeDataSource)


def test_data_source_get_is_callable() -> None:
    """Data source must implement get(args) — the libtokamap Python interface."""
    ds = FakeDataSource(return_value=99)
    result = ds.get({"shot": 12345})

    assert result == 99
    assert ds.calls == [{"shot": 12345}]


def test_data_source_satisfies_protocol() -> None:
    """FakeDataSource is structurally compatible with PythonDataSourceProtocol."""
    # This is a static check at runtime — isinstance with Protocol requires
    # runtime_checkable, so we just verify the attribute exists.
    ds = FakeDataSource()
    assert callable(getattr(ds, "get", None)), "get() must be callable"


# ---------------------------------------------------------------------------
# Tests: registration into a fake mapper
# ---------------------------------------------------------------------------


def test_register_plugin_into_fake_mapper() -> None:
    """Full path: load plugin → create data source → register with mapper."""

    class FakeMapper:
        def __init__(self) -> None:
            self.registered: dict[str, Any] = {}

        def register_python_data_source(self, name: str, obj: Any) -> None:
            self.registered[name] = obj

        def map(self, device: str, ids_path: str, args: dict[str, Any]) -> Any:
            source_name = ids_path.split("/")[0]
            source = self.registered[source_name]
            return source.get(args)

    ep = _make_entry_point("fake", __name__ + ":fake_factory", fake_factory)
    mapper = FakeMapper()

    with _patch_entry_points([ep]):
        plugin = load_plugin("fake")

    ds = plugin.factory({"value": 55})
    mapper.register_python_data_source("fake_source", ds)

    assert "fake_source" in mapper.registered

    result = mapper.map("device", "fake_source/signal", {"shot": 1})
    assert result == 55
    assert ds.calls == [{"shot": 1}]


# ---------------------------------------------------------------------------
# Tests: concurrency safety warning
# ---------------------------------------------------------------------------


def test_thread_unsafe_plugin_emits_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Thread-unsafe plugin + thread concurrency mode must log a warning."""
    import logging

    # Build a minimal CLIConfig with thread concurrency and an unsafe plugin.
    from tokamunch.core.config import (
        CLIConfig,
        ConcurrencyConfig,
        ConcurrencyMode,
        DataSourceConfig,
        MapperConfig,
        RunConfig,
    )
    from tokamunch.mapping.mapper_factory import create_mapper_from_config

    unsafe_metadata = DataSourceMetadata(name="unsafe", thread_safe=False)

    class UnsafeFactory:
        def __call__(self, config: dict[str, Any]) -> FakeDataSource:
            return FakeDataSource()

    ep = _make_entry_point("unsafe", __name__ + ":fake_factory", UnsafeFactory())

    cli_config = CLIConfig(
        mapper=MapperConfig(device="test", config="irrelevant.toml"),
        run=RunConfig(
            concurrency=ConcurrencyConfig(mode=ConcurrencyMode.THREAD, workers=2)
        ),
        data_sources=[
            DataSourceConfig(mapper_name="unsafe_src", plugin="unsafe", enabled=True)
        ],
    )

    # Patch entry_points and _load_metadata (to inject our unsafe metadata),
    # and _create_libtokamap_mapper (to skip the real libtokamap call).
    fake_mapper = MagicMock()
    fake_mapper.register_python_data_source = MagicMock()

    with (
        _patch_entry_points([ep]),
        patch(
            "tokamunch.plugins.registry._load_metadata",
            return_value=unsafe_metadata,
        ),
        patch(
            "tokamunch.mapping.mapper_factory._create_libtokamap_mapper",
            return_value=fake_mapper,
        ),
        caplog.at_level(logging.WARNING, logger="tokamunch.mapping.mapper_factory"),
    ):
        create_mapper_from_config(cli_config)

    assert any(
        "not thread-safe" in r.message for r in caplog.records
    ), "Expected a thread-safety warning in the log"
