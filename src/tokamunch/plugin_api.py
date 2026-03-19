from __future__ import annotations

from typing import Any, Protocol


class DataSourceFactory(Protocol):
    """
    Protocol for entry-point data-source factories.

    A factory receives plugin-specific configuration args and returns
    an object suitable for mapper.register_python_data_source(...).
    """

    def __call__(self, args: dict[str, Any]) -> Any: ...
