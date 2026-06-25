"""Plugin system for tokamunch data sources.

Plugins implement the :class:`PythonDataSourceProtocol` and are registered via
setuptools entry points under the ``tokamunch.data_sources`` group.  Each
plugin module may optionally define a module-level ``PLUGIN_METADATA``
(:class:`DataSourceMetadata`) instance; a safe default is synthesised if
absent.
"""

from .api import DataSource, DataSourceFactory, MapperProtocol, PythonDataSourceProtocol
from .metadata import DataSourceMetadata
from .registry import LoadedPlugin, load_data_source_factory, load_plugin

__all__ = [
    "DataSource",  # backward-compat alias for PythonDataSourceProtocol
    "DataSourceFactory",
    "DataSourceMetadata",
    "LoadedPlugin",
    "MapperProtocol",
    "PythonDataSourceProtocol",
    "load_data_source_factory",
    "load_plugin",
]
