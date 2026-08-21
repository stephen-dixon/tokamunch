"""Backward-compatibility shim. Canonical location: tokamunch.plugins.api."""

from .plugins.api import (  # noqa: F401
    DataSource,
    DataSourceFactory,
    MapperProtocol,
    PythonDataSourceProtocol,
)
