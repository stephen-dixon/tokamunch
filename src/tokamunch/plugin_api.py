from __future__ import annotations

from typing import Any, Protocol


class MapperProtocol(Protocol):
    """Protocol for the underlying mapper object (e.g. ``libtokamap.Mapper``).

    Typing ``TokamapInterface.mapper`` against this protocol allows tests and
    library users to supply a lightweight fake without installing libtokamap.
    """

    def map(self, device: str, ids_path: str, args: dict[str, Any]) -> Any: ...


class DataSource(Protocol):
    """
    Protocol for data source objects registered with the mapper.

    The return type of map() is intentionally untyped (Any) to avoid
    introducing a numpy dependency solely for the type hint — callers
    should expect numpy arrays, scalars, or None.
    """

    def map(self, device: str, ids_path: str, args: dict[str, Any]) -> Any: ...


class DataSourceFactory(Protocol):
    """
    Protocol for entry-point data-source factories.

    A factory receives plugin-specific configuration args and returns
    an object suitable for mapper.register_python_data_source(...).
    """

    def __call__(self, args: dict[str, Any]) -> DataSource: ...
