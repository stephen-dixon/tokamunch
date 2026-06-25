from __future__ import annotations

from typing import Any, Protocol


class MapperProtocol(Protocol):
    """Protocol for the underlying mapper object (e.g. ``libtokamap.Mapper``).

    Typing ``TokamapInterface.mapper`` against this protocol allows tests and
    library users to supply a lightweight fake without installing libtokamap.
    """

    def map(self, device: str, ids_path: str, args: dict[str, Any]) -> Any: ...


class PythonDataSourceProtocol(Protocol):
    """Protocol for Python data source objects registered with libtokamap.

    libtokamap calls ``get(kwargs)`` on the registered Python object — passing
    all ``DataSourceArgs`` entries as a plain ``dict``.  Plugin implementations
    must satisfy this interface.

    The return type is intentionally ``Any``; callers should expect numpy
    arrays, scalars, or ``None``.
    """

    def get(self, args: dict[str, Any]) -> Any: ...


# Backward-compatible alias — prefer PythonDataSourceProtocol in new code.
DataSource = PythonDataSourceProtocol


class DataSourceFactory(Protocol):
    """Protocol for entry-point data-source factories.

    A factory receives plugin-specific configuration args and returns a
    ``PythonDataSourceProtocol``-compatible object suitable for
    ``mapper.register_python_data_source(...)``.
    """

    def __call__(self, config: dict[str, Any]) -> PythonDataSourceProtocol: ...
