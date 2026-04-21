"""Plugin system for tokamunch data sources.

Plugins implement the DataSource protocol and are registered via setuptools
entry points under the ``tokamunch.data_sources`` group.
"""

from .api import DataSource, DataSourceFactory, MapperProtocol
from .registry import load_data_source_factory

__all__ = [
    "DataSource",
    "DataSourceFactory",
    "MapperProtocol",
    "load_data_source_factory",
]
