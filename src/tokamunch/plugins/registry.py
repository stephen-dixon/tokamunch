from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from importlib.metadata import entry_points

from .api import DataSourceFactory
from .metadata import DataSourceMetadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedPlugin:
    """A discovered and loaded data-source plugin.

    Bundles the factory callable with its associated metadata so callers can
    inspect safety properties (e.g. ``metadata.thread_safe``) before executing.
    """

    factory: DataSourceFactory
    metadata: DataSourceMetadata


def _load_metadata(ep_value: str, plugin_name: str) -> DataSourceMetadata:
    """Attempt to import the plugin module and read ``PLUGIN_METADATA``.

    ``ep_value`` is the raw entry-point value string, e.g.
    ``"my_package.datasource:factory"``.  If the module does not define
    ``PLUGIN_METADATA``, a safe default is returned.
    """
    module_name = ep_value.split(":")[0]
    try:
        module = importlib.import_module(module_name)
        meta = getattr(module, "PLUGIN_METADATA", None)
        if isinstance(meta, DataSourceMetadata):
            return meta
        if meta is not None:
            logger.warning(
                "Plugin %r: PLUGIN_METADATA is not a DataSourceMetadata instance "
                "(got %r) — using default metadata",
                plugin_name,
                type(meta).__name__,
            )
    except ImportError as exc:
        logger.debug(
            "Plugin %r: could not import module %r to read metadata: %s",
            plugin_name,
            module_name,
            exc,
        )

    return DataSourceMetadata(
        name=plugin_name,
        thread_safe=False,
        process_safe=True,
    )


def load_plugin(name: str) -> LoadedPlugin:
    """Load a data-source plugin by its entry-point name.

    Returns a :class:`LoadedPlugin` containing the factory and metadata.
    Raises :class:`ValueError` if the plugin is not found or ambiguous.
    """
    eps = entry_points(group="tokamunch.data_sources")
    matches = [ep for ep in eps if ep.name == name]

    if not matches:
        available = ", ".join(sorted(ep.name for ep in eps)) or "<none>"
        raise ValueError(
            f"No data-source plugin named {name!r} found. "
            f"Available plugins: {available}"
        )

    if len(matches) > 1:
        raise ValueError(f"Multiple data-source plugins named {name!r} found")

    ep = matches[0]
    factory: DataSourceFactory = ep.load()
    metadata = _load_metadata(ep.value, name)
    return LoadedPlugin(factory=factory, metadata=metadata)


def load_data_source_factory(name: str) -> DataSourceFactory:
    """Load only the factory for a data-source plugin.

    Prefer :func:`load_plugin` in new code so metadata is also available.
    """
    return load_plugin(name).factory
